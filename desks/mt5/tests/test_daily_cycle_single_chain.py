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
v1.4 (audit of fd141ebb9, one must-fix, two should-fixes, two nits):
  * MUST-FIX: `_prune_corrupt` is a declared DestructivePath (check_no_retirement_on_absence);
  * the holder is aged from its LAST PROGRESS, refreshed by `_write_stamp` after every step;
  * exit 76 only when the sidecar's process is measured alive;
  * a future-named quarantine copy sorts oldest and cannot hold a slot forever.
v1.5 (audit of f18726a56, one must-fix, three should-fixes):
  * MUST-FIX: an UNREADABLE stamp (OSError) is never quarantined and nothing is pruned; only a
    stamp still TORN (ValueError / non-dict) after the re-reads is moved aside, and the prune
    runs only after that move succeeded (probes P1a, P1b);
  * quarantine copies are ordered by a sequence number, never the clock (P2b: clock set back);
  * "alive" requires the OS to list the sidecar's pid as the lock holder where it can (Linux);
  * a future-dated progress time is no age: waiters' wall-clock observation of the holder is.
v1.6 (audit of ca5c0508e, CLEAR, two should-fixes and two nits):
  * an unreadable stamp exits 77 (STAMP_UNREADABLE), and 78 (STAMP_UNREADABLE_PERSISTENT) once
    it has lasted past 3 consecutive passes; both are named failures of the hourly leg;
  * a torn stamp that cannot be moved aside (replace failed, or the lock is not ours) runs no
    step and exits 1 (probe P1d);
  * an unreadable seen.json keeps its first_seen.
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
        legacy = cyc.stamp.parent / f"{cyc.stamp.name}.corrupt-20300101T00000{i}Z"
        legacy.write_text("old", encoding="utf-8")
        os.utime(legacy, (1_700_000_000 + i, 1_700_000_000 + i))   # written in name order
    cyc.stamp.write_text("{torn", encoding="utf-8")
    monkeypatch.setattr(daily_cycle.time, "sleep", lambda _s: None)
    assert daily_cycle.main([]) == 0
    kept = sorted(p for p in cyc.stamp.parent.iterdir() if ".corrupt-" in p.name)
    assert len(kept) == daily_cycle.CORRUPT_KEEP == 5
    texts = [p.read_text(encoding="utf-8") for p in kept]
    assert texts.count("{torn") == 1, "the new quarantine is always kept"
    # the seeded names are dated 2030, AFTER this run's own name: a clock-skewed name must not
    # make the evidence just taken sort oldest and be pruned
    olds = [p.name for p in kept if p.read_text(encoding="utf-8") == "old"]
    assert [n[-8:] for n in olds] == ["T000003Z", "T000004Z", "T000005Z", "T000006Z"]


# ----------------------------------------------------------------------------- v1.4


def test_v14_must_fix_prune_corrupt_is_a_declared_destructive_path():
    from libs.ops import reference_freshness as rf

    rows = [r for r in rf.DESTRUCTIVE_PATHS if r.function == "_prune_corrupt"]
    assert len(rows) == 1
    row = rows[0]
    assert row.module == "desks/mt5/research/daily_cycle.py"
    assert row.status == "positive"
    assert "CORRUPT_KEEP" in row.removes and ".corrupt-" in row.removes


def test_v14_sf_a_every_stamp_write_is_a_heartbeat_the_waiter_ages_from(cyc, monkeypatch):
    """A long chain that is still stepping must never read as hung: `_write_stamp` refreshes
    the sidecar's `last_progress` after every step, and the age is measured from it."""
    monkeypatch.setenv("HOURLY_PLAN", "dept:forward")
    clock = _fake_clock(monkeypatch, datetime(2030, 6, 10, 0, 0, tzinfo=UTC))
    ages: list[float] = []

    def step(n, hours):
        def fn():
            cyc.calls.append(n)
            clock.set(clock.now + timedelta(hours=hours))
            ages.append(daily_cycle._holder_age_s() or 0.0)   # at the END of the step
        return fn

    # three steps of 10 h: 30 h in all, far past the 16 h ceiling
    monkeypatch.setattr(daily_cycle, "STEPS", tuple((n, step(n, 10)) for n in ("a", "b", "c")))
    assert daily_cycle.main([]) == 0
    assert cyc.calls == ["a", "b", "c"]
    # from the lock these would read 10 h, 20 h, 30 h -- the last two past the ceiling
    assert ages == [10 * 3600.0] * 3, "aged from the last step, not from the lock"
    stamp = json.loads(cyc.stamp.read_text(encoding="utf-8"))
    assert stamp["last_progress"]["pid"] == os.getpid()
    assert stamp["last_progress"]["at"].startswith("2030-06-11T06:00")


