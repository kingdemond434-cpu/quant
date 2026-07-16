"""Block and stationary bootstrap (autocorrelation-preserving resampling).

Never use an i.i.d. bootstrap on returns: it destroys autocorrelation and understates
uncertainty. The moving-block and stationary bootstraps resample contiguous blocks instead.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

Statistic = Callable[[np.ndarray], float]


def moving_block_indices(n: int, block: int, rng: np.random.Generator) -> np.ndarray:
    """Indices for a circular moving-block bootstrap of length ``n``."""
    if block < 1:
        raise ValueError("block size must be >= 1")
    n_blocks = int(np.ceil(n / block))
    starts = rng.integers(0, n, size=n_blocks)
    offsets = np.arange(block)
    idx = ((starts[:, None] + offsets[None, :]) % n).reshape(-1)
    return idx[:n]


def stationary_block_indices(n: int, mean_block: float, rng: np.random.Generator) -> np.ndarray:
    """Indices for a stationary bootstrap (geometric block lengths)."""
    if mean_block < 1:
        raise ValueError("mean_block must be >= 1")
    p = 1.0 / mean_block
    idx = np.empty(n, dtype=int)
    idx[0] = rng.integers(0, n)
    coin = rng.random(n)
    for t in range(1, n):
        idx[t] = rng.integers(0, n) if coin[t] < p else (idx[t - 1] + 1) % n
    return idx


def block_bootstrap(
    x: np.ndarray, statistic: Statistic, *, block: int = 10, n_boot: int = 1000, seed: int = 0
) -> np.ndarray:
    """Moving-block bootstrap distribution of ``statistic``."""
    arr = np.asarray(x, dtype="float64")
    rng = np.random.default_rng(seed)
    out = np.empty(n_boot, dtype="float64")
    for b in range(n_boot):
        out[b] = statistic(arr[moving_block_indices(len(arr), block, rng)])
    return out


def stationary_bootstrap(
    x: np.ndarray,
    statistic: Statistic,
    *,
    mean_block: float = 10,
    n_boot: int = 1000,
    seed: int = 0,
) -> np.ndarray:
    """Stationary bootstrap distribution of ``statistic``."""
    arr = np.asarray(x, dtype="float64")
    rng = np.random.default_rng(seed)
    out = np.empty(n_boot, dtype="float64")
    for b in range(n_boot):
        out[b] = statistic(arr[stationary_block_indices(len(arr), mean_block, rng)])
    return out


def confidence_interval(samples: np.ndarray, *, alpha: float = 0.05) -> tuple[float, float]:
    """Percentile confidence interval at level ``1 - alpha``."""
    arr = np.asarray(samples, dtype="float64")
    lo = float(np.percentile(arr, 100 * alpha / 2))
    hi = float(np.percentile(arr, 100 * (1 - alpha / 2)))
    return lo, hi
