import MetaTrader5 as mt5
import pandas as pd
from pathlib import Path

PARQUET_DIR = Path(r"C:\Users\dell\mt5-research\data\mt5_universe\parquets")

mt5.initialize()
syms = mt5.symbols_get()
tradable = [s for s in syms if s.visible and s.trade_mode > 0]
existing = set(f.stem.replace("_H1", "") for f in PARQUET_DIR.glob("*_H1.parquet"))
missing = [s for s in tradable if s.name not in existing]

print(f"Missing: {len(missing)}")
for si in missing[:30]:
    rates = mt5.copy_rates_from_pos(si.name, mt5.TIMEFRAME_H1, 0, 10)
    n = len(rates) if rates is not None else 0
    print(f"  {si.name:25s} has {n:4d} bars  (visible={si.visible} mode={si.trade_mode})")

mt5.shutdown()
