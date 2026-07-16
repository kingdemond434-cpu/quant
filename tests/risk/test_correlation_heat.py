"""Correlation control and heat control tests."""

from __future__ import annotations

import numpy as np
import pytest
from tests.risk.conftest import correlated_returns

from libs.risk.correlation import (
    average_off_diagonal,
    check_correlation_limits,
    correlation_clusters,
    diversification_score,
    rolling_correlation,
    stressed_correlation,
)
from libs.risk.heat import PositionHeat, calculate_heat, check_heat_limits


def test_rolling_correlation_shape_and_range() -> None:
    corr = rolling_correlation(correlated_returns(rho=0.5, k=4))
    assert corr.shape == (4, 4)
    assert np.allclose(np.diag(corr), 1.0)


def test_stressed_correlation_pushes_toward_one() -> None:
    corr = rolling_correlation(correlated_returns(rho=0.3, k=3))
    stressed = stressed_correlation(corr, stress=0.5)
    off = ~np.eye(3, dtype=bool)
    assert (stressed[off] >= corr[off] - 1e-9).all()
    assert stressed[off].mean() > corr[off].mean()


def test_correlation_clusters() -> None:
    corr = np.array([[1.0, 0.9, 0.0], [0.9, 1.0, 0.0], [0.0, 0.0, 1.0]])
    clusters = correlation_clusters(corr, threshold=0.7)
    assert [0, 1] in clusters
    assert [2] in clusters


def test_diversification_score_higher_when_uncorrelated() -> None:
    independent = np.eye(3)
    correlated = np.full((3, 3), 0.95)
    np.fill_diagonal(correlated, 1.0)
    weights = np.array([1.0, 1.0, 1.0])
    assert diversification_score(weights, independent) > diversification_score(weights, correlated)


def test_correlation_limit_scalar_decreases_with_rising_correlation() -> None:
    low = check_correlation_limits(rolling_correlation(correlated_returns(rho=0.1, k=4, seed=1)))
    high = check_correlation_limits(rolling_correlation(correlated_returns(rho=0.95, k=4, seed=2)))
    assert low.scalar >= high.scalar
    assert high.crisis_convergence or high.scalar < 1.0


def test_crisis_convergence_detected() -> None:
    corr = np.full((4, 4), 0.95)
    np.fill_diagonal(corr, 1.0)
    result = check_correlation_limits(corr)
    assert result.crisis_convergence
    assert average_off_diagonal(corr) > 0.9


def test_heat_aggregation_and_limits() -> None:
    positions = [
        PositionHeat("XAUUSD", units=10, risk_per_unit=300),   # 3000
        PositionHeat("XAGUSD", units=20, risk_per_unit=100),   # 2000  (same factor)
        PositionHeat("EURUSD", units=1, risk_per_unit=1000),   # 1000
    ]
    heat = calculate_heat(positions)
    assert heat["total"] == pytest.approx(6000.0)
    assert heat["factor:precious_metals"] == pytest.approx(5000.0)
    result = check_heat_limits(heat, equity=100_000.0)
    assert result.ok  # 6% < 20% portfolio cap, each instrument < 5%


def test_heat_breach() -> None:
    positions = [PositionHeat("XAUUSD", units=1, risk_per_unit=30_000)]  # 30% of equity
    heat = calculate_heat(positions)
    result = check_heat_limits(heat, equity=100_000.0)
    assert not result.ok
    assert "portfolio" in result.breaches
