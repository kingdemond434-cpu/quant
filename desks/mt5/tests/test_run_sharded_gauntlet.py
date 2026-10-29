from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import run_sharded_gauntlet as runner


def test_shard_count_falls_closed_and_honours_measurement(monkeypatch) -> None:
    monkeypatch.delenv("GAUNTLET_SHARDS", raising=False)
    assert runner._shards() == 1
    monkeypatch.setenv("GAUNTLET_SHARDS", "7")
    assert runner._shards() == 7
    monkeypatch.setenv("GAUNTLET_SHARDS", "broken")
    assert runner._shards() == 1


def test_retry_count_falls_closed_and_honours_measurement(monkeypatch) -> None:
    monkeypatch.delenv("GAUNTLET_SHARD_RETRIES", raising=False)
    assert runner._retry_attempts() == 2
    monkeypatch.setenv("GAUNTLET_SHARD_RETRIES", "4")
    assert runner._retry_attempts() == 4
    monkeypatch.setenv("GAUNTLET_SHARD_RETRIES", "broken")
    assert runner._retry_attempts() == 2


@pytest.fixture(autouse=True)
def _isolated_state(monkeypatch, tmp_path):
    """No test reads or writes the desk's real peak or resident files."""
    monkeypatch.setattr(runner, "SHARD_PEAKS", tmp_path / "judge_shard_peaks.json")
    monkeypatch.setattr(runner, "RESIDENT_STATE", tmp_path / "JUDGE_RESIDENT.json")
    monkeypatch.setattr(runner, "RESIDENT_MEMORY", tmp_path / "JUDGE_RESIDENT_MEMORY.json")
    monkeypatch.setattr(runner, "RESIDENT_STOP", tmp_path / "RESIDENT_STOP")
    monkeypatch.setattr(runner, "SWEEP_PHASE", tmp_path / "JUDGE_SWEEP_PHASE.json")
    monkeypatch.setattr(runner, "_PHASE_DOC", {})
    monkeypatch.setattr(runner, "HEARTBEAT", tmp_path / "GAUNTLET_HEARTBEAT.json")
    monkeypatch.setattr(runner, "STALL", tmp_path / "GAUNTLET_STALL.json")
    monkeypatch.setattr(runner, "PHASE_TIMES", tmp_path / "judge_phase_times.json")
    monkeypatch.setattr(runner, "_PROGRESS", {})
    monkeypatch.setattr(runner, "MERGE_SNAPSHOT", tmp_path / "snap")
    monkeypatch.setattr(runner, "MERGE_OUTPUTS", (tmp_path / "ug.json", tmp_path / "us.json"))
    runner._ABORT.clear()


def test_parallelism_is_bounded_and_configurable(monkeypatch) -> None:
    monkeypatch.delenv("GAUNTLET_SHARD_CONCURRENCY", raising=False)
    assert runner._parallelism(15) == 2
    assert runner._parallelism(1) == 1
    monkeypatch.setenv("GAUNTLET_SHARD_CONCURRENCY", "4")
    assert runner._parallelism(15) == 4
    monkeypatch.setenv("GAUNTLET_SHARD_CONCURRENCY", "99")
    assert runner._parallelism(15) == 15
    monkeypatch.setenv("GAUNTLET_SHARD_CONCURRENCY", "broken")
    assert runner._parallelism(15) == 1


def test_initial_wave_limits_live_children_without_losing_partitions(monkeypatch, tmp_path):
    import threading
    import time

    active = peak = 0
    completed = []
    lock = threading.Lock()

    def child(argv, **kwargs):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(0.03)
        with lock:
            completed.append(int(argv[-2]))
            active -= 1

    monkeypatch.delenv("GAUNTLET_SHARD_CONCURRENCY", raising=False)
    monkeypatch.setattr(runner, "run", child)
    runner.dispatch(tmp_path, 7, "build")
    assert peak == 2
    assert sorted(completed) == list(range(7))


def test_dispatch_runs_every_shard_once(monkeypatch, tmp_path) -> None:
    calls = []

    def fake_run(argv, **kwargs):
        calls.append((argv, kwargs))

    monkeypatch.setattr(runner, "run", fake_run)
    runner.dispatch(tmp_path, 4, "build")
    assert sorted(int(argv[-2]) for argv, _ in calls) == [0, 1, 2, 3]
    assert all(argv[0] == sys.executable and argv[-1] == "build" for argv, _ in calls)
    assert all(kwargs["check"] is True and kwargs["capture_output"] is False
               for _, kwargs in calls)


def test_dispatch_retries_only_failed_shards_after_parallel_wave(monkeypatch, tmp_path) -> None:
    calls: list[int] = []
    failures_left = {1: 1, 3: 2}

    def fake_run(argv, **kwargs):
        shard = int(argv[-2])
        calls.append(shard)
        if failures_left.get(shard, 0):
            failures_left[shard] -= 1
            raise RuntimeError(f"transient shard {shard}")

    monkeypatch.setattr(runner, "run", fake_run)
    runner.dispatch(tmp_path, 4, "build")

    assert calls.count(0) == 1
    assert calls.count(1) == 2
    assert calls.count(2) == 1
    assert calls.count(3) == 3


