"""The box release loop: checked once, dead runs retried, stages independent."""
from __future__ import annotations

import contextlib
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
