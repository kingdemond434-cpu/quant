"""Fixtures and builders for the validation test suite."""

from __future__ import annotations

import numpy as np


def strong_returns(
    *, n: int = 400, mu: float = 0.02, sd: float = 0.01, seed: int = 1
) -> np.ndarray:
    """A return series with a clear positive edge."""
    return np.random.default_rng(seed).normal(mu, sd, size=n)


def noise_returns(*, n: int = 400, sd: float = 0.01, seed: int = 2) -> np.ndarray:
    return np.random.default_rng(seed).normal(0.0, sd, size=n)


def edge_matrix(
    *, t: int = 300, n: int = 10, best: float = 0.02, sd: float = 0.01, seed: int = 0
) -> np.ndarray:
    """A (T x N) matrix where column 0 carries a persistent edge and the rest are noise."""
    rng = np.random.default_rng(seed)
    matrix = rng.normal(0.0, sd, size=(t, n))
    matrix[:, 0] += best
    return matrix


def noise_matrix(*, t: int = 300, n: int = 10, sd: float = 0.01, seed: int = 3) -> np.ndarray:
    return np.random.default_rng(seed).normal(0.0, sd, size=(t, n))


def complete_prior() -> dict[str, str]:
    return {
        "mechanism": "behavioral",
        "why_it_works": "short-term overreaction in gold around the London open",
        "why_it_might_fail": "the pattern is arbitraged away as it becomes known",
        "why_overfit": "the entry window could be fit to the magic minute",
        "why_decay": "crowding and liquidity changes erode it",
        "how_detect_decay": "CUSUM on live IC vs backtest confidence band",
        "what_replaces_it": "an adjacent session-effect hypothesis from the same family",
    }
