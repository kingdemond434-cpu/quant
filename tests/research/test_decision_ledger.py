"""BEHAVIORAL tests for the rejected-trade ledger.

The safety property first: a favourable counterfactual must never reinstate the decision it
belongs to, because the population of "rejected things that would have worked" is conditioned on
the very outcome being tested. Then the legitimate use: a rejection RULE that is systematically
wrong across its whole population is a real, findable defect.
"""

from __future__ import annotations

import pytest

from libs.research.decision_ledger import (
    MIN_POPULATION_FOR_BIAS,
    OUTCOMES,
    REJECTION_CLASSES,
    Decision,
    counterfactual_summary,
    promotion_is_forbidden,
    summarise,
    systematic_bias,
)


def _d(i: int, outcome: str = "COST_REJECTED", cf: float | None = None) -> Decision:
    return Decision(decision_id=f"D{i}", strategy_id="S1", symbol="BTCUSDT",
                    decided_at="2026-08-08T00:00:00Z", outcome=outcome,
                    reason="modelled cost 9bp > edge 7bp", signal_bps=7.0,
                    modelled_cost_bps=9.0, counterfactual_bps=cf, intended_notional=1_000.0)


def test_an_unknown_outcome_cannot_be_recorded() -> None:
    with pytest.raises(ValueError, match="outcome must be one of"):
        Decision(decision_id="X", strategy_id="S", symbol="B",
                 decided_at="", outcome="LOOKED_BAD")


def test_the_basis_has_nine_ways_to_decline_and_one_to_act() -> None:
    assert len(OUTCOMES) == 10
    assert len(REJECTION_CLASSES) == 9
    assert "EXECUTED" not in REJECTION_CLASSES


# ------------------------------------------------------------ the promotion ban

def test_a_favourable_counterfactual_cannot_reinstate_its_own_decision() -> None:
    """THE SAFETY PROPERTY. The function exists so the reason appears next to the number."""
    msg = promotion_is_forbidden(_d(1, cf=180.0))
    assert "conditioned on the rejection" in msg
    assert "biased upward by construction" in msg
    assert "may never reinstate this decision" in msg


def test_no_public_function_returns_a_promotion() -> None:
    """A grep-shaped guard: if someone adds a `promote`/`reinstate` path, this fails."""
    import libs.research.decision_ledger as m
    assert not [n for n in dir(m)
                if any(w in n.lower() for w in ("promote", "reinstate", "rescue", "override"))
                and not n.startswith("promotion_is_forbidden")]


# ---------------------------------------------------------- the legitimate use

def test_a_systematically_wrong_rejection_rule_is_found() -> None:
    """A cost model 15% too pessimistic does not look like a bias -- it looks like a quiet market.
    This is the measurement that turns it into a finding."""
    decisions = [_d(i, cf=6.0 + (i % 5) * 0.4) for i in range(120)]
    found = systematic_bias(decisions)
    assert found, "a strongly positive rejected population produced no finding"
    assert found[0]["rejection_class"] == "COST_REJECTED"
    assert "about the RULE" in str(found[0]["finding"])
    assert "reinstates nothing" in str(found[0]["finding"])


def test_a_correct_rejection_rule_produces_no_finding() -> None:
    """Centred near zero is what a correct rule looks like. A detector that fires on this is a
    detector that will be muted."""
    decisions = [_d(i, cf=(-1.0) ** i * 5.0) for i in range(120)]
    assert systematic_bias(decisions) == []


def test_a_small_rejected_population_cannot_support_a_bias_claim() -> None:
    """Nine lopsided rejections are not a measurable bias, however lopsided."""
    decisions = [_d(i, cf=40.0) for i in range(9)]
    assert systematic_bias(decisions) == []
    s = counterfactual_summary(decisions)
    assert s["COST_REJECTED"]["sufficient_for_a_bias_claim"] is False


def test_unresolved_counterfactuals_are_not_counted_as_zero() -> None:
    decisions = [_d(i) for i in range(60)]          # none resolved
    s = counterfactual_summary(decisions)
    assert s == {}, "unresolved rejections were summarised as though they had outcomes"
    rep = summarise(decisions)
    assert rep["unresolved_rejections"] == 60
    assert "UNMEASURED" in str(rep["headline"])


# ------------------------------------------------------------------------ report

def test_the_report_shows_the_whole_decision_surface_not_just_the_yes() -> None:
    decisions = ([_d(i, outcome="EXECUTED", cf=3.0) for i in range(10)]
                 + [_d(100 + i, outcome="RISK_REJECTED", cf=-2.0) for i in range(40)]
                 + [_d(200 + i, outcome="CAPACITY_REJECTED", cf=1.0) for i in range(20)])
    rep = summarise(decisions)
    assert rep["executed"] == 10
    assert rep["rejected"] == 60
    assert rep["execution_share"] == pytest.approx(10 / 70, abs=1e-4)
    assert "RISK_REJECTED" in rep["counts_by_outcome"]


def test_the_note_states_the_ban_in_the_artifact_itself() -> None:
    rep = summarise([_d(1, cf=50.0)])
    assert "NEVER reinstates the decision it belongs to" in str(rep["note"])
    assert "preregistered and tested on untouched data" in str(rep["note"])


def test_an_empty_ledger_says_the_surface_is_legible_only_where_it_said_yes() -> None:
    rep = summarise([])
    assert "only where it said yes" in str(rep["headline"])


def test_the_bias_population_floor_is_not_silently_tiny() -> None:
    assert MIN_POPULATION_FOR_BIAS >= 50
