"""Calibrating the cost model from MT5 symbol_info (committee item T1)."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from libs.costs.mt5_calibration import (
    calibrate,
    per_side_cost_fraction,
    round_turn_cost_fraction,
)
from libs.data.instruments import AssetClass


@dataclass
class FakeInfo:
    spread: int
    point: float
    trade_contract_size: float
    swap_long: float
    swap_short: float
    swap_mode: int


def _eurusd() -> FakeInfo:
    # FusionMarkets-Demo EURUSD snapshot: 6 points, 1e-5 point, 100k contract, swap in money.
    return FakeInfo(spread=6, point=1e-5, trade_contract_size=100_000.0,
                    swap_long=-6.55, swap_short=2.76, swap_mode=1)


def test_calibrate_uses_real_spread_and_contract() -> None:
    p = calibrate("EURUSD", _eurusd(), asset_class=AssetClass.FX)
    assert p.spread_price == pytest.approx(6e-5)            # spread points x point
    assert p.contract_size == 100_000.0
    assert p.commission_per_lot == 7.0                      # FX asset-class prior
    assert p.slippage_price_per_side == pytest.approx(3e-5)  # 0.5 x spread


def test_swap_sign_flips_to_cost() -> None:
    # MT5 swap_long negative = a charge to hold long -> stored as a positive cost.
    p = calibrate("EURUSD", _eurusd(), asset_class=AssetClass.FX)
    assert p.swap_long_per_lot_per_night == pytest.approx(6.55)
    assert p.swap_short_per_lot_per_night == pytest.approx(-2.76)


def test_round_turn_fraction_real_eurusd() -> None:
    # Honest number: EURUSD round turn ~1.66 bps (0.83 bps/side) -- BELOW the lab's flat 3 bps/side,
    # i.e. the flat assumption was conservative for majors (and far too cheap for wide spreads).
    p = calibrate("EURUSD", _eurusd(), asset_class=AssetClass.FX)
    rt = round_turn_cost_fraction(p, price=1.1468)
    assert rt == pytest.approx(1.657e-4, rel=0.02)         # ~1.66 bps round turn
    assert per_side_cost_fraction(p, 1.1468) == pytest.approx(rt / 2.0)


def test_per_symbol_cost_differentiates() -> None:
    # The value of T1: cost is per-symbol, not flat. A wide-spread instrument costs more to trade.
    eur = calibrate("EURUSD", _eurusd(), asset_class=AssetClass.FX)
    gold_info = FakeInfo(spread=20, point=0.01, trade_contract_size=100.0,
                         swap_long=-5.0, swap_short=-4.0, swap_mode=1)
    gold = calibrate("XAUUSD", gold_info, asset_class=AssetClass.METAL)
    assert round_turn_cost_fraction(gold, 2300.0) > round_turn_cost_fraction(eur, 1.1468)


def test_points_mode_swap_converts_to_money() -> None:
    info = FakeInfo(spread=30, point=0.01, trade_contract_size=1.0,
                    swap_long=-12.0, swap_short=-8.0, swap_mode=0)  # points mode
    p = calibrate("US500", info, asset_class=AssetClass.INDEX)
    assert p.commission_per_lot == 0.0                      # index = spread-only prior
    # money = -swap * point * contract_size
    assert p.swap_long_per_lot_per_night == pytest.approx(12.0 * 0.01 * 1.0)


def test_zero_price_rejected() -> None:
    from libs.costs.errors import CostError
    p = calibrate("EURUSD", _eurusd(), asset_class=AssetClass.FX)
    with pytest.raises(CostError):
        round_turn_cost_fraction(p, price=0.0)
