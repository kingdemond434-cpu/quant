"""Download bars for ALL visible tradable MT5 symbols at EVERY timeframe, and build
universe.json. Runs on Windows where MetaTrader5 is installed. Then SCP to VPS.

Was H1-only, and not by choice -- see the TIMEFRAME_DEPTH block below.
"""
import json
import os
import sys
import time
from pathlib import Path

import MetaTrader5 as mt5
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from mt5desk.config import desk_root
from mt5desk.universe_registry import cost_fields_from_symbol_info, merge

# PATHS COME FROM `desk_root()`, NEVER A USERNAME (LAWS §1 anti-hardcode; the helper's own
# docstring records that twenty-one files hardcoded `C:\\Users\\dell\\...`, "which meant the desk
# could only ever run on one machine under one username"). This one never adopted it, so on the
# trading box it targeted a directory that does not exist -- which is why NOTHING on that box
# refreshes its bars and most of its 295 parquets were ~28h stale on 2026-08-27. `MT5_DESK_ROOT`
# still overrides, so a machine keeping its store elsewhere sets one env var.
#
# THE CALL SAT FOUR LINES ABOVE ITS OWN IMPORT until 2026-09-06, so this module raised
# `NameError: name 'desk_root' is not defined` at import and could not run AT ALL -- the fix that
# adopted desk_root() introduced the ordering fault in the same edit, and the two cancelled into
# a script that looks correct and has never once executed.
OUT_DIR = desk_root() / "data" / "universe"
OUT_DIR.mkdir(parents=True, exist_ok=True)

UNIVERSE_OUT = OUT_DIR / "universe.json"


# ONE LAYOUT. The desk keeps bars as `data/universe/<SYM>_<TF>.parquet` -- that is where
# `refresh_tail` reads them and where all 295 on the desk box actually live. A `parquets/`
# subdirectory would make this writer's `existing` check see an empty store and
# re-download the entire universe into a directory nothing else reads. The `<TF>` suffix is
# load-bearing, not decoration: it is how `refresh_tail` knows which timeframe to request from
# the terminal, so a file named without one cannot be kept current.
PARQUET_DIR = OUT_DIR
PARQUET_DIR.mkdir(parents=True, exist_ok=True)

mt5.shutdown()
time.sleep(1)
mt5.initialize()
info = mt5.terminal_info()
print(f"Terminal: {info.name}, connected={info.connected}")

syms = mt5.symbols_get()
tradable = [s for s in syms if s.visible and s.trade_mode > 0]
print(f"Tradable symbols: {len(tradable)}")

# Build universe.json + download bars at every eligible timeframe
universe = {}
failed = []
# EVERY TIMEFRAME IS ELIGIBLE, AND `existing` IS KEYED BY (SYMBOL, TIMEFRAME).
#
# It used to be keyed by SYMBOL alone, computed from `*_H1.parquet`. So the moment a symbol had
# an H1 file this downloader considered it finished and would never fetch a second timeframe for
# it -- not once, not ever. That is why the store held 82 symbols at H1 and exactly six non-H1
# files in total, all placed by hand: XAUUSD at M1/M5/M15 and three FX crosses at M15. The desk
# was structurally hourly-only and nothing said so; it looked like a choice.
#
# Depths are per timeframe so each covers a comparable SPAN rather than a comparable bar count:
# 50k bars is six years of H1 and thirty-five days of M1, and a scalp mechanism judged on
# thirty-five days of history is not judged at all.
TIMEFRAME_DEPTH: dict[str, int] = {
    "M1": 200_000, "M5": 120_000, "M15": 80_000, "M30": 60_000,
    "H1": 50_000, "H4": 30_000, "D1": 10_000,
}
_WANTED = [tf.strip().upper() for tf in
           os.environ.get("MT5_TIMEFRAMES", ",".join(TIMEFRAME_DEPTH)).split(",") if tf.strip()]
