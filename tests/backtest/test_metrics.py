"""Tests for the metrics engine."""

from __future__ import annotations

import math

import pandas as pd
import pytest

from libs.backtest.metrics import compute_metrics
from libs.backtest.portfolio import Trade

_TS = pd.Timestamp("2026-01-05", tz="UTC")


def _equity(values: list[float]) -> pd.Series:
    idx = pd.date_range("2026-01-05", periods=len(values), freq="1D", tz="UTC")
    return pd.Series(values, index=idx, name="equity")


def _trade(pnl: float) -> Trade:
    return Trade(
        entry_time=_TS, exit_time=_TS, sign=1, units=1.0,
        entry_price=100.0, exit_price=100.0 + pnl, pnl=pnl,
    )


def test_total_return_and_drawdown() -> None:
    metrics = compute_metrics(_equity([100, 110, 105, 120]), [])
    assert metrics.total_return == pytest.approx(0.2)
    assert metrics.max_drawdown == pytest.approx(-5 / 110)


def test_trade_statistics() -> None:
    metrics = compute_metrics(_equity([100, 101]), [_trade(10), _trade(-5), _trade(15)])
    assert metrics.n_trades == 3
    assert metrics.profit_factor == pytest.approx(25 / 5)
    assert metrics.expectancy == pytest.approx(20 / 3)
    assert metrics.win_rate == pytest.approx(2 / 3)


def test_no_trades_and_no_losses() -> None:
    only_wins = compute_metrics(_equity([100, 101]), [_trade(5), _trade(3)])
    assert math.isinf(only_wins.profit_factor)
    empty = compute_metrics(_equity([100, 100]), [])
    assert empty.profit_factor == 0.0
    assert empty.expectancy == 0.0
    assert empty.n_trades == 0


def test_positive_sharpe_and_sortino_for_noisy_uptrend() -> None:
    metrics = compute_metrics(_equity([100, 101, 100.5, 102, 101.5, 103, 104]), [])
    assert metrics.sharpe > 0
    assert metrics.sortino > 0  # has downside days, so downside deviation is defined


def test_single_point_equity_is_safe() -> None:
    metrics = compute_metrics(_equity([100]), [])
    assert metrics.total_return == 0.0
    assert metrics.sharpe == 0.0
    assert metrics.cagr == 0.0
