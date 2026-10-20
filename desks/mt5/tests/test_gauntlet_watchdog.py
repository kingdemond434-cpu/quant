"""The --once sweep can never stall silently -- and a slow sweep is never killed (2026-10-20).

The first cut of this watchdog took pid 7324 for a hung sweep. It was not: it finished rc 0 after
64,711 s, its merge alone 51,198 s, and the merge deadline that cut seeded at 6,108 s x 3 would
have killed it nine hours before it published (audit HOLD of 2832cebd1). These tests pin the
re-cut: every phase, run and shard threshold is AMBER -- a SLOW record, and the sweep keeps
going while its tree burns CPU -- and the one kill is NO PROGRESS, measured per process. A kill
names its orphans, restores the merge's authority files if they no longer parse, releases the
run's locks, and is a missed-growth line. A dead child never leaves the parent waiting; a dead
prior sweep is recorded, never killed; a live one is killed only when its idleness is measured
twice and its identity is proven in code.
"""

from __future__ import annotations

import json
import os
import socket
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
    """No test reads or writes the desk's real heartbeat, stall, timing, snapshot or lock files."""
    for name, fname in (
        ("SHARD_PEAKS", "judge_shard_peaks.json"),
        ("RESIDENT_STATE", "JUDGE_RESIDENT.json"),
        ("RESIDENT_STOP", "RESIDENT_STOP"),
        ("SWEEP_PHASE", "JUDGE_SWEEP_PHASE.json"),
        ("HEARTBEAT", "GAUNTLET_HEARTBEAT.json"),
        ("STALL", "GAUNTLET_STALL.json"),
        ("PHASE_TIMES", "judge_phase_times.json"),
        ("MERGE_SNAPSHOT", "snap"),
    ):
        monkeypatch.setattr(runner, name, tmp_path / fname)
    monkeypatch.setattr(
        runner,
        "MERGE_OUTPUTS",
        (tmp_path / "universal_gates_external.json", tmp_path / "UNIVERSAL_SURVIVORS.json"),
    )
    monkeypatch.setattr(runner, "_PHASE_DOC", {})
    monkeypatch.setattr(runner, "_PROGRESS", {})
    monkeypatch.setattr(runner, "SHARD_POLL_S", 0.1)
    locks = tmp_path / "locks"
    locks.mkdir()
    monkeypatch.setattr(runner, "_lock_root", lambda: locks)
    for var in (
        "GAUNTLET_SHARD_TIMEOUT_S",
        "GAUNTLET_PHASE_DEADLINE_S",
        "GAUNTLET_RUN_DEADLINE_S",
        "GAUNTLET_NO_PROGRESS_S",
        "GAUNTLET_HEARTBEAT_S",
        "GAUNTLET_SHARD_CONCURRENCY",
        "GAUNTLET_SHARD_RETRIES",
    ):
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


def _stall() -> dict:
    return json.loads(runner.STALL.read_text("utf-8"))


#: A shard child that starts a grandchild, records both pids, and then sleeps: an IDLE tree.
_IDLE = textwrap.dedent("""
    import subprocess, sys, time
    g = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
    with open(sys.argv[1], "a") as fh:
        fh.write(f"{g.pid}\\n")
    time.sleep(120)
""")
#: A shard child that is SLOW but working: it burns CPU for a few seconds, then succeeds.
_BUSY = "import time\nend = time.monotonic() + 2.5\nwhile time.monotonic() < end:\n    pass\n"


def test_a_slow_but_progressing_shard_is_never_killed_and_reads_amber(monkeypatch, tmp_path):
    """The audit's point: past its threshold a working shard is SLOW and left to finish."""

    def fake(argv, **kw):
        return runner._watched_run([sys.executable, "-c", _BUSY], **kw)

    monkeypatch.setenv("GAUNTLET_SHARD_TIMEOUT_S", "0.5")  # the SLOW threshold
    monkeypatch.setenv("GAUNTLET_NO_PROGRESS_S", "1.5")  # the kill window
    monkeypatch.setattr(runner, "run", fake)
    runner.dispatch(tmp_path / "shards", 1, "rule")  # returns: it finished
    st = _stall()
    assert st["status"] == "SLOW" and st["slow"]["reason"] == "shard_slow"
    assert "left running" in st["slow"]["detail"] and st["consecutive"] == 0
    assert not st.get("missed_growth"), "nothing was killed, so nothing was lost"
    times = json.loads(runner.PHASE_TIMES.read_text("utf-8"))
    assert times["shards"]["rule"][0] >= 2.0, "its real wall is measured for the next threshold"


def test_an_idle_hung_shard_is_killed_with_its_tree_by_no_progress(monkeypatch, tmp_path):
    pids = tmp_path / "grandchildren.txt"
    started: list[int] = []

    def fake(argv, **kw):
        k = int(argv[-2])
        started.append(k)
        if k == 0:
            return runner._watched_run([sys.executable, "-c", _IDLE, str(pids)], **kw)
        return runner._watched_run([sys.executable, "-c", "pass"], **kw)

    monkeypatch.setenv("GAUNTLET_NO_PROGRESS_S", "1.5")
    monkeypatch.setenv("GAUNTLET_SHARD_CONCURRENCY", "1")
    monkeypatch.setattr(runner, "run", fake)
    t0 = time.monotonic()
    with pytest.raises(runner.ShardStalled) as err:
        runner.dispatch(tmp_path / "shards", 4, "build")
    assert err.value.k == 0 and err.value.why == "no_progress"
    assert time.monotonic() - t0 < 30
    for gpid in (int(x) for x in pids.read_text().split()):
        assert _wait_gone(gpid), f"grandchild {gpid} survived the no-progress kill"
    st = _stall()
    assert st["status"] == "STALLED" and st["reason"] == "shard_no_progress"
    assert st["shard"]["k"] == 0 and st["shard"]["phase"] == "build" and st["consecutive"] == 1
    assert st["kill"]["orphans"] == [] and st["kill"]["killed"] >= 1
    assert started == [0], "the wave stopped handing out work"
    assert "3 shard(s) of the wave were not started" in st["detail"]
    line = st["missed_growth"][-1]
    assert line["rail"] == "gauntlet_watchdog" and line["kind"] == "opportunity_cost"
    assert line["verdict"] == "UNMEASURED" and line["reason"] == "shard_no_progress"