def test_dispatch_propagates_a_failed_shard(monkeypatch, tmp_path) -> None:
    def fake_run(argv, **kwargs):
        if argv[-2] == "2":
            raise RuntimeError("shard failed")

    monkeypatch.setattr(runner, "run", fake_run)
    with pytest.raises(RuntimeError, match="shard 2 failed after 3 attempt"):
        runner.dispatch(tmp_path, 4, "rule")


def test_actual_child_stderr_survives_retries_and_shard_cleanup(monkeypatch, tmp_path):
    child_run = runner._watched_run           # the real shard runner, on a stand-in child

    shard_dir = tmp_path / "shards"
    shard_dir.mkdir()
    attempts = []

    def child(argv, **kwargs):
        attempts.append(int(argv[-2]))
        return child_run([sys.executable, "-c",
                          "import sys; print('real child error', file=sys.stderr); sys.exit(7)"],
                         **kwargs)

    monkeypatch.setenv("GAUNTLET_SHARD_RETRIES", "1")
    monkeypatch.setattr(runner, "run", child)
    with pytest.raises(RuntimeError, match="refusing partial merge") as failed:
        runner.dispatch(shard_dir, 1, "build")
    shard_dir.rmdir()
    receipts = list((tmp_path / "shards-logs").glob("*.log"))
    assert len(receipts) == 2
    assert attempts == [0, 0]
    assert all("real child error" in p.read_text() for p in receipts)
    assert all("CHILD_FAILED type=CalledProcessError returncode=7" in p.read_text()
               for p in receipts)
    assert "child log=" in str(failed.value.__cause__)


def test_silent_native_failure_has_exit_evidence(monkeypatch, tmp_path):
    import subprocess

    def silent_failure(argv, **kwargs):
        raise subprocess.CalledProcessError(3221225477, argv)

    monkeypatch.setenv("GAUNTLET_SHARD_RETRIES", "0")
    monkeypatch.setattr(runner, "run", silent_failure)
    with pytest.raises(RuntimeError, match="refusing partial merge"):
        runner.dispatch(tmp_path / "shards", 1, "build")
    receipts = list((tmp_path / "shards-logs").glob("*.log"))
    assert len(receipts) == 1
    assert "CHILD_FAILED type=CalledProcessError returncode=3221225477" in receipts[0].read_text()
    assert "CHILD_EXIT_OK" not in receipts[0].read_text()


# --------------------------------------------------------------- measured shard concurrency
def test_unset_cap_is_sized_from_the_recorded_peak(monkeypatch, tmp_path) -> None:
    import json
    monkeypatch.delenv("GAUNTLET_SHARD_CONCURRENCY", raising=False)
    monkeypatch.setattr(runner, "_available_mb", lambda: 40_000.0)
    assert runner._parallelism(15, "rule") == 2            # never measured: the historic 2
    runner.SHARD_PEAKS.write_text(json.dumps({"rule": [1500.0, 4000.0], "build": [9000.0]}))
    assert runner._parallelism(15, "rule") == 5            # 40,000 x 0.5 // 4,000 (largest)
    assert runner._parallelism(15, "build") == 2           # 20,000 // 9,000
    assert runner._parallelism(3, "rule") == 3             # never wider than the shard count
    monkeypatch.setattr(runner, "_available_mb", lambda: 1_000.0)
    assert runner._parallelism(15, "rule") == 1            # never below one
    monkeypatch.setenv("GAUNTLET_SHARD_CONCURRENCY", "3")
    assert runner._parallelism(15, "rule") == 3            # an operator cap always wins


def test_child_peaks_are_folded_with_bounded_history(tmp_path) -> None:
    import json
    logs = tmp_path / "logs"
    logs.mkdir()
    for k, mb in enumerate((1000.0, 2500.0)):
        (logs / f"inv-rule-{k}-attempt-0.peak.json").write_text(json.dumps({"peak_mb": mb}))
    (logs / "inv-rule-9-attempt-0.peak.json").write_text("{broken")
    runner._record_peaks(logs, "inv", "rule")
    assert runner._shard_peak_mb("rule") == 2500.0
    for i in range(runner.SHARD_PEAK_HISTORY + 5):
        (logs / f"inv2-rule-{i}-attempt-0.peak.json").write_text(json.dumps({"peak_mb": 100.0}))
    runner._record_peaks(logs, "inv2", "rule")
    rows = json.loads(runner.SHARD_PEAKS.read_text())["rule"]
    assert len(rows) == runner.SHARD_PEAK_HISTORY and max(rows) == 100.0


def test_record_own_peak_writes_a_receipt(tmp_path) -> None:
    import json
    out = tmp_path / "p.json"
    runner.record_own_peak(str(out))
    assert json.loads(out.read_text())["peak_mb"] > 0


# -------------------------------------------------------------------------- resident judge
class _Clock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


def test_resident_starts_the_next_sweep_with_no_gap(tmp_path) -> None:
    clock, slept, rcs = _Clock(), [], []

    def sweep() -> int:
        clock.t += 900.0
        rcs.append(0)
        return 0

    rc = runner.resident(sweep=sweep, sleep=slept.append, clock=clock, limit_s=0.0,
                         max_sweeps=4)
    assert rc == 0 and len(rcs) == 4 and slept == []      # zero cadence: never sleeps
    import json
    st = json.loads(runner.RESIDENT_STATE.read_text())
    assert st["sweeps"] == 4 and st["status"] == "DONE" and st["busy_seconds"] == 3600.0


