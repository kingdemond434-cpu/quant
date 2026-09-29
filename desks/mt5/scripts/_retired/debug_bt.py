import pandas as pd
from mt5desk.families import get_family_func
from mt5desk.engine import Costs, run_backtest
from mt5desk import families

df = pd.read_parquet("/home/quant/quant-platform/desks/mt5/data/universe/XAUUSD_H1.parquet")
h1 = families._h1(df)
fn = get_family_func("session_range_breakout")
sigs = fn(h1, range_start=7, wait_bars=8, atr_n=20, ttl_bars=12, rr=2.0, signal_at=7, trend_filter="aligned")
print("signals:", len(sigs))

# Debug: check first few signal times and corresponding data
for s in sigs[:3]:
    print(f"  sig: time={s.time} side={s.side} trigger={s.trigger} stop={s.stop} target={s.target}")

costs = Costs(spread_per_lot=0.48, commission_per_lot=3.50, contract_oz=100.0)

# Manually trace what run_backtest does for first signal
idx = h1.index
idx_ns = pd.Series(idx).astype('int64').values  # Use int64 ns
sig_ns = pd.Timestamp(sigs[0].time).value
import numpy as np
locs = np.searchsorted(idx_ns, [sig_ns])
print(f"signal ns: {sig_ns}, locs: {locs}, idx_ns[0]: {idx_ns[0]}")

# Check the bar after signal
i = locs[0] + 1
print(f"i={i}, idx[i]={idx[i]}, open={h1['open'].iloc[i]}")

# Check if trigger is hit within wait_bars
tgt = sigs[0].trigger
for j in range(i, min(i + sigs[0].wait_bars, len(idx))):
    hi = float(h1['high'].iloc[j])
    lo = float(h1['low'].iloc[j])
    if hi >= tgt >= lo:
        print(f"  HIT at bar {j} ({idx[j]}): high={hi}, low={lo}, trigger={tgt}")
        break
else:
    print(f"  NO HIT within wait_bars={sigs[0].wait_bars}")
    for j in range(i, min(i + sigs[0].wait_bars, len(idx))):
        hi = float(h1['high'].iloc[j])
        lo = float(h1['low'].iloc[j])
        print(f"    bar {j} ({idx[j]}): high={hi}, low={lo}")

# Now run backtest
res = run_backtest(h1, sigs, costs)
print("trades:", len(res.trades))
if res.trades:
    exp_r = sum(t.r_multiple for t in res.trades)/len(res.trades)
    print("exp_r:", exp_r)