"""Regression tests for scripts/moneypath_precommit_guard.py (GAP 134).

Reproduces the measured 2026-08-26 02:02 UTC attack: the Dell-side hourly sync scp'd a stale
tree over desks/mt5 and ran `git add desks/mt5 && git commit` over ssh, laundering
marker-stripped money-path code into history (7cb174af). The guard must refuse the staged .py
in ssh context, let the legitimate state JSON land, and restore the worktree — and must block
marker-stripping staged changes in ANY context (the 2026-08-25 local-sibling overwrite class).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
GUARD_SRC = REPO_ROOT / "scripts" / "moneypath_precommit_guard.py"

MARKER = "d1_session_filtered"
PROTECTED_FIXTURE = f'''
PROTECTED = {{
    "desks/mt5/mt5desk/families.py": "{MARKER}",
}}
'''


def _git(repo: Path, *args: str, env: dict[str, str] | None = None,
         check: bool = True) -> subprocess.CompletedProcess[str]:
    r = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True,
                       env=env, timeout=60, check=False)
    if check and r.returncode != 0:
        raise AssertionError(f"git {args} failed rc={r.returncode}: {r.stderr}")
    return r


def _env(ssh: bool) -> dict[str, str]:
    env = dict(os.environ)
    env.pop("SSH_CONNECTION", None)
    env.pop("QUANT_ALLOW_SSH_PY", None)
    if ssh:
        env["SSH_CONNECTION"] = "203.0.113.1 55555 10.0.0.1 22"
    return env


@pytest.fixture()
def scratch_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "desks/mt5/mt5desk").mkdir(parents=True)
    (repo / "desks/mt5/data").mkdir(parents=True)
    (repo / "scripts").mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@test")
    _git(repo, "config", "user.name", "test")
    shutil.copy(GUARD_SRC, repo / "scripts" / "moneypath_precommit_guard.py")
    (repo / "scripts" / "check_moneypath_fence.py").write_text(PROTECTED_FIXTURE)
    (repo / "desks/mt5/mt5desk/families.py").write_text(
        f"def {MARKER}():\n    return 1\n")
    (repo / "desks/mt5/data/state.json").write_text('{"v": 1}\n')
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text(f"#!/bin/sh\nexec {sys.executable} scripts/moneypath_precommit_guard.py\n")
    hook.chmod(0o755)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base", env=_env(ssh=False))
    return repo


def _strip_marker(repo: Path) -> Path:
    f = repo / "desks/mt5/mt5desk/families.py"
    f.write_text(f.read_text().replace(MARKER, "TRAMPLED"))
    return f


def test_ssh_trample_refused_state_lands(scratch_repo: Path) -> None:
    """The measured attack: staged stale .py + legit JSON over ssh -> only the JSON commits."""
    _strip_marker(scratch_repo)
    (scratch_repo / "desks/mt5/data/state.json").write_text('{"v": 2}\n')
    _git(scratch_repo, "add", "--", "desks/mt5/mt5desk/families.py", "desks/mt5/data/state.json")
    _git(scratch_repo, "commit", "-q", "-m", "sync", env=_env(ssh=True), check=False)
    stat = _git(scratch_repo, "show", "--stat", "--format=", "HEAD").stdout
    assert "state.json" in stat
    assert "families.py" not in stat
    assert MARKER in (scratch_repo / "desks/mt5/mt5desk/families.py").read_text()


def test_local_marker_strip_restored(scratch_repo: Path) -> None:
    """Layer 2: a staged change that strips a marker HEAD carries is restored, any context."""
    _strip_marker(scratch_repo)
    _git(scratch_repo, "add", "--", "desks/mt5/mt5desk/families.py")
    _git(scratch_repo, "commit", "-q", "-m", "strip", env=_env(ssh=False), check=False)
    show = _git(scratch_repo, "show", "HEAD:desks/mt5/mt5desk/families.py", check=False)
    assert "TRAMPLED" not in show.stdout
    assert MARKER in (scratch_repo / "desks/mt5/mt5desk/families.py").read_text()


def test_legit_local_change_passes(scratch_repo: Path) -> None:
    f = scratch_repo / "desks/mt5/mt5desk/families.py"
    f.write_text(f.read_text() + "# legit\n")
    _git(scratch_repo, "add", "--", "desks/mt5/mt5desk/families.py")
    _git(scratch_repo, "commit", "-q", "-m", "legit", env=_env(ssh=False))
    assert "# legit" in _git(scratch_repo, "show", "HEAD:desks/mt5/mt5desk/families.py").stdout


def test_new_py_over_ssh_left_untracked(scratch_repo: Path) -> None:
    new = scratch_repo / "desks/mt5/newmod.py"
    new.write_text("print('stale')\n")
    _git(scratch_repo, "add", "--", "desks/mt5/newmod.py")
    _git(scratch_repo, "commit", "-q", "-m", "sync-new", env=_env(ssh=True), check=False)
    ls = _git(scratch_repo, "ls-files", "--", "desks/mt5/newmod.py").stdout.strip()
    assert ls == ""  # never entered history
    assert new.exists()  # bytes preserved for review


def test_ssh_override_env_allows_deliberate_py(scratch_repo: Path) -> None:
    f = scratch_repo / "desks/mt5/mt5desk/families.py"
    f.write_text(f.read_text() + "# deliberate\n")
    _git(scratch_repo, "add", "--", "desks/mt5/mt5desk/families.py")
    env = _env(ssh=True)
    env["QUANT_ALLOW_SSH_PY"] = "1"
    _git(scratch_repo, "commit", "-q", "-m", "principal-act", env=env)
    assert "# deliberate" in _git(scratch_repo, "show", "HEAD:desks/mt5/mt5desk/families.py").stdout
