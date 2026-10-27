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
  * a bounded stand-down exits EXIT_STOOD_DOWN, never recorded as OK.
v1.2 (audit of 8e373a6f2, one must-fix, four should-fixes, one nit):
  * MUST-FIX: a stamp dated after the current UTC date is a clock error -- overwritten, recorded
    in `clock_corrections`, never a block: after the clock is corrected the chain resumes;
  * an unlocked chain waits BETWEEN steps while a healthy holder has the lock (--force past the
    wait, a holder that dies, a chain crossing midnight);
  * the stamp is written atomically and never over an unparseable file;
  * the hourly leg's stand-down is VERDICT_EXITS["daily"] with a noop_reason, so neither
    write_or_explain (LEG_FAILED) nor completion (FAILING) reads it as a failure;
  * a faulty lock file is recorded in the stamp, not only the log;
  * a step raising SystemExit(75) is a failed step, never a stand-down.
v1.3 (audit of d841e58a9, one must-fix, three should-fixes):
  * MUST-FIX: completion reads `verdict_exit=N` as ok ONLY for the explicit no-op set (daily 75);
    deep_forest 1, model_skill 2 and maintain_miners 2 still read FAILING and keep their streaks;
  * a sidecar with no create_time is "unmeasured", never "alive";
  * a stand-down behind a holder older than HOLDER_MAX_WAIT_S is a named FAILURE (exit 76);
  * quarantined `.corrupt-<ts>` stamps are bounded to the newest CORRUPT_KEEP.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
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
    day-D+1 stamp back to D -- that reset the new day to step one on every step it finished.
    (v1.2: the later day is a REAL later day on the clock; a date beyond the clock is a clock
    error and is overwritten -- see the must-fix tests.)"""
    monkeypatch.setenv("HOURLY_PLAN", "dept:forward")
    clock = _fake_clock(monkeypatch, datetime(2030, 6, 10, 23, 50, tzinfo=UTC))
    d1 = "2030-06-11"

    def a():
        cyc.calls.append("a")
        clock.set(datetime(2030, 6, 11, 0, 10, tzinfo=UTC))
        cyc.stamp.write_text(json.dumps({"last_run": d1, "steps": {"a": {"ok": True}}}),
                             encoding="utf-8")

    monkeypatch.setattr(daily_cycle, "STEPS", (("a", a), ("b", lambda: cyc.calls.append("b"))))
    assert daily_cycle.main([]) == 0
    stamp = json.loads(cyc.stamp.read_text(encoding="utf-8"))
    assert stamp["last_run"] == d1
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
    # v1.2 should-fix 4: the fault is in the STAMP, not only the log.
    rec = json.loads(cyc.stamp.read_text(encoding="utf-8"))["chain_lock"]
    assert rec["state"] == "unavailable"
    assert "cannot" in rec["error"]
    assert rec["unlocked_steps"] == ["a", "b", "c"]


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


def test_should_fix_4_the_hourly_leg_never_records_a_stand_down_as_ok(monkeypatch):
    import hourly_cycle

    assert hourly_cycle.DAILY_CYCLE_STOOD_DOWN == daily_cycle.EXIT_STOOD_DOWN
    assert daily_cycle.EXIT_STOOD_DOWN not in (0, 1)

    def fake(rc):
        return lambda *_a, **_k: type("R", (), {"returncode": rc, "stdout": "", "stderr": ""})()

    for rc, want in ((0, "OK"), (1, "FAILED")):
        monkeypatch.setattr(hourly_cycle, "_run_tree", fake(rc))
        assert hourly_cycle.daily()["status"] == want
    monkeypatch.setattr(hourly_cycle, "_run_tree", fake(daily_cycle.EXIT_STOOD_DOWN))
    assert hourly_cycle.daily().get("status") != "OK"


# ----------------------------------------------------------------------------- v1.2 helpers


class _Clock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def set(self, now: datetime) -> None:
        self.now = now


def _fake_clock(monkeypatch, start: datetime) -> _Clock:
    """Replace the module's `datetime` so `datetime.now(...)` reads a settable clock."""
    clock = _Clock(start)

    class _DT(datetime):
        @classmethod
        def now(cls, tz=None):
            return clock.now if tz is not None else clock.now.replace(tzinfo=None)

    monkeypatch.setattr(daily_cycle, "datetime", _DT)
    return clock


