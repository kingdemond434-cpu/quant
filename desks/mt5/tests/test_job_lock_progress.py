"""ALIVE IS NOT PROGRESSING: a lock owner whose CPU time stops advancing is WEDGED, by name.

2026-10-29: the merge_hypotheses lock was held 15 h by a living pid at ~2 GB and the docket's
converter refused behind it every hour, reading only "owner ALIVE". The owner is still never
robbed; it is named RED in JOB_LOCK_HEALTH.json so the stop is somebody's job.
"""
from __future__ import annotations

import json
import socket
import sys
from contextlib import suppress
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "research"))
sys.path.insert(0, str(BASE))

import job_lock as J  # noqa: E402


@pytest.fixture()
def lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(J, "LOCK_ROOT", tmp_path)
    monkeypatch.setattr(J, "HEALTH_REPORT", tmp_path / "JOB_LOCK_HEALTH.json")
    monkeypatch.setattr(J, "STOPS_LEDGER", tmp_path / "JOB_LOCK_STOPS.jsonl")
    path = tmp_path / "merge_hypotheses.json"
    path.write_text(json.dumps({"token": "t1", "pid": 18040, "host": socket.gethostname(),
                                "started_at": "2026-10-29T03:14:56+00:00"}), "utf-8")
    return path


def test_an_owner_whose_cpu_never_moves_is_wedged_after_the_window(lock: Path) -> None:
    first = J.owner_progress(lock, now=0.0, cpu_of=lambda pid: 500.0)
    assert first["status"] == "UNMEASURED"
    idle = J.owner_progress(lock, now=600.0, cpu_of=lambda pid: 500.2)
    assert idle["status"] == "IDLE"
    wedged = J.owner_progress(lock, now=J.WEDGED_AFTER_S + 60.0, cpu_of=lambda pid: 500.4)
    assert wedged["status"] == "WEDGED" and wedged["pid"] == 18040


def test_an_owner_that_keeps_working_is_never_wedged(lock: Path) -> None:
    J.owner_progress(lock, now=0.0, cpu_of=lambda pid: 10.0)
    for k in range(1, 6):
        doc = J.owner_progress(lock, now=k * J.WEDGED_AFTER_S, cpu_of=lambda pid, k=k: 10.0 + k * 60)
        assert doc["status"] == "PROGRESSING"


def test_a_new_owner_starts_afresh(lock: Path) -> None:
    J.owner_progress(lock, now=0.0, cpu_of=lambda pid: 5.0)
    lock.write_text(json.dumps({"token": "t2", "pid": 18041, "host": socket.gethostname()}),
                    "utf-8")
    assert J.owner_progress(lock, now=10 * J.WEDGED_AFTER_S,
                            cpu_of=lambda pid: 5.0)["status"] == "UNMEASURED"


def test_unreadable_cpu_is_unmeasured_never_ok(lock: Path) -> None:
    assert J.owner_progress(lock, now=0.0, cpu_of=lambda pid: None)["status"] == "UNMEASURED"


def test_a_contender_publishes_red_and_still_does_not_steal(lock: Path, monkeypatch) -> None:
    import os
    import time
    monkeypatch.setattr(J, "_owner_state", lambda path: "ALIVE")
    old = time.time() - J.STALE_SECONDS - 60
    os.utime(lock, (old, old))
    cpu = iter([100.0, 100.0])
    monkeypatch.setattr(J, "_owner_cpu_s", lambda pid: next(cpu))
    # First contender records the owner; the second, past the window, finds it wedged.
    with J.exclusive_job("merge_hypotheses") as got:
        assert got is False
    side = J._progress_path(lock)
    rec = json.loads(side.read_text("utf-8"))
    rec["cpu_at"] -= J.WEDGED_AFTER_S + 60
    side.write_text(json.dumps(rec), "utf-8")
    with J.exclusive_job("merge_hypotheses") as got:
        assert got is False, "a living owner is never robbed, wedged or not"
    health = json.loads(J.HEALTH_REPORT.read_text("utf-8"))
    assert health["status"] == "RED" and health["wedged"] == ["merge_hypotheses"]
    assert lock.exists()
    # The owner dies; the next contender reclaims, and the RED row clears on acquisition.
    monkeypatch.setattr(J, "_owner_state", lambda path: "DEAD")
    with J.exclusive_job("merge_hypotheses") as got:
        assert got is True
        health = json.loads(J.HEALTH_REPORT.read_text("utf-8"))
        assert health["status"] == "OK"
        assert health["locks"]["merge_hypotheses"]["status"] == "ACQUIRED"
    with suppress(OSError):
        side.unlink()


def test_a_wedged_row_clears_when_its_owner_releases(lock: Path, monkeypatch) -> None:
    lock.unlink()
    J._publish_health("merge_hypotheses", {"status": "WEDGED", "pid": 1, "why": "x"})
    with J.exclusive_job("merge_hypotheses") as got:
        assert got is True
    health = json.loads(J.HEALTH_REPORT.read_text("utf-8"))
    assert health["status"] == "OK"
    assert health["locks"]["merge_hypotheses"]["status"] in ("RELEASED", "ACQUIRED")
