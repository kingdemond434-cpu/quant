"""Tests for diversification, correlation controls, optimization, and rebalancing."""

from __future__ import annotations

import numpy as np
import pytest
from tests.portfolio.conftest import constant_correlation, make_alpha

from libs.portfolio.covariance import covariance_from_alphas
from libs.portfolio.diversification import (
    apply_correlation_controls,
    concentration,
    diversification_ratio,
    effective_bets,
)
from libs.portfolio.errors import PortfolioError
from libs.portfolio.optimize import optimize_portfolio
from libs.portfolio.rebalance import rebalance


def test_diversification_ratio_and_effective_bets() -> None:
    cov_independent = np.eye(3) * 0.04
    w = np.array([1 / 3, 1 / 3, 1 / 3])
    assert diversification_ratio(w, cov_independent) > 1.0
    assert effective_bets(w) == pytest.approx(3.0)
    assert concentration(np.array([1.0, 0.0, 0.0])) == pytest.approx(1.0)


def test_perfectly_correlated_has_no_diversification() -> None:
    cov = covariance_from_alphas(
        [make_alpha("a"), make_alpha("b")], constant_correlation(2, 0.999)
    )
    dr = diversification_ratio(np.array([0.5, 0.5]), cov)
    assert dr == pytest.approx(1.0, abs=0.01)


def test_correlation_controls_cap_cluster() -> None:
    alphas = [make_alpha("a"), make_alpha("b"), make_alpha("c")]
    corr = np.array([[1.0, 0.95, 0.0], [0.95, 1.0, 0.0], [0.0, 0.0, 1.0]])
    cov = covariance_from_alphas(alphas, corr)
    weights = {"a": 0.45, "b": 0.45, "c": 0.10}
    out, binding = apply_correlation_controls(
        weights, cov, ["a", "b", "c"], cluster_threshold=0.8, max_cluster_weight=0.6
    )
    assert out["a"] + out["b"] <= 0.6 + 1e-9
    assert binding


def test_optimize_tilts_to_quality_but_stays_diversified() -> None:
    alphas = [
        make_alpha("strong", expected_sharpe=2.0),
        make_alpha("weak", expected_sharpe=0.5),
    ]
    weights = optimize_portfolio(alphas, shrink=0.5)
    assert weights["strong"] > weights["weak"]
    assert weights["weak"] > 0.1  # still diversified, not winner-take-all
    assert sum(weights.values()) == pytest.approx(1.0)


def test_optimize_prefers_uncorrelated() -> None:
    alphas = [make_alpha("a"), make_alpha("b"), make_alpha("c")]  # equal quality
    corr = np.array([[1.0, 0.9, 0.0], [0.9, 1.0, 0.0], [0.0, 0.0, 1.0]])
    weights = optimize_portfolio(alphas, correlation=corr)
    assert weights["c"] > weights["a"]  # the uncorrelated alpha is preferred
    assert weights["c"] > weights["b"]


def test_optimize_with_decayed_alpha_reduced() -> None:
    alphas = [
        make_alpha("healthy", expected_sharpe=1.5, decay_score=0.0),
        make_alpha("decayed", expected_sharpe=1.5, decay_score=0.9),
    ]
    weights = optimize_portfolio(alphas)
    assert weights["healthy"] > weights["decayed"]


def test_rebalance_threshold() -> None:
    current = {"a": 0.50, "b": 0.50}
    no_drift = rebalance(current, {"a": 0.52, "b": 0.48}, method="threshold", threshold=0.05)
    assert not no_drift.rebalanced
    drift = rebalance(current, {"a": 0.70, "b": 0.30}, method="threshold", threshold=0.05)
    assert drift.rebalanced
    assert drift.turnover == pytest.approx(0.20)


def test_rebalance_time_always() -> None:
    result = rebalance({"a": 0.5}, {"a": 0.5}, method="time")
    assert result.rebalanced


def test_rebalance_risk_requires_cov() -> None:
    with pytest.raises(PortfolioError):
        rebalance({"a": 0.5, "b": 0.5}, {"a": 0.6, "b": 0.4}, method="risk")


def test_rebalance_invalid_method() -> None:
    with pytest.raises(PortfolioError):
        rebalance({"a": 1.0}, {"a": 1.0}, method="bogus")
