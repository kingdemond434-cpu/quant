"""Migration 0004 — monitoring telemetry and alerts.

A durable, append-only metric time-series and an alert ledger. Metric rows are immutable; alert
rows may be updated only to mark resolution, never deleted. Keeps observability state in the
single SQLite system of record (no parallel store).
"""

from __future__ import annotations

from libs.store.migrations import Migration

_SEVERITIES = "'info', 'warning', 'critical'"

STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE metric_points (
        seq        INTEGER PRIMARY KEY AUTOINCREMENT,
        id         TEXT NOT NULL UNIQUE,
        created_at TEXT NOT NULL,
        name       TEXT NOT NULL,
        value      REAL NOT NULL,
        tags_json  TEXT
    )
    """,
    """
    CREATE TRIGGER metric_points_no_update
    BEFORE UPDATE ON metric_points
    BEGIN
        SELECT RAISE(ABORT, 'metric_points is append-only');
    END
    """,
    """
    CREATE TRIGGER metric_points_no_delete
    BEFORE DELETE ON metric_points
    BEGIN
        SELECT RAISE(ABORT, 'metric_points is append-only');
    END
    """,
    f"""
    CREATE TABLE alerts (
        seq        INTEGER PRIMARY KEY AUTOINCREMENT,
        id         TEXT NOT NULL UNIQUE,
        created_at TEXT NOT NULL,
        severity   TEXT NOT NULL CHECK (severity IN ({_SEVERITIES})),
        source     TEXT NOT NULL,
        metric     TEXT,
        value      REAL,
        threshold  REAL,
        message    TEXT NOT NULL,
        resolved   INTEGER NOT NULL DEFAULT 0
    )
    """,
    """
    CREATE TRIGGER alerts_no_delete
    BEFORE DELETE ON alerts
    BEGIN
        SELECT RAISE(ABORT, 'alerts is append-only (resolve, do not delete)');
    END
    """,
    "CREATE INDEX idx_metric_points_name ON metric_points(name)",
    "CREATE INDEX idx_alerts_resolved ON alerts(resolved)",
)

MIGRATION = Migration(version=4, name="monitoring", statements=STATEMENTS)
