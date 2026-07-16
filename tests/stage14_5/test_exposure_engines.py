"""Factor exposure, tail risk, correlation shock, concentration, regime exposure, crisis alpha."""

from __future__ import annotations

import numpy as np
import pytest

from libs.stage14_5.concentration import ConcentrationEngine
from libs.stage14_5.correlation_shock import CorrelationShockEngine
from libs.stage14_5.crisis_alpha import CrisisAlphaEngine
from libs.stage14_5.errors import Stage14_5Error
from libs.stage14_5.factor_exposure import FactorExposureEngine
from libs.stage14_5.regime_exposure import RegimeExposureEngine
from libs.stage14_5.tail_risk import PortfolioTailRiskEngine


def test_factor_exposure_flags_concentration() -> None:
    eng = FactorExposureEngine(cap=1.0, threshold=70.0)
    ok = eng.evaluate(net_usd=0.2, net_directional=0.1, beta=0.3, volatility_exposure=0.2)
    hot = eng.evaluate(net_usd=0.95, net_directional=0.1, beta=0.2, volatility_exposure=0.1)
    assert ok.acceptable
    assert not hot.acceptable
    assert hot.factor_exposure_score > ok.factor_exposure_score


def test_tail_risk_blends_distribution_and_correlation_collapse() -> None:
    rng = np.random.default_rng(0)
    benign = rng.normal(0.0005, 0.01, size=400)
    result = PortfolioTailRiskEngine().evaluate(benign, correlation_collapse_risk=0.0)
    stressed = PortfolioTailRiskEngine().evaluate(benign, correlation_collapse_risk=0.9)
    assert stressed.tail_risk_score > result.tail_risk_score
    assert 0.0 <= result.tail_risk_score <= 100.0
    assert PortfolioTailRiskEngine().evaluate(np.array([0.01, -0.01])).tail_risk_score == 0.0


def test_correlation_shock_measures_fragility() -> None:
    eng = CorrelationShockEngine(shock=0.8, threshold=30.0)
    diversified = eng.simulate(np.array([[1.0, 0.1], [0.1, 1.0]]))
    already_corr = eng.simulate(np.array([[1.0, 0.9], [0.9, 1.0]]))
    assert diversified.shocked_avg_correlation > diversified.base_avg_correlation
    assert diversified.correlation_fragility_score > already_corr.correlation_fragility_score
    with pytest.raises(Stage14_5Error):
        eng.simulate(np.zeros((2, 3)))


def test_concentration_reports_worst_dimension() -> None:
    eng = ConcentrationEngine(threshold=60.0)
    result = eng.evaluate(
        symbol_weights={"a": 0.5, "b": 0.5},
        alpha_weights={"x": 0.25, "y": 0.25, "z": 0.25, "w": 0.25},
        family_weights={"trend": 0.95, "carry": 0.05},  # highly concentrated
        factor_weights={"f1": 0.5, "f2": 0.5},
        regime_weights={"r1": 0.5, "r2": 0.5},
    )
    assert result.family_concentration == max(
        result.symbol_concentration, result.alpha_concentration, result.family_concentration,
        result.factor_concentration, result.regime_concentration,
    )
    assert not result.acceptable  # family dominance pushes the score up


def test_regime_exposure_flags_uncovered() -> None:
    eng = RegimeExposureEngine(min_exposure=0.05, threshold=50.0)
    balanced = eng.evaluate({"trending": 1, "range": 1, "high_vol": 1, "low_vol": 1, "crisis": 1})
    gappy = eng.evaluate({"trending": 0.9, "range": 0.1})
    assert balanced.balanced
    assert "crisis" in gappy.uncovered_regimes
    assert not gappy.balanced
    assert balanced.regime_balance_score > gappy.regime_balance_score


def test_crisis_alpha_scores_scenario_performance() -> None:
    eng = CrisisAlphaEngine(threshold=55.0, return_scale=0.10)
    strong = eng.evaluate({"market_crash": 0.08, "volatility_spike": 0.06,
                           "liquidity_shock": 0.05, "correlation_breakdown": 0.07})
    weak = eng.evaluate({"market_crash": -0.05, "volatility_spike": -0.03,
                        "liquidity_shock": -0.04, "correlation_breakdown": -0.02})
    assert strong.is_crisis_alpha
    assert not weak.is_crisis_alpha
    assert strong.crisis_alpha_score > weak.crisis_alpha_score
