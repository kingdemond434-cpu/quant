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
import time
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "TmpEntry",
    "fd_scan_coverage",
    "mem_available_mb",
    "pressure_note",
    "tmpfs_top_holders",
    "tmpfs_used_mb",
]

_MEMINFO = Path("/proc/meminfo")
_MOUNTS = Path("/proc/mounts")
_PROC = Path("/proc")


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


@dataclass(frozen=True)
class TmpEntry:
    """One top-level entry under the watched mount, with the ONE fact that makes it actionable.

    `held` is deliberately three-valued and the third value is the load-bearing one:

    * ``True``  -- a live process holds a descriptor under this path. A FACT. Do not delete.
    * ``None``  -- CANNOT TELL. The fd scan could not see every process on the box.
    * ``False`` -- no live process holds it, asserted ONLY when the scan saw every process.

    A two-valued flag here would be worse than no flag at all. Measured on this box: 42 of 175
    pids are fd-readable, so a naive "no descriptor found => orphaned" would certify as safe the
    scratch of 133 processes it simply cannot see -- and the reader would then delete a live
    session's working state on the authority of an instrument that never looked. That is WS-005,
    the desk's most-repeated defect class (absence resolving to a clean verdict), pointed at the
    one decision where being wrong destroys another agent's work mid-run.
    """

    path: str
    mb: int
    age_h: float
    held: bool | None


def fd_scan_coverage() -> tuple[int, int]:
    """``(pids_whose_fds_are_readable, pids_total)`` -- how much of the box the scan can see.

    Published beside every holder verdict rather than kept internal, because it is the number
    that says what the verdict is WORTH. Most of /proc belongs to root or another user here, and
    an unreadable ``/proc/<pid>/fd`` is indistinguishable from a process holding nothing.
    """
    total = readable = 0
    try:
        entries = list(_PROC.iterdir())
    except OSError:
        return (0, 0)
    for p in entries:
        if not p.name.isdigit():
            continue
        total += 1
        try:
            list((p / "fd").iterdir())
        except OSError:
            continue
        readable += 1
    return (readable, total)


def _held_paths(mount: str) -> set[str]:
    """Every path under `mount` that some VISIBLE live process holds a descriptor on.

    Only positive evidence is collected. A pid that vanishes mid-walk, or whose fds cannot be
    read, contributes nothing and must not be recorded as "holding nothing" -- that inversion is
    the whole reason `TmpEntry.held` has a third value.
    """
    prefix = mount.rstrip("/") + "/"
    out: set[str] = set()
    try:
        entries = list(_PROC.iterdir())
    except OSError:
        return out
    for p in entries:
        if not p.name.isdigit():
            continue
        try:
            for fd in (p / "fd").iterdir():
                target = os.path.realpath(fd)
                if target.startswith(prefix):
                    out.add(target)
        except OSError:
            continue  # attrition-ok: an unreadable/vanished pid yields NO evidence either way,
            # and is accounted for by fd_scan_coverage() rather than silently dropped (L1.60).
    return out


def _entry_mb(path: Path) -> int:
    """Bytes under `path` in MB, counted the way the kernel charges the tmpfs: by file size."""
    try:
        st = path.lstat()
    except OSError:
        return 0
    if not path.is_dir() or path.is_symlink():
        return int(st.st_size) // (1024 * 1024)
    total = 0
    for root, _dirs, files in os.walk(path, onerror=lambda _e: None):
        for f in files:
            try:
                total += os.lstat(os.path.join(root, f)).st_size
            except OSError:
                continue  # attrition-ok: a file deleted mid-walk held no RAM by the time we read
    return total // (1024 * 1024)


def tmpfs_top_holders(path: str = "/tmp", *, limit: int = 6,  # noqa: S108 -- read-only, as above
                      min_mb: int = 10) -> list[TmpEntry]:
    """The largest entries under `path`, each with its age and whether anything live holds it.

    THE REPAIR HALF OF THE TMPFS FENCE. The fence reports occupancy and deliberately does not
    delete -- `/tmp` here is shared with the live executor, three recorders and several
    concurrent agent sessions, so an automatic reaper would race a sibling's scratch mid-run.
    But "do not delete automatically" left the human or agent doing the freeing with only a `du`
    line, and `du` cannot answer the single question that makes the deletion safe. So the
    investigation got redone by hand every time, under memory pressure, which is when a mistake
    is likeliest and costliest.

    Returns ``[]`` when `path` is not a tmpfs: there is no hidden RAM to reclaim there, which is
    a different fact from an empty list of large entries but leads to the same non-action.
    """
    if _fstype(path) != "tmpfs":
        return []
    readable, total = fd_scan_coverage()
    complete = total > 0 and readable == total
    held = _held_paths(path)
    now = time.time()
    rows: list[TmpEntry] = []
    try:
        children = list(Path(path).iterdir())
    except OSError:
        return []
    for child in children:
        mb = _entry_mb(child)
        if mb < min_mb:
            continue
        target = os.path.realpath(child)
        is_held = any(h == target or h.startswith(target.rstrip("/") + "/") for h in held)
        try:
            age_h = max(0.0, (now - child.lstat().st_mtime) / 3600.0)
        except OSError:
            continue  # attrition-ok: entry vanished between listing and stat -- it holds no RAM
        rows.append(TmpEntry(path=str(child), mb=mb, age_h=age_h,
                             # True is a fact; False is only assertable with full coverage.
                             held=True if is_held else (False if complete else None)))
    rows.sort(key=lambda r: r.mb, reverse=True)
    return rows[:limit]


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
