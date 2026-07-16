"""Drawdown allocator, risk budget, sleeves, leverage, reinvestment."""

from __future__ import annotations

import pytest

from libs.stage14.allocation import (
    AdaptiveReinvestmentEngine,
    DrawdownAwareAllocator,
    DynamicLeverageEngine,
    PortfolioRiskBudgetEngine,
    SleeveAllocator,
    group_by_sleeve,
)
from libs.stage14.errors import Stage14Error
from libs.stage14.models import AlphaSleeve, PortfolioState


def test_drawdown_allocator_caps_until_recovered() -> None:
    alloc = DrawdownAwareAllocator()
    assert alloc.scale(current_drawdown=0.0) == 1.0
    drawn = alloc.scale(current_drawdown=0.10, recovered=False)
    recovered = alloc.scale(current_drawdown=0.10, recovered=True)
    assert drawn <= 0.5  # restoration capped while still drawn down
    assert recovered >= drawn
    assert alloc.scale(current_drawdown=0.10, recovered=False, regime_stable=False) <= drawn


def test_risk_budget_inverse_vol() -> None:
    eng = PortfolioRiskBudgetEngine()
    weights = eng.inverse_vol_weights({"A": 0.1, "B": 0.2})
    assert weights["A"] > weights["B"]  # lower vol -> more risk weight
    assert sum(weights.values()) == pytest.approx(1.0)
    assert eng.inverse_vol_weights({"A": 0.0, "B": 0.0}) == {"A": 0.0, "B": 0.0}


def test_risk_budget_capital_from_risk_caps_at_one() -> None:
    from libs.stage14.models import RiskBudget

    eng = PortfolioRiskBudgetEngine()
    rw = eng.inverse_vol_weights({"A": 0.1, "B": 0.1})
    capital = eng.capital_from_risk(rw, {"A": 0.1, "B": 0.1}, budget=RiskBudget(vol_budget=0.15))
    assert sum(capital.values()) <= 1.0 + 1e-9
    # zero vol -> zero capital (no divide-by-zero)
    assert eng.capital_from_risk({"A": 1.0}, {"A": 0.0}, budget=RiskBudget())["A"] == 0.0


def test_drawdown_allocator_signal_deterioration() -> None:
    alloc = DrawdownAwareAllocator()
    base = alloc.scale(current_drawdown=0.02)
    worse = alloc.scale(current_drawdown=0.02, signal_deteriorating=True)
    assert worse < base


def test_sleeve_of_maps_text() -> None:
    assert AdaptiveReinvestmentEngine.sleeve_of("momentum") is AlphaSleeve.MOMENTUM
    assert AdaptiveReinvestmentEngine.sleeve_of("nonexistent") is AlphaSleeve.OTHER


def test_sleeve_allocator_caps_and_normalizes() -> None:
    alloc = SleeveAllocator(max_sleeve_weight=0.4)
    budgets = alloc.budgets({
        AlphaSleeve.TREND: 10.0, AlphaSleeve.MOMENTUM: 1.0, AlphaSleeve.CARRY: 1.0,
    })
    assert max(budgets.values()) <= 0.4 + 1e-9
    assert sum(budgets.values()) == pytest.approx(1.0)


def test_sleeve_allocator_equal_when_no_score() -> None:
    budgets = SleeveAllocator().budgets({AlphaSleeve.TREND: 0.0, AlphaSleeve.CARRY: 0.0})
    assert budgets[AlphaSleeve.TREND] == pytest.approx(0.5)


def test_dynamic_leverage_scales_with_health() -> None:
    eng = DynamicLeverageEngine(max_leverage=2.0)
    healthy = eng.decide(volatility_state=0.0, regime_certainty=1.0, survival_score=100.0)
    stressed = eng.decide(volatility_state=0.9, regime_certainty=0.2, survival_score=40.0)
    assert healthy.leverage > stressed.leverage
    assert 0.0 <= stressed.leverage <= 2.0
    with pytest.raises(Stage14Error):
        DynamicLeverageEngine(max_leverage=0.0)


def test_adaptive_reinvestment_state_caps() -> None:
    eng = AdaptiveReinvestmentEngine()
    normal = eng.decide(growth_score=90.0, survival_score=95.0, state=PortfolioState.NORMAL)
    crisis = eng.decide(growth_score=90.0, survival_score=95.0, state=PortfolioState.CRISIS)
    assert normal.reinvestment_rate > 0
    assert crisis.reinvestment_rate == 0.0  # no reinvestment in crisis


def test_group_by_sleeve() -> None:
    grouped = group_by_sleeve([("A", AlphaSleeve.TREND), ("B", AlphaSleeve.TREND),
                               ("C", AlphaSleeve.CARRY)])
    assert grouped[AlphaSleeve.TREND] == ["A", "B"]
    assert grouped[AlphaSleeve.CARRY] == ["C"]
