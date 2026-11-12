"""Idea 624: the seal names the ORIGIN commit the box adopted, and whether the code matches it."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from libs.ops import release

ROOT = Path(__file__).resolve().parents[2]


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True,
                          text=True).stdout.strip()  # fmt: skip


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@t")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "libs").mkdir()
    (tmp_path / "libs" / "a.py").write_text("x = 1\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "origin")
    return tmp_path


def test_unset_says_it_is_not_an_adoption(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(release.ADOPTED_ORIGIN_ENV, raising=False)
    got = release.adopted_origin(_git(repo, "rev-parse", "HEAD"), repo)
    assert got["adopted_origin_sha"] is None and got["adopted_origin_code_match"] is None
    assert "unset" in got["adopted_origin_why"]


def test_a_box_state_commit_on_top_still_matches(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    origin = _git(repo, "rev-parse", "HEAD")
    (repo / "state.json").write_text("{}\n")  # box state: not a code root
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "box state")
    monkeypatch.setenv(release.ADOPTED_ORIGIN_ENV, origin[:12])
    got = release.adopted_origin(_git(repo, "rev-parse", "HEAD"), repo)
    assert got["adopted_origin_sha"] == origin  # resolved to the full sha
    assert got["adopted_origin_code_match"] is True


def test_a_code_difference_is_named(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    origin = _git(repo, "rev-parse", "HEAD")
    (repo / "libs" / "a.py").write_text("x = 2\n")
    _git(repo, "commit", "-qam", "box-local code")
    monkeypatch.setenv(release.ADOPTED_ORIGIN_ENV, origin)
    got = release.adopted_origin(_git(repo, "rev-parse", "HEAD"), repo)
    assert got["adopted_origin_code_match"] is False


def test_an_unknown_commit_is_unmeasured(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(release.ADOPTED_ORIGIN_ENV, "f" * 40)
    got = release.adopted_origin(_git(repo, "rev-parse", "HEAD"), repo)
    assert got["adopted_origin_sha"] == "f" * 40 and got["adopted_origin_code_match"] is None


def test_seal_records_it_and_adopt_and_seal_names_the_gate_target() -> None:
    src = (ROOT / "libs/ops/release.py").read_text(encoding="utf-8")
    assert "doc.update(adopted_origin(head, r))" in src
    ps = (ROOT / "desks/mt5/scripts/Adopt-And-Seal.ps1").read_text(encoding="utf-8")
    seal = ps.index("release.seal(by='Adopt-And-Seal')")
    assert ps.index("$env:QUANT_ADOPTED_ORIGIN_SHA = [string]$gateTarget") < seal
    assert ps.index("Remove-Item Env:\\QUANT_ADOPTED_ORIGIN_SHA") > seal
