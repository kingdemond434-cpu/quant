"""Tests for the reproducibility framework."""

from __future__ import annotations

import os
import random
from pathlib import Path

import pytest
from pydantic import ValidationError
from tests.core.helpers import requires_git

from libs.core.config import hash_config
from libs.core.errors import GitError, ReproducibilityError
from libs.core.reproducibility import (
    GitInfo,
    ReproducibilityStamp,
    VerificationResult,
    create_reproducibility_stamp,
    get_git_info,
    seed_everything,
    verify_reproducibility,
)
from libs.core.time import is_utc

CLEAN = GitInfo(commit="c" * 40, dirty=False, branch="main")
DIRTY = GitInfo(commit="c" * 40, dirty=True, branch="main")
OTHER = GitInfo(commit="d" * 40, dirty=False, branch="main")


# --------------------------------------------------------------------------- seeding


def test_seed_everything_is_deterministic_for_random() -> None:
    seed_everything(42)
    first = [random.random() for _ in range(5)]
    seed_everything(42)
    second = [random.random() for _ in range(5)]
    assert first == second


def test_seed_everything_is_deterministic_for_numpy() -> None:
    np = pytest.importorskip("numpy")
    seed_everything(7)
    first = np.random.rand(5).tolist()
    seed_everything(7)
    second = np.random.rand(5).tolist()
    assert first == second


def test_seed_everything_sets_pythonhashseed() -> None:
    seed_everything(123)
    assert os.environ["PYTHONHASHSEED"] == "123"


def test_seed_everything_rejects_negative() -> None:
    with pytest.raises(ValueError):
        seed_everything(-1)


# --------------------------------------------------------------------------- git info


def test_get_git_info_with_fake_runner(fake_git_runner) -> None:
    runner = fake_git_runner.build(commit="b" * 40, dirty=True, branch="feature")
    info = get_git_info(Path("/does/not/matter"), runner=runner)
    assert info.commit == "b" * 40
    assert info.dirty is True
    assert info.branch == "feature"


@requires_git
def test_get_git_info_real_repo(git_repo: Path) -> None:
    info = get_git_info(git_repo)
    assert len(info.commit) == 40
    int(info.commit, 16)
    assert info.dirty is False
    assert info.branch == "main"


@requires_git
def test_get_git_info_detects_dirty(git_repo: Path) -> None:
    (git_repo / "file.txt").write_text("changed\n", encoding="utf-8")
    assert get_git_info(git_repo).dirty is True


@requires_git
def test_get_git_info_non_repo_raises(tmp_path: Path) -> None:
    with pytest.raises(GitError):
        get_git_info(tmp_path)


# --------------------------------------------------------------------------- stamp creation


def test_create_stamp_records_all_five_facts() -> None:
    config = {"alpha": "trend", "lookback": 50}
    stamp = create_reproducibility_stamp(
        config, "snap_001", seed=123, git_info=CLEAN, set_seed=False
    )
    assert stamp.git_commit == "c" * 40        # git hash
    assert is_utc(stamp.created_at)            # timestamp (UTC)
    assert stamp.seed == 123                   # random seed
    assert stamp.config_hash == hash_config(config)  # config hash
    assert stamp.snapshot_id == "snap_001"     # snapshot id
    assert stamp.git_dirty is False
    assert stamp.git_branch == "main"
    assert stamp.python_version
    assert stamp.platform
    assert stamp.stamp_id.startswith("stamp_")


def test_create_stamp_requires_snapshot_id() -> None:
    with pytest.raises(ReproducibilityError):
        create_reproducibility_stamp({"a": 1}, "", git_info=CLEAN, set_seed=False)


def test_create_stamp_require_clean_git_rejects_dirty() -> None:
    with pytest.raises(ReproducibilityError):
        create_reproducibility_stamp(
            {"a": 1}, "snap", git_info=DIRTY, require_clean_git=True, set_seed=False
        )


def test_create_stamp_generates_seed_when_absent() -> None:
    stamp = create_reproducibility_stamp({"a": 1}, "snap", git_info=CLEAN, set_seed=False)
    assert isinstance(stamp.seed, int)
    assert stamp.seed >= 0


