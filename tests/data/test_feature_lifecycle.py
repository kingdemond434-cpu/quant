"""The feature lifecycle: every transition rule, and the effort ruling that makes it bite.

    python -m pytest tests/data/test_feature_lifecycle.py -q

WHAT MUST NOT REGRESS:

  1. the states and the legal edges are exactly the ones the module documents, and `transition`
     never emits an edge the table does not name
  2. a feature is promoted BY ITS CONSUMER: a gauntlet cell -> USEFUL, an admitted state
     dimension -> STATE_ONLY, the execution layer -> EXECUTION_ONLY
  3. REDUNDANT binds at the STATED bounds (|corr| >= 0.95, R^2 >= 0.90) and not below them
  4. DECAYING binds at K falling windows and not at K-1
  5. NOTHING DIES BELOW MIN_N -- an unmeasured feature is UNMEASURED, not worthless
  6. DEAD is a one-way door: only a NAMED revival condition WITH a positive measurement opens it
  7. `withdraw` refuses compute for DEAD and REDUNDANT, allows it everywhere else, and reads an
     unknown status as NEW rather than as condemned
"""
from __future__ import annotations

import pytest

from libs.data import feature_lifecycle as lc

USEFUL_EV = lc.Evidence(consumers=frozenset({lc.CONSUMER_GAUNTLET}))


# ------------------------------------------------- 1. the shape of the machine

def test_the_eight_states_are_the_documented_ones() -> None:
    assert set(lc.STATES) == {"NEW", "USEFUL", "STATE_ONLY", "EXECUTION_ONLY", "REDUNDANT",
                              "DECAYING", "DEAD", "REVIVED"}
    assert set(lc.ALLOWED) == set(lc.STATES), "every state needs a row in the edge table"
    for src, targets in lc.ALLOWED.items():
        assert src in targets, f"{src} must be allowed to stay where it is"
        assert targets <= set(lc.STATES), f"{src} points at a state that does not exist"


def test_dead_leaves_only_through_revived() -> None:
    """A feature the desk stopped paying for must not drift back to useful unannounced."""
    assert lc.ALLOWED[lc.DEAD] == frozenset({lc.DEAD, lc.REVIVED})


@pytest.mark.parametrize("start", lc.STATES)
@pytest.mark.parametrize("ev", [
    lc.Evidence(),
    USEFUL_EV,
    lc.Evidence(consumers=frozenset({lc.CONSUMER_STATE})),
    lc.Evidence(consumers=frozenset({lc.CONSUMER_EXECUTION})),
    lc.Evidence(roi=-1.0, n=lc.MIN_N),
    lc.Evidence(roi=2.0, n=lc.MIN_N, revival="regime turned"),
    lc.Evidence(spanned_by="other", max_abs_corr=0.99),
    lc.Evidence(falling_windows=lc.DECAY_WINDOWS_K),
])
def test_transition_never_emits_an_illegal_edge(start: str, ev: lc.Evidence) -> None:
    nxt, why = lc.transition(start, ev)
    assert nxt in lc.ALLOWED[start], f"{start} -> {nxt} is not a legal edge ({why})"
    assert why, "a transition without a WHY is a verdict nobody can audit"


# ------------------------------------------------- 2. the consumer decides the job

def test_a_gauntlet_cell_makes_a_new_feature_useful() -> None:
    nxt, why = lc.transition(lc.NEW, USEFUL_EV)
    assert nxt == lc.USEFUL
    assert "gauntlet" in why


def test_a_state_dimension_alone_makes_it_state_only() -> None:
    nxt, why = lc.transition(lc.NEW, lc.Evidence(consumers=frozenset({lc.CONSUMER_STATE})))
    assert nxt == lc.STATE_ONLY
    assert "state dimension" in why


def test_execution_alone_makes_it_execution_only() -> None:
    nxt, why = lc.transition(lc.NEW, lc.Evidence(consumers=frozenset({lc.CONSUMER_EXECUTION})))
    assert nxt == lc.EXECUTION_ONLY
    assert "alpha" in why, "the reason execution-only exists must travel with the verdict"


def test_a_certified_cell_outranks_the_other_two_consumers() -> None:
    ev = lc.Evidence(consumers=frozenset(lc.CONSUMERS))
    assert lc.transition(lc.STATE_ONLY, ev)[0] == lc.USEFUL


def test_a_feature_nothing_reads_and_nothing_measured_does_not_move() -> None:
    nxt, why = lc.transition(lc.NEW, lc.Evidence())
    assert nxt == lc.NEW
    assert "UNMEASURED" in why and "not a verdict" in why


# ------------------------------------------------- 3. redundancy binds at the stated bound

def test_redundant_binds_at_the_stated_correlation() -> None:
    at = lc.Evidence(consumers=frozenset({lc.CONSUMER_GAUNTLET}), spanned_by="realised_vol",
                     max_abs_corr=lc.REDUNDANT_ABS_CORR)
    nxt, why = lc.transition(lc.USEFUL, at)
    assert nxt == lc.REDUNDANT
    assert "realised_vol" in why and str(lc.REDUNDANT_ABS_CORR) in why


def test_just_below_the_bound_is_not_redundant() -> None:
    below = lc.Evidence(consumers=frozenset({lc.CONSUMER_GAUNTLET}), spanned_by="realised_vol",
                        max_abs_corr=lc.REDUNDANT_ABS_CORR - 0.001)
    assert lc.transition(lc.USEFUL, below)[0] == lc.USEFUL


