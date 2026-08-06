"""SIZE STEPS UP ON ARITHMETIC, NEVER ON CONFIDENCE -- 49 statements on the sizing path, untested.

The spec's wording is "no discretionary language", and that is the whole design constraint. This
gate decides how much capital a strategy is allowed, so the assertions here are about the two
properties that make it trustworthy rather than about the five thresholds themselves:

  FAIL-CLOSED ON MISSING EVIDENCE. Every condition reads its input with a default that FAILS. An
  evidence pipeline that breaks silently must not read as five satisfied conditions -- which is
  precisely what a `dict.get(key, 0.0)` written the natural way would produce for the KS p-value
  and the drill streak. Each of the five is therefore tested with the key ABSENT, individually, so
  a future default flipped in the wrong direction cannot hide behind the other four.

  THE ASYMMETRY IS DELIBERATE. Up-steps are one rung at a time and require all five; down-steps are
  unlimited, immediate, never gated and never refused. The cost of an unnecessary down-step is a
  little foregone return; the cost of a delayed one is the book.

The third property is the one that looks like a detail and is not: an UNRECOGNISED size snaps DOWN,
and a size below the floor rung snaps to the floor WITHOUT also consuming a step. Otherwise a
hand-edited state file or a partial write becomes a licence to grow.
"""

from __future__ import annotations

import pytest

from libs.execution import ramp_gate as RG

#: Evidence that satisfies all five conditions with room to spare.
_CLEAN = {
    "trailing_weeks": 8.0,
    "cost_ratio": 1.0,
    "live_sharpe": 1.0,
    "backtest_sharpe": 1.0,
    "slippage_ks_p": 0.5,
    "drill_pass_streak_weeks": 10,
    "calibration_mae_falling_months": 3,
}


def _evidence(**over) -> dict:
    return {**_CLEAN, **over}


# ------------------------------------------------------------------ fail-closed

def test_EMPTY_evidence_satisfies_NOTHING() -> None:
    """The headline property. A broken evidence pipeline must block the step-up, not wave it
    through -- and 'no data' is exactly what a broken pipeline produces."""
    d = RG.may_step_up({})
    assert d.may_step_up is False
    assert d.failed == sorted(d.checks), "every single condition must fail on no evidence"


@pytest.mark.parametrize("key", sorted(_CLEAN))
def test_REMOVING_ANY_SINGLE_INPUT_blocks_the_step_up(key: str) -> None:
    """Tested one key at a time so a default flipped in the permissive direction cannot hide
    behind the other four failing anyway."""
    ev = _evidence()
    del ev[key]
    assert RG.may_step_up(ev).may_step_up is False, f"a missing {key!r} did not block the ramp"


@pytest.mark.parametrize("key", sorted(_CLEAN))
def test_an_UNPARSEABLE_input_blocks_the_step_up(key: str) -> None:
    """A metric that arrives as an error string, a None or a dict is not evidence. `_f` must never
    raise and must never coerce junk into a passing number."""
    for junk in ("n/a", None, {}, [], float("nan")):
        assert RG.may_step_up(_evidence(**{key: junk})).may_step_up is False, (key, junk)


def test_the_reader_never_raises_and_defaults_to_the_failing_value() -> None:
    assert RG._f({}, "missing", 999.0) == 999.0
    assert RG._f({"x": None}, "x", -1.0) == -1.0
    assert RG._f({"x": "junk"}, "x", 7.0) == 7.0
    assert RG._f({"x": "1.5"}, "x", 0.0) == 1.5


# ------------------------------------------------------------------ the five conditions

def test_clean_evidence_passes_all_five() -> None:
    """The positive control: a gate that never opens is not a gate, and 'blocked' from it would
    carry no information."""
    d = RG.may_step_up(_CLEAN)
    assert d.may_step_up is True and d.failed == []
    assert d.reason == "all ramp conditions met"


