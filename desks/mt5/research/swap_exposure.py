"""HOW MUCH OF THIS BOOK IS FINANCED OVERNIGHT, AND WHAT RATE WOULD KILL IT.

`engine.Costs` charges spread and commission. It does not charge swap, and nothing on this desk
measured how much of the book is exposed to one -- so the omission has never been sized. This
script sizes it, per sleeve, from the same trades the projection reports.

It answers two questions and refuses the third:

    HOW OFTEN     -- the share of trades open across a rollover stamp, and the mean and p90
                     charged nights per trade, Wednesday counted triple (T+2 weekend roll).
    WHAT KILLS IT -- the nightly rate per lot at which each sleeve's measured expectancy reaches
                     exactly zero. This needs no broker table, which is why it is the output.
    WHAT IT COSTS -- REFUSED while `--swap-per-lot` is absent. The broker's table is not in this
                     repo; `gateway.py` reads realised swap off closed deals and is the honest
                     source. Reporting zero would launder the omission into an assumption.

    python desks/mt5/research/swap_exposure.py
    python desks/mt5/research/swap_exposure.py --swap-per-lot XAUUSD=12.5 --swap-per-lot AUDCAD=0.4

Writes desks/mt5/swap_exposure.json. Wired by `run_hunt11.py`'s cadence and safe to run alone --
it reads bars and writes one artifact, and places no orders.
"""
from __future__ import annotations

import argparse
import json
import sys
import warnings
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from mt5desk import families                                             # noqa: E402
from mt5desk.engine import Costs, run_backtest                           # noqa: E402
from mt5desk.financing import (                                          # noqa: E402
    FINANCING_VERSION, assess, profile, rollover_nights, stamp_provenance)

warnings.filterwarnings("ignore")

UNI = BASE / "data" / "universe"
OUT = BASE / "swap_exposure.json"

#: The four session windows the live book trades, copied from `portfolio_projection.py` rather
#: than re-derived. If those move and these do not, the exposure is measured on a book the desk no
#: longer runs -- which is why the artifact records them.
WINDOWS = {
    "asia": dict(range_start=7, wait_bars=12, rr=2.0, ttl_bars=12),
    "london_am": dict(range_start=10, range_end=13, signal_at=13, wait_bars=8, rr=2.0,
                      ttl_bars=12),
    "ny_open": dict(range_start=13, range_end=14, signal_at=14, wait_bars=12, rr=2.0, ttl_bars=12),
    "afternoon": dict(range_start=14, range_end=17, signal_at=17, wait_bars=8, rr=2.0,
                      ttl_bars=12),
}

#: THE DEPLOYED BOOK, READ RATHER THAN RE-GUESSED. The survivor cells carry a day-state filter
#: (TREND_DAY / NORMAL_DAY) that decides their sign: run unconditioned, three of the four AUDCAD
#: windows show NEGATIVE expectancy, because the cell the desk deploys is the conditioned subset
#: and the unconditioned parent is a different sleeve wearing the same name. Measuring exposure on
#: the parent and labelling it with the child's name is the error this constant exists to prevent.
PROJECTION = BASE / "portfolio_projection.json"

#: How far a rebuilt sleeve's expectancy may sit from the published one before the row is refused.
#: 0.002R is tight on purpose: the three gold cells that DO reproduce match to four decimals, so
#: anything looser would admit a sleeve that merely resembles the deployed one. Widening this to
#: make rows appear is the exact move that turns a refusal into a false measurement.
REPRO_TOLERANCE_R = 0.002


def _projection_costs(sym: str, meta: dict) -> Costs:
    """`portfolio_projection.py`'s cost construction, reproduced EXACTLY -- gold bug included.

    **THE GOLD SPREAD HERE IS THE DEFECT `Costs.from_symbol` WAS WRITTEN TO END, AND THE
    PROJECTION STILL CARRIES IT.** 0.48 is dollars per OUNCE passed into `spread_per_lot`, which
    wants dollars per lot; the engine divides by contract_size 100 and charges gold 0.0048/oz,
    about 3% of its measured 0.16/oz median. Every gold row in `portfolio_projection.json` is
    therefore very nearly spread-free, and the 3x cost stress meant to catch this stresses 3% to
    9%. `Costs.from_symbol` fixes it and the projection does not call it.

    It is reproduced rather than corrected because THIS script asks one question -- what the
    unmodelled swap does -- and silently repricing the book underneath that question would leave
    numbers matching nothing the desk has published, with two changes tangled in one artifact.
    The defect is reported in the artifact's `known_defects` and is a separate fix.

    The AUDCAD side is not stressed either: `mult` is effectively 1.0, so the spread is crossed
    once where a round trip crosses it twice.
    """
    return Costs(
        spread_per_lot=0.48 if sym == "XAUUSD" else max(
            meta["median_spread_pts"] * meta["tick_size"] * meta["contract_size"], 0.05),
        commission_per_lot=3.50, contract_oz=meta["contract_size"])


