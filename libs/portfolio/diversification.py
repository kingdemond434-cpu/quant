"""Diversification analytics and correlation controls."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np

from libs.portfolio.covariance import cov_to_corr
from libs.risk.correlation import correlation_clusters


def diversification_ratio(weights: np.ndarray, cov: np.ndarray) -> float:
    """(sum |w_i| * sigma_i) / sqrt(w' Cov w): 1 = no diversification, higher = more."""
    w = np.asarray(weights, dtype="float64")
    sigma = np.sqrt(np.diag(np.asarray(cov, dtype="float64")))
    port_vol = float(np.sqrt(w @ cov @ w))
    if port_vol <= 0:
        return 1.0
    return float(np.abs(w) @ sigma / port_vol)


def concentration(weights: np.ndarray) -> float:
    """Herfindahl concentration (sum of squared weights); lower = more diversified."""
    w = np.asarray(weights, dtype="float64")
    return float(np.sum(w**2))


def effective_bets(weights: np.ndarray) -> float:
    """Effective number of independent bets = 1 / concentration."""
    hhi = concentration(weights)
    return 1.0 / hhi if hhi > 0 else 0.0


def apply_correlation_controls(
    weights: Mapping[str, float],
    cov: np.ndarray,
    order: Sequence[str],
    *,
    cluster_threshold: float = 0.8,
    max_cluster_weight: float = 0.60,
) -> tuple[dict[str, float], list[str]]:
    """Cap the total weight of any highly-correlated cluster of alphas."""
    corr = cov_to_corr(np.asarray(cov, dtype="float64"))
    clusters = correlation_clusters(corr, threshold=cluster_threshold)
    out = {i: float(weights[i]) for i in order}
    binding: list[str] = []
    for cluster in clusters:
        if len(cluster) <= 1:
            continue
        members = [order[idx] for idx in cluster]
        total = sum(out[m] for m in members)
        if total > max_cluster_weight and total > 0:
            scale = max_cluster_weight / total
            for m in members:
                out[m] *= scale
            binding.append("correlation_cluster:" + ",".join(sorted(members)))
    return out, binding
