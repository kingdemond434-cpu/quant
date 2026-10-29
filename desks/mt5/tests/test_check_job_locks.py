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
    import os
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


def test_mf1_a_descendant_exiting_is_activity_not_a_stall(tmp_path: Path,
                                                          monkeypatch) -> None:
    monkeypatch.setattr(J, "LOCK_ROOT", tmp_path)
    lock = _hold(tmp_path, "warm_gauntlet_cache")
    J.owner_progress(lock, now=0.0, cpu_of=lambda pid: 100.0)
    out = J.owner_progress(lock, now=J.WEDGED_AFTER_S + 60, cpu_of=lambda pid: 3.0)
    assert out["status"] == "PROGRESSING" and "descendant exited" in out["why"]


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
    assert C.main([]) == C.EXIT_WEDGED == 2
    sys.path.insert(0, str(ROOT / "desks" / "mt5"))
    from research import hourly_cycle as hc
    assert hc._exit_outcome("job_lock_health", 2) == "exit_code=2:OWNER_WEDGED"
    assert 2 not in hc.VERDICT_EXITS.get("job_lock_health", ())


def test_the_bound_artifact_is_the_report_job_lock_writes() -> None:
    assert C.OUT.resolve() == J.HEALTH_REPORT.resolve()
