"""Quality, filters, persistence, stability, and signal decay."""

from __future__ import annotations

from tests.signal_engine.conftest import make_alpha, make_state

from libs.self_improvement.models import DecayLevel
from libs.signal_engine.decay import SignalDecayEngine
from libs.signal_engine.persistence import SignalPersistenceEngine, SignalStabilityEngine
from libs.signal_engine.quality import SignalFilters, SignalQuality


def test_quality_high_for_strong_inputs() -> None:
    q = SignalQuality().score(
        edge_score=85.0, confidence=0.92, persistence_score=100.0,
        stability_score=100.0, alpha_agreement=1.0, decay_weight_multiplier=1.0,
    )
    assert q.quality_score > 80.0
    assert q.passed


def test_quality_scaled_down_by_decay() -> None:
    base = {
        "edge_score": 85.0, "confidence": 0.92, "persistence_score": 100.0,
        "stability_score": 100.0, "alpha_agreement": 1.0,
    }
    healthy = SignalQuality().score(**base, decay_weight_multiplier=1.0)
    decayed = SignalQuality().score(**base, decay_weight_multiplier=0.5)
    assert decayed.quality_score < healthy.quality_score


def test_filters_reject_ungoverned_and_wide_spread() -> None:
    f = SignalFilters()
    assert not f.pre_filter([], make_state()).ok
    ungoverned = [make_alpha(governance_passed=False)]
    assert not f.pre_filter(ungoverned, make_state()).ok
    wide = f.pre_filter([make_alpha()], make_state(spread_bps=999.0))
    assert not wide.ok
    no_liq = f.pre_filter([make_alpha()], make_state(liquidity_score=0.0))
    assert not no_liq.ok
    assert no_liq.reason == "no liquidity"
    assert f.pre_filter([make_alpha()], make_state()).ok


def test_persistence_rewards_durability() -> None:
    eng = SignalPersistenceEngine()
    durable = eng.assess(signal_age=60, survival=1.0, flip_frequency=0.0,
                         noise_level=0.0, regime_consistency=1.0)
    fragile = eng.assess(signal_age=5, survival=0.3, flip_frequency=0.8,
                         noise_level=0.7, regime_consistency=0.2)
    assert durable.persistence_score > fragile.persistence_score
    assert 0.0 <= fragile.persistence_score <= 100.0


def test_stability_threshold() -> None:
    eng = SignalStabilityEngine(threshold=60.0)
    steady = eng.assess(oscillation=0.0, direction_change_rate=0.0, prediction_stability=1.0,
                        alpha_stability=1.0, regime_stability=1.0)
    jittery = eng.assess(oscillation=0.9, direction_change_rate=0.9, prediction_stability=0.1,
                         alpha_stability=0.1, regime_stability=0.1)
    assert steady.passed
    assert not jittery.passed


def test_signal_decay_levels_and_actions() -> None:
    eng = SignalDecayEngine()
    healthy = eng.assess(profit_factor=1.8, sharpe=1.8)
    dead = eng.assess(profit_factor=0.7, sharpe=0.1)
    assert healthy.decay_level is DecayLevel.HEALTHY
    assert healthy.weight_multiplier == 1.0
    assert dead.decay_level is DecayLevel.DEAD
    assert dead.weight_multiplier == 0.0
    assert dead.confidence_multiplier == 0.0
    assert dead.recommended_action == "retire_signal"
