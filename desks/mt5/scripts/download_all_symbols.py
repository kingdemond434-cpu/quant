"""Download H1 data for ALL visible tradable MT5 symbols and build universe.json.
Runs on Windows where MetaTrader5 is installed.
Then SCP to VPS.
"""
import MetaTrader5 as mt5
import pandas as pd
import json
import time
import os
from pathlib import Path

OUT_DIR = Path(r"C:\Users\dell\mt5-research\data\mt5_universe")
OUT_DIR.mkdir(parents=True, exist_ok=True)

UNIVERSE_OUT = OUT_DIR / "universe.json"
PARQUET_DIR = OUT_DIR / "parquets"
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
                    "bars": len(df_tmp),
                    "first_bar": str(df_tmp.index[0]),
                    "last_bar": str(df_tmp.index[-1]),
                }

mt5.shutdown()

# Save universe.json
UNIVERSE_OUT.write_text(json.dumps(universe, indent=2, encoding="utf-8"))

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
