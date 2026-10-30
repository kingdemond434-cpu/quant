"""The hourly job_lock_health leg: every held lock's owner is looked at, a WEDGED research owner
is stopped after two hours by command line (never by bare pid), and nothing on the judge,
certifier, terminal lane or money path is ever stopped automatically."""
from __future__ import annotations

import json
import socket
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "desks" / "mt5"))
sys.path.insert(0, str(ROOT / "desks" / "mt5" / "research"))

import check_job_locks as C  # noqa: E402
import job_lock as J  # noqa: E402


@pytest.fixture()
def root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(J, "LOCK_ROOT", tmp_path)
    monkeypatch.setattr(J, "HEALTH_REPORT", tmp_path / "JOB_LOCK_HEALTH.json")
    monkeypatch.setattr(J, "STOPS_LEDGER", tmp_path / "JOB_LOCK_STOPS.jsonl")
    monkeypatch.setattr(J, "_owner_state", lambda path: "ALIVE")
    monkeypatch.setattr(C, "_journal", lambda name, health: None)
    return tmp_path


def _hold(root: Path, name: str, pid: int = 18040) -> Path:
    p = root / f"{name}.json"
    p.write_text(json.dumps({"token": f"t-{name}", "pid": pid, "host": socket.gethostname()}),
                 "utf-8")
    return p


def test_a_wedged_research_owner_is_stopped_after_two_hours(root: Path) -> None:
    _hold(root, "merge_hypotheses")
    stops: list[tuple[int, tuple[str, ...]]] = []

    def stop(pid, frags, started_at=None):
        stops.append((pid, frags))
        return {"stopped": True, "why": "terminated"}

    C.run(root=root, now=0.0, stop=stop, cpu_of=lambda pid: 50.0)
    one_h = C.run(root=root, now=3600.0, stop=stop, cpu_of=lambda pid: 50.0)
    assert one_h["status"] == "RED" and one_h["wedged"] == ["merge_hypotheses"] and not stops
    two_h = C.run(root=root, now=C.AUTO_STOP_AFTER_S + 60, stop=stop, cpu_of=lambda pid: 50.0)
    assert stops == [(18040, C.AUTO_STOP_JOBS["merge_hypotheses"])]
    assert two_h["locks"]["merge_hypotheses"]["status"] == "STOPPED"
    assert two_h["status"] == "OK"
    report = json.loads(J.HEALTH_REPORT.read_text("utf-8"))
    assert report["stops"][-1]["lock"] == "merge_hypotheses"


def test_the_money_path_and_the_judge_are_never_stopped(root: Path) -> None:
    assert not (set(C.AUTO_STOP_JOBS) & C.NEVER_STOP)
    for name in sorted(C.NEVER_STOP):
        _hold(root, name)
    called: list[int] = []
    C.run(root=root, now=0.0, stop=lambda p, f, s=None: called.append(p),
          cpu_of=lambda pid: 1.0)
    out = C.run(root=root, now=10 * C.AUTO_STOP_AFTER_S,
                stop=lambda p, f, s=None: called.append(p),
                cpu_of=lambda pid: 1.0)
    assert not called
    assert out["status"] == "RED" and out["wedged"] == sorted(C.NEVER_STOP)


def test_a_refused_stop_stays_red(root: Path) -> None:
    _hold(root, "merge_hypotheses")
    def refuse(pid, f, s=None):
        return {"stopped": False, "why": "stop refused: AccessDenied"}
    C.run(root=root, now=0.0, stop=refuse, cpu_of=lambda pid: 1.0)
    out = C.run(root=root, now=C.AUTO_STOP_AFTER_S + 60, stop=refuse, cpu_of=lambda pid: 1.0)
    assert out["status"] == "RED"
    assert "AccessDenied" in out["locks"]["merge_hypotheses"]["auto_stop"]["why"]


def test_stop_checks_the_command_line_before_touching_a_pid(monkeypatch) -> None:
    res = C._stop(os.getpid(), ("definitely_not_this_process_xyz",))
    assert res["stopped"] is False and "pid reused" in res["why"]


