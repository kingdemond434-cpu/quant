#!/usr/bin/env python3
"""CARRY STATE (L1.5 / L1.28a / L1.59) -- the financing leg, per symbol, per SIDE, per night.

WHAT WAS MISSING. `grep -i swap desks/mt5/mt5desk/engine.py` returns ZERO hits: every backtest,
every gate, every certificate and every forward clock on this desk charges overnight financing at
exactly 0.00. `Costs` models spread and commission and stops there, and `book_years.py` lists "NO
SWAP" in its assumptions like a rounding disclaimer.

`mt5desk/financing.py` already measured the exposure and built the whole verdict API for it. It
concluded -- correctly for its sample -- that gold and AUDCAD carry roughly an order of magnitude
of headroom, and then wrote the sentence that closed the question:

    "Publishing it retires the worry permanently instead of leaving it to be re-raised by the
     next session that notices `Costs` has no swap field."

It also said exactly what would reopen it: *"WHAT THIS MODULE WILL NOT DO: INVENT THE RATE. The
honest input is the broker's actual swap table, and it is not in this repo."*

**IT IS IN THE REPO NOW, AND HAS BEEN SINCE 2026-08-26.** Two stores accrued it and nothing ever
read either one:

    desks/mt5/data/intelligence/broker_swaps/    82 hourly panels, 248 symbols  <- the SERIES
    desks/mt5/data/tape/contract_terms/          1 parquet, 1,908 rows          <- the UNITS

So `financing.assess()` has been returning UNMEASURED against an input sitting on disk. This
module is the missing half: it resolves those two stores into a rate in ACCOUNT CURRENCY PER LOT
PER NIGHT and hands it to the socket that was built for it.

================================================================================================
WHY IT IS A STATE AND NOT A CONSTANT -- MEASURED, and this was the falsifier
================================================================================================

The proposal that produced this module said: if nothing transitions, build a static cost field,
not a detector. Measured over the panel's own 3-day window (2026-08-26 -> 2026-08-29):

    81 OF 248 SYMBOLS REPRICED, and EURHKD's SHORT LEG CHANGED SIGN  -24.73 -> -11.88 -> +0.23

A symbol whose financed side flips from charged to paid inside three days is not a constant, and a
certificate minted before the flip is priced on a book the broker no longer runs. The detector is
justified by its own falsifier rather than by assertion.

================================================================================================
THE UNIT IS THE WHOLE TRAP, AGAIN, AND IT IS TWO TRAPS THIS TIME
================================================================================================

This desk has now paid three times for a unit that lives in a DIFFERENT field from the number it
governs: gold's spread in dollars-per-ounce into a per-lot field (3% of the real spread), the
CADJPY commission at 1/184th, and the pooled spread scalar standing in for a fill hour. Swap is
the same shape and is worse, because there are two conventions live at once:

    swap_mode == 1  SYMBOL_SWAP_MODE_POINTS            110 symbols -- swap is in POINTS
    swap_mode == 5  SYMBOL_SWAP_MODE_INTEREST_CURRENT  138 symbols -- swap is ANNUAL PERCENT

**138 of 248 symbols quote financing as a percentage per year.** A consumer reading `swap_long`
as currency-per-night is not out by a factor there -- it is out by a DIMENSION, on 55% of the
universe, and always in the direction that makes a candidate look cheaper than it is.

`libs/research/perishability.py` is the one module that documents the convention, and its comment
says *"In mode 0 (POINTS) the money value is swap*point*contract_size; in any other mode it is
already currency."* Both halves are wrong: mode 0 is DISABLED and mode 1 is POINTS, and mode 5 is
not currency at all. That comment is the desk's only written interpretation of this field, so it
is corrected in the same change as this build.

THE POINTS CONVERSION, and why it needs no assumption. `tick_value` is one `tick_size` of price
movement, for one lot, in the ACCOUNT's currency. So money per point is `tick_value * point /
tick_size`, and `point == 10**-digits` was checked against `tick_size` on all 248 symbols and
agrees on every one -- so the ratio is exactly 1 and the conversion is `swap_points *
tick_value`, measured rather than assumed.

The result was then checked against a quantity this desk does not control. EURUSD long computes
to -5.538 account currency per lot per night on a 100,000 notional, which annualises to
**-1.99%/yr** -- the EUR-minus-USD policy differential, to two significant figures, from a
completely independent direction. The units are right.

THE INTEREST CONVERSION, and the assumption it does carry. Mode 5 is an annual rate on the
position's notional, so it needs a PRICE and a day-count basis:

    money_per_night = (pct / 100) * price * (tick_value / tick_size) / DAY_COUNT

`DAY_COUNT` is a broker convention this desk has not read from the terminal. It is declared, it is
published in the artifact, and BOTH 360 and 365 are emitted so a consumer sees the band (1.4%
wide) instead of a point estimate wearing a hat. The price comes from the desk's own H1 close;
where there is no price series the cell is UNMEASURED with the blocker NAMED, never zero.

================================================================================================
WEDNESDAY IS NOT THE TRIPLE-SWAP DAY ON 150 OF 248 SYMBOLS
================================================================================================

`financing.TRIPLE_SWAP_WEEKDAY = 2` (Wednesday) is hardcoded for the whole universe, and its
docstring justifies it from T+2 spot settlement -- which is correct for spot FX and metals. The
broker publishes the real answer per symbol in `swap_rollover3days`, and it disagrees on the
majority:

    swap_rollover3days == 3  (Wednesday)   98 symbols
    swap_rollover3days == 5  (Friday)     150 symbols

`rollover_nights()` already accepts `triple_weekday` per call -- the parameter exists and nothing
has ever supplied it from the broker. `triple_weekday_for()` below is that supply. Counting the
triple on the wrong weekday misplaces 2/7 of the annual charge onto the wrong trades: it does not
change a symbol's annual cost, it changes WHICH sleeve pays it, which is exactly the error a
per-sleeve gate cannot see.

================================================================================================
WHAT THIS DOES NOT DO
================================================================================================

**IT DOES NOT GATE (L1.60).** The `state` label sorts and routes attention; it applies no
threshold to any promotion decision, in either direction. The canonical ten gates decide. The
number consumers act on is `swap_money_per_lot_night`, and the label exists so a human reading 248
rows can find the 30 that matter.

**IT DOES NOT INVENT A RATE.** Every cell that cannot be resolved carries `UNMEASURED` and a
named blocker. Zero is the specific wrong answer here -- it is the value the desk is already
carrying, so defaulting to it would launder the omission into a modelled assumption (L1.28a).

Run:   .venv/bin/python desks/mt5/research/carry_state.py [--out PATH]
Fence: scripts/check_carry_state.py
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

_DESK = Path(__file__).resolve().parent.parent
_PANEL = _DESK / "data" / "intelligence" / "broker_swaps"
_TERMS = _DESK / "data" / "tape" / "contract_terms"
_UNIVERSE = _DESK / "data" / "universe"
_OUT = _DESK / "data" / "carry_state.json"

CARRY_STATE_VERSION = "carry-state-2026-08-29-a"

#: MT5 ENUM_SYMBOL_SWAP_MODE. Only the two this broker actually uses are resolvable here; every
#: other mode is UNMEASURED with the mode number reported, never guessed into currency.
SWAP_MODE_DISABLED = 0
SWAP_MODE_POINTS = 1
SWAP_MODE_INTEREST_CURRENT = 5

#: Day-count basis for the mode-5 annual rate. A BROKER CONVENTION THIS DESK HAS NOT READ. Both
#: are emitted so the consumer sees the band rather than a point estimate; the 360/365 spread is
#: 1.4%, far below the dimension error this module exists to end, but it is declared because an
#: assumed input must be visible where the number is used and not in a docstring nobody opens.
DAY_COUNT = 360.0
DAY_COUNT_ALT = 365.0

#: MT5 ENUM_DAY_OF_WEEK is SUNDAY=0..SATURDAY=6; Python's `weekday()` is MONDAY=0..SUNDAY=6.
#: Off by one, silently, and both are small integers -- so a raw hand-off reads Wednesday as
#: Thursday and nothing raises.
_MT5_DAY_TO_PYTHON = {0: 6, 1: 0, 2: 1, 3: 2, 4: 3, 5: 4, 6: 5}

#: A night's CREDIT worth at least this share of one spread crossing is materially paid. Below it
#: the sign is real but the size is inside the noise of the spread the desk pays to get on.
PAID_RATIO = 0.02

#: A night's CHARGE worth at least this share of one spread crossing: five nights of holding costs
#: an extra round trip. A statable decision boundary, not a tuned one.
ADVERSE_RATIO = 0.20

#: Distinct panel observations a symbol needs before its transition history may be reported.
MIN_OBS = 2


def triple_weekday_for(rollover3days: int | None) -> int | None:
    """The Python weekday carrying the triple stamp, from the broker's own `swap_rollover3days`.

    This is the value `financing.rollover_nights(triple_weekday=...)` was built to accept and
    that nothing has ever supplied. Returns None for a broker value outside the enum, which
    `rollover_nights` already treats as "no weekend rule" -- the right refusal, since an
    unrecognised day must not silently become Wednesday.
    """
    if rollover3days is None:
        return None
    return _MT5_DAY_TO_PYTHON.get(int(rollover3days))


def _load_terms(terms_dir: Path) -> dict[str, dict[str, Any]]:
    """Latest contract terms per symbol -- the UNITS half. Empty dict if the tape is not here."""
    files = sorted(terms_dir.glob("*.parquet")) if terms_dir.exists() else []
    if not files:
        return {}
    frames = []
    for f in files:
        try:
            frames.append(pd.read_parquet(f))
        except (OSError, ValueError):
            continue
    if not frames:
        return {}
    df = pd.concat(frames, ignore_index=True).sort_values("observed_at")
    out: dict[str, dict[str, Any]] = {}
    for sym, row in df.groupby("symbol").last().iterrows():
        out[str(sym)] = {k: row[k] for k in row.index}
        out[str(sym)]["observed_at"] = str(row.get("observed_at", ""))
    return out


def _load_panel(panel_dir: Path) -> dict[str, list[tuple[str, float, float]]]:
    """Per-symbol swap SERIES from the hourly broker panel, oldest first."""
    series: dict[str, list[tuple[str, float, float]]] = {}
    if not panel_dir.exists():
        return series
    for f in sorted(panel_dir.glob("*.json")):
        try:
            rows = json.loads(f.read_text("utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(rows, list):
            continue
        for r in rows:
            if not isinstance(r, dict) or r.get("kind") != "swap_table":
                continue
            syms = r.get("symbols") or []
            if not syms:
                continue
            lo, sh = r.get("swap_long"), r.get("swap_short")
            if lo is None or sh is None:
                continue
            series.setdefault(str(syms[0]), []).append(
                (str(r.get("found_at", "")), float(lo), float(sh)))
    for v in series.values():
        v.sort()
    return series


def _last_close(symbol: str, universe_dir: Path) -> float | None:
    """The symbol's most recent H1 close -- the notional mode 5 is a percentage OF."""
    f = universe_dir / f"{symbol}_H1.parquet"
    if not f.exists():
        return None
    try:
        df = pd.read_parquet(f, columns=["close"])
    except (OSError, ValueError, KeyError):
        return None
    if df.empty:
        return None
    px = float(df["close"].iloc[-1])
    return px if px > 0 else None


