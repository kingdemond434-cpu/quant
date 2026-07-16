"""Tail-risk tests — VaR, CVaR, gap-through-stop, stress (incl. Monte Carlo)."""

from __future__ import annotations

import numpy as np
import pytest

from libs.risk.errors import RiskError
from libs.risk.tail import (
    calculate_cvar,
    calculate_var,
    default_stress_scenarios,
    gap_through_stop_loss,
    stress_test_portfolio,
)


def test_var_positive_for_loss_tail() -> None:
    rng = np.random.default_rng(0)
    returns = rng.normal(0.0, 0.02, size=5000)
    var = calculate_var(returns, alpha=0.05)
    assert var > 0


def test_cvar_at_least_var() -> None:
    rng = np.random.default_rng(1)
    returns = rng.normal(0.0, 0.02, size=5000)
    assert calculate_cvar(returns, alpha=0.05) >= calculate_var(returns, alpha=0.05)


def test_var_methods_and_validation() -> None:
    returns = np.random.default_rng(2).normal(0, 0.02, 2000)
    assert calculate_var(returns, method="gaussian") > 0
    with pytest.raises(RiskError):
        calculate_var(returns, alpha=1.5)
    with pytest.raises(RiskError):
        calculate_var(returns, method="bogus")


def test_gap_through_stop_worse_than_stop() -> None:
    plain_stop_loss = (100.0 - 95.0) * 10  # 50
    gapped = gap_through_stop_loss(
        units=10, entry_price=100.0, stop_price=95.0, gap_fraction=0.02, side="buy"
    )
    assert gapped > plain_stop_loss  # gap-through fills below the stop
    short = gap_through_stop_loss(
        units=10, entry_price=100.0, stop_price=105.0, gap_fraction=0.02, side="sell"
    )
    assert short > 0


def test_managed_portfolio_survives_stress() -> None:
    # Small, factor-diversified book: worst-case loss stays well within equity.
    positions = {"XAUUSD": 5_000.0, "EURUSD": 5_000.0, "US500": 3_000.0}
    result = stress_test_portfolio(positions, equity=100_000.0)
    assert result.survives
    assert result.worst_case_loss < 100_000.0


def test_oversized_concentrated_book_fails_stress() -> None:
    positions = {"BTCUSD": 300_000.0}  # 3x equity in crypto
    result = stress_test_portfolio(positions, equity=100_000.0)
    assert not result.survives


def test_monte_carlo_cvar_dominates_var() -> None:
    for seed in range(25):
        returns = np.random.default_rng(seed).standard_t(df=4, size=2000) * 0.01
        assert calculate_cvar(returns, alpha=0.05) >= calculate_var(returns, alpha=0.05) - 1e-9


def test_default_scenarios_present() -> None:
    names = {s.name for s in default_stress_scenarios()}
    assert {"broad_risk_off", "liquidity_crisis", "vol_spike"} <= names
