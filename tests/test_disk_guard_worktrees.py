"""A stale worktree on tmpfs is reclaimed WHOLE, never gutted file by file.

MEASURED 2026-08-27. /tmp is a tmpfs on this box, so a checkout left there holds resident RAM
against every organ that runs afterwards: /tmp/gw_base and /tmp/lawgate-head-w59v694v/t held
433MB between them while MemAvailable sat at 695MB, on the box that had OOM-killed its research
organs 221 times in three days (and took root cron with them on 08-20).

The file reaper could not fix it and would have made it worse: it unlinks regular files, so at
24h it would have started deleting TRACKED files inside a registered checkout, leaving
`git worktree list` advertising a tree whose every file reads as deleted -- the mass-deletion
launder this desk has already paid for (R0423). Removal goes through `git worktree remove`,
which refuses a dirty tree, and every refusal is reported with its reason instead of forced.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def guard():
    """Import by path and hand back the module -- never with cwd changed: disk_guard resolves
    ROOT from a literal, so a cwd-based test would reap the LIVE box's /tmp."""
    spec = importlib.util.spec_from_file_location(
        "_t_disk_guard", ROOT / "scripts" / "disk_guard.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _git(args: list[str], cwd: Path) -> str:
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True,
                          check=True).stdout.strip()


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(["init", "-q", "-b", "main"], repo)
    _git(["config", "user.email", "t@t"], repo)
    _git(["config", "user.name", "t"], repo)
    (repo / "a.txt").write_text("hello", encoding="utf-8")
    _git(["add", "a.txt"], repo)
    _git(["commit", "-qm", "one"], repo)
    return repo


def _age(path: Path, hours: float) -> None:
    old = (datetime.now(tz=UTC) - timedelta(hours=hours)).timestamp()
    for f in path.rglob("*"):
        if f.is_file() and not f.is_symlink():
            import os
            os.utime(f, (old, old))


def test_clean_stale_worktree_is_reclaimed_whole(guard, tmp_path, monkeypatch) -> None:
    repo = _repo(tmp_path)
    scratch = tmp_path / "tmp"
    scratch.mkdir()
    wt = scratch / "gw_base"
    _git(["worktree", "add", "-q", "--detach", str(wt), "HEAD"], repo)
    _age(wt, hours=48)
    monkeypatch.setattr(guard, "TMP_DIR", scratch)

    actions: list[str] = []
    freed, removed = guard.reap_tmpfs_worktrees(datetime.now(tz=UTC), repo, actions)

    assert removed == 1
    assert freed > 0
    assert not wt.exists()
    assert "reclaimed" in actions[0]
    assert str(wt) not in _git(["worktree", "list"], repo)


def test_a_worktree_holding_uncommitted_work_is_refused_with_its_reason(
        guard, tmp_path, monkeypatch) -> None:
    repo = _repo(tmp_path)
    scratch = tmp_path / "tmp"
    scratch.mkdir()
    wt = scratch / "dirty"
    _git(["worktree", "add", "-q", "--detach", str(wt), "HEAD"], repo)
    (wt / "a.txt").write_text("edited", encoding="utf-8")
    _age(wt, hours=48)   # stale AND dirty: staleness must not be enough to take it
    monkeypatch.setattr(guard, "TMP_DIR", scratch)

    actions: list[str] = []
    _, removed = guard.reap_tmpfs_worktrees(datetime.now(tz=UTC), repo, actions)

    assert removed == 0
    assert wt.exists(), "a reaper that can eat uncommitted work is not a janitor"
    assert any("uncommitted work" in a for a in actions)


def test_a_fresh_worktree_is_left_alone(guard, tmp_path, monkeypatch) -> None:
    repo = _repo(tmp_path)
    scratch = tmp_path / "tmp"
    scratch.mkdir()
    wt = scratch / "fresh"
    _git(["worktree", "add", "-q", "--detach", str(wt), "HEAD"], repo)
    monkeypatch.setattr(guard, "TMP_DIR", scratch)

    actions: list[str] = []
    _, removed = guard.reap_tmpfs_worktrees(datetime.now(tz=UTC), repo, actions)
    assert removed == 0
    assert wt.exists()


def test_file_reaper_never_unlinks_inside_a_registered_worktree(
        guard, tmp_path, monkeypatch) -> None:
    """The positive control for the hole: without the skip, `a.txt` is a stale regular file
    under /tmp and the file reaper would delete it out of a live checkout."""
    repo = _repo(tmp_path)
    scratch = tmp_path / "tmp"
    scratch.mkdir()
    wt = scratch / "keepme"
    _git(["worktree", "add", "-q", "--detach", str(wt), "HEAD"], repo)
    _age(wt, hours=48)
    loose = scratch / "loose.tmp"
    loose.write_text("scratch", encoding="utf-8")
    _age(scratch, hours=48)
    monkeypatch.setattr(guard, "TMP_DIR", scratch)
    monkeypatch.setattr(guard, "REPO", repo)

    actions: list[str] = []
    _, n_files = guard.reap_tmpfs(datetime.now(tz=UTC), actions)

    assert (wt / "a.txt").exists(), "the file reaper gutted a registered checkout"
    assert not loose.exists(), "control failed: the reaper is not reaping at all"
    assert n_files == 1