def _claim_alive():
    """Hold the lock AND publish this process as its healthy owner, as a real holder does."""
    lk = daily_cycle.ChainLock()
    assert lk.try_acquire(), "the test could not take the chain lock itself"
    assert daily_cycle._holder_health() == "alive"
    return lk


class _Killed(BaseException):
    """A kill mid-step: not an Exception, so `run_step` does not catch it."""


# ----------------------------------------------------------------------------- v1.2 must-fix


def test_must_fix_a_future_stamp_is_a_clock_error_and_the_corrected_clock_resumes(cyc,
                                                                                 monkeypatch):
    """A pass on a clock set a year ahead stamps that future day. v1.1 then refused every write
    on the corrected clock ("never moves backwards"), so a killed pass could never resume: each
    hour re-ran the chain from step one and stamped nothing. Now the future stamp is overwritten,
    the correction is recorded, and the next pass runs only what is left."""
    monkeypatch.setenv("HOURLY_PLAN", "dept:forward")
    clock = _fake_clock(monkeypatch, datetime(2031, 6, 10, 12, 0, tzinfo=UTC))
    assert daily_cycle.main([]) == 0                      # the misset clock stamps 2031-06-10
    assert json.loads(cyc.stamp.read_text(encoding="utf-8"))["last_run"] == "2031-06-10"
    cyc.calls.clear()

    clock.set(datetime(2030, 6, 10, 12, 0, tzinfo=UTC))   # the clock is corrected
    today = "2030-06-10"
    kill = {"on": True}

    def b():
        cyc.calls.append("b")
        if kill["on"]:
            raise _Killed

    monkeypatch.setattr(daily_cycle, "STEPS", (("a", lambda: cyc.calls.append("a")), ("b", b),
                                               ("c", lambda: cyc.calls.append("c"))))
    with pytest.raises(_Killed):
        daily_cycle.main([])                              # killed during b
    stamp = json.loads(cyc.stamp.read_text(encoding="utf-8"))
    assert stamp["last_run"] == today, "the future stamp must not block the corrected clock"
    assert set(stamp["steps"]) == {"a"}, "the 2031 day's steps must not be read as today's"
    assert stamp["clock_corrections"][-1]["from"] == "2031-06-10"
    assert stamp["clock_corrections"][-1]["to"] == today
    assert "clock error" in daily_cycle.LOG.read_text(encoding="utf-8")

    cyc.calls.clear()
    kill["on"] = False
    assert daily_cycle.main([]) == 0
    assert cyc.calls == ["b", "c"], "the next pass resumes where the killed one stopped"
    stamp = json.loads(cyc.stamp.read_text(encoding="utf-8"))
    assert stamp["last_run"] == today
    assert set(stamp["steps"]) == {"a", "b", "c"}
    assert len(stamp["clock_corrections"]) == 1, "the correction is recorded once, and kept"


def test_must_fix_write_stamp_overwrites_only_a_date_beyond_the_clock(cyc, monkeypatch):
    clock = _fake_clock(monkeypatch, datetime(2030, 6, 11, 0, 5, tzinfo=UTC))
    later = {"last_run": "2030-06-11", "steps": {"a": {"ok": True}}}
    cyc.stamp.write_text(json.dumps(later), encoding="utf-8")
    # real clock D+1: a D+1 stamp is a genuine later day, and a D chain may not rewrite it
    assert daily_cycle._write_stamp("2030-06-10", {"z": {"ok": True}}) is False
    assert json.loads(cyc.stamp.read_text(encoding="utf-8")) == later
    # real clock D: the same D+1 stamp is beyond the clock -- a clock error, overwritten
    clock.set(datetime(2030, 6, 10, 23, 0, tzinfo=UTC))
    assert daily_cycle._write_stamp("2030-06-10", {"z": {"ok": True}}) is True
    doc = json.loads(cyc.stamp.read_text(encoding="utf-8"))
    assert doc["last_run"] == "2030-06-10"
    assert doc["steps"] == {"z": {"ok": True}}
    assert doc["clock_corrections"][0]["from"] == "2030-06-11"


