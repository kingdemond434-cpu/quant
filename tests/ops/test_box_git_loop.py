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
