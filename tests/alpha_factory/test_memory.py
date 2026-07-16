"""Research memory persistence, outcome updates, and append-only guarantee."""

from __future__ import annotations

import pytest

from libs.alpha_factory.models import FailureCause, ResearchResult
from libs.alpha_factory.research_memory import ResearchMemory
from libs.store.connection import Database


def test_record_and_get_roundtrip(db: Database) -> None:
    mem = ResearchMemory(db)
    rec = mem.record(
        category="momentum", statement="momentum in low vol",
        result=ResearchResult.SUCCESS, success_reason="robust OOS",
        metrics={"sharpe": 1.8},
    )
    fetched = mem.get(rec.id)
    assert fetched is not None
    assert fetched.statement == "momentum in low vol"
    assert fetched.result is ResearchResult.SUCCESS
    assert fetched.metrics["sharpe"] == 1.8


def test_update_result_merges_metrics(db: Database) -> None:
    mem = ResearchMemory(db)
    rec = mem.record(category="trend_following", statement="trend", metrics={"a": 1})
    assert rec.result is ResearchResult.PENDING
    updated = mem.update_result(
        rec.id, result=ResearchResult.FAILURE, failure_cause=FailureCause.OVERFIT,
        failure_reason="DSR failed", failure_stage="validation", metrics={"b": 2},
    )
    assert updated.result is ResearchResult.FAILURE
    assert updated.failure_cause is FailureCause.OVERFIT
    assert updated.metrics == {"a": 1, "b": 2}


def test_update_unknown_raises(db: Database) -> None:
    with pytest.raises(KeyError):
        ResearchMemory(db).update_result("nope", result=ResearchResult.SUCCESS)


def test_success_rate_and_failure_views(db: Database) -> None:
    mem = ResearchMemory(db)
    mem.record(category="momentum", statement="a", result=ResearchResult.SUCCESS)
    mem.record(category="momentum", statement="b", result=ResearchResult.FAILURE,
               failure_cause=FailureCause.CROWDED_EDGE)
    mem.record(category="momentum", statement="c", result=ResearchResult.PENDING)
    assert mem.success_rate("momentum") == 0.5  # 1 of 2 decided
    assert mem.success_rate("absent") == 0.0
    assert len(mem.failures()) == 1
    assert len(mem.by_category("momentum")) == 3
    assert mem.by_failure_cause(FailureCause.CROWDED_EDGE)[0].statement == "b"
    assert mem.failure_cause_histogram() == {"crowded_edge": 1}


def test_research_memory_is_append_only(db: Database) -> None:
    mem = ResearchMemory(db)
    rec = mem.record(category="carry", statement="carry idea")
    with pytest.raises(Exception, match="append-only"), db.transaction() as conn:
        conn.execute("DELETE FROM research_memory WHERE id = ?", (rec.id,))
