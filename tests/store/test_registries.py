"""Tests for the research-run, alpha, and risk registries."""

from __future__ import annotations

import sqlite3

import pytest

from libs.store.connection import Database
from libs.store.registries import AlphaRegistry, ResearchRuns, RiskRegistry


def test_research_run_lifecycle(db: Database) -> None:
    runs = ResearchRuns(db)
    run = runs.create(git_commit="abc", config_hash="h", seed=7, name="gold_session")
    assert run.status == "running"
    updated = runs.set_status(run.id, "completed", metrics={"sharpe": 1.1})
    assert updated.status == "completed"
    assert updated.metrics == {"sharpe": 1.1}
    assert runs.get(run.id) == updated


def test_alpha_registry_create_and_status(db: Database) -> None:
    registry = AlphaRegistry(db)
    alpha = registry.create(
        name="gold_trend", instruments=["XAUUSD"], card={"edge": "trend premium"}
    )
    assert alpha.status == "candidate"
    assert alpha.instruments == ["XAUUSD"]
    assert alpha.card == {"edge": "trend premium"}
    registry.set_status(alpha.id, "validated")
    registry.set_status(alpha.id, "deployed", deploy_date="2026-06-15T00:00:00Z")
    deployed = registry.list_by_status("deployed")
    assert len(deployed) == 1
    assert deployed[0].deploy_date == "2026-06-15T00:00:00Z"


def test_alpha_invalid_status_rejected(db: Database) -> None:
    registry = AlphaRegistry(db)
    alpha = registry.create(name="x", instruments=["XAUUSD"])
    with pytest.raises(sqlite3.IntegrityError):
        registry.set_status(alpha.id, "not_a_status")


def test_risk_registry_limits_events_approvals(db: Database) -> None:
    risk = RiskRegistry(db)
    limit = risk.add_limit(scope="global", metric="max_drawdown", threshold=0.2)
    assert limit.kind == "limit"
    assert limit.active is True

    event = risk.record_event(
        scope="global", metric="max_drawdown", observed=0.25, action="halt"
    )
    assert event.kind == "event"
    assert event.observed == 0.25

    approval = risk.create_approval(target_ref="intent_1", detail={"qty": 0.1})
    assert approval.kind == "approval"
    assert approval.action == "approve"


def test_risk_approval_rejects_bad_action(db: Database) -> None:
    risk = RiskRegistry(db)
    with pytest.raises(ValueError):
        risk.create_approval(target_ref="intent_1", action="maybe")
