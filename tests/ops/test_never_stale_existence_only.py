"""never_stale escalates the scheduler when process_health only LISTED the task directory.

Audit 2026-09-30: on a schtasks timeout process_health falls back to the task directory
(`existence_only`), which proves a task exists and nothing about how it ran. The watchdog read
that as a scheduler reading and escalated nothing, so the timeout reached nobody.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ops"))

import never_stale as ns  # noqa: E402


@pytest.mark.parametrize("sched,escalates", [
    ({"read": True}, False),
    ({"read": False, "existence_only": True, "why": "schtasks timed out"}, True),
    ({"read": False, "why": "schtasks timed out"}, True),
])
def test_existence_only_is_not_a_scheduler_reading(tmp_path: Path,
                                                   monkeypatch: pytest.MonkeyPatch,
                                                   sched: dict, escalates: bool) -> None:
    health = tmp_path / "process_health.json"
    health.write_text(json.dumps({"scheduler": sched, "processes": []}), encoding="utf-8")
    monkeypatch.setattr(ns, "HEALTH", health)
    monkeypatch.setattr(ns, "_capital_faults", lambda: [])
    doc = ns.run(apply=False)
    rows = [e for e in doc["escalated"] if e["task"] == "(scheduler)"]
    assert bool(rows) is escalates
    if sched.get("existence_only"):
        assert "existence-only" in rows[0]["why"] and rows[0]["verdict"] == "UNMEASURED"


@pytest.mark.parametrize("status,escalates", [
    ("OK schtasks", False),
    ("OK schtasks (brief: last run and last result UNMEASURED)", False),
    ("UNMEASURED: schtasks /query timed out after 45s", True),
])
def test_lives_scheduler_status_is_read_the_same_way(tmp_path: Path,
                                                     monkeypatch: pytest.MonkeyPatch,
                                                     status: str, escalates: bool) -> None:
    """LIVE's process_health publishes `scheduler_status`, not a `scheduler` block; an
    inventory it could not read escalates once, and its SCHEDULER_UNMEASURED rows are skipped."""
    health = tmp_path / "process_health.json"
    health.write_text(json.dumps({"scheduler_status": status, "processes": [
        {"name": "MT5-A", "verdict": "SCHEDULER_UNMEASURED", "why": status}]}),
        encoding="utf-8")
    monkeypatch.setattr(ns, "HEALTH", health)
    monkeypatch.setattr(ns, "_capital_faults", lambda: [])
    doc = ns.run(apply=False)
    assert [e["task"] for e in doc["escalated"]] == (["(scheduler)"] if escalates else [])
    assert doc["acted"] == []