def test_v14_sf_a_a_progressing_holder_past_the_ceiling_is_still_a_verdict(cyc, monkeypatch):
    monkeypatch.setenv("HOURLY_PLAN", "dept:forward")
    lk = _claim_alive()
    try:
        _sidecar_at(datetime.now(UTC) - timedelta(seconds=daily_cycle.HOLDER_MAX_WAIT_S + 3600))
        lk.heartbeat()                                    # took the lock 17 h ago, stepped now
        assert daily_cycle.main([]) == daily_cycle.EXIT_STOOD_DOWN
    finally:
        lk.close()


@pytest.mark.parametrize("pid_kind", ["dead", "reused"])
def test_v14_sf_b_a_stale_sidecar_of_another_process_never_gives_76(cyc, monkeypatch, pid_kind):
    """The auditor's probe: a fresh holder has the lock but its sidecar write failed, and the
    sidecar on disk is 17 h old and names a dead or reused pid. That is no evidence about the
    holder, so the stand-down stays a verdict (75)."""
    monkeypatch.setenv("HOURLY_PLAN", "dept:forward")
    held = _hold()                                        # holds the lock, writes no sidecar
    try:
        if pid_kind == "dead":
            p = subprocess.Popen([sys.executable, "-c", "pass"])
            p.wait(timeout=30)
            pid, started = p.pid, 1.0
        else:
            pid, started = os.getpid(), (daily_cycle._process_start(os.getpid()) or 0.0) - 5.0
        old = datetime.now(UTC) - timedelta(seconds=daily_cycle.HOLDER_MAX_WAIT_S + 3600)
        daily_cycle._owner_path().write_text(json.dumps({
            "pid": pid, "create_time": started, "at": old.isoformat(timespec="seconds")}),
            encoding="utf-8")
        assert daily_cycle._holder_health() == "dead"
        assert daily_cycle.main([]) == daily_cycle.EXIT_STOOD_DOWN
    finally:
        held.close()


def test_v14_nit_a_future_named_quarantine_copy_cannot_hold_a_slot(cyc, monkeypatch):
    """A copy written on a fast clock (name AND mtime in 2099) is pruned in its turn: by v1.5 the
    quarantine SEQUENCE orders copies, and an unsequenced legacy copy is older than all of them,
    so it goes once CORRUPT_KEEP sequenced copies exist -- it holds no slot forever."""
    monkeypatch.setenv("HOURLY_PLAN", "dept:forward")
    monkeypatch.setattr(daily_cycle.time, "sleep", lambda _s: None)
    clock = _fake_clock(monkeypatch, datetime(2030, 6, 10, 12, 0, tzinfo=UTC))
    d = cyc.stamp.parent
    future = d / f"{cyc.stamp.name}.corrupt-20990101T000000Z"
    future.write_text("future", encoding="utf-8")
    t2099 = datetime(2099, 1, 1, tzinfo=UTC).timestamp()
    os.utime(future, (t2099, t2099))
    for n in range(1, daily_cycle.CORRUPT_KEEP + 1):
        cyc.stamp.write_text("{torn", encoding="utf-8")
        clock.set(clock.now + timedelta(days=1))
        assert daily_cycle.main([]) == 0
        present = future.exists()
        assert present == (n < daily_cycle.CORRUPT_KEEP), (n, present)
    kept = sorted(p.name for p in d.iterdir() if ".corrupt-" in p.name)
    assert [daily_cycle._corrupt_seq(d / k) for k in kept] == [1, 2, 3, 4, 5]


# ----------------------------------------------------------------------------- v1.5


