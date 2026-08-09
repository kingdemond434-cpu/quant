"""BEHAVIORAL tests for F3's conditional branch.

Two of these are the whole reason the module exists and they pull in opposite directions:

    a properly preregistered conditional mechanism must be ABLE to pass
    a post-hoc regime rescue must NEVER pass, no matter how good its numbers

A branch that only did the first is a lowered bar. A branch that only did the second is F3 again.
"""

from __future__ import annotations

import pytest

from libs.validation.state_conditional import (
    MIN_STATE_OCCURRENCES,
    REQUIREMENTS,
    ConditionalEvidence,
    Preregistration,
    adjudicate,
    requirement_status,
    rescue_to_new_hypothesis,
    summarise,
)


def _good_prereg(seq: int = 10) -> Preregistration:
    return Preregistration(
        hypothesis_id="H1",
        mechanism_class="STATE_CONDITIONAL_MECHANISM",
        state_definition="funding_8h_annualised > 0.35 and oi_change_24h < 0",
        conditionality_mechanism=(
            "the edge is a crowded-carry unwind: it requires leveraged longs to be paying to hold "
            "the position, which is only true while funding is extreme. Outside that state there "
            "is no crowd to unwind and the mechanism has nothing to act on"),
        sequence=seq)


def _good_evidence(first_eval: int = 20) -> ConditionalEvidence:
    return ConditionalEvidence(
        hypothesis_id="H1", first_evaluated_sequence=first_eval,
        state_occurrences=14, state_share=0.18, as_of_observable=True,
        classifier_stability=0.86, in_state_net_bps=3.4, out_state_net_bps=0.1,
        in_state_n=900, out_state_n=4200, transition_net_bps=-0.4,
        conditional_costs_measured=True, untouched_oos_net_bps=2.7, untouched_oos_n=310)


# ------------------------------------------------------- the branch must be passable

def test_a_properly_preregistered_conditional_mechanism_can_pass() -> None:
    """If this fails the branch is decorative and F3's measured 50% ceiling still binds."""
    v, why = adjudicate(_good_prereg(), _good_evidence())
    assert v == "CONDITIONAL_VALIDATED", why
    assert "not a promotion" in why


def test_passing_the_branch_is_not_a_promotion() -> None:
    _, why = adjudicate(_good_prereg(), _good_evidence())
    assert "gauntlet still owns" in why


# ------------------------------------------------------- the rescue must be refused

def test_a_post_hoc_regime_rescue_is_refused_however_good_the_numbers() -> None:
    """THE DEFECT THIS MODULE EXISTS FOR. The state was declared AFTER the candidate failed, so
    the slice was chosen with the results visible. Spectacular conditional numbers are exactly
    what such a search produces, so they must not help."""
    prereg = _good_prereg(seq=99)                 # declared late
    ev = ConditionalEvidence(
        hypothesis_id="H1", first_evaluated_sequence=20,
        state_occurrences=40, state_share=0.30, as_of_observable=True,
        classifier_stability=0.99, in_state_net_bps=25.0, out_state_net_bps=0.0,
        in_state_n=5000, out_state_n=5000, transition_net_bps=0.0,
        conditional_costs_measured=True, untouched_oos_net_bps=24.0, untouched_oos_n=2000)
    v, why = adjudicate(prereg, ev)
    assert v == "POST_HOC_RESCUE", f"a rescue passed with {v}"
    assert "AFTER the candidate was first evaluated" in why
    assert "untouched data" in why


def test_borrowing_another_hypothesis_declaration_is_also_a_rescue() -> None:
    prereg = _good_prereg()
    ev = ConditionalEvidence(hypothesis_id="H2", first_evaluated_sequence=30,
                             state_occurrences=20, state_share=0.2, as_of_observable=True,
                             classifier_stability=0.9, in_state_net_bps=10.0,
                             conditional_costs_measured=True, transition_net_bps=0.0,
                             untouched_oos_net_bps=9.0, untouched_oos_n=200)
    v, _ = adjudicate(prereg, ev)
    assert v == "POST_HOC_RESCUE"


def test_a_rescue_converts_into_a_forward_hypothesis_with_a_new_id() -> None:
    """The observation is real information and is not thrown away -- it becomes a NEW
    preregistration stamped at the current sequence, testable only on data that arrives later.
    Reusing the id is how a rescued slice inherits its parent's history."""
    prereg = _good_prereg(seq=99)
    ev = _good_evidence(first_eval=20)
    new = rescue_to_new_hypothesis(prereg, ev, sequence_now=140)
    assert new.hypothesis_id != prereg.hypothesis_id
    assert new.sequence == 140
    assert new.is_conditional
    # And the new one cannot be adjudicated against the OLD evidence.
    v, _ = adjudicate(new, ev)
    assert v == "POST_HOC_RESCUE"


