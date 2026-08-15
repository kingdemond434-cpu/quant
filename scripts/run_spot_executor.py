#!/usr/bin/env python3
"""THE ORDER PATH FOR THE SPOT BOOK -- target weights become real fills, or a stated refusal.

WHAT WAS ALREADY BUILT, WHICH IS ALMOST ALL OF IT. `libs/execution/binance_spot_live` is pinned to
api.binance.com, carries a three-part arming contract (keyfile + data/LIVE_ENABLE +
data/LIVE_VPS_VERIFIED), exposes `place_market_quote` sized in USDT, and stamps every order with an
idempotent client ID from `libs.execution.idempotency`. It has no withdrawal or transfer surface
and never will.

WHAT WAS MISSING WAS THE WIRE. `run_spot_momentum` published target weights and nothing turned them
into orders. This is that step and deliberately nothing more.

**IT TRADES THE DELTA, NEVER THE TARGET.** The account's CURRENT holdings are read from the venue
and subtracted first. Placing the target as if the book were empty would re-buy everything already
held on every run -- doubling the position daily while every printed weight still looked correct.
That is the single most expensive mistake available in this file and it is silent.

**DRY RUN IS THE DEFAULT AND `--place` IS THE ONLY WAY TO SPEND MONEY.** A flag that defaults to
placing is a flag somebody sets by forgetting.

**THE RUIN RAILS BIND HERE TOO.** `libs.execution.ruin_rail` is consulted before any order goes
out, and a latched rail refuses the whole run. The arming contract this module inherits from
`binance_spot_live` answers "may this box place orders at all"; it does NOT answer "is the book
frozen right now", and those came apart the moment a second order path existed: `CASHCARRY_KILL`
has been latched since 2026-08-01 and nothing on this path had ever read it.

**EVERY REFUSAL IS PRINTED AND JOURNALLED.** Below min-notional, below step size, arming missing,
cap exceeded -- each is stated with its arithmetic. A book that silently skipped a leg would leave
the operator believing they hold a position they do not.

**NO LEVERAGE EXISTS HERE AND NONE CAN BE ADDED.** Spot is 1x by construction: you hold what you
paid for. Margin is a different product with a different connector and a liquidation price, and
this module has no path to it.

    python scripts/run_spot_executor.py --equity 200                 # dry run, prints the deltas
    python scripts/run_spot_executor.py --equity 200 --place         # places them
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

_TARGETS = Path("data/spot_momentum.json")
_JOURNAL = Path("data/spot_executor_journal.jsonl")
_OUT = Path("web/spot_executor.json")

#: Hard ceiling on the total USDT this script may spend in ONE run, as a fraction of equity. Not a
#: risk knob: a bound on how wrong a single bad targets file can be. A corrupted weight set that
#: asked for 400% of equity would be refused rather than partially filled until the balance ran out.
MAX_RUN_FRAC = 1.0

#: Conservative floor used when the venue publishes no minimum for a symbol. exchange_filters
#: returns 0.0 in that case, and 0.0 would let a $0.30 order through to be rejected at the venue.
FALLBACK_MIN_NOTIONAL = 10.0

#: Quote suffixes the research universe may arrive in, longest first so BTCUSDT strips USDT rather
#: than matching a shorter suffix inside it. Order matters and is not alphabetical by accident.
_KNOWN_QUOTES = ("USDT", "USDC", "FDUSD", "TUSD", "EUR", "GBP", "BTC")


def retarget(symbol: str, quote: str) -> str:
    """Re-quote a research symbol onto the asset THIS ACCOUNT MAY ACTUALLY TRADE.

    WHY THIS IS NOT COSMETIC. Measured 2026-08-15: every order came back `-2010 This symbol is not
    permitted for this account`. Under MiCA, Binance does not permit EEA retail to trade its USDT
    spot pairs at all, and the desk's entire research universe is quoted in USDT because that is
    what the data lake holds. The signal is about the BASE asset -- BNB, LINK, ADA -- and the quote
    is a settlement detail of the venue, so re-quoting changes what is traded not at all and
    changes whether it CAN be traded completely.

    The bars stay USDT-denominated on purpose. USDT/USDC has traded within a few tens of basis
    points of parity for years, so a momentum rank over 20-day returns is unaffected; refitting the
    universe on thinner USDC history would change the measured signal for a reason that has nothing
    to do with the signal.
    """
    for q in _KNOWN_QUOTES:
        if symbol.endswith(q):
            return symbol[: -len(q)] + quote
    return symbol + quote


def _round_step(qty: float, step: float) -> float:
    """Down to the venue's step. ALWAYS DOWN: rounding up can exceed the intended weight and, on
    the last order of a book, the available balance."""
    if step <= 0:
        return qty
    return float(int(qty / step) * step)


def _load_targets() -> tuple[dict[str, float], str]:
    try:
        d = json.loads(_TARGETS.read_text("utf-8"))
    except (OSError, ValueError) as exc:
        return {}, (f"{_TARGETS} unreadable ({type(exc).__name__}) -- UNMEASURED. Refusing to "
                    "trade: an empty target book would read as 'go to cash' and would SELL "
                    "everything, which is a position nobody chose")
    w = d.get("target_weights")
    if not isinstance(w, dict) or not w:
        return {}, (f"{_TARGETS} carries no target_weights. Refusing rather than treating an "
                    "absent book as a flat one")
    return {str(k): float(v) for k, v in w.items()}, f"{len(w)} target weight(s)"


def _resolve_equity(raw: str, targets: dict[str, float], held: dict[str, float],
                    px: dict[str, float], quote: str) -> tuple[float, str]:
    """The denominator, from the venue when asked -- because a hand-typed one goes stale silently.

    MEASURED 2026-08-15, on the first live book: `--equity 198` was passed against a balance that
    had already lost the USDT->USDC conversion spread. Two legs filled, the third came back
    `Account has insufficient balance`, and the operator was left holding a two-thirds book. The
    number was right when it was typed and wrong by the time it was used, which is the whole
    argument for reading it.

    SCOPED, NOT THE WHOLE ACCOUNT. Only the free quote asset plus the coins this book targets are
    counted. A balance can hold positions put there for another reason -- another sleeve, a
    long-term hold, an airdrop -- and sweeping them into the denominator would size this book
    against capital that is already committed, then sell them to fund the difference.

    ALSO WHY IT IS NOT THE DEFAULT: an explicit number is a stated intent, and `auto` re-reads the
    account every run. On a book that is meant to compound, those are the same; on a book being
    deliberately sized down, they are not, and the caller says which one it means.
    """
    if str(raw).strip().lower() != "auto":
        try:
            return float(raw), f"stated by the caller: ${float(raw):,.2f}"
        except (TypeError, ValueError):
            return 0.0, f"--equity {raw!r} is neither a number nor 'auto'"
    total = float(held.get(quote, 0.0))
    parts = [f"{quote} {total:,.2f}"]
    for research_sym in targets:
        base = retarget(research_sym, "")
        qty = float(held.get(base, 0.0))
        if qty <= 0:
            continue
        price = float(px.get(retarget(research_sym, quote)) or 0.0)
        if price <= 0:
            # UNPRICED HOLDING: counting it as zero would understate equity and quietly shrink
            # every target; refusing is the honest move, since the alternative silently sells.
            return 0.0, (f"holding {base} cannot be priced in {quote} -- refusing to compute an "
                         "equity that would understate the book and trigger sells")
        total += qty * price
        parts.append(f"{base} {qty * price:,.2f}")
    return total, f"read from the venue: {' + '.join(parts)} = ${total:,.2f}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--equity", default=None,
                    help="deployable capital, or the literal 'auto' to read it from the venue. "
                         "AUTO IS SCOPED, NOT THE WHOLE ACCOUNT: it values the free quote asset "
                         "plus the coins this book targets, and nothing else -- a balance can hold "
                         "positions put there for another reason, and sweeping them into the book "
                         "would size against capital that is already committed")
    ap.add_argument("--place", action="store_true",
                    help="ACTUALLY PLACE ORDERS. Absent, this prints what it would do and spends "
                         "nothing")
    ap.add_argument("--max-run-frac", type=float, default=MAX_RUN_FRAC)
    ap.add_argument("--quote", default="USDT",
                    help="quote asset to TRADE in, independent of the quote the research universe "
                         "is denominated in. EEA retail cannot trade Binance USDT pairs under "
                         "MiCA (-2010) and must use USDC; the signal is about the base asset and "
                         "is unchanged by the settlement leg")
    ap.add_argument("--cycle", default=None,
                    help="idempotency scope; defaults to the UTC date so a re-run on the same day "
                         "reuses client order IDs and the venue rejects the duplicate")
    args = ap.parse_args()

    from libs.execution import binance_spot_live as live
    from libs.execution.ruin_rail import frozen

    if args.equity is None:
        ap.error("--equity is required: pass a number, or 'auto' to read it from the venue")
    cycle = args.cycle or datetime.now(tz=UTC).strftime("%Y%m%d")
    armed, why_armed = live.is_armed()
    rail_frozen, why_rail = frozen()
    # A LATCHED RAIL DOWNGRADES THE RUN TO A DRY RUN rather than aborting it. The operator still
    # gets the full delta table -- which is what tells them whether clearing the rail is even the
    # right move -- and every row says the rail refused it, so nobody reads the printed book as a
    # placed one.
    place = bool(args.place) and not rail_frozen
    targets, why_targets = _load_targets()

    rep: dict[str, Any] = {
        "updated": datetime.now(tz=UTC).isoformat(),
        "cycle": cycle, "armed": armed, "armed_why": why_armed,
        "rail_frozen": rail_frozen, "rail_why": why_rail, "quote": args.quote,
        "targets_why": why_targets,
        "placed": [], "refused": [], "dry_run": not place,
        "leverage": "1.0x -- SPOT HOLDS WHAT IT PAID FOR. No leverage exists on this path and "
                    "none can be added; margin is a different product with a different connector "
                    "and a liquidation price.",
    }

    if not targets:
        rep["refused"].append({"why": why_targets})
        print(f"spot-executor: {why_targets}")
        _OUT.parent.mkdir(parents=True, exist_ok=True)
        _OUT.write_text(json.dumps(rep, indent=1), "utf-8")
        return 1

    # CURRENT HOLDINGS FIRST. Reading the venue rather than a local file: a local position record
    # can drift from the account and the account is the only thing that is true.
    try:
        held = live.balances() if armed else {}
        px = live.prices()
        filters = live.exchange_filters()
    except Exception as exc:
        msg = (f"venue unreadable ({type(exc).__name__}: {exc}) -- refusing. Trading against an "
               "unknown position is how a rebalance becomes a doubling")
        rep["refused"].append({"why": msg})
        print(f"spot-executor: {msg}")
        _OUT.parent.mkdir(parents=True, exist_ok=True)
        _OUT.write_text(json.dumps(rep, indent=1), "utf-8")
        return 1

    equity, equity_why = _resolve_equity(args.equity, targets, held, px, args.quote)
    if equity <= 0:
        rep["refused"].append({"why": equity_why})
        print(f"spot-executor: {equity_why}")
        _OUT.parent.mkdir(parents=True, exist_ok=True)
        _OUT.write_text(json.dumps(rep, indent=1), "utf-8")
        return 1
    rep["equity_usd"], rep["equity_why"] = round(equity, 2), equity_why

    budget = equity * float(args.max_run_frac)
    spent = 0.0
    # WHAT IS ACTUALLY SPENDABLE, tracked down as orders fill. The target book is computed from
    # EQUITY, which includes coins already held; the cash available to buy with is a different and
    # smaller number. When they diverge -- and they always do, because the earlier legs were sized
    # before the last fill moved prices -- the final leg asks for more than the wallet holds and
    # the venue answers `-2010 Account has insufficient balance`. Measured 2026-08-15: two legs
    # filled, ADA wanted $39.96 against $36.21 free, and the book sat two-thirds complete.
    quote_free = float(held.get(args.quote, 0.0))
    for research_sym, frac in sorted(targets.items(), key=lambda kv: -kv[1]):
        sym = retarget(research_sym, args.quote)
        want_usd = frac * equity
        base = retarget(research_sym, "")
        price = float(px.get(sym) or 0.0)
        have_usd = float(held.get(base, 0.0)) * price
        delta = want_usd - have_usd            # THE DELTA, never the target
        f = filters.get(sym, {})
        min_notional = float(f.get("min_notional") or 0.0) or FALLBACK_MIN_NOTIONAL

        row: dict[str, Any] = {"symbol": sym, "research_symbol": research_sym,
                               "target_weight": frac,
                               "want_usd": round(want_usd, 2), "have_usd": round(have_usd, 2),
                               "delta_usd": round(delta, 2)}
        if price <= 0:
            row["why"] = (f"{sym} carries no price at the venue -- it may not be listed in "
                          f"{args.quote}. UNMEASURED, refusing to size against it")
            rep["refused"].append(row)
            continue
        if abs(delta) < min_notional:
            row["why"] = (f"delta ${abs(delta):,.2f} is below the venue minimum "
                          f"${min_notional:,.2f}. Rounding up would breach the intended weight "
                          "silently; the position stays where it is")
            rep["refused"].append(row)
            continue
        if delta > 0 and delta > quote_free:
            # CLAMP TO THE CASH, rather than letting the venue reject the whole leg. A slightly
            # underweight position is a book; a rejected order is a hole. The shortfall is stated
            # so nobody reads the filled weight as the intended one.
            short = delta - quote_free
            if quote_free < min_notional:
                row["why"] = (f"wants ${delta:,.2f} but only ${quote_free:,.2f} of {args.quote} is "
                              f"free, which is below the venue minimum ${min_notional:,.2f}. "
                              "Nothing placeable; the leg stays empty and says so")
                rep["refused"].append(row)
                continue
            row["clamped_from"] = round(delta, 2)
            row["shortfall_usd"] = round(short, 2)
            row["why_clamped"] = (
                f"sized to the ${quote_free:,.2f} of {args.quote} actually free rather than the "
                f"${delta:,.2f} the target asked for -- ${short:,.2f} short, so this leg lands "
                "UNDERWEIGHT and the next rebalance closes the gap")
            delta = quote_free
            row["delta_usd"] = round(delta, 2)
        if delta > 0 and spent + delta > budget:
            row["why"] = (f"would spend ${spent + delta:,.2f} of a ${budget:,.2f} run budget. "
                          "The cap bounds how wrong ONE bad targets file can be, so it refuses "
                          "rather than partially filling until the balance runs out")
            rep["refused"].append(row)
            continue
        if not armed:
            row["why"] = f"NOT ARMED -- {why_armed}"
            rep["refused"].append(row)
            continue

        side = "BUY" if delta > 0 else "SELL"
        row["side"] = side
        if rail_frozen:
            # NOT a dry run and not a venue rejection: the desk's own rail refused it. Named
            # separately so the journal can never be read as "the venue was fine with this".
            row["why"] = f"RUIN RAIL LATCHED -- {why_rail}"
            rep["refused"].append(row)
            continue
        if not place:
            row["why"] = "DRY RUN -- would place this; --place spends money"
            rep["placed"].append(row)
            if side == "BUY":
                spent += delta
                quote_free -= delta    # or the printed plan spends the same cash on every leg
            continue
        try:
            if side == "BUY":  # place=True here, so a rail is known clear
                res = live.place_market_quote(sym, "BUY", round(delta, 2), cycle=cycle)
                spent += delta
                quote_free -= delta        # the next leg sees what this one left behind
            else:
                # SELLING IS SIZED IN BASE, not quote: quoteOrderQty on a SELL asks the venue to
                # raise a dollar amount, and if the holding is a hair short the whole order fails.
                qty = _round_step(abs(delta) / price, float(f.get("step") or 0.0))
                res = live.place_market(sym, "SELL", qty, cycle=cycle)
            row["result"] = {k: res.get(k) for k in ("orderId", "status", "executedQty",
                                                     "cummulativeQuoteQty")}
            rep["placed"].append(row)
        except Exception as exc:
            row["why"] = f"ORDER REJECTED ({type(exc).__name__}: {exc})"
            rep["refused"].append(row)

    _JOURNAL.parent.mkdir(parents=True, exist_ok=True)
    with _JOURNAL.open("a", encoding="utf-8") as fh:
        for r in rep["placed"] + rep["refused"]:
            fh.write(json.dumps({"at": rep["updated"], "cycle": cycle, **r}) + "\n")
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(rep, indent=1), "utf-8")

    mode = "RAIL FROZEN" if rail_frozen else ("LIVE" if place else "DRY RUN")
    print(f"=== SPOT EXECUTOR [{mode}] === armed={armed} cycle={cycle} equity=${equity:,.2f}")
    if rail_frozen:
        print(f"  RUIN RAIL LATCHED -- nothing was placed. {why_rail}")
    for r in rep["placed"]:
        print(f"  {r.get('side','?'):<4} {r['symbol']:<10} ${abs(r['delta_usd']):>8,.2f}  "
              f"(target ${r['want_usd']:,.2f}, held ${r['have_usd']:,.2f})")
    for r in rep["refused"]:
        print(f"  SKIP {r.get('symbol','-'):<10} {str(r.get('why',''))[:110]}")
    if not place and not rail_frozen:
        print("  nothing was placed. add --place to spend money.")
    print(f"-> {_JOURNAL} and {_OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
