"""Tests for the robustness engines."""

from __future__ import annotations

from pathlib import Path

from tests.discovery.conftest import make_returns

from libs.discovery.capacity import capacity_estimate
from libs.discovery.monte_carlo_survival import monte_carlo_survival
from libs.discovery.objective import discovery_score, expected_log_growth
from libs.discovery.regime_diversification import regime_diversification
from libs.discovery.research_roi import CategoryStat, rank_categories, research_roi
from libs.discovery.stress_scenario import stress_scenario
from libs.discovery.tail_risk import tail_risk


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


def test_capacity_increases_with_adv() -> None:
    small = capacity_estimate(adv_usd=1e6)
    large = capacity_estimate(adv_usd=1e9)
    assert large.capacity_usd > small.capacity_usd
    assert all(v >= 0 for v in large.slippage_curve.values())


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


def test_composite_on_neutral_defaults_is_log_growth_rescaled() -> None:
    """R0261. Nine of ten inputs held constant leaves `growth` as the only free term, so the
    'composite discovery rank' is EXACTLY log_growth times a constant -- it carries no ordering
    information the plain log_growth ranking does not already have. Measured on the committed
    artifact: 0.1253 -> 0.00696 and 0.4068 -> 0.02258, the same K to four figures."""
    const = {
        "survival_probability": 0.95, "diversification_contribution": 0.0,
        "average_correlation": 0.0, "failure_dependency_score": 50.0, "half_life_days": 90.0,
        "capacity_usd": 250_000.0, "fragility_score": 50.0, "tail_risk_score": 50.0,
        "parameter_plateau_score": 50.0,
    }
    ks = [discovery_score(log_growth=g, **const) / g for g in (0.1253, 0.4068, 1.7)]
    assert max(ks) - min(ks) < 1e-12                  # one constant, not a composite


def test_geometric_review_publishes_the_composite_as_UNMEASURED() -> None:
    """A score built from nine literals must not be published as a bare float: read that way it
    claims the diversification / correlation / failure-dependency / plateau content its name
    implies and does not contain (L1.55 -- a defaulted input rendered as a measurement)."""
    src = Path("scripts/run_geometric_review.py").read_text("utf-8")
    assert '"measured": False' in src
    assert '"inputs_defaulted"' in src and '"inputs_measured"' in src
    # the three that have NO producer anywhere in the repo must be named as defaulted
    for missing in ("failure_dependency_score", "parameter_plateau_score",
                    "diversification_contribution"):
        assert missing in src
