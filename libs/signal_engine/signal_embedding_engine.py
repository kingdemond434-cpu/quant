"""Signal embedding engine — embed trade candidates for similarity and de-duplication.

Turns a :class:`TradeCandidate` into a fixed-length numeric vector (its scores plus a regime
one-hot) so signals can be compared and clustered. Tight clusters reveal redundant signals that
would otherwise masquerade as diversification.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np

from libs.signal_engine.models import Regime, TradeCandidate

_EPS = 1e-12
_REGIMES = tuple(Regime)


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
    if na <= _EPS or nb <= _EPS:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


class SignalEmbeddingEngine:
    """Builds candidate embeddings and clusters near-duplicate signals."""

    def embed(self, candidate: TradeCandidate) -> list[float]:
        scores = [
            candidate.edge.edge_score / 100.0,
            candidate.confidence.confidence,
            candidate.quality.quality_score / 100.0,
            candidate.persistence.persistence_score / 100.0,
            candidate.stability.stability_score / 100.0,
            candidate.capacity.future_capacity_score / 100.0,
            candidate.institutional.score / 100.0,
        ]
        one_hot = [1.0 if candidate.regime is r else 0.0 for r in _REGIMES]
        return scores + one_hot

    def similarity(self, a: TradeCandidate, b: TradeCandidate) -> float:
        return _cosine(np.array(self.embed(a)), np.array(self.embed(b)))

    def cluster(
        self, candidates: Mapping[str, TradeCandidate], *, threshold: float = 0.98
    ) -> list[list[str]]:
        vectors = {sym: np.array(self.embed(c)) for sym, c in candidates.items()}
        clusters: list[list[str]] = []
        centroids: list[np.ndarray] = []
        for sym, vec in vectors.items():
            placed = False
            for i, centroid in enumerate(centroids):
                if _cosine(vec, centroid) >= threshold:
                    clusters[i].append(sym)
                    placed = True
                    break
            if not placed:
                clusters.append([sym])
                centroids.append(vec)
        return clusters
