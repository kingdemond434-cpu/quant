"""Strategy similarity engine — prevent research duplication.

Compares a candidate strategy against an existing one across return, signal, factor, and feature
space. A candidate that is ~95% identical to something already validated is flagged as a
duplicate so research effort is not wasted re-discovering known edge.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np

from libs.alpha_factory.models import SimilarityResult

_EPS = 1e-12


def _cosine(a: Mapping[str, float], b: Mapping[str, float]) -> float:
    keys = set(a) | set(b)
    if not keys:
        return 0.0
    va = np.array([a.get(k, 0.0) for k in keys], dtype="float64")
    vb = np.array([b.get(k, 0.0) for k in keys], dtype="float64")
    na, nb = float(np.linalg.norm(va)), float(np.linalg.norm(vb))
    if na <= _EPS or nb <= _EPS:
        return 0.0
    return float(np.dot(va, vb) / (na * nb))


def _abs_pearson(a: Sequence[float], b: Sequence[float]) -> float:
    x, y = np.asarray(a, dtype="float64"), np.asarray(b, dtype="float64")
    if len(x) < 2 or len(x) != len(y) or x.std() <= _EPS or y.std() <= _EPS:
        return 0.0
    return float(abs(np.corrcoef(x, y)[0, 1]))


def _sign_agreement(a: Sequence[float], b: Sequence[float]) -> float:
    x, y = np.sign(np.asarray(a)), np.sign(np.asarray(b))
    if len(x) == 0 or len(x) != len(y):
        return 0.0
    return float(np.mean(x == y))


def _jaccard(a: Sequence[str], b: Sequence[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


class StrategySimilarityEngine:
    """Scores cross-strategy similarity and flags near-duplicates."""

    def __init__(self, *, duplicate_threshold: float = 0.95) -> None:
        self.duplicate_threshold = duplicate_threshold

    def similarity(
        self,
        *,
        returns_a: Sequence[float],
        returns_b: Sequence[float],
        factors_a: Mapping[str, float] | None = None,
        factors_b: Mapping[str, float] | None = None,
        features_a: Sequence[str] | None = None,
        features_b: Sequence[str] | None = None,
    ) -> SimilarityResult:
        return_sim = _abs_pearson(returns_a, returns_b)
        signal_sim = _sign_agreement(returns_a, returns_b)
        factor_sim = _cosine(factors_a or {}, factors_b or {})
        feature_sim = _jaccard(features_a or [], features_b or [])
        overall = float(np.mean([return_sim, signal_sim, factor_sim, feature_sim]))
        return SimilarityResult(
            signal_similarity=signal_sim,
            return_similarity=return_sim,
            factor_similarity=factor_sim,
            feature_similarity=feature_sim,
            overall=overall,
            is_duplicate=overall >= self.duplicate_threshold,
        )
