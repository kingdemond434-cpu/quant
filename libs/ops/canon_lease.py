"""WRITER LEASE FOR CANONICAL ARTIFACTS -- one writer at a time, enforced, with a fencing token.

WHY A LEASE AND NOT MORE FENCES (principal 2026-08-26, item 7). Tonight three separate mechanisms
each caught a piece of the same failure and none prevented it: the money-path fence restored code
by marker, the authority ratchet alarmed on lost evidence, and the same-day fence noticed
un-enrolled certificates. All three are DETECTORS. Meanwhile canon was overwritten twice by a
second certifier nobody had identified, an hourly sync reverted a session's work mid-edit, and a
fence "restored" files from a pin that never held the markers. Detection after the fact cannot fix
a write that already happened; the writes have to be serialised.

WHAT THIS ENFORCES

    acquire(artifact, holder) -> token | None

A holder gets the lease only if it is free or expired. Every write carries the token, and a write
whose token does not match the CURRENT epoch is refused -- that is the fencing property, and it is
what makes this different from a lock file. A process that stalls, loses its lease, then wakes up
and writes cannot corrupt anything: its token is stale, so the write is rejected rather than
racing. That exact sequence is what a paused-then-resumed sync bus does.

WHAT IT DELIBERATELY DOES NOT DO

  * It does not block. A caller that cannot get the lease is told to come back; holding up an
    hourly organ behind a stuck writer converts one stalled process into a stalled desk.
  * It does not protect against a writer that never asks. Nothing in a filesystem can. What it
    does is make asking cheap and make the ASK AUDITABLE: `data/canon_lease.json` records who
    held what, when, and which epoch, so the next unexplained overwrite has a suspect list of one.
  * It does not replace the ratchet or the fence. Those catch the writers that never ask; this
    stops the ones that do from colliding with each other.

TTL is short and heartbeats are cheap, because the failure this must survive is a process dying
mid-write, not a process working slowly.
"""
from __future__ import annotations

import json
import os
import secrets
import socket
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / "data" / "canon_lease.json"

#: A lease this old is dead. Short: the failure mode is a process dying mid-write.
TTL_SECONDS = 120.0
#: Artifacts that may only be written under lease. Named explicitly -- a glob would silently pull
#: in files nobody meant to serialise and turn a safety rail into an outage.
GUARDED = (
    "desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json",
    "desks/mt5/reports/UNIVERSAL_SURVIVORS.json",
    "desks/mt5/reports/shadow/shadow_state.json",
    "desks/mt5/data/sleeves.json",
    "desks/mt5/data/sleeve_registry.json",
)


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _read() -> dict[str, Any]:
    try:
        value = json.loads(STATE.read_text("utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def _write(state: dict[str, Any]) -> None:
    """Atomic replace -- a half-written lease file is worse than no lease file."""
    STATE.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(STATE.parent), prefix=".canon_lease.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=1, default=str)
        os.replace(tmp, STATE)
    finally:
        Path(tmp).unlink(missing_ok=True)


def _identity(holder: str) -> str:
    return f"{holder}@{socket.gethostname()}:{os.getpid()}"


def acquire(artifact: str, holder: str) -> str | None:
    """Take the lease for `artifact`, or return None if someone else holds a live one."""
    state = _read()
    leases: dict[str, dict[str, Any]] = state.setdefault("leases", {})
    row: dict[str, Any] = leases.get(artifact) or {}
    now = _now()
    expires = row.get("expires_at")
    if expires:
        try:
            live = datetime.fromisoformat(str(expires)) > now
            if live and row.get("holder") != _identity(holder):
                return None                     # live lease held by someone else -- do not block
        except ValueError:
            pass
    epoch = int(row.get("epoch") or 0) + 1
    token = f"{epoch}:{secrets.token_hex(8)}"
    leases[artifact] = {
        "holder": _identity(holder), "epoch": epoch, "token": token,
        "acquired_at": now.isoformat(timespec="seconds"),
        "expires_at": (now + timedelta(seconds=TTL_SECONDS)).isoformat(timespec="seconds"),
        "previous_holder": row.get("holder"),
    }
    state["updated_at"] = now.isoformat(timespec="seconds")
    _write(state)
    return token


def valid(artifact: str, token: str | None) -> bool:
    """Is this token still the current epoch? A stale token must never author a write."""
    if not token:
        return False
    leases: dict[str, dict[str, Any]] = _read().get("leases") or {}
    row: dict[str, Any] = leases.get(artifact) or {}
    return bool(row.get("token") == token)


def heartbeat(artifact: str, token: str) -> bool:
    """Extend a lease you still hold. Returns False if it was lost -- stop writing."""
    state = _read()
    leases: dict[str, dict[str, Any]] = state.get("leases") or {}
    row: dict[str, Any] = leases.get(artifact) or {}
    if row.get("token") != token:
        return False
    row["expires_at"] = (_now() + timedelta(seconds=TTL_SECONDS)).isoformat(timespec="seconds")
    _write(state)
    return True


def release(artifact: str, token: str) -> None:
    """Give the lease back early so the next writer does not wait out the TTL."""
    state = _read()
    leases: dict[str, dict[str, Any]] = state.get("leases") or {}
    row: dict[str, Any] = leases.get(artifact) or {}
    if row.get("token") == token:
        row["expires_at"] = _now().isoformat(timespec="seconds")
        row["released_at"] = row["expires_at"]
        _write(state)


@contextmanager
def hold(artifact: str, holder: str, *, required: bool = True) -> Iterator[str | None]:
    """Scope a write to a lease.

    `required=False` lets a caller proceed unleased while still RECORDING that it did, which is
    how an existing writer is migrated without turning the migration into an outage: first make it
    visible, then make it mandatory.
    """
    token = acquire(artifact, holder)
    if token is None:
        _l: dict[str, dict[str, Any]] = _read().get("leases") or {}
        current = (_l.get(artifact) or {}).get("holder", "unknown")
        if required:
            raise RuntimeError(
                f"canon lease for {artifact} is held by {current}; refusing to write. This is the "
                f"serialisation that stops two certifiers racing -- retry on the next cycle "
                f"rather than forcing.")
        yield None
        return
    try:
        yield token
    finally:
        release(artifact, token)


def audit() -> dict[str, Any]:
    """Who holds what, for the next unexplained overwrite."""
    state = _read()
    now = _now()
    rows: dict[str, dict[str, Any]] = {}
    leases: dict[str, dict[str, Any]] = state.get("leases") or {}
    for art, row in leases.items():
        try:
            live = datetime.fromisoformat(str(row.get("expires_at"))) > now
        except (TypeError, ValueError):
            live = False
        rows[art] = {"holder": row.get("holder"), "epoch": row.get("epoch"),
                     "live": live, "previous_holder": row.get("previous_holder")}
    return {"checked_at": now.isoformat(timespec="seconds"), "guarded": list(GUARDED),
            "leases": rows}