def _deny_reads(monkeypatch, path: Path, times: int | None = None) -> dict:
    """Make `path.read_text` raise PermissionError (`times` reads, or always) while the returned
    switch's "on" is True -- flip it rather than `monkeypatch.undo()`, which would also undo the
    `cyc` fixture's STAMP patch and point the module at the real repository."""
    real = Path.read_text
    left = {"n": times}
    switch = {"on": True}

    def read_text(self, *a, **k):
        if switch["on"] and self == path and (left["n"] is None or left["n"] > 0):
            if left["n"] is not None:
                left["n"] -= 1
            raise PermissionError(13, "sharing violation (scanner holds the file)")
        return real(self, *a, **k)

    monkeypatch.setattr(Path, "read_text", read_text)
    return switch


def _seed_copies(d: Path, stamp: Path, n: int = 5) -> list[Path]:
    out = []
    for i in range(1, n + 1):
        p = d / f"{stamp.name}.corrupt-{i:06d}-2030060{i}T000000Z"
        p.write_text(f"copy{i}", encoding="utf-8")
        out.append(p)
    return out


def test_v15_mf_p1a_a_valid_stamp_that_cannot_be_read_is_never_moved(cyc, monkeypatch):
    """Probe P1a: a VALID stamp (today, steps done) raising PermissionError on read. v1.4 moved
    it aside, pruned a real copy and restarted the day; now it is "don't know": nothing moves,
    nothing is pruned, no step runs, and the pass fails loudly for the next one to retry."""
    monkeypatch.setenv("HOURLY_PLAN", "dept:forward")
    monkeypatch.setattr(daily_cycle.time, "sleep", lambda _s: None)
    today = datetime.now(UTC).date().isoformat()
    cyc.stamp.write_text(json.dumps({"last_run": today, "steps": {"a": {"ok": True}}}),
                         encoding="utf-8")
    before = cyc.stamp.read_bytes()
    copies = _seed_copies(cyc.stamp.parent, cyc.stamp)
    _deny_reads(monkeypatch, cyc.stamp)
    assert daily_cycle.main([]) == daily_cycle.EXIT_STAMP_UNREADABLE
    assert cyc.calls == []
    assert cyc.stamp.read_bytes() == before, "the live stamp is never moved or rewritten"
    assert sorted(p for p in cyc.stamp.parent.iterdir() if ".corrupt-" in p.name) == copies
    assert "cannot be READ" in daily_cycle.LOG.read_text(encoding="utf-8")


def test_v15_mf_a_transient_read_denial_is_retried_and_the_day_resumes(cyc, monkeypatch):
    monkeypatch.setenv("HOURLY_PLAN", "dept:forward")
    monkeypatch.setattr(daily_cycle.time, "sleep", lambda _s: None)
    today = datetime.now(UTC).date().isoformat()
    cyc.stamp.write_text(json.dumps({"last_run": today, "steps": {"a": {"ok": True}}}),
                         encoding="utf-8")
    _deny_reads(monkeypatch, cyc.stamp, times=daily_cycle.STAMP_REREADS)
    assert daily_cycle.main([]) == 0
    assert cyc.calls == ["b", "c"], "the re-read found the valid stamp: a and only a skipped"
    assert not [p for p in cyc.stamp.parent.iterdir() if ".corrupt-" in p.name]


def test_v15_mf_p1b_a_denied_read_and_a_failed_replace_prune_nothing(cyc, monkeypatch):
    """Probe P1b: the read is denied AND os.replace fails (a locked file on Windows). v1.4 still
    pruned a copy although no quarantine was taken. Now: nothing moves, nothing is pruned."""
    monkeypatch.setenv("HOURLY_PLAN", "dept:forward")
    monkeypatch.setattr(daily_cycle.time, "sleep", lambda _s: None)
    cyc.stamp.write_text("{torn", encoding="utf-8")
    copies = _seed_copies(cyc.stamp.parent, cyc.stamp)
    real = os.replace
    replaced: list[str] = []

    def replace(src, dst):
        if Path(src) == cyc.stamp:
            replaced.append(str(dst))
            raise PermissionError(13, "in use")
        return real(src, dst)

    monkeypatch.setattr(daily_cycle.os, "replace", replace)
    _deny_reads(monkeypatch, cyc.stamp)
    assert daily_cycle.main([]) == daily_cycle.EXIT_STAMP_UNREADABLE
    assert replaced == [], "an unreadable stamp is not even attempted"
    assert sorted(p for p in cyc.stamp.parent.iterdir() if ".corrupt-" in p.name) == copies


