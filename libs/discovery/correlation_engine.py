"""alpha_correlation_engine — alpha-to-alpha correlation, factor & regime overlap.

Prefers lower correlation and higher diversification benefit over raw standalone CAGR.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
from pydantic import BaseModel, ConfigDict

from libs.discovery.errors import DiscoveryError


class AlphaCorrelationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    average_correlation: float
    factor_overlap: float          # fraction of pairs sharing a family
    regime_overlap: float          # mean cosine similarity of regime-profile vectors
    diversification_contribution: dict[str, float]


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def alpha_correlation(
    returns_matrix: np.ndarray,
    alpha_ids: Sequence[str],
    *,
    families: Sequence[str] | None = None,
    regime_profiles: Sequence[Mapping[str, float]] | None = None,
) -> AlphaCorrelationResult:
    """Measure return correlation, family overlap, and regime overlap across alphas."""
    matrix = np.asarray(returns_matrix, dtype="float64")
    if matrix.ndim != 2 or matrix.shape[1] != len(alpha_ids):
        raise DiscoveryError("returns_matrix columns must match alpha_ids")
    n = matrix.shape[1]
    corr = np.nan_to_num(np.corrcoef(matrix, rowvar=False), nan=0.0)
    off = ~np.eye(n, dtype=bool)
    avg_corr = float(corr[off].mean()) if n > 1 else 0.0

    factor_overlap = 0.0
    if families is not None and n > 1:
        pairs = [
            1.0 if families[i] == families[j] else 0.0
            for i in range(n) for j in range(i + 1, n)
        ]
        factor_overlap = sum(pairs) / len(pairs)

    regime_overlap = 0.0
    if regime_profiles is not None and n > 1:
        keys = sorted({k for p in regime_profiles for k in p})
        vectors = [np.array([p.get(k, 0.0) for k in keys]) for p in regime_profiles]
        sims = [
            _cosine(vectors[i], vectors[j]) for i in range(n) for j in range(i + 1, n)
        ]
        regime_overlap = sum(sims) / len(sims) if sims else 0.0

    div_contribution = {
        alpha_ids[i]: float(1.0 - (corr[i][off[i]].mean() if n > 1 else 0.0)) for i in range(n)
    }
    return AlphaCorrelationResult(
        average_correlation=avg_corr,
        factor_overlap=factor_overlap,
        regime_overlap=regime_overlap,
        diversification_contribution=div_contribution,
    )
