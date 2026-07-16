"""Tests for the event-driven engine (hand-checked scenarios)."""

from __future__ import annotations

import pytest
from tests.backtest.conftest import explicit_bars, make_bars

from libs.backtest.engine import Backtest, BacktestConfig, run_signal_backtest
from libs.backtest.strategy import MovingAverageCrossStrategy, SignalStrategy


def test_units_mode_equity_path_is_exact() -> None:
    result = run_signal_backtest(explicit_bars(), [1, 1, 0, 0], init_cash=100_000.0)
    assert list(result.equity.round(6)) == [100_000.0, 100_005.0, 100_002.0, 100_002.0]
    assert len(result.trades) == 1
    assert result.trades[0].pnl == pytest.approx(2.0)
    assert result.trades[0].entry_price == pytest.approx(100.0)
    assert result.trades[0].exit_price == pytest.approx(102.0)


def test_fraction_mode_single_trade() -> None:
    config = BacktestConfig(sizing_mode="fraction", init_cash=100_000.0)
    result = Backtest(config).run(explicit_bars(), SignalStrategy([1, 0, 0, 0]))
    assert result.equity.iloc[-1] == pytest.approx(105_000.0)
    assert result.trades[0].pnl == pytest.approx(5_000.0)


def test_stop_loss_exit() -> None:
    bars = explicit_bars().iloc[:3].copy()
    bars["open"] = [100.0, 100.0, 99.0]
    bars["high"] = [101.0, 102.0, 100.0]
    bars["low"] = [99.0, 98.0, 96.0]
    bars["close"] = [100.0, 101.0, 97.0]
    config = BacktestConfig(sizing_mode="units", init_cash=100_000.0)
    result = Backtest(config).run(bars, SignalStrategy([1, 1, 1], stop_loss=0.03))
    assert len(result.trades) == 1
    assert result.trades[0].exit_price == pytest.approx(97.0)
    assert result.trades[0].pnl == pytest.approx(-3.0)


def test_short_signal_runs() -> None:
    result = run_signal_backtest(explicit_bars(), [-1, -1, 0, 0])
    assert len(result.equity) == 4
    assert result.trades[0].sign == -1


def test_ma_cross_strategy_runs() -> None:
    bars = make_bars(80, seed=1)
    result = Backtest().run(bars, MovingAverageCrossStrategy(fast=5, slow=20))
    assert len(result.equity) == 80
    assert result.metrics.n_trades >= 0
