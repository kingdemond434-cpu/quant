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
import os
import shutil
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
#: EVERY PERIOD METATRADER 5 OFFERS -- all 21, not the seven this used to name. `_tf_const` already
#: resolves a chart by `getattr(mt5, f"TIMEFRAME_{name}")` and returns None when the terminal has
#: no such period, so a name here that a broker does not serve costs one skipped lookup and is
#: reported, never guessed. The seven were a list somebody typed; the terminal was always able to
#: give all of these.
#:
#: ORDERED BY VALUE PER BYTE, and the order is load-bearing on a box that runs out of disk. A run
#: cut short by space keeps whatever it fetched first, so the charts a desk actually expresses
#: strategies on come first: the seven originals, then the daily/weekly/monthly horizons (tiny and
#: genuinely different mechanisms), then the intraday swing charts, and last the sub-M5 periods
#: that are largely re-samplings of M1 and cost the most per unit of new information.
TIMEFRAMES: tuple[str, ...] = (
    "H1", "M15", "M5", "M30", "H4", "D1", "M1",          # the desk's working charts
    "W1", "MN1",                                          # slow horizons: kilobytes, new mechanisms
    "H2", "H3", "H6", "H8", "H12",                        # intraday swing
    "M2", "M3", "M4", "M6", "M10", "M12", "M20",          # sub-M5: most bytes, least new information
)