def test_sidecars_are_not_locks(root: Path) -> None:
    _hold(root, "edge_search")
    (root / "edge_search.progress.json").write_text("{}", "utf-8")
    (root / "edge_search.peaks.json").write_text("[]", "utf-8")
    assert [p.name for p in C._locks(root)] == ["edge_search.json"]


def test_the_leg_is_hourly_and_its_report_is_watched() -> None:
    hc = (ROOT / "desks" / "mt5" / "research" / "hourly_cycle.py").read_text("utf-8")
    core = hc[hc.index("CORE_LEGS: frozenset[str] = frozenset({"):]
    assert '"job_lock_health"' in core[: core.index("})")]
    assert '_costed("job_lock_health", job_lock_health)' in hc and '"job_lock_health": jlh' in hc
    sys.path.insert(0, str(ROOT))
    from libs.research import layers
    assert layers.LEG_LAYER.get("job_lock_health") == "meta"
    from research import issue_board as board
    assert any(c[1].endswith("JOB_LOCK_HEALTH.json") for c in board.CADENCE)


# --- audit of v5 ---------------------------------------------------------------------------
import os  # noqa: E402
import subprocess  # noqa: E402
import time  # noqa: E402
from datetime import UTC, datetime  # noqa: E402

psutil = pytest.importorskip("psutil")
_REAL_JOURNAL = C._journal


def _wait_children(pid: int, n: int, timeout: float = 20.0) -> list:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        kids = psutil.Process(pid).children(recursive=True)
        if len(kids) >= n:
            return kids
        time.sleep(0.05)
    raise AssertionError("child never started")


def _spawn(script: Path, body: str) -> subprocess.Popen:
    script.write_text(body, "utf-8")
    return subprocess.Popen([sys.executable, str(script)])


_PARENT_WAITS_ON_BUSY_CHILD = (
    "import subprocess, sys\n"
    "subprocess.run([sys.executable, '-c', 'import time\\nt=time.time()\\n"
    "while time.time()-t<60: pass'])\n")


def test_mf1_a_parent_waiting_on_a_busy_child_is_progressing(tmp_path: Path) -> None:
    proc = _spawn(tmp_path / "merge_hypotheses.py", _PARENT_WAITS_ON_BUSY_CHILD)
    try:
        _wait_children(proc.pid, 1)
        time.sleep(1.5)
        own = psutil.Process(proc.pid).cpu_times()
        tree = J._owner_cpu_s(proc.pid)
        assert tree is not None and tree > own.user + own.system + 1.0
    finally:
        for p in psutil.Process(proc.pid).children(recursive=True):
            p.kill()
        proc.kill()
        proc.wait()


def test_a_descendant_exiting_rebases_the_cpu_but_not_the_idle_clock(tmp_path: Path,
                                                                    monkeypatch) -> None:
    monkeypatch.setattr(J, "LOCK_ROOT", tmp_path)
    lock = _hold(tmp_path, "warm_gauntlet_cache")
    J.owner_progress(lock, now=0.0, cpu_of=lambda pid: 100.0)
    # a helper exits every half hour: the sum drops, but a drop is not progress
    for k in range(1, 5):
        out = J.owner_progress(lock, now=k * 1800.0 + 60, cpu_of=lambda pid, k=k: 100.0 - k)
    assert out["status"] == "WEDGED" and out["idle_s"] >= C.AUTO_STOP_AFTER_S
    # and the next child's work counts from the lowered baseline
    nxt = J.owner_progress(lock, now=4 * 1800.0 + 120, cpu_of=lambda pid: 97.5)
    assert nxt["status"] == "PROGRESSING"


def test_mf1_the_stop_takes_the_whole_tree(tmp_path: Path) -> None:
    proc = _spawn(tmp_path / "merge_hypotheses.py", _PARENT_WAITS_ON_BUSY_CHILD)
    try:
        kids = _wait_children(proc.pid, 1)
        later = datetime.now(UTC).isoformat()
        res = C._stop(proc.pid, ("merge_hypotheses",), later)
        assert res["stopped"] is True and res["tree"] == 2, res
        proc.wait(timeout=30)
        assert not any(k.is_running() and k.status() != psutil.STATUS_ZOMBIE for k in kids)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()


