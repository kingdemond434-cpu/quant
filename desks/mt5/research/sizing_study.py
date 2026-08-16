"""Sizing study for the 4-sleeve XAUUSD breakout book (MANDATE_NET_COMPOUNDING).

Block bootstrap over the costed per-trade R stream, fixed-fractional sizing
curve, ruin/stress/correlation metrics. Run from mt5-research with
PYTHONPATH=C:\\Users\\dell\\mt5-research.
"""

import numpy as np

from mt5desk import families
from mt5desk.data import load_gold
from mt5desk.engine import Costs, run_backtest

costs = Costs(spread_per_lot=0.48, commission_per_lot=3.50, contract_oz=100.0)
h1 = families._h1(load_gold().h1)

WINDOWS = [
    ("asia", dict(range_start=7, wait_bars=12, rr=2.0, ttl_bars=12)),
    ("london_am", dict(range_start=10, range_end=13, signal_at=13, wait_bars=8, rr=2.0, ttl_bars=12)),
    ("ny_open", dict(range_start=13, range_end=14, signal_at=14, wait_bars=12, rr=2.0, ttl_bars=12)),
    ("afternoon", dict(range_start=14, range_end=17, signal_at=17, wait_bars=8, rr=2.0, ttl_bars=12)),
]

all_sigs = []
for label, p in WINDOWS:
    sigs = families.family_session_range_breakout(h1, **p)
    for s in sigs:
        s.tag = label
    all_sigs += sigs
all_sigs.sort(key=lambda s: s.time)

res = run_backtest(h1, all_sigs, costs)
rs = np.array([t.r_multiple for t in res.trades])
st = res.stats()
years_dense = 8.5
n_yr = len(rs) / years_dense

print(f"combined: n={len(rs)} exp={st['expectancy_r']:.3f}R t={st['t_stat']:.2f} "
      f"PF={st['profit_factor']:.2f} maxDD={st['max_dd_r']:.1f}R trades/yr={n_yr:.0f}")
print(f"worst single R={rs.min():.2f} | 99th pct |R|={np.quantile(np.abs(rs), 0.99):.2f}")

# cross-sleeve daily correlation
daily = {}
for label, p in WINDOWS:
    sigs = [s for s in all_sigs if s.tag == label]
    r2 = run_backtest(h1, sigs, costs)
    d = {}
    for t in r2.trades:
        day = t.entry_time.date() if hasattr(t, "entry_time") else None
        d[day] = d.get(day, 0.0) + t.r_multiple
    daily[label] = d
    st2 = r2.stats()
    print(f"  {label}: n={st2['n']} exp={st2['expectancy_r']:.3f}R t={st2['t_stat']:.2f} "
          f"maxDD={st2['max_dd_r']:.1f}R")

labels = list(daily)
dates = sorted(set().union(*[set(d) for d in daily.values()]))
mat = np.array([[daily[l].get(d, np.nan) for d in dates] for l in labels])
print("cross-sleeve daily-R Pearson corr:")
for i, a in enumerate(labels):
    row = []
    for j, b in enumerate(labels):
        m = ~np.isnan(mat[i]) & ~np.isnan(mat[j])
        if m.sum() < 30:
            row.append(float("nan"))
        else:
            row.append(float(np.corrcoef(mat[i][m], mat[j][m])[0, 1]))
    print(f"  {a:10s} " + " ".join(f"{v:+.2f}" for v in row))

# --- block bootstrap sizing curve (fixed-fractional, vectorized) ---
BLOCK = 25  # ~1 month of trades, preserves streaks + sleeve clustering
N_SIMS = 30000
N_TRADES = int(round(n_yr))  # one simulated year per sim
EQ_START = 633.89
DIST_USD = 19.1          # ~1.2xATR stop distance (USD/oz)
CONTRACT = 100
FX = 0.92                # USD -> EUR
MARGIN_K = 4300.0 / (DIST_USD * 500.0)  # margin = MARGIN_K * q * equity

