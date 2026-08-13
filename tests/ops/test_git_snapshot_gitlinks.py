"""THE SNAPSHOT MUST NOT TRACK A WORKTREE AS A SUBMODULE (2026-08-12).

scripts/git_snapshot.py runs `git add -A` daily. This desk creates git worktrees under
.claude/worktrees/ routinely, and `git add -A` records any directory holding a `.git` entry as a
GITLINK (mode 160000) even though the repo has no .gitmodules and these are not submodules.

WHY THAT IS EXPENSIVE RATHER THAN UNTIDY. A gitlink's recorded sha moves whenever that worktree
commits, so the parent tree reads ` M <path>` permanently -- and it cannot be cleaned even in
principle, because committing the gitlink only re-points it at the new sha. deploy/pull_deploy.sh
refused on any tracked dirt, so four such gitlinks helped wedge the box's only inbound deploy path:
1078 logged ticks from 08-04, `deployed` zero times.

.gitignore covers .claude/worktrees/, which is where it actually happened. This covers the CLASS --
a worktree or stray clone made anywhere else -- because the failure was never about that one path.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from scripts.git_snapshot import _drop_accidental_gitlinks


def _git(cwd: Path, *args: str) -> str:
    r = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, check=True)
    return r.stdout.strip()


@pytest.fixture
def repo(tmp_path, monkeypatch):
    if not shutil.which("git"):
        pytest.skip("git unavailable")
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-b", "main")
    for k, v in (("user.email", "t@t"), ("user.name", "t"), ("commit.gpgsign", "false")):
        _git(root, "config", k, v)
    (root / "real.txt").write_text("tracked source", "utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "base")
    monkeypatch.chdir(root)
    return root


def _staged_modes(root: Path) -> dict[str, str]:
    out = _git(root, "ls-files", "-s")
    modes = {}
    for ln in out.splitlines():
        if "\t" in ln:
            modes[ln.split("\t", 1)[1]] = ln.split(" ", 1)[0]
    return modes


def _add_worktree(root: Path, name: str) -> Path:
    path = root / ".claude/worktrees" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    _git(root, "worktree", "add", "--detach", str(path), "HEAD")
    return path


class TestAccidentalGitlinksAreRefused:
    def test_git_add_dash_a_really_does_stage_a_worktree_as_a_gitlink(self, repo):
        """PIN THE PREMISE FIRST -- if git ever stops doing this, the guard is dead weight."""
        _add_worktree(repo, "scratch")
        _git(repo, "add", "-A")
        assert _staged_modes(repo).get(".claude/worktrees/scratch") == "160000"

    def test_the_gitlink_is_dropped_from_the_index(self, repo):
        _add_worktree(repo, "scratch")
        _git(repo, "add", "-A")
        dropped = _drop_accidental_gitlinks()
        assert dropped == [".claude/worktrees/scratch"]
        assert ".claude/worktrees/scratch" not in _staged_modes(repo)

    def test_real_source_is_left_alone(self, repo):
        """The guard must be surgical: it drops mode-160000 entries and nothing else."""
        _add_worktree(repo, "scratch")
        (repo / "new_source.py").write_text("x = 1\n", "utf-8")
        _git(repo, "add", "-A")
        _drop_accidental_gitlinks()
        staged = _staged_modes(repo)
        assert "new_source.py" in staged
        assert "real.txt" in staged

    def test_an_already_committed_gitlink_is_untracked_not_merely_unstaged(self, repo):
        """The four live ones were already COMMITTED, so unstaging alone would fix nothing."""
        _add_worktree(repo, "scratch")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-m", "oops, tracked a worktree")
        assert ".claude/worktrees/scratch" in _staged_modes(repo)
        _git(repo, "add", "-A")
        assert _drop_accidental_gitlinks() == [".claude/worktrees/scratch"]
        assert ".claude/worktrees/scratch" not in _staged_modes(repo)

    def test_a_worktree_anywhere_else_is_caught_too(self, repo):
        """.gitignore covers one path; the defect is the class, so the guard is not pathwise."""
        path = repo / "vendor/checkout"
        path.parent.mkdir(parents=True, exist_ok=True)
        _git(repo, "worktree", "add", "--detach", str(path), "HEAD")
        _git(repo, "add", "-A")
        assert _drop_accidental_gitlinks() == ["vendor/checkout"]

    def test_the_worktree_still_works_after_being_untracked(self, repo):
        """Untracking must not damage the sibling session that is using it."""
        path = _add_worktree(repo, "scratch")
        _git(repo, "add", "-A")
        _drop_accidental_gitlinks()
        assert path.exists()
        assert "scratch" in _git(repo, "worktree", "list")

    def test_a_clean_repo_is_a_no_op(self, repo):
        _git(repo, "add", "-A")
        assert _drop_accidental_gitlinks() == []


class TestRealSubmodulesAreNotFoughtWith:
    def test_the_guard_stands_down_when_gitmodules_exists(self, repo):
        """If submodules are ever adopted deliberately, this must not silently un-track them."""
        _add_worktree(repo, "scratch")
        (repo / ".gitmodules").write_text("", "utf-8")
        _git(repo, "add", "-A")
        assert _drop_accidental_gitlinks() == []
        assert ".claude/worktrees/scratch" in _staged_modes(repo)
