"""Tests for order submission, idempotency, retry, timeout, fail-closed, and cancel."""

from __future__ import annotations

import pytest
from tests.execution.conftest import FakeBroker, approval_id, make_request

from libs.execution.engine import ExecStatus, ExecutionEngine
from libs.execution.errors import ExecutionError
from libs.store.connection import Database
from libs.store.trading import OrderStore


def test_submit_fills_and_tracks_position(
    db: Database, broker: FakeBroker, engine: ExecutionEngine
) -> None:
    result = engine.submit_order(make_request(approval_id(db)))
    assert result.status is ExecStatus.FILLED
    assert result.order is not None and result.order.status == "filled"
    assert result.broker_order_id is not None
    position = OrderStore(db).get_position("XAUUSD")
    assert position is not None
    assert position.qty == pytest.approx(0.1)


def test_no_duplicate_orders(db: Database, broker: FakeBroker, engine: ExecutionEngine) -> None:
    approval = approval_id(db)
    first = engine.submit_order(make_request(approval))
    second = engine.submit_order(make_request(approval))  # same idempotency key
    assert first.status is ExecStatus.FILLED
    assert second.status is ExecStatus.DUPLICATE
    assert broker.place_calls == 1  # broker called only once
    assert db.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 1


def test_retry_transient_then_success(
    db: Database, broker: FakeBroker, engine: ExecutionEngine
) -> None:
    broker.fail_transient(2)
    result = engine.submit_order(make_request(approval_id(db)))
    assert result.status is ExecStatus.FILLED
    assert broker.place_calls == 3  # 2 failures + 1 success


def test_retry_exhausted_is_rejected(
    db: Database, broker: FakeBroker, engine: ExecutionEngine
) -> None:
    broker.fail_transient(5)  # exceeds attempts (3)
    result = engine.submit_order(make_request(approval_id(db)))
    assert result.status is ExecStatus.REJECTED
    assert result.order is not None and result.order.status == "rejected"
    assert OrderStore(db).get_position("XAUUSD") is None  # no position created


def test_timeout_needs_reconcile_and_no_fill(
    db: Database, broker: FakeBroker, engine: ExecutionEngine
) -> None:
    broker.set_timeout()
    result = engine.submit_order(make_request(approval_id(db)))
    assert result.status is ExecStatus.NEEDS_RECONCILE
    assert result.order is not None and result.order.status == "pending"
    assert OrderStore(db).get_position("XAUUSD") is None  # never assume a fill


def test_fail_closed_without_approval(engine: ExecutionEngine) -> None:
    with pytest.raises(ExecutionError):
        engine.submit_order(make_request("", risk_approval_id=""))


def test_fail_closed_with_invalid_approval(engine: ExecutionEngine) -> None:
    with pytest.raises(ExecutionError):
        engine.submit_order(make_request("risk_does_not_exist"))


def test_broker_rejection(db: Database, broker: FakeBroker, engine: ExecutionEngine) -> None:
    broker.set_reject()
    result = engine.submit_order(make_request(approval_id(db)))
    assert result.status is ExecStatus.REJECTED
    assert result.order is not None and result.order.status == "rejected"


def test_cancel_pending_order(db: Database, broker: FakeBroker, engine: ExecutionEngine) -> None:
    broker.set_pending()
    submitted = engine.submit_order(make_request(approval_id(db)))
    assert submitted.status is ExecStatus.SUBMITTED
    assert submitted.order is not None
    cancelled = engine.cancel_order(submitted.order.id)
    assert cancelled.status is ExecStatus.CANCELLED
    assert cancelled.order is not None and cancelled.order.status == "cancelled"


def test_cannot_cancel_filled_order(
    db: Database, broker: FakeBroker, engine: ExecutionEngine
) -> None:
    filled = engine.submit_order(make_request(approval_id(db)))
    assert filled.order is not None
    with pytest.raises(ExecutionError):
        engine.cancel_order(filled.order.id)


def test_cancel_unknown_order(engine: ExecutionEngine) -> None:
    with pytest.raises(ExecutionError):
        engine.cancel_order("order_missing")
