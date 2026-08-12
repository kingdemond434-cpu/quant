"""Where the cohort died: separating a weak supply from one gate broken-closed.

The forward-slot queue reports 0 candidates against 10 free slots. That number is produced
equally by a funnel working correctly on noise and by a single gate rejecting everything it
sees, and until now the desk owned no instrument that told those apart.
"""
from __future__ import annotations

from pathlib import Path

from libs.research.rejection_attribution import (
    CONCENTRATION_ALARM,
    GateOutcome,
    attribute,
    concentration,
    read_store,
    report,
)

GATES = ["sanity", "cpcv", "fdr", "cost", "capacity", "regime"]


def _spread():
    """A healthy funnel: candidates bad in different ways fail for different reasons."""
    return [
        GateOutcome("a", "sanity", ("sanity",), ("sanity",)),
        GateOutcome("b", "cpcv", ("cpcv",), ("sanity", "cpcv")),
        GateOutcome("c", "fdr", ("fdr",), ("sanity", "cpcv", "fdr")),
        GateOutcome("d", "cost", ("cost",), ("sanity", "cpcv", "fdr", "cost")),
        GateOutcome("e", None, (), tuple(GATES)),
    ]


def _concentrated():
    """One gate kills everything; the gates behind it never judge a single candidate."""
    return [GateOutcome(str(i), "cpcv", ("cpcv",), ("sanity", "cpcv")) for i in range(20)]


# ------------------------------------------------------------------ the core measurement
def test_a_healthy_funnel_spreads_its_deaths() -> None:
    con = concentration(attribute(_spread(), gate_order=GATES))
    assert not con["concentration_alarm"]
    assert "SPREAD" in con["verdict"] and con["effective_stages"] == 4


def test_one_gate_killing_everything_raises_the_alarm() -> None:
    """THE FINDING THIS EXISTS FOR: an eight-stage gauntlet that is one stage wearing eight hats."""
    con = concentration(attribute(_concentrated(), gate_order=GATES))
    assert con["concentration_alarm"] and con["most_lethal_gate"] == "cpcv"
    assert con["its_share_of_all_deaths"] == 1.0


def test_the_alarm_names_the_test_that_separates_sharp_from_broken() -> None:
    """A gate killing everything is NOT yet a defect -- it may be the sharpest instrument. Only
    the positive controls separate 'everything is noise' from 'broken-closed'."""
    con = concentration(attribute(_concentrated(), gate_order=GATES))
    assert "NOT yet a defect" in con["verdict"]
    assert "certify_gauntlet" in con["verdict"] and "known-GOOD" in con["verdict"]


def test_gates_that_never_judged_a_candidate_are_named() -> None:
    """A gate nothing reaches cannot be said to be validating anything."""
    con = concentration(attribute(_concentrated(), gate_order=GATES))
    assert set(con["gates_never_reached"]) == {"fdr", "cost", "capacity", "regime"}
    assert "absent evidence" in con["unreached_note"]


def test_a_reached_but_never_firing_gate_is_reported_as_redundant_or_inert() -> None:
    outs = [GateOutcome(str(i), "sanity", ("sanity",), tuple(GATES)) for i in range(10)]
    con = concentration(attribute(outs, gate_order=GATES))
    assert con["gates_never_reached"] == []
    assert "redundant" in con["idle_note"]


# ------------------------------------------------------------------ the counterfactual
def test_would_reject_sees_what_the_first_failing_histogram_cannot() -> None:
    """A late gate can be perfectly discriminating and show killed=0 purely because nothing
    survives to it. Reading that as 'useless gate' is the error this column prevents."""
    outs = [GateOutcome(str(i), "sanity", ("sanity", "regime"), ("sanity",)) for i in range(10)]
    att = attribute(outs, gate_order=GATES)
    regime = next(r for r in att["gates"] if r["gate"] == "regime")
    assert regime["killed"] == 0, "it never got to judge anyone"
    assert regime["would_reject"] == 10, "but it would have rejected every one"
    assert regime["never_reached"] == 10


def test_killed_share_of_reached_is_none_when_nothing_reached_it() -> None:
    """A rate over an empty denominator is UNMEASURED, never 0.0."""
    att = attribute(_concentrated(), gate_order=GATES)
    regime = next(r for r in att["gates"] if r["gate"] == "regime")
    assert regime["killed_share_of_reached"] is None


def test_survival_rate_is_reported_exactly() -> None:
    att = attribute(_spread(), gate_order=GATES)
    assert att["n_survivors"] == 1 and att["survival_rate"] == 0.2


# ------------------------------------------------------------------ UNMEASURED is never zero
def test_no_outcomes_is_unmeasured_not_a_clean_funnel() -> None:
    out = attribute([], gate_order=GATES)
    assert out["status"] == "UNMEASURED" and "never a clean funnel" in out["why"]


def test_concentration_refuses_to_judge_an_unmeasured_cohort() -> None:
    assert concentration({"status": "UNMEASURED"})["status"] == "UNMEASURED"


def test_an_absent_store_is_named_not_collapsed_to_empty(tmp_path: Path) -> None:
    r = read_store(tmp_path / "nope.sqlite")
    assert r.status == "ABSENT" and r.outcomes == []
    assert "not the research box" in r.why


def test_a_zero_byte_store_is_distinguished_from_a_cohort_with_no_survivors(tmp_path: Path) -> None:
    """THE DISTINCTION THAT MATTERS. A 0-byte store on a non-research box and a store holding
    1,673 rejected candidates both yield 'no survivors'; only one is a finding about the funnel."""
    p = tmp_path / "empty.sqlite"
    p.touch()
    r = read_store(p)
    assert r.status == "EMPTY_FILE" and "read-without-writer" in r.why


def test_an_unreadable_store_names_the_error(tmp_path: Path) -> None:
    p = tmp_path / "junk.sqlite"
    p.write_bytes(b"not a database at all")
    assert read_store(p).status in ("UNREADABLE", "NO_ROWS")


# ------------------------------------------------------------------ authority
def test_the_report_proposes_no_threshold_change(tmp_path: Path) -> None:
    doc = report(_concentrated(), gate_order=GATES, root=tmp_path)
    assert "MEASUREMENT ONLY" in doc["authority"]
    assert "never loosened to manufacture survivors" in doc["attribution"]["law"] \
        or "ever loosened to manufacture survivors" in doc["attribution"]["law"]
    assert "proposes no threshold change" in doc["authority"]


def test_the_artifact_is_written_only_when_measured(tmp_path: Path) -> None:
    assert "written_to" in report(_spread(), gate_order=GATES, root=tmp_path)
    assert "written_to" not in report([], gate_order=GATES, root=tmp_path)


def test_the_alarm_threshold_is_explicit() -> None:
    assert 0.5 < CONCENTRATION_ALARM < 1.0

