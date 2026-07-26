"""Boundary tests for the sizer -- written because mutation testing said nobody had.

`libs/risk/sizing.py` scored 73% on 2026-07-26 and the survivors were the guard comparisons:
`equity <= 0` mutated to `< 0` and no test noticed, same for `risk_per_unit`, the cost hurdle's
`edge_value <= cost`, and the `risk_amount <= 0` reject. Zero is the interesting value in every
one of them, and zero was exactly what nothing tested.
"""

from __future__ import annotations

import pytest

from libs.risk.errors import RiskError
from libs.risk.sizing import calculate_position_size

BASE = {"equity": 100_000.0, "risk_budget": 0.01, "kelly_fraction": 0.5,
        "risk_per_unit": 10.0, "side": "buy", "global_scalar": 1.0, "vol_scalar": 1.0}


class TestGuardBoundaries:
    @pytest.mark.parametrize("equity", [0.0, -1.0])
    def test_non_positive_equity_raises(self, equity: float) -> None:
        with pytest.raises(RiskError):
            calculate_position_size(**{**BASE, "equity": equity})

    def test_the_smallest_positive_equity_is_accepted(self) -> None:
        # pins the boundary as EXCLUSIVE of zero -- `<= 0` not `< 0`
        assert calculate_position_size(**{**BASE, "equity": 1e-9}).units >= 0.0

    @pytest.mark.parametrize("rpu", [0.0, -1.0])
    def test_non_positive_risk_per_unit_raises(self, rpu: float) -> None:
        with pytest.raises(RiskError):
            calculate_position_size(**{**BASE, "risk_per_unit": rpu})

    def test_an_unknown_side_raises(self) -> None:
        with pytest.raises(RiskError):
            calculate_position_size(**{**BASE, "side": "hold"})


class TestCostHurdleBoundary:
    @pytest.mark.parametrize("edge,cost,rejected", [
        (9.0, 10.0, True),     # below cost
        (10.0, 10.0, True),    # EXACTLY cost -- rejected, the boundary is inclusive
        (10.01, 10.0, False),  # clears cost
    ])
    def test_edge_equal_to_cost_is_rejected(
        self, edge: float, cost: float, rejected: bool
    ) -> None:
        r = calculate_position_size(**{**BASE, "edge_value": edge, "cost": cost})
        assert r.rejected is rejected
        if rejected:
            assert r.binding_constraint == "cost_hurdle" and r.units == 0.0

    def test_the_hurdle_needs_both_halves_to_apply(self) -> None:
        """Only one of edge_value/cost present must NOT silently reject or silently pass --
        it must skip the hurdle entirely."""
        assert not calculate_position_size(**{**BASE, "edge_value": 1.0}).rejected
        assert not calculate_position_size(**{**BASE, "cost": 1e9}).rejected


class TestZeroBudgetBoundary:
    def test_a_zero_cap_rejects_rather_than_sizing_zero_units(self) -> None:
        r = calculate_position_size(**{**BASE, "max_position_amount": 0.0})
        assert r.rejected and r.units == 0.0 and r.binding_constraint == "position_cap"

    def test_a_negative_cap_is_floored_to_zero_and_rejects(self) -> None:
        r = calculate_position_size(**{**BASE, "factor_headroom": -500.0})
        assert r.rejected and r.risk_amount == 0.0

    def test_the_smallest_positive_budget_still_sizes(self) -> None:
        r = calculate_position_size(**{**BASE, "heat_headroom": 1e-6})
        assert not r.rejected and r.units > 0.0

    def test_a_zero_global_scalar_rejects(self) -> None:
        assert calculate_position_size(**{**BASE, "global_scalar": 0.0}).rejected


class TestSignAndBinding:
    def test_a_sell_is_negative_and_a_buy_is_positive(self) -> None:
        assert calculate_position_size(**BASE).units > 0
        assert calculate_position_size(**{**BASE, "side": "sell"}).units < 0

    def test_the_tightest_cap_binds_and_is_named(self) -> None:
        r = calculate_position_size(**{**BASE, "max_position_amount": 50.0,
                                       "factor_headroom": 10.0, "heat_headroom": 500.0})
        assert r.binding_constraint == "factor_cap" and r.risk_amount == 10.0

    def test_units_are_risk_amount_over_risk_per_unit(self) -> None:
        r = calculate_position_size(**{**BASE, "max_position_amount": 100.0})
        assert abs(r.units - 10.0) < 1e-9
