"""The crossing and the slot arithmetic must be trustworthy before the report's numbers are.

Every test here guards a property one of the reported conclusions rests on. The two that matter
most are PREFIX INVARIANCE -- a level above the crossing must never be able to move it, which is
the same rule the desk applies to every rolling statistic -- and NO-CROSSING HONESTY, because
reporting the top of a grid as the floor is how an unmeasured quantity gets written down as a
measured one.
"""

from __future__ import annotations

import math

import numpy as np

from libs.validation.admission_power import (
    POWER_TARGET,
    power_crossing,
    slot_occupancy_cost,
)


def test_crossing_interpolates_inside_the_first_bracket() -> None:
    c = power_crossing([1.0, 2.0, 3.0, 4.0], [0.0, 0.1, 0.4, 0.6])
    assert c.bracketed
    # 0.5 sits halfway between 0.4 at 3.0 and 0.6 at 4.0.
    assert math.isclose(c.sensitivity_floor, 3.5, rel_tol=1e-12)
    assert (c.bracket_lo, c.bracket_hi) == (3.0, 4.0)


def test_crossing_is_prefix_invariant() -> None:
    """LOAD-BEARING. Adding higher levels must not move a crossing that is already located.

    This is the reason the crossing is scanned upward rather than fitted: a logistic fit would let
    the 10.0 point decide where the 3.0 point sits, which is the same defect as a rolling
    statistic peeking at future data. Monte Carlo power curves are not monotone, so the guarantee
    has to be structural rather than assumed.
    """
    levels = [1.0, 2.0, 3.0, 4.0, 5.0, 7.0, 10.0]
    powers = [0.0, 0.05, 0.4, 0.6, 0.55, 0.9, 0.99]
    full = power_crossing(levels, powers).sensitivity_floor
    for k in range(4, len(levels) + 1):
        assert math.isclose(power_crossing(levels[:k], powers[:k]).sensitivity_floor, full,
                            rel_tol=1e-12)


def test_first_crossing_not_last() -> None:
    """A curve that dips back below target above the crossing is still read at the FIRST one."""
    c = power_crossing([1.0, 2.0, 3.0, 4.0], [0.2, 0.6, 0.3, 0.8])
    assert c.bracket_lo == 1.0 and c.bracket_hi == 2.0


def test_no_crossing_reports_infinity_and_says_so() -> None:
    c = power_crossing([1.0, 2.0, 5.0], [0.0, 0.1, 0.4])
    assert not c.bracketed
    assert math.isinf(c.sensitivity_floor)
    # It must NOT quietly return the top of the grid as the answer.
    assert c.sensitivity_floor != 5.0
    assert math.isclose(c.max_power_measured, 0.4)
    assert c.level_at_max_power == 5.0


def test_already_above_target_at_the_bottom_is_an_upper_bound() -> None:
    c = power_crossing([2.0, 3.0], [0.7, 0.9])
    assert c.bracketed and c.sensitivity_floor == 2.0
    assert "UPPER BOUND" in c.note


def test_flat_bracket_does_not_divide_by_dust() -> None:
    """A `> 0` denominator guard would extrapolate thousands of Sharpe units out of float dust."""
    tiny = POWER_TARGET + 1e-18
    c = power_crossing([1.0, 2.0], [POWER_TARGET - 1e-18, tiny])
    assert c.bracketed
    assert 1.0 <= c.sensitivity_floor <= 2.0


def test_unsorted_levels_are_sorted_before_scanning() -> None:
    a = power_crossing([4.0, 1.0, 3.0, 2.0], [0.6, 0.0, 0.4, 0.1])
    b = power_crossing([1.0, 2.0, 3.0, 4.0], [0.0, 0.1, 0.4, 0.6])
    assert math.isclose(a.sensitivity_floor, b.sensitivity_floor, rel_tol=1e-12)


def test_non_finite_and_empty_inputs_block() -> None:
    for c in (power_crossing([], []), power_crossing([1.0], [0.1, 0.2]),
              power_crossing([np.nan], [np.nan])):
        assert not c.bracketed and math.isinf(c.sensitivity_floor)


def test_slot_cost_negligible_bounded_and_saturated() -> None:
    neg = slot_occupancy_cost(1e-4, n_screened_nulls=4800, n_slots=12)
    assert not neg.saturated and neg.expected_false_admissions < 1.0
    assert "NEGLIGIBLE" in neg.verdict

    bound = slot_occupancy_cost(1e-3, n_screened_nulls=4800, n_slots=12)
    assert not bound.saturated and 1.0 <= bound.slots_wasted_per_campaign < 12.0
    assert "BOUNDED" in bound.verdict

    sat = slot_occupancy_cost(1e-2, n_screened_nulls=4800, n_slots=12)
    assert sat.saturated and sat.slots_wasted_per_campaign == 12.0
    assert "SATURATED" in sat.verdict


def test_slot_cost_never_wastes_more_slots_than_exist() -> None:
    c = slot_occupancy_cost(1.0, n_screened_nulls=10_000, n_slots=12)
    assert c.slots_wasted_per_campaign == 12.0
    assert math.isclose(c.fraction_of_slots_wasted, 1.0)


def test_slot_cost_blocks_on_an_unknown_rate() -> None:
    """UNMEASURED IS NOT PASSED: a NaN rate must not read as a safe one."""
    c = slot_occupancy_cost(float("nan"), n_screened_nulls=4800, n_slots=12)
    assert not c.saturated
    assert math.isnan(c.slots_wasted_per_campaign)
    assert "BLOCKED" in c.verdict


def test_zero_slots_is_its_own_state() -> None:
    c = slot_occupancy_cost(0.5, n_screened_nulls=100, n_slots=0)
    assert c.slots_wasted_per_campaign == 0.0
    assert "no forward slots exist" in c.verdict
