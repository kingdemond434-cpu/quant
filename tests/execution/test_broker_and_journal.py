"""Tests for broker-level idempotency and the immutable trade journal."""

from __future__ import annotations

from tests.execution.conftest import FakeBroker, approval_id, make_request

from libs.execution.engine import ExecutionEngine
from libs.store.audit import verify_audit_chain
from libs.store.connection import Database


def test_broker_dedups_same_client_id(broker: FakeBroker) -> None:
    request = make_request("approval_x")
    first = broker.place_order(request)
    second = broker.place_order(request)  # same idempotency key
    assert first.broker_order_id == second.broker_order_id
    positions = broker.get_positions()
    assert len(positions) == 1
    assert positions[0].qty == 0.1  # not doubled


def test_journal_records_events_immutably(
    db: Database, broker: FakeBroker, engine: ExecutionEngine
) -> None:
    engine.submit_order(make_request(approval_id(db)))
    count = db.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
    assert count >= 2  # at least order_submitted + order_filled
    assert verify_audit_chain(db).ok


def test_journal_records_timeout_event(
    db: Database, broker: FakeBroker, engine: ExecutionEngine
) -> None:
    broker.set_timeout()
    engine.submit_order(make_request(approval_id(db)))
    events = [
        row["decision_type"]
        for row in db.execute("SELECT decision_type FROM audit_log").fetchall()
    ]
    assert "order_timeout" in events
    assert verify_audit_chain(db).ok