def test_mf2_a_script_name_inside_another_argument_never_matches(tmp_path: Path) -> None:
    assert not C.runs_script(["bash", "-c", "python gateway.py --log merge_hypotheses.log"],
                             ("merge_hypotheses",))
    assert not C.runs_script(["python", "gateway.py", "--log", "merge_hypotheses.log"],
                             ("merge_hypotheses",))
    assert not C.runs_script(["python", "gateway.py", "--note", "a/merge_hypotheses.py x"],
                             ("merge_hypotheses",))
    assert C.runs_script(["C:\\py\\python.exe", "C:\\opt\\quant\\research\\merge_hypotheses.py"],
                         ("merge_hypotheses",))
    assert C.runs_script(["python3", "-m", "research.merge_hypotheses"], ("merge_hypotheses",))
    proc = subprocess.Popen(["bash", "-c", "sleep 30 # gateway.py --log merge_hypotheses.log"])
    try:
        res = C._stop(proc.pid, ("merge_hypotheses",), datetime.now(UTC).isoformat())
        assert res["stopped"] is False and proc.poll() is None
    finally:
        proc.kill()
        proc.wait()


def test_mf2_a_recycled_pid_with_a_matching_command_line_is_refused(tmp_path: Path) -> None:
    proc = _spawn(tmp_path / "merge_hypotheses.py", "import time\ntime.sleep(30)\n")
    try:
        lock_written_before_it = "2026-01-01T00:00:00+00:00"
        res = C._stop(proc.pid, ("merge_hypotheses",), lock_written_before_it)
        assert res["stopped"] is False and "pid reused" in res["why"]
        assert C._stop(proc.pid, ("merge_hypotheses",), None)["stopped"] is False
        assert proc.poll() is None
    finally:
        proc.kill()
        proc.wait()


def test_mf2_hourly_cycle_is_never_a_curable_owner() -> None:
    assert not any("hourly_cycle" in v for v in C.AUTO_STOP_JOBS.values())


def test_mf3_the_report_is_written_every_pass_and_drops_released_locks(root: Path) -> None:
    out = C.run(root=root, now=100.0, cpu_of=lambda pid: 1.0)
    doc = json.loads(J.HEALTH_REPORT.read_text("utf-8"))
    assert out["status"] == "OK" and doc["status"] == "OK" and doc["locks"] == {}
    assert doc["at"].startswith("1970-01-01T00:01:40")
    lock = _hold(root, "merge_hypotheses")
    C.run(root=root, now=0.0, stop=lambda *a: {"stopped": False, "why": "x"},
          cpu_of=lambda pid: 1.0)
    C.run(root=root, now=J.WEDGED_AFTER_S + 60, stop=lambda *a: {"stopped": False, "why": "x"},
          cpu_of=lambda pid: 1.0)
    assert json.loads(J.HEALTH_REPORT.read_text("utf-8"))["status"] == "RED"
    lock.unlink()                         # the owner died and its lock is gone
    after = C.run(root=root, now=J.WEDGED_AFTER_S + 120, cpu_of=lambda pid: 1.0)
    doc = json.loads(J.HEALTH_REPORT.read_text("utf-8"))
    assert after["status"] == "OK" and doc["status"] == "OK" and "merge_hypotheses" not in doc[
        "locks"]


def test_a_stop_is_journaled(root: Path, monkeypatch, tmp_path: Path) -> None:
    sys.path.insert(0, str(ROOT))
    from libs.ops import events
    path = tmp_path / "events.jsonl"
    monkeypatch.setattr(events, "PATH", path)
    monkeypatch.setattr(C, "_journal", _REAL_JOURNAL)
    _hold(root, "edge_search")
    ok = lambda *a: {"stopped": True, "why": "terminated"}  # noqa: E731
    C.run(root=root, now=0.0, stop=ok, cpu_of=lambda pid: 1.0)
    C.run(root=root, now=C.AUTO_STOP_AFTER_S + 60, stop=ok, cpu_of=lambda pid: 1.0)
    rows = [json.loads(x) for x in path.read_text("utf-8").splitlines()]
    assert rows[-1]["kind"] == "JOB_LOCK_STOPPED" and rows[-1]["lock"] == "edge_search"
    assert "JOB_LOCK_STOPPED" in events.KINDS