# ----------------------------------------------------------------------------- v1.2 should-fix 1


def test_should_fix_1_force_past_the_wait_still_waits_for_a_healthy_holder(cyc, monkeypatch):
    """MT5-Daily with --force, past UNBOUNDED_WAIT_S, while the holder is measured ALIVE: it
    keeps waiting and runs no step until the holder lets go -- then holds the lock itself."""
    monkeypatch.delenv("HOURLY_PLAN", raising=False)
    monkeypatch.setattr(daily_cycle, "UNBOUNDED_WAIT_S", 30.0)
    polls_to_release = 10                                 # 150 s: five times the fallback wait
    held = {"lk": _claim_alive(), "polls": 0}
    events: list[str] = []

    def sleep(_s):
        held["polls"] += 1
        events.append("poll")
        if held["polls"] == polls_to_release:
            held["lk"].close()
            held["lk"] = None
            events.append("released")

    monkeypatch.setattr(daily_cycle.time, "sleep", sleep)

    def step(n):
        def fn():
            events.append(n)
            cyc.calls.append(n)
        return fn

    monkeypatch.setattr(daily_cycle, "STEPS", tuple((n, step(n)) for n in ("a", "b", "c")))
    try:
        assert daily_cycle.main(["--force"]) == 0
    finally:
        if held["lk"] is not None:
            held["lk"].close()
    assert events.index("released") < events.index("a"), "no step may run beside a live holder"
    assert held["polls"] == polls_to_release
    assert cyc.calls == ["a", "b", "c"]
    rec = json.loads(cyc.stamp.read_text(encoding="utf-8"))["chain_lock"]
    assert rec["state"] == "held" and "unlocked_steps" not in rec


def test_should_fix_1_a_hung_live_holder_blocks_only_up_to_the_ceiling(cyc, monkeypatch):
    monkeypatch.delenv("HOURLY_PLAN", raising=False)
    monkeypatch.setattr(daily_cycle, "UNBOUNDED_WAIT_S", 30.0)
    monkeypatch.setattr(daily_cycle, "HOLDER_MAX_WAIT_S", 90.0)
    monkeypatch.setattr(daily_cycle.time, "sleep", lambda _s: None)
    lk = _claim_alive()
    try:
        assert daily_cycle.main([]) == 0
    finally:
        lk.close()
    assert cyc.calls == ["a", "b", "c"], "past the ceiling the day still runs"
    rec = json.loads(cyc.stamp.read_text(encoding="utf-8"))["chain_lock"]
    assert rec["state"] == "contended" and rec["unlocked_steps"] == ["a", "b", "c"]


@pytest.mark.skipif(sys.platform == "win32", reason="kills a POSIX child holding flock")
def test_should_fix_1_a_holder_that_dies_frees_the_waiter_at_once(cyc, monkeypatch):
    monkeypatch.delenv("HOURLY_PLAN", raising=False)
    script = (
        "import sys, time\n"
        "from pathlib import Path\n"
        "sys.path[:0] = [sys.argv[1], sys.argv[2]]\n"
        "import daily_cycle\n"
        "daily_cycle.STAMP = Path(sys.argv[3])\n"
        "lk = daily_cycle.ChainLock()\n"
        "assert lk.try_acquire()\n"
        "print('ready', flush=True)\n"
        "time.sleep(300)\n")
    proc = subprocess.Popen([sys.executable, "-c", script, str(_DESK), str(_DESK / "research"),
                             str(cyc.stamp)], stdout=subprocess.PIPE, text=True)
    try:
        assert proc.stdout is not None and proc.stdout.readline().strip() == "ready"
        assert daily_cycle._holder_health() == "alive"
        sleeps: list[str] = []

        def sleep(_s):
            sleeps.append(daily_cycle._holder_health())
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=30)

        monkeypatch.setattr(daily_cycle.time, "sleep", sleep)
        assert daily_cycle.main([]) == 0
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=30)
        if proc.stdout is not None:
            proc.stdout.close()
    # `time.sleep` is the process-wide function, so other code's sleeps land in the stub too;
    # the chain's own wait is read from its log: one poll, because the kernel freed the lock.
    assert sleeps[0] == "alive"
    assert "chain lock acquired after 15s" in daily_cycle.LOG.read_text(encoding="utf-8")
    assert cyc.calls == ["a", "b", "c"]
    assert json.loads(cyc.stamp.read_text(encoding="utf-8"))["chain_lock"]["state"] == "held"
    assert not daily_cycle._owner_path().exists(), "the owner sidecar is removed at release"