def test_resident_retries_failures_with_growing_backoff(tmp_path) -> None:
    clock, slept = _Clock(), []
    seq = iter([1, 1, 75, 0])
    runner.resident(sweep=lambda: next(seq), sleep=slept.append, clock=clock, limit_s=None,
                    max_sweeps=4)
    assert slept == [runner.RESIDENT_BACKOFF_S[0], runner.RESIDENT_BACKOFF_S[1],
                     runner.RESIDENT_BACKOFF_S[0]]


def test_a_crashing_sweep_is_a_failure_not_an_exit(tmp_path) -> None:
    clock, slept, calls = _Clock(), [], []

    def sweep() -> int:
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("boom")
        return 0

    runner.resident(sweep=sweep, sleep=slept.append, clock=clock, limit_s=None, max_sweeps=2)
    assert len(calls) == 2 and slept == [runner.RESIDENT_BACKOFF_S[0]]


def test_resident_never_starts_a_sweep_the_time_limit_would_kill(tmp_path) -> None:
    clock = _Clock()

    def sweep() -> int:
        clock.t += 3000.0
        return 0

    runner.resident(sweep=sweep, sleep=lambda s: None, clock=clock, limit_s=4 * 3600.0)
    import json
    st = json.loads(runner.RESIDENT_STATE.read_text())
    # 3,000 s sweeps + 300 s margin in 14,400 s: four fit, the fifth would be killed.
    assert st["sweeps"] == 4 and st["status"] == "RESPAWN"


def test_the_stop_file_stops_it(tmp_path) -> None:
    runner.RESIDENT_STOP.write_text("")
    calls: list = []
    runner.resident(sweep=lambda: calls.append(1) or 0, sleep=lambda s: None,
                    clock=_Clock(), limit_s=None)
    assert calls == []


def test_resident_is_the_default_and_once_opts_out(monkeypatch) -> None:
    monkeypatch.delenv("GAUNTLET_RESIDENT", raising=False)
    assert runner._resident_enabled([]) is True
    assert runner._resident_enabled(["--once"]) is False
    monkeypatch.setenv("GAUNTLET_RESIDENT", "0")
    assert runner._resident_enabled([]) is False
    assert runner._resident_enabled(["--resident"]) is True


def test_each_sweep_takes_the_latest_measured_env(monkeypatch) -> None:
    published = {"GAUNTLET_WORKERS": "10", "GAUNTLET_SHARDS": "10"}
    monkeypatch.setattr(runner, "_published_env", lambda: dict(published))
    monkeypatch.setattr(runner, "_LAUNCH", {})
    monkeypatch.setenv("GAUNTLET_WORKERS", "10")      # exported by the launcher from the file
    monkeypatch.setenv("GAUNTLET_SHARDS", "4")        # exported by hand: outranks the organ
    assert runner._sweep_env()["GAUNTLET_WORKERS"] == "10"
    published.update(GAUNTLET_WORKERS="15", GAUNTLET_SHARDS="15", GAUNTLET_PER_WORKER_MB="768")
    env = runner._sweep_env()
    assert env["GAUNTLET_WORKERS"] == "15"
    assert env["GAUNTLET_SHARDS"] == "4"
    assert env["GAUNTLET_PER_WORKER_MB"] == "768"


def test_the_heartbeat_moves_while_a_sweep_runs(tmp_path) -> None:
    import json
    import time as _t

    seen: list[str] = []

    def slow_sweep() -> int:
        _t.sleep(0.35)
        seen.append(json.loads(runner.RESIDENT_STATE.read_text("utf-8"))["heartbeat_utc"])
        return 0

    runner.resident(sweep=slow_sweep, sleep=lambda s: None, max_sweeps=1, heartbeat_s=0.1)
    doc = json.loads(runner.RESIDENT_STATE.read_text("utf-8"))
    assert seen and doc["heartbeat_utc"] >= seen[0]
    assert doc["status"] == "DONE"


def test_an_unexpected_end_is_recorded_as_exited(tmp_path) -> None:
    import json

    def interrupted() -> int:
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        runner.resident(sweep=interrupted, sleep=lambda s: None, heartbeat_s=60)
    doc = json.loads(runner.RESIDENT_STATE.read_text("utf-8"))
    assert doc["status"] == "EXITED" and doc["heartbeat_utc"]


def test_a_hung_sweep_has_a_ceiling_from_its_own_budget(monkeypatch) -> None:
    """A sweep that never ends kept the task's one instance alive and every trigger was refused
    (2026-10-12/13): the child's ceiling is twice ITS build budget, or 3x the longest sweep."""
    assert runner._hang_limit_s(None, env={"GAUNTLET_FRESH_BUDGET_SEC": "8640"}) == 17280.0
    assert runner._hang_limit_s(9000.0, env={"GAUNTLET_FRESH_BUDGET_SEC": "8640"}) == 27000.0
    assert runner._hang_limit_s(None, env={"GAUNTLET_FRESH_BUDGET_SEC": "60"}) \
        == runner.RESIDENT_HANG_FLOOR_S
    # the sealed default when the child's env names no budget
    assert runner._hang_limit_s(None, env={}) == 2 * runner.SEALED_FRESH_BUDGET_S


