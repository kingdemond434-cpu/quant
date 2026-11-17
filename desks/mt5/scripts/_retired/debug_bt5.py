import pandas as pd
from mt5desk.families import get_family_func
from mt5desk import families
import numpy as np

df = pd.read_parquet("/home/quant/quant-platform/desks/mt5/data/universe/XAUUSD_H1.parquet")
h1 = families._h1(df)

print(f"Index tz: {h1.index.tz}")
print(f"Index[0]: {h1.index[0]}")
print(f"Index[0] type: {type(h1.index[0])}")

# Engine method
idx_ns = h1.index.astype("datetime64[ns]").astype("int64")
print(f"Engine idx_ns[0]: {idx_ns[0]}")
print(f"Engine idx_ns[10]: {idx_ns[10]}")

# Check signal
fn = get_family_func("session_range_breakout")
sigs = fn(h1, range_start=7, wait_bars=8, atr_n=20, ttl_bars=12, rr=2.0, signal_at=7, trend_filter="aligned")
s = sigs[0]
sig_ns = pd.Timestamp(s.time).value
print(f"Signal ns: {sig_ns}")

# Searchsorted with engine method
locs = np.searchsorted(idx_ns, [sig_ns])
print(f"locs: {locs}")