def test_v15_mf_a_torn_stamp_whose_move_fails_prunes_nothing(cyc, monkeypatch):
    monkeypatch.setenv("HOURLY_PLAN", "dept:forward")
    monkeypatch.setattr(daily_cycle.time, "sleep", lambda _s: None)
    cyc.stamp.write_text("{torn", encoding="utf-8")
    copies = _seed_copies(cyc.stamp.parent, cyc.stamp)
    real = os.replace

    def replace(src, dst):
        if Path(src) == cyc.stamp:
            raise PermissionError(13, "in use")
        return real(src, dst)

    monkeypatch.setattr(daily_cycle.os, "replace", replace)
    # v1.6 (audit SF2, probe P1d): it also runs NO step -- v1.5 ran every step against {} with
    # the torn file blocking every stamp write, so each pass repeated the whole chain.
    assert daily_cycle.main([]) == 1
    assert cyc.calls == []
    assert cyc.stamp.read_text(encoding="utf-8") == "{torn"
    assert sorted(p for p in cyc.stamp.parent.iterdir() if ".corrupt-" in p.name) == copies
    assert "nothing was pruned" in daily_cycle.LOG.read_text(encoding="utf-8")


def test_v15_mf_a_stamp_torn_once_then_valid_is_not_quarantined(cyc, monkeypatch):
    """The quarantine requires the same re-reads `_write_stamp` does: a read caught mid-write
    that parses on the re-read is not corruption."""
    monkeypatch.setenv("HOURLY_PLAN", "dept:forward")
    monkeypatch.setattr(daily_cycle.time, "sleep", lambda _s: None)
    today = datetime.now(UTC).date().isoformat()
    cyc.stamp.write_text(json.dumps({"last_run": today, "steps": {"a": {"ok": True}}}),
                         encoding="utf-8")
    real = Path.read_text
    first = {"torn": True}

    def read_text(self, *a, **k):
        if self == cyc.stamp and first["torn"]:
            first["torn"] = False
            return '{"last_run": "'
        return real(self, *a, **k)

    monkeypatch.setattr(Path, "read_text", read_text)
    assert daily_cycle.main([]) == 0
    assert cyc.calls == ["b", "c"]
    assert not [p for p in cyc.stamp.parent.iterdir() if ".corrupt-" in p.name]


def test_v15_sf_a_clock_set_back_keeps_the_correctly_dated_newer_copy(cyc, monkeypatch):
    """Probe P2b: clock at 2026-01-01, legacy copies dated 2025-01 and 2026-10. v1.4 pruned the
    genuine 2026-10 copy as "future"; legacy copies are now ordered by mtime, and every new copy
    by sequence, so the 2026-10 copy is kept and the oldest 2025 copy goes."""
    monkeypatch.setenv("HOURLY_PLAN", "dept:forward")
    monkeypatch.setattr(daily_cycle.time, "sleep", lambda _s: None)
    _fake_clock(monkeypatch, datetime(2026, 1, 1, 12, 0, tzinfo=UTC))
    d = cyc.stamp.parent
    names = {f"2025010{i}T000000Z": datetime(2025, 1, i, tzinfo=UTC) for i in range(1, 5)}
    names["20261020T000000Z"] = datetime(2026, 10, 20, tzinfo=UTC)
    for name, when in names.items():
        p = d / f"{cyc.stamp.name}.corrupt-{name}"
        p.write_text(name, encoding="utf-8")
        os.utime(p, (when.timestamp(), when.timestamp()))
    cyc.stamp.write_text("{torn", encoding="utf-8")
    assert daily_cycle.main([]) == 0
    kept = {p.name for p in d.iterdir() if ".corrupt-" in p.name}
    assert f"{cyc.stamp.name}.corrupt-20261020T000000Z" in kept
    assert f"{cyc.stamp.name}.corrupt-20250101T000000Z" not in kept
    assert len(kept) == daily_cycle.CORRUPT_KEEP


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="reads /proc/locks")
def test_v15_sf_b_a_stale_sidecar_naming_another_live_process_is_not_the_holder(cyc,
                                                                               monkeypatch):
    """A stale sidecar names a LIVE process with its true create_time and a 17 h old progress
    time, while THIS process holds the lock. v1.4 read that as alive and gave 76; the OS says
    who holds the lock, so it is not the holder and the stand-down stays a verdict (75)."""
    monkeypatch.setenv("HOURLY_PLAN", "dept:forward")
    other = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
    held = _hold()
    try:
        assert os.getpid() in (daily_cycle._lock_holder_pids() or set())
        old = datetime.now(UTC) - timedelta(seconds=daily_cycle.HOLDER_MAX_WAIT_S + 3600)
        daily_cycle._owner_path().write_text(json.dumps({
            "pid": other.pid, "create_time": daily_cycle._process_start(other.pid),
            "at": old.isoformat(timespec="seconds"),
            "last_progress": old.isoformat(timespec="seconds")}), encoding="utf-8")
        assert daily_cycle._holder_health() == "unmeasured"
        assert daily_cycle.main([]) == daily_cycle.EXIT_STOOD_DOWN
    finally:
        held.close()
        other.kill()
        other.wait(timeout=30)


