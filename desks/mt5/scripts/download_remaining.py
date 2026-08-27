"""Download remaining MT5 H1 data — fast batch version."""
import MetaTrader5 as mt5
import pandas as pd
import json
import time
from pathlib import Path

PARQUET_DIR = Path(r"C:\Users\dell\mt5-research\data\mt5_universe\parquets")
UNIVERSE_OUT = Path(r"C:\Users\dell\mt5-research\data\mt5_universe\universe.json")

mt5.initialize()
print("MT5 initialized")

syms = mt5.symbols_get()
tradable = [s for s in syms if s.visible and s.trade_mode > 0]
print(f"Tradable: {len(tradable)}")

existing = set(f.stem.replace("_H1", "") for f in PARQUET_DIR.glob("*_H1.parquet"))
to_dl = [s for s in tradable if s.name not in existing]
print(f"Already have: {len(existing)}, need: {len(to_dl)}")

for i, si in enumerate(to_dl):
    name = si.name
    rates = mt5.copy_rates_from_pos(name, mt5.TIMEFRAME_H1, 0, 50000)
    if rates is None or len(rates) == 0:
        print(f"  [{i+1}/{len(to_dl)}] {name} NO DATA")
        continue
    df = pd.DataFrame(rates)
    # utc=True IS LOAD-BEARING: MT5 `rates["time"]` is Unix EPOCH SECONDS, so the instants
    # are unambiguous, but pandas drops the tz label without it and `h1_source._normalise`
    # then REFUSES the file ("bar index is timezone-naive"). Five bulk downloaders omitted
    # it while every other producer passed it, so 173 of 197 H1 parquets were unreadable by
    # the shadow/forward chain -- a 197-symbol universe that was effectively 24 symbols.
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df.set_index("time", inplace=True)
    df.to_parquet(PARQUET_DIR / f"{name}_H1.parquet", engine="pyarrow")
    cat = si.path.replace("\\","/").split("/")[0] if "/" in si.path else "Root"
    print(f"  [{i+1}/{len(to_dl)}] {name:25s} {len(df):6d} bars ({cat})")

mt5.shutdown()
print("Done downloading")

# Build universe.json from all parquets + symbol info
syms_map = {s.name: s for s in tradable}
universe = {}
for pq in sorted(PARQUET_DIR.glob("*_H1.parquet")):
    sym_name = pq.stem.replace("_H1", "")
    si = syms_map.get(sym_name)
    df = pd.read_parquet(pq)
    if si:
        path = si.path.replace("\\","/").split("/")
        cat = path[0] if len(path) > 1 else "Root"
        universe[sym_name] = {
            "point": si.point, "digits": si.digits, "tick_size": si.point,
            "median_spread_pts": si.spread,
            "spread_price": round(si.spread * si.point, 6),
            "contract_size": getattr(si, "trade_contract_size", 1.0),
            "volume_min": si.volume_min, "category": cat,
            "bars": len(df),
        }
    else:
        universe[sym_name] = {"tick_size": 1e-5, "digits": 5, "median_spread_pts": 10,
                              "contract_size": 1.0, "category": "Unknown", "bars": len(df)}

UNIVERSE_OUT.write_text(json.dumps(universe, indent=2))
print(f"\nUniverse: {len(universe)} symbols")

cats = {}
for k, v in universe.items():
    cats.setdefault(v.get("category","?"), []).append(k)
for c in sorted(cats):
    print(f"  {c}: {len(cats[c])}")
