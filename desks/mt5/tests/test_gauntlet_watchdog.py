"""The --once sweep can never stall silently (2026-10-20).

pid 7324 sat fourteen hours in the sealed merge at 7-16 GB while every artifact called the judge
healthy, because the only ceiling was the resident's, derived from one 17 h sweep and capped at
48 h. These tests pin the watchdog that replaced the silence: a shard child that hangs is killed
with its tree inside its timeout and named; a child that dies does not leave the parent waiting;
a run past its phase deadline kills its descendants, writes the stall and exits STALL_RC; a dead
or wedged prior sweep is taken over; and the coverage fence reads a stall as RED.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
sys.path.insert(0, str(DESK))
sys.path.insert(0, str(ROOT / "scripts"))
from scripts import run_sharded_gauntlet as runner  # noqa: E402

psutil = pytest.importorskip("psutil")


@pytest.fixture(autouse=True)
def _isolated(monkeypatch, tmp_path):
    """No test reads or writes the desk's real heartbeat, stall, timing or lock files."""
    for name, fname in (("SHARD_PEAKS", "judge_shard_peaks.json"),
                        ("RESIDENT_STATE", "JUDGE_RESIDENT.json"),
                        ("RESIDENT_STOP", "RESIDENT_STOP"),
                        ("SWEEP_PHASE", "JUDGE_SWEEP_PHASE.json"),
                        ("HEARTBEAT", "GAUNTLET_HEARTBEAT.json"),
                        ("STALL", "GAUNTLET_STALL.json"),
                        ("PHASE_TIMES", "judge_phase_times.json")):
        monkeypatch.setattr(runner, name, tmp_path / fname)
    monkeypatch.setattr(runner, "_PHASE_DOC", {})
    monkeypatch.setattr(runner, "_PROGRESS", {})
    locks = tmp_path / "locks"
    locks.mkdir()
    monkeypatch.setattr(runner, "_lock_root", lambda: locks)
    for var in ("GAUNTLET_SHARD_TIMEOUT_S", "GAUNTLET_PHASE_DEADLINE_S",
                "GAUNTLET_RUN_DEADLINE_S", "GAUNTLET_NO_PROGRESS_S", "GAUNTLET_HEARTBEAT_S",
                "GAUNTLET_SHARD_CONCURRENCY", "GAUNTLET_SHARD_RETRIES"):
        monkeypatch.delenv(var, raising=False)
    runner._ABORT.clear()
    yield
    runner._ABORT.clear()


def _gone(pid: int) -> bool:
    if not psutil.pid_exists(pid):
        return True
    try:
        return psutil.Process(pid).status() == psutil.STATUS_ZOMBIE
    except psutil.Error:
        return True


def _wait_gone(pid: int, timeout: float = 10.0) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if _gone(pid):
            return True
        time.sleep(0.1)
    return _gone(pid)


#: A shard child that starts a grandchild, records both pids, and then never returns.
_HANG = textwrap.dedent("""
    import subprocess, sys, time
    g = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
    with open(sys.argv[1], "a") as fh:
        fh.write(f"{g.pid}\\n")
    time.sleep(120)
""")


def test_a_hanging_shard_is_killed_with_its_tree_within_the_timeout(monkeypatch, tmp_path):
    """The defect: `run(..., timeout=None)` let one shard hold the wave forever."""
    from libs.ops.proctree import run as real_run

    pids = tmp_path / "grandchildren.txt"
    started: list[int] = []

    def fake(argv, **kw):
        k = int(argv[-2])
        started.append(k)
        if k == 0:
            return real_run([sys.executable, "-c", _HANG, str(pids)], **kw)
        return real_run([sys.executable, "-c", "pass"], **kw)

    monkeypatch.setenv("GAUNTLET_SHARD_TIMEOUT_S", "2")
    monkeypatch.setenv("GAUNTLET_SHARD_CONCURRENCY", "1")
    monkeypatch.setattr(runner, "run", fake)
    t0 = time.monotonic()
    with pytest.raises(runner.ShardTimeout) as err:
        runner.dispatch(tmp_path / "shards", 4, "build")
    elapsed = time.monotonic() - t0
    assert err.value.k == 0 and elapsed < 2 + 20, elapsed
    # the grandchild died with it: `proctree.run` kills the whole tree on timeout
    for gpid in (int(x) for x in pids.read_text().split()):
        assert _wait_gone(gpid), f"grandchild {gpid} survived the shard timeout"
    stall = json.loads(runner.STALL.read_text("utf-8"))
    assert stall["status"] == "STALLED" and stall["reason"] == "shard_timeout"
    assert stall["shard"]["k"] == 0 and stall["shard"]["phase"] == "build"
    assert stall["consecutive"] == 1
    # THE WAVE STOPPED HANDING OUT WORK: concurrency 1, shard 0 hung, so 1..3 never started.
    assert started == [0]
    assert "3 shard(s) of the wave were not started" in stall["detail"]
    # no shard was recorded as a measured wall, so the next timeout is not sized off a hang
    assert not json.loads(runner.PHASE_TIMES.read_text("utf-8") if runner.PHASE_TIMES.exists()
                          else "{}").get("shards", {}).get("build")