def money_per_lot_night(swap: float, terms: dict[str, Any],
                        price: float | None, *,
                        day_count: float = DAY_COUNT) -> tuple[float | None, str]:
    """One side's financing in ACCOUNT CURRENCY per lot per night, or None and the reason why.

    POSITIVE IS A CREDIT -- the broker pays the desk to hold. This is MT5's own sign convention
    and it is preserved deliberately: `financing.drag_r` wants a positive COST, so the caller
    negates, and publishing both directions under one ambiguous name is how a sign flip ships.
    """
    mode = terms.get("swap_mode")
    if mode is None:
        return None, "no swap_mode: the unit is unknown and the number is uninterpretable"
    mode = int(mode)
    tick_value = float(terms.get("tick_value") or 0.0)
    tick_size = float(terms.get("tick_size") or 0.0)

    if mode == SWAP_MODE_DISABLED:
        return 0.0, "swap disabled by the broker on this symbol (mode 0)"

    if mode == SWAP_MODE_POINTS:
        if tick_value <= 0:
            return None, "mode 1 (POINTS) needs tick_value to reach account currency; absent"
        return float(swap) * tick_value, "mode 1 (POINTS): swap_points * tick_value"

    if mode == SWAP_MODE_INTEREST_CURRENT:
        if price is None:
            return None, ("mode 5 (INTEREST_CURRENT) is an annual PERCENT of notional and needs "
                          "a price; no H1 series for this symbol on this box")
        if tick_value <= 0 or tick_size <= 0:
            return None, "mode 5 needs tick_value/tick_size to value the notional; absent"
        notional_acct = price * (tick_value / tick_size)
        return (float(swap) / 100.0) * notional_acct / day_count, (
            f"mode 5 (INTEREST_CURRENT): pct/100 * price * tick_value/tick_size / {day_count:.0f}"
            " -- day count is a DECLARED broker convention, not read from the terminal")

    return None, (f"swap_mode {mode} is not POINTS or INTEREST_CURRENT; this desk has not "
                  "established its unit and will not guess one")


