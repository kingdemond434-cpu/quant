"""R0412: a sibling MODIFYING a tracked file must not turn the desk-wide gate red -- and the
retraction must be PROVEN at HEAD, never inferred from modification.

MEASURED 2026-08-05: ruff reported three errors, all in ' M' files a concurrent session had
half-edited; `_inflight_py` (untracked-only) returned [], `_attribute` filed every failure as
committed-code, and ci-gate-red named a commit that was innocent. The widening is deliberately
asymmetric: a modified file joins the lint skip-scope, but the alarm is retracted only when
`git show HEAD:file` piped through the same ruff is POSITIVELY clean -- a failure that also
exists at HEAD is a committed failure whoever happens to be editing the file today, and a file
that cannot be shown at HEAD (fresh add) stays attributed to committed code, fail-safe.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import scripts.run_ci as ci


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=str(repo), check=True, capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@t")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "clean.py").write_text("X = 1\n", "utf-8")
    _git(tmp_path, "add", "scripts/clean.py")
    _git(tmp_path, "commit", "-qm", "clean")
    monkeypatch.setattr(ci, "_ROOT", tmp_path)
    return tmp_path


def test_modified_tracked_file_is_seen(repo: Path) -> None:
    """The exact 2026-08-05 blindness: ' M' files must enter the in-flight universe."""
    (repo / "scripts" / "clean.py").write_text("import os\nX = 1\n", "utf-8")
    assert ci._modified_tracked_py() == ["scripts/clean.py"]
    assert ci._inflight_py() == []          # untracked-only, unchanged -- the old blindness


def test_head_clean_version_is_proven_innocent(repo: Path) -> None:
    """Working copy red (F401), HEAD clean => the committed code is provably green."""
    (repo / "scripts" / "clean.py").write_text("import os\nX = 1\n", "utf-8")
    assert ci._lint_clean_at_head("scripts/clean.py") is True


def test_head_red_version_is_never_retracted(repo: Path) -> None:
    """A failure that also exists at HEAD is a committed failure, whoever is editing today."""
    (repo / "scripts" / "clean.py").write_text("import os\nX = 1\n", "utf-8")
    _git(repo, "add", "scripts/clean.py")
    _git(repo, "commit", "-qm", "ship the lint error")
    (repo / "scripts" / "clean.py").write_text("import sys\nX = 1\n", "utf-8")
    assert ci._lint_clean_at_head("scripts/clean.py") is False


def test_fresh_add_cannot_be_proven(repo: Path) -> None:
    """A staged new file has no HEAD version to prove; the alarm stands (fail-safe)."""
    (repo / "scripts" / "new.py").write_text("X = 1\n", "utf-8")
    _git(repo, "add", "scripts/new.py")
    assert "scripts/new.py" in ci._modified_tracked_py()
    assert ci._lint_clean_at_head("scripts/new.py") is False
