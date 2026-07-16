"""Forward-validation statistics -- honest significance for shadow-track promotion.

Closes the two statistical leaks named by the 2026-07-12 external adversarial review
(five independent models converged on both):

  1. AUTOCORRELATION. The naive forward t-stat Sharpe*sqrt(days/365) assumes IID daily
     returns. Funding-carry returns are serially correlated (funding is sticky, basis
     mean-reverts slowly), so the effective sample is smaller than the calendar sample
     and the naive t OVERSTATES significance exactly when N is small. `nw_tstat` shrinks
     N by the Newey-West/Bartlett factor 1 + 2*sum_k (1 - k/(L+1)) * rho_k.
  2. MULTIPLE TESTING. Monitoring m candidates in parallel against a per-strategy 1.65
     bar gives family-wise alpha ~1-(0.95^m), not 5%. `holm_bar` returns the Holm
     step-down per-candidate t threshold. The PRE-REGISTERED PRIMARY hypothesis (carry,
     registered alone before any cohort existed) is exempt -- the clinical-trial
     primary-endpoint convention; the correction applies to the later cohort.

Conservative by construction: the autocorrelation factor is clamped to >= 1 (never award
MORE significance than IID) and <= 5 (a noisy rho estimate must not nuke a real edge).
Pure numpy + stdlib -> cheap every cycle, deterministic, testable.
"""

from __future__ import annotations

import math
from statistics import NormalDist

import numpy as np

_PPY = 365.0


def autocorr_factor(returns: np.ndarray, max_lags: int | None = None) -> float:
    """Bartlett-weighted variance-inflation factor for serially correlated returns.

    factor = 1 + 2 * sum_{k=1..L} (1 - k/(L+1)) * rho_k, clamped to [1, 5].
    Effective N = N / factor.
    """
    r = np.asarray(returns, dtype="float64")
    r = r[np.isfinite(r)]
    n = len(r)
    if n < 20 or float(np.std(r)) == 0.0:
        return 1.0
    lags = max_lags if max_lags is not None else min(10, n // 5)
    mu, var = float(np.mean(r)), float(np.var(r))
    acc = 0.0
    for k in range(1, lags + 1):
        rho = float(np.mean((r[:-k] - mu) * (r[k:] - mu))) / var
        acc += (1.0 - k / (lags + 1.0)) * rho
    return float(min(5.0, max(1.0, 1.0 + 2.0 * acc)))


def nw_tstat(returns: np.ndarray, *, ppy: float = _PPY) -> float:
    """Newey-West-corrected forward t-stat: ann_Sharpe * sqrt(effective_days / ppy).

    Equals the naive t when returns are uncorrelated; strictly smaller when they are
    positively autocorrelated. This is the number the promotion gates consume.
    """
    r = np.asarray(returns, dtype="float64")
    r = r[np.isfinite(r)]
    n = len(r)
    sd = float(np.std(r, ddof=1)) if n > 2 else 0.0
    if n < 5 or sd == 0.0:
        return 0.0
    sharpe_ann = float(np.mean(r)) / sd * math.sqrt(ppy)
    n_eff = n / autocorr_factor(r)
    return round(sharpe_ann * math.sqrt(n_eff / ppy), 2)


def holm_bar(m: int, rank: int = 1, *, alpha: float = 0.05) -> float:
    """Holm step-down one-sided t threshold for the rank-th best of m cohort candidates.

    rank 1 = strongest candidate (bar alpha/m), rank m = weakest (bar alpha). The
    pre-registered PRIMARY hypothesis is exempt (use the plain 1.65 bar); this applies
    to the concurrently-monitored candidate cohort only.
    """
    m, rank = max(1, int(m)), max(1, int(rank))
    adj = alpha / max(1, m - min(rank, m) + 1)
    return round(NormalDist().inv_cdf(1.0 - adj), 2)
