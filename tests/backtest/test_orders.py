"""Tests for the order manager (protective exits)."""

from __future__ import annotations

import pandas as pd

from libs.backtest.events import MarketEvent
from libs.backtest.orders import OrderManager, ProtectiveState

_TS = pd.Timestamp("2026-01-05", tz="UTC")


def _bar(open_: float, high: float, low: float, close: float) -> MarketEvent:
    return MarketEvent(index=0, timestamp=_TS, open=open_, high=high, low=low, close=close,
                       volume=1.0)


def test_long_stop_loss() -> None:
    state = ProtectiveState(entry_price=100.0, sign=1, stop_loss=0.05, anchor=100.0)
    exit_price = OrderManager.check_protective(state, _bar(98, 99, 94, 95))
    assert exit_price == 95.0  # min(stop 95, open 98)


def test_long_stop_loss_gap_fills_at_open() -> None:
    state = ProtectiveState(entry_price=100.0, sign=1, stop_loss=0.05, anchor=100.0)
    exit_price = OrderManager.check_protective(state, _bar(90, 92, 85, 88))
    assert exit_price == 90.0  # gap down below stop -> fills at open


def test_long_take_profit() -> None:
    state = ProtectiveState(entry_price=100.0, sign=1, take_profit=0.05, anchor=100.0)
    exit_price = OrderManager.check_protective(state, _bar(101, 106, 100, 104))
    assert exit_price == 105.0


def test_long_trailing_stop() -> None:
    state = ProtectiveState(entry_price=100.0, sign=1, trailing=0.10, anchor=100.0)
    exit_price = OrderManager.check_protective(state, _bar(110, 120, 107, 108))
    assert exit_price == 108.0  # anchor 120 -> trail stop 108; low 107 triggers


def test_short_stop_loss() -> None:
    state = ProtectiveState(entry_price=100.0, sign=-1, stop_loss=0.05, anchor=100.0)
    exit_price = OrderManager.check_protective(state, _bar(102, 106, 101, 105))
    assert exit_price == 105.0


def test_no_trigger_returns_none() -> None:
    state = ProtectiveState(entry_price=100.0, sign=1, stop_loss=0.05, take_profit=0.10,
                            anchor=100.0)
    assert OrderManager.check_protective(state, _bar(100, 103, 98, 101)) is None
