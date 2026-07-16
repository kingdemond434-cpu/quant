"""Portfolio analytics and capacity governor enforcement."""

from __future__ import annotations

import numpy as np
import pytest

from libs.stage14.analytics import (
    CapitalEfficiencyEngine,
    MarginalContributionEngine,
    PortfolioConvexityEngine,
    PortfolioCorrelationEngine,
    PortfolioResilienceEngine,
    PortfolioStressEngine,
    PortfolioSurvivalEngine,
)
from libs.stage14.capacity import PortfolioCapacityEngine, PortfolioCapacityGovernor
from libs.stage14.models import PortfolioCapacityResult


def test_correlation_engine_flags_concentration() -> None:
    eng = PortfolioCorrelationEngine()
    low = eng.evaluate(np.array([[1.0, 0.1], [0.1, 1.0]]))
    high = eng.evaluate(np.array([[1.0, 0.9], [0.9, 1.0]]))
    assert low.acceptable
    assert not high.acceptable
    assert high.max_pairwise == 0.9


def test_correlation_engine_edge_cases() -> None:
    eng = PortfolioCorrelationEngine()
    single = eng.evaluate(np.array([[1.0]]))  # n < 2
    assert single.acceptable
    assert single.avg_pairwise == 0.0
    with pytest.raises(ValueError, match="square"):
        eng.evaluate(np.zeros((2, 3)))


def test_convexity_short_series_is_neutral() -> None:
    result = PortfolioConvexityEngine().evaluate(np.array([0.01, -0.01]))
    assert result.convexity_score == 50.0


def test_survival_engine_scores() -> None:
    rng = np.random.default_rng(0)
    returns = 0.003 + rng.normal(0.0, 0.008, size=400)
    result = PortfolioSurvivalEngine().evaluate(returns)
    assert 0.0 <= result.survival_probability <= 1.0
    assert result.survival_score == 100.0 * result.survival_probability
    assert 0.0 <= result.stress_survival <= 1.0


def test_stress_and_resilience_and_convexity() -> None:
    rng = np.random.default_rng(1)
    returns = rng.normal(0.0005, 0.01, size=300)
    stress = PortfolioStressEngine().evaluate(returns)
    assert 0.0 <= stress.stress_score <= 100.0
    assert stress.by_scenario

    resilience = PortfolioResilienceEngine().evaluate(
        regime_resilience=0.8, factor_resilience=0.7, capacity_resilience=0.9,
        execution_resilience=0.85,
    )
    assert 0.0 <= resilience.resilience_score <= 100.0

    convexity = PortfolioConvexityEngine().evaluate(returns)
    assert 0.0 <= convexity.convexity_score <= 100.0


def test_marginal_contribution_and_efficiency() -> None:
    mc = MarginalContributionEngine().contributions(
        weights={"a": 0.6, "b": 0.4}, metric={"a": 0.1, "b": -0.05}
    )
    assert mc.by_signal["a"] == pytest.approx(0.06)
    assert mc.by_signal["b"] == pytest.approx(-0.02)
    assert mc.total == pytest.approx(mc.by_signal["a"] + mc.by_signal["b"])

    eff = CapitalEfficiencyEngine().evaluate(
        expected_return=0.2, volatility=0.1, capacity_utilization=0.5
    )
    assert eff.return_per_risk == 2.0
    assert 0.0 <= eff.capital_efficiency_score <= 100.0


def test_capacity_governor_enforces() -> None:
    gov = PortfolioCapacityGovernor(scale_threshold=0.8, slippage_threshold=0.002)
    # impact cost exceeds edge -> zero
    zero = gov.govern(
        PortfolioCapacityResult(capacity_utilization=0.5, capacity_score=50.0,
                                forecast_slippage=0.0, impact_cost=0.05),
        edge=0.01,
    )
    assert zero.action == "zero"
    # forecast slippage too high -> block
    block = gov.govern(
        PortfolioCapacityResult(capacity_utilization=0.5, capacity_score=50.0,
                                forecast_slippage=0.01, impact_cost=0.0),
        edge=0.05,
    )
    assert block.action == "block"
    # high utilization -> scale down
    scale = gov.govern(
        PortfolioCapacityResult(capacity_utilization=0.9, capacity_score=10.0,
                                forecast_slippage=0.0, impact_cost=0.0),
        edge=0.05,
    )
    assert scale.action == "scale"
    assert scale.scale_factor < 1.0
    # all clear -> ok
    ok = gov.govern(
        PortfolioCapacityResult(capacity_utilization=0.5, capacity_score=50.0,
                                forecast_slippage=0.0, impact_cost=0.0),
        edge=0.05,
    )
    assert ok.action == "ok"


def test_capacity_engine_utilization() -> None:
    result = PortfolioCapacityEngine().evaluate(
        deployed_capital=800_000.0, max_efficient_capital=1_000_000.0,
        forecast_slippage=0.001, impact_cost=0.0,
    )
    assert result.capacity_utilization == pytest.approx(0.8)
    assert result.capacity_score == pytest.approx(20.0)
