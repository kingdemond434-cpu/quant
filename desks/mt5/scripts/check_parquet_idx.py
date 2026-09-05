import pandas as pd

df = pd.read_parquet("/home/quant/quant-platform/desks/mt5/data/universe/XAUUSD_H1.parquet")
print(f"Raw parquet index tz: {df.index.tz}")
print(f"Raw index[0]: {df.index[0]}")
print(f"Raw index[0].value: {df.index[0].value}")
print(f"Raw index dtype: {df.index.dtype}")

# After _h1
from mt5desk import families
h1 = families._h1(df)
print(f"\nAfter _h1 index tz: {h1.index.tz}")
print(f"After _h1 index[0]: {h1.index[0]}")
print(f"After _h1 index[0].value: {h1.index[0].value}")
print(f"After _h1 asi8[0]: {h1.index.asi8[0]}")
print(f"After _h1 asi8[10]: {h1.index.asi8[10]}")