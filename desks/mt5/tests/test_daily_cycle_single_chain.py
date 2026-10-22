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
v1.1 (audit of 9a08e48ac, four should-fixes):
  * a chain that fell back to running unlocked retries the lock before every step, takes it when
    it frees, and does not repeat a step another chain stamped meanwhile;
  * the stamp is re-read at every write and `last_run` never moves backwards;
  * a lock FILE that cannot be opened or locked is a logged fault, never "held": the chain runs;
  * a bounded stand-down exits EXIT_STOOD_DOWN, and the hourly leg records STOOD_DOWN, not OK.
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
        assert daily_cycle.main([]) == daily_cycle.EXIT_STOOD_DOWN
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


# ----------------------------------------------------------------------------- v1.1 should-fixes


def test_should_fix_1_the_fallback_retries_the_lock_between_steps_and_keeps_it(cyc, monkeypatch):
    """After the wait runs out the chain runs unlocked -- but only until the holder lets go. From
    the next step on it holds the lock, so an hourly leg that starts then stands down instead of
    running beside it for the rest of a nine-hour chain."""
    monkeypatch.delenv("HOURLY_PLAN", raising=False)
    monkeypatch.setattr(daily_cycle, "UNBOUNDED_WAIT_S", 30.0)
    monkeypatch.setattr(daily_cycle.time, "sleep", lambda _s: None)
    held = {"h": _hold()}
    seen: dict[str, object] = {}

    def a():
        cyc.calls.append("a")
        held["h"].close()                       # the first holder exits during step a
        held["h"] = None

    def c():
        cyc.calls.append("c")
        seen["probe"] = daily_cycle._try_lock(daily_cycle._lock_path())

    monkeypatch.setattr(daily_cycle, "STEPS", (("a", a), ("b", lambda: cyc.calls.append("b")),
                                               ("c", c)))
    try:
        assert daily_cycle.main([]) == 0
    finally:
        if held["h"] is not None:
            held["h"].close()
    assert cyc.calls == ["a", "b", "c"]
    assert seen["probe"] is None, "the fallback chain must hold the lock once it is free"
    after = daily_cycle._try_lock(daily_cycle._lock_path())
    assert after is not None, "released at the end"
    after.close()


def test_should_fix_1_an_unlocked_chain_does_not_repeat_a_step_another_chain_stamped(cyc,
                                                                                     monkeypatch):
    monkeypatch.delenv("HOURLY_PLAN", raising=False)
    monkeypatch.setattr(daily_cycle, "UNBOUNDED_WAIT_S", 30.0)
    monkeypatch.setattr(daily_cycle.time, "sleep", lambda _s: None)
    today = datetime.now(UTC).date().isoformat()
    held = _hold()                               # held for the whole chain: it stays unlocked

    def a():
        cyc.calls.append("a")
        cyc.stamp.write_text(json.dumps({"last_run": today, "steps": {
            "a": {"ok": True}, "b": {"ok": True, "by": "the other chain"}}}), encoding="utf-8")

    monkeypatch.setattr(daily_cycle, "STEPS", (("a", a), ("b", lambda: cyc.calls.append("b")),
                                               ("c", lambda: cyc.calls.append("c"))))
    try:
        assert daily_cycle.main([]) == 0
    finally:
        held.close()
    assert cyc.calls == ["a", "c"]
    steps = json.loads(cyc.stamp.read_text(encoding="utf-8"))["steps"]
    assert steps["b"].get("by") == "the other chain", "another chain's stamped step was erased"
    assert set(steps) == {"a", "b", "c"}


def test_should_fix_2_last_run_never_moves_backwards(cyc, monkeypatch):
    """A chain that began on day D and is still running after 00:00 UTC must not rewrite a
    day-D+1 stamp back to D -- that reset the new day to step one on every step it finished."""
    monkeypatch.setenv("HOURLY_PLAN", "dept:forward")

    def a():
        cyc.calls.append("a")
        cyc.stamp.write_text(json.dumps({"last_run": "2999-01-01",
                                         "steps": {"a": {"ok": True}}}), encoding="utf-8")

    monkeypatch.setattr(daily_cycle, "STEPS", (("a", a), ("b", lambda: cyc.calls.append("b"))))
    assert daily_cycle.main([]) == 0
    stamp = json.loads(cyc.stamp.read_text(encoding="utf-8"))
    assert stamp["last_run"] == "2999-01-01"
    assert set(stamp["steps"]) == {"a"}, "the later day's progress must stand untouched"
    assert "never moves backwards" in daily_cycle.LOG.read_text(encoding="utf-8")


def test_should_fix_2_a_same_day_stamp_is_merged_at_every_write(cyc, monkeypatch):
    monkeypatch.setenv("HOURLY_PLAN", "dept:forward")
    today = datetime.now(UTC).date().isoformat()

    def a():
        cyc.calls.append("a")
        cyc.stamp.write_text(json.dumps({"last_run": today, "steps": {"x": {"ok": True}}}),
                             encoding="utf-8")

    monkeypatch.setattr(daily_cycle, "STEPS", (("a", a), ("b", lambda: cyc.calls.append("b"))))
    assert daily_cycle.main([]) == 0
    assert set(json.loads(cyc.stamp.read_text(encoding="utf-8"))["steps"]) == {"x", "a", "b"}


def test_should_fix_3_an_unopenable_lock_file_is_logged_and_the_chain_still_runs(cyc, tmp_path,
                                                                                monkeypatch):
    """A permission or path fault is not a holder: read as one, the hourly leg would stand down
    on every pass, run nothing and leave no artifact."""
    monkeypatch.setenv("HOURLY_PLAN", "dept:forward")
    blocker = tmp_path / "not_a_dir"
    blocker.write_text("x", encoding="utf-8")
    monkeypatch.setattr(daily_cycle, "_lock_path", lambda: blocker / "daily_cycle.lock")
    assert daily_cycle.main([]) == 0
    assert cyc.calls == ["a", "b", "c"]
    assert "chain lock UNAVAILABLE" in daily_cycle.LOG.read_text(encoding="utf-8")


@pytest.mark.skipif(sys.platform == "win32", reason="exercises the POSIX flock branch")
def test_should_fix_3_only_contention_errnos_read_as_held(tmp_path, monkeypatch):
    import errno
    import fcntl

    def eio(*_a, **_k):
        raise OSError(errno.EIO, "I/O error")

    monkeypatch.setattr(fcntl, "flock", eio)
    with pytest.raises(daily_cycle.LockUnavailable):
        daily_cycle._try_lock(tmp_path / "x.lock")

    def busy(*_a, **_k):
        raise BlockingIOError(errno.EWOULDBLOCK, "busy")

    monkeypatch.setattr(fcntl, "flock", busy)
    assert daily_cycle._try_lock(tmp_path / "y.lock") is None


def test_should_fix_4_the_hourly_leg_records_a_stand_down_as_stood_down_not_ok(monkeypatch):
    import hourly_cycle

    assert hourly_cycle.DAILY_CYCLE_STOOD_DOWN == daily_cycle.EXIT_STOOD_DOWN
    assert daily_cycle.EXIT_STOOD_DOWN not in (0, 1)

    def fake(rc):
        return lambda *_a, **_k: type("R", (), {"returncode": rc, "stdout": "", "stderr": ""})()

    for rc, want in ((0, "OK"), (daily_cycle.EXIT_STOOD_DOWN, "STOOD_DOWN"), (1, "FAILED")):
        monkeypatch.setattr(hourly_cycle, "_run_tree", fake(rc))
        assert hourly_cycle.daily()["status"] == want