def test_consecutive_hangs_widen_the_ceiling_to_a_cap() -> None:
    """Audit of #350: a slow (not stuck) sweep must eventually be allowed to finish."""
    env = {"GAUNTLET_FRESH_BUDGET_SEC": "8640"}
    assert runner._hang_limit_s(None, 1, env) == 34560.0
    assert runner._hang_limit_s(None, 2, env) == 69120.0
    assert runner._hang_limit_s(None, 30, env) == runner.RESIDENT_HANG_CAP_S


def test_a_hung_sweep_is_killed_recorded_and_the_next_one_starts(monkeypatch, tmp_path) -> None:
    import json
    import subprocess

    seen: dict = {}

    class _Child:
        pid = 4242

        def wait(self, timeout=None):
            seen.setdefault("timeouts", []).append(timeout)
            raise subprocess.TimeoutExpired("sweep", timeout or 0)

    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: _Child())
    monkeypatch.setattr(runner, "_kill_sweep_tree", lambda pid: seen.setdefault("killed", pid))
    monkeypatch.setattr(runner, "_sweep_env", lambda: {})
    # A HUNG SWEEP IS AN IDLE ONE (audit of 2832cebd1): the resident kills on its own measurement
    # of the child's tree burning nothing, never on a wall-clock ceiling.
    ticks = iter(float(60 * i) for i in range(10_000))
    assert runner._one_sweep_child(5.0, poll_s=60.0, clock=lambda: next(ticks),
                                   sampler=lambda pid: {"cpu": {pid: 1.0}, "rss_mb": 1.0,
                                                        "procs": 1}) == runner.RESIDENT_HANG_RC
    assert seen["timeouts"][0] == 60.0 and seen["killed"] == 4242
    stall = json.loads(runner.STALL.read_text("utf-8"))
    assert stall["status"] == "STALLED" and stall["reason"] == "resident_kill"

    clock, slept = _Clock(), []
    seq = iter([runner.RESIDENT_HANG_RC, runner.RESIDENT_HANG_RC])
    runner.resident(sweep=lambda: next(seq), sleep=slept.append, clock=clock, limit_s=None,
                    max_sweeps=2)
    doc = json.loads(runner.RESIDENT_STATE.read_text("utf-8"))
    assert doc["hung_kills"] == 2 and doc["consecutive_hangs"] == 2 and doc["last_hung_utc"]
    # A RESTARTED RESIDENT REMEMBERS THE RUN, and a success ends it.
    runner.resident(sweep=lambda: 0, sleep=slept.append, clock=clock, limit_s=None,
                    max_sweeps=0)
    assert json.loads(runner.RESIDENT_STATE.read_text("utf-8"))["consecutive_hangs"] == 2
    runner.resident(sweep=lambda: 0, sleep=slept.append, clock=clock, limit_s=None,
                    max_sweeps=1)
    doc = json.loads(runner.RESIDENT_STATE.read_text("utf-8"))
    assert doc["consecutive_hangs"] == 0 and doc["hung_kills"] == 2


_RESPAWNER = """
import subprocess, sys, time
pids = open(sys.argv[1], "a")
while True:
    p = subprocess.Popen([sys.executable, "-c",
                          "import subprocess,sys,time;"
                          "subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)']);"
                          "time.sleep(60)"])
    pids.write(f"{p.pid}\\n"); pids.flush()
    time.sleep(0.05)
"""


def test_the_tree_kill_leaves_no_orphan_while_the_root_respawns(tmp_path) -> None:
    """Audit of #350: a root that keeps spawning shards (and grandchildren) during the kill."""
    import subprocess
    import sys as _sys
    import time as _t

    psutil = pytest.importorskip("psutil")
    log = tmp_path / "pids.txt"
    root = subprocess.Popen([_sys.executable, "-c", _RESPAWNER, str(log)])
    try:
        _t.sleep(1.5)
        before = {c.pid for c in psutil.Process(root.pid).children(recursive=True)}
        assert len(before) >= 4
        rep = runner._kill_sweep_tree(root.pid)
        root.wait(timeout=15)
        assert rep["orphans"] == [], rep             # the kill names what it could not reach
        _t.sleep(0.5)
        spawned = {int(x) for x in log.read_text().split()} | before
        alive = [p for p in spawned if psutil.pid_exists(p)
                 and psutil.Process(p).status() != psutil.STATUS_ZOMBIE]
        orphans = [p for p in alive
                   if "time.sleep(60)" in " ".join(psutil.Process(p).cmdline())]
        assert not orphans, orphans
    finally:
        with __import__("contextlib").suppress(Exception):
            root.kill()


def test_a_sweep_names_its_phase_and_a_kill_records_it(monkeypatch) -> None:
    """The 33h stall could not say which part of the sweep the core was in: each phase is now
    stamped, folded into the resident's heartbeat, and named on a hung kill."""
    import json

    clock = iter([100.0, 160.0, 400.0])
    with monkeypatch.context() as m:
        m.setattr(runner.time, "time", lambda: next(clock))
        runner._phase("plan")
        runner._phase("build_shards")
        runner._phase("merge_and_publish")
    doc = json.loads(runner.SWEEP_PHASE.read_text("utf-8"))
    assert doc["phase"] == "merge_and_publish"
    assert doc["phases"] == {"plan": 60.0, "build_shards": 240.0}

    seq = iter([runner.RESIDENT_HANG_RC, 0])
    runner.resident(sweep=lambda: next(seq), sleep=lambda s: None, clock=_Clock(),
                    limit_s=None, max_sweeps=2, heartbeat_s=60)
    st = json.loads(runner.RESIDENT_STATE.read_text("utf-8"))
    assert st["killed_in_phase"]["phase"] == "merge_and_publish"