def test_red_exits_with_a_named_failure(root: Path, monkeypatch) -> None:
    monkeypatch.setattr(C, "run", lambda: {"status": "RED", "wedged": ["x"], "locks": {}})
    assert C.main([]) == C.EXIT_WEDGED == 3
    sys.path.insert(0, str(ROOT / "desks" / "mt5"))
    from research import hourly_cycle as hc
    assert hc._exit_outcome("job_lock_health", 3) == "exit_code=3:OWNER_WEDGED"
    assert 3 not in hc.VERDICT_EXITS.get("job_lock_health", ())
    assert hc._exit_outcome("job_lock_health", 2) == "exit_code=2"   # argparse, never WEDGED


def test_the_bound_artifact_is_the_report_job_lock_writes() -> None:
    assert C.OUT.resolve() == J.HEALTH_REPORT.resolve()


# --- audit of v6 (should-fixes) --------------------------------------------------------------
_SPAWNS_IN_A_LOOP = (
    "import subprocess, sys, time, pathlib\n"
    "d = pathlib.Path(sys.argv[1])\n"
    "while True:\n"
    "    p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
    "    (d / str(p.pid)).write_text('')\n"
    "    time.sleep(0.01)\n")


def test_sf1_an_owner_spawning_in_a_loop_leaves_no_orphan(tmp_path: Path) -> None:
    pids = tmp_path / "pids"
    pids.mkdir()
    script = tmp_path / "merge_hypotheses.py"
    script.write_text(_SPAWNS_IN_A_LOOP, "utf-8")
    proc = subprocess.Popen([sys.executable, str(script), str(pids)])
    try:
        _wait_children(proc.pid, 5)
        res = C._stop(proc.pid, ("merge_hypotheses",), datetime.now(UTC).isoformat())
        assert res["stopped"] is True, res
        proc.wait(timeout=30)
        time.sleep(0.5)
        born = [int(p.name) for p in pids.iterdir()]
        assert born
        alive = []
        for pid in born:
            try:
                q = psutil.Process(pid)
                if q.status() != psutil.STATUS_ZOMBIE and "time.sleep(60)" in " ".join(
                        q.cmdline()):
                    alive.append(pid)
            except psutil.NoSuchProcess:
                pass
        assert not alive, f"{len(alive)} orphan(s) of {len(born)}"
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()


def test_sf6_only_the_first_script_element_counts() -> None:
    m = ("merge_hypotheses",)
    assert not C.runs_script(["python", "other.py", "--in", "merge_hypotheses.py"], m)
    assert not C.runs_script(["python", "-c", "import x", "merge_hypotheses.py"], m)
    assert C.runs_script(["python", "-u", "research/merge_hypotheses.py", "--x"], m)
    assert C.runs_script(["pythonw.exe", "-m", "research.merge_hypotheses"], m)


def test_sf7_a_stale_contender_never_drops_a_stop(root: Path) -> None:
    _hold(root, "edge_search")
    ok = lambda *a: {"stopped": True, "why": "terminated"}  # noqa: E731
    C.run(root=root, now=0.0, stop=ok, cpu_of=lambda pid: 1.0)
    stale = json.loads(J.HEALTH_REPORT.read_text("utf-8"))
    C.run(root=root, now=C.AUTO_STOP_AFTER_S + 60, stop=ok, cpu_of=lambda pid: 1.0)
    J.HEALTH_REPORT.write_text(json.dumps(stale), "utf-8")      # a contender's old copy
    J._publish_health("macro_desk", {"status": "ACQUIRED"})
    doc = json.loads(J.HEALTH_REPORT.read_text("utf-8"))
    assert [r["lock"] for r in doc["stops"]] == ["edge_search"]
    assert len(J.STOPS_LEDGER.read_text("utf-8").splitlines()) == 1


def _own_lock(root: Path, name: str = "merge_hypotheses") -> Path:
    p = root / f"{name}.json"
    p.write_text(json.dumps({"token": "mine", "pid": os.getpid(), "host": socket.gethostname(),
                             "started_at": "2026-10-29T00:00:00+00:00"}), "utf-8")
    return p


