"""OpenRouter pre-flight: prove wiring for free, and do not cry wolf.

These tests exist as much to pin the DETECTOR's honesty as the organs'. The first draft of this
module used string markers and produced three separate rounds of false positives on the real repo
-- it matched the word "seats" in a prose comment and missed libs.ops.llm_route entirely. A
readiness check that cries wolf is worse than none: it sends the desk to repair organs that work,
and the wasted afternoon looks like diligence.
"""
from __future__ import annotations

from pathlib import Path

from libs.ops.seat_preflight import (
    DARK_ORGANS,
    OrganReadiness,
    preflight,
    readiness,
)


# ------------------------------------------------------------------ it must cost nothing
def test_the_preflight_spends_nothing() -> None:
    """The entire point is to be free -- imports, file reads and a manifest grep."""
    d = preflight(write=False)
    assert d["spend_incurred"].startswith("ZERO")
    assert "No model is called" in d["spend_incurred"]


def test_it_needs_no_key_to_run() -> None:
    """It must work precisely when the seat is DARK, which is the only time it is useful."""
    import os
    assert not os.environ.get("OPENROUTER_API_KEY"), "this box should be dark"
    assert preflight(write=False)["n_organs"] == len(DARK_ORGANS)


# ------------------------------------------------------------------ the four independent faults
def test_each_fault_is_reported_separately() -> None:
    """A single pass/fail would hide three of the four -- they fail independently."""
    r = OrganReadiness("x", "a.json", importable=True, seated=True, scheduled=True, consumed=False)
    assert r.verdict == "OUTPUT_UNREAD" and not r.ready
    r.consumed = True
    assert r.verdict == "READY_BUT_UNCAPPED" and r.ready, "wiring is complete; spend is not"
    r.capped = True
    assert r.verdict == "READY"


def test_an_uncapped_organ_is_still_wired_but_flagged() -> None:
    """A budget hole must never hide behind a green wiring tick, so `capped` is excluded from
    `ready` and surfaced in the verdict instead."""
    r = OrganReadiness("x", "a.json", importable=True, seated=True, scheduled=True,
                       consumed=True, capped=False)
    assert r.ready and r.verdict == "READY_BUT_UNCAPPED"


def test_a_broken_import_outranks_every_other_fault() -> None:
    r = OrganReadiness("x", "a.json", importable=False, seated=False, scheduled=False)
    assert r.verdict == "BROKEN_IMPORT"


def test_a_missing_script_is_named_rather_than_silently_skipped() -> None:
    r = readiness("no_such_organ_anywhere", "data/nope.json", manifest_text="")
    assert not r.ready and "does not exist" in r.import_error
    assert any("absent from the repo" in n for n in r.notes)


# ------------------------------------------------------------------ the detector's own honesty
def test_seat_detection_follows_the_import_graph_not_prose() -> None:
    """kimi_hunter reaches a model through libs.ops.llm_route and mentions 'seats' only in a
    COMMENT. String markers both missed the real seat and matched the English."""
    r = readiness("kimi_hunter", "data/kimi_hunter.json")
    assert r.seated, "the import graph must find llm_route"


def test_env_var_seating_counts_even_without_a_seat_import() -> None:
    """run_deepseek_cycle reads OPENROUTER_API_KEY directly -- its identity is local and only
    inference leaves the box. Requiring an import would have called it unseated."""
    r = readiness("run_deepseek_cycle", "data/deepseek_evidence.jsonl")
    assert r.seated


def test_an_organ_fired_by_a_scheduled_parent_counts_as_scheduled() -> None:
    """run_external_panel has no cron line of its own; daily_research_cycle fires it. Reporting
    it UNSCHEDULED would be a false alarm."""
    r = readiness("run_external_panel", "data/panel_verdicts.jsonl")
    assert r.scheduled


def test_the_producer_is_never_counted_as_its_own_consumer() -> None:
    r = readiness("run_cro", "docs/research/CRO_BRIEFING.md")
    assert "scripts/run_cro.py" not in r.consumers


# ------------------------------------------------------------------ the live answer
def test_every_dark_organ_is_ready_and_any_regression_is_explained() -> None:
    """UPDATED, NOT RELAXED. This asserted `n_ready >= 8` while three organs were broken; all
    thirteen are now READY, so the floor is raised to match reality and the surviving invariant
    -- a non-READY organ must always say WHY -- is kept as the thing that actually protects the
    desk when one regresses."""
    d = preflight(write=False)
    assert d["n_ready"] == d["n_organs"], d["by_verdict"]
    for o in d["organs"]:
        if not o["verdict"].startswith("READY"):
            assert o["notes"], f"{o['organ']} is not READY and says nothing about why"


def test_a_non_spending_organ_is_not_judged_on_seating() -> None:
    """refresh_panel_roster reads the PUBLIC /models catalogue and buys no inference. Demanding
    a seat of it was a category error that would have sent the desk to fix a correct organ."""
    d = preflight(write=False)
    row = next(o for o in d["organs"] if o["organ"] == "refresh_panel_roster")
    assert row["verdict"] == "READY_NON_SPENDING"


def test_every_organ_declares_the_artifact_it_produces() -> None:
    """The artifact is what makes OUTPUT_UNREAD checkable at all."""
    assert all(script and artifact for script, artifact in DARK_ORGANS)


def test_the_report_writes_where_a_container_can_read_it(tmp_path: Path) -> None:
    d = preflight(root=tmp_path, write=True)
    assert (tmp_path / "docs/research/openrouter_preflight.json").exists()
    assert d["authority"].startswith("MEASUREMENT ONLY")