# ------------------------------------------------------------------ shard progress (published)
def _shards_doc() -> dict:
    import json

    return json.loads(runner.SWEEP_PHASE.read_text("utf-8"))["shards"]


def test_shard_progress_counts_a_wave_with_one_failure_and_a_retry(monkeypatch, tmp_path):
    """A wave of four with shard 2 failing once: the published block counts every start, the
    failure and the retry, and the retry's success lands in done_ok."""
    failures_left = {2: 1}

    def fake_run(argv, **kwargs):
        shard = int(argv[-2])
        if failures_left.get(shard, 0):
            failures_left[shard] -= 1
            raise RuntimeError("transient")

    monkeypatch.setattr(runner, "run", fake_run)
    runner._phase("build_shards")
    runner.dispatch(tmp_path / "shards", 4, "build")
    sh = _shards_doc()
    assert sh["phase"] == "build" and sh["total"] == 4
    assert (sh["started"], sh["done_ok"], sh["failed"], sh["retries"], sh["running"]) == (
        5, 4, 1, 1, 0)
    assert sh["last_finish_utc"] and sh["longest_shard_s"] is not None
    assert sh["seconds_since_last_finish"] is not None
    assert sh["stalled_hint"] is False  # nothing running: never a hang

    # the resident's heartbeat carries it, and the next phase starts without it
    runner._write_state({"status": "SWEEPING"})
    import json
    st = json.loads(runner.RESIDENT_STATE.read_text("utf-8"))
    assert st["sweep_phase"]["shards"]["done_ok"] == 4
    runner._phase("collect_and_cut")
    assert "shards" not in json.loads(runner.SWEEP_PHASE.read_text("utf-8"))


def _overlapping_retries(monkeypatch, tmp_path) -> int:
    """Shards 1 and 3 fail once; returns the most retry children that ran at the same time."""
    import threading
    import time

    failures_left = {1: 1, 3: 1}
    live = {"now": 0, "max": 0}
    lock = threading.Lock()

    def fake_run(argv, **kwargs):
        shard, attempt_log = int(argv[-2]), str(kwargs.get("stdout").name)
        if failures_left.get(shard, 0):
            failures_left[shard] -= 1
            raise RuntimeError("transient")
        if "attempt-1" in attempt_log:
            with lock:
                live["now"] += 1
                live["max"] = max(live["max"], live["now"])
            time.sleep(0.2)
            with lock:
                live["now"] -= 1

    monkeypatch.setattr(runner, "run", fake_run)
    monkeypatch.setattr(runner, "_parallelism", lambda n, phase=None: n)
    runner._phase("build_shards")
    runner.dispatch(tmp_path / "shards", 4, "build")
    return live["max"]


def test_failed_shards_recover_side_by_side(monkeypatch, tmp_path):
    """Measured 10-29: two failed build shards retried back to back, a full shard wall each.
    They now retry together, as wide as the memory rule allows."""
    assert _overlapping_retries(monkeypatch, tmp_path) == 2
    assert _shards_doc()["done_ok"] == 4


def test_serial_recovery_is_the_revert_path(monkeypatch, tmp_path):
    monkeypatch.setenv("GAUNTLET_SHARD_SERIAL_RETRY", "1")
    assert _overlapping_retries(monkeypatch, tmp_path) == 1


def test_a_shard_that_never_recovers_still_refuses_the_merge(monkeypatch, tmp_path):
    def fake_run(argv, **kwargs):
        if int(argv[-2]) == 2:
            raise RuntimeError("always")

    monkeypatch.setattr(runner, "run", fake_run)
    monkeypatch.setenv("GAUNTLET_SHARD_RETRIES", "1")
    runner._phase("build_shards")
    with pytest.raises(RuntimeError, match="shard 2 failed after 2 attempt"):
        runner.dispatch(tmp_path / "shards", 4, "build")


def test_shard_progress_writes_are_atomic_under_concurrency(monkeypatch, tmp_path):
    """Sixteen concurrent children stamping at once never leave a torn or lost count, and a
    reader polling the file throughout always parses it."""
    import json
    import threading
    import time

    monkeypatch.setenv("GAUNTLET_SHARD_CONCURRENCY", "16")
    stop = threading.Event()
    torn: list[str] = []

    def reader() -> None:
        while not stop.is_set():
            try:
                text = runner.SWEEP_PHASE.read_text("utf-8")
            except OSError:
                continue
            try:
                json.loads(text)
            except ValueError:
                torn.append(text)

    def fake_run(argv, **kwargs):
        time.sleep(0.005)

    monkeypatch.setattr(runner, "run", fake_run)
    runner._phase("rule_shards")
    t = threading.Thread(target=reader)
    t.start()
    try:
        runner.dispatch(tmp_path / "shards", 64, "rule")
    finally:
        stop.set()
        t.join()
    assert not torn
    sh = _shards_doc()
    assert (sh["total"], sh["started"], sh["done_ok"], sh["failed"], sh["running"]) == (
        64, 64, 64, 0, 0)
    assert not list(runner.SWEEP_PHASE.parent.glob("*.tmp"))