def test_an_owner_that_beats_is_judged_by_its_beats_not_its_cpu(root: Path) -> None:
    lock = _own_lock(root)
    assert J.heartbeat("merge_hypotheses", "order", expect_s=2700, now=0.0)
    spinning = iter(range(0, 10_000, 140))          # ~2.3 s of CPU a minute, like 2026-10-29
    inside = J.owner_progress(lock, now=2000.0, cpu_of=lambda pid: float(next(spinning)))
    assert inside["status"] == "PROGRESSING" and inside["phase"] == "order"
    past = J.owner_progress(lock, now=2700.0 + 60, cpu_of=lambda pid: float(next(spinning)))
    assert past["status"] == "WEDGED" and past["signal"] == "beat"
    out = C.run(root=root, now=C.AUTO_STOP_AFTER_S + 60,
                stop=lambda *a: {"stopped": True, "why": "t"},
                cpu_of=lambda pid: float(next(spinning)))
    assert out["locks"]["merge_hypotheses"]["status"] == "STOPPED"


def test_a_beat_is_written_only_by_the_lock_owner(root: Path) -> None:
    _hold(root, "merge_hypotheses", pid=1)
    assert J.heartbeat("merge_hypotheses", "order") is False
    assert not (root / "merge_hypotheses.beat.json").exists()
    assert "merge_hypotheses.beat.json" not in [p.name for p in C._locks(root)]


def test_a_previous_owners_beat_is_ignored(root: Path) -> None:
    lock = _own_lock(root)
    J.heartbeat("merge_hypotheses", "order", now=0.0)
    lock.write_text(json.dumps({"token": "next", "pid": os.getpid(),
                                "host": socket.gethostname()}), "utf-8")
    assert J.owner_progress(lock, now=10 * 3600.0, cpu_of=lambda pid: 1.0)["signal"] == "cpu"


