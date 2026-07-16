"""Correlation shock engine — diversification failure under regime transition.

In a crisis, correlations converge toward 1 and diversification evaporates. This simulates that
convergence and measures the effective-bets lost, producing a 0-100 fragility score.
"""

from __future__ import annotations

import numpy as np

from libs.stage14_5.errors import Stage14_5Error
from libs.stage14_5.models import CorrelationShockResult


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _avg_off_diagonal(corr: np.ndarray) -> float:
    n = corr.shape[0]
    if n < 2:
        return 0.0
    iu = np.triu_indices(n, k=1)
    return float(np.mean(corr[iu]))


def _effective_bets(avg_corr: float, n: int) -> float:
    # Equal-weight effective number of bets given an average pairwise correlation.
    denom = 1.0 + (n - 1) * max(0.0, avg_corr)
    return n / denom if denom > 0 else float(n)


class CorrelationShockEngine:
    """Simulates correlation convergence and scores diversification fragility."""

    def __init__(self, *, shock: float = 0.5, threshold: float = 50.0) -> None:
        self.shock = _clip01(shock)
        self.threshold = threshold

    def simulate(self, correlation: np.ndarray) -> CorrelationShockResult:
        corr = np.asarray(correlation, dtype="float64")
        n = corr.shape[0]
        if corr.ndim != 2 or corr.shape[1] != n:
            raise Stage14_5Error("correlation must be square")
        base = _avg_off_diagonal(corr)
        shocked = base + self.shock * (1.0 - base)  # converge toward 1.0
        eb_base = _effective_bets(base, n) if n > 1 else 1.0
        eb_shocked = _effective_bets(shocked, n) if n > 1 else 1.0
        loss = _clip01(1.0 - eb_shocked / eb_base) if eb_base > 0 else 0.0
        score = 100.0 * loss
        return CorrelationShockResult(
            base_avg_correlation=base, shocked_avg_correlation=shocked,
            diversification_loss=loss, correlation_fragility_score=score,
            fragile=score > self.threshold,
        )
