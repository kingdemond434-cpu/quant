"""Hunt #5: filter variants on the 4 breakout windows (trend/range/vol) + DOW diagnostics.

Gate: t > 2, n > 60, PF > 1.05, maxDD > -30R, costs inside.
"""

import json
from pathlib import Path

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

VARIANTS = {
    "baseline": {},
    "trend_aligned": {"trend_filter": "aligned"},
    "range_small": {"range_filter": "small"},
    "range_large": {"range_filter": "large"},
    "vol_low": {"vol_filter": "low"},
    "vol_high": {"vol_filter": "high"},
    "trend_aligned+spread": {"trend_filter": "aligned", "spread_gate": True},
    "ny_spread_gate": {"spread_gate": True},
}

results = {}
print(f"{'window':>10} {'variant':>18} {'n':>5} {'exp_R':>7} {'t':>5} {'PF':>5} "
      f"{'win':>5} {'maxDD_R':>7} {'GATE':>5}")
for wlabel, p in WINDOWS:
    for vlabel, v in VARIANTS.items():
        pp = {**p, **v}
        sigs = families.family_session_range_breakout(h1, **pp)
        if not sigs:
            continue
        res = run_backtest(h1, sigs, costs)
        st = res.stats()
        gate = st["t_stat"] > 2 and st["n"] > 60 and st["profit_factor"] > 1.05 \
            and st["max_dd_r"] > -30
        key = f"{wlabel}|{vlabel}"
        results[key] = {**st, "gate": bool(gate)}
        print(f"{wlabel:>10} {vlabel:>18} {st['n']:5d} {st['expectancy_r']:7.3f} "
              f"{st['t_stat']:5.2f} {st['profit_factor']:5.2f} {st['win_rate']:5.1%} "
              f"{st['max_dd_r']:7.1f} {'PASS' if gate else 'fail':>5}")

# DOW diagnostics on baseline
print("\nDOW diagnostic (baseline, all windows combined per weekday):")
dow_res = {}
for wlabel, p in WINDOWS:
    sigs = families.family_session_range_breakout(h1, **p)
    res = run_backtest(h1, sigs, costs)
    by_dow = {}
    for t in res.trades:
        d = t.entry_time.dayofweek
        by_dow.setdefault(d, []).append(t.r_multiple)
    for d in sorted(by_dow):
        r = np.array(by_dow[d])
        dow_res.setdefault(d, {})[wlabel] = dict(
            n=len(r), exp=float(r.mean()),
            t=float(r.mean() / (r.std(ddof=1) / np.sqrt(len(r)))) if len(r) > 1 else 0.0)
    print(f"  {wlabel}: " + " ".join(
        f"dow{d} n={dow_res[d][wlabel]['n']} exp={dow_res[d][wlabel]['exp']:+.3f} "
        f"t={dow_res[d][wlabel]['t']:+.2f}" for d in sorted(by_dow)))

Path("reports/hunt5.json").write_text(
    json.dumps({"variants": results, "dow": dow_res}, indent=2, default=str), encoding="utf-8")
print("\nwrote reports/hunt5.json")