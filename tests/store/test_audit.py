"""Tests for the append-only, hash-chained audit log."""

from __future__ import annotations

import sqlite3

import pytest

from libs.store.audit import AuditLog, verify_audit_chain
from libs.store.connection import Database
from libs.store.hashchain import GENESIS_PREV_HASH


def test_append_and_read(db: Database) -> None:
    log = AuditLog(db)
    entry = log.append(
        "order_approval",
        actor="risk_service",
        inputs={"symbol": "XAUUSD", "qty": 0.1},
        rationale="within limits",
        outcome="approved",
    )
    assert entry.seq == 1
    assert entry.prev_hash == GENESIS_PREV_HASH
    assert entry.inputs == {"symbol": "XAUUSD", "qty": 0.1}
    assert log.count() == 1


def test_chain_links_and_verifies(db: Database) -> None:
    log = AuditLog(db)
    first = log.append("a", actor="x", inputs={"i": 1})
    second = log.append("b", actor="x", inputs={"i": 2})
    assert second.prev_hash == first.row_hash
    result = verify_audit_chain(db)
    assert result.ok
    assert result.length == 2
    assert bool(result) is True


def test_update_is_blocked_by_trigger(db: Database) -> None:
    AuditLog(db).append("a", actor="x", inputs={"i": 1})
    with pytest.raises(sqlite3.Error):
        db.execute("UPDATE audit_log SET actor = 'evil' WHERE seq = 1")


def test_delete_is_blocked_by_trigger(db: Database) -> None:
    AuditLog(db).append("a", actor="x", inputs={"i": 1})
    with pytest.raises(sqlite3.Error):
        db.execute("DELETE FROM audit_log WHERE seq = 1")


def test_tamper_detection_after_dropping_trigger(db: Database) -> None:
    log = AuditLog(db)
    log.append("a", actor="x", inputs={"i": 1})
    log.append("b", actor="x", inputs={"i": 2})
    # Bypass immutability to simulate out-of-band tampering of the database file.
    db.execute("DROP TRIGGER audit_log_no_update")
    db.execute("UPDATE audit_log SET actor = 'evil' WHERE seq = 1")
    result = verify_audit_chain(db)
    assert not result.ok
    assert result.broken_seq == 1


def test_empty_chain_is_valid(db: Database) -> None:
    result = verify_audit_chain(db)
    assert result.ok
    assert result.length == 0