def classify(money: float | None, spread_money: float | None) -> tuple[str, float | None]:
    """Descriptive state for one side. LABELS, never gates (L1.60).

    UNMEASURED and UNCLASSIFIED ARE DIFFERENT FACTS AND ARE NEVER COLLAPSED. The first says the
    financing rate itself is unknown -- no consumer may charge anything. The second says the rate
    is KNOWN but the symbol carries no spread basis to scale it against, so only the state label
    is unavailable; `swap_money_per_lot_night` is fully usable and MUST still be charged.

    This module's first run collapsed them and reported USDJPY -- a symbol on a LIVE forward clock,
    whose rate resolves cleanly to +3.843 per lot per night -- as UNMEASURED, because
    `median_spread_pts` is 0.0 for it (24 of 251 registry entries are). A consumer keyed on the
    label would then have refused a rate the desk had measured, which is the producer/consumer
    verdict collapse this desk keeps paying for, reproduced inside the module built to end it.
    """
    if money is None:
        return "UNMEASURED", None
    if not spread_money or spread_money <= 0:
        return "UNCLASSIFIED", None
    ratio = money / spread_money
    if ratio >= PAID_RATIO:
        return "CARRY-PAID", ratio
    if ratio <= -ADVERSE_RATIO:
        return "CARRY-ADVERSE", ratio
    return "CARRY-NEUTRAL", ratio


