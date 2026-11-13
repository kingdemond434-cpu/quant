import pandas as pd
import numpy as np

# Check what asi8 returns for different index types
idx_tz = pd.date_range("2018-03-19", periods=10, freq="H", tz="UTC")
idx_naive = pd.date_range("2018-03-19", periods=10, freq="H")

print("TZ-aware index:")
print(f"  asi8[0]: {idx_tz.asi8[0]}")
print(f"  value[0]: {idx_tz[0].value}")

print("Naive index:")
print(f"  asi8[0]: {idx_naive.asi8[0]}")
print(f"  value[0]: {idx_naive[0].value}")

# Check pandas version
print(f"Pandas version: {pd.__version__}")