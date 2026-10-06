"""The fence must heal a replayed snapshot and NEVER touch somebody's live edit.

MEASURED 2026-08-27: `docs/GAP_REGISTER.md` was reverted byte-for-byte to a 02:45 blob roughly
every two minutes while this cycle wrote gap rows. The commit the replayer restores is itself
titled "restore rows 146-150", so an earlier session lost the same rows the same way.
"""
from __future__ import annotations

import importlib.util
import subprocess
from functools import partial
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load(root: Path):
    spec = importlib.util.spec_from_file_location(
        "_drf", ROOT / "scripts" / "check_doc_replay_fence.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.ROOT = root
    mod.OUT = root / "fence.json"
    mod.LOG = root / "fence.log"
    # This fixture has its own Git index. Keep real locking, without contending
    # for the live desk's machine-wide Windows writer mutex.
    mod.git_writer_lock = partial(mod.git_writer_lock, mechanism="file")
    return mod


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.email", "t@t")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "docs").mkdir()
    doc = tmp_path / "docs" / "GAP_REGISTER.md"
    doc.write_text("row 1\n", encoding="utf-8")
    _git(tmp_path, "add", "docs/GAP_REGISTER.md")
    _git(tmp_path, "commit", "-qm", "old snapshot")
    doc.write_text("row 1\nrow 2\n", encoding="utf-8")
    _git(tmp_path, "add", "docs/GAP_REGISTER.md")
    _git(tmp_path, "commit", "-qm", "current")
    return tmp_path


def test_a_replayed_old_snapshot_is_healed(repo: Path) -> None:
    doc = repo / "docs" / "GAP_REGISTER.md"
    doc.write_text("row 1\n", encoding="utf-8")          # exactly the OLD blob -> a replay
    mod = _load(repo)
    # A SUCCESSFUL HEAL IS SUCCESS. Non-zero here would park the unit permanently in `failed`,
    # and a unit that is always failed is a unit nobody reads.
    assert mod.main() == 0
    assert doc.read_text(encoding="utf-8") == "row 1\nrow 2\n", "the register was not restored"
    import json
    art = json.loads((repo / "fence.json").read_text(encoding="utf-8"))
    assert art["status"] == "HEALED"
    assert art["healed"][0]["outcome"] == "HEALED"


def test_a_genuine_edit_is_never_touched(repo: Path) -> None:
    """The whole point: a fence that eats live edits is worse than the defect it heals."""
    doc = repo / "docs" / "GAP_REGISTER.md"
    doc.write_text("row 1\nrow 2\nrow 3 written right now\n", encoding="utf-8")
    mod = _load(repo)
    assert mod.main() == 0
    assert "row 3 written right now" in doc.read_text(encoding="utf-8")


def test_a_clean_file_is_reported_clean(repo: Path) -> None:
    mod = _load(repo)
    assert mod.main() == 0
    import json
    doc = json.loads((repo / "fence.json").read_text(encoding="utf-8"))
    assert doc["status"] == "OK"
    assert "docs/GAP_REGISTER.md" in doc["clean"]


def test_the_finding_names_the_commit_that_was_replayed(repo: Path) -> None:
    """'It reverted' is not actionable; 'it reverted to THIS commit' names the replayer's copy."""
    (repo / "docs" / "GAP_REGISTER.md").write_text("row 1\n", encoding="utf-8")
    mod = _load(repo)
    finding = mod.check("docs/GAP_REGISTER.md")
    assert finding is not None
    assert finding["subject"] == "old snapshot"
    assert len(finding["replayed_from"]) == 40


def test_contended_fixture_lock_cannot_report_a_successful_heal(repo: Path, monkeypatch) -> None:
    import json

    from libs.ops.git_writer_lock import git_writer_lock

    doc = repo / "docs" / "GAP_REGISTER.md"
    doc.write_text("row 1\n", encoding="utf-8")
    mod = _load(repo)
    production_timeouts = []

    def bounded_fixture_lock(root, *, timeout_s):
        production_timeouts.append(timeout_s)
        return git_writer_lock(root, timeout_s=0.01, mechanism="file")

    with git_writer_lock(repo, timeout_s=0.01, mechanism="file") as owner:
        assert owner.held
        with monkeypatch.context() as patch:
            patch.setattr(mod, "git_writer_lock", bounded_fixture_lock)
            assert mod.main() == 1
        assert doc.read_text(encoding="utf-8") == "row 1\n"
        assert json.loads(mod.OUT.read_text(encoding="utf-8"))["status"] == "HEAL_FAILED"
        log = mod.LOG.read_text(encoding="utf-8")
        assert "REPLAY HEAL FAILED" in log
        assert "REPLAY HEALED" not in log
        assert "not restored from HEAD" in log
        assert production_timeouts == [120.0]
    assert mod.main() == 0
    assert doc.read_text(encoding="utf-8") == "row 1\nrow 2\n"
