"""HOST MEMORY, INCLUDING THE MEMORY THAT BELONGS TO NO PROCESS.

WHY THIS EXISTS. Every memory check on this desk watches PROCESS RSS. `/tmp` here is a **tmpfs**,
so a file written under it is RESIDENT RAM owned by no process at all -- invisible to every one of
those checks by construction. Measured 2026-08-05: 35 orphaned pytest run directories holding
1021MB, 26% of a 3.8GB swapless box that also carries the live executor, three recorders and
several agent sessions, against 189MB available. Nothing on the desk was looking, because nothing
on the desk had a way to look.

THE CLOSED LOOP THAT KEPT IT INVISIBLE. A run killed by the OOM killer never reaches its own
cleanup, so its scratch directory is orphaned; pytest's start-of-run GC skips a directory whose
lock still looks live; the orphans accumulate; free RAM falls; the next run is likelier to be
killed. The symptom -- rc=-9 with no traceback and no summary -- looks exactly like a broken test
suite, and was filed as one twice.

NONE AND ZERO ARE DIFFERENT ANSWERS AND ARE KEPT DIFFERENT. Every reader here returns ``None``
when it cannot measure, never a fabricated ``0``. "We could not read /proc" must never render as
"there was no memory": the first is a gap in the instrument, the second is a fact about the box,
and they demand opposite responses. Callers render ``None`` as "unknown" (L1.28a -- unmeasured is
never OK, and never silently zero).

Pure stdlib and dependency-free, deliberately: this is imported by the CI gate and by max_audit,
both of which must stay small and must not drag the desk's libraries into a process whose whole
job is to report that the box is out of room.
"""

from __future__ import annotations

import os
from pathlib import Path

__all__ = ["mem_available_mb", "pressure_note", "tmpfs_used_mb"]

_MEMINFO = Path("/proc/meminfo")
_MOUNTS = Path("/proc/mounts")


def mem_available_mb() -> int | None:
    """MemAvailable in MB, or ``None`` where /proc is absent or unreadable.

    Read at the moment a step dies so the diagnosis is CHECKABLE rather than asserted. This box
    cannot read ``journalctl -k``, so an OOM kill can NEVER be confirmed from the log -- rc=-9 is
    all the desk will ever see. That is precisely why the memory figure has to be captured at the
    moment of death rather than reconstructed afterwards from a quiet box.
    """
    try:
        for line in _MEMINFO.read_text("utf-8").splitlines():
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) // 1024
    except (OSError, ValueError, IndexError):
        return None
    return None


def _fstype(path: str) -> str | None:
    """Filesystem type of the mount `path` resolves onto, or ``None`` if it cannot be determined.

    Longest-prefix match against /proc/mounts, which is how the kernel resolves it: `/tmp` and `/`
    can both be prefixes of `/tmp/x` and only the longer one is the mount actually carrying it.
    """
    try:
        target = os.path.realpath(path)
        mounts = _MOUNTS.read_text("utf-8").splitlines()
    except OSError:
        return None
    best: tuple[int, str] | None = None
    for line in mounts:
        parts = line.split()
        if len(parts) < 3:
            continue
        point, kind = parts[1].replace("\\040", " "), parts[2]
        under = target == point or target.startswith(point.rstrip("/") + "/")
        if under and (best is None or len(point) > best[0]):
            best = (len(point), kind)
    return None if best is None else best[1]


def tmpfs_used_mb(path: str = "/tmp") -> int | None:  # noqa: S108 -- read-only: this module
    # MEASURES the mount, it never creates a file there. S108 guards against writing predictable
    # paths into a world-writable directory, which is the opposite of what happens here.
    """MB of RAM held by files under `path`'s filesystem, or ``None`` if `path` is not a tmpfs.

    ``None`` here carries a MEANING beyond "unmeasured": on a box where `/tmp` is a real disk
    there is no memory being consumed and nothing for this reader to report. The caller must not
    convert that into "0MB of tmpfs pressure" on a box where the answer is "this measurement does
    not apply" -- the two look identical in a log line and lead to different investigations.
    """
    if _fstype(path) != "tmpfs":
        return None
    try:
        st = os.statvfs(path)
    except OSError:
        return None
    return int((st.f_blocks - st.f_bfree) * st.f_frsize) // (1024 * 1024)


def pressure_note(path: str = "/tmp") -> str:  # noqa: S108 -- read-only, as above
    """One line of host-memory evidence for a death report, safe to embed in any message.

    Never raises and never returns an empty string, because it is called on the failure path of
    the desk's safety gate: an instrument that can itself throw while reporting a kill would turn
    a diagnosable red into an unexplained one.
    """
    avail = mem_available_mb()
    used = tmpfs_used_mb(path)
    left = "MemAvailable unknown" if avail is None else f"MemAvailable {avail}MB"
    if used is None:
        return f"{left}, {path} is not a tmpfs (no hidden RAM there)"
    return f"{left}, {used}MB of RAM held by files under {path} (tmpfs)"
