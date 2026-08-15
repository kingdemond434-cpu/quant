#!/usr/bin/env python3
"""THE LAST LINK: a pre-registered ICT setup becomes a sized, risk-checked, journalled intent.

WHAT WAS ALREADY BUILT, AND IT IS MOST OF IT. `docs/research/DISCRETIONARY_PLAYBOOK_PREREGISTRATION.md`
carries the principal's playbook as H1-H11, pre-registered as testable hypotheses with their kill
filters declared as regime gates rather than smuggled in as sizing. H3 -- ICT/SMC -- is fully
implemented in `libs/ict/strategy.py`, and `setups()` returns an `ICTSetup` carrying `direction`,
`entry_price`, `stop` and `target`: a complete trade story with the bar index of every step it
actually reached.

WHAT WAS MISSING WAS THE ADAPTER, and only that. `libs/execution/discretionary_sleeve.RuleSignal`
requires exactly those fields, so the distance between a detected setup and a placeable intent was
a field mapping nobody had written. The strategy was never the gap; the wire was.

**THE PRE-REGISTRATION SURVIVES BECAUSE THIS TRANSLATES AND NEVER DECIDES.** Direction, entry, stop
and target all come from `ICTParams` and the detector. This script chooses no threshold, no filter
and no level. If it did, the playbook's pre-registration would be gone the moment it started
trading -- the terms would have been fixed before the data for the DETECTOR and after the data for
whatever this file added on top.

**IT PLACES NOTHING BY DEFAULT, AND `--place` GOES THROUGH THE SHARED PRIMITIVE.** Eleven rules
must not mean eleven sets of rails, so every order this script sends goes through
`libs.execution.spot_order_path.place_entry` -- the same rail check, arming check, free-cash clamp,
floor-to-the-cent and venue-held stop the momentum book uses. A second, thinner order path built
beside it is how two sets of rails come to exist for one book and drift apart silently.

**AND EVERY ENTRY RESTS A STOP AT THE VENUE.** Each hypothesis declares one; it is placed as a
STOP_LOSS_LIMIT immediately after the fill, sized from what actually filled. A stop that lives in
this journal is an intention that dies with the process.

    python scripts/run_discretionary_live.py --symbols BTCUSDT,ETHUSDT --equity 200
"""

from __future__ import annotations

# PATH BOOTSTRAP. `python scripts/x.py` puts scripts/ on sys.path, NOT the repo root.
import sys as _sys
from pathlib import Path as _P

if str(_P(__file__).resolve().parent.parent) not in _sys.path:
    _sys.path.insert(0, str(_P(__file__).resolve().parent.parent))

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from libs.discretionary import rules, tape
from libs.execution.discretionary_sleeve import (
    Decision,
    RuleSignal,
    SleeveState,
    journal,
    size_and_check,
)
from libs.execution.spot_order_path import place_entry

_JOURNAL = Path("data/discretionary_journal.jsonl")
_OUT = Path("web/discretionary_live.json")
_LAKE = "data/lake"

#: WHO IS FORCED TO TRADE AGAINST YOU -- the hunt's own admission criterion, answered once for this
#: family rather than re-invented per signal. A liquidity sweep IS the forced participant: stops
#: resting beyond a swing are not discretionary orders, they are orders that MUST execute when
#: touched, and the market-structure shift that follows is the evidence the flow was absorbed
#: rather than continued. A candidate that cannot name this is a pattern, not a mechanism.
_FORCED = ("stops resting beyond the swept swing -- they must fill when touched and cannot wait; "
           "the structure shift after the sweep is the evidence that flow was absorbed")


def _to_signal(setup: Any, symbol: str, rule_id: str) -> RuleSignal:
    """ICTSetup -> RuleSignal. A FIELD MAPPING, deliberately nothing more.

    Every number is carried through untouched. Rounding, clamping or 'improving' a stop here would
    move the pre-registered terms after the data arrived, which is the whole thing the playbook's
    pre-registration exists to prevent.
    """
    return RuleSignal(
        rule_id=rule_id,
        symbol=symbol,
        side="BUY" if int(setup.direction) > 0 else "SELL",
        entry_price=float(setup.entry_price),
        stop_price=float(setup.stop),
        target_price=float(setup.target),
        forced_participant=_FORCED,
        note=f"H3 ICT sweep->shift->entry at bars {setup.sweep_i}/{setup.shift_i}/{setup.entry_i}",
    )