def test_a_child_that_dies_never_leaves_the_parent_waiting(monkeypatch, tmp_path):
    """An OOM-killed shard is a failed child, retried and then refused -- never a wait."""
    die = "import os, signal; os.kill(os.getpid(), getattr(signal, 'SIGKILL', 9))"

    def fake(argv, **kw):
        return runner._watched_run([sys.executable, "-c", die], **kw)

    monkeypatch.setenv("GAUNTLET_SHARD_RETRIES", "1")
    monkeypatch.setattr(runner, "run", fake)
    t0 = time.monotonic()
    with pytest.raises(RuntimeError, match="refusing partial merge"):
        runner.dispatch(tmp_path / "shards", 2, "rule")
    assert time.monotonic() - t0 < 30
    assert not runner.STALL.exists(), "a death is a failure the resident retries, not a stall"


#: A --once stand-in: the real watchdog over a main thread that never returns, in its own
#: process so `os._exit`, the descendant kill and the merge-file restore are exercised for real.
#: The idle threshold is raised to 0.1 core so the watchdog's own sampling never reads as work.
_STUCK_SWEEP = textwrap.dedent("""
    import json, subprocess, sys, time
    from pathlib import Path
    sys.path[:0] = [{root!r}, {desk!r}]
    from scripts import run_sharded_gauntlet as r
    tmp = Path({tmp!r})
    r.HEARTBEAT, r.STALL = tmp / "GAUNTLET_HEARTBEAT.json", tmp / "GAUNTLET_STALL.json"
    r.PHASE_TIMES, r.SWEEP_PHASE = tmp / "judge_phase_times.json", tmp / "phase.json"
    r.MERGE_OUTPUTS = (tmp / "universal_gates_external.json", tmp / "UNIVERSAL_SURVIVORS.json")
    r.MERGE_SNAPSHOT = tmp / "snap"
    r.NO_PROGRESS_CORES = 0.1
    r._lock_root = lambda: tmp / "locks"
    (tmp / "locks" / "certification_lane.json").write_text(json.dumps(
        {{"pid": __import__("os").getpid(), "host": __import__("socket").gethostname(),
          "started_at": "2026-10-20T00:00:00+00:00"}}))
    for f in r.MERGE_OUTPUTS:
        f.write_text(json.dumps({{"verdicts": [1, 2, 3], "name": f.name}}))
    g = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
    (tmp / "grandchild.txt").write_text(str(g.pid))
    r._phase("merge_and_publish")
    r.snapshot_merge_outputs()
    r.MERGE_OUTPUTS[0].write_text('{{"verdicts": [1, 2')      # killed mid-write
    r.SweepWatchdog(beat_s=0.5, lane=lambda: True).start()
    time.sleep(120)          # the sealed merge that never returns, burning nothing
""")


