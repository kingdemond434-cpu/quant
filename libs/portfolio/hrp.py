"""Hierarchical Risk Parity (López de Prado).

Correlation clustering -> quasi-diagonalization -> recursive bisection with inverse-variance
allocation. No matrix inversion, so it is robust to the unstable covariances that wreck Markowitz.
"""

from __future__ import annotations

from typing import cast

import numpy as np
from scipy.cluster.hierarchy import linkage
from scipy.spatial.distance import squareform

from libs.portfolio.covariance import cov_to_corr


def _quasi_diag(link: np.ndarray, num_items: int) -> list[int]:
    links = link.astype(int)
    current = [int(links[-1, 0]), int(links[-1, 1])]
    while max(current) >= num_items:
        expanded: list[int] = []
        for item in current:
            if item < num_items:
                expanded.append(item)
            else:
                row = links[item - num_items]
                expanded.append(int(row[0]))
                expanded.append(int(row[1]))
        current = expanded
    return current


def _cluster_variance(cov: np.ndarray, items: list[int]) -> float:
    sub = cov[np.ix_(items, items)]
    inv_var = 1.0 / np.diag(sub)
    weights = inv_var / inv_var.sum()
    return float(weights @ sub @ weights)


def hrp_weights(cov: np.ndarray) -> np.ndarray:
    """Compute HRP weights for a covariance matrix (original asset order)."""
    sigma = np.asarray(cov, dtype="float64")
    n = sigma.shape[0]
    if n == 1:
        return np.array([1.0])

    corr = cov_to_corr(sigma)
    distance = np.sqrt(np.clip(0.5 * (1.0 - corr), 0.0, None))
    condensed = squareform(distance, checks=False)
    link = linkage(condensed, method="single")
    sort_ix = _quasi_diag(np.asarray(link), n)

    weights = np.ones(n, dtype="float64")
    clusters: list[list[int]] = [sort_ix]
    while clusters:
        next_clusters: list[list[int]] = []
        for cluster in clusters:
            if len(cluster) <= 1:
                continue
            mid = len(cluster) // 2
            left, right = cluster[:mid], cluster[mid:]
            var_left = _cluster_variance(sigma, left)
            var_right = _cluster_variance(sigma, right)
            alpha = 1.0 - var_left / (var_left + var_right)
            for i in left:
                weights[i] *= alpha
            for i in right:
                weights[i] *= 1.0 - alpha
            next_clusters.extend((left, right))
        clusters = next_clusters

    return cast("np.ndarray", weights / weights.sum())
