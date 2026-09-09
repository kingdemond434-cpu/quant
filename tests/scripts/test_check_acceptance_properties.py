"""Five properties, measured from artifacts; an absent artifact is UNMEASURED, never a grade."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts import check_acceptance_properties as cap  # noqa: E402

NOW = datetime(2026, 9, 9, tzinfo=UTC)


def _desk(tmp_path: Path) -> Path:
    for d in ("data/hypotheses", "data/universe", "reports"):
        (tmp_path / d).mkdir(parents=True, exist_ok=True)
    return tmp_path


def test_everything_absent_is_unmeasured_not_failed(tmp_path: Path) -> None:
    doc = cap.measure(_desk(tmp_path), ROOT, NOW)
    assert doc["met"] == 0 and set(doc["unmeasured"]) >= {"AP1", "AP3", "AP4"}
    assert all(p["status"] in ("MET", "PARTIAL", "MISSING") for p in doc["properties"].values())


def test_ap1_counts_cells_the_system_opened_this_week(tmp_path: Path) -> None:
    desk = _desk(tmp_path)
    fresh, old = (NOW - timedelta(days=2)).isoformat(), (NOW - timedelta(days=40)).isoformat()
    (desk / "data" / "hunt_coverage.json").write_text(json.dumps({"vectors": {
        "a": {"name": "a", "outcome": "YIELDED", "first_seen": fresh},
        "b": {"name": "b", "outcome": "NAMED_ONLY", "first_seen": old}}}), "utf-8")
    (desk / "data" / "universe" / "universe.json").write_text(json.dumps({
        "XAUUSD": {"_provenance": {"bars": {"at": fresh}}},
        "EURUSD": {"_provenance": {"bars": {"at": old}}}}), "utf-8")
    p = cap.ap1(desk, ROOT, NOW)
    assert p["measured"] and p["status"] == "MET"
    assert p["cells_opened_7d"] == 2 and p["frontier_vectors_hunted"] == 1
    assert p["universe_symbols"] == 2 and p["universe_symbols_new_7d"] == 1


def test_ap3_is_the_attribution_share(tmp_path: Path) -> None:
    desk = _desk(tmp_path)
    (desk / "reports" / "attribution_chain.json").write_text(
        json.dumps({"deals": 4, "attributed": 3, "share": 0.75, "unmatched_deals": [9]}), "utf-8")
    p = cap.ap3(desk)
    assert p["status"] == "PARTIAL" and p["measured"] and p["share"] == 0.75
    (desk / "reports" / "attribution_chain.json").write_text(
        json.dumps({"deals": 4, "attributed": 4, "share": 1.0}), "utf-8")
    assert cap.ap3(desk)["status"] == "MET"
    (desk / "reports" / "attribution_chain.json").write_text(
        json.dumps({"deals": 0, "attributed": 0, "share": None}), "utf-8")
    p = cap.ap3(desk)
    assert p["status"] == "MISSING" and p["measured"] is False, "no deals is no measurement"


def test_ap4_needs_missions_issued_and_candidates_tagged(tmp_path: Path) -> None:
    desk = _desk(tmp_path)
    (desk / "reports" / "research_missions.json").write_text(json.dumps({"missions": [
        {"id": "m1", "at": (NOW - timedelta(days=1)).isoformat()}]}), "utf-8")
    (desk / "data" / "hypotheses" / "miner_candidates.json").write_text(json.dumps({
        "candidates": [{"symbol": "XAUUSD", "mission": "m1"}, {"symbol": "EURUSD"}]}), "utf-8")
    p = cap.ap4(desk, NOW)
    assert p["status"] == "MET" and p["issued_7d"] == 1 and p["candidates_tagged"] == 1


def test_ap5_counts_arms_with_a_verdict_and_rent_retirements(tmp_path: Path) -> None:
    desk = _desk(tmp_path)
    (desk / "reports" / "RESEARCH_BANDIT.json").write_text(json.dumps({"arms": {
        "reddit": {"verdict": "KEEP"}, "kimi": {}}}), "utf-8")
    (desk / "reports" / "MODULE_RENT.json").write_text(json.dumps({"modules": {}, "retire": []}),
                                                       "utf-8")
    p = cap.ap5(desk)
    assert p["status"] == "MET" and p["arms_with_verdict"] == 1 and p["rent_retire_named"] == 0


def test_the_ledger_takes_the_measured_verdicts(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.json"
    ledger.write_text(json.dumps({"acceptance_properties": [
        {"id": "AP3", "name": "x", "status": "MISSING", "measure": "m", "evidence": []}]}), "utf-8")
    doc = {"at": "t", "properties": {"AP3": {"status": "PARTIAL", "measured": True,
                                             "share": 0.75, "why": "w"}}}
    assert cap.patch_ledger(doc, ledger) == 1
    row = json.loads(ledger.read_text("utf-8"))["acceptance_properties"][0]
    assert row["status"] == "PARTIAL"
    assert "MEASURED" in row["evidence"][0] and "0.75" in row["evidence"][0]
