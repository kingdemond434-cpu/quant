"""Download H1 data for ALL visible tradable MT5 symbols and build universe.json.
Runs on Windows where MetaTrader5 is installed.
Then SCP to VPS.
"""
import json
import sys
import time
from pathlib import Path

import MetaTrader5 as mt5
import pandas as pd

# PATHS COME FROM `desk_root()`, NEVER A USERNAME (LAWS §1 anti-hardcode; the helper's own
# docstring records that twenty-one files hardcoded `C:\\Users\\dell\\...`, "which meant the desk
# could only ever run on one machine under one username"). This one never adopted it, so on the
# trading box it targeted a directory that does not exist -- which is why NOTHING on that box
# refreshes its bars and most of its 295 parquets were ~28h stale on 2026-08-27. `MT5_DESK_ROOT`
# still overrides, so a machine keeping its store elsewhere sets one env var.
OUT_DIR = desk_root() / "data" / "universe"
OUT_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from mt5desk.config import desk_root  # noqa: E402
from mt5desk.universe_registry import cost_fields_from_symbol_info, merge  # noqa: E402

UNIVERSE_OUT = OUT_DIR / "universe.json"


# ONE LAYOUT. The desk keeps H1 bars as `data/universe/<SYM>_H1.parquet` -- that is where
# `refresh_tail` reads them and where all 295 on the desk box actually live. A `parquets/`
# subdirectory would make this writer's `existing` check see an empty store and
# re-download the entire universe into a directory nothing else reads.
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

# Build universe.json + download H1 data
universe = {}
failed = []
existing = set(f.stem.replace("_H1", "") for f in PARQUET_DIR.glob("*_H1.parquet"))
print(f"Already downloaded: {len(existing)} symbols")

to_download = [s for s in tradable if s.name not in existing]
print(f"To download: {len(to_download)} symbols")

for i, sym_info in enumerate(to_download):
    name = sym_info.name
    point = sym_info.point
    digits = sym_info.digits
    spread_pts = sym_info.spread
    contract_size = getattr(sym_info, "trade_contract_size", 1.0)
    volume_min = sym_info.volume_min
    path = sym_info.path.replace("\\", "/")
    category = path.split("/")[0] if "/" in path else "Root"
    spread_price = spread_pts * point

    rates = mt5.copy_rates_from_pos(name, mt5.TIMEFRAME_H1, 0, 50000)

    if rates is None or len(rates) == 0:
        print(f"  [{i+1}/{len(to_download)}] {name:25s} NO DATA")
        failed.append(name)
        continue

    df = pd.DataFrame(rates)
    # utc=True IS LOAD-BEARING: MT5 `rates["time"]` is Unix EPOCH SECONDS, so the instants
    # are unambiguous, but pandas drops the tz label without it and `h1_source._normalise`
    # then REFUSES the file ("bar index is timezone-naive"). Five bulk downloaders omitted
    # it while every other producer passed it, so 173 of 197 H1 parquets were unreadable by
    # the shadow/forward chain -- a 197-symbol universe that was effectively 24 symbols.
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df.set_index("time", inplace=True)

    pq_path = PARQUET_DIR / f"{name}_H1.parquet"
    df.to_parquet(pq_path, engine="pyarrow")

    universe[name] = {
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
        "bars": len(df),
        "first_bar": str(df.index[0]),
        "last_bar": str(df.index[-1]),
    }

    print(f"  [{i+1}/{len(to_download)}] {name:25s} {len(df):6d} bars ({category})")

# Also load already-existing into universe
for sym_name in existing:
    if sym_name not in universe:
        pq_path = PARQUET_DIR / f"{sym_name}_H1.parquet"
        if pq_path.exists():
            df_tmp = pd.read_parquet(pq_path)
            sym_info_list = [s for s in tradable if s.name == sym_name]
            if sym_info_list:
                si = sym_info_list[0]
                path = si.path.replace("\\", "/")
                cat = path.split("/")[0] if "/" in path else "Root"
                universe[sym_name] = {
                    "point": si.point, "digits": si.digits, "tick_size": si.point,
                    "median_spread_pts": si.spread,
                    "spread_price": round(si.spread * si.point, 6),
                    "contract_size": getattr(si, "trade_contract_size", 1.0),
                    "volume_min": si.volume_min, "category": cat,
                    **cost_fields_from_symbol_info(si),
                    "bars": len(df_tmp),
                    "first_bar": str(df_tmp.index[0]),
                    "last_bar": str(df_tmp.index[-1]),
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
