"""Does macro conditioning change anything? Screened, ranked, not promoted.

    python research/run_macro_conditioned_sweep.py

THE QUESTION

`data/cross_asset_anchors.pkl` carries a daily 10y real yield back to 2010
(DGS10 - T10YIE). Gold pays no coupon, so the real yield is literally its
opportunity cost, and the standing macro claim is that gold rises when real
yields fall. That claim is testable on data this desk already has, and had
never been tested here because nothing read the macro artifacts at all.

This runs each family BOTH ways -- unconditioned, and conditioned on the
macro state the mechanism's economics actually name -- and reports the pair
side by side. The interesting number is not either t-stat alone; it is the
DIFFERENCE, because that is the only thing attributable to the macro
conditioning rather than to the underlying family.

WHICH CONDITION FOR WHICH ASSET, AND WHY THAT MAPPING

  metals   REAL_YIELD_10Y falling  -- opportunity cost of a zero-coupon asset
  FX       DXY falling             -- the dollar leg of a USD-quoted pair
  crypto   VIX falling             -- risk appetite; these trade as risk assets

Each mapping is an economic argument, written down so it can be disagreed
with. A condition chosen because it improved the number, rather than because
the mechanism implies it, is curve-fitting with extra steps.

WHAT BAR APPLIES -- AND THIS IS THE PART THAT CHANGED

Per docs/research/TWO_STAGE_DISCOVERY_LAW.md (principal, 2026-07-23), a
backtest sweep is STAGE A: a RANKING DEVICE with ZERO promotion authority.
Its multiplicity arithmetic "cannot create a phantom edge no matter what it
is" because nothing screened here is ever validated -- promotion happens
only from forward evidence accrued after pre-registration, in one of the 12
confirmation slots, under `forward_stats.holm_bar`.

So this sweep reports the SCREENING bar (t >= 1.96) as its ranking
threshold, and prints the deflated bar alongside for reference ONLY. Neither
number promotes anything. Calling a Stage-A result a "kill" -- as an earlier
sweep in this repo did -- overstates what a screen can conclude in exactly
the direction that discards live candidates.
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
from mt5desk.multiplicity import deflation  # noqa: E402

BASE = Path(__file__).resolve().parent.parent
UNI = BASE / "data" / "universe"

SCREEN_BAR = 1.96

#: symbol -> (macro column, lookback days for the change, economic reason)
CONDITION = {
    "XAUUSD": ("REAL_YIELD_10Y", 20, "zero-coupon: real yield IS the carry cost"),
    "XAGUSD": ("REAL_YIELD_10Y", 20, "same carry logic, higher beta"),
    "GBPUSD": ("DXY", 20, "USD-quoted: the dollar is half the pair"),
    "AUDUSD": ("DXY", 20, "USD-quoted, and a risk-sensitive commodity currency"),
    "NZDUSD": ("DXY", 20, "USD-quoted, risk-sensitive"),
    "BTCUSD": ("VIX", 20, "trades as a risk asset, not as digital gold"),
    "ETHUSD": ("VIX", 20, "trades as a risk asset"),
}

FAMILIES = {
    "dip_pullback": (families.family_dip_pullback_pct, {"pullback_pct": 0.05}),
    "dip_rsi": (families.family_dip_rsi_reclaim, {"oversold": 30.0}),
    "dip_shock": (families.family_dip_atr_shock, {"atr_k": 2.0}),
}


def _t(trades) -> tuple[int, float, float]:
    n = len(trades)
    if n < 20:
        return n, float("nan"), float("nan")
    r = np.array([t.r_multiple for t in trades])
    return n, float(r.mean() / (r.std(ddof=1) / np.sqrt(n))), float(r.mean())


def _favourable(hist: pd.DataFrame, col: str, lookback: int) -> pd.Series:
    """Dates where `col` has FALLEN over `lookback` days.

    Falling real yields / dollar / VIX is the supportive state for every
    mapping above. Uses a strict decrease so a flat series is NOT counted as
    favourable -- 'not rising' and 'falling' are different claims and only
    the second is the one being tested.
    """
    if col not in hist.columns:
        return pd.Series(dtype=bool)
    s = hist[col].dropna()
    return (s - s.shift(lookback)) < 0


def main() -> int:
    meta = json.loads((UNI / "universe.json").read_text(encoding="utf-8"))
    hist = macro_regime.load_history()
    if hist is None:
        print("MACRO HISTORY ABSENT (data/cross_asset_anchors.pkl) -- this sweep "
              "cannot run. That is UNMEASURED, not a clean result.")
        return 2

    pairs = [(s, f) for s in CONDITION for f in FAMILIES if (UNI / f"{s}_H1.parquet").exists()]
    trials = len(pairs) * 2          # each cell run unconditioned AND conditioned
    print(f"Macro-conditioned sweep: {len(pairs)} cells x 2 arms = {trials} runs")
    print(f"STAGE A = RANKING (TWO_STAGE_DISCOVERY_LAW). screening bar t >= {SCREEN_BAR}")
    print(f"[deflated bar for {trials} would be {1.96 + deflation(trials):.2f} -- "
          f"reference only, promotes nothing]\n")

    rows = []
    for sym, fam in pairs:
        col, lookback, why = CONDITION[sym]
        h1 = pd.read_parquet(UNI / f"{sym}_H1.parquet")
        costs = Costs.from_symbol(meta[sym], mult=2.0)
        fn, params = FAMILIES[fam]
        sigs = fn(h1, **params)
        if not sigs:
            continue

        n_u, t_u, e_u = _t(run_backtest(h1, sigs, costs).trades)

        fav = _favourable(hist, col, lookback)
        if fav.empty:
            continue
        fav_dates = set(fav[fav].index.date)
        cond = [s for s in sigs if s.time.date() in fav_dates]
        n_c, t_c, e_c = _t(run_backtest(h1, cond, costs).trades) if cond else (0, float("nan"), float("nan"))

        rows.append({"symbol": sym, "family": fam, "condition": f"{col} falling {lookback}d",
                     "why": why, "n_uncond": n_u, "t_uncond": t_u, "exp_uncond": e_u,
                     "n_cond": n_c, "t_cond": t_c, "exp_cond": e_c,
                     "t_delta": (t_c - t_u) if (t_c == t_c and t_u == t_u) else float("nan")})

    print(f"{'symbol':<8} {'family':<14} {'condition':<24} "
          f"{'n_u':>5} {'t_u':>6} | {'n_c':>5} {'t_c':>6} | {'Δt':>6}")
    for r in sorted(rows, key=lambda r: -(r["t_delta"] if r["t_delta"] == r["t_delta"] else -99)):
        f2 = lambda v: f"{v:6.2f}" if v == v else "   n/a"   # noqa: E731
        print(f"{r['symbol']:<8} {r['family']:<14} {r['condition']:<24} "
              f"{r['n_uncond']:5d} {f2(r['t_uncond'])} | {r['n_cond']:5d} {f2(r['t_cond'])} "
              f"| {f2(r['t_delta'])}")

    helped = [r for r in rows if r["t_delta"] == r["t_delta"] and r["t_delta"] > 0]
    ranked = [r for r in rows if r["t_cond"] == r["t_cond"] and r["t_cond"] >= SCREEN_BAR]
    print(f"\nmacro conditioning RAISED t in {len(helped)}/{len(rows)} cells.")
    print(f"{len(ranked)} conditioned cell(s) clear the SCREENING bar t >= {SCREEN_BAR} "
          f"-- these are RANKED CANDIDATES for a forward slot, not survivors.")
    if not ranked:
        print("Nothing ranks. Under the two-stage law that is a screening outcome, "
              "not a verdict on the mechanism -- no forward evidence has been spent.")

    out = BASE / "reports" / "macro_conditioned_sweep.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"screen_bar": SCREEN_BAR, "runs": trials, "rows": rows},
                              indent=2, default=str), encoding="utf-8")
    print(f"\n-> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
