"""box_loop worktrees: nested checkouts survive; stale ones go at pass start (Audit MF-1)."""
from __future__ import annotations

import subprocess
from pathlib import Path

from ops.box_git import box_ci, box_loop


def _cfg(tmp: Path) -> box_loop.Config:
    bare = tmp / "repo"
    bare.mkdir()
    g = ["git", "-C", str(bare), "-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run([*g, "init", "-q"], check=True)
    (bare / "f.txt").write_text("1", encoding="utf-8")
    subprocess.run([*g, "add", "f.txt"], check=True)
    subprocess.run([*g, "commit", "-q", "-m", "one"], check=True)
    return box_loop.Config(forge_url="https://127.0.0.1", bare=bare, work=tmp / "work",
                           tokens=tmp / "t", ca=tmp / "ca", state=tmp / "state.json")


def test_nested_worktrees_both_survive(tmp_path, monkeypatch):
    monkeypatch.setattr(box_ci, "disk_ok", lambda free: (True, "ok"))
    cfg = _cfg(tmp_path)
    head = box_loop.git(cfg, "rev-parse", "HEAD")
    with box_loop.worktree(cfg, head) as b, box_loop.worktree(cfg, head) as h:
        assert (b / "f.txt").is_file() and (h / "f.txt").is_file()
    assert not list(cfg.work.glob("wt_*"))


def test_sweep_removes_stale_checkouts_only_at_pass_start(tmp_path, monkeypatch):
    monkeypatch.setattr(box_ci, "disk_ok", lambda free: (True, "ok"))
    cfg = _cfg(tmp_path)
    head = box_loop.git(cfg, "rev-parse", "HEAD")
    cfg.work.mkdir()
    stale = cfg.work / "wt_dead"
    box_loop.git(cfg, "worktree", "add", "-q", "--detach", str(stale), head)
    assert box_loop.sweep_stale(cfg) == 1
    assert not stale.exists()
    assert "wt_dead" not in box_loop.git(cfg, "worktree", "list")
    assert box_loop.sweep_stale(cfg) == 0


def test_checkout_refused_below_disk_floor(tmp_path, monkeypatch):
    monkeypatch.setattr(box_ci, "disk_ok", lambda free: (False, "1.0 GB free"))
    cfg = _cfg(tmp_path)
    try:
        with box_loop.worktree(cfg, "HEAD"):
            raise AssertionError("checkout made below the floor")
    except RuntimeError as exc:
        assert "no checkout" in str(exc)


def test_checkout_gets_the_long_limit_and_a_failed_add_leaves_nothing(tmp_path, monkeypatch):
    """Box 11-20 19:55Z: a ~50k-file checkout outran the 300 s bare-repo limit, so CI never
    started. Checkouts get WORKTREE_ADD_TIMEOUT; a failed add is cleaned up at once."""
    monkeypatch.setattr(box_ci, "disk_ok", lambda free: (True, "ok"))
    cfg = _cfg(tmp_path)
    head = box_loop.git(cfg, "rev-parse", "HEAD")
    seen: list[tuple[list[str], float]] = []
    real = box_loop._run

    def spy(argv, **kw):
        seen.append((list(argv), kw.get("timeout", 3600)))
        return real(argv, **kw)

    monkeypatch.setattr(box_loop, "_run", spy)
    with box_loop.worktree(cfg, head) as d:
        assert (d / "f.txt").is_file()
    adds = [(a, t) for a, t in seen if "add" in a and "worktree" in a]
    assert adds and adds[0][1] == box_loop.WORKTREE_ADD_TIMEOUT > 300
    assert "checkout.workers=0" in adds[0][0]

    def slow(argv, **kw):
        if "add" in argv and "worktree" in argv:
            real(argv, **kw)               # leaves a full checkout behind, then "times out"
            return 124, "timed out after 1800s"
        return real(argv, **kw)

    monkeypatch.setattr(box_loop, "_run", slow)
    try:
        with box_loop.worktree(cfg, head):
            raise AssertionError("a timed-out checkout was used")
    except RuntimeError as exc:
        assert "timed out" in str(exc)
    assert not list(cfg.work.glob("wt_*"))
    assert box_loop.git(cfg, "worktree", "list").count("\n") == 0