def test_a_child_that_dies_never_leaves_the_parent_waiting(monkeypatch, tmp_path):
    """An OOM-killed shard is a failed child, retried and then refused -- never a wait."""
    from libs.ops.proctree import run as real_run

    die = "import os, signal; os.kill(os.getpid(), getattr(signal, 'SIGKILL', 9))"

    def fake(argv, **kw):
        return real_run([sys.executable, "-c", die], **kw)

    monkeypatch.setenv("GAUNTLET_SHARD_RETRIES", "1")
    monkeypatch.setattr(runner, "run", fake)
    t0 = time.monotonic()
    with pytest.raises(RuntimeError, match="refusing partial merge"):
        runner.dispatch(tmp_path / "shards", 2, "rule")
    assert time.monotonic() - t0 < 30
    # a death is a failure the resident retries, not a stall the watchdog widens for
    assert not runner.STALL.exists()


#: A --once stand-in: the real watchdog over a main thread that never returns, in its own
#: process so `os._exit` and the descendant kill are exercised for real.
_STUCK_SWEEP = textwrap.dedent("""
    import json, subprocess, sys, time
    from pathlib import Path
    sys.path[:0] = [{root!r}, {desk!r}]
    from scripts import run_sharded_gauntlet as r
    tmp = Path({tmp!r})
    r.HEARTBEAT, r.STALL = tmp / "GAUNTLET_HEARTBEAT.json", tmp / "GAUNTLET_STALL.json"
    r.PHASE_TIMES, r.SWEEP_PHASE = tmp / "judge_phase_times.json", tmp / "phase.json"
    r._lock_root = lambda: tmp / "locks"
    (tmp / "locks" / "certification_lane.json").write_text(json.dumps(
        {{"pid": __import__("os").getpid(), "host": __import__("socket").gethostname(),
          "started_at": "2026-10-20T00:00:00+00:00"}}))
    g = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
    (tmp / "grandchild.txt").write_text(str(g.pid))
    r._phase("merge_and_publish")
    r.SweepWatchdog(beat_s=0.2, lane=lambda: True).start()
    time.sleep(120)          # the sealed merge that never returns
""")


def test_a_run_past_its_phase_deadline_kills_its_tree_writes_the_stall_and_exits(tmp_path):
    script = _STUCK_SWEEP.format(root=str(ROOT), desk=str(DESK), tmp=str(tmp_path))
    env = {**os.environ, "GAUNTLET_PHASE_DEADLINE_S": "1.5"}
    t0 = time.monotonic()
    proc = subprocess.run([sys.executable, "-c", script], env=env, timeout=60,
                          capture_output=True, text=True, check=False)
    elapsed = time.monotonic() - t0
    assert proc.returncode == runner.STALL_RC, (proc.returncode, proc.stderr[-2000:])
    assert elapsed < 30, elapsed
    stall = json.loads((tmp_path / "GAUNTLET_STALL.json").read_text("utf-8"))
    assert stall["status"] == "STALLED"
    assert stall["reason"] == "phase_deadline:merge_and_publish"
    assert stall["phase"] == "merge_and_publish" and stall["last_progress"]["beat_utc"]
    hb = json.loads((tmp_path / "GAUNTLET_HEARTBEAT.json").read_text("utf-8"))
    assert hb["status"] == "STALLED" and hb["killed"] >= 1
    assert hb["locks_released"] == ["certification_lane"]
    assert not (tmp_path / "locks" / "certification_lane.json").exists()
    assert _wait_gone(int((tmp_path / "grandchild.txt").read_text()))


