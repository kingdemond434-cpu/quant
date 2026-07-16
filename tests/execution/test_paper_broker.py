"""Paper broker — deterministic fills, idempotency, position tracking."""

from __future__ import annotations

from libs.execution.broker import OrderRequest
from libs.execution.paper_broker import PaperBroker


def _req(key: str, side: str = "buy", qty: float = 0.1) -> OrderRequest:
    return OrderRequest(
        idempotency_key=key, instrument="EURUSD", side=side, qty=qty, order_type="market",
        risk_approval_id="appr-1",
    )


def test_fills_at_mark_price_and_tracks_position() -> None:
    broker = PaperBroker(default_price=1.10)
    result = broker.place_order(_req("a"))
    assert result.status == "filled"
    assert result.fill_price == 1.10
    positions = broker.get_positions()
    assert positions[0].instrument == "EURUSD"
    assert positions[0].qty == 0.1


def test_idempotent_dedup() -> None:
    broker = PaperBroker()
    first = broker.place_order(_req("same"))
    second = broker.place_order(_req("same"))
    assert first.broker_order_id == second.broker_order_id  # no double fill
    assert broker.get_positions()[0].qty == 0.1


def test_slippage_is_adverse() -> None:
    broker = PaperBroker(default_price=100.0, slippage_bps=10.0)
    buy = broker.place_order(_req("b", side="buy"))
    sell = broker.place_order(_req("s", side="sell"))
    assert buy.fill_price is not None and buy.fill_price > 100.0   # buy pays up
    assert sell.fill_price is not None and sell.fill_price < 100.0  # sell receives less


def test_set_price_overrides_default() -> None:
    broker = PaperBroker(default_price=1.0)
    broker.set_price("EURUSD", 1.2345)
    assert broker.place_order(_req("c")).fill_price == 1.2345
    assert broker.get_order("c") is not None
    assert broker.cancel_order(1) is True