def test_v15_sf_c_a_future_progress_time_does_not_mute_a_hang(cyc, monkeypatch):
    """A fast clock wrote `at` and `last_progress` a day ahead. They are not an age (v1.4 read
    them as fresh for good). The first waiter records when it SAW this holder; once that is past
    the ceiling by wall clock, the stand-down is a failure (76)."""
    monkeypatch.setenv("HOURLY_PLAN", "dept:forward")
    lk = _claim_alive()
    try:
        ahead = (datetime.now(UTC) + timedelta(days=1)).isoformat(timespec="seconds")
        side = json.loads(daily_cycle._owner_path().read_text(encoding="utf-8"))
        side.update({"at": ahead, "last_progress": ahead})
        daily_cycle._owner_path().write_text(json.dumps(side), encoding="utf-8")
        assert daily_cycle._holder_age_s() is None, "a future time is unmeasured, not fresh"
        assert daily_cycle.main([]) == daily_cycle.EXIT_STOOD_DOWN
        seen = json.loads(daily_cycle._seen_path().read_text(encoding="utf-8"))
        assert seen["holder"] == [os.getpid(), side["create_time"]]
        long_ago = datetime.now(UTC) - timedelta(seconds=daily_cycle.HOLDER_MAX_WAIT_S + 60)
        seen["first_seen"] = long_ago.isoformat(timespec="seconds")
        daily_cycle._seen_path().write_text(json.dumps(seen), encoding="utf-8")
        assert daily_cycle.main([]) == daily_cycle.EXIT_HOLDER_HUNG
        # a NEW holder identity restarts the observation
        seen["holder"] = [os.getpid() + 1, 0.0]
        daily_cycle._seen_path().write_text(json.dumps(seen), encoding="utf-8")
        assert daily_cycle.main([]) == daily_cycle.EXIT_STOOD_DOWN
    finally:
        lk.close()


# ----------------------------------------------------------------------------- v1.6


def test_v16_sf1_an_unreadable_stamp_is_named_and_escalates_after_three_passes(cyc,
                                                                              monkeypatch,
                                                                              capsys):
    monkeypatch.setenv("HOURLY_PLAN", "dept:forward")
    monkeypatch.setattr(daily_cycle.time, "sleep", lambda _s: None)
    today = datetime.now(UTC).date().isoformat()
    cyc.stamp.write_text(json.dumps({"last_run": today, "steps": {"a": {"ok": True}}}),
                         encoding="utf-8")
    deny = _deny_reads(monkeypatch, cyc.stamp)
    got = [daily_cycle.main([]) for _ in range(5)]
    assert got == [77, 77, 77, 78, 78]
    assert daily_cycle.EXIT_STAMP_UNREADABLE == 77
    assert daily_cycle.EXIT_STAMP_UNREADABLE_PERSISTENT == 78
    assert cyc.calls == []
    log = daily_cycle.LOG.read_text(encoding="utf-8")
    assert "ESCALATED" in log and "5 consecutive" in log
    assert "STAMP_UNREADABLE_PERSISTENT: 5 consecutive passes" in capsys.readouterr().out

    deny["on"] = False                                # readable again: the count resets
    assert daily_cycle.main([]) == 0
    assert cyc.calls == ["b", "c"]
    assert not daily_cycle._unreadable_path().exists()
    deny["on"] = True
    assert daily_cycle.main([]) == 77, "a new outage starts the count again"