def test_should_fix_1_a_chain_crossing_midnight_is_waited_for_then_the_new_day_runs_once(
        cyc, monkeypatch):
    """The D chain is still running at 00:05 on D+1 when MT5-Daily starts the D+1 chain. The
    D+1 chain waits for it, then runs D+1's steps once -- no step twice, and the D chain's last
    writes cannot reset D+1."""
    monkeypatch.delenv("HOURLY_PLAN", raising=False)
    monkeypatch.setattr(daily_cycle, "UNBOUNDED_WAIT_S", 30.0)
    _fake_clock(monkeypatch, datetime(2030, 6, 11, 0, 5, tzinfo=UTC))
    cyc.stamp.write_text(json.dumps({"last_run": "2030-06-10", "steps": {"a": {"ok": True}}}),
                         encoding="utf-8")
    held = {"lk": _claim_alive(), "polls": 0}
    events: list[str] = []

    def sleep(_s):
        held["polls"] += 1
        if held["polls"] == 4:                            # the D chain finishes its day
            assert daily_cycle._write_stamp("2030-06-10", {"b": {"ok": True},
                                                           "c": {"ok": True}})
            held["lk"].close()
            held["lk"] = None
            events.append("released")

    monkeypatch.setattr(daily_cycle.time, "sleep", sleep)

    def step(n):
        def fn():
            events.append(n)
            cyc.calls.append(n)
        return fn

    monkeypatch.setattr(daily_cycle, "STEPS", tuple((n, step(n)) for n in ("a", "b", "c")))
    try:
        assert daily_cycle.main([]) == 0
    finally:
        if held["lk"] is not None:
            held["lk"].close()
    assert events[0] == "released"
    assert cyc.calls == ["a", "b", "c"]
    stamp = json.loads(cyc.stamp.read_text(encoding="utf-8"))
    assert stamp["last_run"] == "2030-06-11" and set(stamp["steps"]) == {"a", "b", "c"}
    assert "clock_corrections" not in stamp


def test_should_fix_1_an_unlocked_chain_waits_between_steps_for_a_holder_that_turns_healthy(
        cyc, monkeypatch):
    """The fallback starts unlocked behind an UNMEASURED holder. When the holder is later
    measured alive, the chain waits before its next step instead of running it beside it."""
    monkeypatch.delenv("HOURLY_PLAN", raising=False)
    monkeypatch.setattr(daily_cycle, "UNBOUNDED_WAIT_S", 30.0)
    held = {"h": _hold()}                                 # no sidecar: health unmeasured
    events: list[str] = []
    seen: dict[str, object] = {}

    def sleep(_s):
        events.append("poll")
        if daily_cycle._holder_health() == "alive":
            daily_cycle._owner_path().unlink()
            held["h"].close()
            held["h"] = None
            events.append("released")

    monkeypatch.setattr(daily_cycle.time, "sleep", sleep)

    def a():
        events.append("a")
        daily_cycle._atomic_write(daily_cycle._owner_path(), json.dumps({
            "pid": os.getpid(), "create_time": daily_cycle._process_start(os.getpid())}))

    def c():
        events.append("c")
        seen["probe"] = daily_cycle._try_lock(daily_cycle._lock_path())

    monkeypatch.setattr(daily_cycle, "STEPS", (("a", a), ("b", lambda: events.append("b")),
                                               ("c", c)))
    try:
        assert daily_cycle.main([]) == 0
    finally:
        if held["h"] is not None:
            held["h"].close()
    assert events.index("a") < events.index("released") < events.index("b")
    assert events[events.index("a") + 1] == "poll", "b waited for the healthy holder"
    assert seen["probe"] is None, "and holds the lock from then on"
    assert json.loads(cyc.stamp.read_text(encoding="utf-8"))["chain_lock"][
        "unlocked_steps"] == ["a"]


