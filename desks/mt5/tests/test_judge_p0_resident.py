"""Judge P0 (2026-11-25): the resident ends a sweep whose own watchdog went quiet, and an idle
multi-process tree reads idle.

Sweep pid 18528: GAUNTLET_HEARTBEAT.json last written 12:56:39Z (beat 30 s), its 16-19-process
tree burning 0.1 s CPU per 5 s -- 0.02 core, exactly the flat NO_PROGRESS_CORES, which `>=` read
as progress. Neither the sweep's watchdog nor the resident killed it; the judge published nothing.
"""
from __future__ import annotations

import json
import socket
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import run_sharded_gauntlet as runner


@pytest.fixture(autouse=True)
def _isolated(monkeypatch, tmp_path):
    for name, fn in (("RESIDENT_STATE", "JUDGE_RESIDENT.json"),
                     ("RESIDENT_MEMORY", "JUDGE_RESIDENT_MEMORY.json"),
                     ("SWEEP_PHASE", "JUDGE_SWEEP_PHASE.json"),
                     ("HEARTBEAT", "GAUNTLET_HEARTBEAT.json"), ("STALL", "GAUNTLET_STALL.json"),
                     ("PHASE_TIMES", "judge_phase_times.json")):
        monkeypatch.setattr(runner, name, tmp_path / fn)
    monkeypatch.setattr(runner, "_PHASE_DOC", {})
    monkeypatch.setattr(runner, "_PROGRESS", {})
    monkeypatch.setattr(runner, "MERGE_SNAPSHOT", tmp_path / "snap")
    monkeypatch.setattr(runner, "MERGE_OUTPUTS", (tmp_path / "ug.json", tmp_path / "us.json"))
    monkeypatch.setattr(runner, "_lock_root", lambda: tmp_path / "locks")
    monkeypatch.setattr(runner, "record_resume_delay", lambda *a, **k: None)
    monkeypatch.setattr(runner, "_sweep_env", lambda: {})
    (tmp_path / "locks").mkdir()
    runner._ABORT.clear()


# ------------------------------------------------------------------ the idle threshold
def _tree(n: int, cpu_each: float) -> dict:
    return {"cpu": dict.fromkeys(range(1, n + 1), cpu_each), "rss_mb": 1.0, "procs": n}


def test_an_idle_sixteen_process_tree_at_the_flat_threshold_now_reads_idle() -> None:
    tr = runner._TreeProgress(0.0)
    tr.update(_tree(16, 0.0), 1.0)
    # the box: 0.1 cpu-s per 5 s over the whole tree = 0.02 core
    assert tr.update(_tree(16, 0.1 / 16), 6.0) is False


def test_a_one_process_tree_reads_exactly_as_before() -> None:
    tr = runner._TreeProgress(0.0)
    tr.update(_tree(1, 0.0), 1.0)
    assert tr.update(_tree(1, 0.1), 6.0) is True          # 0.02 core: progress, as always
    assert tr.update(_tree(1, 0.1 + 0.05), 11.0) is False  # 0.01 core: idle, as always


def test_real_work_in_a_big_tree_is_always_progress() -> None:
    tr = runner._TreeProgress(0.0)
    tr.update(_tree(19, 0.0), 1.0)
    one_core = {"cpu": {**dict.fromkeys(range(2, 20), 0.0), 1: 5.0}, "rss_mb": 1.0, "procs": 19}
    assert tr.update(one_core, 6.0) is True                # a busy merge among idle workers
    assert tr.threshold(10_000) == runner.NO_PROGRESS_TREE_CAP_CORES


# ------------------------------------------------------------- the child's own heartbeat
class _Child:
    pid = 4242

    def __init__(self) -> None:
        self.polls = 0

    def wait(self, timeout=None):
        self.polls += 1
        if self.polls > 50:
            return 0
        raise subprocess.TimeoutExpired("sweep", timeout or 0)


def _hb(pid: int, age_s: float, status: str = "RUNNING") -> None:
    beat = datetime.now(UTC) - timedelta(seconds=age_s)
    runner._write_json_atomic(runner.HEARTBEAT, {
        "pid": pid, "status": status, "beat_utc": beat.isoformat(), "beat_every_s": 30.0,
        "phase": "prewarm", "started_utc": (beat - timedelta(hours=8)).isoformat()})


def _launch(monkeypatch, child: _Child) -> list[int]:
    killed: list[int] = []
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: child)
    monkeypatch.setattr(runner, "_kill_sweep_tree",
                        lambda pid: killed.append(pid) or {"killed": 17, "orphans": []})
    return killed


def _busy():
    t = [0.0]

    def sample(pid):
        t[0] += 60.0
        return {"cpu": {pid: t[0]}, "rss_mb": 1.0, "procs": 1}   # one busy core throughout
    return sample


def test_a_stale_running_heartbeat_is_a_hang_even_when_the_tree_looks_busy(monkeypatch) -> None:
    child = _Child()
    killed = _launch(monkeypatch, child)
    _hb(child.pid, age_s=runner.heartbeat_hang_s(30.0) + 60)
    lock = runner._lock_root() / "certification_lane.json"
    lock.write_text(json.dumps({"pid": child.pid, "host": socket.gethostname()}))
    clock = iter(float(i) for i in range(10_000))
    rc = runner._one_sweep_child(None, poll_s=0.0, clock=lambda: next(clock), sampler=_busy())
    assert rc == runner.RESIDENT_HANG_RC and killed == [child.pid]
    st = json.loads(runner.STALL.read_text("utf-8"))
    assert st["reason"] == "resident_kill" and "watchdog is wedged" in st["detail"]
    assert not lock.exists()                         # the next sweep does not wait behind it
    assert json.loads(runner.HEARTBEAT.read_text("utf-8"))["status"] == "KILLED_BY_RESIDENT"


def test_a_heartbeat_inside_the_window_or_of_another_pid_never_kills(monkeypatch) -> None:
    for pid, age in ((4242, runner.heartbeat_hang_s(30.0) - 120), (999, 10 ** 6)):
        child = _Child()
        killed = _launch(monkeypatch, child)
        _hb(pid, age_s=age)
        clock = iter(float(i) for i in range(10_000))
        assert runner._one_sweep_child(None, poll_s=0.0, clock=lambda c=clock: next(c),
                                       sampler=_busy()) == 0
        assert killed == []


def test_a_finished_sweep_still_alive_long_after_is_hung_on_its_way_out(monkeypatch) -> None:
    child = _Child()
    killed = _launch(monkeypatch, child)
    _hb(child.pid, age_s=runner.EXIT_HANG_S + 60, status="DONE")
    clock = iter(float(i) for i in range(10_000))
    assert runner._one_sweep_child(None, poll_s=0.0, clock=lambda: next(clock),
                                   sampler=_busy()) == runner.RESIDENT_HANG_RC
    assert killed == [child.pid]


def test_the_hang_window_is_derived_from_the_beat() -> None:
    assert runner.heartbeat_hang_s(30.0) == max(3 * runner.HEARTBEAT_STALE_S, 10 * 30 + 300)
    assert runner.heartbeat_hang_s(None) == runner.heartbeat_hang_s(runner.WATCHDOG_BEAT_S)
    assert runner.heartbeat_hang_s("junk") == runner.heartbeat_hang_s(runner.WATCHDOG_BEAT_S)
