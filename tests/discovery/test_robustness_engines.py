"""Tests for the robustness engines."""

from __future__ import annotations

import numpy as np
from tests.discovery.conftest import make_returns, make_returns_matrix

from libs.discovery.capacity import capacity_estimate
from libs.discovery.correlation_engine import alpha_correlation
from libs.discovery.failure_dependency import failure_dependency
from libs.discovery.family_concentration import family_concentration
from libs.discovery.fragility import alpha_fragility
from libs.discovery.half_life import alpha_half_life
from libs.discovery.monte_carlo_survival import monte_carlo_survival
from libs.discovery.objective import discovery_score, expected_log_growth
from libs.discovery.parameter_stability import parameter_stability
from libs.discovery.portfolio_geometry import portfolio_geometry
from libs.discovery.regime_diversification import regime_diversification
from libs.discovery.research_roi import CategoryStat, rank_categories, research_roi
from libs.discovery.stress_scenario import stress_scenario
from libs.discovery.tail_risk import tail_risk


def test_fragility_robust_vs_fragile() -> None:
    robust = alpha_fragility(
        parameter_stability=0.9, regime_robustness=0.8, cost_sensitivity=0.1,
        slippage_sensitivity=0.1, data_sensitivity=0.1,
    )
    fragile = alpha_fragility(
        parameter_stability=0.1, regime_robustness=0.1, cost_sensitivity=0.9,
        slippage_sensitivity=0.9, data_sensitivity=0.9,
    )
    assert robust.robust and robust.fragility_score < fragile.fragility_score
    assert not fragile.robust


def test_parameter_stability_plateau_vs_spike() -> None:
    plateau = parameter_stability(lambda p: 1.0, {"x": 5}, {"x": [1, 3, 9]})
    assert plateau.robust and plateau.plateau_score == 100.0
    spike = parameter_stability(
        lambda p: 10.0 if p["x"] == 5 else 0.0, {"x": 5}, {"x": [1, 3, 9]}
    )
    assert spike.sharp_peak and not spike.robust


def test_failure_dependency_independent_vs_coupled() -> None:
    independent = failure_dependency(make_returns_matrix(rho=0.0, seed=1))
    base = make_returns(seed=2)
    coupled = failure_dependency(np.column_stack([base, base, base]))
    assert independent.independent
    assert coupled.failure_dependency_score > independent.failure_dependency_score


def test_regime_diversification() -> None:
    even = regime_diversification({"trend": 0.1, "range": 0.1, "high_vol": 0.1, "low_vol": 0.1})
    single = regime_diversification(
        {"trend": 0.4, "range": -0.1, "high_vol": -0.1, "low_vol": -0.1}
    )
    assert even.robust
    assert not single.robust


def test_monte_carlo_survival_calm_series_survives() -> None:
    result = monte_carlo_survival(make_returns(mu=0.0005, sd=0.005, seed=3), n_sims=300)
    assert 0.0 <= result.survival_probability <= 1.0
    assert result.passed


def test_stress_scenario_exposure_matters() -> None:
    returns = make_returns(mu=0.0002, sd=0.004, seed=4)
    assert not stress_scenario(returns, exposure=1.0).passed   # a 50% shock breaches the limit
    assert stress_scenario(returns, exposure=0.0).passed       # no exposure -> resilient


def test_tail_risk_flags_fat_tails() -> None:
    normal = make_returns(sd=0.01, seed=5)
    fat = normal.copy()
    fat[10] = -0.25  # a crash day
    assert tail_risk(fat).tail_risk_score > tail_risk(normal).tail_risk_score


def test_half_life_rising_vs_declining() -> None:
    rising = alpha_half_life(np.linspace(0.5, 1.5, 60))
    declining = alpha_half_life(np.linspace(1.5, 0.1, 60))
    assert not rising.declining
    assert declining.declining


def test_capacity_increases_with_adv() -> None:
    small = capacity_estimate(adv_usd=1e6)
    large = capacity_estimate(adv_usd=1e9)
    assert large.capacity_usd > small.capacity_usd
    assert all(v >= 0 for v in large.slippage_curve.values())


def test_family_concentration() -> None:
    balanced = family_concentration(
        {"trend": 0.25, "momentum": 0.25, "session": 0.25, "carry": 0.25}
    )
    concentrated = family_concentration({"trend": 0.9, "momentum": 0.1})
    assert balanced.balanced
    assert not concentrated.balanced


def test_research_roi_and_ranking() -> None:
    roi = research_roi(
        ideas_generated=100, ideas_tested=50, ideas_validated=5, time_hours=40.0,
        production_contribution=0.3, expected_future_contribution=0.2,
    )
    assert 0.0 <= roi.research_roi_score <= 100.0
    ranked = rank_categories(
        {
            "session": CategoryStat(tested=20, validated=4, contribution=0.5),
            "seasonal": CategoryStat(tested=20, validated=0, contribution=0.0),
        }
    )
    assert ranked[0][0] == "session"


def test_portfolio_geometry_score() -> None:
    returns = make_returns(mu=0.0005, sd=0.008, seed=6)
    result = portfolio_geometry(returns, diversification_ratio=1.5)
    assert 0.0 <= result.portfolio_geometry_score <= 100.0
    assert result.geometric_growth != 0.0


def test_correlation_engine() -> None:
    independent = alpha_correlation(make_returns_matrix(rho=0.0, seed=7), ["a", "b", "c", "d"])
    base = make_returns(seed=8)
    coupled = alpha_correlation(np.column_stack([base, base]), ["a", "b"])
    assert independent.average_correlation < coupled.average_correlation


def test_objective_log_growth_and_score() -> None:
    assert expected_log_growth(make_returns(mu=0.001, sd=0.005, seed=9)) > 0
    low = discovery_score(
        log_growth=0.1, survival_probability=0.99, diversification_contribution=0.5,
        average_correlation=0.1, failure_dependency_score=10, half_life_days=400,
        capacity_usd=1e6, fragility_score=10, tail_risk_score=10, parameter_plateau_score=80,
    )
    high = discovery_score(
        log_growth=0.3, survival_probability=0.99, diversification_contribution=0.5,
        average_correlation=0.1, failure_dependency_score=10, half_life_days=400,
        capacity_usd=1e6, fragility_score=10, tail_risk_score=10, parameter_plateau_score=80,
    )
    assert high > low