# ----------------------------------------------------------------------------- v1.2 should-fix 2


def test_should_fix_2_the_stamp_is_written_atomically_with_a_retry(cyc, monkeypatch):
    real = os.replace
    fails = {"n": 2}

    def flaky(src, dst):
        if fails["n"]:
            fails["n"] -= 1
            raise PermissionError(13, "in use by a reader (Windows)")
        return real(src, dst)

    monkeypatch.setattr(daily_cycle.os, "replace", flaky)
    monkeypatch.setattr(daily_cycle.time, "sleep", lambda _s: None)
    assert daily_cycle._write_stamp("2030-06-10", {"a": {"ok": True}}) is True
    assert fails["n"] == 0
    assert json.loads(cyc.stamp.read_text(encoding="utf-8"))["last_run"] == "2030-06-10"
    assert [p.name for p in cyc.stamp.parent.iterdir() if p.name.endswith(".tmp")] == []


def test_should_fix_2_an_unparseable_stamp_is_never_overwritten(cyc, monkeypatch):
    monkeypatch.setattr(daily_cycle.time, "sleep", lambda _s: None)
    cyc.stamp.write_text('{"last_run": "2030-06-10", "steps": {"a"', encoding="utf-8")
    before = cyc.stamp.read_bytes()
    assert daily_cycle._write_stamp(datetime.now(UTC).date().isoformat(), {"b": {}}) is False
    assert cyc.stamp.read_bytes() == before
    assert "cannot be parsed" in daily_cycle.LOG.read_text(encoding="utf-8")


def test_should_fix_2_an_unparseable_stamp_under_the_held_lock_is_kept_aside(cyc, monkeypatch):
    monkeypatch.setenv("HOURLY_PLAN", "dept:forward")
    cyc.stamp.write_text("{torn", encoding="utf-8")
    assert daily_cycle.main([]) == 0
    aside = [p for p in cyc.stamp.parent.iterdir() if ".corrupt-" in p.name]
    assert len(aside) == 1 and aside[0].read_text(encoding="utf-8") == "{torn"
    assert set(json.loads(cyc.stamp.read_text(encoding="utf-8"))["steps"]) == {"a", "b", "c"}


# ----------------------------------------------------------------------------- v1.2 should-fix 3


def test_should_fix_3_a_stand_down_is_a_declared_verdict_not_a_failure(monkeypatch):
    import hourly_cycle

    from libs.ops import completion, write_or_explain

    assert hourly_cycle.VERDICT_EXITS["daily"] == (daily_cycle.EXIT_STOOD_DOWN,)
    assert hourly_cycle._exit_outcome("daily", 75) == "verdict_exit=75"
    assert hourly_cycle._exit_outcome("daily", 1) == "exit_code=1"
    monkeypatch.setattr(hourly_cycle, "_run_tree", lambda *_a, **_k: type(
        "R", (), {"returncode": 75, "stdout": "", "stderr": ""})())
    out = hourly_cycle.daily()
    assert "status" not in out, "a status would become the ledger outcome and read as FAILING"
    assert out["exit_code"] == 75 and out["verdict_exit"] and out["noop_reason"]

    snap = {"/x/artifact.json": {"exists": True, "mtime": 1.0, "size": 1}}
    rec = write_or_explain.judge("daily", snap, snap, out,
                                 verdict_exits=hourly_cycle.VERDICT_EXITS["daily"])
    assert rec["verdict"] == write_or_explain.DECLARED_NO_OP
    undeclared = write_or_explain.judge("daily", snap, snap, out, verdict_exits=())
    assert undeclared["verdict"] == write_or_explain.LEG_FAILED, "the declaration is what saves it"

    assert completion._failed(out) is None
    assert completion._failed({"exit_code": 75}) is not None, "an undeclared 75 still fails"
    assert completion._streak([{"outcome": "exit_code=1"}, {"outcome": "verdict_exit=75"}],
                              "daily") == 0
    assert completion._streak([{"outcome": "verdict_exit=75"}, {"outcome": "exit_code=1"}],
                              "daily") == 1
    assert completion._streak([{"outcome": "verdict_exit=75"}], "model_skill") == 1, \
        "the no-op set is per leg: 75 is a no-op for daily only"


