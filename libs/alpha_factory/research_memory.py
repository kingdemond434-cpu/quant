"""Research memory — a durable record of every idea ever tested (never lose knowledge).

Persists to the ``research_memory`` table (migration 0003) via the existing Database; rows are
append-only (no deletes) but an outcome may be updated. Stores structured failure causes so the
hypothesis engine and allocator can steer effort away from low-probability research paths.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from typing import Any

from libs.alpha_factory.models import FailureCause, IdeaRecord, ResearchResult
from libs.core.ids import generate_id
from libs.core.time import to_iso8601, utcnow
from libs.store.connection import Database

_COLUMNS = (
    "id, created_at, category, statement, result, failure_cause, failure_reason, "
    "success_reason, failure_stage, lessons, metrics_json, predecessor_id"
)


def _row_to_record(row: sqlite3.Row) -> IdeaRecord:
    return IdeaRecord(
        id=row["id"],
        created_at=row["created_at"],
        category=row["category"],
        statement=row["statement"],
        result=ResearchResult(row["result"]),
        failure_cause=(
            FailureCause(row["failure_cause"]) if row["failure_cause"] else FailureCause.NONE
        ),
        failure_reason=row["failure_reason"],
        success_reason=row["success_reason"],
        failure_stage=row["failure_stage"],
        lessons=row["lessons"],
        metrics=json.loads(row["metrics_json"]) if row["metrics_json"] else {},
        predecessor_id=row["predecessor_id"],
    )


class ResearchMemory:
    """Reader/writer for the durable research-memory table."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def record(
        self,
        *,
        category: str,
        statement: str,
        result: ResearchResult = ResearchResult.PENDING,
        failure_cause: FailureCause = FailureCause.NONE,
        failure_reason: str | None = None,
        success_reason: str | None = None,
        failure_stage: str | None = None,
        lessons: str | None = None,
        metrics: Mapping[str, Any] | None = None,
        predecessor_id: str | None = None,
    ) -> IdeaRecord:
        record = IdeaRecord(
            id=generate_id("idea"), created_at=to_iso8601(utcnow()), category=category,
            statement=statement, result=result, failure_cause=failure_cause,
            failure_reason=failure_reason, success_reason=success_reason,
            failure_stage=failure_stage, lessons=lessons, metrics=dict(metrics or {}),
            predecessor_id=predecessor_id,
        )
        with self.db.transaction() as conn:
            conn.execute(
                f"INSERT INTO research_memory ({_COLUMNS}) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    record.id, record.created_at, record.category, record.statement,
                    record.result.value, record.failure_cause.value, record.failure_reason,
                    record.success_reason, record.failure_stage, record.lessons,
                    json.dumps(record.metrics), record.predecessor_id,
                ),
            )
        return record

    def update_result(
        self,
        idea_id: str,
        *,
        result: ResearchResult,
        failure_cause: FailureCause = FailureCause.NONE,
        failure_reason: str | None = None,
        success_reason: str | None = None,
        failure_stage: str | None = None,
        lessons: str | None = None,
        metrics: Mapping[str, Any] | None = None,
    ) -> IdeaRecord:
        existing = self.get(idea_id)
        if existing is None:
            raise KeyError(f"unknown idea {idea_id}")
        merged = {**existing.metrics, **(metrics or {})}
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE research_memory SET result = ?, failure_cause = ?, failure_reason = ?, "
                "success_reason = ?, failure_stage = ?, lessons = ?, metrics_json = ? "
                "WHERE id = ?",
                (
                    result.value, failure_cause.value, failure_reason, success_reason,
                    failure_stage, lessons or existing.lessons, json.dumps(merged), idea_id,
                ),
            )
        got = self.get(idea_id)
        assert got is not None  # just updated
        return got

    def get(self, idea_id: str) -> IdeaRecord | None:
        row = self.db.execute(
            f"SELECT {_COLUMNS} FROM research_memory WHERE id = ?", (idea_id,)
        ).fetchone()
        return _row_to_record(row) if row else None

    def all(self) -> list[IdeaRecord]:
        rows = self.db.execute(
            f"SELECT {_COLUMNS} FROM research_memory ORDER BY created_at, id"
        ).fetchall()
        return [_row_to_record(r) for r in rows]

    def by_category(self, category: str) -> list[IdeaRecord]:
        return [r for r in self.all() if r.category == category]

    def failures(self) -> list[IdeaRecord]:
        return [r for r in self.all() if r.result is ResearchResult.FAILURE]

    def by_failure_cause(self, cause: FailureCause) -> list[IdeaRecord]:
        return [r for r in self.failures() if r.failure_cause is cause]

    def success_rate(self, category: str | None = None) -> float:
        records = self.by_category(category) if category is not None else self.all()
        decided = [r for r in records if r.result is not ResearchResult.PENDING]
        if not decided:
            return 0.0
        wins = sum(1 for r in decided if r.result is ResearchResult.SUCCESS)
        return wins / len(decided)

    def failure_cause_histogram(self) -> dict[str, int]:
        hist: dict[str, int] = {}
        for r in self.failures():
            hist[r.failure_cause.value] = hist.get(r.failure_cause.value, 0) + 1
        return hist
