"""Fixtures and builders for the portfolio test suite."""

from __future__ import annotations

from typing import Any

import numpy as np

from libs.portfolio.models import AlphaInput, StrategyType
from libs.risk.instruments import Factor


def make_alpha(alpha_id: str, **overrides: Any) -> AlphaInput:
    defaults: dict[str, Any] = {
        "alpha_id": alpha_id,
        "volatility": 0.10,
        "factor": Factor.PRECIOUS_METALS,
        "strategy_type": StrategyType.TREND,
        "expected_return": 0.20,
        "expected_sharpe": 1.0,
        "expected_drawdown": 0.10,
        "decay_score": 0.0,
        "stability": 1.0,
    }
    defaults.update(overrides)
    return AlphaInput(**defaults)


def constant_correlation(n: int, rho: float) -> np.ndarray:
    corr = np.full((n, n), rho, dtype="float64")
    np.fill_diagonal(corr, 1.0)
    return corr


def synthetic_returns(n: int = 300, k: int = 3, *, seed: int = 0) -> np.ndarray:
    """Independent positive-drift return columns for analytics tests."""
    rng = np.random.default_rng(seed)
    return rng.normal(0.001, 0.01, size=(n, k))
