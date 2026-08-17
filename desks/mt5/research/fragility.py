"""fragility + DSR audit over ALL real survivors at once.

For every REAL survivor (from REAL_SURVIVORS.json):
  - DSR (Deflated Sharpe Ratio, Bailey-Lopez de Prado): Sharpe deflated by the
    multiplicity of the hunt search. PSR normal assumption, gamma = Euler-Mascheroni.
  - Fragility from the reconstructed daily R series (signals rebuilt exactly as the
    hunt generated them, trades grouped by entry day):
      worst_decile_market_exp : mean R on the market's (symbol's) worst 10% days
      max_consec_loss_days, p99_loss_day, max_single_day_loss
  - Pairwise correlation across all survivors' daily R (aligned days).

PASS_DSR     : DSR >= 0.95
PASS_FRAGILE : worst_decile_market_exp >= -0.10R AND p99 single-day loss >= -3.0R
REAL2        : REAL && PASS_DSR && PASS_FRAGILE

Output: reports/REAL_SURVIVORS.json updated with dsr + fragile fields.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
REPORTS = BASE / "reports"
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "research"))

from mt5desk import families  # noqa: E402
from mt5desk.engine import Costs, run_backtest  # noqa: E402

GAMMA = 0.5772156649015329
EULER_E = np.e


def phi_inv(p: float) -> float:
    # Acklam rational approximation of the inverse normal CDF (no scipy dep)
    if p <= 0.0:
        return -8.0
    if p >= 1.0:
        return 8.0
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    plow, phigh = 0.02425, 1.0 - 0.02425
    if p < plow:
        q = np.sqrt(-2.0 * np.log(p))
        return float((((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5])
                     / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0))
    if p <= phigh:
        q = p - 0.5
        r = q * q
        return float((((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q
                     / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1.0))
    q = np.sqrt(-2.0 * np.log(1.0 - p))
    return float(-(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5])
                 / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0))


def phi(x: float) -> float:
    from math import erf
    return float(0.5 * (1.0 + erf(x / np.sqrt(2.0))))


def dsr_for_hunt(hunt: str) -> dict:
    data = json.loads((REPORTS / hunt).read_text("utf-8"))
    cells = data.get("all", [])
    srs = []
    n_cells = 0
    for c in cells:
        n = c.get("n", 0)
        t = c.get("t", 0.0)
        if n and t == t:
            srs.append(t / np.sqrt(n))
            n_cells += 1
    if len(srs) < 30:
        return {"n_trials": n_cells, "sr0": None}
    v = float(np.var(srs))
    if v <= 0:
        return {"n_trials": n_cells, "sr0": 0.0}
    sr0 = np.sqrt(v) * ((1 - GAMMA) * phi_inv(1 - 1.0 / n_cells)
                        + GAMMA * phi_inv(1 - 1.0 / (n_cells * EULER_E)))
    return {"n_trials": n_cells, "sr0": float(sr0)}


def main() -> int:
    sv = json.loads((REPORTS / "REAL_SURVIVORS.json").read_text("utf-8"))
    from run_hunt12 import WINDOWS as W12, day_states  # noqa
    from run_hunt16 import WINDOWS as W16, FAMILIES as F16  # noqa
    meta = json.loads((BASE / "data" / "universe" / "universe.json").read_text("utf-8"))

    h12 = json.loads((REPORTS / "hunt12.json").read_text("utf-8"))
    h16 = json.loads((REPORTS / "hunt16.json").read_text("utf-8"))
    dsr12 = dsr_for_hunt("hunt12.json")
    dsr16 = dsr_for_hunt("hunt16.json")
    h1_cache: dict[str, pd.DataFrame] = {}
    daily_cache: dict[str, pd.DataFrame] = {}

    def symbol_h1(sym: str) -> pd.DataFrame:
        if sym not in h1_cache:
            h1_cache[sym] = families._h1(
                pd.read_parquet(BASE / "data" / "universe" / f"{sym}_H1.parquet"))
        return h1_cache[sym]

    def costs_for(sym: str) -> Costs:
        m = meta.get(sym, {})
        return Costs(
            spread_per_lot=0.48 if sym == "XAUUSD" else max(
                m.get("median_spread_pts", 1) * m.get("tick_size", 1e-5) * m.get("contract_size", 1e5), 0.05),
            commission_per_lot=3.50, contract_oz=m.get("contract_size", 1e5))

    def daily_r(sym: str, hunt: str, row: dict) -> pd.Series:
        key = (sym, hunt, row["fam"], row["side"], row["win"], row["state"])
        if key in daily_cache:
            return daily_cache[key]
        h1 = symbol_h1(sym)
        states = day_states(h1)
        if hunt == "hunt12.json":
            sigs = families.family_session_range_breakout(h1, **W12[row["win"]])
            sdays = [pd.Timestamp(s.time).date() for s in sigs]
        else:
            ffn = F16[row["fam"]]
            sday = W16[row["win"]].get("signal_at") or W16[row["win"]]["range_start"]
            sigs = [s for s in ffn(h1, 1 if row["side"] == "LONG" else -1) if s.time.hour == sday]
            sdays = [pd.Timestamp(s.time).date() for s in sigs]
        sub = [s for s, d in zip(sigs, sdays) if states.get(d) == row["state"]]
        res = run_backtest(h1, sub, costs_for(sym))
        series = pd.Series({pd.Timestamp(t.entry_time).date(): t.r_multiple for t in res.trades},
                           dtype=float)
        series = series.groupby(level=0).sum()
        daily_cache[key] = series
        return series

    mkt_cache: dict[str, pd.Series] = {}

    def market_daily(sym: str) -> pd.Series:
        if sym not in mkt_cache:
            h1 = symbol_h1(sym)
            c = pd.Series(h1["close"].to_numpy(float), index=h1.index)
            mkt_cache[sym] = np.log(c).diff().resample("D").sum().dropna()
        return mkt_cache[sym]

    rows = sv["real_survivors"]
    print(f"auditing {len(rows)} survivors (DSR + fragility + correlation)...", flush=True)
    for r in rows:
        hunt = r["hunt"]
        d = dsr12 if hunt == "hunt12.json" else dsr16
        n = r["n"]
        sr = r["t"] / np.sqrt(n) if n else 0.0
        dsr = phi((sr - d["sr0"]) * np.sqrt(n - 1)) if d.get("sr0") is not None and n > 1 else None
        s = daily_r(r["sym"], hunt, r)
        mk = market_daily(r["sym"])
        joint = pd.concat([s.rename("s"), mk.rename("m")], axis=1, join="inner").dropna()
        worst = joint[joint["m"] <= joint["m"].quantile(0.10)]
        wde = float(worst["s"].mean()) if len(worst) else float("nan")
        p99 = float(s.quantile(0.01)) if len(s) else float("nan")
        neg = s < 0
        consec = 0
        best_streak = 0
        for v in neg:
            consec = consec + 1 if v else 0
            best_streak = max(best_streak, consec)
        r.update(dsr=round(dsr, 3) if dsr is not None else None,
                 dsr_pass=bool(dsr is not None and dsr >= 0.95),
                 worst_decile_market_exp=round(wde, 3),
                 p99_loss_day=round(p99, 3),
                 max_consec_loss_days=int(best_streak),
                 fragile_pass=bool(wde >= -0.10 and p99 >= -3.0),
                 days=len(s))
        r["REAL2"] = bool(r["REAL"] and r["dsr_pass"] and r["fragile_pass"])

    syms = sorted({r["sym"] for r in rows})
    mats: dict[str, pd.DataFrame] = {}
    for sym in syms:
        col = {}
        for r in rows:
            if r["sym"] == sym:
                col[r["hunt"].split(".")[0] + ":" + r["fam"] + ":" + r["side"] + ":" + r["win"] + ":" + r["state"]] = daily_r(sym, r["hunt"], r)
        mats[sym] = pd.DataFrame(col).sort_index()
    corr_pairs = []
    for i in range(len(rows)):
        si = daily_r(rows[i]["sym"], rows[i]["hunt"], rows[i])
        for j in range(i + 1, len(rows)):
            sj = daily_r(rows[j]["sym"], rows[j]["hunt"], rows[j])
            jj = pd.concat([si, sj], axis=1, join="inner").dropna()
            if len(jj) >= 60:
                c = float(jj.iloc[:, 0].corr(jj.iloc[:, 1]))
                if c == c:
                    corr_pairs.append((c, i, j))
    arr = np.array([p[0] for p in corr_pairs]) if corr_pairs else np.array([])
    top = sorted(corr_pairs, reverse=True)[:12]
    corr = {
        "pairs": len(corr_pairs),
        "mean_corr": round(float(arr.mean()), 3) if len(arr) else None,
        "frac_corr_gt_0.3": round(float((arr > 0.3).mean()), 3) if len(arr) else None,
        "frac_corr_gt_0.5": round(float((arr > 0.5).mean()), 3) if len(arr) else None,
        "top_pairs": [{"corr": round(c, 3),
                       "a": f"{rows[i]['sym']} {rows[i]['fam']} {rows[i]['side']} {rows[i]['win']} {rows[i]['state']}",
                       "b": f"{rows[j]['sym']} {rows[j]['fam']} {rows[j]['side']} {rows[j]['win']} {rows[j]['state']}"}
                      for c, i, j in top],
    }
    sv["dsr"] = {"hunt12": dsr12, "hunt16": dsr16}
    sv["correlation"] = corr
    sv["total_real2"] = int(sum(1 for r in rows if r["REAL2"]))
    sv["swept_at"] = datetime.now(timezone.utc).isoformat()
    (REPORTS / "REAL_SURVIVORS.json").write_text(json.dumps(sv, indent=2, default=str),
                                                 encoding="utf-8")
    (REPORTS / "DONE_fragility").write_text(
        datetime.now(timezone.utc).isoformat(), encoding="utf-8")
    n_dsr = sum(1 for r in rows if r["dsr_pass"])
    n_fr = sum(1 for r in rows if r["fragile_pass"])
    n2 = sv["total_real2"]
    print(f"\nDSR pass: {n_dsr}/{len(rows)} | fragile pass: {n_fr}/{len(rows)} | "
          f"REAL2 (all): {n2}/{len(rows)}", flush=True)
    print(f"corr: mean={corr['mean_corr']} frac>0.3={corr['frac_corr_gt_0.3']} "
          f"frac>0.5={corr['frac_corr_gt_0.5']}", flush=True)
    for t in corr["top_pairs"][:5]:
        print(f"  {t['corr']:+.2f}  {t['a']}  <>  {t['b']}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())