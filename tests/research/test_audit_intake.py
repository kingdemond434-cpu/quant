"""The cold-audit classifier is a POLICY, so it is tested like one.

Every case here is the standing order written as a sentence an audit would plausibly produce. The
two that matter most are the near-misses: a reduction that BUYS growth must be admitted, and a
word that merely CONTAINS a refusal term must not fire -- the first run of this classifier refused
seven rows, all seven because "cap" matched inside "capital" and "capture".
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "audit_intake", ROOT / "desks" / "mt5" / "research" / "audit_intake.py")
assert _spec and _spec.loader
audit_intake = importlib.util.module_from_spec(_spec)
sys.modules["audit_intake"] = audit_intake
_spec.loader.exec_module(audit_intake)


@pytest.mark.parametrize("text", [
    "We recommend reducing the 20% heat floor to 10% during elevated volatility.",
    "You should consider whether the minimum heat floor is appropriate for this account size.",
    "Consider raising the heat target only after a review of the heat floor rationale.",
])
def test_heat_floor_criticism_is_refused_on_sight(text: str) -> None:
    """The floor is the principal's standing order. No phrasing of the question is entertained."""
    v = audit_intake.classify(text)
    assert v["verdict"] == "REFUSED_HEAT_FLOOR", v


@pytest.mark.parametrize("text", [
    "We suggest reducing position size during regimes with unstable correlation estimates.",
    "The desk should lower its leverage until forward evidence accumulates.",
    "Consider capping exposure per sleeve to limit tail risk.",
    "It would be prudent to scale back the allocation to the newest sleeves.",
])
def test_timid_recommendations_are_refused(text: str) -> None:
    """A smaller book is refused even when the argument for it is good. Rule 1 requires the PROOF
    that E[log W] rises, and an audit's confidence is not that proof."""
    v = audit_intake.classify(text)
    assert v["verdict"] == "REFUSED_TIMID", v


@pytest.mark.parametrize("text", [
    "We recommend reducing the correlation between the three gold sleeves.",
    "You should eliminate the lookahead in the regime labels used for sizing.",
    "Consider cutting the trial count spent on single-name equities.",
    "The desk should reduce slippage by moving the entry off the minute boundary.",
])
def test_reductions_that_buy_growth_are_admitted(text: str) -> None:
    """Reducing rho, lookahead, trial count or slippage RAISES robust forward E[log W]. The verb
    is the same as a timid recommendation's; the object is what separates them."""
    v = audit_intake.classify(text)
    assert v["verdict"] == "ADMIT", v


@pytest.mark.parametrize("text", [
    "promoter.capital_verdict returns the allocation view the promoter reads when stale",
    "costs are not charged, so the book is sized on gross returns it can never capture",
    "50 trades (n_eff 45.1), 14d, always-valid lower bound -0.5914R > 0",
])
def test_words_that_merely_contain_a_refusal_term_do_not_fire(text: str) -> None:
    """capital / capture / capacity contain "cap"; "lower bound" contains "lower". None of these
    is a recommendation to shrink anything, and all three were refused by the first draft."""
    v = audit_intake.classify(text)
    assert v["verdict"] != "REFUSED_TIMID", v


def test_measurement_is_not_judged_as_advice() -> None:
    """Diagnostic prose is recorded and excluded, not classified. A refusal list padded with
    verdicts on text nobody proposed acting on is a list that stops being read."""
    v = audit_intake.classify("n=50 but only 14.0 independent observations (distinct_clusters)")
    assert v["verdict"] == "NOT_A_RECOMMENDATION", v


def test_absent_sources_report_unmeasured_not_clean() -> None:
    """L1.28a: absence never resolves to a clean verdict. If no audit artifact exists the status
    must say UNMEASURED, because "the audit found nothing" and "the audit never ran" are
    different facts and only one of them is about the desk."""
    doc = audit_intake.build()
    if doc["n_sources_present"] == 0:
        assert doc["status"] == "UNMEASURED"
        assert doc["unmeasured_note"]
    else:
        assert doc["status"] == "OK"


def test_every_source_is_named_whether_present_or_not() -> None:
    """A source that silently drops off the list is a lane that stops being watched."""
    doc = audit_intake.build()
    assert len(doc["sources"]) == len(audit_intake.SOURCES)
    assert all(s["state"] in ("PRESENT", "ABSENT") for s in doc["sources"])
