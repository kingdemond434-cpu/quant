"""An orphaned, silent lock holder is reclaimed; a live or heartbeating one never is (2026-11-05).

pid 30100 (pythonw, 2.44 GB, its parent 14376 gone, 0 CPU) held data/.job_locks/pf_allocator.json
from 06:50Z; `_owner_state` read any live pid as ALIVE, so every MT5-AllocatorFast pass stood down
for ~4.5 h and exited 0, reading green. The Auditor's five criteria are pinned here.
"""
from __future__ import annotations

import json
import socket
import sys
import time
import types
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import job_lock as JL  # noqa: E402


class _Proc:
    def __init__(self, pid: int, ctime: float, ppid: int) -> None:
        self.pid, self._ctime, self._ppid = pid, ctime, ppid

    def create_time(self) -> float:
        return self._ctime

    def ppid(self) -> int:
        return self._ppid

    def is_running(self) -> bool:
        return True


def _fake_psutil(procs: dict[int, _Proc]) -> types.SimpleNamespace:
    class NoSuchProcess(Exception):
        pass

    def process(pid: int) -> _Proc:
        if pid not in procs:
            raise NoSuchProcess(pid)
        return procs[pid]
    return types.SimpleNamespace(Process=process, NoSuchProcess=NoSuchProcess,
                                 pid_exists=lambda pid: pid in procs)


@pytest.fixture
def locks(tmp_path, monkeypatch):
    monkeypatch.setattr(JL, "LOCK_ROOT", tmp_path)
    monkeypatch.setattr(JL, "record_spec", lambda *a, **k: None)
    monkeypatch.setattr(JL, "peak_rss_mb", lambda: None)
    return tmp_path


def _lock(path: Path, *, pid: int, ctime: float | None, beat_age_s: float) -> None:
    path.write_text(json.dumps({
        "token": "held", "pid": pid, "host": socket.gethostname(),
        "started_at": "2026-11-05T06:50:58+00:00", "create_time": ctime,
        "heartbeat_at": time.time() - beat_age_s}), "utf-8")


def test_an_orphaned_silent_holder_is_reclaimed(locks, monkeypatch) -> None:
    now = time.time()
    monkeypatch.setitem(sys.modules, "psutil", _fake_psutil({30100: _Proc(30100, now - 16000,
                                                                           14376)}))
    monkeypatch.setattr(JL, "_owner_state", lambda p: "ALIVE")
    path = locks / "pf_allocator.json"
    _lock(path, pid=30100, ctime=now - 16000, beat_age_s=4.5 * 3600)
    assert "parent 14376" in (JL.orphan_stale(path, 3600) or "")
    with JL.exclusive_job("pf_allocator", heartbeat_stale_s=3600) as go:
        assert go is True


def test_a_live_slow_holder_is_refused_orphan_or_not_while_it_beats(locks, monkeypatch) -> None:
    now = time.time()
    procs = {7: _Proc(7, now - 900, 1), 1: _Proc(1, now - 99999, 0)}
    monkeypatch.setitem(sys.modules, "psutil", _fake_psutil(procs))
    monkeypatch.setattr(JL, "_owner_state", lambda p: "ALIVE")
    path = locks / "pf_allocator.json"
    _lock(path, pid=7, ctime=now - 900, beat_age_s=2 * 3600)     # silent, but its parent lives
    assert JL.orphan_stale(path, 3600) is None
    with JL.exclusive_job("pf_allocator", heartbeat_stale_s=3600) as go:
        assert go is False
    assert JL.LAST_REFUSAL["pf_allocator"]["pid"] == 7
    procs.pop(1)                                                 # orphaned, but still beating
    _lock(path, pid=7, ctime=now - 900, beat_age_s=30)
    assert JL.orphan_stale(path, 3600) is None
    with JL.exclusive_job("pf_allocator", heartbeat_stale_s=3600) as go:
        assert go is False
    # a job that never opted into heartbeats is untouched by this rule
    _lock(path, pid=7, ctime=now - 900, beat_age_s=9 * 3600)
    with JL.exclusive_job("pf_allocator") as go:
        assert go is False