def test_stalled_hint_is_false_before_the_first_finish_and_true_past_the_longest(monkeypatch):
    """Nothing finished is UNMEASURED, never a hang; a gap longer than the longest measured shard
    while a child still runs is the hint."""
    now = [1000.0]
    monkeypatch.setattr(runner.time, "time", lambda: now[0])
    runner._phase("build_shards")
    runner._shard_progress("begin", "build", total=3)
    for _ in range(3):
        runner._shard_progress("start", "build")
    now[0] = 100_000.0  # a very long silence with nothing finished
    sh = runner._sweep_phase()["shards"]
    assert sh["seconds_since_last_finish"] is None and sh["stalled_hint"] is False

    runner._shard_progress("ok", "build", elapsed_s=120.0)
    now[0] += 60.0
    sh = runner._sweep_phase()["shards"]
    assert sh["seconds_since_last_finish"] == 60.0 and sh["stalled_hint"] is False
    now[0] += 61.0  # 121 s since the last finish > 120 s longest shard, two still running
    sh = runner._sweep_phase()["shards"]
    assert sh["running"] == 2 and sh["stalled_hint"] is True


def test_a_fast_failure_never_raises_the_stalled_hint(monkeypatch):
    """Audit should-fix 1: one shard OOMs in 3 s early in a wave while fourteen healthy shards
    still run. The crash is not a yardstick for a healthy shard, so longest_shard_s stays
    UNMEASURED and the hint stays false however long the healthy shards take; only a SUCCESSFUL
    shard sets the yardstick, and a failure never lengthens it."""
    now = [1000.0]
    monkeypatch.setattr(runner.time, "time", lambda: now[0])
    runner._phase("build_shards")
    runner._shard_progress("begin", "build", total=15)
    for _ in range(15):
        runner._shard_progress("start", "build")
    now[0] += 3.0
    runner._shard_progress("failed", "build", elapsed_s=3.0)
    now[0] += 10.0  # 10 s since the crash > its 3 s, with 14 healthy shards still running
    sh = runner._sweep_phase()["shards"]
    assert (sh["running"], sh["failed"], sh["done_ok"]) == (14, 1, 0)
    assert sh["longest_shard_s"] is None
    assert sh["stalled_hint"] is False
    now[0] += 7200.0  # still false hours later: nothing has SUCCEEDED, so nothing is measured
    assert runner._sweep_phase()["shards"]["stalled_hint"] is False

    # the first success sets the yardstick; a later longer failure does not stretch it
    runner._shard_progress("ok", "build", elapsed_s=600.0)
    runner._shard_progress("failed", "build", elapsed_s=5000.0)
    sh = runner._sweep_phase()["shards"]
    assert sh["longest_shard_s"] == 600.0 and sh["stalled_hint"] is False
    now[0] += 601.0
    sh = runner._sweep_phase()["shards"]
    assert sh["running"] == 12 and sh["stalled_hint"] is True


def test_a_failed_publish_leaves_no_tmp_file(monkeypatch, tmp_path):
    """Audit should-fix 2: when os.replace raises (NTFS: the destination held open by a reader,
    or read-only), both publishers swallow it as a report and unlink their per-pid/thread tmp
    instead of leaking it."""
    def deny(src, dst):
        raise PermissionError(13, "Access is denied", str(dst))

    monkeypatch.setattr(runner.os, "replace", deny)
    runner._phase("build_shards")                     # SWEEP_PHASE publisher
    runner._shard_progress("begin", "build", total=2)
    runner._write_state({"status": "SWEEPING"})       # RESIDENT_STATE publisher
    assert not runner.SWEEP_PHASE.exists() and not runner.RESIDENT_STATE.exists()
    assert not list(tmp_path.glob("*.tmp"))


def test_the_shard_block_declares_its_hint_report_only():
    """Audit should-fix 4 (III.16): nothing consumes stalled_hint yet, and the published block
    says so in data, not only in prose. The pager v4 contract fields are untouched."""
    import json

    runner._phase("rule_shards")
    runner._shard_progress("begin", "rule", total=1)
    doc = json.loads(runner.SWEEP_PHASE.read_text("utf-8"))
    assert {"pid", "sweep_started_utc", "phase", "phase_started_utc"} <= set(doc)
    assert doc["phase"] == doc["shards"]["phase"] + "_shards"
    assert doc["shards"]["stalled_hint_authority"] == "report_only"


