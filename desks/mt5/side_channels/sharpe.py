import numpy as np
import pandas as pd

from mt5desk import families
from mt5desk.data import load_gold
from mt5desk.engine import Costs, run_backtest

costs = Costs(spread_per_lot=0.48, commission_per_lot=3.50, contract_oz=100.0)
h1 = families._h1(load_gold().h1)

for label, params in [
    ("base rs=7 wait=8", dict(range_start=7, wait_bars=8, rr=2.0, ttl_bars=12)),
    ("best rs=6 wait=12", dict(range_start=6, wait_bars=12, rr=2.0, ttl_bars=12)),
    ("deployed rs=7 wait=12", dict(range_start=7, wait_bars=12, rr=2.0, ttl_bars=12)),
]:
    sigs = families.family_session_range_breakout(h1, **params)
    res = run_backtest(h1, sigs, costs)
    rs = np.array([t.r_multiple for t in res.trades])
    n = len(rs)
    per_trade_sr = rs.mean() / rs.std(ddof=1)
    years = (h1.index[-1] - h1.index[0]).days / 365.25
    trades_per_year = n / years
    ann_sr = per_trade_sr * np.sqrt(trades_per_year)
    # Newey-West (3 lags) honest version
    e = rs - rs.mean()
    var = e @ e / n
    for lag in range(1, 4):
        cov = e[lag:] @ e[:-lag] / n
        var += 2 * (1 - lag / 4) * cov
    nw_sr = rs.mean() / np.sqrt(var)
    ann_nw = nw_sr * np.sqrt(trades_per_year)
    wins = rs[rs > 0]
    print(f"{label}: n={n} trades/yr={trades_per_year:.0f}")
    print(f"  per-trade SR={per_trade_sr:.3f}  annualized SR={ann_sr:.2f}")
    print(f"  Newey-West(3) per-trade={nw_sr:.3f}  annualized={ann_nw:.2f}")
    print(f"  win={len(wins)/n:.1%} exp={rs.mean():.3f}R")

# daily PnL on 0.02 lot in EUR (approximation: R x current stop distance x 100 x 0.02)
res = run_backtest(h1, families.family_session_range_breakout(
    h1, range_start=7, wait_bars=12, rr=2.0, ttl_bars=12), costs)
rs = np.array([t.r_multiple for t in res.trades])
print("\ndeplyed 0.02 lot: mean R/trade", rs.mean().round(3),
      "| worst R", rs.min().round(2), "| R>3 share", (rs > 3).mean().round(3))