# ------------------------------------------------- global F3 is not reachable from here

def test_a_candidate_that_declared_global_cannot_use_this_branch_after_failing() -> None:
    """The escape hatch this module must not have: fail global F3, then reclassify."""
    prereg = Preregistration(hypothesis_id="H1", mechanism_class="GLOBAL_MECHANISM", sequence=1)
    v, why = adjudicate(prereg, _good_evidence())
    assert v == "NOT_CONDITIONAL"
    assert "global F3 applies unchanged" in why


def test_an_edge_that_works_everywhere_is_sent_back_to_global_f3() -> None:
    ev = ConditionalEvidence(
        hypothesis_id="H1", first_evaluated_sequence=20, state_occurrences=14, state_share=0.18,
        as_of_observable=True, classifier_stability=0.9, in_state_net_bps=2.0,
        out_state_net_bps=5.0, in_state_n=900, out_state_n=4200, transition_net_bps=0.1,
        conditional_costs_measured=True, untouched_oos_net_bps=2.0, untouched_oos_n=300)
    v, why = adjudicate(_good_prereg(), ev)
    assert v == "NOT_CONDITIONAL"
    assert "the declared state is not the condition" in why


# ---------------------------------------------------------------- the eight requirements

def test_all_eight_requirements_are_measured_not_asserted() -> None:
    st = requirement_status(_good_prereg(), _good_evidence())
    assert set(st) == set(REQUIREMENTS)
    assert all(ok for ok, _ in st.values())


@pytest.mark.parametrize("field,value,expect", [
    ("as_of_observable", False, "AS_OF_OBSERVABILITY"),
    ("state_occurrences", 3, "STATE_RECURRENCE"),
    ("state_share", 0.01, "STATE_RECURRENCE"),
])
def test_a_structural_requirement_failure_blocks_the_branch(field, value, expect) -> None:
    ev = _good_evidence()
    ev = ConditionalEvidence(**{**ev.__dict__, field: value})
    v, why = adjudicate(_good_prereg(), ev)
    assert v == "INSUFFICIENT_STATE_EVIDENCE"
    assert expect in why


def test_it_only_worked_there_is_not_a_mechanism() -> None:
    """The observation that needs explaining is not the explanation, and the string that says so
    is the one a hurried author would actually type."""
    prereg = Preregistration(
        hypothesis_id="H1", mechanism_class="STATE_CONDITIONAL_MECHANISM",
        state_definition="regime == 2",
        conditionality_mechanism="it only worked there", sequence=1)
    v, why = adjudicate(prereg, _good_evidence())
    assert v == "INSUFFICIENT_STATE_EVIDENCE"
    assert "MECHANISM_FOR_CONDITIONALITY" in why


def test_an_unopened_lockbox_is_unproven_not_validated() -> None:
    ev = ConditionalEvidence(**{**_good_evidence().__dict__,
                                "untouched_oos_net_bps": None, "untouched_oos_n": 0})
    v, why = adjudicate(_good_prereg(), ev)
    assert v == "CONDITIONAL_UNPROVEN"
    assert "lockbox was never opened" in why
    assert "not a kill" in why


def test_a_conditional_edge_that_dies_out_of_sample_is_the_branch_working() -> None:
    ev = ConditionalEvidence(**{**_good_evidence().__dict__, "untouched_oos_net_bps": -1.2})
    v, why = adjudicate(_good_prereg(), ev)
    assert v == "CONDITIONAL_UNPROVEN"
    assert "did not survive untouched OOS" in why


def test_pooled_costs_inside_a_state_are_caught() -> None:
    ev = ConditionalEvidence(**{**_good_evidence().__dict__,
                                "conditional_costs_measured": False})
    v, why = adjudicate(_good_prereg(), ev)
    assert v == "CONDITIONAL_UNPROVEN"
    assert "CONDITIONAL_COSTS" in why


# ------------------------------------------------------------------------ the report

def test_the_report_names_rescues_and_refuses_to_bury_them() -> None:
    good = (_good_prereg(), _good_evidence())
    bad = (_good_prereg(seq=99), _good_evidence(first_eval=20))
    rep = summarise([good, bad])
    assert rep["counts"]["POST_HOC_RESCUE"] == 1
    assert rep["counts"]["CONDITIONAL_VALIDATED"] == 1
    assert "POST-HOC RESCUES" in str(rep["headline"])
    assert "Global F3 is UNCHANGED" in str(rep["note"])


def test_an_empty_report_says_unexercised_not_clean() -> None:
    rep = summarise([])
    assert "UNEXERCISED, not absent" in str(rep["headline"])


def test_the_recurrence_floor_is_not_silently_tiny() -> None:
    assert MIN_STATE_OCCURRENCES >= 8
