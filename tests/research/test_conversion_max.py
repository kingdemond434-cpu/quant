"""Conversion pressure, and the fences that stop it corrupting what it converts.

test_throughput_leads_because_the_settled_rate_flatters is the one that matters. The
recommendation ledger settles at 95% while 190 of 283 items rot open -- a CRO reading "95%"
concludes conversion is solved and stops looking. A metric that flatters the thing it measures is
worse than no metric, because it ends the investigation.
"""
from __future__ import annotations

import json

from libs.research.conversion_max import (
    Family,
    assemble,
    dilution_report,
    duplicate_of,
    normalise_title,
    pressure_block,
)

# --------------------------------------------------------------------- the metric must not lie

def test_throughput_leads_because_the_settled_rate_flatters() -> None:
    """THE TEST THAT MATTERS. 88 converted, 5 dead, 190 open: settling at 95% is true and useless.
    Throughput at 31% is the number that describes the backlog."""
    f = Family("recommendations", total=283, converted=88, dead=5, open=190)
    assert f.settled_rate == 0.946
    assert f.throughput_rate == 0.311
    line = f.line()
    assert line.index("THROUGHPUT") < line.index("settled rate")
    assert "must not be read as health" in line
    assert line.startswith("recommendations: 190 OPEN (67% of everything acquired)")


def test_a_family_with_no_verdicts_is_unmeasured_not_zero() -> None:
    f = Family("cro", total=0, converted=0, dead=0, open=0)
    assert f.settled_rate is None and f.throughput_rate is None
    assert "UNMEASURED" in f.line()


def test_scheduled_is_counted_open_not_converted() -> None:
    """A schedule is a promise. A family that counts promises as conversions reads as worked while
    nothing ships -- which is precisely how 67 'scheduled' items became invisible."""
    state = assemble()
    rec = next(f for f in state.families if f.name == "recommendations")
    assert "promise, not a conversion" in rec.note


def test_a_missing_ledger_is_reported_not_silently_empty(tmp_path) -> None:
    """A missing backlog reads as an empty one, and an empty backlog reads as a tended one."""
    state = assemble(tmp_path)
    assert state.families
    assert all(f.note for f in state.families), "a missing family reported no reason"


def test_the_binding_backlog_is_named() -> None:
    """A board listing four backlogs produces none of them."""
    state = assemble()
    worst = state.worst()
    assert worst is not None
    assert worst.open == max(f.open for f in state.families)
    assert f"THE BINDING BACKLOG THIS CYCLE is {worst.name}" in pressure_block(state)


# ------------------------------------------------------------------------- the pressure is real

def test_the_pressure_block_is_built_from_measurements_not_exhortation() -> None:
    """'Convert more' is exhortation and produces padding. A counted backlog produces work."""
    block = pressure_block(assemble())
    assert "CONVERSION: ONE FAMILY, MAXIMISED" in block
    assert any(ch.isdigit() for ch in block)
    for demand in ("ROTTING", "Recommend KILLS", "ACQUISITION/READING gap"):
        assert demand in block


def test_the_block_warns_about_its_own_failure_modes() -> None:
    """Maximum aggression on conversion is exactly what exposes a seat to padding and to
    re-proposal, so the demand and the warning have to travel together."""
    block = pressure_block(assemble())
    assert "PADDING" in block and "RE-PROPOSING WHAT IS ALREADY OPEN" in block
    assert "RETURN EIGHT" in block
    assert "The evidence bar does NOT move" in block


# ------------------------------------------------------------------------ the duplicate fence

def test_a_restatement_of_an_open_item_is_caught() -> None:
    known = {normalise_title("Wire the CPCV purge and embargo into the validation path")}
    assert duplicate_of("Wire the CPCV purge and embargo into the validation path", known)
    assert duplicate_of("wire  the CPCV purge, and embargo into THE validation path!", known)


