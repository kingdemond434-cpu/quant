"""The silent-organ census names every silent organ and turns RED on a new one."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[2]


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "check_silent_organs", ROOT / "scripts" / "check_silent_organs.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["check_silent_organs"] = mod
    spec.loader.exec_module(mod)
    return mod


so = _load()
so.NEVER_STALE = Path("/nonexistent/NEVER_STALE.json")


def _w(path: Path, doc: object) -> Path:
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


def _inputs(tmp: Path, legs: dict, tasks: list) -> tuple[Path, Path]:
    h = _w(tmp / "process_health.json", {"at": "t", "scheduler": {"read": True},
                                         "processes": tasks})
    m = _w(tmp / "sync_marker.json", {"last_cycle": "t", **legs})
    return h, m


def test_a_leg_killed_at_its_cap_is_silent_even_with_no_status(tmp_path: Path) -> None:
    h, m = _inputs(tmp_path, {"descendants": {"exit_code": None, "timeout_s": 720},
                              "sweep": {"exit_code": 0}}, [])
    doc = so.build(health_path=h, marker_path=m)
    assert [r["organ"] for r in doc["organs"]] == ["leg:descendants"]
    assert doc["organs"][0]["verdict"] == "TIMEOUT"


def test_first_reading_has_no_baseline_and_is_not_red(tmp_path: Path) -> None:
    h, m = _inputs(tmp_path, {"x": {"status": "LEG_FAILED", "error": "boom"}},
                   [{"name": "MT5-A", "verdict": "STALE", "why": "old"},
                    {"name": "MT5-B", "verdict": "OK"}])
    doc = so.build(health_path=h, marker_path=m, previous=None)
    assert doc["status"] == "AMBER" and doc["new_silent"] == []
    assert doc["n_silent"] == 2


def test_a_new_silent_organ_turns_the_fence_red(tmp_path: Path) -> None:
    h, m = _inputs(tmp_path, {"x": {"status": "LEG_FAILED", "error": "boom"}}, [])
    first = so.build(health_path=h, marker_path=m, previous=None)
    h, m = _inputs(tmp_path, {"x": {"status": "LEG_FAILED", "error": "boom"},
                              "y": {"exit_code": None, "timeout_s": 60}}, [])
    second = so.build(health_path=h, marker_path=m, previous=first)
    assert second["status"] == "RED" and second["new_silent"] == ["leg:y"]
    streak = {r["organ"]: r["passes_silent"] for r in second["organs"]}
    assert streak == {"leg:x": 2, "leg:y": 1}


def test_recovery_is_listed_as_cleared(tmp_path: Path) -> None:
    h, m = _inputs(tmp_path, {"x": {"status": "LEG_FAILED", "error": "boom"}}, [])
    first = so.build(health_path=h, marker_path=m, previous=None)
    h, m = _inputs(tmp_path, {"x": {"exit_code": 0}}, [])
    second = so.build(health_path=h, marker_path=m, previous=first)
    assert second["status"] == "GREEN" and second["cleared"] == ["leg:x"]


def test_nothing_readable_is_unmeasured_never_zero(tmp_path: Path) -> None:
    doc = so.build(health_path=tmp_path / "a.json", marker_path=tmp_path / "b.json")
    assert doc["status"] == "UNMEASURED" and doc["n_silent"] is None


def test_an_unread_scheduler_makes_the_count_a_floor(tmp_path: Path) -> None:
    h = _w(tmp_path / "ph.json", {"scheduler": {"read": False, "why": "timed out"},
                                  "processes": []})
    m = _w(tmp_path / "sm.json", {})
    doc = so.build(health_path=h, marker_path=m)
    assert doc["n_silent"] is None and doc["n_silent_floor"] == 0
    assert "timed out" in doc["unmeasured"][0]["why"]


def test_main_exits_two_on_red(tmp_path: Path, monkeypatch) -> None:
    out = tmp_path / "SILENT_ORGANS.json"
    h, m = _inputs(tmp_path, {}, [])
    monkeypatch.setattr(so, "PROCESS_HEALTH", h)
    monkeypatch.setattr(so, "SYNC_MARKER", m)
    assert so.main(["--out", str(out)]) == 0
    _inputs(tmp_path, {"z": {"status": "MISSING", "why": "gone"}}, [])
    assert so.main(["--out", str(out)]) == so.RED_EXIT
    assert json.loads(out.read_text())["new_silent"] == ["leg:z"]


# ---------------------------------------------------------------- audit R1 / R1b / R2 (2026-09-30)
def _health(tmp: Path, rows: list, read: bool = True) -> Path:
    sched = {"read": read, "why": "" if read else "schtasks /query did not answer within 180s"}
    return _w(tmp / "process_health.json", {"at": "t", "scheduler": sched, "processes": rows})


def test_audit_R1_simulation_scheduler_timeout_never_reads_green_or_clears(tmp_path: Path) -> None:
    """3 NOT_SCHEDULED, then a scheduler timeout: the audit saw GREEN, 3 cleared, exit 0."""
    m = _w(tmp_path / "sync_marker.json", {"last_cycle": "t"})
    ns = [{"name": f"MT5-X{i}", "verdict": "NOT_SCHEDULED", "why": "absent"} for i in range(3)]
    first = so.build(health_path=_health(tmp_path, ns), marker_path=m,
                     never_stale_path=tmp_path / "none.json")
    assert first["n_silent"] == 3
    unread = [{"name": f"MT5-X{i}", "verdict": "UNMEASURED"} for i in range(3)]
    second = so.build(health_path=_health(tmp_path, unread, read=False), marker_path=m,
                      previous=first, never_stale_path=tmp_path / "none.json")
    assert second["status"] == "UNMEASURED"
    assert second["cleared"] == []
    assert second["n_silent"] is None and second["n_silent_floor"] == 3
    out = tmp_path / "SILENT_ORGANS.json"
    _w(out, first)
    so.PROCESS_HEALTH, so.SYNC_MARKER = tmp_path / "process_health.json", m
    so.NEVER_STALE = tmp_path / "none.json"
    assert so.main(["--out", str(out)]) == 0          # nothing NEW; but never GREEN
    assert json.loads(out.read_text())["status"] == "UNMEASURED"


def test_audit_R1b_carried_rows_keep_streak_and_first_seen(tmp_path: Path) -> None:
    h, m = _inputs(tmp_path, {"x": {"status": "LEG_FAILED", "error": "boom"}}, [])
    first = so.build(health_path=h, marker_path=m, never_stale_path=tmp_path / "n.json")
    second = so.build(health_path=h, marker_path=tmp_path / "gone.json", previous=first,
                      never_stale_path=tmp_path / "n.json")
    row = {r["organ"]: r for r in second["organs"]}["leg:x"]
    assert row["verdict"] == "UNMEASURED" and row["carried"] is True
    assert row["first_seen"] == first["organs"][0]["first_seen"]
    assert row["passes_silent"] == 1 and second["cleared"] == []


def test_audit_R2_a_watchdog_escalation_is_a_red_fence_item(tmp_path: Path) -> None:
    h, m = _inputs(tmp_path, {}, [{"name": "MT5-A", "verdict": "FAILING", "why": "x"}])
    ns = _w(tmp_path / "NEVER_STALE.json", {"escalated": [
        {"task": "(scheduler)", "verdict": "UNMEASURED", "diagnosis": "schtasks hung"},
        {"task": "MT5-A", "verdict": "FAILING", "diagnosis": "dup of the task row"}]})
    doc = so.build(health_path=h, marker_path=m, never_stale_path=ns)
    assert doc["fence"] == "RED" and doc["escalated"] == ["escalated:(scheduler)"]
    assert [r["organ"] for r in doc["organs"]].count("escalated:MT5-A") == 0
