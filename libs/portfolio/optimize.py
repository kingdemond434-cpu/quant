"""Robust portfolio optimization — risk-parity base, quality-tilted, diversification-aware.

Prefers multiple uncorrelated alphas over a single high-CAGR one: it starts from equal-risk
weights, tilts modestly toward quality (Sharpe, penalized for decay and instability) and toward
low-correlation alphas, then shrinks back to the risk-parity base to tame estimation noise.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast

import numpy as np

from libs.portfolio.covariance import covariance_from_alphas
from libs.portfolio.errors import PortfolioError
from libs.portfolio.models import AlphaInput
from libs.portfolio.risk_parity import risk_parity_weights


def _quality(alphas: Sequence[AlphaInput]) -> np.ndarray:
    q = np.array(
        [
            max(0.0, a.expected_sharpe)
            * (1.0 - min(max(a.decay_score, 0.0), 1.0))
            * min(max(a.stability, 0.0), 1.0)
            for a in alphas
        ],
        dtype="float64",
    )
    return q if q.sum() > 0 else np.ones(len(alphas))


def _diversification_preference(correlation: np.ndarray | None, n: int) -> np.ndarray:
    if correlation is None or n < 2:
        return np.ones(n)
    corr = np.asarray(correlation, dtype="float64")
    avg_corr = (corr.sum(axis=1) - 1.0) / (n - 1)
    return cast("np.ndarray", np.clip(1.0 - avg_corr, 0.05, None))


def optimize_portfolio(
    alphas: Sequence[AlphaInput],
    *,
    correlation: np.ndarray | None = None,
    shrink: float = 0.5,
) -> dict[str, float]:
    """Compute robustness-weighted target weights (shrunk toward risk parity)."""
    if not 0.0 <= shrink <= 1.0:
        raise PortfolioError("shrink must be in [0, 1]")
    cov = covariance_from_alphas(alphas, correlation)
    base = risk_parity_weights(cov)

    quality = _quality(alphas)
    div_pref = _diversification_preference(correlation, len(alphas))
    tilt = (quality / quality.mean()) * div_pref

    raw = base * tilt
    raw = raw / raw.sum()
    weights = (1.0 - shrink) * base + shrink * raw
    weights = cast("np.ndarray", weights / weights.sum())
    return {alpha.alpha_id: float(w) for alpha, w in zip(alphas, weights, strict=True)}
