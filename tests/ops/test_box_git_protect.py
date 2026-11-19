"""The box repo's branch protection: GitHub's rules, enforced by the repo's own pre-receive hook."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ops.box_git import protect as P  # noqa: E402

LIVE = f"refs/heads/{P.LIVE_BRANCH}"
A, B = "a" * 40, "b" * 40


def ff(_a: str, _b: str) -> bool:
    return True


def rewrite(_a: str, _b: str) -> bool:
    return False


@pytest.mark.parametrize("ref", [LIVE, "refs/heads/production", "refs/heads/master"])
def test_a_thread_can_never_move_a_protected_branch(ref: str) -> None:
    v = P.decide(A, B, ref, "thread", ff)
    assert not v.ok and "only the box merge gate" in v.why


def test_the_live_branch_is_protected_although_its_name_starts_with_claude() -> None:
    assert LIVE.startswith(P.WORK_PREFIX)
    assert not P.decide(P.ZERO, B, LIVE, "thread", ff).ok


def test_even_the_gate_cannot_rewrite_live() -> None:
    assert P.decide(A, B, LIVE, "gate", ff).ok
    v = P.decide(A, B, LIVE, "gate", rewrite)
    assert not v.ok and "fast-forward" in v.why


def test_threads_push_work_branches_but_never_force() -> None:
    assert P.decide(P.ZERO, B, "refs/heads/claude/x", "thread", ff).ok
    assert P.decide(A, B, "refs/heads/claude/x", "thread", ff).ok
    assert not P.decide(A, B, "refs/heads/claude/x", "thread", rewrite).ok


def test_nothing_is_ever_deleted() -> None:
    for role in P.ROLES:
        assert not P.decide(A, P.ZERO, "refs/heads/claude/x", role, ff).ok


def test_release_tags_are_the_authoritys_and_write_once() -> None:
    tag = "refs/tags/release/20261119T000000Z-abcdef012345"
    assert not P.decide(P.ZERO, B, tag, "thread", ff).ok
    assert not P.decide(P.ZERO, B, tag, "gate", ff).ok
    assert P.decide(P.ZERO, B, tag, "authority", ff).ok
    assert not P.decide(A, B, tag, "authority", ff).ok


def test_unknown_refs_and_roles_get_the_least_authority() -> None:
    assert not P.decide(P.ZERO, B, "refs/heads/main", "thread", ff).ok
    assert not P.decide(P.ZERO, B, "refs/notes/x", "gate", ff).ok
    assert P.role_from_env({P.ROLE_ENV: "admin"}) == "thread"
    assert P.role_from_env({}) == "thread"
    assert P.role_from_env({P.ROLE_ENV: "GATE"}) == "gate"


def test_one_refused_update_refuses_the_whole_push() -> None:
    lines = [f"{P.ZERO} {B} refs/heads/claude/ok\n", f"{A} {B} {LIVE}\n"]
    assert P.main(lines, {}) == 1
    assert P.main([f"{P.ZERO} {B} refs/heads/claude/ok\n"], {}) == 0


# ------------------------------------------------------------- end to end, a real bare repo
def _git(cwd: Path, *args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    e = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
         "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t", **(env or {})}
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, env=e,
                          check=False)


@pytest.mark.skipif(os.name == "nt", reason="the hook shim is a POSIX script in this test")
def test_the_hook_refuses_a_force_push_to_live_in_a_real_repo(tmp_path: Path) -> None:
    bare = tmp_path / "origin.git"
    _git(tmp_path, "init", "-q", "--bare", str(bare))
    hook = bare / "hooks" / "pre-receive"
    hook.write_text(f"#!/bin/sh\nPYTHONPATH={ROOT} exec {sys.executable} -m ops.box_git.protect\n")
    hook.chmod(0o755)
    work = tmp_path / "w"
    _git(tmp_path, "init", "-q", str(work))
    (work / "f").write_text("1")
    _git(work, "add", "f")
    _git(work, "commit", "-qm", "one")
    gate = {P.ROLE_ENV: "gate"}
    assert _git(work, "push", str(bare), f"HEAD:{LIVE}", env=gate).returncode == 0
    assert _git(work, "push", str(bare), "HEAD:refs/heads/claude/w").returncode == 0
    r = _git(work, "push", str(bare), f"HEAD:{LIVE}")
    assert r.returncode == 0  # nothing to update is not a refusal
    (work / "f").write_text("2")
    _git(work, "commit", "-qam", "two")
    r = _git(work, "push", str(bare), f"HEAD:{LIVE}")
    assert r.returncode != 0 and "only the box merge gate" in r.stderr
    assert _git(work, "push", str(bare), "HEAD:refs/heads/claude/w").returncode == 0
    _git(work, "reset", "-q", "--hard", "HEAD~1")
    (work / "f").write_text("3")
    _git(work, "commit", "-qam", "three")
    r = _git(work, "push", "-f", str(bare), "HEAD:refs/heads/claude/w")
    assert r.returncode != 0 and "no force push" in r.stderr
