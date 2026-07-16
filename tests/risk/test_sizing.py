"""Position-size synthesis tests (caps bind; cost hurdle rejects)."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from libs.risk.errors import RiskError
from libs.risk.sizing import calculate_position_size


def test_base_formula() -> None:
    result = calculate_position_size(
        100_000.0, kelly_fraction=0.25, vol_scalar=1.0, risk_budget=0.5,
        global_scalar=1.0, risk_per_unit=10.0,
    )
    assert result.risk_amount == pytest.approx(12_500.0)  # 100k * 0.5 * 0.25
    assert result.units == pytest.approx(1250.0)
    assert result.binding_constraint == "target"


def test_position_cap_binds() -> None:
    result = calculate_position_size(
        100_000.0, kelly_fraction=0.5, vol_scalar=1.0, risk_budget=1.0,
        global_scalar=1.0, risk_per_unit=10.0, max_position_amount=25_000.0,
    )
    assert result.risk_amount == pytest.approx(25_000.0)
    assert result.binding_constraint == "position_cap"


def test_cost_hurdle_rejects() -> None:
    result = calculate_position_size(
        100_000.0, kelly_fraction=0.25, vol_scalar=1.0, risk_budget=0.5,
        global_scalar=1.0, risk_per_unit=10.0, edge_value=1.0, cost=2.0,
    )
    assert result.rejected
    assert result.binding_constraint == "cost_hurdle"


def test_sell_side_negative_units() -> None:
    result = calculate_position_size(
        100_000.0, kelly_fraction=0.25, vol_scalar=1.0, risk_budget=0.5,
        global_scalar=1.0, risk_per_unit=10.0, side="sell",
    )
    assert result.units < 0


def test_no_headroom_rejects() -> None:
    result = calculate_position_size(
        100_000.0, kelly_fraction=0.25, vol_scalar=1.0, risk_budget=0.5,
        global_scalar=1.0, risk_per_unit=10.0, factor_headroom=0.0,
    )
    assert result.rejected


def test_invalid_inputs() -> None:
    with pytest.raises(RiskError):
        calculate_position_size(
            0.0, kelly_fraction=0.25, vol_scalar=1.0, risk_budget=0.5,
            global_scalar=1.0, risk_per_unit=10.0,
        )
    with pytest.raises(RiskError):
        calculate_position_size(
            100_000.0, kelly_fraction=0.25, vol_scalar=1.0, risk_budget=0.5,
            global_scalar=1.0, risk_per_unit=0.0,
        )


@given(
    kelly=st.floats(min_value=0.0, max_value=0.5),
    vol=st.floats(min_value=0.1, max_value=3.0),
    budget=st.floats(min_value=0.0, max_value=1.0),
    scalar=st.floats(min_value=0.0, max_value=1.0),
    rpu=st.floats(min_value=1.0, max_value=1000.0),
    pos_cap=st.floats(min_value=0.0, max_value=50_000.0),
    factor=st.floats(min_value=0.0, max_value=50_000.0),
    heat=st.floats(min_value=0.0, max_value=50_000.0),
)
def test_sizing_never_exceeds_caps(
    kelly: float, vol: float, budget: float, scalar: float, rpu: float,
    pos_cap: float, factor: float, heat: float,
) -> None:
    result = calculate_position_size(
        100_000.0, kelly_fraction=kelly, vol_scalar=vol, risk_budget=budget,
        global_scalar=scalar, risk_per_unit=rpu,
        max_position_amount=pos_cap, factor_headroom=factor, heat_headroom=heat,
    )
    # risk amount never exceeds any configured cap
    assert result.risk_amount <= pos_cap + 1e-6
    assert result.risk_amount <= factor + 1e-6
    assert result.risk_amount <= heat + 1e-6
    # nor the target risk
    target = 100_000.0 * scalar * budget * kelly * vol
    assert result.risk_amount <= target + 1e-6
