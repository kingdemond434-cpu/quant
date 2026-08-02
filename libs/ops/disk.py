"""DISK HEADROOM FOR THE TAPE -- the one resource whose exhaustion is silent and irreversible.

WHY THIS IS NOT A UTILITY MODULE. The moat is the desk's only unreplicable asset: a day not
recorded cannot be bought back at any price. Running out of disk therefore does not cost money,
it costs a permanent hole in the archive -- and it does it QUIETLY, because a paused recorder
keeps its heartbeat fresh and a full filesystem makes every other organ fail first and louder.

THE FAILURE THIS EXISTS TO PREVENT, STATED PRECISELY. If the recorders pause, the grid stops
growing. Coverage is filled/total, so a frozen denominator lets the miner race to 100% -- and the
desk would read a triumphant number at the exact moment the asset stopped accumulating. That is
worse than a red alarm: it is a green one that is wrong, and it would retire the chase.

So headroom is measured with a growth rate attached rather than as a percentage. "39% used" is
not a finding; "12 days until the recorders pause" is.

Pure and dependency-free apart from shutil, so the recorders can import it without dragging the
desk's libraries into a process that must stay small and never die.
"""

from __future__ import annotations

import shutil
from pathlib import Path

__all__ = [
    "PAUSE_FRAC",
    "WARN_DAYS",
    "days_to_pause",
    "headroom",
    "tape_bytes",
    "usage",
]

#: Fraction of the filesystem at which recorders stop WRITING. Deliberately below 100%: a full
#: disk does not merely stop the tape, it breaks every organ that writes an artifact, and the
#: audit that would tell you why is one of them.
PAUSE_FRAC = 0.80

#: Days of headroom below which the situation is a defect rather than a status. Two weeks is the
#: honest lead time for the only fix that does not lose data -- buying storage and moving cold
#: tape onto it is a procurement action, not a command, and procurement has a latency.
WARN_DAYS = 21.0


def usage(path: str = "/") -> dict:
    u = shutil.disk_usage(path)
    return {
        "total_bytes": u.total,
        "used_bytes": u.used,
        "free_bytes": u.free,
        "used_frac": round(u.used / max(1, u.total), 4),
    }


def headroom(path: str = "/", pause_frac: float = PAUSE_FRAC) -> dict:
    """Bytes remaining before the recorders pause -- NOT before the disk is full.

    The distinction is the point. Free space says how much room is left; this says how much of
    it the tape is actually allowed to have, which is the number that governs the archive.
    """
    u = usage(path)
    limit = int(u["total_bytes"] * pause_frac)
    # CLAMPED TO WHAT THE FILESYSTEM WILL ACTUALLY HAND OVER. used + free does not equal total on
    # most real filesystems -- reserved blocks, overlay layers and journal space all sit in the
    # difference -- so `limit - used` can exceed the bytes that can be written. Reporting the
    # unclamped figure promises headroom that does not exist and lets the tape hit ENOSPC BEFORE
    # the 80% guard ever fires, which is precisely the silent stop this module exists to prevent.
    return {
        **u,
        "pause_at_bytes": limit,
        "headroom_bytes": max(0, min(limit - u["used_bytes"], u["free_bytes"])),
        "paused": u["used_bytes"] >= limit or u["free_bytes"] <= 0,
    }


def tape_bytes(root: Path) -> tuple[int, int]:
    """(bytes, files) under the moat. Cheap enough to run every mining pass.

    Measured directly rather than trusted from a counter, because the number's whole job is to
    catch the case where writing STOPPED -- and a counter that stops being updated looks exactly
    like a tape that stopped growing, which is the thing it is supposed to distinguish.
    """
    total = files = 0
    if not root.exists():
        return 0, 0
    for p in root.rglob("*"):
        if p.is_file():
            try:
                total += p.stat().st_size
            except OSError:
                continue
            files += 1
    return total, files


def days_to_pause(growth_bytes_per_day: float, path: str = "/",
                  pause_frac: float = PAUSE_FRAC) -> dict:
    """WHEN, not whether. A percentage is a status line; a date is an action.

    Returns state UNKNOWN rather than a large number when growth is not measurable -- inventing
    'never' from an unmeasured rate is how a fourteen-day problem gets filed as a non-problem.
    """
    h = headroom(path, pause_frac)
    if h["paused"]:
        return {**h, "state": "PAUSED", "days": 0.0,
                "note": ("recorders are at or past the write limit NOW. The grid has stopped "
                         "growing, so any coverage number rising from here is measuring a frozen "
                         "denominator and must not be read as progress.")}
    if growth_bytes_per_day <= 0:
        return {**h, "state": "UNKNOWN", "days": None,
                "note": ("growth is not measurable yet, so the headroom is a percentage rather "
                         "than a date. A percentage cannot be acted on.")}
    days = h["headroom_bytes"] / growth_bytes_per_day
    return {
        **h,
        "state": "URGENT" if days < WARN_DAYS else "OK",
        "days": round(days, 1),
        "growth_bytes_per_day": int(growth_bytes_per_day),
        "note": (
            f"{days:.1f} days until the recorders pause. Deleting mined tape is NOT an option: "
            "the seven reconstructions are the first seven, not the last, so raw tape must stay "
            "re-readable as mechanisms are added. Buy storage and move COLD tape onto it."
            if days < WARN_DAYS else
            f"{days:.1f} days of headroom at the measured growth rate."),
    }