def test_a_wave_with_slow_reports_and_shard_events_shares_one_phase_doc(monkeypatch, tmp_path):
    """The merge of judge plan phase v2.2 with shard progress v2: one sweep's phase document
    carries the plan's phases (opened by PlanTracker through `_phase`), the shard wave's
    start/ok/failed block, and the wave's `slow()` reports, all at once. The SLOW record names
    the shard and the launcher's phase from the same document; the internal `_t0`/`_t` stamps
    stay out of the published file while `_own_elapsed_s` still reads `_t0`; and the next phase
    opens without the shard block."""
    import json
    import threading

    from scripts.judge_plan_progress import PlanTracker

    now = [1000.0]
    monkeypatch.setattr(runner.time, "time", lambda: now[0])
    runner._phase("plan")
    plan = PlanTracker(runner._PHASE_DOC, runner.SWEEP_PHASE, on_phase=runner._phase,
                       clock=lambda: now[0])
    plan.step("lane_and_docket")
    now[0] += 30.0
    plan.line("PRE-WARM START: 12 cells")              # opens the sweep phase "prewarm"
    now[0] += 50.0
    plan.line("PRE-WARM: 12 warmed")                    # opens "plan_handoff"
    now[0] += 20.0
    runner._phase("build_shards")

    class _Tracker:
        def idle_s(self, _now: float) -> float:
            return 4.0

    failures_left = {2: 1}
    lock = threading.Lock()

    def fake_run(argv, **kwargs):
        shard = int(argv[-2])
        if shard in (0, 3):  # past the SLOW threshold, still progressing: amber, left running
            kwargs["on_slow"](kwargs["slow_s"] + 5.0, _Tracker())
        with lock:
            if failures_left.get(shard, 0):
                failures_left[shard] -= 1
                raise RuntimeError("transient")

    monkeypatch.setattr(runner, "run", fake_run)
    runner.dispatch(tmp_path / "shards", 4, "build")

    # the slow() reports: counted for the watchdog and recorded amber, named by shard and phase
    assert runner._progress_snapshot()["slow"] == 2
    stall = json.loads(runner.STALL.read_text("utf-8"))
    assert stall["status"] == "SLOW"
    slow_rows = [r for r in stall["history"] if r["kind"] == "SLOW"]
    assert sorted(r["shard"]["k"] for r in slow_rows) == [0, 3]
    assert all(r["reason"] == "shard_slow" and r["phase"] == "build_shards"
               and r["shard"]["phase"] == "build"
               and r["shard"]["receipt"].endswith("-attempt-0.log") for r in slow_rows)

    # the start/ok/failed events, in the same published document as the plan's phases
    doc = json.loads(runner.SWEEP_PHASE.read_text("utf-8"))
    sh = doc["shards"]
    assert (sh["phase"], sh["total"], sh["started"], sh["done_ok"], sh["failed"],
            sh["retries"], sh["running"]) == ("build", 4, 5, 4, 1, 1, 0)
    assert sh["stalled_hint"] is False and sh["stalled_hint_authority"] == "report_only"
    assert doc["phase"] == "build_shards" == sh["phase"] + "_shards"
    assert doc["phases"] == {"plan": 30.0, "prewarm": 50.0, "plan_handoff": 20.0}
    assert doc["plan_step"] == "plan_handoff"
    assert {"pid", "sweep_started_utc", "phase", "phase_started_utc"} <= set(doc)
    assert not [k for k in doc if k.startswith("_")]   # `_t0` and `_t` are never published
    assert runner._PHASE_DOC["_t0"] == 1000.0
    assert runner._own_elapsed_s() == 100.0

    # the next phase opens without the shard block, keeping the plan's measured phases
    now[0] += 7.0
    runner._phase("collect_and_cut")
    doc = json.loads(runner.SWEEP_PHASE.read_text("utf-8"))
    assert "shards" not in doc and doc["phases"]["build_shards"] == 7.0
    assert doc["phases"]["prewarm"] == 50.0
    assert not [k for k in doc if k.startswith("_")]


def test_phase_and_shard_progress_never_lose_a_count_under_the_phase_lock(
        tmp_path, monkeypatch) -> None:
    """Audit of a971d83da, should-fix 1: `_phase` (the launcher's thread) and `_shard_progress`
    (dispatch's child threads) read-modify-write `_PHASE_DOC` and its file under `_PHASE_LOCK`.

    Every "start" event is counted exactly once: in the shard block a `_phase` closed (and
    popped), or in the block left at the end. The critical section is widened with a sleep
    inside it so that, without the lock, a thread that read the block before a `_phase` popped
    it writes it back (a resurrected count) or two threads increment one stale copy (a lost
    count); `_flush_phase_doc` also iterates a dict another thread is changing. Replacing
    `_PHASE_LOCK` with a no-op context fails this test."""
    import threading
    import time as _time

    popped: list[dict] = []

    class _Doc(dict):
        def pop(self, key, *default):  # type: ignore[override]
            val = super().pop(key, *default)
            if key == "shards" and isinstance(val, dict):
                popped.append(val)
            return val

    monkeypatch.setattr(runner, "SWEEP_PHASE", tmp_path / "JUDGE_SWEEP_PHASE.json")
    monkeypatch.setattr(runner, "_PHASE_DOC", _Doc())
    live = runner._shard_live

    def slow_live(shards, now):
        _time.sleep(0.0005)                      # inside the critical section
        return live(shards, now)

    monkeypatch.setattr(runner, "_shard_live", slow_live)
    runner._phase("build_shards")
    threads, per_thread, errors = 6, 60, []
    go = threading.Event()

    def child() -> None:
        go.wait()
        for _ in range(per_thread):
            runner._shard_progress("start", "build")

    def launcher() -> None:
        go.wait()
        try:
            for i in range(120):
                runner._phase("build_shards" if i % 2 else "rule_shards")
                _time.sleep(0.0005)
        except Exception as exc:                 # e.g. dict changed size during iteration
            errors.append(exc)

    workers = [threading.Thread(target=child) for _ in range(threads)]
    workers.append(threading.Thread(target=launcher))
    for w in workers:
        w.start()
    go.set()
    for w in workers:
        w.join(timeout=120)
    assert not [w for w in workers if w.is_alive()], "no deadlock"
    assert not errors, errors
    final = runner._PHASE_DOC.get("shards") or {}
    counted = sum(int(b.get("started") or 0) for b in popped) + int(final.get("started") or 0)
    assert counted == threads * per_thread, (
        f"{counted} starts counted for {threads * per_thread} events")