class _FakeTree:
    """A sampler whose CPU total the test controls."""

    def __init__(self) -> None:
        self.cpu = 0.0

    def __call__(self, pid: int) -> dict:
        return {"cpu": {pid: self.cpu}, "rss_mb": 10.0, "procs": 1}


def _dog(clock, tree, **kw):
    exits: list[int] = []
    dog = runner.SweepWatchdog(beat_s=30, clock=clock, sampler=tree, lane=lambda: True,
                               exit_fn=exits.append, **kw)
    return dog, exits


def test_a_tree_that_burns_no_cpu_is_a_stall_even_inside_its_deadline(monkeypatch):
    now = [1000.0]
    tree = _FakeTree()
    monkeypatch.setattr(runner, "_kill_descendants", lambda pid: 0)
    dog, exits = _dog(lambda: now[0], tree)
    runner._PHASE_DOC.update(phase="plan", _t=now[0], phases={})
    for _ in range(10):                       # working: 30 cpu-s per 60 s
        now[0] += 60
        tree.cpu += 30
        dog.tick()
    assert not exits
    hb = json.loads(runner.HEARTBEAT.read_text("utf-8"))
    assert hb["status"] == "RUNNING" and hb["idle_s"] == 0.0 and hb["tree"]["procs"] == 1
    for _ in range(int(runner.NO_PROGRESS_S // 60) + 2):   # silent: no CPU at all
        now[0] += 60
        dog.tick()
        if exits:
            break
    assert exits == [runner.STALL_RC]
    assert json.loads(runner.STALL.read_text("utf-8"))["reason"] == "no_progress"


def test_the_run_deadline_is_the_backstop(monkeypatch):
    now = [0.0]
    tree = _FakeTree()
    monkeypatch.setattr(runner, "_kill_descendants", lambda pid: 0)
    monkeypatch.setenv("GAUNTLET_RUN_DEADLINE_S", "100")
    dog, exits = _dog(lambda: now[0], tree)
    now[0] = 50.0
    tree.cpu = 50.0
    dog.tick()
    assert not exits
    now[0] = 101.0
    tree.cpu = 100.0
    dog.tick()
    assert exits == [runner.STALL_RC]
    assert json.loads(runner.STALL.read_text("utf-8"))["reason"] == "run_deadline"


def test_no_heartbeat_is_published_before_the_lane_is_held(monkeypatch):
    """A run refused the lane (rc 75) must never overwrite the lane holder's heartbeat."""
    dog = runner.SweepWatchdog(beat_s=30, clock=lambda: 0.0, sampler=_FakeTree(),
                               lane=lambda: False, exit_fn=lambda rc: None)
    dog.tick()
    dog.finish(runner.LANE_HELD_RC)
    assert not runner.HEARTBEAT.exists()


def test_deadlines_are_derived_from_measured_walls_and_widen_per_stall(monkeypatch):
    # the seed: 3x the longest measured merge (6,108 s)
    assert runner.phase_deadline_s("merge_and_publish", 0, {}) == 3 * 6108.0
    assert runner.phase_deadline_s("done", 0, {}) is None
    # this box's own history wins over the seed, and is floored at an hour
    times = {"phases": {"merge_and_publish": [100.0, 200.0]},
             "shards": {"rule": [50.0, 700.0]}, "sweeps": [5000.0]}
    assert runner.phase_deadline_s("merge_and_publish", 0, times) == runner.PHASE_DEADLINE_FLOOR_S
    assert runner.shard_timeout_s("rule", 0, times) == 3 * 700.0
    assert runner.run_deadline_s(0, times) == runner.RUN_DEADLINE_FLOOR_S
    # before any shard is measured, a shard may take as long as its whole measured wave
    assert runner.shard_timeout_s("build", 0, {}) == runner.MEASURED_PHASE_S["build_shards"]
    # a slow (not stuck) phase still finishes: each consecutive stall doubles, to the cap
    assert runner.phase_deadline_s("merge_and_publish", 1, {}) == 2 * 3 * 6108.0
    assert runner.phase_deadline_s("merge_and_publish", 30, {}) == runner.RESIDENT_HANG_CAP_S
    # an operator ceiling is honoured; zero or junk can never switch a ceiling off
    monkeypatch.setenv("GAUNTLET_PHASE_DEADLINE_S", "900")
    assert runner.phase_deadline_s("plan", 0, {}) == 900.0
    monkeypatch.setenv("GAUNTLET_PHASE_DEADLINE_S", "0")
    assert runner.phase_deadline_s("plan", 0, {}) == 3 * runner.MEASURED_PHASE_S["plan"]
    monkeypatch.setenv("GAUNTLET_SHARD_TIMEOUT_S", "junk")
    assert runner.shard_timeout_s("rule", 0, {}) == max(runner.SHARD_TIMEOUT_FLOOR_S,
                                                       runner.MEASURED_PHASE_S["rule_shards"])


def test_a_finished_sweep_clears_the_stall_and_records_its_walls(monkeypatch):
    runner.record_stall("no_progress", detail="x")
    runner.record_stall("no_progress", detail="y")
    assert runner.consecutive_stalls() == 2
    runner._PHASE_DOC.update(phases={"plan": 100.0, "merge_and_publish": 5000.0},
                             _t0=time.time() - 6000.0)
    runner._sweep_succeeded()
    st = json.loads(runner.STALL.read_text("utf-8"))
    assert st["status"] == "CLEAR" and st["consecutive"] == 0 and len(st["history"]) == 2
    times = json.loads(runner.PHASE_TIMES.read_text("utf-8"))
    assert times["phases"]["merge_and_publish"] == [5000.0] and times["sweeps"][0] >= 6000.0


def _write_hb(pid: int, *, beat_age_s: float, create_time: float | None,
              deadline_in_s: float = 3600.0) -> None:
    now = datetime.now(UTC)
    runner._write_json_atomic(runner.HEARTBEAT, {
        "pid": pid, "create_time": create_time, "status": "RUNNING", "phase": "merge_and_publish",
        "beat_utc": (now - timedelta(seconds=beat_age_s)).isoformat(timespec="seconds"),
        "run_deadline_utc": (now + timedelta(seconds=deadline_in_s)).isoformat(
            timespec="seconds")})


def test_a_dead_prior_sweep_is_recorded_and_a_wedged_one_is_taken_over(tmp_path):
    # DEAD: the pid is gone, the heartbeat still says RUNNING
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    _write_hb(dead.pid, beat_age_s=5, create_time=1.0)
    assert runner.take_over_stale()["action"] == "recorded_dead"
    st = json.loads(runner.STALL.read_text("utf-8"))
    assert st["reason"] == "died_unrecorded" and st["consecutive"] == 0
    assert json.loads(runner.HEARTBEAT.read_text("utf-8"))["status"] == "DEAD"

    # ALIVE AND FRESH: left alone
    stuck = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
    try:
        born = psutil.Process(stuck.pid).create_time()
        _write_hb(stuck.pid, beat_age_s=5, create_time=born)
        assert runner.take_over_stale() is None
        # ALIVE BUT ITS WATCHDOG IS WEDGED: killed, and the stall is named
        _write_hb(stuck.pid, beat_age_s=runner.HEARTBEAT_STALE_S + 60, create_time=born)
        took = runner.take_over_stale()
        assert took["action"] == "killed" and took["pid"] == stuck.pid
        stuck.wait(timeout=15)
        st = json.loads(runner.STALL.read_text("utf-8"))
        assert st["reason"] == "takeover" and st["consecutive"] == 1
    finally:
        if stuck.poll() is None:
            stuck.kill()


def test_a_reused_pid_never_holds_a_sweep_lock(tmp_path):
    import socket

    locks = runner._lock_root()
    me = psutil.Process(os.getpid()).create_time()
    old = datetime.fromtimestamp(me - 600, UTC).isoformat()
    new = datetime.fromtimestamp(me + 0.5, UTC).isoformat()
    (locks / "certification_lane.json").write_text(json.dumps(
        {"pid": os.getpid(), "host": socket.gethostname(), "started_at": old}))
    (locks / "external_gauntlet.json").write_text(json.dumps(
        {"pid": os.getpid(), "host": socket.gethostname(), "started_at": new}))
    assert runner._reclaim_reused_locks() == ["certification_lane"]
    assert (locks / "external_gauntlet.json").exists()


def test_the_resident_kills_a_child_whose_watchdog_went_quiet(monkeypatch):
    class _Child:
        pid = 31337

        def wait(self, timeout=None):
            raise subprocess.TimeoutExpired("sweep", timeout or 0)

    killed: list[int] = []
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: _Child())
    monkeypatch.setattr(runner, "_kill_sweep_tree", killed.append)
    monkeypatch.setattr(runner, "_sweep_env", lambda: {})
    _write_hb(_Child.pid, beat_age_s=runner.HEARTBEAT_STALE_S + 30, create_time=None)
    assert runner._one_sweep_child(None, poll_s=0.01) == runner.RESIDENT_HANG_RC
    assert killed == [_Child.pid]
    st = json.loads(runner.STALL.read_text("utf-8"))
    assert st["reason"] == "resident_kill" and "watchdog is wedged" in st["detail"]
    # recorded once: the next sweep's takeover does not report it again as unrecorded
    assert json.loads(runner.HEARTBEAT.read_text("utf-8"))["status"] == "KILLED_BY_RESIDENT"
    assert runner.take_over_stale() is None


def test_the_write_survives_a_read_only_destination(tmp_path):
    """Windows: `os.replace` onto a read-only file raises WinError 5; the report still lands."""
    import stat

    target = tmp_path / "ro.json"
    target.write_text("{}")
    os.chmod(target, stat.S_IREAD)
    try:
        runner._write_json_atomic(target, {"ok": True})
        assert json.loads(target.read_text("utf-8")) == {"ok": True}
    finally:
        os.chmod(target, stat.S_IWRITE | stat.S_IREAD)


# ---------------------------------------------------------------- the fence reads it as RED
def _fence():
    import check_judge_coverage as fence
    return fence


def test_the_coverage_fence_reads_a_stall_as_red_on_the_box(tmp_path):
    fence = _fence()
    hb, st = tmp_path / "hb.json", tmp_path / "st.json"
    assert fence.judge_liveness(heartbeat=hb, stall=st)["state"] == "UNMEASURED"
    st.write_text(json.dumps({"status": "STALLED", "reason": "phase_deadline:merge_and_publish",
                              "stalled_utc": "2026-10-20T07:00:00+00:00", "consecutive": 1}))
    assert fence.judge_liveness(heartbeat=hb, stall=st)["state"] == "FAIL"
    report = tmp_path / "missing.json"
    box = fence.judge(report=report, require_state=True, liveness=True, heartbeat=hb, stall=st)
    assert box["verdict"] == "FAIL" and box["checks"][-1]["metric"] == "judge_alive"
    # off the box a published stall WARNs: a commit is not blamed for a box incident
    off = fence.judge(report=report, require_state=False, liveness=True, heartbeat=hb, stall=st)
    assert off["verdict"] == "UNMEASURED" and off["checks"][-1]["state"] == "WARN"
    # a cleared stall and a fresh RUNNING heartbeat pass
    st.write_text(json.dumps({"status": "CLEAR", "consecutive": 0}))
    now = datetime.now(UTC)
    hb.write_text(json.dumps({"status": "RUNNING", "pid": 1, "phase": "plan",
                              "beat_utc": now.isoformat(),
                              "run_deadline_utc": (now + timedelta(hours=9)).isoformat()}))
    assert fence.judge_liveness(heartbeat=hb, stall=st)["state"] == "PASS"
    # ...a stale one does not
    hb.write_text(json.dumps({"status": "RUNNING", "pid": 1, "phase": "plan",
                              "beat_utc": (now - timedelta(minutes=30)).isoformat()}))
    assert fence.judge_liveness(heartbeat=hb, stall=st)["state"] == "FAIL"
    # ...nor one still RUNNING past its own deadline
    hb.write_text(json.dumps({"status": "RUNNING", "pid": 1, "phase": "merge_and_publish",
                              "beat_utc": now.isoformat(),
                              "run_deadline_utc": (now - timedelta(hours=1)).isoformat()}))
    assert fence.judge_liveness(heartbeat=hb, stall=st)["state"] == "FAIL"


def test_a_handed_in_report_is_never_coloured_by_box_liveness(tmp_path):
    fence = _fence()
    out = fence.judge(report=tmp_path / "missing.json", require_state=False)
    assert all(c.get("metric") != "judge_alive" for c in out.get("checks") or [])
