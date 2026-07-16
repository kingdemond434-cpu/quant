"""Volatility targeting, risk budgeting, and factor-cap tests."""

from __future__ import annotations

import numpy as np
import pytest

from libs.risk.config import VolConfig
from libs.risk.errors import RiskError
from libs.risk.factor_caps import check_factor_exposure
from libs.risk.instruments import Factor
from libs.risk.risk_budget import allocate_risk_budget, enforce_risk_budget, risk_contributions
from libs.risk.vol_target import (
    adjust_for_volatility,
    ewma_volatility,
    realized_volatility,
    regime_adjusted_volatility,
    vol_target,
)


def test_realized_and_ewma_vol() -> None:
    returns = np.random.default_rng(0).normal(0, 0.02, 500)
    assert realized_volatility(returns) > 0
    assert ewma_volatility(returns) > 0


def test_vol_target_reduces_in_high_vol_increases_in_calm() -> None:
    high = vol_target(0.40, target_vol=0.10)  # forecast 4x target
    calm = vol_target(0.05, target_vol=0.10)  # forecast half target
    assert high < 1.0
    assert calm > 1.0


def test_vol_target_clamped() -> None:
    assert vol_target(1e-9, target_vol=0.10, k_max=3.0) == 3.0
    assert vol_target(100.0, target_vol=0.10, k_min=0.2) == 0.2


def test_adjust_for_volatility() -> None:
    cfg = VolConfig(target=0.10, k_min=0.2, k_max=3.0)
    assert adjust_for_volatility(1000.0, 0.20, config=cfg) == pytest.approx(500.0)


def test_regime_adjusted_volatility() -> None:
    assert regime_adjusted_volatility(0.10, regime_multiplier=2.5) == pytest.approx(0.25)
    with pytest.raises(RiskError):
        regime_adjusted_volatility(0.1, regime_multiplier=-1.0)


def test_risk_contributions_sum_to_portfolio_vol() -> None:
    cov = np.array([[0.04, 0.01], [0.01, 0.09]])
    weights = np.array([0.5, 0.5])
    rc = risk_contributions(weights, cov)
    port_vol = np.sqrt(weights @ cov @ weights)
    assert rc.sum() == pytest.approx(port_vol)


def test_allocate_and_enforce_budget() -> None:
    alloc = allocate_risk_budget({"a": 1.0, "b": 3.0}, total_risk=1000.0)
    assert alloc["a"] == pytest.approx(250.0)
    assert alloc["b"] == pytest.approx(750.0)
    enforced = enforce_risk_budget({"a": 300.0, "b": 750.0}, {"a": 250.0, "b": 800.0})
    assert enforced.enforced["a"] == 250.0  # clamped
    assert "a" in enforced.breached
    assert enforced.scaled


def test_factor_caps_aggregate_correlated_symbols() -> None:
    # gold + silver are one precious-metals bet
    exposures = {"XAUUSD": 30_000.0, "XAGUSD": 20_000.0}
    result = check_factor_exposure(
        exposures, equity=100_000.0, factor_caps={Factor.PRECIOUS_METALS: 0.40}
    )
    assert not result.ok  # 50% > 40% cap
    assert result.breaches[0].factor is Factor.PRECIOUS_METALS


def test_factor_caps_within_limit() -> None:
    exposures = {"XAUUSD": 10_000.0, "EURUSD": 10_000.0}
    result = check_factor_exposure(
        exposures, equity=100_000.0,
        factor_caps={Factor.PRECIOUS_METALS: 0.40, Factor.FX: 0.40},
    )
    assert result.ok
