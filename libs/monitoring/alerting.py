"""Alert persistence and routing.

Alerts are recorded to the durable ``alerts`` table and dispatched to pluggable sinks. The default
:class:`CollectingSink` keeps them in memory (useful for tests and headless runs); production can
add log/webhook sinks without changing callers.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from typing import Protocol

from libs.core.ids import generate_id
from libs.core.time import to_iso8601, utcnow
from libs.monitoring.models import Alert, Severity
from libs.store.connection import Database


def _row_to_alert(row: sqlite3.Row) -> Alert:
    return Alert(
        id=row["id"], created_at=row["created_at"], severity=Severity(row["severity"]),
        source=row["source"], metric=row["metric"], value=row["value"],
        threshold=row["threshold"], message=row["message"], resolved=bool(row["resolved"]),
    )


class AlertSink(Protocol):
    def emit(self, alert: Alert) -> None: ...


class CollectingSink:
    """An in-memory sink that retains every alert emitted (default, deterministic)."""

    def __init__(self) -> None:
        self.alerts: list[Alert] = []

    def emit(self, alert: Alert) -> None:
        self.alerts.append(alert)


class AlertStore:
    """Writer/reader for the ``alerts`` table (append-only; resolvable, never deleted)."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def record(
        self,
        *,
        severity: Severity,
        source: str,
        message: str,
        metric: str | None = None,
        value: float | None = None,
        threshold: float | None = None,
    ) -> Alert:
        alert = Alert(
            id=generate_id("alert"), created_at=to_iso8601(utcnow()), severity=severity,
            source=source, metric=metric, value=value, threshold=threshold, message=message,
        )
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO alerts "
                "(id, created_at, severity, source, metric, value, threshold, message, resolved) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)",
                (alert.id, alert.created_at, alert.severity.value, alert.source, alert.metric,
                 alert.value, alert.threshold, alert.message),
            )
        return alert

    def resolve(self, alert_id: str) -> None:
        with self.db.transaction() as conn:
            conn.execute("UPDATE alerts SET resolved = 1 WHERE id = ?", (alert_id,))

    def open_alerts(self) -> list[Alert]:
        rows = self.db.execute(
            "SELECT * FROM alerts WHERE resolved = 0 ORDER BY seq"
        ).fetchall()
        return [_row_to_alert(r) for r in rows]

    def all(self) -> list[Alert]:
        rows = self.db.execute("SELECT * FROM alerts ORDER BY seq").fetchall()
        return [_row_to_alert(r) for r in rows]


class AlertRouter:
    """Fans an alert out to every configured sink."""

    def __init__(self, sinks: Sequence[AlertSink] | None = None) -> None:
        self.sinks: list[AlertSink] = list(sinks) if sinks else [CollectingSink()]

    def dispatch(self, alert: Alert) -> None:
        for sink in self.sinks:
            sink.emit(alert)
