"""Tests for the alpha lifecycle manager (registry, transitions, audit, decay, successors)."""

from __future__ import annotations

import sqlite3

import pytest
from tests.alpha.conftest import make_live, make_new

from libs.alpha.errors import AlphaError, AlphaStateError
from libs.alpha.manager import AlphaLifecycleManager
from libs.alpha.state import AlphaState
from libs.store.connection import Database


def test_register_creates_candidate_with_audit(manager: AlphaLifecycleManager) -> None:
    card = manager.register_alpha(make_new())
    assert card.status is AlphaState.CANDIDATE
    assert card.decay_score == 0.0
    events = manager.audit_trail(card.id)
    assert [e.event_type for e in events] == ["creation"]


def test_promotion_chain_sets_deployment_date(manager: AlphaLifecycleManager) -> None:
    card = manager.register_alpha(make_new())
    card = manager.promote_alpha(card.id)
    assert card.status is AlphaState.PROBATION
    card = manager.promote_alpha(card.id)
    assert card.status is AlphaState.ACTIVE
    assert card.deployment_date is not None


def test_illegal_promotion_raises(manager: AlphaLifecycleManager) -> None:
    card = manager.register_alpha(make_new())
    manager.promote_alpha(card.id)  # -> probation
    manager.promote_alpha(card.id)  # -> active
    with pytest.raises(AlphaStateError):
        manager.promote_alpha(card.id)  # active cannot be promoted


def test_illegal_transition_raises(manager: AlphaLifecycleManager) -> None:
    card = manager.register_alpha(make_new())
    with pytest.raises(AlphaStateError):
        manager.transition(card.id, AlphaState.ACTIVE, reason="skip probation")


def test_update_alpha_and_unknown_field(manager: AlphaLifecycleManager) -> None:
    card = manager.register_alpha(make_new())
    updated = manager.update_alpha(card.id, expected_sharpe=2.0)
    assert updated.expected_sharpe == 2.0
    assert any(e.event_type == "update" for e in manager.audit_trail(card.id))
    with pytest.raises(AlphaError):
        manager.update_alpha(card.id, status="active")


def test_record_performance_updates_live_metrics(manager: AlphaLifecycleManager) -> None:
    card = manager.register_alpha(make_new())
    snapshot = manager.record_performance(card.id, make_live(sharpe=1.2, cagr=0.15))
    assert snapshot.sharpe == 1.2
    refreshed = manager.get_alpha(card.id)
    assert refreshed is not None and refreshed.live_sharpe == 1.2
    assert len(manager.performance.history(card.id)) == 1


def test_evaluate_health(manager: AlphaLifecycleManager) -> None:
    card = manager.register_alpha(make_new())
    health = manager.evaluate_health(card.id, make_live())
    assert health.healthy


def test_evaluate_decay_healthy_keeps_state(manager: AlphaLifecycleManager) -> None:
    card = manager.register_alpha(make_new())
    manager.promote_alpha(card.id)
    manager.promote_alpha(card.id)  # active
    result = manager.evaluate_decay(card.id, make_live())
    assert result.recommended_state is AlphaState.ACTIVE
    assert manager.get_alpha(card.id).status is AlphaState.ACTIVE


def test_evaluate_decay_auto_downgrades_and_recommends_successors(
    manager: AlphaLifecycleManager,
) -> None:
    replacement = manager.register_alpha(make_new(name="gold_session_v2"))
    card = manager.register_alpha(make_new())
    manager.promote_alpha(card.id)
    manager.promote_alpha(card.id)  # active

    degraded = make_live(
        sharpe=0.1, cagr=0.0, max_drawdown=0.35, profit_factor=0.7,
        expectancy=0.0, win_rate=0.4, regime_stability=0.2,
    )
    first = manager.evaluate_decay(card.id, degraded)
    assert first.decay_score > 0.5
    assert manager.get_alpha(card.id).status is AlphaState.WATCH  # active -> watch (gradual)

    manager.evaluate_decay(card.id, degraded)
    assert manager.get_alpha(card.id).status is AlphaState.DECAYING
    events = [e.event_type for e in manager.audit_trail(card.id)]
    assert "successor_recommendation" in events
    assert replacement.id in {c.id for c in manager.recommend_successors(card.id)}


def test_retire_with_successor_links_both(manager: AlphaLifecycleManager) -> None:
    old = manager.register_alpha(make_new())
    new = manager.register_alpha(make_new(name="successor"))
    retired = manager.retire_alpha(old.id, successor_id=new.id)
    assert retired.status is AlphaState.RETIRED
    assert retired.retirement_date is not None
    assert retired.successor_id == new.id
    assert manager.get_alpha(new.id).predecessor_id == old.id


def test_predecessor_link_on_register(manager: AlphaLifecycleManager) -> None:
    parent = manager.register_alpha(make_new())
    child = manager.register_alpha(make_new(name="child", predecessor_id=parent.id))
    assert manager.get_alpha(parent.id).successor_id == child.id
    assert child.predecessor_id == parent.id


def test_audit_log_is_append_only(manager: AlphaLifecycleManager, db: Database) -> None:
    card = manager.register_alpha(make_new())
    with pytest.raises(sqlite3.Error):
        db.execute("UPDATE alpha_events SET actor = 'x' WHERE alpha_id = ?", (card.id,))
    with pytest.raises(sqlite3.Error):
        db.execute("DELETE FROM alpha_events WHERE alpha_id = ?", (card.id,))


def test_registry_listings(manager: AlphaLifecycleManager) -> None:
    a = manager.register_alpha(make_new(name="a"))
    manager.register_alpha(make_new(name="b"))
    manager.promote_alpha(a.id)  # a -> probation
    assert len(manager.list_all()) == 2
    assert len(manager.list_candidates()) == 1
    probation = manager.list_by_status(AlphaState.PROBATION)
    assert {c.status for c in probation} == {AlphaState.PROBATION}


def test_unknown_alpha_raises(manager: AlphaLifecycleManager) -> None:
    with pytest.raises(AlphaError):
        manager.promote_alpha("alpha_missing")