def _side_report(side: str, series: list[tuple[str, float, float]], idx: int,
                 terms: dict[str, Any], price: float | None,
                 spread_money: float | None) -> dict[str, Any]:
    values = [row[idx] for row in series]
    latest = values[-1]
    money, why = money_per_lot_night(latest, terms, price)
    money_alt = money_per_lot_night(latest, terms, price, day_count=DAY_COUNT_ALT)[0]
    state, ratio = classify(money, spread_money)

    prev = None
    since = series[0][0]
    for i in range(len(values) - 1, 0, -1):
        if values[i - 1] != latest:
            prev = values[i - 1]
            since = series[i][0]
            break
    prev_money = money_per_lot_night(prev, terms, price)[0] if prev is not None else None
    prev_state = classify(prev_money, spread_money)[0] if prev_money is not None else None

    return {
        "side": side,
        "swap_raw": latest,
        "swap_money_per_lot_night": None if money is None else round(money, 6),
        "swap_money_per_lot_night_365": None if money_alt is None else round(money_alt, 6),
        "swap_cost_per_lot_night": None if money is None else round(-money, 6),
        "state": state,
        "carry_ratio_vs_spread": None if ratio is None else round(ratio, 6),
        "unit": why,
        "n_obs": len(values),
        "n_distinct": len(set(values)),
        "changed_in_window": len(set(values)) > 1,
        "prev_swap_raw": prev,
        "prev_state": prev_state,
        "since": since,
        "sign_flipped": bool(prev_money is not None and money is not None
                             and (prev_money > 0) != (money > 0)),
    }