def test_an_idle_sweep_is_killed_restores_the_merge_files_and_exits(tmp_path):
    script = _STUCK_SWEEP.format(root=str(ROOT), desk=str(DESK), tmp=str(tmp_path))
    # the phase threshold is far off: only the no-progress rule may end this run
    env = {**os.environ, "GAUNTLET_NO_PROGRESS_S": "2", "GAUNTLET_PHASE_DEADLINE_S": "9999"}
    t0 = time.monotonic()
    proc = subprocess.run(
        [sys.executable, "-c", script],
        env=env,
        timeout=60,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == runner.STALL_RC, (proc.returncode, proc.stderr[-2000:])
    assert time.monotonic() - t0 < 30
    st = json.loads((tmp_path / "GAUNTLET_STALL.json").read_text("utf-8"))
    assert st["status"] == "STALLED" and st["reason"] == "no_progress"
    assert st["phase"] == "merge_and_publish" and st["last_progress"]["beat_utc"]
    assert st["restored_from_merge_snapshot"] == ["universal_gates_external.json"]
    assert st["missed_growth"][-1]["lost_s"] is not None
    restored = json.loads((tmp_path / "universal_gates_external.json").read_text("utf-8"))
    assert restored["verdicts"] == [1, 2, 3], "the torn authority file was put back"
    hb = json.loads((tmp_path / "GAUNTLET_HEARTBEAT.json").read_text("utf-8"))
    assert hb["status"] == "STALLED" and hb["killed"] >= 1 and hb["orphans"] == []
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
    dog = runner.SweepWatchdog(
        beat_s=30, clock=clock, sampler=tree, lane=lambda: True, exit_fn=exits.append, **kw
    )
    return dog, exits


def test_a_phase_past_its_threshold_with_cpu_progress_is_slow_and_keeps_going(monkeypatch):
    """pid 7324's case: the merge ran 51,198 s and was working all the way."""
    now = [0.0]
    tree = _FakeTree()
    monkeypatch.setattr(runner, "_kill_descendants", lambda pid: pytest.fail("killed a sweep"))
    monkeypatch.setenv("GAUNTLET_PHASE_DEADLINE_S", "100")
    monkeypatch.setenv("GAUNTLET_RUN_DEADLINE_S", "300")
    dog, exits = _dog(lambda: now[0], tree)
    runner._PHASE_DOC.update(phase="merge_and_publish", _t=0.0, phases={})
    for _ in range(20):  # 20 minutes, one busy core
        now[0] += 60
        tree.cpu += 60
        dog.tick()
    assert exits == []
    st = _stall()
    assert st["status"] == "SLOW" and st["consecutive"] == 0
    reasons = [h["reason"] for h in st["history"]]
    assert reasons.count("phase_deadline:merge_and_publish") == 1, "recorded once, not per beat"
    assert reasons.count("run_deadline") == 1
    hb = json.loads(runner.HEARTBEAT.read_text("utf-8"))
    assert hb["status"] == "RUNNING"
    assert set(hb["slow"]) == {"phase_deadline:merge_and_publish", "run_deadline"}


def test_a_tree_that_burns_no_cpu_is_the_only_kill(monkeypatch):
    now = [1000.0]
    tree = _FakeTree()
    monkeypatch.setattr(runner, "_kill_descendants", lambda pid: {"killed": 0, "orphans": []})
    dog, exits = _dog(lambda: now[0], tree)
    runner._PHASE_DOC.update(phase="plan", _t=now[0], phases={})
    for _ in range(10):  # working: 30 cpu-s per 60 s
        now[0] += 60
        tree.cpu += 30
        dog.tick()
    assert not exits
    hb = json.loads(runner.HEARTBEAT.read_text("utf-8"))
    assert hb["status"] == "RUNNING" and hb["idle_s"] == 0.0 and hb["tree"]["procs"] == 1
    for _ in range(int(runner.NO_PROGRESS_S // 60) + 2):  # silent: no CPU at all
        now[0] += 60
        dog.tick()
        if exits:
            break
    assert exits == [runner.STALL_RC]
    st = _stall()
    assert st["reason"] == "no_progress" and st["missed_growth"][-1]["lost_s"] > 0


def test_unmeasured_progress_never_kills(monkeypatch):
    """No psutil: the thresholds still write SLOW, and nothing is ever killed."""
    now = [0.0]
    monkeypatch.setenv("GAUNTLET_RUN_DEADLINE_S", "100")
    dog, exits = _dog(lambda: now[0], lambda pid: None)
    for _ in range(int(runner.NO_PROGRESS_CAP_S // 600) + 2):
        now[0] += 600
        dog.tick()
    assert exits == [] and _stall()["status"] == "SLOW"


def test_no_heartbeat_is_published_before_the_lane_is_held(monkeypatch):
    """A run refused the lane (rc 75) must never overwrite the lane holder's heartbeat."""
    dog = runner.SweepWatchdog(
        beat_s=30,
        clock=lambda: 0.0,
        sampler=_FakeTree(),
        lane=lambda: False,
        exit_fn=lambda rc: None,
    )
    dog.tick()
    dog.finish(runner.LANE_HELD_RC)
    assert not runner.HEARTBEAT.exists()


def test_thresholds_are_the_max_of_history_and_the_measured_seed(monkeypatch):
    seed = runner.MEASURED_PHASE_S
    # THE SEED IS WHAT THE BOX MEASURED: a 51,198 s merge and a 64,711 s sweep
    assert seed["merge_and_publish"] == 51198.0 and runner.MEASURED_SWEEP_S == 64711.4
    assert runner.phase_deadline_s("merge_and_publish", 0, {}) == 3 * 51198.0
    assert runner.phase_deadline_s("done", 0, {}) is None
    # max(history, seed), never `history or seed`: one fast merge cannot drop the floor
    times = {
        "phases": {"merge_and_publish": [100.0, 200.0]},
        "shards": {"rule": [50.0, 700.0]},
        "sweeps": [5000.0],
    }
    assert runner.phase_deadline_s("merge_and_publish", 0, times) == 3 * 51198.0
    assert runner.run_deadline_s(0, times) == 2 * 64711.4
    assert runner.shard_timeout_s("rule", 0, times) == 3 * 700.0
    # ...and a longer history raises it
    longer = {"phases": {"merge_and_publish": [55000.0]}, "sweeps": [80000.0]}
    assert runner.phase_deadline_s("merge_and_publish", 0, longer) == 3 * 55000.0
    assert runner.run_deadline_s(0, longer) == 2 * 80000.0
    # a shard's threshold is never under its whole measured wave
    assert runner.shard_timeout_s("build", 0, {}) == seed["build_shards"]
    # each consecutive stall doubles a threshold, to the cap
    assert runner.phase_deadline_s("plan", 1, {}) == 2 * 3 * seed["plan"]
    assert runner.phase_deadline_s("merge_and_publish", 30, {}) == runner.RESIDENT_HANG_CAP_S
    # an operator value is honoured; zero or junk can never switch one off
    monkeypatch.setenv("GAUNTLET_PHASE_DEADLINE_S", "900")
    assert runner.phase_deadline_s("plan", 0, {}) == 900.0
    monkeypatch.setenv("GAUNTLET_PHASE_DEADLINE_S", "0")
    assert runner.phase_deadline_s("plan", 0, {}) == 3 * seed["plan"]
    monkeypatch.setenv("GAUNTLET_SHARD_TIMEOUT_S", "junk")
    assert runner.shard_timeout_s("rule", 0, {}) == max(
        runner.SHARD_TIMEOUT_FLOOR_S, seed["rule_shards"]
    )


def test_a_finished_sweep_clears_the_stall_records_its_walls_and_drops_the_snapshot():
    runner.record_stall("no_progress", detail="x")
    runner.record_stall("no_progress", detail="y")
    assert runner.consecutive_stalls() == 2
    runner.MERGE_OUTPUTS[0].write_text("{}")
    runner.snapshot_merge_outputs()
    assert (runner.MERGE_SNAPSHOT / "universal_gates_external.json").exists()
    runner._PHASE_DOC.update(
        phases={"plan": 100.0, "merge_and_publish": 5000.0}, _t0=time.time() - 6000.0
    )
    runner._sweep_succeeded()
    st = _stall()
    assert st["status"] == "CLEAR" and st["consecutive"] == 0 and len(st["history"]) == 2
    assert len(st["missed_growth"]) == 2, "the bill is history; a clear does not erase it"
    times = json.loads(runner.PHASE_TIMES.read_text("utf-8"))
    assert times["phases"]["merge_and_publish"] == [5000.0] and times["sweeps"][0] >= 6000.0
    assert not runner.MERGE_SNAPSHOT.exists()


def test_the_snapshot_is_dropped_only_on_positive_evidence():
    """v4.1: an output that is absent or unparseable at removal time keeps the snapshot."""
    runner.MERGE_OUTPUTS[0].write_text("{}")
    runner.snapshot_merge_outputs()
    runner.MERGE_OUTPUTS[0].write_text("{trunc")            # the sealed writer died mid-file
    runner._PARSE_CACHE.clear()
    assert runner._drop_merge_snapshot() is False
    assert (runner.MERGE_SNAPSHOT / "universal_gates_external.json").exists()
    runner.MERGE_OUTPUTS[0].unlink()                        # absent: still kept
    assert runner._drop_merge_snapshot() is False
    runner.MERGE_OUTPUTS[0].write_text("{}")                # read back and parses: removed
    runner._PARSE_CACHE.clear()
    assert runner._drop_merge_snapshot() is True
    assert not runner.MERGE_SNAPSHOT.exists()
    from libs.ops import reference_freshness as rf

    row = [p for p in rf.DESTRUCTIVE_PATHS if p.function == "_drop_merge_snapshot"]
    assert len(row) == 1 and row[0].status == "positive"


def test_a_slow_record_never_washes_an_unanswered_stall_amber():
    runner.record_stall("no_progress", detail="x")
    runner.record_slow("phase_deadline:plan", detail="slow")
    st = _stall()
    assert st["status"] == "STALLED" and st["slow"]["reason"] == "phase_deadline:plan"
    assert st["consecutive"] == 1


def _write_hb(
    pid: int,
    *,
    beat_age_s: float,
    create_time: object,
    deadline_in_s: float = 3600.0,
    cpu_s: float | None = None,
) -> None:
    now = datetime.now(UTC)
    runner._write_json_atomic(
        runner.HEARTBEAT,
        {
            "pid": pid,
            "create_time": create_time,
            "status": "RUNNING",
            "phase": "merge_and_publish",
            "started_utc": (now - timedelta(seconds=beat_age_s + 600)).isoformat(
                timespec="seconds"
            ),
            "beat_utc": (now - timedelta(seconds=beat_age_s)).isoformat(timespec="seconds"),
            "tree": None if cpu_s is None else {"procs": 1, "rss_mb": 1.0, "cpu_s": cpu_s},
            "run_deadline_utc": (now + timedelta(seconds=deadline_in_s)).isoformat(
                timespec="seconds"
            ),
        },
    )


def _spawn(code: str, *extra: str) -> subprocess.Popen:
    p = subprocess.Popen([sys.executable, "-c", code, *extra])
    time.sleep(0.3)
    return p


def _cpu(pid: int) -> float:
    t = psutil.Process(pid).cpu_times()
    return float(t.user) + float(t.system)


def test_a_dead_prior_sweep_is_recorded_never_killed():
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    _write_hb(dead.pid, beat_age_s=5, create_time=1.0)
    assert runner.take_over_stale()["action"] == "recorded_dead"
    st = _stall()
    assert st["reason"] == "died_unrecorded" and st["consecutive"] == 0
    assert st["missed_growth"][-1]["lost_s"] is not None
    assert json.loads(runner.HEARTBEAT.read_text("utf-8"))["status"] == "DEAD"


def test_an_unparseable_create_time_is_treated_as_dead_and_nothing_is_killed(monkeypatch):
    live = _spawn("import time; time.sleep(60)", "run_sharded_gauntlet.py", "--once")
    try:
        monkeypatch.setattr(runner, "_kill_sweep_tree", lambda pid: pytest.fail("killed"))
        _write_hb(live.pid, beat_age_s=99999, create_time="not-a-number")
        assert runner._alive_as(live.pid, "not-a-number") is False
        assert runner._alive_as(live.pid, None) is False
        assert runner.take_over_stale()["action"] == "recorded_dead"
        assert live.poll() is None, "identity unproven: recorded, never killed"
    finally:
        live.kill()
        live.wait()


def test_a_live_prior_sweep_is_killed_only_on_measured_idleness_and_proven_identity(monkeypatch):
    monkeypatch.setenv("GAUNTLET_NO_PROGRESS_S", "600")
    idle = _spawn("import time; time.sleep(60)", "run_sharded_gauntlet.py", "--once")
    busy = _spawn("while True: pass", "run_sharded_gauntlet.py", "--once")
    plain = _spawn("import time; time.sleep(60)")
    try:
        # FRESH: left alone
        born = psutil.Process(idle.pid).create_time()
        _write_hb(idle.pid, beat_age_s=5, create_time=born, cpu_s=_cpu(idle.pid))
        assert runner.take_over_stale(sample_s=0.5) is None
        # A QUIET HEARTBEAT BUT A BURNING TREE: SLOW, left running
        bborn = psutil.Process(busy.pid).create_time()
        _write_hb(busy.pid, beat_age_s=700, create_time=bborn, cpu_s=0.0)
        took = runner.take_over_stale(sample_s=0.5)
        assert took["action"] == "left_running" and busy.poll() is None
        assert _stall()["status"] == "SLOW"
        # PAST ITS THRESHOLD WITH A FRESH BEAT: its own watchdog's business, never a takeover
        _write_hb(busy.pid, beat_age_s=5, create_time=bborn, deadline_in_s=-7200)
        assert runner.take_over_stale(sample_s=0.5) is None
        # IDLE, BUT NOT PROVABLY A --once SWEEP: never killed
        pborn = psutil.Process(plain.pid).create_time()
        _write_hb(plain.pid, beat_age_s=700, create_time=pborn, cpu_s=_cpu(plain.pid))
        took = runner.take_over_stale(sample_s=0.5)
        assert took["action"] == "left_running" and plain.poll() is None
        assert any("identity not proven" in w for w in took["why"])
        # IDLE SINCE ITS BEAT, IDLE LIVE, AND PROVABLY THE SWEEP: killed, recorded, billed
        _write_hb(idle.pid, beat_age_s=700, create_time=born, cpu_s=_cpu(idle.pid))
        took = runner.take_over_stale(sample_s=0.5)
        assert took["action"] == "killed" and took["pid"] == idle.pid
        idle.wait(timeout=15)
        st = _stall()
        assert st["reason"] == "takeover" and st["consecutive"] == 1
        assert st["kill"]["orphans"] == [] and st["missed_growth"][-1]["reason"] == "takeover"
    finally:
        for p in (idle, busy, plain):
            if p.poll() is None:
                p.kill()
            p.wait()


def _lock(name: str, pid: int, started: float) -> Path:
    path = runner._lock_root() / f"{name}.json"
    path.write_text(
        json.dumps(
            {
                "pid": pid,
                "host": socket.gethostname(),
                "started_at": datetime.fromtimestamp(started, UTC).isoformat(),
            }
        )
    )
    return path


def test_a_reused_pid_is_reclaimed_but_never_from_a_possible_writer():
    plain = _spawn("import time; time.sleep(60)")
    certifier = _spawn("import time; time.sleep(60)", "certifier_launcher.py")
    try:
        pborn = psutil.Process(plain.pid).create_time()
        cborn = psutil.Process(certifier.pid).create_time()
        # a dead owner's lock, its pid now a miner born long after the stamp: reclaimed
        lane = _lock("certification_lane", plain.pid, pborn - 3600)
        assert runner._reclaim_reused_locks() == ["certification_lane"] and not lane.exists()
        # the same, but the pid now runs certifier_launcher (which takes certification_lane
        # itself): NEVER reclaimed, whatever the clocks say -- two writers are impossible
        lane = _lock("certification_lane", certifier.pid, cborn - 3600)
        assert runner._reclaim_reused_locks() == [] and lane.exists()
        # a wall clock stepped back 100 s: the writer looks "born after" its own lock, inside
        # the margin, so it is left alone
        lane = _lock("certification_lane", plain.pid, pborn - 100)
        assert runner._reclaim_reused_locks() == [] and lane.exists()
        # our own lock is never ours to reclaim
        own = _lock("external_gauntlet", os.getpid(), 0.0)
        assert runner._reclaim_reused_locks() == [] and own.exists()
        assert runner._is_certifier(None) is True
        assert runner._is_certifier("python run_sharded_gauntlet.py") is False  # the resident
        assert runner._is_certifier("python run_sharded_gauntlet.py --once") is True
    finally:
        for p in (plain, certifier):
            p.kill()
            p.wait()


class _Child:
    """A sweep child that runs `polls` resident polls, then exits rc 0 (or never, when None)."""

    def __init__(self, polls: int | None) -> None:
        self.pid = 31337
        self.left = polls

    def wait(self, timeout=None):
        if self.left is not None:
            self.left -= 1
            if self.left < 0:
                return 0
        raise subprocess.TimeoutExpired("sweep", timeout or 0)


def test_the_resident_lets_a_slow_progressing_sweep_finish(monkeypatch):
    child = _Child(polls=40)
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: child)
    monkeypatch.setattr(runner, "_kill_sweep_tree", lambda pid: pytest.fail("killed a sweep"))
    monkeypatch.setattr(runner, "_sweep_env", lambda: {})
    t, tree = [0.0], _FakeTree()

    def clock():
        t[0] += 600.0
        tree.cpu += 600.0  # one busy core, all the way
        return t[0]

    assert runner._one_sweep_child(1200.0, poll_s=0.0, clock=clock, sampler=tree) == 0
    st = _stall()
    assert st["status"] == "SLOW" and st["slow"]["reason"] == "resident_slow"
    assert [h["reason"] for h in st["history"]].count("resident_slow") == 1


def test_the_resident_kills_an_idle_sweep_and_records_it_once(monkeypatch):
    child = _Child(polls=None)
    killed: list[int] = []
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: child)
    monkeypatch.setattr(
        runner, "_kill_sweep_tree", lambda pid: killed.append(pid) or {"killed": 3, "orphans": []}
    )
    monkeypatch.setattr(runner, "_sweep_env", lambda: {})
    _write_hb(child.pid, beat_age_s=runner.HEARTBEAT_STALE_S + 30, create_time=None)
    t, tree = [0.0], _FakeTree()

    def clock():
        t[0] += 60.0
        return t[0]

    assert (
        runner._one_sweep_child(None, poll_s=0.0, clock=clock, sampler=tree)
        == runner.RESIDENT_HANG_RC
    )
    assert killed == [child.pid]
    st = _stall()
    assert st["reason"] == "resident_kill" and "measured by the resident" in st["detail"]
    assert st["kill"]["killed"] == 3 and st["missed_growth"][-1]["lost_s"] > 0
    assert t[0] > runner.NO_PROGRESS_S, "never inside the child's own no-progress window"
    assert [h.get("reason") for h in st["history"]].count("resident_slow") == 1
    assert json.loads(runner.HEARTBEAT.read_text("utf-8"))["status"] == "KILLED_BY_RESIDENT"
    assert runner.take_over_stale() is None


def test_the_resident_never_kills_without_a_measurement(monkeypatch):
    child = _Child(polls=30)
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: child)
    monkeypatch.setattr(runner, "_kill_sweep_tree", lambda pid: pytest.fail("killed blind"))
    monkeypatch.setattr(runner, "_sweep_env", lambda: {})
    t = [0.0]

    def clock():
        t[0] += 3600.0
        return t[0]

    assert runner._one_sweep_child(7200.0, poll_s=0.0, clock=clock, sampler=lambda pid: None) == 0


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


def test_a_restore_only_replaces_a_file_that_no_longer_parses():
    a, b = runner.MERGE_OUTPUTS
    a.write_text(json.dumps({"v": 1}))
    b.write_text(json.dumps({"s": 1}))
    runner.snapshot_merge_outputs()
    a.write_text('{"v": ')  # torn
    b.write_text(json.dumps({"s": 2}))  # newer and whole: kept
    assert runner.restore_merge_outputs() == [a.name]
    assert json.loads(a.read_text()) == {"v": 1} and json.loads(b.read_text()) == {"s": 2}


# ---------------------------------------------------------------- the fence reads it right
def _fence():
    import check_judge_coverage as fence

    return fence


def test_the_coverage_fence_reads_a_kill_red_and_a_slow_sweep_amber(tmp_path):
    fence = _fence()
    hb, st = tmp_path / "hb.json", tmp_path / "st.json"
    assert fence.judge_liveness(heartbeat=hb, stall=st)["state"] == "UNMEASURED"
    st.write_text(
        json.dumps(
            {
                "status": "STALLED",
                "reason": "no_progress",
                "stalled_utc": "2026-10-20T07:00:00+00:00",
                "consecutive": 1,
            }
        )
    )
    assert fence.judge_liveness(heartbeat=hb, stall=st)["state"] == "FAIL"
    report = tmp_path / "missing.json"
    box = fence.judge(report=report, require_state=True, liveness=True, heartbeat=hb, stall=st)
    assert box["verdict"] == "FAIL" and box["checks"][-1]["metric"] == "judge_alive"
    off = fence.judge(report=report, require_state=False, liveness=True, heartbeat=hb, stall=st)
    assert off["verdict"] == "UNMEASURED" and off["checks"][-1]["state"] == "WARN"
    # SLOW IS AMBER: a recorded slow phase, and a RUNNING sweep past its run threshold
    st.write_text(
        json.dumps(
            {
                "status": "SLOW",
                "consecutive": 0,
                "slow": {
                    "reason": "phase_deadline:merge_and_publish",
                    "phase": "merge_and_publish",
                },
            }
        )
    )
    assert fence.judge_liveness(heartbeat=hb, stall=st)["state"] == "WARN"
    now = datetime.now(UTC)
    st.write_text(json.dumps({"status": "CLEAR", "consecutive": 0}))
    hb.write_text(
        json.dumps(
            {
                "status": "RUNNING",
                "pid": 1,
                "phase": "merge_and_publish",
                "beat_utc": now.isoformat(),
                "run_deadline_utc": (now - timedelta(hours=1)).isoformat(),
            }
        )
    )
    assert fence.judge_liveness(heartbeat=hb, stall=st)["state"] == "WARN"
    # a fresh RUNNING heartbeat with a clear record passes
    hb.write_text(
        json.dumps(
            {
                "status": "RUNNING",
                "pid": 1,
                "phase": "plan",
                "beat_utc": now.isoformat(),
                "run_deadline_utc": (now + timedelta(hours=9)).isoformat(),
            }
        )
    )
    assert fence.judge_liveness(heartbeat=hb, stall=st)["state"] == "PASS"
    # a stale one (a wedged watchdog) does not
    hb.write_text(
        json.dumps(
            {
                "status": "RUNNING",
                "pid": 1,
                "phase": "plan",
                "beat_utc": (now - timedelta(minutes=30)).isoformat(),
            }
        )
    )
    assert fence.judge_liveness(heartbeat=hb, stall=st)["state"] == "FAIL"


def test_the_hourly_liveness_leg_exits_zero_on_amber_and_one_on_red(tmp_path):
    fence = _fence()
    hb, st = tmp_path / "hb.json", tmp_path / "st.json"
    st.write_text(json.dumps({"status": "SLOW", "slow": {"reason": "run_deadline"}}))
    doc = fence.liveness_fence(require_state=True, heartbeat=hb, stall=st)
    assert doc["verdict"] == "PASS" and doc["state"] == "WARN"
    st.write_text(json.dumps({"status": "STALLED", "reason": "no_progress"}))
    assert fence.liveness_fence(require_state=True, heartbeat=hb, stall=st)["verdict"] == "FAIL"
    assert fence.liveness_fence(require_state=False, heartbeat=hb, stall=st)["state"] == "WARN"


def test_judge_alive_is_an_hourly_core_leg():
    hc = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    core = hc[hc.index("CORE_LEGS: frozenset[str] = frozenset({") :]
    assert '"judge_alive"' in core[: core.index("})")]
    assert '_costed("judge_alive", judge_alive)' in hc and '"judge_alive": jal' in hc
    assert '"scripts/check_judge_coverage.py", "--liveness"' in hc
    from libs.research import layers

    assert layers.LEG_LAYER.get("judge_alive") == "meta"


def test_the_watchdog_bill_reaches_missed_growth():
    import research.missed_growth as mg

    assert mg.organ_published_lines(runner.STALL)["verdict"] == "UNMEASURED"
    runner.record_slow("run_deadline", detail="slow")
    assert mg.organ_published_lines(runner.STALL)["verdict"] == "NOT_BINDING"
    runner.record_stall("no_progress", detail="idle", lost_s=1234.5)
    got = mg.organ_published_lines(runner.STALL)
    assert got["verdict"] == "UNMEASURED" and got["lost_s"] == 1234.5


def test_a_handed_in_report_is_never_coloured_by_box_liveness(tmp_path):
    fence = _fence()
    out = fence.judge(report=tmp_path / "missing.json", require_state=False)
    assert all(c.get("metric") != "judge_alive" for c in out.get("checks") or [])


# ------------------------------------------------- v3: the audit of 7cf2ece90
@pytest.mark.skipif(sys.platform == "win32", reason="the probe holds the lock with fcntl")
def test_stall_writers_lose_nothing_across_threads():
    """4 threads x 25 stalls, interleaved with SLOW writes: every stall is counted, no red is
    washed amber (before the lock: 36 of 100 survived)."""
    import threading

    def worker(i: int) -> None:
        for j in range(25):
            runner.record_stall("no_progress", detail=f"t{i}-{j}", lost_s=1.0)
            runner.record_slow("run_deadline", detail=f"t{i}-{j}")

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    st = _stall()
    assert st["consecutive"] == 100 and st["status"] == "STALLED"
    assert len(st["missed_growth"]) == runner.MISSED_GROWTH_HISTORY
    assert st["lock"] == "LOCKED" and st.get("unlocked_writes", 0) == 0
    assert _lock_free(), "the OS lock is released after the last write"


_RACER = textwrap.dedent("""
    import sys
    from pathlib import Path
    sys.path[:0] = [{root!r}, {desk!r}]
    from scripts import run_sharded_gauntlet as r
    tmp = Path({tmp!r})
    r.HEARTBEAT, r.STALL = tmp / "GAUNTLET_HEARTBEAT.json", tmp / "GAUNTLET_STALL.json"
    for j in range(25):
        r.record_stall("no_progress", detail=f"p{{j}}", lost_s=1.0)
        r.record_slow("run_deadline", detail=f"p{{j}}")
""")


def test_stall_writers_lose_nothing_across_processes(tmp_path):
    """The resident and the sweep are different processes: the lock file serialises them."""
    script = _RACER.format(root=str(ROOT), desk=str(DESK), tmp=str(tmp_path))
    procs = [subprocess.Popen([sys.executable, "-c", script]) for _ in range(4)]
    assert [p.wait(timeout=120) for p in procs] == [0, 0, 0, 0]
    st = json.loads((tmp_path / "GAUNTLET_STALL.json").read_text("utf-8"))
    assert st["consecutive"] == 100 and st["status"] == "STALLED"


def _lock_free() -> bool:
    """Can a fresh descriptor take the stall lock right now (POSIX flock)?"""
    import fcntl

    fd = os.open(str(runner.STALL.with_name(f"{runner.STALL.name}.lock")), os.O_RDWR | os.O_CREAT)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(fd, fcntl.LOCK_UN)
        return True
    except BlockingIOError:
        return False
    finally:
        os.close(fd)


_HOLDER = textwrap.dedent("""
    import fcntl, os, sys, time
    fd = os.open(sys.argv[1], os.O_RDWR | os.O_CREAT)
    fcntl.flock(fd, fcntl.LOCK_EX)
    open(sys.argv[2], "w").write("held")
    time.sleep(120)
""")


def _hold_lock(tmp_path: Path) -> subprocess.Popen:
    flag = tmp_path / "held.flag"
    lock = runner.STALL.with_name(f"{runner.STALL.name}.lock")
    p = subprocess.Popen([sys.executable, "-c", _HOLDER, str(lock), str(flag)])
    end = time.monotonic() + 10
    while not flag.exists() and time.monotonic() < end:
        time.sleep(0.05)
    assert flag.exists()
    return p


@pytest.mark.skipif(sys.platform == "win32", reason="the probe holds the lock with fcntl")
def test_a_dead_holder_never_blocks_the_next_writer(tmp_path):
    """The OS drops the lock with its holder: no stale-break, so nothing can spin or race."""
    holder = _hold_lock(tmp_path)
    holder.kill()
    holder.wait()
    t0 = time.monotonic()
    runner.record_stall("no_progress", detail="x")
    assert time.monotonic() - t0 < 2.0
    st = _stall()
    assert st["consecutive"] == 1 and st["lock"] == "LOCKED"


def test_a_lock_file_with_a_future_mtime_changes_nothing():
    lock = runner.STALL.with_name(f"{runner.STALL.name}.lock")
    lock.write_text("999999\n")
    future = time.time() + 86400
    os.utime(lock, (future, future))
    t0 = time.monotonic()
    runner.record_stall("no_progress", detail="x")
    assert time.monotonic() - t0 < 2.0 and _stall()["lock"] == "LOCKED"


def test_a_lock_that_cannot_be_opened_returns_by_the_deadline_without_spinning(monkeypatch):
    """The v3 must-fix: a failure that skipped the deadline check spun a core forever holding
    the thread lock. Every failure now sleeps and the deadline is always checked."""
    monkeypatch.setattr(runner, "STALL_LOCK_WAIT_S", 0.5)
    real_open = os.open

    def deny(path, *a, **k):
        if str(path).endswith(".lock"):
            raise PermissionError(13, "Access is denied", str(path))
        return real_open(path, *a, **k)

    monkeypatch.setattr(runner.os, "open", deny)
    cpu0, t0 = time.process_time(), time.monotonic()
    runner.record_stall("no_progress", detail="x")
    wall, cpu = time.monotonic() - t0, time.process_time() - cpu0
    assert 0.5 <= wall < 3.0, wall
    assert cpu < 0.5 * wall, f"spun: {cpu:.2f} cpu-s in {wall:.2f}s"
    st = _stall()
    assert st["lock"].startswith("UNLOCKED") and "PermissionError" in st["lock"]
    assert st["unlocked_writes"] == 1 and st["consecutive"] == 1


@pytest.mark.skipif(sys.platform == "win32", reason="the probe holds the lock with fcntl")
def test_a_lock_held_past_the_deadline_writes_unlocked_and_says_so(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "STALL_LOCK_WAIT_S", 0.5)
    holder = _hold_lock(tmp_path)
    try:
        t0 = time.monotonic()
        runner.record_slow("run_deadline", detail="x")
        assert time.monotonic() - t0 < 3.0
        st = _stall()
        assert st["lock"].startswith("UNLOCKED") and "held by another writer" in st["lock"]
        assert st["unlocked_writes"] == 1
    finally:
        holder.kill()
        holder.wait()
    runner.record_slow("run_deadline", detail="y")
    st = _stall()
    assert st["lock"] == "LOCKED" and st["unlocked_writes"] == 1, "the count is kept"


def test_one_denied_process_makes_the_whole_tree_unmeasured(monkeypatch):
    """The probe: a readable idle parent over a denied busy grandchild read as measured idle."""
    parent = _spawn(
        "import subprocess, sys, time\n"
        "subprocess.Popen([sys.executable, '-c', 'while True: pass'])\n"
        "time.sleep(60)"
    )
    try:
        time.sleep(0.5)
        kids = {c.pid for c in psutil.Process(parent.pid).children(recursive=True)}
        assert kids
        real = psutil.Process.cpu_times

        def some_denied(self, *a, **k):
            if self.pid in kids:
                raise psutil.AccessDenied(self.pid)
            return real(self, *a, **k)

        monkeypatch.setattr(psutil.Process, "cpu_times", some_denied)
        assert runner._sample_tree(parent.pid) is None
        monkeypatch.setattr(psutil.Process, "cpu_times", real)
        real_io = psutil.Process.io_counters

        def io_denied(self, *a, **k):
            if self.pid in kids:
                raise psutil.AccessDenied(self.pid)
            return real_io(self, *a, **k)

        monkeypatch.setattr(psutil.Process, "io_counters", io_denied)
        assert runner._sample_tree(parent.pid) is None
    finally:
        for c in psutil.Process(parent.pid).children(recursive=True):
            with __import__("contextlib").suppress(psutil.Error):
                c.kill()
        parent.kill()
        parent.wait()


def test_a_forced_utime_cannot_fool_the_parse_cache():
    a = runner.MERGE_OUTPUTS[0]
    a.write_text(json.dumps({"v": 1}))
    st = a.stat()
    assert runner._parses(a) is True
    a.write_text('{"v": 2 ')  # same size, torn
    os.utime(a, ns=(st.st_atime_ns, st.st_mtime_ns))  # mtime forced back
    assert a.stat().st_size == st.st_size and a.stat().st_mtime_ns == st.st_mtime_ns
    assert runner._parses(a) is False


def test_cpu_that_cannot_be_read_is_unmeasured_and_never_kills(monkeypatch, tmp_path):
    """The probe: AccessDenied on every cpu_times() read a busy child as measured idle."""

    def denied(self, *a, **k):
        raise psutil.AccessDenied(self.pid)

    monkeypatch.setattr(psutil.Process, "cpu_times", denied)
    busy = _spawn("while True: pass")
    try:
        assert runner._sample_tree(busy.pid) is None
    finally:
        busy.kill()
        busy.wait()
    # ...and the shard runner, sampling such a child, lets it finish
    t0 = time.monotonic()
    done = runner._watched_run([sys.executable, "-c", _BUSY], idle_s=0.5, poll_s=0.1)
    assert done.returncode == 0 and time.monotonic() - t0 >= 2.0


def test_a_wall_clock_jump_never_reads_a_busy_tree_as_idle(monkeypatch):
    monkeypatch.setattr(runner, "_kill_descendants", lambda pid: pytest.fail("killed a sweep"))
    wall, mono = [0.0], [0.0]
    tree = _FakeTree()
    exits: list[int] = []
    dog = runner.SweepWatchdog(
        beat_s=30,
        clock=lambda: wall[0],
        mono=lambda: mono[0],
        sampler=tree,
        lane=lambda: True,
        exit_fn=exits.append,
    )
    for _ in range(5):
        wall[0] += 60
        mono[0] += 60
        tree.cpu += 60
        dog.tick()
    wall[0] += 1900  # NTP / VM resume: wall time leaps, 60 s really passed
    mono[0] += 60
    tree.cpu += 60
    dog.tick()
    # and a real gap (a frozen sampler) longer than 3 beats is a fresh baseline, not idleness
    mono[0] += 1900
    wall[0] += 1900
    tree.cpu += 1.0
    dog.tick()
    assert exits == [] and dog.progress.gaps == 1


def test_io_advancing_is_progress_and_a_heartbeat_trickle_is_not():
    tr = runner._TreeProgress(0.0)
    assert tr.update({"cpu": {1: 0.0}, "io": {1: 0.0}}, 1.0) is False
    assert tr.update({"cpu": {1: 0.0}, "io": {1: 8e6}}, 61.0) is True  # ~133 KB/s
    assert tr.update({"cpu": {1: 0.0}, "io": {1: 8e6 + 4096}}, 121.0) is False
    assert tr.update({"cpu": {1: 0.0}}, 181.0) is False  # no io: CPU only


def test_a_restore_removes_partial_copies_and_never_full_parses_a_big_file(monkeypatch):
    a, b = runner.MERGE_OUTPUTS
    a.write_text(json.dumps({"v": list(range(50))}, indent=2))
    b.write_text(json.dumps({"s": 1}, indent=2))
    runner.snapshot_merge_outputs()
    (runner.MERGE_SNAPSHOT / "universal_gates_external.json.4242.tmp").write_text("partial")
    (a.parent / f"{a.name}.restore.4242.tmp").write_text("partial")
    monkeypatch.setattr(runner, "PARSE_FULL_MAX_BYTES", 16)

    def no_full_load(*args, **kw):
        raise AssertionError("a large file was fully parsed")

    monkeypatch.setattr(runner.json, "load", no_full_load)
    a.write_text(a.read_text()[:-40])  # torn mid-write
    assert runner._parses(a) is False
    assert runner.restore_merge_outputs() == [a.name]
    assert runner._parses(a) is True and runner._parses(b) is True
    assert not list(runner.MERGE_SNAPSHOT.glob("*.tmp"))
    assert not list(a.parent.glob("*.restore.*.tmp"))


def test_a_fail_pages_through_the_issue_board_and_a_pass_clears_it(tmp_path):
    fence = _fence()
    alarm = tmp_path / "JUDGE_ALIVE_ALARM.txt"
    fence.sync_alarm({"verdict": "FAIL", "why": "no_progress"}, alarm)
    assert "no_progress" in alarm.read_text()
    fence.sync_alarm({"verdict": "UNMEASURED"}, alarm)
    assert alarm.exists(), "absence of evidence never clears a page"
    fence.sync_alarm({"verdict": "PASS"}, alarm)
    assert not alarm.exists()
    import research.issue_board as board

    assert any(a[0] == "JUDGE_ALIVE_ALARM.txt" for a in board.ALARMS)
    assert any(c[1].endswith("judge_alive_fence.json") for c in board.CADENCE)
    assert fence.LIVENESS_ALARM.parent.name == "data"