# ----------------------------------------------------------------------------- v1.2 nit


def test_nit_a_step_raising_systemexit_75_is_a_failed_step_not_a_stand_down(cyc, monkeypatch):
    monkeypatch.setenv("HOURLY_PLAN", "dept:forward")

    def b():
        cyc.calls.append("b")
        raise SystemExit(daily_cycle.EXIT_STOOD_DOWN)

    monkeypatch.setattr(daily_cycle, "STEPS", (("a", lambda: cyc.calls.append("a")), ("b", b),
                                               ("c", lambda: cyc.calls.append("c"))))
    assert daily_cycle.main([]) == 1
    assert cyc.calls == ["a", "b", "c"], "the chain goes on past the step that exited"
    steps = json.loads(cyc.stamp.read_text(encoding="utf-8"))["steps"]
    assert steps["b"]["ok"] is False and "SystemExit" in steps["b"]["error"]


# ----------------------------------------------------------------------------- v1.3 must-fix


@pytest.mark.parametrize(("leg", "code"), [("deep_forest", 1), ("model_skill", 2),
                                           ("maintain_miners", 2)])
def test_v13_must_fix_other_verdict_exits_still_read_failing(leg, code):
    """Those codes include uncaught exceptions (deep_forest), a data outage (model_skill) and a
    fence TIMEOUT/ERROR (maintain_miners); completion must keep reading them as failures and keep
    their outage streak -- only `daily` 75 is a declared no-op."""
    from libs.ops import completion

    assert completion.NOOP_EXITS == {"daily": (75,)}
    outcome = f"verdict_exit={code}"
    assert completion._ok_outcome(outcome, leg) is False
    assert completion._ok_outcome(outcome) is False
    assert completion._streak([{"outcome": outcome}] * 5, leg) == 5
    assert completion._ok_outcome("verdict_exit=75", "daily") is True
    assert completion._ok_outcome("verdict_exit=1", "daily") is False


def test_v13_must_fix_a_crashing_deep_forest_reads_failing_with_its_streak(tmp_path):
    """The auditor's probe: five `verdict_exit=1` rows and a marker that rotated the leg out read
    FAILING with streak 5 (v1.1), not UNKNOWN_HERE with streak 0 (v1.2)."""
    from libs.ops import completion

    root = _DESK.parents[1]
    if "deep_forest" not in completion.legs(root):
        pytest.skip("deep_forest is not a leg of the cycles in this tree")
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text("".join(json.dumps({"run": "deep_forest", "outcome": "verdict_exit=1",
                                          "at": f"2030-06-10T0{i}:00:00+00:00"}) + "\n"
                              for i in range(5)), encoding="utf-8")
    marker = tmp_path / "marker.json"
    marker.write_text(json.dumps({"deep_forest": {"status": "ROTATED_OUT"}}), encoding="utf-8")
    leg = next(x for x in completion.judge(root, marker_path=marker, ledger_path=ledger)
               if x.name == "deep_forest")
    assert leg.node is not None, "deep_forest has a capability-graph node, so it is judged"
    assert leg.verdict == completion.FAILING, leg.why
    assert leg.streak == 5


# ----------------------------------------------------------------------------- v1.3 should-fixes


