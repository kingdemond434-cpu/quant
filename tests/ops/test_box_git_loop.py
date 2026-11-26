"""The box release loop: checked once, dead runs retried, stages independent."""
from __future__ import annotations

import contextlib
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ops.box_git import box_ci  # noqa: E402
from ops.box_git import box_loop as L  # noqa: E402

NOW = datetime(2026, 11, 19, 20, tzinfo=UTC)


def _cfg(tmp: Path) -> L.Config:
    return L.Config(forge_url="https://127.0.0.1:443", bare=tmp / "b.git", work=tmp / "w",
                    tokens=tmp / "t", ca=tmp / "ca.pem", state=tmp / "s.json")


def test_a_completed_status_means_checked_and_a_dead_pending_is_retried() -> None:
    assert L.checked([{"status": "completed"}], NOW)
    young = (NOW - timedelta(hours=1)).isoformat()
    old = (NOW - timedelta(hours=7)).isoformat()
    assert L.checked([{"status": "in_progress", "started_at": young}], NOW)
    assert not L.checked([{"status": "in_progress", "started_at": old}], NOW)
    assert not L.checked([], NOW)


def test_one_failing_stage_never_stops_the_others(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(L, "live_head", lambda cfg: (_ for _ in ()).throw(RuntimeError("no git")))
    monkeypatch.setattr(L, "pr_tick", lambda cfg: "no PR waiting for checks")
    monkeypatch.setattr(L, "promote_tick", lambda cfg: "nothing new to promote")
    doc = L.tick(_cfg(tmp_path))
    assert doc["gate"].startswith("ERROR") and doc["full"].startswith("ERROR")
    assert doc["pr"] == "no PR waiting for checks" and doc["promote"] == "nothing new to promote"


def test_a_full_run_that_dies_is_recorded_red_and_frees_the_slot(tmp_path: Path,
                                                                 monkeypatch) -> None:
    cfg = _cfg(tmp_path)
    monkeypatch.setattr(L, "_resources", lambda cfg: (True, 4, "ok"))

    def boom(cfg, sha):
        raise RuntimeError("worktree failed")
    monkeypatch.setattr(L, "worktree", boom)
    with contextlib.suppress(RuntimeError):
        L.full_tick(cfg, "h1")
    s = box_ci.load_state(cfg.state)
    assert s["full_running"] is None
    assert s["full_results"][-1] == {**s["full_results"][-1], "head": "h1", "ok": False}


def test_resources_unmeasured_start_nothing(tmp_path: Path, monkeypatch) -> None:
    cfg = _cfg(tmp_path)
    monkeypatch.setattr(L, "_resources", lambda cfg: (False, 0, "no idle cores right now"))
    assert "waits" in L.full_tick(cfg, "h1")
    assert box_ci.load_state(cfg.state).get("full_running") is None


def test_only_an_auditor_clear_of_the_exact_head_lets_pr_code_run() -> None:
    h = "a" * 40
    assert L.audited_clear([{"body": f"AUDIT CLEAR {h} merge"}], h)
    assert not L.audited_clear([{"body": f"UNCOUNTED CLEAR {h} merge"}], h)
    assert not L.audited_clear([{"body": f"AUDIT CLEAR {h}"}, {"body": f"AUDIT HOLD {h}"}], h)
    assert not L.audited_clear([{"body": f"AUDIT CLEAR {'b' * 40}"}], h)
    assert not L.audited_clear([], h)


def test_pr_code_runs_through_the_worker_folder_never_in_the_loop(tmp_path: Path) -> None:
    import threading
    cfg = L.Config(**{**_cfg(tmp_path).__dict__, "ci_jobs": tmp_path / "jobs"})
    L.JOB_POLL_S = 0.05
    stop = threading.Event()

    def worker() -> None:
        while not stop.is_set():
            L.worker_pass(tmp_path / "jobs")
            stop.wait(0.05)
    t = threading.Thread(target=worker)
    t.start()
    probe = [sys.executable, "-c", "import os; print(os.environ.get('SECRET_X'))"]
    os.environ["SECRET_X"] = "leak"
    try:
        rc, out = L._run_untrusted(cfg, probe, cwd=tmp_path, extra_env={"A": "1"}, timeout=60)
    finally:
        os.environ.pop("SECRET_X", None)
        stop.set()
        t.join()
    assert rc == 0 and out.strip() == "None"  # the loop's environment does not leak to the job
    assert not list((tmp_path / "jobs" / "pending").glob("*"))
    assert not list((tmp_path / "jobs" / "done").glob("*"))


def _run(name: str, concl: str, summary: str, hours_ago: float, rid: int,
         status: str = "completed") -> dict:
    return {"id": rid, "name": name, "status": status, "conclusion": concl,
            "started_at": (NOW - timedelta(hours=hours_ago)).isoformat(),
            "output": {"summary": summary}}


def test_a_red_the_box_caused_is_rerun_a_bounded_number_of_times() -> None:
    """Box 11-20: PR #17 went 5/5 red on git exit 128 and a timeout; a completed red was final."""
    env = "box: risk-invariants: ... returned non-zero exit status 128"
    t_out = "box CI, 141 impacted test file(s): pytest rc=1: +++ Timeout +++"
    first = [_run("quality", "failure", t_out, 2, 1), _run("risk-invariants", "failure", env, 2, 2)]
    assert not L.checked(first, NOW)                          # an hour later: re-run
    assert L.checked([_run("quality", "failure", t_out, 0.5, 1)], NOW)   # not yet
    # a re-run in flight is judged like any pending
    inflight = [*first, _run("quality", "", "running", 0.2, 3, status="in_progress")]
    assert L.checked(inflight, NOW)
    # the re-run's green answers the head
    assert L.checked([*first, _run("quality", "success", "ok", 0.1, 4),
                      _run("risk-invariants", "success", "ok", 0.1, 5)], NOW)
    # three environmental reds in a row: final
    three = [_run("quality", "failure", t_out, h, i) for i, h in enumerate((9, 6, 3))]
    assert L.checked(three, NOW)


def test_a_red_the_code_caused_stays_final() -> None:
    red = [_run("quality", "failure", "box CI: pytest rc=1: 1 failed; FAILED tests/a.py::t", 5, 1)]
    assert L.checked(red, NOW)
    mixed = [*red, _run("risk-invariants", "failure", "exit status 128", 5, 2)]
    assert L.checked(mixed, NOW)              # a real red decides the head; no re-run


def test_a_job_gets_the_workers_own_home_and_never_one_the_job_file_names(tmp_path: Path) -> None:
    """Box 2026-11-24: Path.home() raised at import in 38-48 modules because a job carried no
    profile variables. The worker supplies its OWN; a job file cannot choose them."""
    import json
    jobs = tmp_path / "jobs"
    (jobs / "pending").mkdir(parents=True)
    probe = [sys.executable, "-c",
             "import os; print(os.environ.get('USERPROFILE'), os.environ.get('TEMP'))"]
    doc = {"id": "j1", "argv": probe, "cwd": str(tmp_path), "timeout": 60,
           "env": {"PATH": os.environ.get("PATH", ""), "USERPROFILE": "C:/Users/quantgate",
                   "SYSTEMROOT": os.environ.get("SYSTEMROOT", "")}}
    (jobs / "pending" / "j1.json").write_text(json.dumps(doc), encoding="utf-8")
    saved = {k: os.environ.get(k) for k in ("USERPROFILE", "TEMP")}
    os.environ["USERPROFILE"], os.environ["TEMP"] = str(tmp_path / "worker"), str(tmp_path)
    try:
        assert L.worker_pass(jobs) == 1
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    out = json.loads((jobs / "done" / "j1.json").read_text(encoding="utf-8"))
    assert out["rc"] == 0, out
    assert out["out"].split() == [str(tmp_path / "worker"), str(tmp_path)]


def test_a_replay_red_at_the_old_600s_cap_is_rerun_and_still_blocks_until_it_passes() -> None:
    """Boot r15 (box 2026-11-26): every fast-path replay hit the 600 s cap, the PR counted as
    checked after two env re-runs and 0 of 148 CLEAR PRs ever merged. A red that measured a cap
    smaller than the job has now is run again at once, however many times it already ran."""
    old = "box: replay-shadow rc=124: timed out after 600s"
    reds = [_run("replay-shadow", "failure", old, h, i) for i, h in enumerate((30, 20, 10))]
    assert not L.checked(reds, NOW)                       # three old-cap reds: run it again
    assert not L.checked([_run("replay-shadow", "failure", old, 0.1, 9)], NOW)   # no hour wait
    now_cap = f"box: replay-shadow rc=124: timed out after {L.FAST_REPLAY_TIMEOUT_S}s"
    assert L.checked([*reds, _run("replay-shadow", "failure", now_cap, 0.1, 10)], NOW)
    assert L.checked([*reds, _run("replay-shadow", "success", "ok", 0.1, 11)], NOW)
    # a risk timeout at its own (unchanged) cap is no old-cap red
    risk = "box: risk suites rc=124: timed out after 600s"
    assert L.checked([_run("risk-invariants", "failure", risk, h, i)
                      for i, h in enumerate((9, 6, 3))], NOW)
    # a real code red in another context decides the head: no hour of replay is spent on it
    code = _run("risk-invariants", "failure", "risk suites rc=1: 2 failed", 5, 20)
    assert L.checked([code, *reds], NOW)
