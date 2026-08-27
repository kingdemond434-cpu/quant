"""Cross-controller, cross-shell single-instance locks for heavy MT5 research writers."""
from __future__ import annotations

import json
import os
import socket
import sys
import uuid
from contextlib import contextmanager, suppress
from datetime import UTC, datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
LOCK_ROOT = BASE / "data" / ".job_locks"
STALE_SECONDS = 45 * 60


def _owner_is_dead(path: Path) -> bool:
    """True when the lock names a process on THIS host that no longer exists.

    A time-only stale rule makes live work wait on a corpse: a killed ssh leaves an orphaned
    writer, or the box reboots mid-run, and the next 45 minutes of hourly attempts are refused
    by a lock nobody holds (measured 2026-08-27 -- the searcher was blocked this way minutes
    after its import crash was fixed). Liveness is checked first and the timer remains the
    backstop for the cases liveness cannot answer: a lock written by a DIFFERENT host, or an
    unreadable/short-write lock file, is never reclaimed on this basis.
    """
    try:
        row = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return False                      # unreadable: fall back to the age rule, never guess
    if str(row.get("host") or "") != socket.gethostname():
        return False                      # another machine's lock is not ours to judge
    pid = row.get("pid")
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)                   # signal 0: existence check, never delivers a signal
    except ProcessLookupError:
        return True
    except PermissionError:
        return False                      # alive under another user
    except OSError as exc:
        # WINDOWS NEVER RAISES ProcessLookupError HERE, so on the box this whole function could
        # only ever return False and the liveness path -- the entire reason it exists -- was dead
        # code. MEASURED on the desk box (win32) 2026-08-27: `os.kill(<nonexistent pid>, 0)`
        # raises plain `OSError` with `winerror=87` (ERROR_INVALID_PARAMETER), errno 22, and a
        # LIVE pid raises nothing. So on Windows the age rule was the only recovery there has
        # ever been, and the docstring's promise -- that live work never waits 45 minutes on a
        # corpse -- was true on Linux and false where the searcher actually runs.
        # Narrow on purpose: only the documented not-a-process signature counts as dead. Any
        # other OSError is still UNKNOWN and falls back to the age rule, because reclaiming a
        # lock from a process that is merely unreachable would let two writers run at once, which
        # is worse than waiting.
        if sys.platform == "win32" and getattr(exc, "winerror", None) == 87:
            return True
        return False
    return False


@contextmanager
def exclusive_job(name: str):
    """Yield True to one writer, False to concurrent duplicates; recover stale crash locks."""
    LOCK_ROOT.mkdir(parents=True, exist_ok=True)
    path = LOCK_ROOT / f"{name}.json"
    token = uuid.uuid4().hex
    payload = json.dumps({
        "token": token, "pid": os.getpid(), "host": socket.gethostname(),
        "started_at": datetime.now(UTC).isoformat(),
    })
    owned = False
    for _attempt in range(2):
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                stale = datetime.now(UTC).timestamp() - path.stat().st_mtime > STALE_SECONDS
            except OSError:
                stale = False
            if _owner_is_dead(path):
                print(f"{name}: reclaiming lock from dead owner (pid gone) -- {path}")
                stale = True
            if stale:
                with suppress(OSError):
                    path.unlink()
                continue
            print(f"{name}: REFUSED duplicate writer; active lock {path}")
            yield False
            return
        else:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
            owned = True
            break
    if not owned:
        print(f"{name}: REFUSED writer; stale lock could not be recovered")
        yield False
        return
    try:
        yield True
    finally:
        # Never delete a successor's lock after a stale-owner race.
        try:
            current = json.loads(path.read_text("utf-8"))
            if current.get("token") == token:
                path.unlink()
        except (OSError, ValueError, AttributeError):
            pass
