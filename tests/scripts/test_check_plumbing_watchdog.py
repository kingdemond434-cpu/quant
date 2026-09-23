"""THE FENCE THAT MAKES SILENCE IMPOSSIBLE.

The watchdog can only report. This fence is what makes the report cost something: while a
plumbing defect is older than its own escalation window, the law gate does not pass, and
repairing the pipes becomes the cheapest way to ship anything else.

The property that matters most here is the one that is easiest to get wrong: AN ABSENT REPORT IS
A BREACH. A watchdog that stopped running reports no defects because it reports nothing, and a
fence that read that as health would convert the loudest failure the desk can have into its
quietest. Three tests pin it -- missing file, unreadable file, stale file.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# LOADED BY PATH, not by `import scripts.<name>`: `tests/scripts/__init__.py` makes a REGULAR
# package called `scripts`, and a regular package beats the repo root's namespace package
# (`scripts/` has no `__init__.py`) wherever it sits on the path -- so `import scripts.X` resolves
# to the TEST directory. The same route `test_check_conversion_debt` takes, for the same reason.
_SPEC = importlib.util.spec_from_file_location(
    "check_plumbing_watchdog", ROOT / "scripts" / "check_plumbing_watchdog.py")
assert _SPEC and _SPEC.loader
fence = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(fence)

NOW = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)


def _report(tmp_path: Path, doc: object) -> Path:
    p = tmp_path / "PLUMBING_WATCHDOG.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    return p


def test_an_absent_report_is_itself_a_breach(tmp_path: Path) -> None:
    doc = fence.check(tmp_path / "nothing.json", NOW)
    assert doc["ok"] is False and doc["measured"] is False
    assert doc["breaches"][0]["check"] == "watchdog_artifact"
    assert "silence" in doc["breaches"][0]["why"]
    assert doc["breaches"][0]["repair"]


def test_an_unreadable_report_is_a_breach_not_a_pass(tmp_path: Path) -> None:
    p = tmp_path / "PLUMBING_WATCHDOG.json"
    p.write_text("{not json", encoding="utf-8")
    assert fence.check(p, NOW)["ok"] is False


def test_a_report_that_is_not_a_document_is_a_breach(tmp_path: Path) -> None:
    p = _report(tmp_path, ["a", "list"])
    assert fence.check(p, NOW)["ok"] is False


def test_a_stale_report_is_a_breach_because_the_watchdog_itself_stopped(tmp_path: Path) -> None:
    p = _report(tmp_path, {"at": (NOW - timedelta(hours=9)).isoformat(), "defects": [],
                           "n_defects": 0})
    doc = fence.check(p, NOW)
    assert doc["ok"] is False
    assert doc["breaches"][0]["check"] == "watchdog_artifact"
    assert "stopped" in doc["breaches"][0]["why"]


def test_a_report_with_no_timestamp_is_unmeasured_and_never_a_pass(tmp_path: Path) -> None:
    p = _report(tmp_path, {"defects": [], "n_defects": 0})
    doc = fence.check(p, NOW)
    assert doc["ok"] is False and "UNMEASURED" in doc["breaches"][0]["why"]


def test_a_fresh_report_with_no_defects_passes(tmp_path: Path) -> None:
    p = _report(tmp_path, {"at": (NOW - timedelta(minutes=10)).isoformat(), "defects": [],
                           "n_defects": 0, "n_escalated": 0})
    doc = fence.check(p, NOW)
    assert doc["ok"] is True and doc["breaches"] == []


def test_a_young_defect_is_published_and_does_not_yet_wedge_the_gate(tmp_path: Path) -> None:
    """The defect is loud on pass one. The GATE waits for the escalation window, so a transient
    that heals inside the hour does not block every other builder's push."""
    p = _report(tmp_path, {"at": NOW.isoformat(), "n_defects": 1, "n_escalated": 0,
                           "defects": [{"organ": "MT5-AdoptRelease", "check": "adoption_task",
                                        "age_s": 600, "escalate_after_s": 10_800,
                                        "past_escalation_window": False,
                                        "evidence": "e", "repair": "r"}]})
    doc = fence.check(p, NOW)
    assert doc["ok"] is True and doc["n_defects"] == 1


def test_a_defect_past_its_window_wedges_the_gate_with_the_evidence_and_the_repair(
        tmp_path: Path) -> None:
    p = _report(tmp_path, {"at": NOW.isoformat(), "n_defects": 1, "n_escalated": 1,
                           "defects": [{"organ": "MT5-AdoptRelease", "check": "adoption_task",
                                        "age_s": 345_600, "escalate_after_s": 10_800,
                                        "past_escalation_window": True,
                                        "evidence": "four days behind origin",
                                        "repair": "Adopt-And-Seal.ps1"}]})
    doc = fence.check(p, NOW)
    assert doc["ok"] is False
    b = doc["breaches"][0]
    assert b["organ"] == "MT5-AdoptRelease"
    assert "four days behind origin" in b["why"]
    assert b["repair"] == "Adopt-And-Seal.ps1"


def test_the_fence_is_registered_in_the_law_gate() -> None:
    """A gate that never ran is a claim the desk cannot cash (L1.49). It lives in _STATE_FENCES
    because it judges LIVE state -- the box's scheduler, process table and checkout -- which a
    clean CI clone does not have and must not be asked about."""
    spec = importlib.util.spec_from_file_location(
        "_rlg_for_test", ROOT / "scripts" / "run_law_gate.py")
    assert spec and spec.loader
    rlg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rlg)
    assert ("check_plumbing_watchdog.py", ()) in rlg._STATE_FENCES
    assert ("check_plumbing_watchdog.py", ()) not in rlg._LAW_FENCES


def test_report_only_measures_without_wedging(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setattr(fence, "check", lambda *_a, **_k: {
        "ok": False, "measured": True, "at": NOW.isoformat(), "n_defects": 3,
        "breaches": [{"organ": "x", "check": "adoption_task", "why": "w", "repair": "r"}]})
    assert fence.main(["--report-only"]) == 0
    assert fence.main([]) == 2
