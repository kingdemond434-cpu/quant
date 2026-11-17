"""Build universe.json from parquets only — no MT5 needed."""
import pandas as pd
import json
from pathlib import Path

PARQUET_DIR = Path(r"C:\Users\dell\mt5-research\data\mt5_universe\parquets")
UNIVERSE_OUT = Path(r"C:\Users\dell\mt5-research\data\mt5_universe\universe.json")

universe = {}
for pq in sorted(PARQUET_DIR.glob("*.parquet")):
    name = pq.stem.rpartition("_")[0] or pq.stem
    try:
        df = pd.read_parquet(pq)
        universe[name] = {
            "tick_size": 1e-5, "digits": 5, "median_spread_pts": 10,
            "contract_size": 1.0, "category": "Pending", "bars": len(df),
        }
    except:
        pass

UNIVERSE_OUT.write_text(json.dumps(universe, indent=2))
print(f"Universe: {len(universe)} symbols")
