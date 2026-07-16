"""Deflated Sharpe Ratio and friends (multiple-testing aware significance).

The Probabilistic Sharpe Ratio adjusts a Sharpe for sample length, skew, and kurtosis. The
Deflated Sharpe Ratio additionally raises the benchmark to the *expected maximum* Sharpe under
N trials — so the more configurations searched, the higher the bar (Bailey & López de Prado).
"""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel, ConfigDict
from scipy.stats import kurtosis, norm, skew

from libs.validation.errors import ValidationError

EULER_MASCHERONI = 0.5772156649015329


def sharpe_ratio(returns: np.ndarray, *, ddof: int = 1) -> float:
    """Per-period Sharpe ratio (mean / std). Returns 0 if std is 0."""
    r = np.asarray(returns, dtype="float64")
    if len(r) == 0:
        return 0.0
    std = float(r.std(ddof=ddof))
    return float(r.mean() / std) if std > 0 else 0.0


def probabilistic_sharpe_ratio(returns: np.ndarray, *, sr_benchmark: float = 0.0) -> float:
    """P(true Sharpe > benchmark) given the sample, accounting for skew/kurtosis."""
    r = np.asarray(returns, dtype="float64")
    n = len(r)
    if n < 3:
        return 0.0
    sr = sharpe_ratio(r)
    g3 = float(skew(r, bias=False))
    g4 = float(kurtosis(r, fisher=False, bias=False))  # non-excess (normal = 3)
    denom = 1.0 - g3 * sr + ((g4 - 1.0) / 4.0) * sr**2
    if denom <= 0:
        return 0.0
    z = (sr - sr_benchmark) * np.sqrt(n - 1) / np.sqrt(denom)
    return float(norm.cdf(z))


def expected_max_sharpe(n_trials: int, variance_of_sharpes: float) -> float:
    """Expected maximum Sharpe across ``n_trials`` independent no-skill trials."""
    if n_trials < 2 or variance_of_sharpes <= 0:
        return 0.0
    sigma = np.sqrt(variance_of_sharpes)
    a = norm.ppf(1.0 - 1.0 / n_trials)
    b = norm.ppf(1.0 - 1.0 / (n_trials * np.e))
    return float(sigma * ((1.0 - EULER_MASCHERONI) * a + EULER_MASCHERONI * b))


class DSRResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    dsr: float
    sr_observed: float
    sr0_threshold: float
    n_trials: int
    variance_of_sharpes: float
    passed: bool

    def __bool__(self) -> bool:
        return self.passed


def deflated_sharpe_ratio(
    returns: np.ndarray,
    *,
    n_trials: int,
    variance_of_sharpes: float | None = None,
    sharpe_estimates: np.ndarray | None = None,
    threshold: float = 0.95,
) -> DSRResult:
    """Compute the Deflated Sharpe Ratio and whether it clears ``threshold``."""
    if variance_of_sharpes is None:
        if sharpe_estimates is None:
            raise ValidationError("provide variance_of_sharpes or sharpe_estimates")
        arr = np.asarray(sharpe_estimates, dtype="float64")
        if len(arr) < 2:
            raise ValidationError("need >= 2 sharpe_estimates to estimate variance")
        variance_of_sharpes = float(arr.var(ddof=1))
    sr0 = expected_max_sharpe(n_trials, variance_of_sharpes)
    dsr = probabilistic_sharpe_ratio(returns, sr_benchmark=sr0)
    return DSRResult(
        dsr=dsr,
        sr_observed=sharpe_ratio(returns),
        sr0_threshold=sr0,
        n_trials=n_trials,
        variance_of_sharpes=variance_of_sharpes,
        passed=dsr >= threshold,
    )


def min_track_record_length(
    returns: np.ndarray, *, sr_benchmark: float = 0.0, confidence: float = 0.95
) -> float:
    """Minimum number of observations for the Sharpe to be significant vs the benchmark."""
    r = np.asarray(returns, dtype="float64")
    sr = sharpe_ratio(r)
    if sr <= sr_benchmark:
        return float("inf")
    g3 = float(skew(r, bias=False))
    g4 = float(kurtosis(r, fisher=False, bias=False))
    z = float(norm.ppf(confidence))
    numerator = 1.0 - g3 * sr + ((g4 - 1.0) / 4.0) * sr**2
    return float(1.0 + numerator * (z / (sr - sr_benchmark)) ** 2)