_EXEC_REPORT = Path("web/spot_executor.json")


def _from_ict(setup: Any) -> rules.Setup:
    """ICTSetup -> the common Setup, so one adapter serves all eleven hypotheses.

    H3 predates the rest of the family and carries its own dataclass. Translating it here rather
    than giving it a second order path is the point: eleven rules with eleven routes to the venue
    is eleven sets of rails that can disagree.
    """
    return rules.Setup(
        rule_id="H3_ict_sweep_shift", direction=int(setup.direction),
        entry_price=float(setup.entry_price), stop=float(setup.stop),
        target=float(setup.target), bar=int(setup.entry_i),
        note=f"H3 ICT sweep->shift->entry at bars "
             f"{setup.sweep_i}/{setup.shift_i}/{setup.entry_i}")


def _resolve_equity(raw: str) -> tuple[float, str]:
    """A number, or the figure the spot executor last read FROM THE VENUE.

    Deliberately not a second venue read. The executor runs immediately before this in the cycle
    and already resolved equity against live balances; re-deriving it here would give two organs
    two answers on the same book, and the one that sized the orders is the one that is true.

    An ABSENT or STALE report refuses rather than falling back to a literal. A default denominator
    is the exact defect this replaces: it is right when written and silently wrong afterwards.
    """
    if str(raw).strip().lower() != "auto":
        try:
            return float(raw), f"stated by the caller: ${float(raw):,.2f}"
        except (TypeError, ValueError):
            return 0.0, f"--equity {raw!r} is neither a number nor 'auto'"
    try:
        rep = json.loads(_EXEC_REPORT.read_text("utf-8"))
        eq = float(rep["equity_usd"])
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return 0.0, (f"--equity auto, but {_EXEC_REPORT} is unreadable ({type(exc).__name__}). "
                     "Refusing rather than inventing a denominator: every intent below would be "
                     "sized against a number nobody measured")
    return eq, f"read from {_EXEC_REPORT}, which resolved it against live balances: ${eq:,.2f}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--symbols", default="BTCUSDT,ETHUSDT")
    ap.add_argument("--equity", required=True,
                    help="deployable equity in USD, or 'auto' to read the figure the spot "
                         "executor last published. Never guessed: a fabricated denominator sizes "
                         "every position wrongly and silently, and a LITERAL is a fabricated "
                         "denominator the moment the account moves")
    ap.add_argument("--realised-today", type=float, default=0.0)
    ap.add_argument("--open-positions", type=int, default=0)
    ap.add_argument("--min-notional", type=float, default=None,
                    help="venue minimum notional; omit only if genuinely unknown")
    ap.add_argument("--rule-id", default="H3_ict_sweep_shift",
                    help="label for the ICT detector only; every other rule carries its own id")
    ap.add_argument("--place", action="store_true",
                    help="ACTUALLY PLACE the taken intents, each with a venue-held stop. Absent, "
                         "this journals what it would do and spends nothing")
    ap.add_argument("--quote", default="USDT",
                    help="quote asset to trade in -- USDC for EEA retail, whose account may not "
                         "touch Binance USDT pairs under MiCA")
    ap.add_argument("--no-tape", action="store_true",
                    help="skip H4/H5. They read data/moat aggTrade partitions, which is a gzip "
                         "scan per symbol -- worth skipping on a clone with no tape, never on the "
                         "box that records it")
    ap.add_argument("--spot-only", action="store_true",
                    help="SPOT VENUE: refuse every short signal instead of placing it. Required "
                         "wherever derivatives are unavailable -- EEA retail under MiCA, which "
                         "includes Ireland")
    args = ap.parse_args()

    # THE RAILS ARE REPORTED HERE, NOT ENFORCED. This script places nothing, so a latched rail
    # cannot stop an order it never sends -- but an intent list printed during a freeze reads as a
    # book about to be taken, and whoever routes it by hand needs to see the freeze on the same
    # screen. Enforcement lives in the module that actually spends money.
    from libs.execution.ruin_rail import frozen
    rail_frozen, why_rail = frozen()

    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    try:
        from libs.autodiscovery.crypto_adapter import _read_frames
        from libs.data.timeframe import Timeframe
        from libs.ict.strategy import setups
        frames = _read_frames(symbols, Timeframe.D1, _LAKE)
    except Exception as exc:
        print(f"discretionary-live: inputs unreadable ({type(exc).__name__}: {exc}) -- UNMEASURED, "
              "nothing written. An empty intent list would read as 'the rule did not fire', which "
              "is a different and false claim")
        return 1

    equity, equity_why = _resolve_equity(args.equity)
    if equity <= 0:
        print(f"discretionary-live: {equity_why}")
        return 1
    state = SleeveState(equity_usd=equity,
                        realised_pnl_today_usd=float(args.realised_today),
                        open_positions=int(args.open_positions))
    rows: list[dict[str, Any]] = []
    absent: list[str] = []
    skipped_short: list[str] = []
    no_tape: list[str] = []
    placed: list[dict[str, Any]] = []
    # THE VENUE IS READ ONCE, not per rule. Eleven rules each fetching balances would be eleven
    # round trips describing eleven slightly different accounts.
    live_mod: Any = None
    place_ctx = None
    free_quote = 0.0
    steps: dict[str, float] = {}
    if args.place:
        from libs.execution import binance_spot_live
        live_mod = binance_spot_live
        place_ctx = True
        try:
            free_quote = float(live_mod.balances().get(args.quote, 0.0))
            steps = {k: float(v.get("step") or 0.0)
                     for k, v in live_mod.exchange_filters().items()}
        except Exception as exc:
            print(f"discretionary-live: venue unreadable ({type(exc).__name__}: {exc}) -- "
                  "refusing to place. Sizing against an unknown balance is how a sleeve spends "
                  "money it does not have")
            return 1
    cycle = datetime.now(tz=UTC).strftime("%Y%m%d")
    for sym in symbols:
        df = frames.get(sym)
        if df is None or len(df) == 0:
            absent.append(sym)
            continue
        # EVERY REGISTERED RULE, not just H3. The playbook pre-registers H1-H11; H3 lived in
        # libs/ict and the other ten had no detector, so a sleeve described as "the discretionary
        # book" was one hypothesis wide. libs/discretionary/rules holds the rest.
        found = [_from_ict(x) for x in setups(df)] + list(rules.detect(df))
        # H4 and H5 need the moat tape rather than candles, and NO TAPE is reported as no tape --
        # never as no setups, which would be a claim about the market rather than about the data.
        prof = None
        if not args.no_tape:
            trades = tape.load_trades(sym)
            prof = tape.volume_profile(trades)
            if prof is None:
                no_tape.append(sym)
            else:
                found.extend(rules.detect_with_tape(df, prof))
        if not found:
            continue
        # THE MOST RECENT SETUP PER RULE. Replaying every historical setup as a live intent would
        # place a year of trades at once, and the older ones are not signals -- they are backtest
        # rows whose outcome is already known. Per RULE rather than per symbol: keeping only one
        # would silently drop nine hypotheses' worth of evidence on any day two of them fire.
        latest: dict[str, Any] = {}
        for st in found:
            latest[st.rule_id] = st
        for st in latest.values():
            sig = _to_signal(st, sym, st.rule_id)
            # A SHORT ON A SPOT VENUE IS REFUSED, NEVER INVERTED AND NEVER SILENTLY DROPPED.
            # On spot a SELL closes a position you already hold; it does not open a short.
            # Inverting the direction would trade the OPPOSITE of the pre-registered hypothesis
            # under its name -- the journal would then record that rule's hit rate against trades
            # it never called for, which is worse than not trading it. Dropping it silently is the
            # other failure: the sleeve would look like a long-only book that fires half as often,
            # and nobody could tell that half its signals were unplaceable rather than absent.
            # THIS MATTERS MORE NOW THAT ELEVEN RULES RUN: H1, H7 and H11 are fade mechanisms and
            # will call shorts routinely, so on a spot account the refusal rate IS the measurement.
            if args.spot_only and sig.side == "SELL":
                skipped_short.append(f"{sym}:{st.rule_id}")
                rows.append(journal(Decision(
                    False, 0.0, 0.0,
                    f"SHORT REFUSED -- spot-only venue. {st.rule_id} called a short on {sym} and a "
                    "spot account cannot open one: a SELL here closes inventory rather than "
                    "opening a position. Recorded rather than dropped so the journal shows the "
                    "rule FIRED and the VENUE refused it, which is a different fact from the rule "
                    "staying silent",
                    dict(vars(sig))), _JOURNAL))
                continue
            decision = size_and_check(sig, state, min_notional_usd=args.min_notional)
            row = journal(decision, _JOURNAL)
            if decision.take:
                state.open_positions += 1      # the concurrency cap binds WITHIN a run too
                if args.place or place_ctx is not None:
                    # THE SLEEVE'S OWN RISK CHECK HAS ALREADY RUN. size_and_check owns
                    # per-trade risk, the daily loss cap and the concurrency cap; the order path
                    # owns the venue's rules and the rails. Neither re-implements the other, and
                    # an order reaching the venue has passed BOTH.
                    out = place_entry(
                        live_mod, sym, float(decision.notional_usd), cycle=cycle,
                        quote=args.quote, free_quote=free_quote,
                        min_notional=float(args.min_notional or 0.0) or 5.0,
                        stop_price=float(sig.stop_price), step=steps.get(sym, 0.0),
                        place=bool(args.place))
                    row["order"] = out.as_row()
                    placed.append(out.as_row())
                    if out.placed:
                        free_quote -= out.usd   # the next rule sees what this one left behind
            rows.append(row)

    payload = {
        "updated": datetime.now(tz=UTC).isoformat(),
        "equity_usd": equity,
        "equity_why": equity_why,
        "rule_id": args.rule_id,
        "n_intents": len(rows),
        "n_taken": sum(1 for r in rows if r.get("taken")),
        "absent_symbols": absent,
        "spot_only": bool(args.spot_only),
        "rail_frozen": rail_frozen,
        "rail_why": why_rail,
        "shorts_refused": skipped_short,
        "orders": placed,
        "placed": bool(args.place),
        "rules_run": sorted([args.rule_id, *rules.READY, *rules.TAPE_RULES]),
        "no_tape_symbols": no_tape,
        "still_blocked": rules.BLOCKED,
        "intents": rows,
        "note": ("Intents only -- nothing is placed here. Routing goes through the executor and "
                 "risk kernel the carry path already uses; a second, thinner order path beside it "
                 "is how one book comes to have two different sets of rails. Every decision is "
                 "journalled to data/discretionary_journal.jsonl INCLUDING refusals, because a "
                 "sleeve that records only its trades cannot tell a rule that fired twice from a "
                 "rule that fired forty times behind a binding risk cap."),
    }
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(payload, indent=1), "utf-8")

    print(f"discretionary-live [{args.rule_id}]: {len(rows)} intent(s), "
          f"{payload['n_taken']} would be taken, equity ${equity:,.2f}")
    if rail_frozen:
        print(f"  RUIN RAIL LATCHED -- these intents are NOT placeable until it is cleared. "
              f"{why_rail}")
    for r in rows:
        mark = "TAKE  " if r.get("taken") else "REFUSE"
        print(f"  {mark} {r.get('symbol','?'):<10} {r.get('side','?'):<4} "
              f"qty={r.get('qty')} risk=${r.get('risk_usd')}")
        print(f"         {r.get('why','')[:160]}")
    if skipped_short:
        print(f"  SHORTS REFUSED (spot-only): {', '.join(skipped_short)} -- the rule fired and the "
              "venue cannot place it, which is not the same as the rule staying silent")
    if no_tape:
        print(f"  NO TAPE for: {', '.join(no_tape)} -- H4/H5 are UNMEASURED on these, which is a "
              "statement about the recorder, not about the market")
    if absent:
        print(f"  no bars for: {', '.join(absent)} -- UNMEASURED, not 'no setup'")
    print(f"-> {_JOURNAL} and {_OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
