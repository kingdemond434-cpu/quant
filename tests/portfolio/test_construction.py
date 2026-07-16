"""Tests for sleeve-allocation primitives (portfolio construction)."""

from __future__ import annotations

import numpy as np

from libs.portfolio.construction import (
    blend,
    concentration_cap,
    marginal_sharpe,
    max_sharpe_weights,
    portfolio_sharpe,
    turnover,
)


def test_portfolio_sharpe_quadrature_for_uncorrelated() -> None:
    # two uncorrelated equal-Sharpe sleeves, equal weight -> S_p = wᵀμ/sqrt(wᵀCw)
    w = np.array([0.5, 0.5])
    mu = np.array([1.0, 1.0])
    corr = np.eye(2)
    # (0.5+0.5) / sqrt(0.25+0.25) = 1/0.7071 ≈ 1.414
    assert abs(portfolio_sharpe(w, mu, corr) - np.sqrt(2)) < 1e-9


def test_max_sharpe_tilts_to_higher_sharpe() -> None:
    w = max_sharpe_weights(np.array([2.0, 1.0]), np.eye(2))
    assert w[0] > w[1]                     # more capital to the stronger sleeve
    assert abs(w.sum() - 1.0) < 1e-9
    assert (w >= 0).all()                  # long-only


def test_max_sharpe_handles_singular_correlation() -> None:
    corr = np.ones((3, 3))                 # perfectly collinear -> singular without ridge
    w = max_sharpe_weights(np.array([1.0, 1.0, 1.0]), corr)
    assert abs(w.sum() - 1.0) < 1e-9
    assert np.isfinite(w).all()


def test_concentration_cap_enforced_and_normalised() -> None:
    w = concentration_cap(np.array([0.7, 0.2, 0.1]), cap=0.35)
    assert w.max() <= 0.35 + 1e-9
    assert abs(w.sum() - 1.0) < 1e-9


def test_concentration_cap_noop_when_within_limit() -> None:
    w0 = np.array([0.34, 0.33, 0.33])
    assert np.allclose(concentration_cap(w0, cap=0.35), w0)


def test_marginal_sharpe_positive_for_diversifier() -> None:
    mu = np.array([1.0, 1.0])
    corr = np.array([[1.0, -0.5], [-0.5, 1.0]])   # negatively correlated -> both add value
    mc = marginal_sharpe(np.array([0.5, 0.5]), mu, corr)
    assert (mc > 0).all()


def test_blend_and_turnover() -> None:
    b = blend(np.array([1.0, 0.0]), np.array([0.0, 1.0]), 0.5)
    assert np.allclose(b, [0.5, 0.5])
    assert abs(turnover({"a": 0.5, "b": 0.5}, {"a": 0.7, "b": 0.3}) - 0.2) < 1e-9
