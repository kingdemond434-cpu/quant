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
