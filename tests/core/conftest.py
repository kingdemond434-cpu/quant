"""Shared fixtures for the core test suite."""

from __future__ import annotations

import logging
import os
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest
from tests.core.helpers import GIT_EXECUTABLE, FakeGitRunnerFactory


@pytest.fixture(autouse=True)
def _clean_qp_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove platform environment variables so tests are hermetic."""
    for key in list(os.environ):
        if key.startswith("QP_"):
            monkeypatch.delenv(key, raising=False)


@pytest.fixture(autouse=True)
def _reset_settings_cache() -> Iterator[None]:
    from libs.core.config import clear_settings_cache

    clear_settings_cache()
    yield
    clear_settings_cache()


@pytest.fixture(autouse=True)
def _restore_root_logger() -> Iterator[None]:
    """Snapshot and restore the root logger so logging tests don't leak handlers."""
    root = logging.getLogger()
    saved_handlers = list(root.handlers)
    saved_level = root.level
    yield
    for handler in list(root.handlers):
        if handler not in saved_handlers:
            root.removeHandler(handler)
    for handler in saved_handlers:
        if handler not in root.handlers:
            root.addHandler(handler)
    root.setLevel(saved_level)


def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True)


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Create a temporary git repository with one commit on branch ``main``."""
    if GIT_EXECUTABLE is None:  # pragma: no cover - guarded by requires_git on callers
        pytest.skip("git executable not available")
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(["init", "-b", "main"], repo)
    _git(["config", "user.email", "test@example.com"], repo)
    _git(["config", "user.name", "Test"], repo)
    _git(["config", "commit.gpgsign", "false"], repo)
    (repo / "file.txt").write_text("initial\n", encoding="utf-8")
    _git(["add", "."], repo)
    _git(["commit", "-m", "initial"], repo)
    return repo


@pytest.fixture
def fake_git_runner() -> FakeGitRunnerFactory:
    """Return a factory that builds a deterministic, git-free git runner."""
    return FakeGitRunnerFactory()