def stop_value_per_lot(trades, meta: dict) -> float:
    """MEDIAN money at risk per 1.0 lot, in account currency -- one R at full size.

    (stop_distance / tick_size) * tick_value, the conversion `book_sizing` documents. The naive
    `contract_size * stop_distance` returns yen on the JPY crosses and reads them as euros.

    MEDIAN, and over the RECENT regime rather than all history, for the reason book_sizing gives:
    gold traded at $1,300 in 2018 and $3,300 now, so a dollar-denominated stop has tripled. A
    breakeven swap computed against a 2018-weighted stop understates the rate by roughly that
    factor, in the direction that makes every sleeve look safe.
    """
    recent = [t for t in trades if pd.Timestamp(t.entry_time) >= pd.Timestamp(
        "2025-02-01", tz="UTC")] or list(trades)
    d = np.array([abs(t.entry - t.stop) / meta["tick_size"] * meta["tick_value"] for t in recent],
                 dtype=float)
    return float(np.median(d)) if len(d) else 0.0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--swap-per-lot", action="append", default=[], metavar="SYM=RATE",
                    help="MEASURED nightly swap per 1.0 lot, account currency. Absent -> "
                         "UNMEASURED, and only the breakeven is reported.")
    ap.add_argument("--json", action="store_true", help="print the artifact instead of a table")
    args = ap.parse_args()

    rates: dict[str, float] = {}
    for spec in args.swap_per_lot:
        sym, _, val = spec.partition("=")
        if not val:
            print(f"--swap-per-lot wants SYM=RATE, got {spec!r}", file=sys.stderr)
            return 2
        rates[sym.strip().upper()] = float(val)

    if not PROJECTION.exists():
        print(f"{PROJECTION.name} absent -- the deployed sleeve list is UNKNOWN on this clone, "
              "and guessing it would measure a book nobody runs", file=sys.stderr)
        return 3
    cells = json.loads(PROJECTION.read_text(encoding="utf-8"))["rows"]

    from research.run_hunt12 import day_states                            # noqa: PLC0415

    meta_all = json.loads((UNI / "universe.json").read_text(encoding="utf-8"))
    rows, worst, bars_cache, state_cache = [], None, {}, {}
    for cell in cells:
        sym, win, state = cell["sym"], cell["win"], cell.get("state")
        bars = UNI / f"{sym}_H1.parquet"
        if not bars.exists():
            rows.append({"name": cell["name"], "state": "ABSENT",
                         "why": f"{bars.name} not on this clone -- exposure UNMEASURED, not zero"})
            continue
        if sym not in bars_cache:
            # `_h1` AND THE PROJECTION'S OWN COST CONSTRUCTION, NOT from_symbol. Both are copied
            # deliberately: this script's job is to add ONE question to the deployed book, and a
            # sleeve whose trades do not reproduce the projection's is a different sleeve. Running
            # raw bars without `_h1` (which reindexes to a continuous hourly grid before dropping
            # gaps) moves every bar-counted `wait_bars`/`ttl_bars` across weekend gaps, and it
            # turned three of the four AUDCAD cells negative -- a discrepancy that was entirely
            # mine and would have been published as the desk's.
            bars_cache[sym] = families._h1(pd.read_parquet(bars))
        h1, meta = bars_cache[sym], meta_all[sym]
        sigs = families.family_session_range_breakout(h1, **WINDOWS[win])
        if state not in (None, "base"):
            if sym not in state_cache:
                state_cache[sym] = day_states(h1)
            days = state_cache[sym]
            sigs = [s for s in sigs if days.get(pd.Timestamp(s.time).date()) == state]
        trades = run_backtest(h1, sigs, _projection_costs(sym, meta)).trades
        if not trades:
            continue
        nights = [rollover_nights(pd.Timestamp(t.entry_time).to_pydatetime(),
                                  pd.Timestamp(t.exit_time).to_pydatetime())
                  for t in trades]
        prof = profile(nights)
        stop_v = stop_value_per_lot(trades, meta)
        exp_r = float(np.mean([t.r_multiple for t in trades]))

        # THE REPRODUCTION GUARD. A swap verdict is a claim about a SPECIFIC sleeve, and this
        # script rebuilds that sleeve from `WINDOWS[win]` -- the gold window config. The hunt12
        # survivor cells carry their own tuned parameters in `reports/hunt12_partial.json`, which
        # is NOT on this clone, so rebuilding them from the gold config produces a lookalike: same
        # name, same symbol, different trades. Measured here, AUDCAD_asia_TREND_DAY rebuilds at
        # +0.0802R against the +0.5295R the projection published -- a sleeve six times weaker
        # wearing the deployed one's name.
        #
        # So the expectancy is CHECKED against the published one and the row is REFUSED when it
        # does not reproduce. An unreproducible sleeve gets "we could not measure this", never a
        # breakeven computed off the wrong trades, which would be a precise-looking number about
        # a sleeve nobody runs (L1.28a).
        published = cell.get("exp")
        if published is not None and abs(exp_r - float(published)) > REPRO_TOLERANCE_R:
            rows.append({
                "name": cell["name"], "state": "NOT REPRODUCED", "symbol": sym, "window": win,
                "day_state": state, "expectancy_r": round(exp_r, 6),
                "expectancy_published": float(published), "trades": len(trades),
                "why": (f"rebuilt at {exp_r:+.4f}R against the published {float(published):+.4f}R "
                        f"(tolerance {REPRO_TOLERANCE_R}). This cell's parameters live in "
                        "reports/hunt12_partial.json, which is absent here, so it was rebuilt "
                        "from the gold window config and is a DIFFERENT sleeve. Swap exposure "
                        "UNMEASURED for it -- run this on the box that has the hunt reports")})
            continue

        v = assess(cell["name"], expectancy_r=exp_r, mean_nights=prof.mean_nights,
                   stop_value_per_lot=stop_v, swap_per_lot=rates.get(sym))
        row = {**asdict(v), "symbol": sym, "window": win, "day_state": state,
               "stop_value_per_lot": round(stop_v, 2), **asdict(prof)}
        rows.append(row)
        if v.breakeven_per_lot is not None and (
                worst is None or v.breakeven_per_lot < worst["breakeven_per_lot"]):
            worst = row

    art = {
        "version": FINANCING_VERSION,
        "stamp": stamp_provenance(),
        "rates_supplied": rates or None,
        "windows": {k: dict(v) for k, v in WINDOWS.items()},
        "rows": rows,
        "most_exposed": None if worst is None else worst["name"],
        "note": ("Swap is NOT in engine.Costs. Every net-R figure this desk publishes for a "
                 "crossing sleeve is therefore an upper bound, by the amount below."),
        "known_defects": [
            "portfolio_projection.py passes spread_per_lot=0.48 for XAUUSD -- dollars per OUNCE "
            "into a field wanting dollars per LOT. The engine divides by contract_size 100 and "
            "charges gold 0.0048/oz against a measured 0.16/oz median, so every gold row in "
            "portfolio_projection.json runs at ~3% of its real spread. Costs.from_symbol exists "
            "to prevent exactly this and the projection does not call it. Reproduced here "
            "verbatim so these rows match the published book; fixing it is a separate change.",
            "AUDCAD costs are built at mult=1.0 -- the spread crossed once, where a round trip "
            "crosses it twice.",
        ],
    }
    OUT.write_text(json.dumps(art, indent=1), encoding="utf-8")

    if args.json:
        print(json.dumps(art, indent=1))
        return 0

    print(f"OVERNIGHT FINANCING EXPOSURE   [{FINANCING_VERSION}]")
    print(stamp_provenance())
    print()
    print(f"{'sleeve':22s} {'trades':>7s} {'cross%':>7s} {'nights':>7s} {'p90':>4s} "
          f"{'exp R':>8s} {'1R/lot':>9s} {'kills it':>10s}")
    for r in rows:
        if r.get("state") in ("ABSENT", "NOT REPRODUCED"):
            print(f"{r['name']:22s} {r['state']}: {r['why']}")
            continue
        be = r["breakeven_per_lot"]
        print(f"{r['name']:22s} {r['trades']:7d} {r['crossing_rate']:7.1%} "
              f"{r['mean_nights']:7.3f} {r['p90_nights']:4d} {r['expectancy_r']:+8.4f} "
              f"{r['stop_value_per_lot']:9.2f} "
              f"{('n/a' if be is None else f'{be:,.2f}'):>10s}")
    if worst is not None:
        print()
        print(f"MOST EXPOSED: {worst['name']} -- {worst['why']}")
    print()
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