LOTS = [0.005, 0.0075, 0.010, 0.0125, 0.015, 0.020, 0.030, 0.040, 0.050, 0.060]


def sim(mean_scale=1.0, vol_scale=1.0, seed=7):
    rng = np.random.default_rng(seed)
    r = rs * mean_scale
    r = (r - r.mean()) * vol_scale + r.mean()
    blocks = [r[i:i + BLOCK] for i in range(0, len(r), BLOCK)]
    if len(r) % BLOCK:  # pad last partial block with leading trades
        blocks[-1] = np.concatenate([blocks[-1], r[:BLOCK - len(r) % BLOCK]])
    nblk = len(blocks)
    table = np.concatenate(blocks)
    # block-concatenated sims: each sim = 14 drawn blocks sliced at 331 trades
    nblocks_per_sim = int(np.ceil(N_TRADES / BLOCK))
    b = rng.integers(0, nblk, size=(N_SIMS, nblocks_per_sim))
    within = np.arange(BLOCK)[None, None, :]
    idx = (b[:, :, None] * BLOCK + within).reshape(N_SIMS, -1)[:, :N_TRADES]
    rmat = table[idx]  # (N_SIMS, N_TRADES)
    out = {}
    for lot in LOTS:
        q = lot * DIST_USD * CONTRACT * FX / EQ_START
        floor = MARGIN_K * q
        eq = np.cumprod(1.0 + q * rmat, axis=1)
        peak = np.maximum.accumulate(eq, axis=1)
        dd = 1.0 - eq / peak
        broke = eq < floor          # equity < margin -> broker stop-out
        ruined = (eq < 0.02) | broke
        any_ruin = ruined.any(axis=1)
        term = eq[:, -1].copy()
        term[any_ruin] = 0.0
        ddmax = dd.max(axis=1)
        live = term > 0
        med = np.median(term[live]) if live.any() else 0.0
        out[lot] = dict(
            q=q,
            cagr_med=med - 1.0,
            p5_wealth=float(np.quantile(term[live], 0.05)) if live.any() else 0.0,
            p_dd30=float((ddmax > 0.30).mean()),
            p_dd50=float((ddmax > 0.50).mean()),
            p_dd70=float((ddmax > 0.70).mean()),
            p_ruin=float(any_ruin.mean()),
        )
    return out


print("\n=== sizing curve (base edge) ===")
print(f"{'lot':>6} {'risk%':>6} {'medCAGR':>8} {'5pctWealth':>10} "
      f"{'P(DD30)':>8} {'P(DD50)':>8} {'P(DD70)':>8} {'P(ruin)':>8}")
base = sim(1.0, 1.0)
for lot, m in base.items():
    print(f"{lot:6.3f} {m['q']*100:5.1f}% {m['cagr_med']*100:7.0f}% {m['p5_wealth']:10.3f} "
          f"{m['p_dd30']:8.2f} {m['p_dd50']:8.2f} {m['p_dd70']:8.2f} {m['p_ruin']:8.4f}")

print("\n=== stress: edge halved (mean x0.5, vol x1.3) ===")
print(f"{'lot':>6} {'risk%':>6} {'medCAGR':>8} {'5pctWealth':>10} "
      f"{'P(DD30)':>8} {'P(DD50)':>8} {'P(DD70)':>8} {'P(ruin)':>8}")
stress = sim(0.5, 1.3)
for lot, m in stress.items():
    print(f"{lot:6.3f} {m['q']*100:5.1f}% {m['cagr_med']*100:7.0f}% {m['p5_wealth']:10.3f} "
          f"{m['p_dd30']:8.2f} {m['p_dd50']:8.2f} {m['p_dd70']:8.2f} {m['p_ruin']:8.4f}")

# Kelly reference
var = rs.var(ddof=1)
print(f"\nKelly full f* = exp/var = {rs.mean()/var:.3f} ({rs.mean()/var*100:.1f}% risk/trade "
      f"= {rs.mean()/var*EQ_START/(DIST_USD*CONTRACT*FX):.3f} lot)")