TIMEFRAMES = [tf for tf in _WANTED if tf in TIMEFRAME_DEPTH]
if not TIMEFRAMES:
    raise SystemExit(f"MT5_TIMEFRAMES={_WANTED} names no timeframe this desk stores "
                     f"({', '.join(TIMEFRAME_DEPTH)}) -- refusing to download nothing quietly")

existing = {(f.stem.rpartition("_")[0], f.stem.rpartition("_")[2])
            for f in PARQUET_DIR.glob("*.parquet") if "_" in f.stem}
print(f"Already downloaded: {len(existing)} (symbol, timeframe) series "
      f"across {len({s for s, _ in existing})} symbols")

jobs = [(s, tf) for s in tradable for tf in TIMEFRAMES if (s.name, tf) not in existing]
print(f"To download: {len(jobs)} series over timeframes {', '.join(TIMEFRAMES)}")

for i, (sym_info, tf) in enumerate(jobs):
    name = sym_info.name
    period = getattr(mt5, f"TIMEFRAME_{tf}", None)
    if period is None:
        print(f"  [{i+1}/{len(jobs)}] {name:25s} {tf:4s} NO SUCH TIMEFRAME IN MT5")
        failed.append(f"{name}_{tf}")
        continue
    point = sym_info.point
    digits = sym_info.digits
    spread_pts = sym_info.spread
    contract_size = getattr(sym_info, "trade_contract_size", 1.0)
    volume_min = sym_info.volume_min
    path = sym_info.path.replace("\\", "/")
    category = path.split("/")[0] if "/" in path else "Root"
    spread_price = spread_pts * point

    mt5.symbol_select(name, True)
    rates = mt5.copy_rates_from_pos(name, period, 0, TIMEFRAME_DEPTH[tf])

    if rates is None or len(rates) == 0:
        print(f"  [{i+1}/{len(jobs)}] {name:25s} {tf:4s} NO DATA")
        failed.append(f"{name}_{tf}")
        continue

    df = pd.DataFrame(rates)
    # utc=True IS LOAD-BEARING: MT5 `rates["time"]` is Unix EPOCH SECONDS, so the instants
    # are unambiguous, but pandas drops the tz label without it and `h1_source._normalise`
    # then REFUSES the file ("bar index is timezone-naive"). Five bulk downloaders omitted
    # it while every other producer passed it, so 173 of 197 H1 parquets were unreadable by
    # the shadow/forward chain -- a 197-symbol universe that was effectively 24 symbols.
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df.set_index("time", inplace=True)

    pq_path = PARQUET_DIR / f"{name}_{tf}.parquet"
    df.to_parquet(pq_path, engine="pyarrow")

    # THE REGISTRY ROW IS PER SYMBOL, NOT PER SERIES. point/digits/spread/contract_size are
    # properties of the instrument and identical at every timeframe, so the first series to
    # arrive writes them. Only the bar census below is timeframe-specific, and it is keyed as
    # such -- overwriting `bars`/`first_bar`/`last_bar` on each pass would leave the registry
    # describing whichever timeframe happened to be downloaded last.
    universe.setdefault(name, {}).setdefault("series", {})[tf] = {
        "bars": len(df), "first_bar": str(df.index[0]), "last_bar": str(df.index[-1]),
    }
    universe[name] |= {
        "point": point,
        "digits": digits,
        "tick_size": point,
        "median_spread_pts": spread_pts,
        "spread_price": round(spread_price, 6),
        "contract_size": contract_size,
        "volume_min": volume_min,
        "category": category,
        # THE FIELD WHOSE ABSENCE MAKES 42% OF THE UNIVERSE UNPRICEABLE. `tick_value` is the only
        # field carrying a price in ACCOUNT currency, so without it `spread_cost_per_lot` returns
        # 0.0 and gate 8 (stress_costs) cannot judge the candidate at all. Measured 2026-08-27:
        # 82 of 197 registry rows had none -- 67 Equities, 15 Indices, 23 uncategorised -- because
        # the ONLY producer that ever wrote it (`fetch_universe.py`) carries a hardcoded 32-symbol
        # list. The terminal has had the answer in hand on every one of these iterations and this
        # writer was dropping it. `currency_profit` rides along because it is MT5's OWN answer to
        # the denomination question, and it is the only correct route for a share or index CFD
        # whose name ("3M", "AUS200") carries no code to parse -- see universe_registry.
        **cost_fields_from_symbol_info(sym_info),
        # Kept for every reader that predates `series` and asks for the flat fields. They now
        # describe the LONGEST series held, which is the honest answer to "how much history is
        # there for this symbol" -- not whichever timeframe finished last.
        **max((s for s in universe[name]["series"].values()), key=lambda s: s["bars"]),
    }

    print(f"  [{i+1}/{len(jobs)}] {name:25s} {tf:4s} {len(df):7d} bars ({category})")

