"""Health scoring and decay classification."""

from __future__ import annotations

import pytest
from tests.self_improvement.conftest import make_live, make_live_poor, register

from libs.alpha.manager import AlphaLifecycleManager
from libs.self_improvement.decay_engine import AlphaDecayEngine, classify_decay
from libs.self_improvement.health_monitor import AlphaHealthMonitor
from libs.self_improvement.models import DecayLevel, HealthLevel


@pytest.mark.parametrize(
    ("score", "level"),
    [
        (95.0, HealthLevel.ELITE),
        (90.0, HealthLevel.ELITE),
        (89.9, HealthLevel.STRONG),
        (80.0, HealthLevel.STRONG),
        (70.0, HealthLevel.STABLE),
        (60.0, HealthLevel.WEAK),
        (59.9, HealthLevel.CRITICAL),
        (0.0, HealthLevel.CRITICAL),
    ],
)
def test_health_level_classify(score: float, level: HealthLevel) -> None:
    assert HealthLevel.classify(score) is level


def test_health_monitor_scores_and_orders(manager: AlphaLifecycleManager) -> None:
    card = register(manager)
    monitor = AlphaHealthMonitor()
    good = monitor.assess(card, make_live())
    poor = monitor.assess(card, make_live_poor())
    assert 0.0 <= poor.health_score <= 100.0
    assert 0.0 <= good.health_score <= 100.0
    assert good.health_score > poor.health_score
    assert good.level is HealthLevel.classify(good.health_score)
    assert good.alpha_id == card.id
    assert good.components  # component breakdown is reported


@pytest.mark.parametrize(
    ("pf", "sharpe", "level"),
    [
        (1.7, 1.6, DecayLevel.HEALTHY),
        (1.7, 1.0, DecayLevel.WATCH),   # high PF but Sharpe not confirming -> watch
        (1.3, 1.0, DecayLevel.WATCH),
        (1.1, 1.0, DecayLevel.WEAK),
        (0.9, 0.5, DecayLevel.DECAYING),
        (0.7, 0.1, DecayLevel.DEAD),
    ],
)
def test_classify_decay_thresholds(pf: float, sharpe: float, level: DecayLevel) -> None:
    assert classify_decay(profit_factor=pf, sharpe=sharpe) is level


@pytest.mark.parametrize(
    ("sharpe", "level"),
    [(2.0, DecayLevel.HEALTHY), (1.0, DecayLevel.WEAK), (-1.0, DecayLevel.DEAD)],
)
def test_classify_decay_sharpe_proxy(sharpe: float, level: DecayLevel) -> None:
    # When profit factor is unavailable, Sharpe acts as the proxy.
    assert classify_decay(profit_factor=None, sharpe=sharpe) is level


def test_decay_engine_dead_recommends_retire(manager: AlphaLifecycleManager) -> None:
    card = register(manager)
    engine = AlphaDecayEngine()
    assessment = engine.assess(card, make_live_poor())
    assert assessment.decay_level is DecayLevel.DEAD
    assert assessment.weight_multiplier == 0.0
    assert assessment.allow_increase is False
    assert assessment.recommended_action == "retire"
    assert 0.0 <= assessment.decay_score <= 1.0


def test_decay_engine_healthy_keeps_full_weight(manager: AlphaLifecycleManager) -> None:
    card = register(manager)
    assessment = AlphaDecayEngine().assess(card, make_live())
    assert assessment.decay_level is DecayLevel.HEALTHY
    assert assessment.weight_multiplier == 1.0
    assert assessment.allow_increase is True
