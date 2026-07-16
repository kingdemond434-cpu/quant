"""Reproducibility framework.

Reproducibility is the product: an unreproducible result is not evidence. Every research
run binds five things — a **git commit**, a **UTC timestamp**, a **random seed**, a
**config hash**, and a **data-snapshot id** — into a :class:`ReproducibilityStamp`.
:func:`verify_reproducibility` later re-derives those facts and reports any drift, so a
result can be challenged months after the fact.
"""

from __future__ import annotations

import os
import platform as platform_module
import random
import subprocess
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

from libs.core.config import find_project_root, hash_config
from libs.core.errors import GitError, ReproducibilityError
from libs.core.ids import new_stamp_id
from libs.core.time import ensure_utc, utcnow

# A git command runner: takes (args, cwd) and returns trimmed stdout. Injectable for tests.
GitRunner = Callable[[list[str], Path], str]

_UINT32 = 2**32


# --------------------------------------------------------------------------- git


def _default_git_runner(args: list[str], cwd: Path) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:  # git not installed
        raise GitError("git executable not found on PATH") from exc
    if result.returncode != 0:
        raise GitError(
            f"git {' '.join(args)} failed (exit {result.returncode}): {result.stderr.strip()}"
        )
    return result.stdout.strip()


class GitInfo(BaseModel):
    """A point-in-time snapshot of the working tree's git state."""

    model_config = ConfigDict(frozen=True)

    commit: str
    dirty: bool
    branch: str | None = None


def get_git_info(repo_path: Path | None = None, *, runner: GitRunner | None = None) -> GitInfo:
    """Return the current git commit, dirty flag, and branch.

    Raises:
        GitError: if the path is not a git repository, has no commits, or git is missing.
    """
    cwd = Path(repo_path) if repo_path is not None else find_project_root()
    run = runner or _default_git_runner
    commit = run(["rev-parse", "HEAD"], cwd)
    if not commit:
        raise GitError(f"no commits found in repository at {cwd}")
    porcelain = run(["status", "--porcelain"], cwd)
    try:
        branch: str | None = run(["rev-parse", "--abbrev-ref", "HEAD"], cwd)
    except GitError:
        branch = None
    return GitInfo(commit=commit, dirty=bool(porcelain.strip()), branch=branch)


# --------------------------------------------------------------------------- seeding


def seed_everything(seed: int) -> int:
    """Seed all relevant RNGs deterministically and return the seed.

    Seeds the stdlib ``random`` module, NumPy (if installed), and sets ``PYTHONHASHSEED``
    for any child processes spawned afterwards.
    """
    if seed < 0:
        raise ValueError("seed must be non-negative")
    os.environ["PYTHONHASHSEED"] = str(seed)
    random.seed(seed)
    try:
        import numpy as np

        np.random.seed(seed % _UINT32)
    except ImportError:  # pragma: no cover - numpy is a declared dependency
        pass
    return seed


def _generate_seed() -> int:
    """Generate a fresh, recordable seed when the caller did not supply one."""
    return random.SystemRandom().randint(0, 2**31 - 1)


# --------------------------------------------------------------------------- stamp


class ReproducibilityStamp(BaseModel):
    """An immutable record binding code + data + config + seed + time for one run."""

    model_config = ConfigDict(frozen=True)

    stamp_id: str
    created_at: Any  # datetime; validated to UTC below
    git_commit: str
    git_dirty: bool
    git_branch: str | None
    seed: int
    config_hash: str
    snapshot_id: str
    python_version: str
    platform: str

    @field_validator("created_at")
    @classmethod
    def _created_at_utc(cls, value: Any) -> Any:
        return ensure_utc(value)


