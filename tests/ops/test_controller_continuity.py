from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from libs.ops.controller_continuity import (
    ControllerLeaseError,
    checkpoint,
    claim,
    heartbeat,
    read_state,
    release,
    transfer,
)


def _paths(tmp_path: Path) -> tuple[Path, Path, Path]:
    return tmp_path / "lease.json", tmp_path / "checkpoint.json", tmp_path / "history.jsonl"


def test_claim_checkpoint_and_atomic_transfer_are_monotonically_fenced(tmp_path: Path) -> None:
    state, saved, history = _paths(tmp_path)
    now = datetime(2026, 8, 9, tzinfo=UTC)
    codex = claim("codex", state_path=state, now=now, ttl_seconds=120)
    held = claim("claude", state_path=state, now=now, ttl_seconds=120)
    assert held["status"] == "LEASE_HELD"
    epoch, token = int(codex["epoch"]), str(codex["fencing_token"])
    beat = heartbeat(
        "codex", epoch, token, state_path=state, now=now + timedelta(seconds=30), ttl_seconds=120
    )
    assert beat["heartbeat_at"] != codex["heartbeat_at"]
    row = checkpoint(
        "codex",
        epoch,
        token,
        {"branch": "shared", "frontier": 77},
        state_path=state,
        checkpoint_path=saved,
        history_path=history,
        now=now + timedelta(seconds=31),
    )
    assert row["summary"]["frontier"] == 77
    handed = transfer(
        "codex",
        epoch,
        token,
        "claude",
        {"resume": "same frontier"},
        state_path=state,
        checkpoint_path=saved,
        history_path=history,
        now=now + timedelta(seconds=32),
    )
    assert handed["lease"]["epoch"] == epoch + 1
    assert handed["lease"]["controller"] == "claude"
    with pytest.raises(ControllerLeaseError, match="stale or foreign"):
        checkpoint(
            "codex",
            epoch,
            token,
            {},
            state_path=state,
            checkpoint_path=saved,
            history_path=history,
        )
    next_lease = handed["lease"]
    released = release(
        "claude",
        int(next_lease["epoch"]),
        str(next_lease["fencing_token"]),
        state_path=state,
        now=now + timedelta(seconds=40),
    )
    assert released["status"] == "RELEASED"
    assert read_state(state_path=state)["active"] is False
    assert len(history.read_text("utf-8").splitlines()) == 2


def test_expired_controller_is_reclaimed_without_stopping_workers(tmp_path: Path) -> None:
    state, _, _ = _paths(tmp_path)
    now = datetime(2026, 8, 9, tzinfo=UTC)
    first = claim("claude", state_path=state, now=now, ttl_seconds=30)
    second = claim("codex", state_path=state, now=now + timedelta(seconds=31), ttl_seconds=30)
    assert second["epoch"] == int(first["epoch"]) + 1
    assert second["persistent_workers_controller_independent"] is True


def test_expired_holder_is_fenced_from_every_control_plane_mutation(tmp_path: Path) -> None:
    state, saved, history = _paths(tmp_path)
    now = datetime(2026, 8, 9, tzinfo=UTC)
    lease = claim("codex", state_path=state, now=now, ttl_seconds=30)
    epoch, token = int(lease["epoch"]), str(lease["fencing_token"])
    expired_at = now + timedelta(seconds=31)

    with pytest.raises(ControllerLeaseError, match="lease expired"):
        heartbeat("codex", epoch, token, state_path=state, now=expired_at)
    with pytest.raises(ControllerLeaseError, match="lease expired"):
        checkpoint(
            "codex",
            epoch,
            token,
            {},
            state_path=state,
            checkpoint_path=saved,
            history_path=history,
            now=expired_at,
        )
    with pytest.raises(ControllerLeaseError, match="lease expired"):
        transfer(
            "codex",
            epoch,
            token,
            "claude",
            {},
            state_path=state,
            checkpoint_path=saved,
            history_path=history,
            now=expired_at,
        )
    with pytest.raises(ControllerLeaseError, match="lease expired"):
        release("codex", epoch, token, state_path=state, now=expired_at)

    assert not saved.exists()
    assert not history.exists()
    assert read_state(state_path=state)["epoch"] == epoch


def test_corrupt_existing_lease_fails_closed_without_overwrite(tmp_path: Path) -> None:
    state, _, _ = _paths(tmp_path)
    corrupt = "{not-valid-json"
    state.write_text(corrupt, "utf-8")
    with pytest.raises(ControllerLeaseError, match="corrupt"):
        claim("codex", state_path=state, ttl_seconds=30)
    assert state.read_text("utf-8") == corrupt


def test_controller_inputs_fail_closed(tmp_path: Path) -> None:
    state, saved, history = _paths(tmp_path)
    with pytest.raises(ValueError, match="ttl_seconds"):
        claim("codex", state_path=state, ttl_seconds=1)
    lease = claim("codex", state_path=state, ttl_seconds=30)
    with pytest.raises(ValueError, match="different"):
        transfer(
            "codex",
            int(lease["epoch"]),
            str(lease["fencing_token"]),
            "codex",
            {},
            state_path=state,
            checkpoint_path=saved,
            history_path=history,
        )


def test_the_lease_is_anchored_to_the_repository_not_the_callers_directory(tmp_path,
                                                                          monkeypatch) -> None:
    """A relative lease path gives every working directory its own lease.

    MEASURED 2026-11-14. The three defaults were bare relative paths, so from a git worktree
    `_read` found no file, `_validate` saw no active lease, and the control plane refused with
    "stale or foreign fencing token" -- a message about the token for a fault about the path --
    while `data/controller_lease.json` in the repository held a LIVE lease belonging to the very
    caller being refused. The CRO cycle tells a lane to work in a worktree AND to checkpoint after
    each closure, so both instructions could not be followed at once.

    A lease is the one piece of state that must never have two copies.
    """
    from libs.ops import controller_continuity as cc

    root = Path(cc.__file__).resolve().parents[2]
    for path in (cc.DEFAULT_STATE, cc.DEFAULT_CHECKPOINT, cc.DEFAULT_HISTORY):
        assert path.is_absolute(), path
        assert path.parent == root / "data", path

    # ... and the anchor does not move when the caller does.
    monkeypatch.chdir(tmp_path)
    import importlib

    again = importlib.reload(cc)
    assert again.DEFAULT_STATE.parent == root / "data"
    assert again.DEFAULT_STATE.name == "controller_lease.json"