# --- audit of v7 -----------------------------------------------------------------------------
def test_mf1_the_cycles_own_launch_argv_matches() -> None:
    m = ("merge_hypotheses",)
    script = "C:\\opt\\quant\\desks\\mt5\\research\\merge_hypotheses.py"
    assert C.runs_script([sys.executable, "-u", "-W", "ignore", script], m)  # _producer's argv
    assert C.runs_script(["python", "-X", "utf8", "merge_hypotheses.py"], m)
    assert C.runs_script(["python", "-Wignore", "merge_hypotheses.py"], m)
    assert not C.runs_script(["python", "-W", "merge_hypotheses.py", "other.py"], m)
    assert not C.runs_script(["python", "-W"], m)
    hc = (ROOT / "desks" / "mt5" / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '[sys.executable, "-u", "-W", "ignore", str(target), *args]' in hc


def test_mf1_an_hourly_launched_owner_is_stoppable(tmp_path: Path) -> None:
    script = tmp_path / "merge_hypotheses.py"
    script.write_text("import time\ntime.sleep(60)\n", "utf-8")
    proc = subprocess.Popen([sys.executable, "-u", "-W", "ignore", str(script)])
    try:
        time.sleep(0.3)
        res = C._stop(proc.pid, ("merge_hypotheses",), datetime.now(UTC).isoformat())
        assert res["stopped"] is True and res["list_rounds_capped"] is False, res
        proc.wait(timeout=30)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()


def test_mf2_a_refusal_mid_freeze_never_leaves_the_owner_stopped(tmp_path: Path,
                                                                 monkeypatch) -> None:
    script = tmp_path / "merge_hypotheses.py"
    script.write_text("import time\ntime.sleep(60)\n", "utf-8")
    proc = subprocess.Popen([sys.executable, str(script)])
    try:
        time.sleep(0.3)

        def denied(self, recursive=False):
            raise psutil.AccessDenied(self.pid)
        monkeypatch.setattr(psutil.Process, "children", denied)
        res = C._stop(proc.pid, ("merge_hypotheses",), datetime.now(UTC).isoformat())
        assert res["stopped"] is False and "AccessDenied" in res["why"]
        time.sleep(0.3)
        assert psutil.Process(proc.pid).status() != psutil.STATUS_STOPPED
        assert proc.poll() is None
    finally:
        proc.kill()
        proc.wait()


def test_a_beat_limit_is_clamped_and_a_future_beat_is_unreadable(root: Path) -> None:
    lock = _own_lock(root)
    J.heartbeat("merge_hypotheses", "order", expect_s=float("inf"), now=0.0)
    beat = json.loads((root / "merge_hypotheses.beat.json").read_text("utf-8"))
    assert beat["expect_s"] == J.BEAT_EXPECT_MAX_S
    assert J.owner_progress(lock, now=J.BEAT_EXPECT_MAX_S + 60,
                            cpu_of=lambda pid: 1.0)["status"] == "WEDGED"
    J.heartbeat("merge_hypotheses", "order", now=10_000.0)
    out = J.owner_progress(lock, now=100.0, cpu_of=lambda pid: 1.0)
    assert out["signal"] == "cpu"                # a beat from the future vouches for nothing
    assert not list(root.glob("*.tmp"))


# --- audit of v8 (should-fixes) --------------------------------------------------------------
def test_a_beaten_phase_that_is_busy_is_never_stopped(root: Path) -> None:
    _own_lock(root)
    J.heartbeat("merge_hypotheses", "families", expect_s=3600, now=0.0)
    cpu = iter(float(k * 3000) for k in range(100))   # ~0.8 of a core, working hard
    stops: list[int] = []

    def stop(pid, frags, started_at=None):
        stops.append(pid)
        return {"stopped": True, "why": "t"}
    for now in (600.0, 3700.0, 7300.0, 11_000.0, 20_000.0):
        out = C.run(root=root, now=now, stop=stop, cpu_of=lambda pid: next(cpu))
    assert out["locks"]["merge_hypotheses"]["status"] == "WEDGED"     # named RED ...
    assert out["locks"]["merge_hypotheses"]["cpu_rate"] > J.BUSY_CPU_RATE
    assert not stops                                                    # ... never killed
    assert out["locks"]["merge_hypotheses"]["auto_stop_withheld"].startswith("busy")
    assert not C.stoppable({"signal": "beat", "idle_s": 3 * 3600.0, "limit_s": 60,
                            "cpu_rate": None})


def test_sf3_combined_and_inline_flags_parse_like_cpython() -> None:
    m = ("merge_hypotheses",)
    assert not C.runs_script(["python", "-cimport x", "merge_hypotheses.py"], m)
    assert not C.runs_script(["python", "-uW", "merge_hypotheses.py", "other.py"], m)
    assert not C.runs_script(["python", "-", "merge_hypotheses.py"], m)
    assert C.runs_script(["python", "-uW", "ignore", "merge_hypotheses.py"], m)
    assert C.runs_script(["python", "-mresearch.merge_hypotheses"], m)
    assert C.runs_script(["python", "-u", "C:\\Program Files\\q\\merge_hypotheses.py"], m)
    assert C.runs_script(["python", "-u", "-W", "ignore", "merge_hypotheses.py"], m)


def test_sf2_a_partial_kill_names_the_pids_it_terminated(tmp_path: Path, monkeypatch) -> None:
    script = tmp_path / "merge_hypotheses.py"
    script.write_text(_PARENT_WAITS_ON_BUSY_CHILD, "utf-8")
    proc = subprocess.Popen([sys.executable, str(script)])
    try:
        kids = _wait_children(proc.pid, 1)
        real = psutil.Process.terminate

        def refuse_owner(self):
            if self.pid == proc.pid:
                raise psutil.AccessDenied(self.pid)
            return real(self)
        monkeypatch.setattr(psutil.Process, "terminate", refuse_owner)
        res = C._stop(proc.pid, ("merge_hypotheses",), datetime.now(UTC).isoformat())
        assert res["stopped"] is False and res["terminated"] == [kids[0].pid]
        assert psutil.Process(proc.pid).status() != psutil.STATUS_STOPPED
    finally:
        monkeypatch.undo()
        for k in psutil.Process(proc.pid).children(recursive=True):
            k.kill()
        proc.kill()
        proc.wait()


def test_sf4_a_nan_beat_vouches_for_nothing(root: Path) -> None:
    lock = _own_lock(root)
    (root / "merge_hypotheses.beat.json").write_text(
        '{"token": "mine", "phase": "x", "at": NaN, "expect_s": null}', "utf-8")
    assert J.owner_progress(lock, now=100.0, cpu_of=lambda pid: 1.0)["signal"] == "cpu"


# --- audit of v9 (should-fixes) --------------------------------------------------------------
def test_sf1_a_contenders_look_seconds_later_never_measures_a_rate(root: Path) -> None:
    lock = _own_lock(root)
    J.heartbeat("merge_hypotheses", "families", expect_s=3600, now=0.0)
    J.owner_progress(lock, now=100.0, cpu_of=lambda pid: 1000.0)            # hourly seed
    J.owner_progress(lock, now=3600.0 - 2, cpu_of=lambda pid: 3880.0)       # the leg's look
    # a contender 2 s later, across a 2 s IO stall, must not measure 0.0 ...
    near = J.owner_progress(lock, now=3600.0, cpu_of=lambda pid: 3880.0)
    assert near["cpu_rate"] is None
    # ... nor overwrite the baseline: the next hourly look still measures ~0.8 cores
    later = J.owner_progress(lock, now=7200.0, cpu_of=lambda pid: 6760.0)
    assert later["cpu_rate"] == pytest.approx(0.8, abs=0.01)


def test_sf1_a_clock_jump_or_a_bad_baseline_measures_nothing(root: Path) -> None:
    lock = _own_lock(root)
    J.heartbeat("merge_hypotheses", "families", expect_s=3600, now=0.0)
    J.owner_progress(lock, now=100.0, cpu_of=lambda pid: 1000.0)
    jump = J.owner_progress(lock, now=100.0 + 9 * 3600, cpu_of=lambda pid: 3880.0)
    assert jump["cpu_rate"] is None                                        # re-seeded
    side = root / "merge_hypotheses.progress.json"
    for bad in (float("-inf"), -1e12, True):
        rec = json.loads(side.read_text("utf-8"))
        rec["obs_t"] = bad
        side.write_text(json.dumps(rec), "utf-8")
        out = J.owner_progress(lock, now=40_000.0, cpu_of=lambda pid: 5000.0)
        assert out["cpu_rate"] is None


def test_sf2_withheld_says_why_and_a_day_without_a_beat_is_stopped() -> None:
    beat = {"signal": "beat", "limit_s": 3600.0}
    assert C.withheld({**beat, "idle_s": 3 * 3600.0, "cpu_rate": 0.8}) == "busy 0.80 cores"
    assert C.withheld({**beat, "idle_s": 3 * 3600.0}) == "cpu_rate unmeasured"
    assert C.withheld({**beat, "idle_s": 3 * 3600.0, "cpu_rate": 0.04}) is None
    assert C.withheld({**beat, "idle_s": C.BEAT_HARD_CEILING_S, "cpu_rate": 0.9}) is None
    assert C.withheld({**beat, "idle_s": 600.0}).startswith("no beat for 0.2 h")


def test_sf3_a_partial_kill_is_journaled_and_ledgered(root: Path, monkeypatch) -> None:
    journaled: list[str] = []
    monkeypatch.setattr(C, "_journal", lambda name, health: journaled.append(name))
    _hold(root, "edge_search")
    part = lambda *a: {"stopped": False, "terminated": [11], "why": "refused"}  # noqa: E731
    C.run(root=root, now=0.0, stop=part, cpu_of=lambda pid: 1.0)
    out = C.run(root=root, now=C.AUTO_STOP_AFTER_S + 60, stop=part, cpu_of=lambda pid: 1.0)
    assert out["status"] == "RED" and journaled == ["edge_search"]
    row = json.loads(J.STOPS_LEDGER.read_text("utf-8").splitlines()[-1])
    assert row["partial"] is True and row["terminated"] == [11]


def test_sf5_nits() -> None:
    assert not C.runs_script(["python", "--", "-u", "x.py"], ("x",))
    assert C.runs_script(["python", "-u", "--", "x.py"], ("x",))
    assert not J._finite(True) and not J._finite(float("nan")) and J._finite(1.5)
