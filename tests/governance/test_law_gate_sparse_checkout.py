"""A HEAD law verdict covers the full tree even from a sparse source checkout."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from scripts.run_law_gate import _at_head


@pytest.mark.parametrize("dirty", [True, False])
def test_sparse_caller_does_not_remove_committed_fence_inputs(tmp_path: Path,
                                                           dirty: bool) -> None:
    def git(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=tmp_path, capture_output=True,
                              text=True, check=True).stdout

    git("init", "-q")
    git("config", "user.email", "test@example.invalid")
    git("config", "user.name", "test")
    for name in ("source", "policy"):
        (tmp_path / name).mkdir()
    (tmp_path / "source" / "code.txt").write_text("committed", encoding="utf-8")
    (tmp_path / "policy" / "seal.txt").write_text("sealed", encoding="utf-8")
    git("add", "-A")
    git("commit", "-qm", "fixture")
    git("sparse-checkout", "set", "source")
    if dirty:
        (tmp_path / "source" / "code.txt").write_text("dirty", encoding="utf-8")
    assert not (tmp_path / "policy" / "seal.txt").exists()
    where, subject, errors = _at_head(tmp_path)
    try:
        assert errors == [] and "HEAD" in subject
        assert (where / "policy" / "seal.txt").read_text("utf-8") == "sealed"
        assert (where / "source" / "code.txt").read_text("utf-8") == "committed"
        assert not (tmp_path / "policy" / "seal.txt").exists()
        assert git("sparse-checkout", "list").strip() == "source"
    finally:
        git("worktree", "remove", "--force", str(where))
