"""THE RESEARCH ORGANISATION (P53 / P54 / P60 / P62).

A desk staffed by agents fails in organisational ways that no amount of statistical rigour inside
any single agent will catch. Four properties, and each is a refusal.

An agent may not grade its own work. Not "should not" -- may not, structurally, because anyone
asked to grade their own work grades it favourably and a flagged conflict in a busy week is a
conflict that ships.

Reputation is precision, never volume. Being right about two of three must beat being right about
two of forty, or the metric rewards exactly the cheap behaviour.

A borrowed method arrives with its preconditions or not at all.

And the implementer may not merge on red canaries -- it could otherwise silently disable the
gates it exists to serve, and it would look like a productive week.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent


def _load():
    spec = importlib.util.spec_from_file_location(
        "_resorg", _ROOT / "desks" / "mt5" / "research" / "research_org.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def ro():
    return _load()


def _full(ro, **over):
    a = {"ADVOCATE": "a", "SKEPTIC": "b", "REPLICATOR": "c", "VALIDATOR": "d"}
    a.update(over)
    return ro.Review("a claim", a)


# --------------------------------------------------------------------------- P54
def test_four_separate_identities_may_proceed(ro) -> None:
    out = ro.open_review(_full(ro))
    assert out["admissible"] is True and out["conflicts"] == []


@pytest.mark.parametrize("dup", ["ADVOCATE", "SKEPTIC", "REPLICATOR"])
def test_no_identity_may_also_validate(ro, dup) -> None:
    """The specific conflict that matters: whoever validates must hold no other role."""
    out = ro.open_review(_full(ro, VALIDATOR={"ADVOCATE": "a", "SKEPTIC": "b",
                                              "REPLICATOR": "c"}[dup]))
    assert out["admissible"] is False, f"{dup} was allowed to validate its own claim"
    assert "grade their own work" in out["why"]


def test_a_conflicted_review_is_refused_not_flagged(ro) -> None:
    """A flagged conflict in a busy week is a conflict that ships."""
    out = ro.open_review(_full(ro, VALIDATOR="a"))
    assert out["admissible"] is False
    assert out["why"].startswith("REFUSED")


def test_a_missing_skeptic_is_not_a_review(ro) -> None:
    """ABSENCE IS NEVER A PASS. A review without its skeptic is an endorsement."""
    out = ro.open_review(ro.Review("c", {"ADVOCATE": "a", "REPLICATOR": "c", "VALIDATOR": "d"}))
    assert out["admissible"] is False
    assert "SKEPTIC" in out["why"] and "endorsement" in out["why"]


# --------------------------------------------------------------------------- P53
def test_precision_beats_volume(ro) -> None:
    """THE PROPERTY. Right about two of three must beat right about two of forty."""
    loud = ro.Record("loud", proposed=40, proposed_correct=2).reputation()
    careful = ro.Record("careful", proposed=12, proposed_correct=8).reputation()
    assert loud["status"] == careful["status"] == "RATED"
    assert careful["reputation"] > loud["reputation"], (
        "a high-volume agent with a poor hit rate outranked a careful one -- the metric is "
        "rewarding throughput, which is the cheap behaviour")


def test_too_few_claims_is_unrated_not_perfect(ro) -> None:
    """A single lucky call must not read as a perfect record."""
    r = ro.Record("newcomer", proposed=2, proposed_correct=2).reputation()
    assert r["status"] == "UNRATED" and r.get("reputation") is None


def test_skeptic_precision_is_scored_separately(ro) -> None:
    """Skepticism only pays if being right about a problem is what earns the credit."""
    r = ro.Record("s", proposed=5, proposed_correct=2, objections=9, objections_upheld=8)
    out = r.reputation()
    assert out["skeptic_precision"] is not None
    assert out["skeptic_precision"] > out["proposal_precision"]


# --------------------------------------------------------------------------- P60
def test_a_method_arrives_with_its_assumptions(ro) -> None:
    """A technique borrowed without its preconditions is applied where it does not hold, and it
    arrives with borrowed credibility."""
    fm = ro.frontier_methods()
    assert fm["admitted"], "no method admitted"
    for m in fm["methods"]:
        assert m["assumptions"], f"{m['name']} carries no assumptions"
        assert m["transfers"], f"{m['name']} does not say what transfers"


def test_a_method_whose_assumptions_fail_here_is_refused_with_the_reason(ro) -> None:
    """Survival analysis is the worked example: the desk kills losers, so censoring is
    informative and the standard estimator is biased."""
    fm = ro.frontier_methods()
    assert fm["refused"], "every borrowed method was admitted; none was even examined"
    bad = next(m for m in fm["methods"] if not m["holds_here"])
    assert bad["note"], "a refused method with no reason teaches nothing"
    assert "censoring" in bad["note"] or "biased" in bad["note"]


# --------------------------------------------------------------------------- P62
def test_the_implementer_may_not_merge_on_red_canaries(ro) -> None:
    """THE GATE THAT MATTERS. Merging here could silently disable the validation the desk runs
    on, and it would look like a productive week."""
    out = ro.implement("a real gap", {"branch": True, "build": True, "tests": True,
                                      "canaries": False, "merge": True})
    assert out["status"] == "BLOCKED" and out["blocked_at"] == "canaries"
    assert "silently disable" in out["why"]


def test_the_implementer_may_not_start_without_a_named_gap(ro) -> None:
    out = ro.implement("", {"branch": True, "build": True, "tests": True,
                            "canaries": True, "merge": True})
    assert out["status"] == "REFUSED"
    assert "nobody asked for" in out["why"]


def test_every_step_is_a_gate(ro) -> None:
    """Not a stage: a red step stops the pipeline where it is."""
    for step in ("branch", "build", "tests"):
        state = dict.fromkeys(ro.PIPELINE, True)
        state[step] = False
        out = ro.implement("gap", state)
        assert out["status"] == "BLOCKED" and out["blocked_at"] == step


def test_all_green_merges(ro) -> None:
    out = ro.implement("gap", dict.fromkeys(ro.PIPELINE, True))
    assert out["status"] == "MERGED" and out["blocked_at"] is None
    assert "CANARIES" in out["why"]
