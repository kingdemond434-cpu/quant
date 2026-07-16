"""failure_dependency_engine — hidden dependencies between alphas.

Diversification of *failure modes* matters more than diversification of returns: alphas with
uncorrelated returns in calm markets can share a hidden factor that breaks them together in
stress. Measures tail co-failure and drawdown synchronization.
"""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel, ConfigDict

from libs.discovery.errors import DiscoveryError


class FailureDependencyResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    failure_dependency_score: float  # 0-100, higher = more co-dependent (worse)
    independent: bool
    avg_failure_correlation: float
    max_co_failure_probability: float

    def __bool__(self) -> bool:
        return self.independent


def failure_dependency(
    returns_matrix: np.ndarray, *, tail_quantile: float = 0.05, threshold: float = 50.0
) -> FailureDependencyResult:
    """Score how much a set of alphas tends to fail together in the tail."""
    matrix = np.asarray(returns_matrix, dtype="float64")
    if matrix.ndim != 2 or matrix.shape[1] < 2:
        raise DiscoveryError("returns_matrix must be 2-D with >= 2 alphas")
    n = matrix.shape[1]

    tail_flags = np.zeros_like(matrix)
    for k in range(n):
        cutoff = np.quantile(matrix[:, k], tail_quantile)
        tail_flags[:, k] = (matrix[:, k] <= cutoff).astype("float64")

    corr = np.corrcoef(tail_flags, rowvar=False)
    corr = np.nan_to_num(corr, nan=0.0)
    off = ~np.eye(n, dtype=bool)
    avg_failure_corr = float(corr[off].mean())

    max_co_failure = 0.0
    for i in range(n):
        for j in range(i + 1, n):
            both = float(np.mean((tail_flags[:, i] == 1) & (tail_flags[:, j] == 1)))
            max_co_failure = max(max_co_failure, both)

    score = max(0.0, min(100.0, 100.0 * avg_failure_corr))
    return FailureDependencyResult(
        failure_dependency_score=score,
        independent=score <= threshold,
        avg_failure_correlation=avg_failure_corr,
        max_co_failure_probability=max_co_failure,
    )
