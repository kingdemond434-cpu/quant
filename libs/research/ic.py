"""Information Coefficient (IC) toolkit -- judge signals by prediction quality, not backtest Sharpe.

IC is the rank correlation between a signal and the FORWARD return. Elite shops optimise IC because:
(1) it is far harder to overfit than a backtest Sharpe (no position-sizing/exit degrees of freedom),
(2) it is additive across breadth -- the fundamental law of active mgmt, IR ~= IC * sqrt(breadth),
(3) IC decay exposes alpha rot early. This computes per-period cross-sectional IC and its stability
(IC-IR), hit rate, significance, and decay -- the institutional candidate filter.
"""

from __future__ import annotations

import numpy as np
from scipy.stats import rankdata


def _spearman(a: np.ndarray, b: np.ndarray) -> float:
    """Nan-safe Spearman rank correlation between two vectors."""
    m = np.isfinite(a) & np.isfinite(b)
    if int(m.sum()) < 3:
        return float("nan")
    ra = rankdata(a[m]).astype("float64")
    rb = rankdata(b[m]).astype("float64")
    ra -= ra.mean()
    rb -= rb.mean()
    denom = float(np.sqrt((ra * ra).sum() * (rb * rb).sum()))
    return float((ra * rb).sum() / denom) if denom > 0 else float("nan")


def cross_sectional_ic(signal: np.ndarray, fwd: np.ndarray) -> np.ndarray:
    """Per-period cross-sectional IC. signal, fwd are (T, N) arrays (time x assets)."""
    s = np.asarray(signal, dtype="float64")
    f = np.asarray(fwd, dtype="float64")
    return np.array([_spearman(s[t], f[t]) for t in range(s.shape[0])])


def ic_stats(ic: np.ndarray, *, periods_per_year: float = 365.0) -> dict[str, float]:
    """Summary stats of an IC series: mean IC, IC-IR (annualised), hit rate, t-stat, decay."""
    ic = np.asarray(ic, dtype="float64")
    ic = ic[np.isfinite(ic)]
    n = len(ic)
    if n < 5:
        return {"n": float(n), "mean_ic": 0.0, "ic_ir": 0.0, "hit_rate": 0.0,
                "t_stat": 0.0, "ic_decay": 0.0}
    mean = float(np.mean(ic))
    sd = float(np.std(ic))
    icir = (mean / sd) * float(np.sqrt(periods_per_year)) if sd > 0 else 0.0
    hit = float(np.mean(ic > 0))
    tstat = mean / (sd / float(np.sqrt(n))) if sd > 0 else 0.0
    h = n // 2
    decay = float(np.mean(ic[h:]) - np.mean(ic[:h]))      # 2nd-half minus 1st-half (negative=rot)
    return {"n": n, "mean_ic": round(mean, 4), "ic_ir": round(icir, 2),
            "hit_rate": round(hit, 3), "t_stat": round(tstat, 2), "ic_decay": round(decay, 4)}


def evaluate_signal(signal: np.ndarray, fwd: np.ndarray, *,
                    periods_per_year: float = 365.0) -> dict[str, float]:
    """One-call IC evaluation of a (T, N) signal vs its (T, N) forward returns."""
    return ic_stats(cross_sectional_ic(signal, fwd), periods_per_year=periods_per_year)
