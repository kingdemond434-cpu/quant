import pandas as pd
from mt5desk.families import get_family_func
from mt5desk.engine import Costs, run_backtest
from mt5desk import families

df = pd.read_parquet("/home/quant/quant-platform/desks/mt5/data/universe/XAUUSD_H1.parquet")
h1 = families._h1(df)
fn = get_family_func("session_range_breakout")
# Test with trigger=None (market entry at next open)
sigs = fn(h1, range_start=7, wait_bars=8, atr_n=20, ttl_bars=12, rr=2.0, signal_at=7, trend_filter="aligned")
print("signals:", len(sigs))
for s in sigs[:3]:
    print(f"  time={s.time} side={s.side} stop={s.stop} target={s.target} ttl={s.ttl_bars} trigger={s.trigger}")

costs = Costs(spread_per_lot=0.48, commission_per_lot=3.50, contract_oz=100.0)
res = run_backtest(h1, sigs, costs)
print("trades:", len(res.trades))
if res.trades:
    print("exp_r:", sum(t.r_multiple for t in res.trades)/len(res.trades))
    print("first:", res.trades[0])