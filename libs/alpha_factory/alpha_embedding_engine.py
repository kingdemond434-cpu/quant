"""Alpha embedding engine — embed alphas into a vector space for clustering/crowding.

Turns an :class:`AlphaDNA` into a fixed-length numeric embedding so alphas can be compared and
clustered. Greedy cosine clustering surfaces duplicated alpha families and latent crowding (many
near-identical alphas masquerading as diversification).
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np

from libs.alpha_factory.models import AlphaDNA

_EPS = 1e-12
# Fixed projection axes so every embedding is comparable across alphas.
_FACTORS = ("momentum", "value", "growth", "quality", "carry", "volatility", "liquidity", "macro")
_REGIMES = ("trend", "range", "momentum", "mean_reversion", "volatility", "crisis", "neutral")


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
    if na <= _EPS or nb <= _EPS:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


class AlphaEmbeddingEngine:
    """Builds DNA embeddings and clusters alphas by cosine similarity."""

    def embed(self, dna: AlphaDNA) -> list[float]:
        factors = [float(dna.factor_exposures.get(f, 0.0)) for f in _FACTORS]
        regimes = [float(dna.regime_affinity.get(r, 0.0)) for r in _REGIMES]
        return dna.numeric_vector() + factors + regimes

    def similarity(self, a: AlphaDNA, b: AlphaDNA) -> float:
        return _cosine(np.array(self.embed(a)), np.array(self.embed(b)))

    def cluster(
        self, dnas: Mapping[str, AlphaDNA], *, threshold: float = 0.95
    ) -> list[list[str]]:
        """Greedy single-pass clustering; clusters of >1 reveal duplication/crowding."""
        vectors = {aid: np.array(self.embed(d)) for aid, d in dnas.items()}
        clusters: list[list[str]] = []
        centroids: list[np.ndarray] = []
        for aid, vec in vectors.items():
            placed = False
            for i, centroid in enumerate(centroids):
                if _cosine(vec, centroid) >= threshold:
                    clusters[i].append(aid)
                    placed = True
                    break
            if not placed:
                clusters.append([aid])
                centroids.append(vec)
        return clusters
