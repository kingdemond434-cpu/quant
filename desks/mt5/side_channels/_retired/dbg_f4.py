import numpy as np
import pandas as pd

from mt5desk import families
from mt5desk.data import load_gold

h1 = families._h1(load_gold().h1)
atr = families._atr(h1, 20)
vmed = atr.rolling(120).median()

rows = h1[h1.index.hour == 21]
print("bars at hour 21:", len(rows))
locs = rows.index.get_indexer(h1.index)
locs = [i for i in locs if i >= 2 and i != -1]
print("sample:", len(locs))
moves = []
vol_highs = 0
for i in locs[:5000]:
    a = atr.iloc[i]
    if not (a > 0) or np.isnan(vmed.iloc[i]):
        continue
    pre = float(h1["close"].iloc[i - 2])
    now = float(h1["close"].iloc[i - 1])
    m = abs(now - pre) / a
    moves.append(m)
    if a > 0.5 * vmed.iloc[i]:
        vol_highs += 1
moves = np.array(moves)
print("moves>1.0 ATR:", (moves > 1.0).sum(), "/", len(moves))
print("moves>0.75:", (moves > 0.75).sum())
print("vol_high share:", vol_highs / len(moves) if len(moves) else 0)
print("move quantiles:", np.percentile(moves, [50, 75, 90, 95]) if len(moves) else None)