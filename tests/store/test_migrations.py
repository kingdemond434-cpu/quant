"""Tests for the migration runner."""

from __future__ import annotations

from pathlib import Path

from migrations import MIGRATIONS

from libs.store.connection import Database
from libs.store.migrations import applied_versions, current_version, run_migrations

_EXPECTED_TABLES = {
    "snapshots",
    "config_versions",
    "audit_log",
    "trials_ledger",
    "alpha_registry",
    "risk_registry",
    "research_runs",
    "orders",
    "fills",
    "positions",
    "alpha_cards",
    "alpha_events",
    "alpha_performance",
    "research_memory",
    "metric_points",
    "alerts",
    "research_candidates",
    "lab_checkpoint",
    "campaigns",
    "workers",
    "candidate_returns",
}


def test_run_migrations_applies_all(db: Database) -> None:
    assert current_version(db) == 7
    assert applied_versions(db) == [1, 2, 3, 4, 5, 6, 7]


def test_migrations_are_idempotent(db_path: Path) -> None:
    database = Database(db_path)
    first = run_migrations(database, MIGRATIONS)
    second = run_migrations(database, MIGRATIONS)
    assert first == [1, 2, 3, 4, 5, 6, 7]
    assert second == []
    database.close()


def test_all_tables_created(db: Database) -> None:
    rows = db.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    names = {row[0] for row in rows}
    assert names >= _EXPECTED_TABLES


def test_schema_migrations_records_hash(db: Database) -> None:
    row = db.execute("SELECT version, name, sha256 FROM schema_migrations").fetchone()
    assert row["version"] == 1
    assert row["name"] == "core"
    assert len(row["sha256"]) == 64
