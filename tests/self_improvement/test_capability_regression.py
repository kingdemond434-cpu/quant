"""BEHAVIORAL tests for the anti-regression ratchet.

Two properties pulling in opposite directions, and the module is only useful if it holds both:

    a change that is cheaper while a capability fell is NOT an upgrade
    a change that adds complexity earning more than it costs IS an upgrade

A module that only enforced the first would become an argument against every expansion, which is
precisely what the specification forbids it from being.
"""

from __future__ import annotations

import pytest

from libs.self_improvement.capability_regression import (
    CAPABILITY_DIMENSIONS,
    COST_DIMENSIONS,
    CapabilitySnapshot,
    RegressionRecord,
    compare,
    summarise,
    verdict,
)

BEFORE = CapabilitySnapshot(
    subsystem="miner", at="t0",
    metrics={"source_languages": 7, "validation_power": 0.8, "token_cost": 100.0},
    tests_passing=("test_a", "test_b"))


def test_a_cheaper_change_that_lost_a_capability_is_a_regression() -> None:
    """THE HEADLINE CASE. Shorter prompts, 60% fewer tokens, and four source languages gone."""
    after = CapabilitySnapshot("miner", "t1",
                               {"source_languages": 3, "validation_power": 0.8,
                                "token_cost": 40.0},
                               ("test_a", "test_b"))
    v, why = verdict(BEFORE, after)
    assert v == "REGRESSION"
    assert "source_languages" in why
    assert "not benefits in themselves" in why


def test_added_complexity_that_earns_more_than_it_costs_is_an_upgrade() -> None:
    """The converse, and it must hold or this module becomes a brake on every expansion."""
    after = CapabilitySnapshot("miner", "t1",
                               {"source_languages": 12, "validation_power": 0.9,
                                "token_cost": 400.0},
                               ("test_a", "test_b", "test_c"))
    v, why = verdict(BEFORE, after, expected_surplus_gain=0.3)
    assert v == "UPGRADE", why
    assert "no capability dimension fell" in why


def test_a_dropped_test_is_a_withdrawn_capability_claim() -> None:
    after = CapabilitySnapshot("miner", "t1", dict(BEFORE.metrics), ("test_a",))
    v, why = verdict(BEFORE, after)
    assert v == "REGRESSION"
    assert "test_b" in why


def test_no_incumbent_snapshot_makes_the_change_unverifiable() -> None:
    """A regression you did not measure before is one you cannot detect after."""
    after = CapabilitySnapshot("miner", "t1", {"source_languages": 99})
    v, why = verdict(CapabilitySnapshot("miner"), after)
    assert v == "UNVERIFIABLE"
    assert "left with the code" in why


def test_an_intentional_loss_is_allowed_when_it_is_recorded() -> None:
    """Removing genuinely negative-value capability is good work. Losing it silently is not."""
    after = CapabilitySnapshot("miner", "t1",
                               {"source_languages": 3, "validation_power": 0.8,
                                "token_cost": 40.0},
                               ("test_a", "test_b"))
    rec = RegressionRecord("miner", "source_languages",
                           reason="four feeds were dead links returning 404 for six months",
                           measured_cost=0.0, measured_benefit=0.4, approved_by="principal")
    v, why = verdict(BEFORE, after, accepted=(rec,))
    assert v == "ACCEPTED_REGRESSION"
    assert "SILENT loss is" in why


def test_an_unapproved_record_does_not_launder_a_regression() -> None:
    after = CapabilitySnapshot("miner", "t1",
                               {"source_languages": 3, "validation_power": 0.8,
                                "token_cost": 40.0},
                               ("test_a", "test_b"))
    rec = RegressionRecord("miner", "source_languages", reason="", approved_by="")
    assert verdict(BEFORE, after, accepted=(rec,))[0] == "REGRESSION"


def test_a_partially_covered_loss_is_still_a_regression() -> None:
    """Recording one of two losses does not cover the other."""
    after = CapabilitySnapshot("miner", "t1",
                               {"source_languages": 3, "validation_power": 0.5,
                                "token_cost": 40.0},
                               ("test_a", "test_b"))
    rec = RegressionRecord("miner", "source_languages", reason="dead feeds",
                           approved_by="principal")
    v, why = verdict(BEFORE, after, accepted=(rec,))
    assert v == "REGRESSION"
    assert "validation_power" in why


def test_an_unknown_dimension_cannot_hide_a_regression_behind_a_new_name() -> None:
    with pytest.raises(ValueError, match="unknown dimension"):
        CapabilitySnapshot("x", metrics={"vibes": 1.0})
    assert "source_languages" in CAPABILITY_DIMENSIONS
    assert "token_cost" in COST_DIMENSIONS


def test_a_dimension_measured_on_one_side_only_is_unverified_not_held() -> None:
    after = CapabilitySnapshot("miner", "t1",
                               {"source_languages": 7, "validation_power": 0.8,
                                "token_cost": 100.0, "throughput": 5.0},
                               ("test_a", "test_b"))
    d = compare(BEFORE, after)
    assert d["dimensions_measured_on_one_side_only"] == ["throughput"]
    _, why = verdict(BEFORE, after)
    assert "UNVERIFIED" in why and "rather than held" in why


def test_cost_and_capability_deltas_are_reported_separately() -> None:
    after = CapabilitySnapshot("miner", "t1",
                               {"source_languages": 9, "validation_power": 0.7,
                                "token_cost": 40.0},
                               ("test_a", "test_b"))
    d = compare(BEFORE, after)
    assert d["capability_gains"] == {"source_languages": 2.0}
    assert d["capability_losses"] == {"validation_power": pytest.approx(-0.1)}
    assert d["cost_savings"] == {"token_cost": 60.0}


def test_the_report_leads_with_unrecorded_regressions() -> None:
    good = CapabilitySnapshot("clean", "t1", {"source_languages": 9}, ("t",))
    bad = CapabilitySnapshot("broken", "t1", {"source_languages": 1}, ("t",))
    base = CapabilitySnapshot("x", "t0", {"source_languages": 5}, ("t",))
    rep = summarise([(base, good), (base, bad)])
    rows = rep["rows"]
    assert isinstance(rows, list)
    assert rows[0]["subsystem"] == "broken"
    assert rep["regressions"] == 1


def test_the_note_forbids_citing_this_module_against_useful_complexity() -> None:
    rep = summarise([(BEFORE, BEFORE)])
    note = str(rep["note"])
    assert "never reasons that stand alone" in note
    assert "must never be cited against it" in note
    assert "no bias toward smaller" in note


def test_an_empty_report_says_regressions_would_be_invisible() -> None:
    rep = summarise([])
    assert "unverified upgrade claim" in str(rep["headline"])
