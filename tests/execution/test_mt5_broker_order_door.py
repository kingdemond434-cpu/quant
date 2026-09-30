"""`libs.execution.broker.MT5Broker` reaches the venue only through the one door for money.

MetaTrader5 installs only on Windows, so the module is faked in `sys.modules`. The tests pin that
both of the broker's writes (a market order and a cancel) go through `mt5desk.order_door.send`:
`order_check` runs first, one ledger row is written per attempt, and a broker-check rejection of
new risk comes back as `rejected` without a send.
"""
from __future__ import annotations

import sys
from types import SimpleNamespace
from typing import Any

import pytest

from libs.execution.broker import MT5Broker, OrderRequest, _order_door


class _FakeMT5(SimpleNamespace):
    TRADE_ACTION_DEAL = 1
    TRADE_ACTION_REMOVE = 8
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    ORDER_FILLING_IOC = 1
    TRADE_RETCODE_DONE = 10009
    POSITION_TYPE_BUY = 0

    def __init__(self) -> None:
        super().__init__()
        self.check_retcode = 0
        self.checked: list[dict] = []
        self.sent: list[dict] = []

    def initialize(self) -> bool:
        return True

    def last_error(self) -> tuple[int, str]:
        return (1, "ok")

    def symbol_info_tick(self, symbol: str) -> Any:
        return SimpleNamespace(bid=1.1, ask=1.1002)

    def order_check(self, req: dict) -> Any:
        self.checked.append(dict(req))
        return SimpleNamespace(retcode=self.check_retcode, comment="checked")

    def order_send(self, req: dict) -> Any:
        self.sent.append(dict(req))
        return SimpleNamespace(retcode=10009, order=77, deal=88, volume=req.get("volume", 0.0),
                               price=req.get("price", 0.0), comment="done")


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> _FakeMT5:
    monkeypatch.setenv("MT5_ORDER_DOOR_DIR", str(tmp_path))
    mod = _FakeMT5()
    monkeypatch.setitem(sys.modules, "MetaTrader5", mod)
    _order_door()._MEMORY_IN_DOUBT.clear()
    return mod


def _req() -> OrderRequest:
    return OrderRequest(idempotency_key="k-1", instrument="EURUSD", side="buy", qty=0.1,
                        order_type="market", risk_approval_id="appr-1")


def test_mt5_broker_binds_the_guarded_module(fake: _FakeMT5) -> None:
    assert _order_door().is_guarded(MT5Broker()._mt5)


def test_place_and_cancel_go_through_the_door(fake: _FakeMT5) -> None:
    b = MT5Broker()
    res = b.place_order(_req())
    assert res.status == "filled" and res.broker_order_id == 77
    assert b.cancel_order(77) is True
    assert len(fake.checked) == 2 and len(fake.sent) == 2
    rows = _order_door().read_ledger()
    assert [r["kind"] for r in rows] == ["open", "cancel"]
    assert all(r["caller"] == "libs.execution.broker" for r in rows)


def test_a_broker_check_reject_is_rejected_without_a_send(fake: _FakeMT5) -> None:
    fake.check_retcode = 10019                       # no_money
    res = MT5Broker().place_order(_req())
    assert res.status == "rejected" and fake.sent == []
    assert res.broker_order_id == 0 and res.filled_qty == 0.0