@pytest.mark.parametrize(("over", "expect_failed"), [
    ({"trailing_weeks": 7.9}, "window_ge_8_weeks"),
    ({"cost_ratio": 1.26}, "a_cost_le_1_25x"),
    ({"live_sharpe": 0.59, "backtest_sharpe": 1.0}, "b_live_sharpe_ge_0_6x_backtest"),
    ({"slippage_ks_p": 0.05}, "c_slippage_ks_p_gt_0_05"),
    ({"drill_pass_streak_weeks": 7}, "d_drill_streak_ge_8w"),
    ({"calibration_mae_falling_months": 1}, "e_mae_falling_2_months"),
])
def test_each_condition_blocks_on_its_own_and_NAMES_ITSELF(over, expect_failed) -> None:
    """A gate that says 'blocked' without saying which condition gets argued with rather than
    fixed."""
    d = RG.may_step_up(_evidence(**over))
    assert d.may_step_up is False
    assert d.failed == [expect_failed]
    assert expect_failed in d.reason


@pytest.mark.parametrize(("over", "name"), [
    ({"trailing_weeks": 8.0}, "window_ge_8_weeks"),
    ({"cost_ratio": 1.25}, "a_cost_le_1_25x"),
    ({"live_sharpe": 0.6, "backtest_sharpe": 1.0}, "b_live_sharpe_ge_0_6x_backtest"),
    ({"drill_pass_streak_weeks": 8}, "d_drill_streak_ge_8w"),
    ({"calibration_mae_falling_months": 2}, "e_mae_falling_2_months"),
])
def test_the_boundary_itself_PASSES_for_the_inclusive_conditions(over, name) -> None:
    assert RG.step_up_conditions(_evidence(**over))[name] is True


def test_the_KS_boundary_is_EXCLUSIVE_because_p_equal_0_05_is_a_rejection() -> None:
    """`p > 0.05`, not `>=`. At exactly the threshold the slippage distribution has failed to
    match the model, and rounding that into a pass is how a cost assumption drifts."""
    assert RG.step_up_conditions(_evidence(slippage_ks_p=0.05))["c_slippage_ks_p_gt_0_05"] is False
    assert RG.step_up_conditions(
        _evidence(slippage_ks_p=0.0501))["c_slippage_ks_p_gt_0_05"] is True


def test_the_sharpe_condition_is_RELATIVE_to_the_same_period_backtest() -> None:
    """An absolute Sharpe bar would pass a strategy that halved against its own backtest in a good
    market, and fail one holding 90% of its backtest in a bad one."""
    assert RG.step_up_conditions(
        _evidence(live_sharpe=0.5, backtest_sharpe=0.8))["b_live_sharpe_ge_0_6x_backtest"] is True
    assert RG.step_up_conditions(
        _evidence(live_sharpe=1.5, backtest_sharpe=3.0))["b_live_sharpe_ge_0_6x_backtest"] is False


def test_a_missing_backtest_sharpe_makes_the_bar_UNREACHABLE_rather_than_free() -> None:
    """It defaults to 999, so 0.6x it cannot be cleared. Defaulting it to 0 would make the
    condition free for exactly the strategy that never recorded a backtest."""
    ev = _evidence(live_sharpe=99.0)
    del ev["backtest_sharpe"]
    assert RG.step_up_conditions(ev)["b_live_sharpe_ge_0_6x_backtest"] is False


# ------------------------------------------------------------------ the ladder

def test_the_ladder_is_enumerated_and_monotone() -> None:
    """Steps are a LOOKUP, never an expression somebody can re-derive differently in another file
    -- which is how five disagreeing copies of a policy appear."""
    assert list(RG.SIZE_STEPS) == sorted(RG.SIZE_STEPS)
    assert len(set(RG.SIZE_STEPS)) == len(RG.SIZE_STEPS)
    assert RG.SIZE_STEPS[-1] == 1.0
    assert RG.SIZE_STEPS[0] > 0.0


