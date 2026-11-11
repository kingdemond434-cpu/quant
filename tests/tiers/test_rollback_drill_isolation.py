"""The rollback drill acts on its own sandbox and nothing else, whatever GIT_* the caller set.

Audit 2026-10-07: with GIT_DIR / GIT_WORK_TREE / GIT_INDEX_FILE inherited, the drill rewrote a
victim repository's hooksPath (the moneypath guard), identity, signing and index, and still
read PASS. The victim here carries all three variables and must come out byte-identical.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from libs.tiers import rollback


def _git(cwd: Path, *a: str) -> str:
    return subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True,
                          text=True).stdout.strip()


def test_a_victim_repo_named_by_git_env_is_never_touched(tmp_path: Path,
                                                         monkeypatch: pytest.MonkeyPatch) -> None:
    victim = tmp_path / "victim"
    victim.mkdir()
    _git(victim, "init", "-q")
    _git(victim, "config", "core.hooksPath", "ops/githooks")
    _git(victim, "config", "user.email", "owner@example")
    _git(victim, "config", "user.name", "owner")
    (victim / "a.txt").write_text("x\n", "utf-8")
    _git(victim, "add", "a.txt")
    config = (victim / ".git" / "config").read_bytes()
    index = (victim / ".git" / "index").read_bytes()
    monkeypatch.setenv("GIT_DIR", str(victim / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(victim))
    monkeypatch.setenv("GIT_INDEX_FILE", str(victim / ".git" / "index"))
    d = rollback.drill()
    assert d["status"] == "PASS", d
    assert (victim / ".git" / "config").read_bytes() == config
    assert (victim / ".git" / "index").read_bytes() == index
    monkeypatch.delenv("GIT_DIR")
    monkeypatch.delenv("GIT_WORK_TREE")
    monkeypatch.delenv("GIT_INDEX_FILE")
    assert subprocess.run(["git", "rev-parse", "--verify", "HEAD"], cwd=victim,
                          capture_output=True).returncode != 0, "the victim gained a commit"


def test_the_sandbox_env_carries_no_git_variable(tmp_path: Path,
                                                 monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_DIR", "/elsewhere/.git")
    monkeypatch.setenv("git_work_tree", "/elsewhere")
    env = rollback._sandbox_env(tmp_path)
    assert not [k for k in env if k.upper().startswith("GIT_") and k != "GIT_CEILING_DIRECTORIES"]
    assert env["GIT_CEILING_DIRECTORIES"] == str(tmp_path.parent)
