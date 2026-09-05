"""The graveyard records WHICH GATE said no, because that is the only part a proposer can use.

Measured 2026-09-05: all 30,208 FAILED rows carried one sentence -- "research_queue ext-<id>:
canonical verdict REJECTED". `search_populations.graveyard_derived` picks a mutation axis by
matching vocabulary in that reason (cost -> horizon, turnover -> state, leak -> lag, correlation
-> residualisation), so the largest dataset the desk produces yielded exactly nothing, and
correctly so: "REJECTED" names no cause, and mutating on it is mutating on noise wearing the word
failure.

The cause was never lost, only unfollowed -- the queue row names its report and the report names
the gate. Pinned here: the cause is read from the report, an unreadable report says so rather than
implying one, and the one-shot repair improves a bare row without ever re-judging it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_ROOT / "scripts"))

import backfill_hypothesis_graph as bh  # noqa: E402


def _report(tmp_path: Path, rel: str = "reports/gates.json") -> str:
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"verdicts": [
        {"cell": "EURJPY.asia", "sym": "EURJPY", "passed": False, "stages": {
            "observations": {"passed": True},
            "stress_costs": {"passed": False,
                             "message": "net of cost the edge is 0.01R, under the 0.05R bar"},
            "expected_value": {"passed": False, "message": "EV negative at the modelled spread"},
        }},
        {"cell": "AUDCAD.london_am", "sym": "AUDCAD", "passed": False, "stages": {
            "leakage": {"passed": False, "message": "lookahead in the entry rule"}}},
        {"cell": "GBPUSD.ny_open", "sym": "GBPUSD", "passed": True, "stages": {
            "observations": {"passed": True}}},
    ]}), "utf-8")
    return rel


def _row(cell: str, rel: str, rid: str = "ext-1") -> dict:
    return {"id": rid, "canonical_cell": cell, "canonical_report": rel,
            "canonical_verdict": "REJECTED"}


def test_the_failing_gate_and_its_message_reach_the_reason(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(bh, "ROOT", tmp_path)
    monkeypatch.setattr(bh, "_REPORT_CACHE", {})
    rel = _report(tmp_path)
    why, gates = bh.failure_cause(_row("EURJPY.asia", rel))
    assert "stress_costs" in why and "expected_value" in why
    assert "net of cost" in why
    assert bh.cause_is_named(why)
    # the whole gate record rides along, so the graveyard keeps the evidence, not just a sentence
    assert gates["stress_costs"]["passed"] is False
    assert gates["canonical_report"]["path"] == rel


def test_the_reason_carries_vocabulary_the_mutation_axes_match() -> None:
    """The point of the reason is that `graveyard_derived` can act on it.

    Skipped where the consumer is not on the tree: this pins the CONTRACT between the reason and
    the axis table, and a branch carrying only the writer has no table to check against. It is a
    skip with a stated reason, never a silent pass.
    """
    pytest.importorskip("libs.research.search_populations",
                        reason="the graveyard's consumer ships with the search populations")
    from libs.research.search_populations import FATE_TO_AXIS
    for why, expected in (("ext-1: REJECTED at stress_costs -- net of cost", "horizon"),
                          ("ext-2: REJECTED at leakage -- lookahead in the entry", "lag"),
                          ("ext-3: REJECTED at correlation -- correlated with a live sleeve",
                           "residualisation")):
        hit = next((axis for needle, axis in FATE_TO_AXIS.items() if needle in why.lower()), None)
        assert hit == expected, why


def test_an_unreadable_report_says_so_and_never_implies_a_cause(tmp_path, monkeypatch) -> None:
    """A silent absence must never read as a stated cause."""
    monkeypatch.setattr(bh, "ROOT", tmp_path)
    monkeypatch.setattr(bh, "_REPORT_CACHE", {})
    why, gates = bh.failure_cause(_row("EURJPY.asia", "reports/does_not_exist.json"))
    assert "cause unrecoverable" in why
    assert not bh.cause_is_named(why)
    assert gates["canonical_report"]["path"] == "reports/does_not_exist.json"

    rel = _report(tmp_path)
    why2, _ = bh.failure_cause(_row("NOSUCH.cell", rel))
    assert "cause unrecoverable" in why2 and "NOSUCH.cell" in why2


def test_a_verdict_with_no_failed_gate_is_named_as_such(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(bh, "ROOT", tmp_path)
    monkeypatch.setattr(bh, "_REPORT_CACHE", {})
    rel = _report(tmp_path)
    why, gates = bh.failure_cause(_row("GBPUSD.ny_open", rel))
    assert "no gate is marked failed" in why
    assert not bh.cause_is_named(why)
    assert gates["observations"]["passed"] is True


def test_the_bare_verdict_is_not_a_named_cause() -> None:
    assert not bh.cause_is_named("research_queue ext-20260901-ef06f1: canonical verdict REJECTED")
    assert not bh.cause_is_named("")
    assert bh.cause_is_named("research_queue ext-1: REJECTED at stress_costs -- net of cost")


def test_the_report_is_read_once_per_path(tmp_path, monkeypatch) -> None:
    """46,786 rejected rows point at the same report; reading it per row is 46,786 reads."""
    monkeypatch.setattr(bh, "ROOT", tmp_path)
    monkeypatch.setattr(bh, "_REPORT_CACHE", {})
    rel = _report(tmp_path)
    bh.failure_cause(_row("EURJPY.asia", rel))
    (tmp_path / rel).unlink()                      # gone from disk; the index is already held
    why, _ = bh.failure_cause(_row("AUDCAD.london_am", rel))
    assert "leakage" in why
