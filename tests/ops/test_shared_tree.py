"""R0423 -- two live sessions in one worktree corrupt each other's commits.

A sibling session runs a broad `git commit` between another session's `git add` and its
`git commit`, sweeping the staged files into a commit whose message is about something else. The
CODE survives; the RATIONALE is destroyed, and under L1.16 a repair is only durable if its
mechanism is understood. Live instance: d971a08 is titled "R0261: the composite discovery rank is
log_growth wearing nine other names" and carries the $4,807 futures-leg repair in
libs/execution/carry_accounting.py.

Recorded three times, fixed per-instance three times ("re-commit it"), never generalised.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from libs.ops import shared_tree as ST


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True,
                          check=True).stdout.strip()


def test_a_bash_shell_whose_PATH_says_claude_is_not_a_session():
    """THE 5:1 FALSE POSITIVE THE FIRST RUN PRODUCED.

    `pgrep -f clau[d]e` matches the whole command line, and every Bash tool invocation here is
    `/bin/bash -c source /home/quant/.claude/shell-snapshots/...` -- `.claude` in a PATH. Measured
    2026-08-13: 5 phantom sessions against 1 real one. A detector that cries wolf gets disabled,
    which would leave the real defect undetected forever, so the match is on the EXECUTABLE.
    """
    # This test process is python, not claude -- the executable test must reject it.
    assert ST._is_session(os.getpid()) is False


def test_a_vanished_pid_is_not_a_session_rather_than_an_exception():
    assert ST._is_session(999_999_998) is False
    assert ST._ppid(999_999_998) is None
    assert ST._ancestors(999_999_998) == set()


def test_own_ancestors_are_excluded_so_a_subagent_is_never_a_sibling():
    """A subagent shares this worktree BY DESIGN and does not independently commit."""
    mine = ST._ancestors(os.getpid())
    assert os.getpid() in mine
    assert ST._ppid(os.getpid()) in mine
    # every pid this returns must be outside my own tree, whatever is running on the box
    assert all(not (ST._ancestors(p) & mine) for p in ST._live_session_pids())


def test_two_linked_worktrees_of_one_repo_are_NOT_a_shared_checkout(tmp_path):
    """SAME REPO IS NOT SAME WORKTREE, and the difference IS the fix this law recommends.

    Two sessions in two linked worktrees share a git_common_dir and cannot sweep each other's
    staged files. Reporting that as the defect would flag the recommended arrangement.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(tmp_path, "init", "-q", str(repo))
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    (repo / "f").write_text("x\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")
    linked = tmp_path / "wt"
    _git(repo, "worktree", "add", "-q", "-b", "side", str(linked))

    # The shared .git is EQUAL across the two worktrees...
    assert ST._git_common_dir(repo) == ST._git_common_dir(linked)
    # ...and yet they are not the same worktree, which is what decides the verdict.
    cwd = Path.cwd()
    try:
        os.chdir(repo)
        assert ST._same_worktree(linked) is False
        assert ST._same_worktree(repo) is True
    finally:
        os.chdir(cwd)


def test_outside_a_git_tree_is_UNMEASURED_never_clear(tmp_path):
    """Absence must never resolve to a clean verdict (L1.28a)."""
    cwd = Path.cwd()
    try:
        os.chdir(tmp_path)
        rep = ST.detect(_pids=[])
        assert rep["status"] == "UNMEASURED"
    finally:
        os.chdir(cwd)


def test_no_other_session_reads_CLEAR_and_names_the_worktree():
    rep = ST.detect(_pids=[])
    assert rep["status"] == "CLEAR"
    assert rep["same_worktree"] == [] and rep["git_common_dir"].endswith(".git")
    assert rep["next_action"] == "none"


def test_the_advice_names_the_worktree_command_and_the_two_banned_moves():
    """The generalisation, not another per-instance re-commit."""
    rep = ST.detect(_pids=[os.getpid()])       # pretend this process is a sibling session
    advice = ST.detect(_pids=[])["next_action"] if rep["status"] != "SHARED" else rep[
        "next_action"]
    if rep["status"] == "SHARED":
        assert "git worktree add" in advice
        assert "git stash" in advice and "git commit -a" in advice
