"""Kelly sizing and geometric growth / capital-growth simulation."""

from __future__ import annotations

import numpy as np
import pytest

from libs.stage14.errors import Stage14Error
from libs.stage14.growth import CapitalGrowthSimulator, GeometricGrowthEngine
from libs.stage14.kelly import FractionalKellyEngine, KellyEngine


def test_kelly_estimate_full_half_quarter() -> None:
    est = KellyEngine().estimate(win_rate=0.6, payoff_ratio=2.0, confidence=1.0)
    # f* = 0.6 - 0.4/2 = 0.4
    assert est.full == pytest.approx(0.4)
    assert est.half == pytest.approx(0.2)
    assert est.quarter == pytest.approx(0.1)


def test_kelly_confidence_haircut_and_floor() -> None:
    haircut = KellyEngine().estimate(win_rate=0.6, payoff_ratio=2.0, confidence=0.5)
    assert haircut.full == pytest.approx(0.2)
    # negative edge floors at zero (no anti-betting)
    assert KellyEngine().estimate(win_rate=0.3, payoff_ratio=1.0).full == 0.0
    with pytest.raises(Stage14Error):
        KellyEngine().estimate(win_rate=0.5, payoff_ratio=0.0)


def test_fractional_kelly_third_base_half_max_when_qualified() -> None:
    eng = FractionalKellyEngine()
    base = eng.fraction_of_kelly(volatility_state=0.0, regime_uncertainty=0.0)
    assert base == pytest.approx(1 / 3)  # third-Kelly base/standard under good conditions
    qualified = eng.fraction_of_kelly(
        volatility_state=0.0, regime_uncertainty=0.0, roi_qualified=True
    )
    assert qualified == pytest.approx(0.5)  # half-Kelly only when ROI qualifies
    stressed = eng.fraction_of_kelly(
        volatility_state=0.9, regime_uncertainty=0.9, fragility=0.8, roi_qualified=True
    )
    assert stressed < qualified         # health still scales it down
    assert qualified <= 0.5             # half-Kelly maximum, ever
    # sizing applies the fraction to the full estimate
    assert eng.size(0.4, volatility_state=0.0, regime_uncertainty=0.0) == pytest.approx(0.4 / 3)
    assert eng.size(
        0.4, volatility_state=0.0, regime_uncertainty=0.0, roi_qualified=True
    ) == pytest.approx(0.2)


def test_fractional_kelly_validates_config() -> None:
    with pytest.raises(Stage14Error):
        FractionalKellyEngine(base_fraction=0.6, max_fraction=0.5)


def test_geometric_growth_scores_positive_drift() -> None:
    rng = np.random.default_rng(0)
    returns = 0.005 + rng.normal(0.0, 0.005, size=500)
    result = GeometricGrowthEngine().evaluate(returns)
    assert result.expected_cagr > 0
    assert result.expected_terminal_wealth > 1.0
    assert 0.0 <= result.geometric_growth_score <= 100.0
    assert 0.0 <= result.growth_efficiency <= 1.0


def test_geometric_growth_empty_is_safe() -> None:
    result = GeometricGrowthEngine().evaluate(np.array([]))
    assert result.geometric_growth_score == 0.0


def test_capital_growth_simulator_short_series_is_safe() -> None:
    sim = CapitalGrowthSimulator(n_sims=50).simulate(np.array([0.01]))
    assert sim.probability_of_ruin == 1.0
    assert sim.survival_probability == 0.0


def test_capital_growth_simulator() -> None:
    rng = np.random.default_rng(1)
    returns = 0.004 + rng.normal(0.0, 0.01, size=400)
    sim = CapitalGrowthSimulator(n_sims=500).simulate(returns)
    assert sim.cagr_p5 <= sim.cagr_median <= sim.cagr_p95
    assert 0.0 <= sim.survival_probability <= 1.0
    assert 0.0 <= sim.probability_of_ruin <= 1.0
    assert sim.terminal_wealth_median > 0
