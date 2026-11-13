import pandas as pd
from mt5desk.families import get_family_func
from mt5desk import families
import numpy as np

df = pd.read_parquet("/home/quant/quant-platform/desks/mt5/data/universe/XAUUSD_H1.parquet")
h1 = families._h1(df)
fn = get_family_func("session_range_breakout")
sigs = fn(h1, range_start=7, wait_bars=8, atr_n=20, ttl_bars=12, rr=2.0, signal_at=7, trend_filter="aligned")

idx = h1.index
idx_ns = np.asarray(idx.asi8, dtype="int64")

# Check first signal
s = sigs[0]
sig_ns = pd.Timestamp(s.time).value
print(f"Signal time: {s.time}")
print(f"sig_ns: {sig_ns}")
print(f"idx_ns[0]: {idx_ns[0]}")
print(f"idx_ns[10]: {idx_ns[10]}")
print(f"sig_ns > idx_ns[0]: {sig_ns > idx_ns[0]}")
print(f"sig_ns > idx_ns[-1]: {sig_ns > idx_ns[-1]}")

# Check all signal ns
sig_ns_arr = np.array([pd.Timestamp(s.time).value for s in sigs], dtype="int64")
print(f"min sig_ns: {sig_ns_arr.min()}")
print(f"max sig_ns: {sig_ns_arr.max()}")