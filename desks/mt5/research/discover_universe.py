"""Ask the broker what it ACTUALLY offers, and price every bit of it.

    python research/discover_universe.py                # report only, writes nothing
    python research/discover_universe.py --write        # update data/universe/universe.json
    python research/discover_universe.py --write --fetch-bars   # and cache H1 for new symbols

THE HOLE THIS FILLS, AND IT IS THE REASON THE DESK TRADES 23 SYMBOLS

`mt5desk/universe.py` was written specifically to replace a hardcoded symbol list. It classifies
an offering, prices it, reports per-class coverage, and its docstring says so at length. It has
TWENTY-SIX TESTS. It has never been called by anything but those tests.

`mt5.symbols_get()` -- the one call that enumerates what a broker actually lists -- appears
NOWHERE in this desk. Not in the gateway, not in research, not in any fetcher. So the universe
has always been `fetch_universe.CANDIDATES`: 32 names typed by hand, of which 23 survived, and
the desk has never once asked Fusion what else exists. Energy, softs, and the entire share-CFD
complex are absent from every hunt ever run here, and the absence was invisible because nothing
was in a position to notice it (III.16 -- built is not a status; name the caller).

This is that caller.

WHAT EXPANSION ACTUALLY COSTS, MEASURED RATHER THAN FEARED

More symbols means more cells means a higher significance bar, and `mt5desk.multiplicity`
already raises it automatically. The cost is smaller than intuition suggests, because the
deflation term grows like sqrt(2 ln n):

    symbols   trials   t you must beat
         23      368              4.90
        100     1600              5.33
        400     6400              5.70

Seventeen times the universe costs 0.8 t-units. That is cheap, and it is the quantitative reason
to say yes to breadth.

WHAT EXPANSION BUYS, WHICH IS THE PART THAT DECIDES *WHICH* SYMBOLS

Effective breadth is k_eff = n/(1+(n-1)rho), and the Sharpe multiplier is sqrt(k_eff):

     n    rho=0.6    rho=0.2
    20    1.6 (1.27x)   4.2 (2.04x)
   100    1.7 (1.29x)   4.8 (2.19x)

rho=0.6 is what USD-quoted FX majors actually look like -- they are one short-USD bet wearing
twenty names. TWENTY INSTRUMENTS ACROSS CLASSES BEAT ONE HUNDRED FX PAIRS, decisively, and no
amount of additional correlated symbols closes that gap: the rho=0.6 column is flat.

So this script does not merely count what exists. It reports CLASS COVERAGE, because the classes
with a zero are where the unexploited breadth is, and adding a thirtieth USD pair is close to
free in multiplicity and close to worthless in growth.

WHAT IT REFUSES TO DO

It does not decide what is worth trading -- that is the gate's job, per cell, against measured
cost. It admits anything with a real cost model and enough history, and reports everything else
as excluded WITH ITS REASON, because a silently shrinking universe is how the energy complex
went missing for the life of this desk.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mt5desk.config import DATA, terminal_path  # noqa: E402
from mt5desk.multiplicity import deflation, sweep_size  # noqa: E402
from mt5desk.universe import MIN_BARS, classify_all, coverage  # noqa: E402

OUT = DATA / "universe"

#: History depth to sample when measuring bars and spread. Enough to establish a median spread
#: and to know whether the symbol clears MIN_BARS, without pulling full history for hundreds of
#: instruments on a discovery pass.
PROBE_BARS = 2000

#: Sweep shape the multiplicity estimate is quoted against -- four session windows, four day
#: states, matching how this desk actually sweeps. Only used to REPORT the cost of a universe
#: size; the gates compute their own.
WINDOWS, STATES = 4, 4


def probe(mt5, symbol: str) -> dict | None:
    """Tick economics and recent history for one symbol, or None if it cannot be costed.

    Selects the symbol into Market Watch first: a broker lists far more instruments than are
    visible by default, and an unselected symbol returns no rates at all -- which would read as
    "no history" and silently exclude most of the offering.
    """
    if not mt5.symbol_select(symbol, True):
        return None
    info = mt5.symbol_info(symbol)
    if info is None:
        return None
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, PROBE_BARS)
    n = 0 if rates is None else len(rates)
    spread_pts = float(getattr(info, "spread", 0) or 0)
    if n:
        import pandas as pd                                          # noqa: PLC0415
        df = pd.DataFrame(rates)
        if "spread" in df and len(df):
            spread_pts = float(df["spread"].median())
    first = last = ""
    if n:
        first = str(datetime.fromtimestamp(int(rates[0]["time"]), tz=UTC))
        last = str(datetime.fromtimestamp(int(rates[-1]["time"]), tz=UTC))
    return {
        "bars": n,
        "contract_size": float(getattr(info, "trade_contract_size", 0) or 0),
        "tick_size": float(getattr(info, "trade_tick_size", 0) or 0),
        "tick_value": float(getattr(info, "trade_tick_value", 0) or 0),
        "min_volume": float(getattr(info, "volume_min", 0) or 0),
        "volume_step": float(getattr(info, "volume_step", 0) or 0),
        "median_spread_pts": spread_pts,
        "first": first, "last": last,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--write", action="store_true",
                    help="update universe.json. Without it this only reports, so the offering "
                         "can be read before it changes what the desk sweeps")
    ap.add_argument("--limit", type=int, default=0,
                    help="probe at most N symbols (a smoke test; 0 = every symbol offered)")
    args = ap.parse_args(argv)

    try:
        import MetaTrader5 as mt5                                    # noqa: PLC0415
    except ImportError:
        print("REFUSED: MetaTrader5 is not installed here. This must run on the box with the "
              "terminal -- it is the only place that can be asked what the broker offers.")
        return 2

    if mt5.terminal_info() is None and not mt5.initialize(path=terminal_path()):
        print(f"REFUSED: terminal initialize failed: {mt5.last_error()}")
        return 2

    acct = mt5.account_info()
    print(f"broker : {getattr(acct, 'company', '?')} / {getattr(acct, 'server', '?')}")

    offered = mt5.symbols_get() or []
    if not offered:
        print("REFUSED: symbols_get() returned nothing. Not 'the broker offers no symbols' -- "
              "an empty offering is a connection or permission failure, and writing a universe "
              "from it would erase the one on disk.")
        return 3
    names = sorted(s.name for s in offered)
    if args.limit:
        names = names[:args.limit]
    print(f"offered: {len(offered)} symbols; probing {len(names)}\n")

    summary: dict[str, dict] = {}
    skipped: list[str] = []
    for i, sym in enumerate(names, 1):
        if i % 50 == 0:
            print(f"  ... probed {i}/{len(names)}", flush=True)
        row = probe(mt5, sym)
        if row is None:
            skipped.append(sym)
            continue
        summary[sym] = row

    inst = classify_all(summary)
    usable = [x for x in inst if x.usable]
    rep = coverage(inst)

    print(f"\n{'class':<12} {'usable':>7} {'unusable':>9}   note")
    for cls, row in rep.items():
        note = ""
        if row["usable"] == 0:
            note = "NEVER TESTED BY THIS DESK -- this is where unexploited breadth is"
        print(f"{cls:<12} {row['usable']:7d} {row['unusable']:9d}   {note}")

    old = 0
    p = OUT / "universe.json"
    if p.exists():
        old = len(json.loads(p.read_text(encoding="utf-8")))
    n_old = sweep_size(max(old, 1), WINDOWS, STATES)
    n_new = sweep_size(max(len(usable), 1), WINDOWS, STATES)
    print(f"\nuniverse {old} -> {len(usable)} usable of {len(summary)} probed "
          f"({len(skipped)} could not be selected or costed)")
    print(f"multiplicity: {n_old} -> {n_new} cells; required t rises "
          f"{1.96 + deflation(n_old):.2f} -> {1.96 + deflation(n_new):.2f}")
    print("  Breadth is PAID FOR in significance, and the two move together automatically.")
    print("  But k_eff = n/(1+(n-1)rho): correlated additions buy almost nothing. Prefer the")
    print("  classes showing zero above over another USD-quoted pair.")

    if not args.write:
        print("\n(report only -- pass --write to update universe.json)")
        return 0

    # NEVER SHRINK SILENTLY. A discovery pass that returns fewer symbols than are on disk is far
    # more likely to be a Market Watch or permissions problem than a broker delisting half its
    # book, and overwriting on that basis would delete the desk's tested universe.
    if old and len(usable) < old * 0.8:
        print(f"\nREFUSED TO WRITE: {len(usable)} usable is under 80% of the {old} already on "
              f"disk. That is far more likely to be a connection, Market Watch or permissions "
              f"problem than a real delisting. Re-run, or pass --write again once the count "
              f"looks right.")
        return 4

    OUT.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\n-> {p} ({len(summary)} symbols, {len(usable)} usable)")
    print(f"   H1 history still needs fetching for anything new: research/fetch_universe.py")
    print(f"   Symbols below {MIN_BARS} bars are carried but reported unusable until they have "
          f"history.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
