"""EXPERIMENT DESIGN AND CAPACITY (P18 / P19 / P65 / P29 / P30).

Three refusals carry this module.

An experiment that cannot change the decision must score ZERO however interesting it is. That is
the factor desks skip, and skipping it is why research backlogs fill with questions whose every
possible answer leads to the same action.

A CONFIRMING test must be excluded outright, not merely ranked last. A test a false hypothesis
would also pass carries no information (L1.63), and leaving it in a ranked queue means a busy week
runs it.

And theory and empirics must never be averaged. High empirics with no mechanism and high mechanism
with no empirics collapse to the same middling score, and they demand opposite responses -- one
needs a harder test, the other needs a reason.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent


def _load():
    spec = importlib.util.spec_from_file_location(
        "_expdesign", _ROOT / "desks" / "mt5" / "research" / "experiment_design.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def ed():
    return _load()


# --------------------------------------------------------------------------- P18
def test_an_experiment_that_changes_nothing_is_refused(ed) -> None:
    """THE FACTOR DESKS SKIP. Free of value at positive cost is not 'cheap'."""
    e = ed.Experiment("re_run_everything", p_changes_decision=0.0, decision_value=99.0,
                      cost_hours=1.0)
    out = ed.evsi(e)
    assert out["queue"] is False, "an experiment with a 99-unit payoff was queued despite no "\
                                  "possible answer changing the decision"
    assert "free of value at positive cost" in out["why"]


def test_a_decisive_cheap_experiment_is_queued(ed) -> None:
    out = ed.evsi(ed.Experiment("measure_markout", 0.8, 0.25, 1.0, falsifies="cost < edge"))
    assert out["queue"] is True and out["evsi"] > 0


def test_cost_can_outweigh_a_real_decision_change(ed) -> None:
    """A question worth answering is not automatically worth what it costs to answer."""
    out = ed.evsi(ed.Experiment("huge_sweep", 0.9, 0.05, 500.0, falsifies="x"))
    assert out["queue"] is False and out["evsi"] < 0


# --------------------------------------------------------------------------- P19
def test_a_confirming_design_is_excluded_not_ranked(ed) -> None:
    """Ranking it last still leaves it in a queue a busy week will run."""
    out = ed.cheapest_falsifier([
        ed.Experiment("cheap_confirm", 0.5, 0.1, 0.5),
        ed.Experiment("dear_falsify", 0.5, 0.1, 20.0, falsifies="the mechanism is real"),
    ])
    assert out["choice"] == "dear_falsify", (
        "the cheap CONFIRMING test won on price; thoroughness is not power and a test a false "
        "hypothesis would also pass settles nothing")
    assert "cheap_confirm" in out["excluded_confirming"]


def test_the_cheapest_falsifier_wins_among_falsifiers(ed) -> None:
    out = ed.cheapest_falsifier([
        ed.Experiment("dear", 0.5, 0.1, 30.0, falsifies="a"),
        ed.Experiment("cheap", 0.5, 0.1, 2.0, falsifies="b"),
    ])
    assert out["choice"] == "cheap" and out["cost_hours"] == 2.0


def test_a_queue_of_only_confirming_tests_settles_nothing(ed) -> None:
    """ABSENCE IS NEVER A PASS: 'no falsifier available' is a finding, not a clean slate."""
    out = ed.cheapest_falsifier([ed.Experiment("a", 0.5, 0.1, 1.0),
                                 ed.Experiment("b", 0.5, 0.1, 2.0)])
    assert out["status"] == "NONE_FALSIFYING"
    assert "carries no information" in out["why"]


# --------------------------------------------------------------------------- P65
def test_empirics_without_mechanism_is_named_not_averaged(ed) -> None:
    """The classic overfit signature: it worked and nobody can say why."""
    out = ed.arbitrate(p_mechanism=0.15, p_empirical=0.85)
    assert out["verdict"] == "EMPIRICS_WITHOUT_MECHANISM"
    assert "harder test" in out["next"].lower()
    assert "bigger position" in out["next"], "the recommended action must rule out sizing up"


def test_mechanism_without_empirics_is_named_not_averaged(ed) -> None:
    """The most seductive state on a research desk: the story survives every failed test."""
    out = ed.arbitrate(p_mechanism=0.85, p_empirical=0.15)
    assert out["verdict"] == "MECHANISM_WITHOUT_EMPIRICS"
    assert "not more of the same test" in out["next"].lower()


def test_the_two_opposite_cases_do_not_collapse_to_one_score(ed) -> None:
    """THE WHOLE POINT. Averaging destroys exactly the information the pair carries."""
    a = ed.arbitrate(0.15, 0.85)
    b = ed.arbitrate(0.85, 0.15)
    assert a["verdict"] != b["verdict"]
    assert a["next"] != b["next"], (
        "two candidates needing opposite responses were given the same recommendation")


def test_agreement_is_reported_as_nothing_to_arbitrate(ed) -> None:
    out = ed.arbitrate(0.78, 0.82)
    assert out["verdict"].startswith("AGREED")
    assert "nothing to arbitrate" in out["why"]


# --------------------------------------------------------------------------- P29 / P30
def test_impact_grows_with_size_so_the_universe_shrinks(ed) -> None:
    """Assuming no impact is the error that makes every strategy look infinitely scalable."""
    c = ed.capacity_curve(edge_bp=8.0, adv_lots=40.0)
    nets = [r["net_bp"] for r in c["curve"]]
    assert nets == sorted(nets, reverse=True), "net edge did not decay with size"
    assert not c["curve"][-1]["viable"], "the largest size was still viable; impact is not biting"
    assert c["max_viable_lots"] > 0


def test_a_small_edge_at_our_capital_is_named_a_moat(ed) -> None:
    """Edges too small for an institution are the ones nobody has arbitraged away."""
    out = ed.at_our_capital(edge_bp=8.0, adv_lots=40.0)
    assert out["viable_here"] is True
    assert "MOAT" in out["verdict"]


def test_an_edge_that_dies_at_our_size_says_so(ed) -> None:
    out = ed.at_our_capital(edge_bp=0.01, adv_lots=0.02)
    assert out["viable_here"] is False
    assert "not viable even at our size" in out["verdict"]


def test_capacity_is_always_scored_at_the_desks_own_capital(ed) -> None:
    """A capacity study run at a size this desk will never trade studies somebody else's desk."""
    assert ed.DESK_CAPITAL > 0
    out = ed.at_our_capital(edge_bp=8.0, adv_lots=40.0)
    assert out["capital"] == ed.DESK_CAPITAL
    assert "somebody else's desk" in out["why_our_size"]
