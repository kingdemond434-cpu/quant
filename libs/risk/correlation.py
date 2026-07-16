"""Correlation controls — measure, stress, cluster, and govern by correlation.

Correlations spike toward 1 in crises, so the diversification measured in calm markets
evaporates when you need it. We size against a *stressed* matrix, watch realized correlation
drift as a crowding/crisis early-warning, and cut gross exposure when it rises.
"""

from __future__ import annotations

from typing import cast

import numpy as np
from pydantic import BaseModel, ConfigDict

from libs.risk.config import CorrelationLimits
from libs.risk.errors import RiskError


def rolling_correlation(returns_matrix: np.ndarray, *, window: int | None = None) -> np.ndarray:
    """Correlation matrix of columns (optionally over the last ``window`` rows)."""
    m = np.asarray(returns_matrix, dtype="float64")
    if m.ndim != 2 or m.shape[1] < 2:
        raise RiskError("returns_matrix must be 2-D with >= 2 columns")
    if window is not None:
        m = m[-window:]
    if m.shape[0] < 2:
        raise RiskError("need >= 2 observations for correlation")
    corr = np.corrcoef(m, rowvar=False)
    return cast("np.ndarray", np.nan_to_num(corr, nan=0.0))


def stressed_correlation(corr: np.ndarray, *, stress: float = 0.5) -> np.ndarray:
    """Shrink off-diagonal correlations toward 1 to model crisis convergence."""
    if not 0.0 <= stress <= 1.0:
        raise RiskError("stress must be in [0, 1]")
    c = np.asarray(corr, dtype="float64").copy()
    n = c.shape[0]
    off = ~np.eye(n, dtype=bool)
    c[off] = c[off] + (1.0 - c[off]) * stress
    np.fill_diagonal(c, 1.0)
    return c


def correlation_clusters(corr: np.ndarray, *, threshold: float = 0.7) -> list[list[int]]:
    """Group indices whose pairwise correlation exceeds ``threshold`` (union-find)."""
    c = np.asarray(corr, dtype="float64")
    n = c.shape[0]
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i in range(n):
        for j in range(i + 1, n):
            if abs(c[i, j]) >= threshold:
                parent[find(i)] = find(j)

    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    return [sorted(g) for g in groups.values()]


def diversification_score(weights: np.ndarray, corr: np.ndarray) -> float:
    """Diversification ratio (Σ|w_i|) / sqrt(wᵀCw); 1 = no diversification, higher = better."""
    w = np.asarray(weights, dtype="float64")
    c = np.asarray(corr, dtype="float64")
    port_vol = float(np.sqrt(w @ c @ w))
    if port_vol <= 0:
        return 1.0
    return float(np.abs(w).sum() / port_vol)


def average_off_diagonal(corr: np.ndarray) -> float:
    """Mean of the off-diagonal correlations."""
    c = np.asarray(corr, dtype="float64")
    n = c.shape[0]
    if n < 2:
        return 0.0
    off = ~np.eye(n, dtype=bool)
    return float(c[off].mean())


class CorrelationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    average_correlation: float
    scalar: float  # exposure scalar in (0, 1]
    crisis_convergence: bool

    def __bool__(self) -> bool:
        return not self.crisis_convergence


def correlation_scalar(average_correlation: float, limits: CorrelationLimits) -> float:
    """Exposure scalar in (0, 1] that falls as average correlation rises past the limit."""
    if average_correlation <= limits.max_avg_corr:
        return 1.0
    if average_correlation >= limits.crisis_avg_corr:
        return limits.cut_scalar_floor
    span = limits.crisis_avg_corr - limits.max_avg_corr
    frac = (average_correlation - limits.max_avg_corr) / span if span > 0 else 1.0
    return 1.0 - frac * (1.0 - limits.cut_scalar_floor)


def check_correlation_limits(
    corr: np.ndarray, *, limits: CorrelationLimits | None = None
) -> CorrelationResult:
    """Return an exposure scalar that falls as average correlation rises past the limit."""
    cfg = limits or CorrelationLimits()
    avg = average_off_diagonal(corr)
    return CorrelationResult(
        average_correlation=avg,
        scalar=correlation_scalar(avg, cfg),
        crisis_convergence=avg >= cfg.crisis_avg_corr,
    )
