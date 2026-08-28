"""Cross-controller, cross-shell single-instance locks for heavy MT5 research writers."""
from __future__ import annotations

import json
import os
import socket
import time
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


def free_mb() -> int | None:
    """Physical memory actually available right now, or None where it cannot be read.

    UNMEASURED is a real answer (L1.28a): if this cannot be determined, admission must not
    invent a number, and the caller admits the job rather than blocking work on ignorance.
    """
    if sys.platform == "win32":
        import ctypes

        class _MS(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

        st = _MS()
        st.dwLength = ctypes.sizeof(_MS)
        try:
            if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
                return None
        except (AttributeError, OSError):
            return None
        return int(st.ullAvailPhys // (1024 * 1024))
    try:
        for line in Path("/proc/meminfo").read_text("utf-8").splitlines():
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) // 1024
    except (OSError, ValueError, IndexError):
        return None
    return None


@contextmanager
def exclusive_job(name: str, need_mb: int = 0):
    """Yield True to one writer, False to duplicates OR when the box cannot fit this job.

    THE MEMORY PRECONDITION (2026-08-28). This desk box has 8GB and runs the LIVE MT5 terminal
    beside the miners. A per-name lock stops a job racing itself; it has nothing to say about
    edge_search and external_gauntlet colliding, and colliding is what they did -- measured that
    night at 0.3GB free, with the sweep alive 87 minutes at a trickle of CPU having produced
    nothing. A thrashing process still breathes, so every liveness check passed while the box
    made no progress at all. The same collision shows up three times as `oom-kill` in the unit
    death log, so this is a recurring class, not an incident.

    Starting a job that does not fit is strictly worse than not starting it: it destroys its own
    run, degrades every neighbour, and endangers the terminal that holds live positions. Standing
    down is cheap -- the trigger is hourly and the per-cell cache makes the next attempt resume
    rather than restart -- so refusal costs a delay while admission costs the hour AND the box.

    The refusal is LOUD and names the number, because a silent stand-down is indistinguishable
    from the crash it prevents, and this desk has been burned by exactly that ambiguity.
    """
    if need_mb > 0:
        # MEDIAN OF THREE, NOT ONE SAMPLE. Free memory on this box is a sawtooth: the searcher
        # builds primitives for a symbol, peaks, emits, releases. Measured 2026-08-28, a single
        # reading said 55MB while readings seconds either side said 1,605MB -- and the backfill
        # stood down on the trough for a box that had ample room. One sample of a sawtooth is a
        # coin flip, and a job whose start depends on a coin flip is not scheduled, it is
        # gambled. Three readings across ~20 seconds outlast the trough; a genuinely starved box
        # reads low in all of them.
        readings = []
        for i in range(3):
            if i:
                time.sleep(10)
            r = free_mb()
            if r is not None:
                readings.append(r)
        avail = sorted(readings)[len(readings) // 2] if readings else None
        if avail is not None and avail < need_mb:
            print(f"{name}: STOOD DOWN -- needs ~{need_mb}MB, box has {avail}MB available. "
                  f"Not started (a job that does not fit thrashes the box and the live "
                  f"terminal); the next scheduled trigger retries and the cache makes it resume.")
            yield False
            return
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
