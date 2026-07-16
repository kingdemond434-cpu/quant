"""Tests for risk parity, HRP, and capital/risk allocation."""

from __future__ import annotations

import numpy as np
import pytest
from tests.portfolio.conftest import constant_correlation, make_alpha

from libs.portfolio.analytics import allocate_capital
from libs.portfolio.covariance import covariance_from_alphas
from libs.portfolio.hrp import hrp_weights
from libs.portfolio.risk_parity import allocate_risk, risk_parity_weights
from libs.risk.risk_budget import risk_contributions


def test_risk_parity_diagonal_is_inverse_vol() -> None:
    cov = np.diag([0.04, 0.01])  # vols 0.2 and 0.1
    w = risk_parity_weights(cov)
    assert w == pytest.approx([1 / 3, 2 / 3], abs=1e-6)
    assert w.sum() == pytest.approx(1.0)


def test_risk_parity_equalizes_risk_contributions() -> None:
    alphas = [
        make_alpha("a", volatility=0.20),
        make_alpha("b", volatility=0.10),
        make_alpha("c", volatility=0.15),
    ]
    cov = covariance_from_alphas(alphas, constant_correlation(3, 0.3))
    w = risk_parity_weights(cov)
    rc = risk_contributions(w, cov)
    assert rc.max() - rc.min() < 1e-6  # equal risk contribution


def test_hrp_weights_sum_to_one_and_inverse_variance() -> None:
    cov = np.diag([0.04, 0.01])  # asset 1 has lower variance
    w = hrp_weights(cov)
    assert w.sum() == pytest.approx(1.0)
    assert (w > 0).all()
    assert w[1] > w[0]  # lower-variance asset gets more weight


def test_hrp_multi_asset() -> None:
    alphas = [make_alpha(f"a{i}", volatility=0.1 + 0.02 * i) for i in range(5)]
    cov = covariance_from_alphas(alphas, constant_correlation(5, 0.2))
    w = hrp_weights(cov)
    assert w.sum() == pytest.approx(1.0)
    assert (w > 0).all()


def test_allocate_risk_returns_normalized_dict() -> None:
    alphas = [make_alpha("a", volatility=0.2), make_alpha("b", volatility=0.1)]
    weights = allocate_risk(alphas)
    assert sum(weights.values()) == pytest.approx(1.0)
    assert set(weights) == {"a", "b"}


def test_allocate_capital() -> None:
    capital = allocate_capital({"a": 0.3, "b": 0.7}, 100_000.0)
    assert capital == {"a": pytest.approx(30_000.0), "b": pytest.approx(70_000.0)}