# Also load already-existing series into the universe, at every timeframe on disk.
for sym_name, sym_tf in sorted(existing):
    pq_path = PARQUET_DIR / f"{sym_name}_{sym_tf}.parquet"
    if not pq_path.exists():
        continue
    sym_info_list = [s for s in tradable if s.name == sym_name]
    if not sym_info_list:
        continue
    df_tmp = pd.read_parquet(pq_path)
    si = sym_info_list[0]
    path = si.path.replace("\\", "/")
    cat = path.split("/")[0] if "/" in path else "Root"
    row = universe.setdefault(sym_name, {})
    row.setdefault("series", {})[sym_tf] = {
        "bars": len(df_tmp), "first_bar": str(df_tmp.index[0]),
        "last_bar": str(df_tmp.index[-1]),
    }
    row |= {
        "point": si.point, "digits": si.digits, "tick_size": si.point,
        "median_spread_pts": si.spread,
        "spread_price": round(si.spread * si.point, 6),
        "contract_size": getattr(si, "trade_contract_size", 1.0),
        "volume_min": si.volume_min, "category": cat,
        **cost_fields_from_symbol_info(si),
        **max((s for s in row["series"].values()), key=lambda s: s["bars"]),
    }

mt5.shutdown()

# Save universe.json -- MERGED, never clobbered, and it now actually writes.
# TWO DEFECTS IN ONE LINE (measured 2026-08-27):
#   1. `json.dumps(..., encoding="utf-8")` raises `TypeError: JSONEncoder.__init__() got an
#      unexpected keyword argument 'encoding'` on every Python 3. This script did the ENTIRE
#      download -- hundreds of symbols, minutes of terminal I/O -- and then died on the write, so
#      nobody who ran it ever got a universe.json out of it. `encoding` belongs to write_text.
#   2. It CLOBBERED. `universe_registry` exists because three producers each wrote their own
#      field set over the others, and this script is named in its docstring as one of the three;
#      the merge it prescribes was never adopted here. A producer that does not know a field must
#      not be able to delete it.
_prior = {}
if UNIVERSE_OUT.exists():
    try:
        _prior = json.loads(UNIVERSE_OUT.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"  WARN: prior universe.json unreadable ({exc}); writing this run's rows alone")
        _prior = {}
_merged = merge(_prior, universe, source="download_all_symbols")
UNIVERSE_OUT.write_text(json.dumps(_merged, indent=2), encoding="utf-8")
print(f"universe.json: {len(universe)} row(s) this run merged into {len(_merged)} total")

# Summary
cats = {}
for k, v in universe.items():
    c = v.get("category", "Root")
    cats.setdefault(c, []).append(k)

print(f"\n{'='*60}")
print(f"UNIVERSE BUILT: {len(universe)} symbols")
for c in sorted(cats):
    print(f"  {c:20s}: {len(cats[c])} symbols")
print(f"Failed: {len(failed)}: {failed[:10]}")
print(f"\nSaved to: {UNIVERSE_OUT}")
print(f"Parquets: {PARQUET_DIR}")
