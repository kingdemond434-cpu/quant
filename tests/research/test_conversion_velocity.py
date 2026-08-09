"""BEHAVIORAL tests for economic conversion velocity.

The distinction everything here turns on: a delay that BUYS evidence is correct, and a delay that
buys nothing is waste. A module that conflated them would be a throughput metric that argues for
lowering a validation bar, which is the one use it must never have.
"""

from __future__ import annotations

import pytest

from libs.research.conversion_velocity import (
    STAGES,
    ConversionRecord,
    bound_by,
    economic_waiting_cost,
    stage_latencies,
    summarise,
    velocity,
)


def _rec(**kw) -> ConversionRecord:
    base: dict[str, object] = {
        "candidate_id": "A1", "stage_days": {"discovered": 0.0, "survivor": 2.0},
        "half_life_days": 12.0, "expected_bps_per_day": 1.5,
        "effective_n": 0.0, "required_effective_n": 0.0, "age_days": 10.0}
    base.update(kw)
    return ConversionRecord(**base)  # type: ignore[arg-type]


# ------------------------------------------------------- evidence-bound vs process-bound

def test_a_candidate_still_accumulating_evidence_is_waiting_correctly() -> None:
    v, why = bound_by(_rec(effective_n=12, required_effective_n=60))
    assert v == "EVIDENCE_BOUND"
    assert "CORRECTLY" in why
    assert "lowered bar wearing a stopwatch" in why


def test_a_candidate_with_sufficient_evidence_and_no_movement_is_pure_waste() -> None:
    v, why = bound_by(_rec(effective_n=400, required_effective_n=60, age_days=13.0))
    assert v == "PROCESS_BOUND"
    assert "the evidence is IN" in why
    assert "buys nothing" in why
    assert "'portfolio_admitted'" in why, "the report must name the stage that is not happening"


def test_missing_counts_are_unmeasured_not_assumed_either_way() -> None:
    """Defaulting to either answer is the WS-005 shape, and the two answers are opposites."""
    v, why = bound_by(_rec())
    assert v == "UNMEASURED"
    assert "opposite findings" in why


def test_a_closed_chain_is_complete() -> None:
    v, _ = bound_by(_rec(stage_days=dict.fromkeys(STAGES, 1.0)))
    assert v == "COMPLETE"


# ---------------------------------------------------------------------- waiting cost

def test_the_waiting_cost_is_priced_and_declared_a_lower_bound() -> None:
    cost, why = economic_waiting_cost(_rec(age_days=14.0, half_life_days=10.0,
                                           expected_bps_per_day=2.0))
    assert cost > 0
    assert "lower bound" in why or "Excludes the live information" in why
    assert "not estimated here" in why


def test_a_longer_delay_costs_strictly_more() -> None:
    a, _ = economic_waiting_cost(_rec(age_days=5.0))
    b, _ = economic_waiting_cost(_rec(age_days=25.0))
    assert b > a


def test_an_unpriceable_delay_returns_zero_that_says_it_measured_nothing() -> None:
    cost, why = economic_waiting_cost(_rec(half_life_days=0.0))
    assert cost == 0.0
    assert "Zero here means nothing was priced, never that nothing was lost" in why


# ------------------------------------------------------------------------ latencies

def test_stage_latencies_are_none_where_a_stage_never_happened() -> None:
    lat = stage_latencies(_rec())
    assert lat["discovered->survivor"] == 2.0
    assert lat["survivor->portfolio_admitted"] is None


def test_velocity_uses_medians_so_one_straggler_does_not_define_throughput() -> None:
    fast = [_rec(candidate_id=f"F{i}",
                 stage_days={"discovered": 0.0, "survivor": 2.0}) for i in range(5)]
    slow = _rec(candidate_id="S", stage_days={"discovered": 0.0, "survivor": 400.0})
    med = velocity([*fast, slow])
    assert med["research_to_survivor"] == pytest.approx(2.0)


def test_an_untraversed_transition_is_none_not_zero() -> None:
    med = velocity([_rec()])
    assert med["survivor_to_first_fill"] is None, (
        "a transition nothing has ever made reported a latency of zero, which reads as instant")


# ------------------------------------------------------------------------------ report

def test_the_report_leads_with_process_bound_candidates_ranked_by_cost() -> None:
    cheap = _rec(candidate_id="cheap", effective_n=400, required_effective_n=60,
                 expected_bps_per_day=0.2, age_days=9.0)
    dear = _rec(candidate_id="dear", effective_n=400, required_effective_n=60,
                expected_bps_per_day=8.0, age_days=30.0)
    waiting = _rec(candidate_id="waiting", effective_n=5, required_effective_n=60)
    rep = summarise([cheap, waiting, dear])
    rows = rep["rows"]
    assert isinstance(rows, list)
    assert rows[0]["candidate_id"] == "dear"
    assert rep["process_bound"] == 2
    assert rep["evidence_bound"] == 1
    assert "PROCESS-bound" in str(rep["headline"])


def test_the_note_forbids_using_this_metric_to_lower_a_bar() -> None:
    rep = summarise([_rec(effective_n=1, required_effective_n=60)])
    assert "EVIDENCE_BOUND latency is correct and is not a target for reduction" in str(rep["note"])


def test_an_empty_ledger_says_the_decisive_gap_is_unwatched() -> None:
    rep = summarise([])
    assert "UNMEASURED" in str(rep["headline"])
    assert "the one gap nobody is watching" in str(rep["headline"])