def test_v16_sf1_an_unreadable_count_file_reads_as_at_the_limit(cyc, monkeypatch):
    monkeypatch.setenv("HOURLY_PLAN", "dept:forward")
    monkeypatch.setattr(daily_cycle.time, "sleep", lambda _s: None)
    cyc.stamp.write_text("{}", encoding="utf-8")
    daily_cycle._unreadable_path().parent.mkdir(parents=True, exist_ok=True)
    daily_cycle._unreadable_path().write_text("{torn", encoding="utf-8")
    _deny_reads(monkeypatch, cyc.stamp)
    assert daily_cycle.main([]) == 78, "a broken count never restarts the outage at 1"


@pytest.mark.parametrize(("rc", "label"), [(77, "STAMP_UNREADABLE"),
                                           (78, "STAMP_UNREADABLE_PERSISTENT")])
def test_v16_sf1_the_hourly_leg_names_both_codes_as_failures(monkeypatch, rc, label):
    import hourly_cycle

    from libs.ops import write_or_explain

    assert hourly_cycle._exit_outcome("daily", rc) == f"exit_code={rc}:{label}"
    assert rc not in hourly_cycle.VERDICT_EXITS["daily"]
    monkeypatch.setattr(hourly_cycle, "_run_tree", lambda *_a, **_k: type(
        "R", (), {"returncode": rc, "stdout": "", "stderr": ""})())
    out = hourly_cycle.daily()
    assert "status" not in out and out["exit_code"] == rc and "noop_reason" not in out
    snap = {"/x/artifact.json": {"exists": True, "mtime": 1.0, "size": 1}}
    rec = write_or_explain.judge("daily", snap, snap, out,
                                 verdict_exits=hourly_cycle.VERDICT_EXITS["daily"])
    assert rec["verdict"] == write_or_explain.LEG_FAILED


def test_v16_sf2_a_torn_stamp_this_chain_cannot_move_runs_no_step(cyc, monkeypatch):
    """Torn, and the lock is another chain's (the unbounded caller ran out its wait): not ours
    to move, and running against {} would repeat every finished step -- fail closed."""
    monkeypatch.delenv("HOURLY_PLAN", raising=False)
    monkeypatch.setattr(daily_cycle, "UNBOUNDED_WAIT_S", 30.0)
    monkeypatch.setattr(daily_cycle.time, "sleep", lambda _s: None)
    cyc.stamp.write_text("{torn", encoding="utf-8")
    held = _hold()
    try:
        assert daily_cycle.main([]) == 1
    finally:
        held.close()
    assert cyc.calls == []
    assert cyc.stamp.read_text(encoding="utf-8") == "{torn"
    assert not [p for p in cyc.stamp.parent.iterdir() if ".corrupt-" in p.name]


def test_v16_nit_an_unreadable_seen_file_keeps_first_seen(cyc, monkeypatch):
    lk = _claim_alive()
    try:
        side = json.loads(daily_cycle._owner_path().read_text(encoding="utf-8"))
        first = "2030-01-01T00:00:00+00:00"
        doc = json.dumps({"holder": [side["pid"], side["create_time"]], "first_seen": first})
        daily_cycle._seen_path().write_text(doc, encoding="utf-8")
        deny = _deny_reads(monkeypatch, daily_cycle._seen_path())
        assert daily_cycle._observed_hold_s() is None
        deny["on"] = False
        assert json.loads(daily_cycle._seen_path().read_text(encoding="utf-8"))["first_seen"] \
            == first, "an unreadable seen file is never replaced"
    finally:
        lk.close()
