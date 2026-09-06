"""The desk's REAL chart-edge library, macro-conditioned, priced three ways.

    python research/run_edges_macro_fusion_sweep.py

WHY THIS RE-RUN EXISTS -- TWO CORRECTIONS TO THE EARLIER SWEEPS

1. THE WRONG FAMILIES WERE TESTED. The dip sweep and the macro-conditioning
   sweep both ran `family_dip_*` -- three mechanisms written for that sweep.
   The desk's actual library is twelve families reverse-engineered from real
   sources: session range breakouts, prior-day/week level breakouts, failed
   breakouts, fair-value gaps, order blocks, London-close and Asia momentum,
   COMEX settlement effects, day-of-week and Monday-gap effects. Those are
   the "proven chart edges" worth mixing with macro, and none of them had
   been run against the macro state.

2. THE COST MODEL WAS PROBABLY TOO HARSH. Every earlier sweep used
   `Costs.from_symbol(meta, mult=2.0)` -- the FULL median spread, doubled.
   On a raw-spread/commission account that is roughly five times the real
   cost on gold, and cost enters every t-statistic. Rather than swap one
   guess for another, all three regimes are run side by side:

     WIDE      median spread x2 + commission   (what the earlier sweeps used)
     RAW       20% of median spread + commission (a raw account still has SOME
               spread; "zero spread" is a marketing description of a residual)
     ZERO      commission only (the optimistic bound -- kept because it is a
               BOUND, not because any account fills at it)

   Reporting the bound alongside the realistic case is the point: if a family
   only works at ZERO it does not work, and seeing that explicitly is more
   useful than arguing about which single number to use.

WHAT THIS DOES NOT CHANGE

The bar is STILL the Stage-A screening bar, t >= 1.96, per
TWO_STAGE_DISCOVERY_LAW -- ranking only, zero promotion authority. Cheaper
costs make more candidates rank; they do not make a ranked candidate an edge.
Only forward evidence in a confirmation slot does that.
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
warnings.filterwarnings("ignore", category=UserWarning)

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from mt5desk import families, macro_regime  # noqa: E402
from mt5desk.engine import Costs, run_backtest  # noqa: E402

BASE = Path(__file__).resolve().parent.parent
UNI = BASE / "data" / "universe"
SCREEN_BAR = 1.96

#: The desk's real chart-edge library -- every family taking only `df`.
#: The three dip_* families are deliberately EXCLUDED: they were written for
#: the earlier sweep and are not part of the desk's researched library.
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

#: symbol -> (macro column, lookback days, economic reason for the mapping)
CONDITION = {
    "XAUUSD": ("REAL_YIELD_10Y", 20, "zero-coupon: the real yield IS the carry cost"),
    "XAGUSD": ("REAL_YIELD_10Y", 20, "same carry logic, higher beta"),
    "GBPUSD": ("DXY", 20, "USD-quoted: the dollar is half the pair"),
    "USDJPY": ("DGS10", 20, "the classic carry driver"),
}

COST_REGIMES = {"WIDE": 2.0, "RAW": 0.2, "ZERO": 0.0}


def _costs(meta: dict, mult: float) -> Costs:
    """Costs at one spread regime. Commission is never scaled.

    Commission is contractual -- it does not widen with volatility and
    stressing it models nothing that happens. Only the spread varies.
    """
    cs = float(meta.get("contract_size", 1e5))
    spread = (float(meta.get("median_spread_pts", 0.0))
              * float(meta.get("tick_size", 0.0)) * cs)
    return Costs(spread_per_lot=max(spread * mult, 0.0),
                 commission_per_lot=3.50, contract_oz=cs)


def _t(trades) -> tuple[int, float, float]:
    n = len(trades)
    if n < 20:
        return n, float("nan"), float("nan")
    r = np.array([t.r_multiple for t in trades])
    return n, float(r.mean() / (r.std(ddof=1) / np.sqrt(n))), float(r.mean())


def _favourable(hist: pd.DataFrame, col: str, lookback: int):
    if col not in hist.columns:
        return None
    s = hist[col].dropna()
    return (s - s.shift(lookback)) < 0


def main() -> int:
    meta = json.loads((UNI / "universe.json").read_text(encoding="utf-8"))
    hist = macro_regime.load_history()
    if hist is None:
        print("MACRO HISTORY ABSENT -- UNMEASURED, not a clean result.")
        return 2

    print(f"{len(EDGES)} real chart families x {len(CONDITION)} symbols "
          f"x {len(COST_REGIMES)} cost regimes x (plain | macro-conditioned)")
    print(f"STAGE A ranking, screening bar t >= {SCREEN_BAR}. "
          f"Cheaper costs rank more candidates; they do not create edge.\n")

    rows = []
    for sym, (col, lookback, _why) in CONDITION.items():
        p = UNI / f"{sym}_H1.parquet"
        if not p.exists() or sym not in meta:
            continue
        h1 = pd.read_parquet(p)
        fav = _favourable(hist, col, lookback)
        fav_dates = set(fav[fav].index.date) if fav is not None else set()

        for ename, fn in EDGES.items():
            try:
                sigs = fn(h1)
            except Exception as e:                        # noqa: BLE001
                print(f"  SKIP {sym}/{ename}: {e}")
                continue
            if not sigs:
                continue
            cond = [s for s in sigs if s.time.date() in fav_dates]

            for rname, mult in COST_REGIMES.items():
                costs = _costs(meta[sym], mult)
                n_p, t_p, e_p = _t(run_backtest(h1, sigs, costs).trades)
                n_c, t_c, e_c = (_t(run_backtest(h1, cond, costs).trades)
                                 if cond else (0, float("nan"), float("nan")))
                rows.append({"symbol": sym, "edge": ename, "cost": rname,
                             "driver": col,
                             "n_plain": n_p, "t_plain": t_p, "exp_plain": e_p,
                             "n_macro": n_c, "t_macro": t_c, "exp_macro": e_c})

    def ranked(rs, key_t, key_n):
        return [r for r in rs if isinstance(r[key_t], float) and r[key_t] == r[key_t]
                and r[key_t] >= SCREEN_BAR and r[key_n] >= 20]

    print(f"{'symbol':<8} {'edge':<24} {'cost':<5} "
          f"{'n':>5} {'t plain':>8} | {'n':>5} {'t macro':>8}")
    best = sorted(rows, key=lambda r: -max(
        r["t_plain"] if r["t_plain"] == r["t_plain"] else -99,
        r["t_macro"] if r["t_macro"] == r["t_macro"] else -99))
    for r in best[:28]:
        fp = f"{r['t_plain']:8.2f}" if r["t_plain"] == r["t_plain"] else "     n/a"
        fc = f"{r['t_macro']:8.2f}" if r["t_macro"] == r["t_macro"] else "     n/a"
        print(f"{r['symbol']:<8} {r['edge']:<24} {r['cost']:<5} "
              f"{r['n_plain']:5d} {fp} | {r['n_macro']:5d} {fc}")

    print("\nRANKED CELLS BY COST REGIME (screening bar, n>=20):")
    for rname in COST_REGIMES:
        sub = [r for r in rows if r["cost"] == rname]
        rp = ranked(sub, "t_plain", "n_plain")
        rm = ranked(sub, "t_macro", "n_macro")
        print(f"  {rname:<5} plain {len(rp):>3}/{len(sub)}   "
              f"macro-conditioned {len(rm):>3}/{len(sub)}")

    print("\nTOP RANKED (any regime):")
    allr = [(r, "plain", r["t_plain"], r["n_plain"], r["exp_plain"]) for r in rows] + \
           [(r, "macro", r["t_macro"], r["n_macro"], r["exp_macro"]) for r in rows]
    allr = [x for x in allr if x[2] == x[2] and x[2] >= SCREEN_BAR and x[3] >= 20]
    for r, arm, t, n, e in sorted(allr, key=lambda x: -x[2])[:15]:
        print(f"  {r['symbol']:<8} {r['edge']:<24} {r['cost']:<5} {arm:<6} "
              f"n={n:5d} t={t:6.2f} exp={e:+.4f}R")
    if not allr:
        print("  none.")

    out = BASE / "reports" / "edges_macro_fusion_sweep.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"screen_bar": SCREEN_BAR, "rows": rows}, indent=2,
                              default=str), encoding="utf-8")
    print(f"\n-> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
