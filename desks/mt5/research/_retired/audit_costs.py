from collections import Counter

import numpy as np
import pandas as pd

from mt5desk import families
from mt5desk.data import load_gold
from mt5desk.engine import Costs, run_backtest

gold = load_gold()
h1 = families._h1(gold.h1)

years = Counter(t.year for t in h1.index)
print("H1 bars per year:")
for y in sorted(years):
    print(f"  {y}: {years[y]}")

base = families.family_session_range_breakout(h1, range_start=7, wait_bars=8, rr=2.0)
for label, c in [
    ("measured  (spread 0.48, comm 3.50)", Costs(0.48, 3.50, 100.0)),
    ("cheap     (spread 0.20, comm 2.00)", Costs(0.20, 2.00, 100.0)),
    ("stressed  (spread 1.00, comm 7.00)", Costs(1.00, 7.00, 100.0)),
    ("zero-cost (upper bound)", Costs(0.0, 0.0, 100.0)),
]:
    st = run_backtest(h1, base, c).stats()
    print(f"{label}: n={st['n']} exp={st['expectancy_r']:.3f}R t={st['t_stat']:.2f} "
          f"PF={st['profit_factor']:.2f} maxDD={st['max_dd_r']:.1f}R")

s = run_backtest(h1, base, Costs(0.48, 3.50, 100.0)).stats()
print(f"\nbase: win={s['win_rate']:.1%} avgW={s['avg_win_r']:.2f}R avgL={s['avg_loss_r']:.2f}R")
# per-trade $ on 0.5 lot at current gold
atr = families._atr(h1, 20)
stop_dist = max(1.2 * float(atr.iloc[-1]), 0.0)
lot = 0.5
print(f"current ATR(20)={float(atr.iloc[-1]):.2f} -> stop~{1.2*float(atr.iloc[-1]):.2f}/oz")
print(f"0.5 lot R = {1.2*float(atr.iloc[-1])*100*lot:.2f} USD (100oz*0.5)")
print(f"expected/trade at exp=0.122R = {0.122*1.2*float(atr.iloc[-1])*100*lot:.2f} USD")
print(f"costs/trade = {(0.48+7.0)*lot:.2f} USD (spread+comm, 0.5 lot)")