def build(panel_dir: Path | None = None, terms_dir: Path | None = None,
          universe_dir: Path | None = None) -> dict[str, Any]:
    panel_dir = panel_dir or _PANEL
    terms_dir = terms_dir or _TERMS
    universe_dir = universe_dir or _UNIVERSE

    panel = _load_panel(panel_dir)
    terms = _load_terms(terms_dir)
    reg_path = universe_dir / "universe.json"
    try:
        registry = json.loads(reg_path.read_text("utf-8"))
    except (OSError, ValueError):
        registry = {}

    symbols: dict[str, Any] = {}
    skipped: list[dict[str, str]] = []
    for sym, series in sorted(panel.items()):
        if len(series) < MIN_OBS:
            skipped.append({"symbol": sym, "why": f"only {len(series)} panel observation(s)"})
            continue
        t = terms.get(sym)
        if not t:
            skipped.append({"symbol": sym,
                            "why": "no contract_terms row: swap_mode unknown, unit unresolvable"})
            continue
        meta = registry.get(sym) or {}
        tick_value = float(t.get("tick_value") or 0.0)
        spread_pts = float(meta.get("median_spread_pts") or 0.0)
        spread_money = spread_pts * tick_value if (spread_pts > 0 and tick_value > 0) else None
        mode = int(t.get("swap_mode")) if t.get("swap_mode") is not None else None
        price = (_last_close(sym, universe_dir)
                 if mode == SWAP_MODE_INTEREST_CURRENT else None)

        roll = t.get("swap_rollover3days")
        roll = int(roll) if roll is not None else None
        symbols[sym] = {
            "symbol": sym,
            "asset_class": meta.get("asset_class"),
            "swap_mode": mode,
            "swap_rollover3days": roll,
            "triple_swap_weekday": triple_weekday_for(roll),
            "contract_size": float(t.get("contract_size") or 0.0),
            "tick_value": tick_value,
            "currency_profit": str(t.get("currency_profit") or ""),
            "price_used": price,
            "spread_money_per_lot": None if spread_money is None else round(spread_money, 6),
            "terms_observed_at": t.get("observed_at"),
            "first_obs": series[0][0],
            "last_obs": series[-1][0],
            "long": _side_report("long", series, 1, t, price, spread_money),
            "short": _side_report("short", series, 2, t, price, spread_money),
        }

    sides = [s[k] for s in symbols.values() for k in ("long", "short")]
    measured = [s for s in sides if s["swap_money_per_lot_night"] is not None]
    return {
        "version": CARRY_STATE_VERSION,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "panel": str(panel_dir),
        "terms": str(terms_dir),
        "day_count": DAY_COUNT,
        "day_count_alt": DAY_COUNT_ALT,
        "paid_ratio": PAID_RATIO,
        "adverse_ratio": ADVERSE_RATIO,
        "window_start": min((s["first_obs"] for s in symbols.values()), default=None),
        "window_end": max((s["last_obs"] for s in symbols.values()), default=None),
        "n_symbols": len(symbols),
        "n_skipped": len(skipped),
        "skipped": skipped[:50],
        "n_sides": len(sides),
        "n_measured_sides": len(measured),
        "n_unmeasured_sides": len(sides) - len(measured),
        "n_paid_sides": sum(1 for s in sides if s["state"] == "CARRY-PAID"),
        "n_adverse_sides": sum(1 for s in sides if s["state"] == "CARRY-ADVERSE"),
        "n_unclassified_sides": sum(1 for s in sides if s["state"] == "UNCLASSIFIED"),
        "n_changed_symbols": sum(1 for v in symbols.values()
                                 if v["long"]["changed_in_window"]
                                 or v["short"]["changed_in_window"]),
        "n_sign_flipped_sides": sum(1 for s in sides if s["sign_flipped"]),
        "symbols": symbols,
    }


