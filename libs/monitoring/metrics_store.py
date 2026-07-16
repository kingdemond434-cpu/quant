"""Metrics store — durable, append-only metric time-series (migration 0004)."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from typing import Any

from libs.core.ids import generate_id
from libs.core.time import to_iso8601, utcnow
from libs.monitoring.models import MetricPoint
from libs.store.connection import Database


def _row_to_point(row: sqlite3.Row) -> MetricPoint:
    return MetricPoint(
        id=row["id"], created_at=row["created_at"], name=row["name"], value=row["value"],
        tags=json.loads(row["tags_json"]) if row["tags_json"] else {},
    )


class MetricsStore:
    """Writer/reader for the append-only ``metric_points`` table."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def record(
        self, name: str, value: float, *, tags: Mapping[str, Any] | None = None
    ) -> MetricPoint:
        point = MetricPoint(
            id=generate_id("metric"), created_at=to_iso8601(utcnow()), name=name,
            value=float(value), tags=dict(tags or {}),
        )
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO metric_points (id, created_at, name, value, tags_json) "
                "VALUES (?, ?, ?, ?, ?)",
                (point.id, point.created_at, point.name, point.value, json.dumps(point.tags)),
            )
        return point

    def latest(self, name: str) -> MetricPoint | None:
        row = self.db.execute(
            "SELECT * FROM metric_points WHERE name = ? ORDER BY seq DESC LIMIT 1", (name,)
        ).fetchone()
        return _row_to_point(row) if row else None

    def history(self, name: str, *, limit: int = 100) -> list[MetricPoint]:
        rows = self.db.execute(
            "SELECT * FROM metric_points WHERE name = ? ORDER BY seq DESC LIMIT ?", (name, limit)
        ).fetchall()
        return [_row_to_point(r) for r in reversed(rows)]
