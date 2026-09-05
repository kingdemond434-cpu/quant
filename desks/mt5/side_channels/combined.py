import numpy as np

from mt5desk import families
from mt5desk.data import load_gold
from mt5desk.engine import Costs, run_backtest

costs = Costs(spread_per_lot=0.48, commission_per_lot=3.50, contract_oz=100.0)
h1 = families._h1(load_gold().h1)

WINDOWS = [
    dict(range_start=7, wait_bars=12, rr=2.0, ttl_bars=12),
    dict(range_start=10, range_end=13, signal_at=13, wait_bars=8, rr=2.0, ttl_bars=12),
    dict(range_start=13, range_end=14, signal_at=14, wait_bars=12, rr=2.0, ttl_bars=12),
    dict(range_start=14, range_end=17, signal_at=17, wait_bars=8, rr=2.0, ttl_bars=12),
]

all_sigs = []
for p in WINDOWS:
    all_sigs += families.family_session_range_breakout(h1, **p)
all_sigs.sort(key=lambda s: s.time)

res = run_backtest(h1, all_sigs, costs)
st = res.stats()
rs = np.array([t.r_multiple for t in res.trades])
years_dense = 8.5
n_yr = len(rs) / years_dense
per_trade_sr = rs.mean() / rs.std(ddof=1)
ann_sr = per_trade_sr * np.sqrt(n_yr)

print(f"combined book: n={len(rs)} over {years_dense}y dense -> {n_yr:.0f} trades/yr")
print(f"exp={st['expectancy_r']:.3f}R t={st['t_stat']:.2f} PF={st['profit_factor']:.2f} "
      f"win={st['win_rate']:.1%} maxDD={st['max_dd_r']:.1f}R")
print(f"per-trade SR={per_trade_sr:.3f} annualized SR={ann_sr:.2f}")

for lot, risk_pct in [(0.01, 2.7), (0.02, 5.4)]:
    r_per_trade = st["expectancy_r"] * lot * 100 * 19.1 / (634 if False else 633.89)
    # risk per trade in EUR: stop ~19.1 EUR/oz-equivalent * 100 oz * lot... R in EUR
    r_eur = st["expectancy_r"] * 19.1 * 100 * lot * (0.92)  # $->EUR 0.92
    ann_eur = r_eur * n_yr
    print(f"\nlot={lot}: risk/trade ~{5.4*lot/0.02:.1f}% of 633.89 EUR | "
          f"exp {r_eur:.2f} EUR/trade | ~{ann_eur:.0f} EUR/yr = {ann_eur/633.89:.0%} arithmetic")
    print(f"  worst historical DD at this lot: {st['max_dd_r']*5.4*lot/0.02:.0f} EUR "
          f"({st['max_dd_r']*5.4*lot/0.02/633.89:.0%})")