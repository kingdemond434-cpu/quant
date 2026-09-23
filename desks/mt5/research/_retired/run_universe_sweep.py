"""The whole universe x the whole family library, ranked, and clustered by correlation.

    python research/run_universe_sweep.py

WHY THE CORRELATION HALF MATTERS MORE THAN THE RANKING HALF

Finding more edges does not, by itself, let the desk carry more risk. The heat
budget is `Q_OPT x legs` scaled by sqrt(k_eff), where k_eff is the number of
INDEPENDENT bets -- so ten sleeves that all fire on the same dollar move are
worth roughly one, and the budget correctly refuses to grow for them. Adding a
correlated sleeve raises turnover and drawdown while adding no capacity.

So this does two things, and the second is the point:

  1. screen 12 families x 23 symbols at the Stage-A bar (t >= 1.96)
  2. take what screens, build the correlation matrix of their DAILY RETURN
     SERIES, and report clusters -- so the desk can pick one representative
     per cluster instead of ten copies of the same bet.

k_eff IS REPORTED, NOT ASSUMED. `heat_budget()` treats an unmeasured k_eff as
1.0 (the base budget) precisely because treating "not yet measured" as
"independent" is how a correlated book sizes like a diversified one and
discovers the truth during the drawdown. This produces the measurement that
lets k_eff be passed honestly.

STAGE A ONLY. Nothing here promotes anything; 276 cells at t>=1.96 will throw
off false positives by construction, and the forward slots are what settle it.
The ranking decides who gets a slot, not who gets capital.
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
warnings.filterwarnings("ignore")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from mt5desk import families  # noqa: E402
from mt5desk.engine import Costs, run_backtest  # noqa: E402

BASE = Path(__file__).resolve().parent.parent
UNI = BASE / "data" / "universe"
SCREEN_BAR = 1.96
MIN_TRADES = 30

EDGES = {
    "session_range_breakout": families.family_session_range_breakout,
    "level_breakout": families.family_level_breakout,
    "failed_breakout": families.family_failed_breakout,
    "fair_value_gap": families.family_fair_value_gap,
    "order_block": families.family_order_block,
    "london_close_momentum": families.family_london_close_momentum,
    "asia_momentum": families.family_asia_momentum,
    "momentum_volgate": families.family_momentum_volgate,
    "comex_settlement": families.family4_comex_settlement_effect,
    "dow_effect": families.family_dow_effect,
    "monday_gap": families.family_monday_gap,
    "spread_state_avoidance": families.family7_spread_state_avoidance,
}

#: RAW-SPREAD COSTS. 20% of the median spread plus full commission -- the
#: Fusion account this desk actually trades. `mult=2.0` (the old default) is
#: the WIDE regime and priced gold roughly five times its real cost, which
#: discarded two thirds of the candidates in the earlier sweep.
SPREAD_MULT = 0.2


def _costs(meta: dict) -> Costs:
    cs = float(meta.get("contract_size", 1e5))
    spread = (float(meta.get("median_spread_pts", 0.0))
              * float(meta.get("tick_size", 0.0)) * cs)
    return Costs(spread_per_lot=max(spread * SPREAD_MULT, 0.0),
                 commission_per_lot=3.50, contract_oz=cs)


def main() -> int:
    meta = json.loads((UNI / "universe.json").read_text(encoding="utf-8"))
    syms = sorted(s for s in meta if (UNI / f"{s}_H1.parquet").exists())
    print(f"{len(EDGES)} families x {len(syms)} symbols = {len(EDGES)*len(syms)} cells")
    print(f"raw-spread costs (mult={SPREAD_MULT}) + $3.50/lot commission")
    print(f"Stage-A screening bar t >= {SCREEN_BAR}, n >= {MIN_TRADES}\n")

    rows, series = [], {}
    for sym in syms:
        h1 = pd.read_parquet(UNI / f"{sym}_H1.parquet")
        costs = _costs(meta[sym])
        for ename, fn in EDGES.items():
            try:
                sigs = fn(h1)
            except Exception:                                   # noqa: BLE001
                continue
            if not sigs:
                continue
            trades = run_backtest(h1, sigs, costs).trades
            n = len(trades)
            if n < MIN_TRADES:
                continue
            r = np.array([t.r_multiple for t in trades])
            t_stat = float(r.mean() / (r.std(ddof=1) / np.sqrt(n)))
            key = f"{sym}.{ename}"
            rows.append({"key": key, "symbol": sym, "edge": ename, "n": n,
                         "t": t_stat, "exp": float(r.mean())})
            if t_stat >= SCREEN_BAR:
                # daily R series, for the correlation half
                s = pd.Series(r, index=pd.to_datetime([t.entry_time for t in trades]))
                series[key] = s.resample("1D").sum()

    rows.sort(key=lambda x: -x["t"])
    ranked = [r for r in rows if r["t"] >= SCREEN_BAR]
    print(f"{len(ranked)} of {len(rows)} priceable cells clear t >= {SCREEN_BAR}\n")
    print(f"{'symbol':<8} {'edge':<24} {'n':>6} {'exp R':>9} {'t':>7}")
    for r in ranked[:30]:
        print(f"{r['symbol']:<8} {r['edge']:<24} {r['n']:6d} {r['exp']:+9.4f} {r['t']:7.2f}")

    # ---- the part that decides capacity ---------------------------------
    if len(series) >= 2:
        df = pd.DataFrame(series).fillna(0.0)
        C = df.corr()
        n_s = len(C)
        avg_rho = float((C.values.sum() - n_s) / (n_s * (n_s - 1)))
        k_eff = n_s / (1 + (n_s - 1) * max(avg_rho, 0.0))
        print(f"\n{n_s} screening sleeves | mean pairwise rho {avg_rho:+.3f} "
              f"-> k_eff {k_eff:.2f}")
        print(f"  heat budget at k_eff=None (base): 9.00%")
        print(f"  heat budget at this k_eff:        "
              f"{min(0.03*3*np.sqrt(k_eff/2.26), 0.15)*100:.2f}%  (ceiling 15%)")

        # greedy low-correlation selection
        picked = []
        for r in ranked:
            k = r["key"]
            if k not in C.index:
                continue
            if all(abs(C.loc[k, p]) < 0.30 for p in picked):
                picked.append(k)
        print(f"\nLOW-CORRELATION SET (|rho| < 0.30 pairwise): {len(picked)} sleeves")
        for k in picked[:15]:
            r = next(x for x in ranked if x["key"] == k)
            print(f"  {k:<34} n={r['n']:5d} t={r['t']:5.2f} exp={r['exp']:+.4f}")
        if picked:
            sub = C.loc[picked, picked]
            a = float((sub.values.sum() - len(picked)) / max(len(picked)*(len(picked)-1), 1))
            ke = len(picked) / (1 + (len(picked)-1) * max(a, 0.0))
            print(f"\n  that set: mean rho {a:+.3f} -> k_eff {ke:.2f} "
                  f"-> budget {min(0.03*3*np.sqrt(ke/2.26), 0.15)*100:.2f}%")

    out = BASE / "reports" / "universe_sweep.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"screen_bar": SCREEN_BAR, "rows": rows}, indent=2),
                   encoding="utf-8")
    print(f"\n-> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
