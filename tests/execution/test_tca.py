"""Post-trade TCA and slippage attribution."""

from __future__ import annotations

import pytest

from libs.costs.model import TradeCost
from libs.execution.errors import ExecutionError
from libs.execution.tca import PostTradeTCA, SlippageAttribution


def test_buy_slippage_is_adverse_when_filling_above_arrival() -> None:
    tca = PostTradeTCA().analyze(
        symbol="XAUUSD", side="buy", arrival_price=2000.0, decision_price=1999.0,
        fills=[(2002.0, 1.0), (2004.0, 1.0)], forecast_cost=4.0,
    )
    assert tca.avg_fill_price == 2003.0
    assert tca.slippage_bps > 0  # paid up -> adverse
    assert tca.implementation_shortfall > 0
    assert tca.realized_cost == pytest.approx((2003.0 - 2000.0) * 2.0)
    assert tca.cost_error == pytest.approx(tca.realized_cost - 4.0)


def test_sell_slippage_sign() -> None:
    tca = PostTradeTCA().analyze(
        symbol="EURUSD", side="sell", arrival_price=1.1000, decision_price=1.1000,
        fills=[(1.0990, 2.0)],
    )
    assert tca.slippage_bps > 0  # received less than arrival -> adverse for a sell


def test_favorable_fill_is_negative_slippage() -> None:
    tca = PostTradeTCA().analyze(
        symbol="XAUUSD", side="buy", arrival_price=2000.0, decision_price=2000.0,
        fills=[(1998.0, 1.0)],
    )
    assert tca.slippage_bps < 0  # filled cheaper than arrival


def test_tca_rejects_bad_inputs() -> None:
    tca = PostTradeTCA()
    with pytest.raises(ExecutionError):
        tca.analyze(symbol="X", side="hold", arrival_price=1.0, decision_price=1.0,
                    fills=[(1.0, 1.0)])
    with pytest.raises(ExecutionError):
        tca.analyze(symbol="X", side="buy", arrival_price=1.0, decision_price=1.0, fills=[])


def test_slippage_attribution_partitions_cost() -> None:
    tca = PostTradeTCA().analyze(
        symbol="XAUUSD", side="buy", arrival_price=2000.0, decision_price=2000.0,
        fills=[(2003.0, 1.0)],
    )  # realized_cost = 3.0
    forecast = TradeCost(instrument="XAUUSD", qty_lots=1.0, spread=1.0, commission=0.0,
                         slippage=1.0, financing=0.0, gap=0.0, total=2.0)
    parts = SlippageAttribution().attribute(tca, forecast)
    assert parts == {"spread": 1.0, "impact": 1.0, "timing": 1.0}
    assert sum(parts.values()) == pytest.approx(tca.realized_cost)