def test_a_clean_gate_moves_exactly_ONE_rung() -> None:
    """One rung at a time is the point: eight weeks of evidence buys one step, not the ladder."""
    for i, rung in enumerate(RG.SIZE_STEPS[:-1]):
        size, why = RG.next_step(rung, _CLEAN)
        assert size == RG.SIZE_STEPS[i + 1]
        assert "one rung up" in why


def test_a_blocked_gate_HOLDS_the_current_rung_and_says_why() -> None:
    size, why = RG.next_step(RG.SIZE_STEPS[1], _evidence(cost_ratio=5.0))
    assert size == RG.SIZE_STEPS[1]
    assert "a_cost_le_1_25x" in why


def test_the_top_rung_does_not_step_past_full_size() -> None:
    size, why = RG.next_step(1.0, _CLEAN)
    assert size == 1.0 and "already at the top rung" in why


def test_an_UNRECOGNISED_size_snaps_DOWN_because_an_unknown_state_is_not_a_licence_to_grow(
) -> None:
    size, why = RG.next_step(0.47, _CLEAN)      # between 0.35 and 0.55
    assert size == 0.35
    assert "snapped down" in why


def test_a_size_BELOW_THE_FLOOR_snaps_to_the_floor_without_ALSO_consuming_a_rung() -> None:
    """Snapping to the floor is already a step UP in absolute terms. Letting it also take a rung is
    what would turn 0.01 into 0.20 in a single tick -- from a partial write or a hand-edited file.
    """
    size, why = RG.next_step(0.01, _CLEAN)
    assert size == RG.SIZE_STEPS[0]
    assert "no step this tick" in why


def test_zero_and_negative_sizes_snap_to_the_floor_too() -> None:
    for start in (0.0, -1.0):
        assert RG.next_step(start, _CLEAN)[0] == RG.SIZE_STEPS[0]


def test_a_size_exactly_ON_a_rung_is_not_treated_as_unrecognised() -> None:
    """Float comparison with no tolerance would call 0.35 unrecognised on some paths and snap a
    perfectly valid state down a rung every tick."""
    for rung in RG.SIZE_STEPS:
        size, why = RG.next_step(rung, _evidence(cost_ratio=99.0))
        assert size == rung and "snapped down" not in why


# ------------------------------------------------------------------ down-steps

def test_a_down_step_is_NEVER_gated_by_the_evidence() -> None:
    """The asymmetry is the whole risk stance. `step_down` takes no evidence argument at all --
    there is no signature by which it could be refused."""
    for rung in RG.SIZE_STEPS[1:]:
        size, why = RG.step_down(rung, "drill failed")
        assert size < rung
        assert "drill failed" in why


def test_a_down_step_from_the_floor_goes_to_ZERO_not_to_the_floor() -> None:
    """There is always a rung below: flat. A floor that could not be left would keep the desk in
    the market through exactly the event the down-step was for."""
    size, _ = RG.step_down(RG.SIZE_STEPS[0], "ruin rail")
    assert size == 0.0


def test_a_down_step_from_an_unrecognised_size_lands_on_a_real_rung() -> None:
    assert RG.step_down(0.47, "why")[0] == 0.35
    assert RG.step_down(0.0, "why")[0] == 0.0


def test_the_reason_is_always_carried_onto_the_down_step() -> None:
    """A size reduction with no recorded cause is one nobody can reverse with confidence later."""
    _, why = RG.step_down(0.55, "KS test failed on 2026-08-06")
    assert "KS test failed on 2026-08-06" in why


def test_down_steps_are_UNLIMITED_and_can_walk_the_whole_ladder_in_one_session() -> None:
    """Immediate and unrate-limited. A rate limit here would be a delayed down-step, and the cost
    of a delayed one is the book."""
    size = RG.SIZE_STEPS[-1]
    for _ in range(len(RG.SIZE_STEPS) + 1):
        size, _ = RG.step_down(size, "cascade")
    assert size == 0.0