def test_a_reused_pid_is_reclaimed(locks, monkeypatch) -> None:
    now = time.time()
    procs = {30100: _Proc(30100, now - 60, 1), 1: _Proc(1, now - 99999, 0)}
    monkeypatch.setitem(sys.modules, "psutil", _fake_psutil(procs))
    monkeypatch.setattr(JL, "_owner_state", lambda p: "ALIVE")
    path = locks / "pf_allocator.json"
    _lock(path, pid=30100, ctime=now - 16000, beat_age_s=4.5 * 3600)
    assert "reused" in (JL.orphan_stale(path, 3600) or "")
    with JL.exclusive_job("pf_allocator", heartbeat_stale_s=3600) as go:
        assert go is True


def test_the_holder_beats_and_a_refused_allocator_pass_reads_red(locks, monkeypatch) -> None:
    monkeypatch.setattr(JL, "HEARTBEAT_EVERY_S", 0.0)
    with JL.exclusive_job("beater") as go:
        assert go
        before = json.loads((locks / "beater.json").read_text("utf-8"))["heartbeat_at"]
        time.sleep(0.01)
        assert JL.heartbeat("beater") is True
        after = json.loads((locks / "beater.json").read_text("utf-8"))["heartbeat_at"]
        assert after > before
    assert JL.heartbeat("beater") is False                       # released: nothing to stamp
    src = (_DESK / "research" / "pf_allocator.py").read_text(encoding="utf-8")
    assert "heartbeat_stale_s=LOCK_HEARTBEAT_STALE_S" in src
    assert "reason, rc = lock_refusal(holder)" in src and "return rc" in src
    assert "LOCK_REFUSED_EXIT = 3" in src
    hc = (_DESK / "research" / "hourly_cycle.py").read_text(encoding="utf-8")
    assert '"pf_allocator": {3: "LOCK_REFUSED"}' in hc


def test_a_refused_pass_is_red_only_when_the_holder_is_silent_or_unreadable() -> None:
    """#752 audit MF: the ordinary overlap with a heartbeating pass is BUSY and exits 0; a holder
    silent past LOCK_BUSY_HEARTBEAT_S that cannot be reclaimed, or an unreadable lock, exits 3;
    a memory stand-down is NO_ROOM, never a lock refusal."""
    from research import pf_allocator as pa
    assert pa.lock_refusal({"pid": 7, "heartbeat_age_s": 40.0, "owner": "ALIVE"}) == ("BUSY", 0)
    assert pa.lock_refusal({"pid": 7, "heartbeat_age_s": pa.LOCK_BUSY_HEARTBEAT_S + 1,
                            "owner": "ALIVE"}) == ("LOCK_REFUSED", 3)
    assert pa.lock_refusal({"owner": "ALIVE", "lock": "unreadable"}) == ("LOCK_REFUSED", 3)
    assert pa.lock_refusal({"reason": "NO_ROOM", "need_mb": 900, "free_mb": 100}) == (
        "NO_ROOM", 0)


def test_the_memory_refusal_is_named_no_room(locks, monkeypatch) -> None:
    monkeypatch.setattr(JL, "measured_need_mb", lambda name, mb: (mb, "declared"))
    monkeypatch.setattr(JL, "free_mb", lambda: 10)
    monkeypatch.setattr(JL, "admit_patience_s", lambda: 0.0)
    monkeypatch.setattr(JL.time, "sleep", lambda s: None)
    with JL.exclusive_job("pf_allocator", need_mb=5000) as go:
        assert go is False
    assert JL.LAST_REFUSAL["pf_allocator"]["reason"] == "NO_ROOM"
    with JL.exclusive_job("pf_allocator") as go:              # a later admitted pass clears it
        assert go is True
    assert "pf_allocator" not in JL.LAST_REFUSAL