def test_a_zeroed_resident_record_does_not_reset_the_hang_ceiling() -> None:
    """2026-10-22: an unclean restart left JUDGE_RESIDENT.json as NUL bytes; the next resident
    forgot an 18 h longest sweep and set a 4.8 h ceiling on a sweep that needs ~18 h."""
    import json

    clock, slept = _Clock(), []
    seq = iter([0])

    def sweep() -> int:
        clock.t += 64711.4                          # one measured 18 h sweep
        return next(seq)

    runner.resident(sweep=sweep, sleep=slept.append, clock=clock, limit_s=None, max_sweeps=1)
    assert json.loads(runner.RESIDENT_MEMORY.read_text("utf-8"))["longest_sweep_s"] == 64711.4
    runner.RESIDENT_STATE.write_bytes(b"\0" * 839)  # what the crash left behind
    seen: dict = {}

    def probe() -> int:
        seen["longest"] = state_longest = json.loads(
            runner.RESIDENT_STATE.read_text("utf-8"))["longest_sweep_s"]
        assert state_longest == 64711.4
        return 0

    runner.resident(sweep=probe, sleep=slept.append, clock=clock, limit_s=None, max_sweeps=1)
    assert seen["longest"] == 64711.4
    env = {"GAUNTLET_FRESH_BUDGET_SEC": "8640"}
    assert runner._hang_limit_s(seen["longest"], 0, env) == runner.RESIDENT_HANG_CAP_S


def test_the_larger_remembered_longest_sweep_wins_and_hangs_survive() -> None:
    import json

    runner.RESIDENT_STATE.write_text(json.dumps({"longest_sweep_s": 600.0}), "utf-8")
    runner.RESIDENT_MEMORY.write_text(json.dumps({"longest_sweep_s": 64711.4,
                                                  "consecutive_hangs": 1, "hung_kills": 3}),
                                      "utf-8")
    got = runner._recall()
    assert got == {"longest_sweep_s": 64711.4, "consecutive_hangs": 1, "hung_kills": 3}


#: Each is a JSON token as it would sit in a damaged file; the tests write it verbatim.
_BAD_TOKENS = ['"12"', "NaN", "Infinity", "-Infinity", "[3]", '{"n": 1}', "-5", "true", "null",
               "1" + "0" * 400]


@pytest.mark.parametrize("token", _BAD_TOKENS)
def test_a_bad_remembered_value_never_crashes_the_resident(token) -> None:
    """Audit of e80a73a87: a string, NaN or list in either file must not stop resident()."""
    import json

    raw = "{" + ", ".join(f'"{k}": {token}' for k in
                          ("longest_sweep_s", "consecutive_hangs", "hung_kills")) + "}"
    runner.RESIDENT_STATE.write_text(raw, "utf-8")
    runner.RESIDENT_MEMORY.write_text(raw, "utf-8")
    got = runner._recall()
    for k in ("consecutive_hangs", "hung_kills"):
        assert got[k] is None or (isinstance(got[k], int) and got[k] >= 0)
    assert got["consecutive_hangs"] is None or got["consecutive_hangs"] <= 64
    assert got["longest_sweep_s"] is None or got["longest_sweep_s"] > 0
    clock, slept = _Clock(), []
    runner.resident(sweep=lambda: 0, sleep=slept.append, clock=clock, limit_s=None,
                    max_sweeps=1)
    doc = json.loads(runner.RESIDENT_STATE.read_text("utf-8"))
    hangs = doc["consecutive_hangs"]
    assert isinstance(hangs, int) and 0 <= hangs <= 64
    env = {"GAUNTLET_FRESH_BUDGET_SEC": "8640"}
    assert runner._hang_limit_s(doc.get("longest_sweep_s"), hangs, env) > 0


def test_a_bad_record_value_falls_back_to_the_mirror() -> None:
    import json

    runner.RESIDENT_STATE.write_text(json.dumps({"longest_sweep_s": "x", "consecutive_hangs":
                                                 "y", "hung_kills": [1]}), "utf-8")
    runner.RESIDENT_MEMORY.write_text(json.dumps({"longest_sweep_s": 64711.4,
                                                  "consecutive_hangs": 10**6,
                                                  "hung_kills": 3.0}), "utf-8")
    assert runner._recall() == {"longest_sweep_s": 64711.4, "consecutive_hangs": 64,
                                "hung_kills": 3}
    assert runner._hang_limit_s(None, 10**6, {}) == runner.RESIDENT_HANG_CAP_S


def test_a_failed_replace_leaves_no_tmp_behind(monkeypatch, tmp_path) -> None:
    import os

    def _refuse(src, dst):
        raise PermissionError(13, "denied")

    monkeypatch.setattr(os, "replace", _refuse)
    target = tmp_path / "out.json"
    with pytest.raises(OSError):
        runner._durable_write(target, "{}")
    assert not target.exists() and not list(tmp_path.glob("out.json.*.tmp"))