def test_v13_should_fix_1_a_sidecar_without_create_time_is_unmeasured(cyc):
    side = daily_cycle._owner_path()
    side.parent.mkdir(parents=True, exist_ok=True)
    for doc in ({"pid": os.getpid(), "create_time": None}, {"pid": os.getpid()}):
        side.write_text(json.dumps(doc), encoding="utf-8")
        assert daily_cycle._holder_health() == "unmeasured", doc
    side.write_text(json.dumps({"pid": os.getpid(),
                                "create_time": daily_cycle._process_start(os.getpid())}),
                    encoding="utf-8")
    assert daily_cycle._holder_health() == "alive"


def _sidecar_at(at: datetime) -> None:
    side = daily_cycle._owner_path()
    doc = json.loads(side.read_text(encoding="utf-8"))
    doc["at"] = at.isoformat(timespec="seconds")
    side.write_text(json.dumps(doc), encoding="utf-8")


def test_v13_should_fix_2_a_stand_down_behind_a_hung_holder_is_a_failure(cyc, monkeypatch,
                                                                        capsys):
    import hourly_cycle

    monkeypatch.setenv("HOURLY_PLAN", "dept:forward")
    lk = _claim_alive()
    try:
        _sidecar_at(datetime.now(UTC))
        assert daily_cycle.main([]) == daily_cycle.EXIT_STOOD_DOWN, "a fresh holder: a verdict"
        assert "WRITE_OR_EXPLAIN: NO_OP" in capsys.readouterr().out
        _sidecar_at(datetime.now(UTC)
                    - timedelta(seconds=daily_cycle.HOLDER_MAX_WAIT_S + 60))
        assert daily_cycle.main([]) == daily_cycle.EXIT_HOLDER_HUNG
        assert "WRITE_OR_EXPLAIN: NO_OP" not in capsys.readouterr().out
    finally:
        lk.close()
    assert cyc.calls == []
    assert "HOLDER HUNG" in daily_cycle.LOG.read_text(encoding="utf-8")

    assert hourly_cycle.DAILY_CYCLE_HOLDER_HUNG == daily_cycle.EXIT_HOLDER_HUNG
    assert daily_cycle.EXIT_HOLDER_HUNG not in hourly_cycle.VERDICT_EXITS["daily"]
    assert hourly_cycle._exit_outcome("daily", 76) == "exit_code=76:HOLDER_HUNG"
    monkeypatch.setattr(hourly_cycle, "_run_tree", lambda *_a, **_k: type(
        "R", (), {"returncode": 76, "stdout": "", "stderr": ""})())
    out = hourly_cycle.daily()
    assert "status" not in out and not out.get("verdict_exit") and "noop_reason" not in out

    from libs.ops import completion, write_or_explain

    snap = {"/x/artifact.json": {"exists": True, "mtime": 1.0, "size": 1}}
    rec = write_or_explain.judge("daily", snap, snap, out,
                                 verdict_exits=hourly_cycle.VERDICT_EXITS["daily"])
    assert rec["verdict"] == write_or_explain.LEG_FAILED
    assert completion._failed(out) is not None
    assert completion._ok_outcome("exit_code=76:HOLDER_HUNG", "daily") is False


def test_v13_should_fix_3_quarantined_stamps_are_bounded(cyc, monkeypatch):
    monkeypatch.setenv("HOURLY_PLAN", "dept:forward")
    for i in range(7):
        (cyc.stamp.parent / f"{cyc.stamp.name}.corrupt-20300101T00000{i}Z").write_text(
            "old", encoding="utf-8")
    cyc.stamp.write_text("{torn", encoding="utf-8")
    assert daily_cycle.main([]) == 0
    kept = sorted(p for p in cyc.stamp.parent.iterdir() if ".corrupt-" in p.name)
    assert len(kept) == daily_cycle.CORRUPT_KEEP == 5
    texts = [p.read_text(encoding="utf-8") for p in kept]
    assert texts.count("{torn") == 1, "the new quarantine is always kept"
    # the seeded names are dated 2030, AFTER this run's own name: a clock-skewed name must not
    # make the evidence just taken sort oldest and be pruned
    olds = [p.name for p in kept if p.read_text(encoding="utf-8") == "old"]
    assert [n[-8:] for n in olds] == ["T000003Z", "T000004Z", "T000005Z", "T000006Z"]
