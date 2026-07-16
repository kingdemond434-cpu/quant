"""Tests for the Fusion cost model."""

from __future__ import annotations

import pytest

from libs.costs.errors import CostError
from libs.costs.model import (
    TradeSpec,
    estimate_portfolio_cost,
    estimate_trade_cost,
    net_pnl,
)


def test_eurusd_components() -> None:
    cost = estimate_trade_cost("EURUSD", 1.0, price=1.10)
    assert cost.spread == pytest.approx(2.0)       # 0.00002 * 100_000
    assert cost.commission == pytest.approx(7.0)
    assert cost.slippage == pytest.approx(2.0)     # 0.00001 * 100_000 * 2
    assert cost.financing == 0.0
    assert cost.gap == 0.0
    assert cost.total == pytest.approx(11.0)


def test_gold_round_turn_matches_hurdle() -> None:
    cost = estimate_trade_cost("XAUUSD", 1.0, price=2000.0)
    assert cost.total == pytest.approx(25.0)       # 12 spread + 7 commission + 6 slippage
    per_oz = cost.total / 100.0                     # contract size 100 oz
    assert 0.2 <= per_oz <= 0.4                     # ~ $0.25-0.35/oz hurdle


def test_financing_scales_with_nights() -> None:
    cost = estimate_trade_cost("XAUUSD", 1.0, price=2000.0, side="buy", holding_nights=3)
    assert cost.financing == pytest.approx(15.0)   # 5 * 1 * 3
    assert cost.total == pytest.approx(40.0)


def test_short_uses_short_swap() -> None:
    long_cost = estimate_trade_cost("XAUUSD", 1.0, price=2000.0, side="buy", holding_nights=2)
    short_cost = estimate_trade_cost("XAUUSD", 1.0, price=2000.0, side="sell", holding_nights=2)
    assert long_cost.financing == pytest.approx(10.0)   # 5 * 2
    assert short_cost.financing == pytest.approx(8.0)   # 4 * 2


def test_include_gap_adds_gap_component() -> None:
    cost = estimate_trade_cost("XAUUSD", 1.0, price=2000.0, include_gap=True)
    assert cost.gap == pytest.approx(2000.0)       # 0.01 * 2000 * 100 * 1
    assert cost.total == pytest.approx(2025.0)


def test_quantity_scales_cost() -> None:
    one = estimate_trade_cost("EURUSD", 1.0, price=1.1)
    two = estimate_trade_cost("EURUSD", 2.0, price=1.1)
    assert two.total == pytest.approx(2 * one.total)


def test_invalid_inputs_raise() -> None:
    with pytest.raises(CostError):
        estimate_trade_cost("EURUSD", 0.0, price=1.1)
    with pytest.raises(CostError):
        estimate_trade_cost("EURUSD", 1.0, price=0.0)
    with pytest.raises(CostError):
        estimate_trade_cost("UNKNOWN", 1.0, price=1.0)


def test_portfolio_cost_aggregates() -> None:
    trades = [
        TradeSpec(instrument="EURUSD", qty_lots=1.0, price=1.1),
        TradeSpec(instrument="XAUUSD", qty_lots=1.0, price=2000.0),
        TradeSpec(instrument="EURUSD", qty_lots=1.0, price=1.1),
    ]
    portfolio = estimate_portfolio_cost(trades)
    assert portfolio.n_trades == 3
    assert portfolio.total == pytest.approx(11.0 + 25.0 + 11.0)
    assert portfolio.by_instrument["EURUSD"] == pytest.approx(22.0)
    assert portfolio.by_instrument["XAUUSD"] == pytest.approx(25.0)


def test_net_pnl_subtracts_cost() -> None:
    cost = estimate_trade_cost("XAUUSD", 1.0, price=2000.0)
    assert net_pnl(100.0, cost) == pytest.approx(75.0)
