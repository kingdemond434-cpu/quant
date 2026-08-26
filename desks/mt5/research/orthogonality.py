"""Orthogonality test: does AUDJPY add residual P&L beyond the AUDCAD TREND_DAY
cluster? Regresses AUDJPY TREND_DAY daily R on AUDCAD TREND_DAY daily R and
reports residual Sharpe + alpha. If residual Sharpe stays strong, AUDJPY adds
portfolio alpha; if not, it is another expression of the same factor.

Also reports the same for gold_asia vs the AUD cluster (diversifier check).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# QUALIFIED: the DESK-level SUPERSEDED stub shadows the bare name under pytest (see
# research/allocation.py); `research.` cannot be shadowed.
from research.portfolio_projection import build_daily, build_sleeves  # noqa: E402

BASE = Path(__file__).resolve().parent.parent


def residual_stats(y: pd.Series, x: pd.Series) -> dict:
    df = pd.concat([y.rename("y"), x.rename("x")], axis=1).dropna()
    if len(df) < 30:
        return {"n": len(df), "ready": False}
    beta = df["x"].cov(df["y"]) / df["x"].var()
    resid = df["y"] - beta * df["x"]
    alpha = resid.mean()
    rs = resid.std(ddof=1)
    res_sharpe = alpha / rs * np.sqrt(252) if rs > 0 else 0.0
    return {"n": len(df), "ready": True, "beta": float(beta), "alpha_day": float(alpha),
            "residual_sharpe": float(res_sharpe), "corr": float(df["x"].corr(df["y"]))}


def main() -> None:
    sleeves = build_sleeves()
    daily = build_daily(sleeves)
    aud = daily[[c for c in daily.columns if c.startswith("AUDCAD") and "TREND" in c]].sum(axis=1)
    jpy = daily[[c for c in daily.columns if c.startswith("AUDJPY") and "TREND" in c]].sum(axis=1)
    gold = daily[[c for c in daily.columns if c.startswith("gold_asia")]].sum(axis=1)

    out = {}
    if jpy.abs().sum() == 0:
        print("AUDJPY not in survivors yet (hunt12 still sweeping); re-run later")
        out["audjpy"] = {"ready": False}
    else:
        r = residual_stats(jpy, aud)
        out["audjpy_vs_audcad"] = r
        print(f"AUDJPY TREND_DAY vs AUDCAD TREND_DAY cluster: n={r['n']} corr={r['corr']:.3f} "
              f"beta={r['beta']:.3f} residual Sharpe={r['residual_sharpe']:.2f}")

    g = residual_stats(gold, aud)
    out["gold_asia_vs_audcad"] = g
    print(f"gold_asia vs AUDCAD TREND_DAY cluster: n={g['n']} corr={g['corr']:.3f} "
          f"beta={g['beta']:.3f} residual Sharpe={g['residual_sharpe']:.2f}")

    (BASE / "reports" / "orthogonality.json").write_text(
        json.dumps(out, indent=2, default=str), encoding="utf-8")
    print("\n-> reports/orthogonality.json")


if __name__ == "__main__":
    main()