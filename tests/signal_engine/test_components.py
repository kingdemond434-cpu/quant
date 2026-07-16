"""Weighting, aggregation, regime routing, edge, expected value, meta model, confidence."""

from __future__ import annotations

from tests.signal_engine.conftest import make_alpha, make_state

from libs.signal_engine.aggregation import SignalAggregator
from libs.signal_engine.alpha_weighting import AlphaWeighting, DynamicWeighting
from libs.signal_engine.confidence_engine import ConfidenceEngine
from libs.signal_engine.edge_estimator import EdgeEstimator
from libs.signal_engine.expected_value import ExpectedValueEngine
from libs.signal_engine.meta_model import MetaModel
from libs.signal_engine.models import Direction, Regime
from libs.signal_engine.regime import (
    RegimeRouter,
    RegimeTransitionRouter,
    transition_confidence,
)


def test_dynamic_weighting_normalizes_and_favours_quality() -> None:
    state = make_state()
    strong = make_alpha("strong", health_score=95.0)
    weak = make_alpha("weak", health_score=40.0, decay_multiplier=0.5)
    weights = DynamicWeighting().weights([strong, weak], state)
    assert abs(sum(weights.values()) - 1.0) < 1e-9
    assert weights["strong"] > weights["weak"]


def test_alpha_weight_zero_when_regime_mismatch() -> None:
    state = make_state(regime=Regime.CRISIS, predicted_regime=Regime.CRISIS)
    # affinity only for TREND -> zero affinity for CRISIS -> zero weight
    alpha = make_alpha("trend_only", regime_affinity={Regime.TREND.value: 1.0})
    assert AlphaWeighting().weight(alpha, state) == 0.0


def test_aggregator_net_direction_and_agreement() -> None:
    state = make_state()
    buy = make_alpha("b", direction=Direction.BUY)
    sell = make_alpha("s", direction=Direction.SELL, strength=0.3)
    weights = DynamicWeighting().weights([buy, sell], state)
    agg = SignalAggregator().aggregate([buy, sell], weights)
    assert agg.direction is Direction.BUY
    assert 0.0 < agg.alpha_agreement <= 1.0
    assert agg.breakdown["b"] > 0 and agg.breakdown["s"] < 0


def test_aggregator_flat_on_cancellation() -> None:
    state = make_state()
    buy = make_alpha("b", direction=Direction.BUY, strength=0.8, health_score=90.0)
    sell = make_alpha("s", direction=Direction.SELL, strength=0.8, health_score=90.0)
    weights = DynamicWeighting().weights([buy, sell], state)
    agg = SignalAggregator().aggregate([buy, sell], weights)
    assert agg.direction is Direction.FLAT


def test_regime_routers_and_transition_confidence() -> None:
    alpha = make_alpha(regime_affinity={Regime.TREND.value: 1.0, Regime.CRISIS.value: 0.0})
    state = make_state(regime=Regime.TREND, predicted_regime=Regime.CRISIS,
                       transition_probability=1.0)
    assert RegimeRouter().route(alpha, state) == 1.0
    # fully-confident transition toward CRISIS (affinity 0) pulls the route down
    assert RegimeTransitionRouter().route(alpha, state) < 1.0
    assert transition_confidence(make_state(transition_probability=0.5)) == 0.0
    assert transition_confidence(make_state(transition_probability=1.0)) == 1.0


def test_edge_estimator_ranges_and_friction() -> None:
    est = EdgeEstimator()
    signals = [make_alpha("a"), make_alpha("b")]
    weights = DynamicWeighting().weights(signals, make_state())
    clean = est.estimate(signals, weights, make_state())
    noisy = est.estimate(
        signals, weights, make_state(spread_bps=18.0, volatility_state=0.9, liquidity_score=0.4)
    )
    assert 0.0 <= clean.edge_score <= 100.0
    assert clean.edge_score > noisy.edge_score  # frictions erode edge
    assert clean.expected_pf > 1.0


def test_expected_value_positive_and_cost_adjusted() -> None:
    eng = ExpectedValueEngine()
    signals = [make_alpha("a")]
    weights = {"a": 1.0}
    cheap = eng.estimate(signals, weights, spread_bps=1.0)
    expensive = eng.estimate(signals, weights, spread_bps=1.0, market_impact_bps=200.0)
    assert cheap.positive
    assert cheap.expected_value > expensive.expected_value
    assert not expensive.positive  # heavy impact destroys the edge


def test_meta_model_monotonic() -> None:
    m = MetaModel()
    low = m.predict_proba(edge=0.1, agreement=0.1, persistence=0.1, stability=0.1)
    high = m.predict_proba(edge=0.95, agreement=0.95, persistence=0.95, stability=0.95)
    assert 0.0 < low < high < 1.0


def test_confidence_punishes_weakest_link() -> None:
    eng = ConfidenceEngine()
    kwargs = {
        "edge_score": 85.0, "alpha_agreement": 1.0, "regime_confidence": 1.0,
        "future_regime_confidence": 1.0, "cross_asset_confirmation": 1.0,
        "microstructure_confirmation": 1.0, "capacity_confidence": 1.0,
        "portfolio_contribution": 0.9, "persistence": 1.0, "stability": 1.0,
    }
    strong = eng.estimate(**kwargs)
    weak_link = eng.estimate(**{**kwargs, "cross_asset_confirmation": 0.0})
    assert strong.confidence > weak_link.confidence
    assert 0.0 <= weak_link.confidence <= 1.0


def test_zero_weight_branches() -> None:
    state = make_state()
    # all-zero conviction -> all weights zero (DynamicWeighting fallback)
    flat = [make_alpha("a", strength=0.0), make_alpha("b", strength=0.0)]
    weights = DynamicWeighting().weights(flat, state)
    assert all(w == 0.0 for w in weights.values())

    # empty weights drive the weighted helpers to their zero branch
    edge = EdgeEstimator().estimate([make_alpha("a", profit_factor=None)], {}, state)
    assert edge.expected_return == 0.0
    assert edge.expected_pf == 1.0  # PF proxy when no stated PF
    ev = ExpectedValueEngine().estimate([make_alpha("a")], {})
    assert ev.expected_value == 0.0
