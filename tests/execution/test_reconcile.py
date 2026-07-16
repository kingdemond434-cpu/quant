"""Tests for reconciliation, safe restart, and the broker-as-source-of-truth rule."""

from __future__ import annotations

from tests.execution.conftest import FakeBroker, approval_id, make_request

from libs.execution.engine import ExecutionEngine
from libs.store.connection import Database
from libs.store.trading import OrderStore


def test_reconcile_adopts_broker_truth_and_halts_on_divergence(
    db: Database, broker: FakeBroker, engine: ExecutionEngine
) -> None:
    broker.add_position("XAUUSD", 0.5, 1990.0)  # broker has a position the engine doesn't know
    report = engine.reconcile_positions()
    assert report.divergence
    assert report.halted  # fail closed
    position = OrderStore(db).get_position("XAUUSD")
    assert position is not None and position.qty == 0.5  # adopted broker truth


def test_safe_start_syncs_without_halting(
    db: Database, broker: FakeBroker, engine: ExecutionEngine
) -> None:
    broker.add_position("BTCUSD", 0.2, 50_000.0)
    report = engine.safe_start()
    assert report.divergence  # there was state to adopt
    assert not report.halted  # restart adopts broker state rather than halting
    assert OrderStore(db).get_position("BTCUSD").qty == 0.2


def test_reconcile_no_divergence_after_fill(
    db: Database, broker: FakeBroker, engine: ExecutionEngine
) -> None:
    engine.submit_order(make_request(approval_id(db)))  # fills 0.1 and syncs
    report = engine.reconcile_positions()
    assert not report.divergence
    assert not report.halted


def test_reconcile_zeroes_stale_internal_position(
    db: Database, broker: FakeBroker, engine: ExecutionEngine
) -> None:
    # engine thinks it holds a position the broker has since closed
    OrderStore(db).upsert_position(instrument="XAUUSD", qty=1.0, avg_price=2000.0)
    report = engine.reconcile_positions()
    assert report.divergence
    assert OrderStore(db).get_position("XAUUSD").qty == 0.0