def swap_per_lot(state: dict, symbol: str, side: str) -> float | None:
    """The COST per lot per night for `financing.assess(swap_per_lot=...)`, or None.

    Positive is a cost, which is `financing.drag_r`'s convention and the NEGATION of the artifact's
    published credit-positive field. The conversion lives here, once, rather than at each call
    site -- a sign convention re-derived per caller is a sign error waiting for its first consumer.

    None means the desk does not know, and every caller must pass it straight through to
    `assess()`, which renders it UNMEASURED. Substituting 0.0 reinstates exactly the defect this
    module exists to end (L1.28a).
    """
    sym = (state.get("symbols") or {}).get(symbol)
    if not sym:
        return None
    leg = sym.get(side)
    if not leg:
        return None
    # KEYED ON THE VALUE, NOT ON THE LABEL. Keying on `state` refused every UNCLASSIFIED side --
    # symbols whose rate is measured and whose spread basis merely is not -- and handed back None
    # for a number the desk holds. See `classify`.
    money = leg.get("swap_money_per_lot_night")
    return None if money is None else -float(money)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, default=_OUT)
    ap.add_argument("--panel", type=Path, default=None)
    ap.add_argument("--terms", type=Path, default=None)
    ap.add_argument("--universe", type=Path, default=None)
    args = ap.parse_args(argv)

    rep = build(args.panel, args.terms, args.universe)
    if not rep["symbols"]:
        print("carry_state: NO SYMBOLS RESOLVED -- refusing to write an empty carry state "
              f"(panel {args.panel or _PANEL}, terms {args.terms or _TERMS}). "
              "Unmeasured is not OK (L1.28a).")
        return 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(rep, indent=1, sort_keys=True) + "\n", "utf-8")

    print(f"carry_state: {rep['n_symbols']} symbols, {rep['n_sides']} sides, "
          f"{rep['n_measured_sides']} MEASURED, {rep['n_unmeasured_sides']} UNMEASURED, "
          f"{rep['n_skipped']} skipped -> {args.out}")
    print(f"  states: {rep['n_paid_sides']} CARRY-PAID, {rep['n_adverse_sides']} CARRY-ADVERSE, "
          f"{rep['n_unclassified_sides']} UNCLASSIFIED (rate known, no spread basis)")
    print(f"  transitions in {rep['window_start']} -> {rep['window_end']}: "
          f"{rep['n_changed_symbols']} symbols repriced, "
          f"{rep['n_sign_flipped_sides']} sides CHANGED SIGN")
    worst = sorted(({**s[k], "symbol": s["symbol"]}
                    for s in rep["symbols"].values()
                    for k in ("long", "short")
                    if s[k]["swap_money_per_lot_night"] is not None),
                   key=lambda v: v["swap_money_per_lot_night"])
    if worst:
        fmt = "{sym} {side} {v:+.3f}"
        heavy = [fmt.format(sym=s["symbol"], side=s["side"],
                            v=s["swap_money_per_lot_night"]) for s in worst[:5]]
        paid = [fmt.format(sym=s["symbol"], side=s["side"],
                           v=s["swap_money_per_lot_night"]) for s in worst[-5:][::-1]]
        print("  heaviest charges/lot/night: " + ", ".join(heavy))
        print("  largest credits/lot/night:  " + ", ".join(paid))
    return 0


if __name__ == "__main__":
    sys.exit(main())