def create_reproducibility_stamp(
    config: Mapping[str, Any] | BaseModel | None,
    snapshot_id: str,
    *,
    seed: int | None = None,
    repo_path: Path | None = None,
    set_seed: bool = True,
    require_clean_git: bool = False,
    runner: GitRunner | None = None,
    git_info: GitInfo | None = None,
) -> ReproducibilityStamp:
    """Create a reproducibility stamp and (optionally) seed the RNGs.

    Args:
        config: the configuration object whose hash is recorded.
        snapshot_id: the immutable data-snapshot id the run reads from.
        seed: the random seed; a fresh recordable seed is generated when ``None``.
        repo_path: repository to read git state from (defaults to the project root).
        set_seed: when ``True``, seed all RNGs with the resolved seed.
        require_clean_git: when ``True``, refuse to stamp a dirty working tree.
        runner: injectable git runner (for testing).
        git_info: pre-fetched git state (bypasses ``runner``/``repo_path``).

    Raises:
        ReproducibilityError: if ``require_clean_git`` is set and the tree is dirty,
            or git state cannot be obtained.
    """
    if not snapshot_id:
        raise ReproducibilityError("snapshot_id is required for a reproducibility stamp")

    try:
        info = git_info or get_git_info(repo_path, runner=runner)
    except GitError as exc:
        raise ReproducibilityError(f"cannot stamp without git state: {exc}") from exc

    if require_clean_git and info.dirty:
        raise ReproducibilityError(
            "working tree is dirty; commit or stash before creating a reproducibility stamp"
        )

    resolved_seed = _generate_seed() if seed is None else seed
    if resolved_seed < 0:
        raise ReproducibilityError("seed must be non-negative")
    if set_seed:
        seed_everything(resolved_seed)

    return ReproducibilityStamp(
        stamp_id=new_stamp_id(),
        created_at=utcnow(),
        git_commit=info.commit,
        git_dirty=info.dirty,
        git_branch=info.branch,
        seed=resolved_seed,
        config_hash=hash_config(config),
        snapshot_id=snapshot_id,
        python_version=platform_module.python_version(),
        platform=platform_module.platform(),
    )


class VerificationResult(BaseModel):
    """The outcome of verifying a stamp against the current environment."""

    model_config = ConfigDict(frozen=True)

    ok: bool
    mismatches: list[str]
    current_commit: str
    current_dirty: bool

    def __bool__(self) -> bool:
        return self.ok


def verify_reproducibility(
    stamp: ReproducibilityStamp,
    *,
    config: Mapping[str, Any] | BaseModel | None = None,
    snapshot_id: str | None = None,
    repo_path: Path | None = None,
    require_clean: bool = True,
    strict: bool = False,
    runner: GitRunner | None = None,
    git_info: GitInfo | None = None,
) -> VerificationResult:
    """Verify that the current environment matches a stamp.

    Checks the git commit, optionally the clean-tree requirement, and (when provided) the
    config hash and snapshot id. Returns a :class:`VerificationResult`; with ``strict=True``
    a mismatch raises instead.

    Raises:
        ReproducibilityError: when git state cannot be read, or ``strict`` and verification fails.
    """
    try:
        info = git_info or get_git_info(repo_path, runner=runner)
    except GitError as exc:
        raise ReproducibilityError(f"cannot verify without git state: {exc}") from exc

    mismatches: list[str] = []
    if info.commit != stamp.git_commit:
        mismatches.append(
            f"git commit mismatch: stamp={stamp.git_commit} current={info.commit}"
        )
    if require_clean and info.dirty:
        mismatches.append("working tree is dirty; code does not match a committed state")

    if config is not None:
        current_hash = hash_config(config)
        if current_hash != stamp.config_hash:
            mismatches.append(
                f"config hash mismatch: stamp={stamp.config_hash} current={current_hash}"
            )

    if snapshot_id is not None and snapshot_id != stamp.snapshot_id:
        mismatches.append(
            f"snapshot id mismatch: stamp={stamp.snapshot_id} current={snapshot_id}"
        )

    result = VerificationResult(
        ok=not mismatches,
        mismatches=mismatches,
        current_commit=info.commit,
        current_dirty=info.dirty,
    )
    if strict and not result.ok:
        raise ReproducibilityError("reproducibility verification failed: " + "; ".join(mismatches))
    return result
