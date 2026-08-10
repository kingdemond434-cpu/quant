"""Durable controller lease, fencing token and checkpoint continuity.

Claude and Codex are reasoning controllers of one operation.  This module coordinates only their
state-changing control-plane work.  It never stops collectors, deterministic workers, monitors,
queued experiments or execution safety processes when a controller lease expires.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from collections.abc import Iterator, Mapping
from contextlib import contextmanager, suppress
from datetime import UTC, datetime, timedelta
from pathlib import Path

from libs.core.coerce import integer

__all__ = [
    "ControllerLeaseError",
    "checkpoint",
    "claim",
    "heartbeat",
    "read_state",
    "release",
    "transfer",
]

DEFAULT_STATE = Path("data/controller_lease.json")
DEFAULT_CHECKPOINT = Path("data/controller_checkpoint.json")
DEFAULT_HISTORY = Path("data/controller_checkpoint_history.jsonl")


class ControllerLeaseError(RuntimeError):
    """Raised when a stale or foreign controller attempts a fenced mutation."""


def _now(value: datetime | None = None) -> datetime:
    stamp = value or datetime.now(tz=UTC)
    return stamp if stamp.tzinfo else stamp.replace(tzinfo=UTC)


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def _read(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _read_claim_state(path: Path) -> dict[str, object]:
    """A lost lease may be reclaimed; a corrupt lease must be repaired, never guessed away."""
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ControllerLeaseError("controller lease state is unreadable or corrupt") from exc
    if not isinstance(value, dict):
        raise ControllerLeaseError("controller lease state is corrupt (expected an object)")
    return value


def _write_atomic(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(json.dumps(dict(value), indent=1, default=str), "utf-8")
    os.replace(temporary, path)


@contextmanager
def _mutex(state_path: Path, *, stale_seconds: float = 30.0) -> Iterator[None]:
    lock = state_path.with_name(f".{state_path.name}.lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    acquired = False
    for _ in range(100):
        try:
            descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(f"{os.getpid()} {time.time()}\n")
            acquired = True
            break
        except FileExistsError:
            try:
                stale = time.time() - lock.stat().st_mtime > stale_seconds
            except OSError:
                stale = False
            if stale:
                with suppress(OSError):
                    lock.unlink()
            time.sleep(0.01)
    if not acquired:
        raise ControllerLeaseError("controller lease mutex is busy")
    try:
        yield
    finally:
        with suppress(OSError):
            lock.unlink()


def read_state(*, state_path: Path = DEFAULT_STATE) -> dict[str, object]:
    state = _read(state_path)
    expires = state.get("expires_at")
    active = False
    if expires:
        try:
            active = datetime.fromisoformat(str(expires).replace("Z", "+00:00")) > _now()
        except ValueError:
            active = False
    return {
        **state,
        "active": active,
        "persistent_workers_controller_independent": True,
    }


def claim(
    controller: str,
    *,
    ttl_seconds: int = 900,
    state_path: Path = DEFAULT_STATE,
    now: datetime | None = None,
) -> dict[str, object]:
    """Claim an expired/unowned control plane and issue a monotonically fenced lease."""
    if not controller.strip() or ttl_seconds < 30:
        raise ValueError("controller is required and ttl_seconds must be >=30")
    stamp = _now(now)
    with _mutex(state_path):
        prior = _read_claim_state(state_path)
        expires = prior.get("expires_at")
        active = False
        if expires:
            try:
                active = datetime.fromisoformat(str(expires).replace("Z", "+00:00")) > stamp
            except ValueError:
                active = False
        if active:
            return {
                "status": "LEASE_HELD",
                "controller": prior.get("controller"),
                "epoch": prior.get("epoch"),
                "expires_at": expires,
                "persistent_workers_controller_independent": True,
            }
        epoch = integer(prior.get("epoch")) + 1
        nonce = uuid.uuid4().hex
        token = hashlib.sha256(f"{controller}|{epoch}|{nonce}".encode()).hexdigest()
        state = {
            "status": "LEASED",
            "controller": controller,
            "epoch": epoch,
            "fencing_token": token,
            "claimed_at": _iso(stamp),
            "heartbeat_at": _iso(stamp),
            "expires_at": _iso(stamp + timedelta(seconds=ttl_seconds)),
            "predecessor": prior.get("controller"),
            "persistent_workers_controller_independent": True,
        }
        _write_atomic(state_path, state)
        return state


def _validate(
    state: Mapping[str, object],
    *,
    controller: str,
    epoch: int,
    fencing_token: str,
    now: datetime | None = None,
) -> None:
    if (
        state.get("controller") != controller
        or integer(state.get("epoch"), -1) != epoch
        or state.get("fencing_token") != fencing_token
        or state.get("status") != "LEASED"
    ):
        raise ControllerLeaseError("stale or foreign fencing token")
    try:
        expires_at = datetime.fromisoformat(str(state["expires_at"]).replace("Z", "+00:00"))
    except (KeyError, TypeError, ValueError) as exc:
        raise ControllerLeaseError("controller lease expired or has invalid expiry") from exc
    if _now(expires_at) <= _now(now):
        raise ControllerLeaseError("controller lease expired")


def heartbeat(
    controller: str,
    epoch: int,
    fencing_token: str,
    *,
    ttl_seconds: int = 900,
    state_path: Path = DEFAULT_STATE,
    now: datetime | None = None,
) -> dict[str, object]:
    with _mutex(state_path):
        stamp = _now(now)
        state = _read(state_path)
        _validate(
            state,
            controller=controller,
            epoch=epoch,
            fencing_token=fencing_token,
            now=stamp,
        )
        state.update(
            {
                "heartbeat_at": _iso(stamp),
                "expires_at": _iso(stamp + timedelta(seconds=ttl_seconds)),
            }
        )
        _write_atomic(state_path, state)
        return state


def checkpoint(
    controller: str,
    epoch: int,
    fencing_token: str,
    summary: Mapping[str, object],
    *,
    state_path: Path = DEFAULT_STATE,
    checkpoint_path: Path = DEFAULT_CHECKPOINT,
    history_path: Path = DEFAULT_HISTORY,
    now: datetime | None = None,
) -> dict[str, object]:
    """Atomically publish controller state after validating the current fencing token."""
    with _mutex(state_path):
        stamp = _now(now)
        state = _read(state_path)
        _validate(
            state,
            controller=controller,
            epoch=epoch,
            fencing_token=fencing_token,
            now=stamp,
        )
        row = {
            "checkpointed_at": _iso(stamp),
            "controller": controller,
            "epoch": epoch,
            "summary": dict(summary),
            "handoff_contract": "one operation; resume, never reset",
        }
        _write_atomic(checkpoint_path, row)
        history_path.parent.mkdir(parents=True, exist_ok=True)
        with history_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, default=str) + "\n")
        state["last_checkpoint_at"] = row["checkpointed_at"]
        state["last_checkpoint_epoch"] = epoch
        _write_atomic(state_path, state)
        return row


def transfer(
    controller: str,
    epoch: int,
    fencing_token: str,
    successor: str,
    summary: Mapping[str, object],
    *,
    ttl_seconds: int = 900,
    state_path: Path = DEFAULT_STATE,
    checkpoint_path: Path = DEFAULT_CHECKPOINT,
    history_path: Path = DEFAULT_HISTORY,
    now: datetime | None = None,
) -> dict[str, object]:
    """Checkpoint and atomically hand ownership to a successor with a higher fence epoch."""
    if not successor.strip() or successor == controller:
        raise ValueError("successor must be a different named controller")
    with _mutex(state_path):
        stamp = _now(now)
        state = _read(state_path)
        _validate(
            state,
            controller=controller,
            epoch=epoch,
            fencing_token=fencing_token,
            now=stamp,
        )
        row = {
            "checkpointed_at": _iso(stamp),
            "controller": controller,
            "epoch": epoch,
            "successor": successor,
            "summary": dict(summary),
            "handoff_contract": "one operation; resume, never reset",
        }
        _write_atomic(checkpoint_path, row)
        history_path.parent.mkdir(parents=True, exist_ok=True)
        with history_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, default=str) + "\n")
        next_epoch = epoch + 1
        token = hashlib.sha256(f"{successor}|{next_epoch}|{uuid.uuid4().hex}".encode()).hexdigest()
        next_state = {
            "status": "LEASED",
            "controller": successor,
            "predecessor": controller,
            "epoch": next_epoch,
            "fencing_token": token,
            "claimed_at": _iso(stamp),
            "heartbeat_at": _iso(stamp),
            "expires_at": _iso(stamp + timedelta(seconds=ttl_seconds)),
            "last_checkpoint_at": row["checkpointed_at"],
            "last_checkpoint_epoch": epoch,
            "persistent_workers_controller_independent": True,
        }
        _write_atomic(state_path, next_state)
        return {"checkpoint": row, "lease": next_state}


def release(
    controller: str,
    epoch: int,
    fencing_token: str,
    *,
    state_path: Path = DEFAULT_STATE,
    now: datetime | None = None,
) -> dict[str, object]:
    with _mutex(state_path):
        stamp = _now(now)
        state = _read(state_path)
        _validate(
            state,
            controller=controller,
            epoch=epoch,
            fencing_token=fencing_token,
            now=stamp,
        )
        state.update({"status": "RELEASED", "released_at": _iso(stamp), "expires_at": _iso(stamp)})
        _write_atomic(state_path, state)
        return state
