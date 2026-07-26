"""§6 numeric ramp gate. The asymmetry is the point: five conditions to grow, none to shrink."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from libs.execution.ramp_gate import (
    SIZE_STEPS,
    may_step_up,
    next_step,
    step_down,
    step_up_conditions,
)

CLEAN = {
    "trailing_weeks": 8.0,
    "cost_ratio": 1.0,
    "live_sharpe": 1.0,
    "backtest_sharpe": 1.2,
    "slippage_ks_p": 0.4,
    "drill_pass_streak_weeks": 9,
    "calibration_mae_falling_months": 2,
}


class TestFailClosed:
    def test_empty_evidence_blocks_every_condition(self) -> None:
        """An evidence pipeline that breaks silently must not read as five satisfied
        conditions. Every default has to fail, so absence blocks."""
        assert not any(step_up_conditions({}).values())

    def test_a_clean_sheet_passes(self) -> None:
        assert may_step_up(CLEAN).may_step_up

    def test_junk_values_do_not_raise_and_do_not_pass(self) -> None:
        junk = dict.fromkeys(CLEAN, "banana")
        d = may_step_up(junk)
        assert not d.may_step_up

    def test_none_is_treated_as_missing_not_as_zero(self) -> None:
        assert not may_step_up({**CLEAN, "cost_ratio": None}).may_step_up


class TestEachConditionCanBlockAlone:
    def test_cost_over_budget_blocks(self) -> None:
        d = may_step_up({**CLEAN, "cost_ratio": 1.26})
        assert not d.may_step_up and d.failed == ["a_cost_le_1_25x"]

    def test_live_sharpe_short_of_the_backtest_blocks(self) -> None:
        d = may_step_up({**CLEAN, "live_sharpe": 0.5, "backtest_sharpe": 1.0})
        assert d.failed == ["b_live_sharpe_ge_0_6x_backtest"]

    def test_a_rejected_slippage_ks_blocks(self) -> None:
        d = may_step_up({**CLEAN, "slippage_ks_p": 0.049})
        assert d.failed == ["c_slippage_ks_p_gt_0_05"]

    def test_a_short_drill_streak_blocks(self) -> None:
        d = may_step_up({**CLEAN, "drill_pass_streak_weeks": 7})
        assert d.failed == ["d_drill_streak_ge_8w"]

    def test_mae_not_falling_long_enough_blocks(self) -> None:
        d = may_step_up({**CLEAN, "calibration_mae_falling_months": 1})
        assert d.failed == ["e_mae_falling_2_months"]

    def test_a_short_window_blocks(self) -> None:
        d = may_step_up({**CLEAN, "trailing_weeks": 7.9})
        assert d.failed == ["window_ge_8_weeks"]


class TestStepping:
    def test_a_clean_gate_climbs_exactly_one_rung(self) -> None:
        nxt, _ = next_step(SIZE_STEPS[0], CLEAN)
        assert nxt == SIZE_STEPS[1]

    def test_a_blocked_gate_holds(self) -> None:
        nxt, why = next_step(SIZE_STEPS[1], {})
        assert nxt == SIZE_STEPS[1] and "blocked by" in why

    def test_the_top_rung_does_not_overflow(self) -> None:
        nxt, why = next_step(SIZE_STEPS[-1], CLEAN)
        assert nxt == SIZE_STEPS[-1] and "top rung" in why

    def test_an_unrecognised_size_snaps_down_not_up(self) -> None:
        """An unknown state is not a licence to grow."""
        nxt, why = next_step(0.47, CLEAN)
        assert nxt == 0.35 and "snapped down" in why

    def test_a_size_below_every_rung_snaps_to_the_floor(self) -> None:
        nxt, _ = next_step(0.01, CLEAN)
        assert nxt == SIZE_STEPS[0]

    @given(cur=st.sampled_from(SIZE_STEPS))
    def test_stepping_up_never_skips_a_rung(self, cur: float) -> None:
        nxt, _ = next_step(cur, CLEAN)
        i, j = SIZE_STEPS.index(cur), SIZE_STEPS.index(nxt)
        assert j - i in (0, 1)


class TestDownStepsAreUnconditional:
    def test_a_down_step_needs_no_evidence(self) -> None:
        nxt, why = step_down(SIZE_STEPS[3], "canary failed")
        assert nxt == SIZE_STEPS[2] and "canary failed" in why

    def test_the_floor_down_step_reaches_zero(self) -> None:
        assert step_down(SIZE_STEPS[0], "tripwire")[0] == 0.0

    @given(cur=st.floats(0.0, 1.0))
    def test_a_down_step_never_increases_size(self, cur: float) -> None:
        assert step_down(cur, "any reason")[0] <= cur
