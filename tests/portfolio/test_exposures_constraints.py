"""Tests for exposures, risk contributions, and constraint enforcement."""

from __future__ import annotations

import numpy as np
import pytest
from tests.portfolio.conftest import make_alpha

from libs.portfolio.constraints import apply_constraints
from libs.portfolio.covariance import covariance_from_alphas
from libs.portfolio.exposures import (
    calculate_factor_exposures,
    calculate_risk_contributions,
    calculate_strategy_exposures,
)
from libs.portfolio.models import PortfolioConstraints, StrategyType
from libs.risk.instruments import Factor


def _alphas() -> list:
    return [
        make_alpha("gold", factor=Factor.PRECIOUS_METALS, strategy_type=StrategyType.TREND),
        make_alpha("silver", factor=Factor.PRECIOUS_METALS, strategy_type=StrategyType.TREND),
        make_alpha("eur", factor=Factor.FX, strategy_type=StrategyType.MEAN_REVERSION),
    ]


def test_factor_and_strategy_exposures() -> None:
    weights = {"gold": 0.4, "silver": 0.2, "eur": 0.4}
    factors = calculate_factor_exposures(weights, _alphas())
    strategies = calculate_strategy_exposures(weights, _alphas())
    assert factors["precious_metals"] == pytest.approx(0.6)
    assert factors["fx"] == pytest.approx(0.4)
    assert strategies["trend"] == pytest.approx(0.6)


def test_risk_contributions_sum_to_one() -> None:
    alphas = _alphas()
    cov = covariance_from_alphas(alphas)
    order = [a.alpha_id for a in alphas]
    rc = calculate_risk_contributions({"gold": 0.4, "silver": 0.2, "eur": 0.4}, cov, order)
    assert sum(rc.values()) == pytest.approx(1.0)


def test_per_weight_cap_water_fills() -> None:
    weights = {"gold": 0.5, "silver": 0.3, "eur": 0.2}
    constraints = PortfolioConstraints(
        max_weight=0.4, max_factor_weight=1.0, max_strategy_weight=1.0, max_asset_class_weight=1.0
    )
    out, binding = apply_constraints(weights, _alphas(), constraints)
    assert max(out.values()) <= 0.4 + 1e-9
    assert sum(out.values()) == pytest.approx(1.0)  # water-fill preserves the total
    assert "max_weight" in binding


def test_factor_cap_scales_group_down() -> None:
    weights = {"gold": 0.4, "silver": 0.3, "eur": 0.3}
    out, binding = apply_constraints(
        weights, _alphas(), PortfolioConstraints(max_weight=1.0, max_factor_weight=0.40)
    )
    pm = out["gold"] + out["silver"]
    assert pm <= 0.40 + 1e-9
    assert any(b.startswith("factor:") for b in binding)


def test_long_only_clips_negatives() -> None:
    out, binding = apply_constraints(
        {"gold": -0.2, "silver": 0.7, "eur": 0.5}, _alphas(), PortfolioConstraints()
    )
    assert all(w >= 0.0 for w in out.values())  # no shorts under long-only
    assert any(b.startswith("long_only:") for b in binding)


def test_constraints_monte_carlo_respect_caps() -> None:
    alphas = _alphas()
    constraints = PortfolioConstraints(max_weight=0.5, max_factor_weight=0.6)
    rng = np.random.default_rng(0)
    for _ in range(100):
        raw = rng.random(3)
        weights = dict(zip([a.alpha_id for a in alphas], (raw / raw.sum()).tolist(), strict=True))
        out, _ = apply_constraints(weights, alphas, constraints)
        assert max(out.values()) <= constraints.max_weight + 1e-6
        pm = out["gold"] + out["silver"]
        assert pm <= constraints.max_factor_weight + 1e-6