def test_create_stamp_set_seed_actually_seeds() -> None:
    create_reproducibility_stamp({"a": 1}, "snap", seed=99, git_info=CLEAN, set_seed=True)
    seeded_sequence = [random.random() for _ in range(3)]
    seed_everything(99)
    assert seeded_sequence == [random.random() for _ in range(3)]


def test_create_stamp_missing_git_raises_reproducibility_error(fake_git_runner) -> None:
    def boom(args: list[str], cwd: Path) -> str:
        raise GitError("no repo")

    with pytest.raises(ReproducibilityError):
        create_reproducibility_stamp({"a": 1}, "snap", runner=boom, set_seed=False)


def test_stamp_is_immutable() -> None:
    stamp = create_reproducibility_stamp({"a": 1}, "snap", git_info=CLEAN, set_seed=False)
    with pytest.raises(ValidationError):
        stamp.seed = 5  # type: ignore[misc]


# --------------------------------------------------------------------------- verification


def _stamp(config: object) -> ReproducibilityStamp:
    return create_reproducibility_stamp(config, "snap", seed=1, git_info=CLEAN, set_seed=False)


def test_verify_passes_when_everything_matches() -> None:
    stamp = _stamp({"a": 1})
    result = verify_reproducibility(
        stamp, config={"a": 1}, snapshot_id="snap", git_info=CLEAN, require_clean=True
    )
    assert isinstance(result, VerificationResult)
    assert result.ok
    assert bool(result) is True
    assert result.mismatches == []


def test_verify_detects_commit_mismatch() -> None:
    stamp = _stamp({"a": 1})
    result = verify_reproducibility(stamp, git_info=OTHER)
    assert not result.ok
    assert any("commit" in m for m in result.mismatches)


def test_verify_detects_dirty_tree() -> None:
    stamp = _stamp({"a": 1})
    result = verify_reproducibility(stamp, git_info=DIRTY, require_clean=True)
    assert not result.ok
    assert any("dirty" in m for m in result.mismatches)


def test_verify_allows_dirty_when_not_required() -> None:
    stamp = _stamp({"a": 1})
    result = verify_reproducibility(stamp, git_info=DIRTY, require_clean=False)
    assert result.ok


def test_verify_detects_config_change() -> None:
    stamp = _stamp({"a": 1})
    result = verify_reproducibility(stamp, config={"a": 2}, git_info=CLEAN)
    assert not result.ok
    assert any("config" in m for m in result.mismatches)


def test_verify_detects_snapshot_mismatch() -> None:
    stamp = _stamp({"a": 1})
    result = verify_reproducibility(stamp, snapshot_id="other", git_info=CLEAN)
    assert not result.ok
    assert any("snapshot" in m for m in result.mismatches)


def test_verify_strict_raises_on_mismatch() -> None:
    stamp = _stamp({"a": 1})
    with pytest.raises(ReproducibilityError):
        verify_reproducibility(stamp, git_info=OTHER, strict=True)


def test_verify_missing_git_raises_reproducibility_error() -> None:
    stamp = _stamp({"a": 1})

    def boom(args: list[str], cwd: Path) -> str:
        raise GitError("no repo")

    with pytest.raises(ReproducibilityError):
        verify_reproducibility(stamp, runner=boom)


# --------------------------------------------------------------------------- integration


@requires_git
def test_create_then_verify_against_real_repo(git_repo: Path) -> None:
    config = {"strategy": "gold_session", "window": 20}
    stamp = create_reproducibility_stamp(
        config, "snap_real", seed=5, repo_path=git_repo, set_seed=False
    )
    result = verify_reproducibility(
        stamp, config=config, snapshot_id="snap_real", repo_path=git_repo, require_clean=True
    )
    assert result.ok


@requires_git
def test_verify_real_repo_detects_config_drift(git_repo: Path) -> None:
    stamp = create_reproducibility_stamp(
        {"window": 20}, "snap_real", seed=5, repo_path=git_repo, set_seed=False
    )
    result = verify_reproducibility(stamp, config={"window": 21}, repo_path=git_repo)
    assert not result.ok
