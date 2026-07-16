"""Tests for orders/fills/positions and the structural risk-approval invariant."""

from __future__ import annotations

import pytest

from libs.store.connection import Database
from libs.store.registries import RiskRegistry
from libs.store.trading import OrderStore


def _approval(db: Database, action: str = "approve") -> str:
    return RiskRegistry(db).create_approval(target_ref="intent_1", action=action).id


def test_order_requires_valid_approval(db: Database) -> None:
    store = OrderStore(db)
    approval_id = _approval(db)
    order = store.create_order(
        instrument="XAUUSD", side="buy", qty=0.1, order_type="market",
        risk_approval_id=approval_id, intended_price=2000.0,
    )
    assert order.status == "pending"
    assert order.risk_approval_id == approval_id


def test_order_rejected_without_existing_approval(db: Database) -> None:
    store = OrderStore(db)
    with pytest.raises(ValueError):
        store.create_order(
            instrument="XAUUSD", side="buy", qty=0.1, order_type="market",
            risk_approval_id="risk_does_not_exist",
        )


def test_order_rejected_when_approval_is_a_limit(db: Database) -> None:
    store = OrderStore(db)
    limit_id = RiskRegistry(db).add_limit(scope="global", metric="dd", threshold=0.2).id
    with pytest.raises(ValueError):
        store.create_order(
            instrument="XAUUSD", side="buy", qty=0.1, order_type="market",
            risk_approval_id=limit_id,
        )


def test_order_rejected_when_approval_is_a_rejection(db: Database) -> None:
    store = OrderStore(db)
    rejection_id = _approval(db, action="reject")
    with pytest.raises(ValueError):
        store.create_order(
            instrument="XAUUSD", side="buy", qty=0.1, order_type="market",
            risk_approval_id=rejection_id,
        )


def test_fills_and_status(db: Database) -> None:
    store = OrderStore(db)
    order = store.create_order(
        instrument="XAUUSD", side="buy", qty=0.2, order_type="market",
        risk_approval_id=_approval(db),
    )
    store.record_fill(order_id=order.id, fill_price=2001.0, fill_qty=0.2, commission=0.07)
    store.set_order_status(order.id, "filled", mt5_ticket=12345)
    fills = store.fills_for(order.id)
    assert len(fills) == 1
    assert fills[0].fill_qty == 0.2
    assert store.get_order(order.id).status == "filled"
    assert store.get_order(order.id).mt5_ticket == 12345


def test_positions_upsert(db: Database) -> None:
    store = OrderStore(db)
    store.upsert_position(instrument="XAUUSD", qty=0.2, avg_price=2000.0)
    store.upsert_position(instrument="XAUUSD", qty=0.5, avg_price=2010.0, realized_pnl=3.0)
    position = store.get_position("XAUUSD")
    assert position.qty == 0.5
    assert position.avg_price == 2010.0
    assert position.realized_pnl == 3.0