def test_a_known_item_with_qualifiers_bolted_on_is_caught() -> None:
    """The common padding shape: restate an open item with extra words so it looks new."""
    known = {normalise_title("Read the deribit options surface feed")}
    assert duplicate_of("Read the deribit options surface feed for skew signals", known)


def test_a_genuinely_different_recommendation_survives() -> None:
    """A false positive here silently discards real work, which is worse than letting one
    near-duplicate through -- so the match is deliberately not fuzzy beyond containment."""
    known = {normalise_title("Read the deribit options surface feed")}
    assert not duplicate_of("Measure funding-basis carry decay on OKX perps", known)


def test_short_titles_do_not_collide_by_containment() -> None:
    """Containment on a two-word title would swallow half the ledger."""
    known = {normalise_title("Fix CPCV")}
    assert not duplicate_of("Fix CPCV purge embargo and re-measure gate power", known)


def test_an_empty_title_is_not_a_duplicate() -> None:
    assert not duplicate_of("", {normalise_title("anything")})


# ------------------------------------------------------------------------- the padding detector

def _rows(n: int, *, rejected: int) -> list[dict[str, object]]:
    return [{"rejected_reason": "x" if i < rejected else ""} for i in range(n)]


def test_padding_is_detected_when_volume_buys_a_worse_pool() -> None:
    """Aggression is supposed to raise conversions, not raise output. If the reject rate climbed,
    the extra output is padding and the raw count should read SMALLER, not larger."""
    rows = _rows(24, rejected=2) + _rows(24, rejected=14)
    rep = dilution_report(rows, window=24)
    assert "PADDING" in rep["verdict"]
    assert rep["delta"] > 0.15


def test_a_steady_reject_rate_reads_as_holding() -> None:
    rows = _rows(24, rejected=4) + _rows(24, rejected=5)
    assert "HOLDING" in dilution_report(rows, window=24)["verdict"]


def test_a_persistently_bad_pool_is_flagged_even_without_a_trend() -> None:
    rows = _rows(24, rejected=18) + _rows(24, rejected=18)
    assert "LOW YIELD" in dilution_report(rows, window=24)["verdict"]


def test_too_little_history_is_unmeasured_rather_than_a_number() -> None:
    assert "UNMEASURED" in dilution_report(_rows(6, rejected=1), window=24)["verdict"]


# ------------------------------------------------------------------------------- integration

def test_the_cro_contract_rejects_a_restatement() -> None:
    from libs.research.cro_role import parse
    base = {"title": "T", "deliverable": "alpha_opportunity", "lever": "edge", "kind": "activate",
            "evidence_class": "hypothesis", "why_it_matters": "w", "bottleneck": "b",
            "mechanism": "m", "expected_upside": "u", "risks": "r", "dependencies": "d",
            "validation_method": "v", "opportunity_cost": "o", "estimated_roi": "roi",
            "confidence": "medium", "success_metric": "s"}
    known = {normalise_title("Read the deribit options surface feed")}
    res = parse(json.dumps([{**base, "title": "Read the deribit options surface feed"},
                            {**base, "title": "Measure basis carry decay on OKX perps"}]),
                known_open=known)
    assert [r.title for r in res.accepted] == ["Measure basis carry decay on OKX perps"]
    assert "inflates the backlog" in res.rejected[0].rejected_reason


def test_passing_an_empty_known_set_disables_the_fence() -> None:
    from libs.research.cro_role import parse
    base = {"title": "Anything at all", "deliverable": "alpha_opportunity", "lever": "edge",
            "kind": "activate", "evidence_class": "hypothesis", "why_it_matters": "w",
            "bottleneck": "b", "mechanism": "m", "expected_upside": "u", "risks": "r",
            "dependencies": "d", "validation_method": "v", "opportunity_cost": "o",
            "estimated_roi": "roi", "confidence": "medium", "success_metric": "s"}
    assert len(parse(json.dumps([base]), known_open=set()).accepted) == 1