def test_r2_spans_it_even_when_no_single_feature_does() -> None:
    ev = lc.Evidence(spanned_by="the admitted set", max_abs_corr=0.4,
                     spanned_r2=lc.REDUNDANT_R2)
    assert lc.transition(lc.NEW, ev)[0] == lc.REDUNDANT
    assert not lc.is_spanned(lc.Evidence(spanned_by="x", max_abs_corr=0.4, spanned_r2=0.5))


def test_a_span_with_no_spanning_feature_named_is_not_a_span() -> None:
    """`spanned_by` is the evidence; a bare number with nothing behind it is not."""
    assert not lc.is_spanned(lc.Evidence(max_abs_corr=0.99))


# ------------------------------------------------- 4. decay is a warning with a count

def test_decaying_binds_at_k_windows_and_not_at_k_minus_one() -> None:
    k = lc.DECAY_WINDOWS_K
    assert lc.transition(lc.USEFUL, lc.Evidence(falling_windows=k))[0] == lc.DECAYING
    holds = lc.Evidence(consumers=frozenset({lc.CONSUMER_GAUNTLET}), falling_windows=k - 1)
    assert lc.transition(lc.USEFUL, holds)[0] == lc.USEFUL


def test_a_decaying_feature_still_gets_compute() -> None:
    assert lc.withdraw(lc.DECAYING).may_spend
    assert "still" in lc.withdraw(lc.DECAYING).why


# ------------------------------------------------- 5. nothing dies below MIN_N

def test_a_negative_roi_below_min_n_kills_nothing() -> None:
    thin = lc.Evidence(roi=-5.0, n=lc.MIN_N - 1)
    nxt, why = lc.transition(lc.USEFUL, thin)
    assert nxt == lc.USEFUL, "an unmeasured feature is UNMEASURED, not worthless"
    assert "UNMEASURED" in why


def test_a_negative_roi_at_min_n_kills_and_says_the_number() -> None:
    ev = lc.Evidence(roi=-0.25, n=lc.MIN_N, ci=(-0.5, -0.05))
    nxt, why = lc.transition(lc.USEFUL, ev)
    assert nxt == lc.DEAD
    assert "-0.25" in why and f"n={lc.MIN_N}" in why and "CI" in why


def test_zero_roi_is_death_because_zero_earns_nothing_and_still_costs() -> None:
    assert lc.transition(lc.NEW, lc.Evidence(roi=0.0, n=lc.MIN_N))[0] == lc.DEAD


def test_death_outranks_every_other_rule() -> None:
    """A dead feature that is also used, also spanned and also decaying is dead."""
    ev = lc.Evidence(roi=-1.0, n=lc.MIN_N, consumers=frozenset({lc.CONSUMER_GAUNTLET}),
                     spanned_by="other", max_abs_corr=0.99,
                     falling_windows=lc.DECAY_WINDOWS_K + 4)
    assert lc.transition(lc.USEFUL, ev)[0] == lc.DEAD


# ------------------------------------------------- 6. revival needs a reason AND a number

def test_dead_stays_dead_without_a_named_revival_condition() -> None:
    nxt, why = lc.transition(lc.DEAD, lc.Evidence(roi=9.0, n=lc.MIN_N * 10))
    assert nxt == lc.DEAD
    assert "no revival condition" in why


def test_a_named_condition_without_the_measurement_does_not_revive() -> None:
    nxt, why = lc.transition(lc.DEAD, lc.Evidence(roi=9.0, n=lc.MIN_N - 1,
                                                  revival="vol regime changed"))
    assert nxt == lc.DEAD
    assert "vol regime changed" in why and f"needs {lc.MIN_N}" in why


def test_a_named_condition_with_a_positive_measurement_revives() -> None:
    ev = lc.Evidence(roi=0.4, n=lc.MIN_N, ci=(0.1, 0.7), revival="vol regime changed")
    nxt, why = lc.transition(lc.DEAD, ev)
    assert nxt == lc.REVIVED
    assert "vol regime changed" in why and "+0.4" in why


def test_a_revived_feature_can_be_promoted_and_can_die_again() -> None:
    assert lc.transition(lc.REVIVED, USEFUL_EV)[0] == lc.USEFUL
    assert lc.transition(lc.REVIVED, lc.Evidence(roi=-1.0, n=lc.MIN_N))[0] == lc.DEAD


# ------------------------------------------------- 7. the effort ruling

def test_dead_and_redundant_are_the_only_states_that_withdraw_effort() -> None:
    withdrawn = {s for s in lc.STATES if not lc.withdraw(s)}
    assert withdrawn == {lc.DEAD, lc.REDUNDANT}


def test_every_effort_ruling_says_why() -> None:
    for s in lc.STATES:
        assert len(lc.withdraw(s).why) > 20, f"{s} withdraws or funds compute without a reason"


def test_an_unknown_status_is_read_as_new_not_as_condemned() -> None:
    e = lc.withdraw("SOMETHING_A_LATER_VERSION_WROTE")
    assert e.may_spend
    assert "read as NEW" in e.why


def test_the_effort_ruling_is_usable_as_a_boolean() -> None:
    """The call site is `if not withdraw(status): skip` -- that must work without `.may_spend`."""
    assert bool(lc.withdraw(lc.USEFUL)) is True
    assert bool(lc.withdraw(lc.DEAD)) is False