#: Bars per chart. MT5 caps a single request, and shorter charts need more rows to span the same
#: history: 50,000 M1 bars is ~35 trading days, while 50,000 H1 is ~8 years. Sized so every chart
#: covers a window long enough for the walk-forward and CPCV gates to have folds to work with.
#: The seven original depths are unchanged -- they were tuned against those gates -- and the new
#: charts are interpolated between their neighbours on the same span-not-count principle.
BARS = {
    "M1": 200_000, "M2": 200_000, "M3": 200_000, "M4": 200_000, "M5": 200_000,
    "M6": 180_000, "M10": 160_000, "M12": 155_000, "M15": 150_000, "M20": 130_000,
    "M30": 100_000, "H1": 50_000, "H2": 45_000, "H3": 40_000, "H4": 30_000,
    "H6": 25_000, "H8": 22_000, "H12": 18_000, "D1": 10_000, "W1": 3_000, "MN1": 1_000,
}


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

    # A DOWNLOAD MUST NEVER BE THE THING THAT FILLS THE DISK. Measured 2026-09-07: the box sat at
    # 0.964 GB free, and at that level a parquet write truncates, a git push dies as "the remote
    # end hung up unexpectedly", and a tick-tape append loses what it could not flush -- none of
    # which say "disk full". The full 21-chart lake is 10-20 GB; the box cannot hold it, and the
    # honest behaviour is to fetch what fits, in value order, and SAY where it stopped.
    #
    # The floor is generous on purpose: the tape appends continuously while this runs, and leaving
    # it a gigabyte of headroom costs a few charts that the next pass picks up anyway.
    # THE FLOOR IS WHAT THE REST OF THE BOX NEEDS, NOT WHAT THIS SCRIPT NEEDS.
    #
    # It was 2 GB, and that number is why the disk kept ending up full. This runs EVERY HOUR from
    # `hourly_cycle.refresh_bars`, and it downloads until free space reaches the floor -- so the
    # steady state of this box is "exactly the floor, forever". Two gigabytes is more than enough
    # for the next parquet and nowhere near enough for what else lives here: a `git pull` of this
    # repo unpacks and writes loose objects, the tick tape appends continuously and can never be
    # deleted, and the gauntlet writes a cache. Measured 2026-09-07, in this order: the lake
    # refilled to the floor, `git pull` died as "cannot write loose object file: No space left on
    # device", `git stash` could not save the worktree, and the box could not pull the fix for
    # what was wrong with it. None of those three announce themselves as a disk problem.
    #
    # 8 GB leaves room for a pull, a tape that grows ~0.2-0.5 GB a day, and the caches -- roughly
    # three weeks of tape growth before anything has to give, and `reclaim_disk` sheds the least
    # valuable charts if it ever does. Overridable per-box, because the right number is a
    # property of the disk this runs on and not of this file.
    floor_bytes = float(os.environ.get("BARS_MIN_FREE_GB", "8")) * (1024 ** 3)
    stopped_for_space = False

    # CHART-MAJOR, NOT SYMBOL-MAJOR, and on a disk-limited box this is the whole point of the
    # value ordering above. Symbol-major means a run that stops for space at symbol 120 leaves
    # symbols 121-250 with NO chart at all -- so the ordering by value would buy nothing, because
    # what got dropped is chosen by alphabet rather than by usefulness. Sweeping one chart across
    # every symbol before starting the next means an interrupted run leaves EVERY symbol holding
    # the charts the desk actually trades, and only the marginal periods are missing.
    got, skipped, empty = 0, 0, 0
    done_syms = 0
    for tf in charts:
        const = _tf_const(tf)
        if const is None:
            print(f"  {tf}: this terminal has no such period -- skipped, not guessed")
            continue
        if shutil.disk_usage(PARQUET_DIR).free < floor_bytes:
            stopped_for_space = True
            free_gb = shutil.disk_usage(PARQUET_DIR).free / (1024 ** 3)
            print(f"STOPPING before {tf} at {free_gb:.2f} GB free (floor "
                  f"{floor_bytes/(1024**3):.1f} GB): {got} chart(s) written. Every symbol holds "
                  f"the charts fetched before this one -- the desk's working set comes first by "
                  f"design. Free space and re-run, or narrow --timeframes.", file=sys.stderr)
            break
        for i, si in enumerate(tradable, 1):
            if shutil.disk_usage(PARQUET_DIR).free < floor_bytes:
                stopped_for_space = True
                print(f"STOPPING mid-{tf} at {i-1}/{len(tradable)} symbols: disk floor reached",
                      file=sys.stderr)
                break
            name = si.name
            done_syms = max(done_syms, i)
            out = PARQUET_DIR / f"{name}_{tf}.parquet"
            if out.exists() and not args.refresh:
                skipped += 1
                continue
            # ASK SMALLER WHEN THE TERMINAL SAYS NOTHING, because "nothing" is what MT5 returns
            # when the request EXCEEDS its Max-bars-in-chart setting -- not fewer bars, none at
            # all. Measured on the box 2026-09-07: H1 (50,000) and H4 (30,000) fetched 212 and
            # 50 charts, while M5 (200,000), M15 (150,000) and M30 (100,000) returned empty for
            # all 250 symbols -- roughly 750 empties in three charts. Read as "the broker has no
            # intraday history", which is false: the terminal simply holds fewer bars than asked
            # for, and the whole intraday and scalp universe was unreachable because of it.
            #
            # Halving down to a floor asks the same question in terms the terminal can answer.
            # The first non-empty answer is the deepest history it actually has, so this fetches
            # MORE data than a conservative fixed cap would, not less -- and a symbol that truly
            # has no history for a chart still ends at `empty`, reported as before.
            want = BARS.get(tf, 50_000)
            rates = None
            while want >= 2_000:
                rates = mt5.copy_rates_from_pos(name, const, 0, want)
                if rates is not None and len(rates):
                    break
                want //= 2
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
            # ZSTD, for the same reason the tick tape now uses it and with more force here: this
            # call runs 21 charts x 250 symbols, so an uncompressed default multiplies across the
            # whole lake. Measured 2026-09-07 on tick-shaped frames, zstd was x2.06 against the
            # pyarrow default of snappy, and OHLC bars are the same kind of data -- monotonic
            # timestamps, prices in a narrow band, small repeated volumes. The codec lives in the
            # file's own metadata, so every reader is unchanged: they pass none and get this.
            df.to_parquet(out, engine="pyarrow", compression="zstd")
            got += 1
            if i % 50 == 0:
                print(f"  {tf} [{i}/{len(tradable)}] {got} written, {skipped} present, "
                      f"{empty} empty", flush=True)
        print(f"  {tf}: done ({got} written so far, "
              f"{shutil.disk_usage(PARQUET_DIR).free/(1024**3):.2f} GB free)", flush=True)
        if stopped_for_space:
            break

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
