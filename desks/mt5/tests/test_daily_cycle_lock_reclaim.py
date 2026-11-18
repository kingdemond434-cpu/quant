"""A chain killed while holding the daily lock (MT5-Daily at PT10H, 2026-11-11, pid 21524)
leaves its owner sidecar and a `chain_lock: held` stamp behind. The OS lock died with it; the
next chain must say in the log and the stamp WHO it took the lock over from."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for p in (str(_DESK), str(_DESK / "research")):
    if p not in sys.path:
        sys.path.insert(0, p)

import daily_cycle  # noqa: E402


@pytest.fixture
def iso(tmp_path, monkeypatch):
    monkeypatch.setattr(daily_cycle, "STAMP", tmp_path / "daily_cycle_state.json")
    monkeypatch.setattr(daily_cycle, "LOG", tmp_path / "daily_cycle.log")
    return tmp_path


def _sidecar(doc: dict) -> None:
    p = daily_cycle._owner_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc), encoding="utf-8")


def test_a_dead_holders_sidecar_is_named_on_acquire(iso) -> None:
    _sidecar({"pid": 21524, "create_time": 1.0, "at": "2026-11-10T21:50:01+00:00",
              "last_progress": "2026-11-11T01:30:10+00:00"})
    lk = daily_cycle.ChainLock()
    try:
        assert lk.try_acquire()
        log = daily_cycle.LOG.read_text(encoding="utf-8")
        assert "chain lock RECLAIMED from dead holder pid 21524" in log
        assert "2026-11-11T01:30:10+00:00" in log
        rec = lk.record()
        assert rec["state"] == "held" and rec["since"]
        assert rec["reclaimed_from"]["pid"] == 21524
        assert rec["reclaimed_from"]["last_progress"] == "2026-11-11T01:30:10+00:00"
        # the sidecar now names this process, not the dead one
        assert json.loads(daily_cycle._owner_path().read_text())["pid"] != 21524
    finally:
        lk.close()


def test_a_clean_start_reclaims_nothing(iso) -> None:
    lk = daily_cycle.ChainLock()
    try:
        assert lk.try_acquire()
        assert "reclaimed_from" not in lk.record()
        assert not daily_cycle.LOG.exists() or "RECLAIMED" not in daily_cycle.LOG.read_text()
    finally:
        lk.close()


@pytest.mark.parametrize("doc", ["not json", "[]", '{"pid": "x"}', '{"pid": 0}'])
def test_an_unreadable_sidecar_is_not_a_reclaim(iso, doc) -> None:
    p = daily_cycle._owner_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(doc, encoding="utf-8")
    lk = daily_cycle.ChainLock()
    try:
        assert lk.try_acquire()
        assert "reclaimed_from" not in lk.record()
    finally:
        lk.close()


@pytest.mark.skipif(sys.platform == "win32", reason="SIGKILLs a POSIX child holding flock")
def test_a_killed_holder_is_reclaimed_and_named(iso) -> None:
    script = (
        "import sys, time\n"
        "from pathlib import Path\n"
        "sys.path[:0] = [sys.argv[1], sys.argv[2]]\n"
        "import daily_cycle\n"
        "daily_cycle.STAMP = Path(sys.argv[3])\n"
        "daily_cycle.LOG = Path(sys.argv[4])\n"
        "lk = daily_cycle.ChainLock()\n"
        "assert lk.try_acquire()\n"
        "print('ready', flush=True)\n"
        "time.sleep(300)\n")
    proc = subprocess.Popen([sys.executable, "-c", script, str(_DESK), str(_DESK / "research"),
                             str(daily_cycle.STAMP), str(daily_cycle.LOG)],
                            stdout=subprocess.PIPE, text=True)
    try:
        assert proc.stdout is not None and proc.stdout.readline().strip() == "ready"
        held = daily_cycle.ChainLock()
        assert not held.try_acquire(), "a live holder keeps the lock"
        proc.kill()                     # what a PT10H kill does: no close(), sidecar left behind
        proc.wait(timeout=30)
        assert daily_cycle._owner_path().exists()
        lk = daily_cycle.ChainLock()
        try:
            assert lk.try_acquire()
            assert lk.record()["reclaimed_from"]["pid"] == proc.pid
            assert f"RECLAIMED from dead holder pid {proc.pid}" in \
                daily_cycle.LOG.read_text(encoding="utf-8")
        finally:
            lk.close()
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=30)
        if proc.stdout is not None:
            proc.stdout.close()
