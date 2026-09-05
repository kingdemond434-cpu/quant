"""Merge MT5 symbol metadata into universe.json."""
import json
from pathlib import Path

PARQUET_DIR = Path(r"C:\Users\dell\mt5-research\data\mt5_universe\parquets")
UNIVERSE_OUT = Path(r"C:\Users\dell\mt5-research\data\mt5_universe\universe.json")
MT5_DATA = Path(r"C:\Users\dell\mt5-research\data\mt5_all_symbols.json")

mt5_all = json.loads(MT5_DATA.read_text())
existing = set(f.stem.replace("_H1", "") for f in PARQUET_DIR.glob("*_H1.parquet"))

universe = {}
for name in sorted(existing):
    if name in mt5_all:
        m = mt5_all[name]
        cat = m.get("path", "").split("\\")[0] if "\\" in m.get("path", "") else m.get("path", "").split("/")[0]
        universe[name] = {
            "point": m["point"], "digits": m["digits"], "tick_size": m["point"],
            "median_spread_pts": m["spread"],
            "spread_price": round(m["spread"] * m["point"], 6),
            "contract_size": m.get("contract_size", 1.0),
            "volume_min": m.get("volume_min", 1),
            "category": cat, "bars": 0,
        }
    else:
        universe[name] = {
            "tick_size": 1e-5, "digits": 5, "median_spread_pts": 10,
            "contract_size": 1.0, "category": "Unknown", "bars": 0,
        }

UNIVERSE_OUT.write_text(json.dumps(universe, indent=2))

cats = {}
for k, v in universe.items():
    cats.setdefault(v["category"], []).append(k)
print(f"Universe: {len(universe)} symbols")
for c in sorted(cats):
    print(f"  {c:20s}: {len(cats[c])}")
