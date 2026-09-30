import pandas as pd
from mt5desk.families import get_family_func
from mt5desk.engine import Costs, run_backtest
from mt5desk import families

df = pd.read_parquet("/home/quant/quant-platform/desks/mt5/data/universe/XAUUSD_H1.parquet")
h1 = families._h1(df)
fn = get_family_func("session_range_breakout")

# Test wait_bars=12, trend_filter="aligned"
sigs = fn(h1, range_start=7, wait_bars=12, atr_n=20, ttl_bars=12, rr=2.0, trend_filter="aligned")
print("signals:", len(sigs))

costs = Costs(spread_per_lot=0.48, commission_per_lot=3.50, contract_oz=100.0)
res = run_backtest(h1, sigs, costs)
print("trades:", len(res.trades))
if res.trades:
    exp_r = sum(t.r_multiple for t in res.trades)/len(res.trades)
    print("exp_r:", exp_r)
    wins = sum(1 for t in res.trades if t.r_multiple > 0)
    print(f"win rate: {wins}/{len(res.trades)} = {wins/len(res.trades):.2%}")