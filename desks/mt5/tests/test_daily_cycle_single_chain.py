"""One daily chain at a time: the hourly leg stands down while MT5-Daily holds the chain.

`MT5-Daily` runs `daily_cycle.py` for hours with no deadline; the `forward` department resident's
hourly `daily` leg starts the same file under a 900 s kill on every pass. Without a lock each such
pass re-ran the step MT5-Daily was executing and was killed before stamping it, and after 00:00 UTC
it began the new day while MT5-Daily's old-date stamp writes kept resetting it. These pin:
  * a bounded caller (HOURLY_PLAN set) runs NOTHING while another chain holds the lock;
  * an unbounded caller (MT5-Daily) waits, then re-reads the stamp, so it never repeats a step the
    holder completed and never loses one;
  * an unbounded caller whose wait runs out still runs every step -- the lock removes duplicates,
    never a run;
  * `--step` (the markout clock) is untouched by the lock;
  * the lock lives in the gitignored per-machine lock directory beside the stamp.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for p in (str(_DESK), str(_DESK / "research")):
    if p not in sys.path:
        sys.path.insert(0, p)

import daily_cycle  # noqa: E402


@pytest.fixture
def cyc(tmp_path, monkeypatch):
    monkeypatch.setattr(daily_cycle, "STAMP", tmp_path / "daily_cycle_state.json")
    monkeypatch.setattr(daily_cycle, "LOG", tmp_path / "daily_cycle.log")
    calls: list[str] = []

    def step(name):
        def fn():
            calls.append(name)
        return fn

    monkeypatch.setattr(daily_cycle, "STEPS", tuple((n, step(n)) for n in ("a", "b", "c")))
    return type("C", (), {"calls": calls, "stamp": tmp_path / "daily_cycle_state.json"})


def _hold():
    handle = daily_cycle._try_lock(daily_cycle._lock_path())
    assert handle is not None, "the test could not take the chain lock itself"
    return handle


def test_a_bounded_caller_runs_nothing_while_another_chain_holds_the_lock(cyc, monkeypatch):
    monkeypatch.setenv("HOURLY_PLAN", "dept:forward")
    held = _hold()
    try:
        assert daily_cycle.main([]) == 0
    finally:
        held.close()
    assert cyc.calls == []
    assert not cyc.stamp.exists(), "a caller that stood down must not touch the day's stamp"


def test_a_bounded_caller_runs_the_chain_when_nothing_holds_it(cyc, monkeypatch):
    monkeypatch.setenv("HOURLY_PLAN", "dept:forward")
    assert daily_cycle.main([]) == 0
    assert cyc.calls == ["a", "b", "c"]


def test_the_unbounded_caller_waits_then_runs_only_what_the_holder_left(cyc, monkeypatch):
    """MT5-Daily must never lose the day to a short hourly run that held the lock at 23:50, and
    must not repeat what that run finished: it re-reads the stamp after it is admitted."""
    monkeypatch.delenv("HOURLY_PLAN", raising=False)
    today = datetime.now(UTC).date().isoformat()
    held = {"h": _hold()}

    def holder_finishes(_s):
        if held["h"] is not None:
            cyc.stamp.write_text(json.dumps({"last_run": today,
                                             "steps": {"a": {"ok": True, "seconds": 1.0}}}),
                                 encoding="utf-8")
            held["h"].close()
            held["h"] = None

    monkeypatch.setattr(daily_cycle.time, "sleep", holder_finishes)
    try:
        assert daily_cycle.main([]) == 0
    finally:
        if held["h"] is not None:
            held["h"].close()
    assert cyc.calls == ["b", "c"]
    stamp = json.loads(cyc.stamp.read_text(encoding="utf-8"))
    assert set(stamp["steps"]) == {"a", "b", "c"}


def test_an_unbounded_caller_whose_wait_runs_out_still_runs_every_step(cyc, monkeypatch):
    monkeypatch.delenv("HOURLY_PLAN", raising=False)
    monkeypatch.setattr(daily_cycle, "UNBOUNDED_WAIT_S", 30.0)
    monkeypatch.setattr(daily_cycle.time, "sleep", lambda _s: None)
    held = _hold()
    try:
        assert daily_cycle.main([]) == 0
    finally:
        held.close()
    assert cyc.calls == ["a", "b", "c"]


def test_the_single_step_clock_ignores_the_chain_lock(cyc, monkeypatch):
    """`--step markout` is the live-truth clock that exists BECAUSE the chain is long; the lock
    must never make it wait for, or stand down behind, the chain."""
    monkeypatch.setenv("HOURLY_PLAN", "dept:forward")
    held = _hold()
    try:
        assert daily_cycle.main(["--step", "b"]) == 0
    finally:
        held.close()
    assert cyc.calls == ["b"]


def test_the_lock_is_a_gitignored_per_machine_file_beside_the_stamp():
    real = daily_cycle.STAMP.parent / ".job_locks" / "daily_cycle.lock"
    root = _DESK.parents[1]
    rel = real.relative_to(root).as_posix()
    r = subprocess.run(["git", "check-ignore", "-q", "--no-index", rel], cwd=root,
                       capture_output=True, text=True, check=False)
    assert r.returncode == 0, f"{rel} must be gitignored: a lock names a PID on one machine"
