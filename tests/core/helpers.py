"""Non-fixture test helpers (importable without conftest double-loading)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from libs.core.reproducibility import GitRunner

GIT_EXECUTABLE = shutil.which("git")
requires_git = pytest.mark.skipif(GIT_EXECUTABLE is None, reason="git executable not available")


class FakeGitRunnerFactory:
    """Builds canned git runners for tests that must not shell out to git."""

    def build(
        self,
        *,
        commit: str = "a" * 40,
        dirty: bool = False,
        branch: str = "main",
    ) -> GitRunner:
        def runner(args: list[str], cwd: Path) -> str:
            if args[:1] == ["rev-parse"] and "--abbrev-ref" in args:
                return branch
            if args[:1] == ["rev-parse"]:
                return commit
            if args[:1] == ["status"]:
                return " M file.txt" if dirty else ""
            raise AssertionError(f"unexpected git args: {args}")  # pragma: no cover

        return runner


def write_config_dir(directory: Path, *, base: str, env_name: str, env_yaml: str) -> Path:
    """Write a minimal ``base.yaml`` + ``<env>.yaml`` pair into ``directory``."""
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "base.yaml").write_text(base, encoding="utf-8")
    (directory / f"{env_name}.yaml").write_text(env_yaml, encoding="utf-8")
    return directory
