"""Tests for the Database connection (WAL, foreign keys, single-writer, transactions)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from libs.store.connection import Database


def test_wal_mode_enabled(db: Database) -> None:
    assert db.journal_mode() == "wal"


def test_foreign_keys_enforced(db: Database) -> None:
    assert db.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    # an order referencing a non-existent risk approval violates the FK
    with pytest.raises(sqlite3.IntegrityError), db.transaction() as conn:
        conn.execute(
            "INSERT INTO orders "
            "(id, created_at, updated_at, instrument, side, qty, order_type, "
            " risk_approval_id, status) "
            "VALUES ('order_x', 't', 't', 'XAUUSD', 'buy', 1.0, 'market', 'missing', 'pending')"
        )


def test_read_only_database_cannot_write(db: Database, db_path: Path) -> None:
    reader = Database(db_path, read_only=True)
    try:
        with pytest.raises(sqlite3.OperationalError):
            reader.execute(
                "INSERT INTO positions (instrument, qty, avg_price, updated_at) "
                "VALUES ('XAUUSD', 1.0, 2000.0, 't')"
            )
    finally:
        reader.close()


def test_read_only_rejects_transaction(db_path: Path) -> None:
    Database(db_path).close()  # ensure the file exists
    reader = Database(db_path, read_only=True)
    try:
        with pytest.raises(RuntimeError), reader.transaction():
            pass
    finally:
        reader.close()


def test_transaction_rolls_back_on_error(db: Database) -> None:
    with pytest.raises(RuntimeError), db.transaction() as conn:
        conn.execute(
            "INSERT INTO positions (instrument, qty, avg_price, updated_at) "
            "VALUES ('XAUUSD', 1.0, 2000.0, 't')"
        )
        raise RuntimeError("boom")
    assert db.execute("SELECT COUNT(*) FROM positions").fetchone()[0] == 0


def test_transaction_commits_on_success(db: Database) -> None:
    with db.transaction() as conn:
        conn.execute(
            "INSERT INTO positions (instrument, qty, avg_price, updated_at) "
            "VALUES ('XAUUSD', 1.0, 2000.0, 't')"
        )
    assert db.execute("SELECT COUNT(*) FROM positions").fetchone()[0] == 1
