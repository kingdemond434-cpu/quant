"""Crowding, capacity, factor exposure, execution, portfolio context, uncertainty, scoring."""

from __future__ import annotations

import numpy as np
from tests.signal_engine.conftest import make_alpha

from libs.signal_engine.capacity import SignalCapacityForecaster
from libs.signal_engine.crowding import SignalCrowdingEngine
from libs.signal_engine.execution import ExecutionFeasibilityEngine
from libs.signal_engine.factor_exposure import FactorExposureEngine
from libs.signal_engine.institutional_score import institutional_signal_score
from libs.signal_engine.portfolio_context import PortfolioContextEngine
from libs.signal_engine.uncertainty import SignalUncertaintyEngine, signal_tail_risk


def test_crowding_threshold() -> None:
    eng = SignalCrowdingEngine(threshold=70.0)
    clean = eng.assess(avg_alpha_correlation=0.0, factor_overlap=0.0, public_crowding=0.0)
    crowded = eng.assess(avg_alpha_correlation=0.95, factor_overlap=0.95, public_crowding=0.95)
    assert clean.acceptable
    assert not crowded.acceptable
    assert 0.0 <= crowded.crowding_score <= 100.0


def test_capacity_forecaster_penalizes_oversize() -> None:
    eng = SignalCapacityForecaster()
    small = eng.forecast(adv_usd=1e9, intended_notional=0.0)
    big = eng.forecast(adv_usd=1e9, intended_notional=5e8)
    assert small.future_capacity_score >= big.future_capacity_score
    assert small.maximum_efficient_capital > 0.0
    assert 0.0 <= big.capacity_confidence <= 1.0


def test_factor_exposure_concentration() -> None:
    eng = FactorExposureEngine(max_concentration=0.40)
    signals = [make_alpha("a"), make_alpha("b"), make_alpha("c")]
    weights = {"a": 1 / 3, "b": 1 / 3, "c": 1 / 3}
    diversified = eng.assess(
        signals, weights,
        # one unknown factor ("weird") is ignored; three known factors spread the risk
        loadings={
            "a": {"momentum": 1.0, "weird": 5.0},
            "b": {"carry": 1.0},
            "c": {"value": 1.0},
        },
    )
    concentrated = eng.assess(
        signals, weights,
        loadings={"a": {"momentum": 1.0}, "b": {"momentum": 1.0}, "c": {"momentum": 1.0}},
    )
    assert diversified.acceptable
    assert "weird" not in diversified.exposures
    assert not concentrated.acceptable
    assert eng.assess(signals, weights).concentration == 0.0  # no loadings


def test_execution_feasibility_threshold() -> None:
    eng = ExecutionFeasibilityEngine(threshold=50.0)
    ok = eng.assess(spread_bps=1.0, expected_slippage_bps=0.5, market_impact_bps=0.0,
                    liquidity_score=1.0)
    bad = eng.assess(spread_bps=30.0, expected_slippage_bps=20.0, market_impact_bps=10.0,
                     liquidity_score=0.3, latency_risk=0.5)
    assert ok.passed and ok.execution_score >= 50.0
    assert not bad.passed
    assert 0.0 <= bad.fill_probability <= 1.0


def test_portfolio_context_rejects_correlated_concentrating() -> None:
    eng = PortfolioContextEngine(max_concentration=0.40)
    good = eng.evaluate(candidate_sharpe=1.8, candidate_sortino=2.0, candidate_calmar=1.0,
                        correlation_to_portfolio=0.0, marginal_diversification=1.0,
                        concentration_after=0.2)
    bad = eng.evaluate(candidate_sharpe=1.8, candidate_sortino=2.0, candidate_calmar=1.0,
                       correlation_to_portfolio=1.0, marginal_diversification=0.0,
                       concentration_after=0.9)
    assert good.accept
    assert good.marginal_sharpe_improvement > 0
    assert not bad.accept  # fully correlated + concentrating


def test_uncertainty_and_tail_risk() -> None:
    eng = SignalUncertaintyEngine()
    confident = eng.estimate(alpha_agreement=1.0, n_alphas=5, sample_size=500,
                             volatility_state=0.1)
    uncertain = eng.estimate(alpha_agreement=0.2, n_alphas=1, sample_size=10,
                             volatility_state=0.9)
    assert uncertain.uncertainty_score > confident.uncertainty_score
    rng = np.random.default_rng(0)
    score = signal_tail_risk(rng.normal(0, 0.01, 500))
    assert 0.0 <= score <= 100.0


def test_institutional_score_rewards_and_penalizes() -> None:
    base = {
        "edge_score": 85.0, "confidence": 0.9, "capacity_score": 100.0,
        "persistence_score": 100.0, "stability_score": 100.0, "decay_weight_multiplier": 1.0,
        "portfolio_contribution": 90.0, "execution_score": 95.0,
    }
    clean = institutional_signal_score(**base, tail_risk_score=0.0, uncertainty_score=0.0)
    risky = institutional_signal_score(**base, tail_risk_score=90.0, uncertainty_score=0.9)
    assert 0.0 <= risky.score < clean.score <= 100.0
