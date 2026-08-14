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

**IT PLACES NOTHING BY DEFAULT.** It prints and journals intents. `--place` is deliberately absent:
routing to the venue goes through the same executor and risk kernel the carry path uses, and a
second, thinner order path built beside it is how two different sets of rails come to exist for one
book.

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

from libs.execution.discretionary_sleeve import (
    RuleSignal,
    SleeveState,
    journal,
    size_and_check,
)

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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--symbols", default="BTCUSDT,ETHUSDT")
    ap.add_argument("--equity", type=float, required=True,
                    help="deployable equity in USD -- required, never guessed: a fabricated "
                         "denominator sizes every position wrongly and silently")
    ap.add_argument("--realised-today", type=float, default=0.0)
    ap.add_argument("--open-positions", type=int, default=0)
    ap.add_argument("--min-notional", type=float, default=None,
                    help="venue minimum notional; omit only if genuinely unknown")
    ap.add_argument("--rule-id", default="H3_ict_sweep_shift")
    args = ap.parse_args()

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

    state = SleeveState(equity_usd=float(args.equity),
                        realised_pnl_today_usd=float(args.realised_today),
                        open_positions=int(args.open_positions))
    rows: list[dict[str, Any]] = []
    absent: list[str] = []
    for sym in symbols:
        df = frames.get(sym)
        if df is None or len(df) == 0:
            absent.append(sym)
            continue
        found = setups(df)
        if not found:
            continue
        # THE MOST RECENT SETUP ONLY. Replaying every historical setup as a live intent would
        # place a year of trades at once, and the older ones are not signals -- they are backtest
        # rows whose outcome is already known.
        sig = _to_signal(found[-1], sym, args.rule_id)
        decision = size_and_check(sig, state, min_notional_usd=args.min_notional)
        rows.append(journal(decision, _JOURNAL))
        if decision.take:
            state.open_positions += 1          # the concurrency cap binds WITHIN a run, not only across

    payload = {
        "updated": datetime.now(tz=UTC).isoformat(),
        "equity_usd": float(args.equity),
        "rule_id": args.rule_id,
        "n_intents": len(rows),
        "n_taken": sum(1 for r in rows if r.get("taken")),
        "absent_symbols": absent,
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
          f"{payload['n_taken']} would be taken, equity ${args.equity:,.2f}")
    for r in rows:
        mark = "TAKE  " if r.get("taken") else "REFUSE"
        print(f"  {mark} {r.get('symbol','?'):<10} {r.get('side','?'):<4} "
              f"qty={r.get('qty')} risk=${r.get('risk_usd')}")
        print(f"         {r.get('why','')[:160]}")
    if absent:
        print(f"  no bars for: {', '.join(absent)} -- UNMEASURED, not 'no setup'")
    print(f"-> {_JOURNAL} and {_OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
