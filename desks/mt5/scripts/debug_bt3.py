import pandas as pd
from mt5desk.families import get_family_func
from mt5desk import families
import numpy as np

df = pd.read_parquet("/home/quant/quant-platform/desks/mt5/data/universe/XAUUSD_H1.parquet")
h1 = families._h1(df)
fn = get_family_func("session_range_breakout")
sigs = fn(h1, range_start=7, wait_bars=8, atr_n=20, ttl_bars=12, rr=2.0, signal_at=7, trend_filter="aligned")

idx = h1.index
idx_ns = np.asarray(idx.asi8, dtype="int64")  # Engine method
n = len(idx)

print(f"Data: {idx[0]} to {idx[-1]}, n={n}")
print(f"idx_ns[0]: {idx_ns[0]}, idx_ns[-1]: {idx_ns[-1]}")

valid = 0
for s in sigs:
    sig_ns = pd.Timestamp(s.time).value
    locs = np.searchsorted(idx_ns, [sig_ns])
    i = locs[0] + 1
    if i > 0 and i < n - 1:
        valid += 1
        if valid <= 3:
            print(f"  Valid sig: time={s.time}, i={i}, idx[i]={idx[i]}")

print(f"Total signals: {len(sigs)}")
print(f"Valid signals: {valid}")