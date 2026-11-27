"""Turn-taking on `certification_lane`: the resident judge yields between sweeps to a waiting
certifier.

WHY (hourly pass, 2026-11-25 11:00Z). The judge sweep (`run_sharded_gauntlet.py`, resident) runs
sweeps back to back with ZERO cadence and holds `certification_lane` for each whole sweep. The
QQuant certifier (`certifier_launcher.py`, hourly at :27) tried the lane ONCE and, finding it
held, printed DEFERRED and exited: QQUANT_GATES went 379 minutes stale against its 180-minute
contract, and every hour it tried, it lost. The gap between two judge sweeps is a few
milliseconds; nothing ever landed in it.

THE TURN. A certifier that finds the lane held writes a WAITER record beside the lock and keeps
retrying for up to `CERT_WAIT_S`. The resident judge reads that record BEFORE it starts its next
sweep and holds off (up to `YIELD_MAX_S`) while a live waiter is there, so the certifier takes
the lane at the sweep boundary. No sweep is interrupted and no cell is lost; the judge gives up
one certifier run's wall per hour at most. A waiter whose process is gone, on another host, or
older than `WAITER_FRESH_S` is ignored, so a crashed certifier never parks the judge.

Not a priority inversion on capital: the certifier writes the gates the promoter reads, so a
certifier that never runs freezes promotion of everything the judge certified.
"""
from __future__ import annotations

import contextlib
import json
import os
import socket
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

#: How long a certifier keeps retrying a held lane before it stands down for this hour. Under the
#: hourly trigger so a waiting certifier never overlaps its own next run.
CERT_WAIT_S = 50 * 60
CERT_RETRY_S = 20.0
#: The most the resident judge holds off one sweep for a waiter. A certifier run that has not
#: taken the lane in this long is not going to; the judge resumes.
YIELD_MAX_S = 15 * 60
YIELD_POLL_S = 10.0
#: A waiter record older than this is a crashed certifier's, never honoured.
WAITER_FRESH_S = CERT_WAIT_S + 10 * 60
#: NEVER SILENT-OK (2026-11-25): the certifier exited 0 on every deferral, so the scheduler showed
#: green while QQUANT_GATES aged past its 180-minute contract. Every outcome is recorded in
#: OUTCOME, and from this many deferrals in a row (3 hourly runs = the contract) the launcher
#: exits STARVED_RC, so the task itself goes red and the guardian's failed-task check sees it.
STARVED_STREAK = 3
STARVED_RC = 75
OUTCOME = Path(__file__).resolve().parent.parent / "reports" / "CERTIFIER_LANE.json"


def _root() -> Path:
    from research.job_lock import LOCK_ROOT
    return Path(LOCK_ROOT)


def waiter_path(lane: str = "certification_lane", root: Path | None = None) -> Path:
    return (root or _root()) / f"{lane}.waiting.json"


def _alive(pid: int) -> bool:
    try:
        import psutil
        return bool(psutil.pid_exists(pid))
    except Exception:
        return True                      # unknown counts as alive; WAITER_FRESH_S still bounds it


def announce(who: str, *, lane: str = "certification_lane", root: Path | None = None) -> None:
    """Record that THIS process is waiting for `lane`. Best effort."""
    path = waiter_path(lane, root)
    doc = {"pid": os.getpid(), "host": socket.gethostname(), "who": who,
           "since_utc": datetime.now(UTC).isoformat(timespec="seconds"), "since": time.time()}
    with contextlib.suppress(OSError):
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps(doc), encoding="utf-8")
        os.replace(tmp, path)


def clear(*, lane: str = "certification_lane", root: Path | None = None) -> None:
    """Remove the waiter record if it is THIS process's (never a successor's)."""
    path = waiter_path(lane, root)
    with contextlib.suppress(OSError, ValueError, AttributeError):
        doc = json.loads(path.read_text("utf-8"))
        if doc.get("pid") == os.getpid() and doc.get("host") == socket.gethostname():
            path.unlink()


def waiting(*, lane: str = "certification_lane", root: Path | None = None,
            now: float | None = None) -> dict[str, Any] | None:
    """The live waiter record, or None: absent, unreadable, stale, another host or a dead pid."""
    try:
        doc = json.loads(waiter_path(lane, root).read_text("utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(doc, dict) or doc.get("host") != socket.gethostname():
        return None
    since, pid = doc.get("since"), doc.get("pid")
    if not isinstance(since, (int, float)) or not isinstance(pid, int):
        return None
    if (now if now is not None else time.time()) - since > WAITER_FRESH_S or not _alive(pid):
        return None
    return doc


def yield_to_waiter(*, sleep: Callable[[float], Any] = time.sleep,
                    clock: Callable[[], float] = time.monotonic,
                    max_s: float = YIELD_MAX_S, poll_s: float = YIELD_POLL_S,
                    lane: str = "certification_lane", root: Path | None = None
                    ) -> dict[str, Any] | None:
    """Called by the resident judge before each sweep, while it holds no lock. Holds off while a
    live waiter is there, at most `max_s`. Returns what it did, or None when nobody waited."""
    first = waiting(lane=lane, root=root)
    if first is None:
        return None
    t0 = clock()
    while clock() - t0 < max_s and waiting(lane=lane, root=root) is not None:
        sleep(poll_s)
    return {"who": first.get("who"), "pid": first.get("pid"),
            "held_s": round(clock() - t0, 1),
            "outcome": ("TIMED_OUT" if waiting(lane=lane, root=root) is not None
                        else "TOOK_TURN")}


def record_outcome(outcome: str, *, rc: int | None = None, path: Path | None = None) -> int:
    """Record one certifier run's outcome; return the exit code the launcher should give.

    RAN -> the battery's own rc (the streak resets). DEFERRED -> 0 while the deferral streak is
    under STARVED_STREAK, STARVED_RC from then on. A record that cannot be written never changes
    the rc of a run that ran."""
    path = path or OUTCOME
    try:
        prev = json.loads(path.read_text("utf-8"))
        if not isinstance(prev, dict):
            prev = {}
    except (OSError, ValueError):
        prev = {}
    now = datetime.now(UTC).isoformat(timespec="seconds")
    streak = 0 if outcome == "RAN" else int(prev.get("deferred_streak") or 0) + 1
    doc = {**prev, "schema": "certifier_lane/1", "last_outcome": outcome, "last_at_utc": now,
           "deferred_streak": streak, "starved_at_streak": STARVED_STREAK}
    if outcome == "RAN":
        doc.update(last_ran_utc=now, last_rc=rc)
    else:
        doc.update(last_deferred_utc=now)
    doc["status"] = "STARVED" if streak >= STARVED_STREAK else "OK"
    with contextlib.suppress(OSError):
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps(doc, indent=1), encoding="utf-8")
        os.replace(tmp, path)
    if outcome == "RAN":
        return int(rc or 0)
    return STARVED_RC if streak >= STARVED_STREAK else 0
