"""Tests for cost stress scenarios."""

from __future__ import annotations

import pytest

from libs.costs.model import apply_stress_costs, estimate_trade_cost
from libs.costs.scenarios import CostScenario


@pytest.mark.parametrize(
    ("scenario", "multiplier"),
    [
        (CostScenario.BASE, 1.0),
        (CostScenario.X2, 2.0),
        (CostScenario.X3, 3.0),
        (CostScenario.X5, 5.0),
    ],
)
def test_multipliers(scenario: CostScenario, multiplier: float) -> None:
    assert scenario.multiplier == multiplier


def test_stress_scales_market_components_only() -> None:
    base = estimate_trade_cost("XAUUSD", 1.0, price=2000.0, side="buy", holding_nights=2)
    # base: spread 12, commission 7, slippage 6, financing 10, gap 0 -> total 35
    stressed = apply_stress_costs(base, CostScenario.X3)
    assert stressed.spread == pytest.approx(36.0)        # 12 * 3
    assert stressed.slippage == pytest.approx(18.0)      # 6 * 3
    assert stressed.commission == pytest.approx(7.0)     # fixed
    assert stressed.financing == pytest.approx(10.0)     # fixed
    assert stressed.total == pytest.approx(36.0 + 7.0 + 18.0 + 10.0)


def test_stress_base_is_identity() -> None:
    base = estimate_trade_cost("EURUSD", 1.0, price=1.1)
    stressed = apply_stress_costs(base, CostScenario.BASE)
    assert stressed.total == pytest.approx(base.total)


def test_stress_scales_gap() -> None:
    base = estimate_trade_cost("XAUUSD", 1.0, price=2000.0, include_gap=True)
    stressed = apply_stress_costs(base, CostScenario.X5)
    assert stressed.gap == pytest.approx(base.gap * 5)
