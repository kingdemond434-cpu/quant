"""Download every MT5 chart the desk can trade, INTO THE DIRECTORY THE DESK ACTUALLY READS.

THE TWO DEFECTS THIS FIXES, and between them they are why 15,275 of 23,465 docket cells were
refused at `symbol_eligibility` on 2026-09-06 -- 65% of everything the desk had mined, never
judged, because the bars were not there.

  1. IT WROTE SOMEWHERE NOTHING READS. `PARQUET_DIR` was
     `C:\\Users\\dell\\mt5-research\\data\\mt5_universe\\parquets` and `UNIVERSE_OUT` the
     universe.json beside it. The desk reads `desks/mt5/data/universe/`. Different directories,
     so every symbol this script fetched landed outside the tree the gauntlet, the backtest and
     the forward engine look in -- and its own `existing` check then read that same foreign
     directory, so it also believed the work was already done and skipped it next run. The
     download succeeded, the desk stayed blind, and nothing reported a contradiction.

  2. IT FETCHED ONLY H1. `mt5.TIMEFRAME_H1`, hardcoded, so no intraday chart existed for any
     symbol and every M1/M5/M15/M30/H4/D1 candidate was unrunnable by construction -- the desk
     could mine an intraday mechanism and never test one.

Both are the same species of defect the desk keeps finding: a producer that succeeds into a place
no consumer reads. The path is now DERIVED from this file's location, so it cannot drift from the
tree it belongs to, and the timeframes are a list rather than a literal.

    python scripts/download_remaining.py                    # every chart, missing symbols only
    python scripts/download_remaining.py --timeframes H1,M5 # a subset
    python scripts/download_remaining.py --refresh          # re-fetch symbols already present
    python scripts/download_remaining.py --wanted <file>    # only symbols named in a JSON list
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import MetaTrader5 as mt5
import pandas as pd

#: DERIVED, NEVER TYPED. `scripts/` -> `desks/mt5/` -> `data/universe`, the one directory
#: `run_external_backtest.bars`, `external_gauntlet` and `shadow_forward` all read. A literal
#: path here is what let the downloader and the desk disagree for as long as they did.
BASE = Path(__file__).resolve().parent.parent
PARQUET_DIR = BASE / "data" / "universe"
UNIVERSE_OUT = PARQUET_DIR / "universe.json"

#: Every chart the desk can express a strategy on. The gauntlet, the forward engine and the
#: universal executor all run a cell on its OWN timeframe, so a chart absent here is a whole
#: class of mechanism the desk cannot test -- not a smaller sample of the same one.
TIMEFRAMES: tuple[str, ...] = ("M1", "M5", "M15", "M30", "H1", "H4", "D1")

#: Bars per chart. MT5 caps a single request, and shorter charts need more rows to span the same
#: history: 50,000 M1 bars is ~35 trading days, while 50,000 H1 is ~8 years. Sized so every chart
#: covers a window long enough for the walk-forward and CPCV gates to have folds to work with.
BARS = {"M1": 200_000, "M5": 200_000, "M15": 150_000, "M30": 100_000,
        "H1": 50_000, "H4": 30_000, "D1": 10_000}


def _tf_const(name: str):
    """MT5's constant for a chart name, or None if this terminal has no such timeframe."""
    return getattr(mt5, f"TIMEFRAME_{name}", None)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--timeframes", default=",".join(TIMEFRAMES))
    ap.add_argument("--refresh", action="store_true",
                    help="re-fetch charts already on disk (default: only what is missing)")
    ap.add_argument("--wanted", default="",
                    help="JSON file holding a list of symbols to prioritise; others are skipped")
    args = ap.parse_args(argv)

    charts = [t.strip().upper() for t in args.timeframes.split(",") if t.strip()]
    PARQUET_DIR.mkdir(parents=True, exist_ok=True)

    if not mt5.initialize():
        # THE TERMINAL'S ABSENCE IS REPORTED, NOT ASSUMED AWAY. This script is scheduled on the
        # research VPS too, where there is no terminal; exiting 2 (this desk's UNANSWERED code)
        # distinguishes "no terminal here" from "fetched nothing", which look identical in a log.
        print(f"UNANSWERED: MT5 will not initialize ({mt5.last_error()}); no bars can be "
              f"fetched on this host", file=sys.stderr)
        return 2
    print(f"MT5 initialized -> writing into {PARQUET_DIR}")

    wanted: set[str] = set()
    if args.wanted:
        try:
            wanted = {str(s).upper() for s in json.loads(Path(args.wanted).read_text("utf-8"))}
            print(f"prioritising {len(wanted)} requested symbol(s)")
        except (OSError, ValueError) as exc:
            print(f"--wanted unreadable ({exc}); fetching the full tradable set instead")

    syms = mt5.symbols_get() or ()
    tradable = [s for s in syms if s.visible and s.trade_mode > 0]
    if wanted:
        tradable = [s for s in tradable if s.name.upper() in wanted] or tradable
    print(f"Tradable symbols: {len(tradable)}   charts: {', '.join(charts)}")

    got, skipped, empty = 0, 0, 0
    for i, si in enumerate(tradable, 1):
        name = si.name
        for tf in charts:
            const = _tf_const(tf)
            if const is None:
                continue
            out = PARQUET_DIR / f"{name}_{tf}.parquet"
            if out.exists() and not args.refresh:
                skipped += 1
                continue
            rates = mt5.copy_rates_from_pos(name, const, 0, BARS.get(tf, 50_000))
            if rates is None or len(rates) == 0:
                empty += 1
                continue
            df = pd.DataFrame(rates)
            # utc=True IS LOAD-BEARING: MT5 `rates["time"]` is Unix EPOCH SECONDS, so the
            # instants are unambiguous, but pandas drops the tz label without it and
            # `h1_source._normalise` then REFUSES the file ("bar index is timezone-naive").
            # Five bulk downloaders omitted it while every other producer passed it, so 173 of
            # 197 H1 parquets were unreadable by the shadow/forward chain -- a 197-symbol
            # universe that was effectively 24 symbols.
            df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
            df.set_index("time", inplace=True)
            df.to_parquet(out, engine="pyarrow")
            got += 1
        if i % 25 == 0:
            print(f"  [{i}/{len(tradable)}] {got} written, {skipped} present, {empty} empty",
                  flush=True)

    mt5.shutdown()
    print(f"Done: {got} chart(s) written, {skipped} already present, {empty} returned no data")

    # ---- universe.json: MERGED, never replaced -----------------------------------------------
    # A symbol the terminal cannot see this session (delisted, hidden, market closed) must not
    # lose its cost model -- every certificate on it becomes unpriceable and the gauntlet then
    # refuses it at `symbol_eligibility`, which is the exact failure this whole script exists to
    # end. So existing entries survive and are updated, never dropped.
    universe: dict = {}
    try:
        prior = json.loads(UNIVERSE_OUT.read_text("utf-8"))
        if isinstance(prior, dict):
            universe.update(prior)
    except (OSError, ValueError):
        pass
    before = len(universe)

    syms_map = {s.name: s for s in tradable}
    for pq in sorted(PARQUET_DIR.glob("*_*.parquet")):
        sym_name = pq.stem.rpartition("_")[0]
        if not sym_name:
            continue
        si = syms_map.get(sym_name)
        if si is None:
            continue                        # keep whatever entry it already had; never guess one
        path = si.path.replace("\\", "/").split("/")
        universe[sym_name] = {
            "point": si.point, "digits": si.digits, "tick_size": si.point,
            "median_spread_pts": si.spread,
            "spread_price": round(si.spread * si.point, 6),
            "contract_size": getattr(si, "trade_contract_size", 1.0),
            "volume_min": si.volume_min,
            "category": path[0] if len(path) > 1 else "Root",
            "charts": sorted(p.stem.rpartition("_")[2]
                             for p in PARQUET_DIR.glob(f"{sym_name}_*.parquet")),
        }
    UNIVERSE_OUT.write_text(json.dumps(universe, indent=2), encoding="utf-8")
    print(f"Universe: {len(universe)} symbols ({len(universe) - before:+d} this run)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
