"""Build universe.json from all downloaded parquets + MT5 symbol info."""
import MetaTrader5 as mt5
import pandas as pd
import json
from pathlib import Path

PARQUET_DIR = Path(r"C:\Users\dell\mt5-research\data\mt5_universe\parquets")
UNIVERSE_OUT = Path(r"C:\Users\dell\mt5-research\data\mt5_universe\universe.json")

mt5.initialize()
syms = {s.name: s for s in mt5.symbols_get()}
mt5.shutdown()

universe = {}
cats = {}
for pq in sorted(PARQUET_DIR.glob("*.parquet")):
    name = pq.stem.rpartition("_")[0] or pq.stem
    df = pd.read_parquet(pq)
    si = syms.get(name)
    if si:
        path = si.path.replace("\\", "/").split("/")
        cat = path[0] if len(path) > 1 else "Root"
        universe[name] = {
            "point": si.point, "digits": si.digits, "tick_size": si.point,
            "median_spread_pts": si.spread,
            "spread_price": round(si.spread * si.point, 6),
            "contract_size": getattr(si, "trade_contract_size", 1.0),
            "volume_min": si.volume_min, "category": cat,
            "bars": len(df),
        }
    else:
        universe[name] = {"tick_size": 1e-5, "digits": 5, "median_spread_pts": 10,
                          "contract_size": 1.0, "category": "Unknown", "bars": len(df)}
    cat = universe[name]["category"]
    cats.setdefault(cat, []).append(name)

UNIVERSE_OUT.write_text(json.dumps(universe, indent=2))
print(f"Universe: {len(universe)} symbols")
for c in sorted(cats):
    print(f"  {c:20s}: {len(cats[c])}")
