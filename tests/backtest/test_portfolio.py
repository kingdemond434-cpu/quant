"""Tests for the portfolio engine (average-cost realized PnL)."""

from __future__ import annotations

import pandas as pd
import pytest

from libs.backtest.events import FillEvent
from libs.backtest.portfolio import PortfolioEngine

_TS = pd.Timestamp("2026-01-05", tz="UTC")


def _fill(units_delta: float, price: float, commission: float = 0.0) -> FillEvent:
    return FillEvent(timestamp=_TS, units_delta=units_delta, price=price, commission=commission)


def test_long_open_close_profit() -> None:
    pf = PortfolioEngine(init_cash=100_000.0)
    pf.apply_fill(_fill(1, 100))
    pf.apply_fill(_fill(-1, 110))
    assert pf.units == 0.0
    assert len(pf.trades) == 1
    assert pf.trades[0].pnl == pytest.approx(10.0)
    assert pf.equity(110) == pytest.approx(100_010.0)


def test_partial_exit() -> None:
    pf = PortfolioEngine(init_cash=100_000.0)
    pf.apply_fill(_fill(2, 100))
    pf.apply_fill(_fill(-1, 110))  # close 1 at +10
    pf.apply_fill(_fill(-1, 90))   # close 1 at -10
    assert [t.pnl for t in pf.trades] == pytest.approx([10.0, -10.0])
    assert pf.units == 0.0


def test_reversal_realizes_then_opens() -> None:
    pf = PortfolioEngine(init_cash=100_000.0)
    pf.apply_fill(_fill(1, 100))
    pf.apply_fill(_fill(-3, 120))  # close 1 (+20), open short 2 at 120
    assert pf.trades[0].pnl == pytest.approx(20.0)
    assert pf.units == pytest.approx(-2.0)
    assert pf.entry_price == pytest.approx(120.0)


def test_short_profit() -> None:
    pf = PortfolioEngine(init_cash=100_000.0)
    pf.apply_fill(_fill(-1, 100))
    pf.apply_fill(_fill(1, 90))
    assert pf.trades[0].pnl == pytest.approx(10.0)
    assert pf.units == 0.0


def test_commission_reduces_trade_pnl() -> None:
    pf = PortfolioEngine(init_cash=100_000.0)
    pf.apply_fill(_fill(1, 100))
    pf.apply_fill(_fill(-1, 110, commission=2.0))
    assert pf.trades[0].pnl == pytest.approx(8.0)  # 10 gross - 2 commission
