"""Read an artifact's CONTENT stamp from the head of the file, without parsing the file.

WHY THE HEAD AND NOT THE MTIME. A file's modification time says when somebody last wrote the
FILE, not when its producer last produced the CONTENT, and on this desk those are routinely
different people: readers heal, prune, re-encode and touch the artifacts they read, a checkout or
a box-state adoption rewrites them, and a copy lands with a fresh mtime over stale bytes.
`desks/mt5/data/hypotheses/miner_candidates.json` carried a `compiled_at` weeks old while its
mtime kept moving (2026-09-24, "its mtime was being healed by its readers"; again 2026-10-20 on
the trading box, every scheduled task rc 0). Only the producer's own stamp can say how old the
content is.

WHY NOT `json.load`. That artifact is ~70 MB; parsing it to read one field costs seconds and
hundreds of megabytes on a box where memory is the binding constraint, and a freshness fence that
is expensive gets taken off its clock. Producers here write their stamp as the FIRST key
(`json.dump` keeps insertion order), so the first few kilobytes carry it.

ABSENCE IS NEVER A VERDICT OF FRESHNESS (L1.28a). A missing file, an unreadable head, a head with
no such key or a value that does not parse as a time all come back as `None` with the reason, and
every caller treats that as UNMEASURED -- which fails a fence, never passes it.
"""
from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

#: How much of the file is read. The stamp is the first key; 64 KiB is generous for any header.
HEAD_BYTES = 64 * 1024


def read_head_stamp(path: Path | str, key: str,
                    head_bytes: int = HEAD_BYTES) -> tuple[datetime | None, str]:
    """(stamp as an aware UTC datetime, how it was read) or (None, why it could not be).

    The first `"key": "<value>"` in the first `head_bytes` of the file is taken. A naive stamp is
    read as UTC (the desk's writers stamp UTC), and a value that is not ISO-8601 is unreadable.
    """
    p = Path(path)
    try:
        with p.open("rb") as fh:
            head = fh.read(max(1, int(head_bytes)))
    except FileNotFoundError:
        return None, f"UNMEASURED: {p} does not exist"
    except OSError as exc:
        return None, f"UNMEASURED: {p} unreadable ({type(exc).__name__}: {exc})"
    text = head.decode("utf-8-sig", errors="replace")
    m = re.search(r'"' + re.escape(key) + r'"\s*:\s*"([^"\\]{1,64})"', text)
    if m is None:
        return None, (f"UNMEASURED: no {key!r} stamp in the first {len(head):,} bytes of {p} "
                      "(the producer's content stamp is absent or not at the head)")
    raw = m.group(1).strip()
    try:
        stamp = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None, f"UNMEASURED: {key}={raw!r} in {p} is not an ISO-8601 time"
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=UTC)
    return stamp.astimezone(UTC), f"{key}={raw} read from the file head"


def stamp_age_min(path: Path | str, key: str, now: datetime | None = None,
                  head_bytes: int = HEAD_BYTES) -> tuple[float | None, str]:
    """(age of the content stamp in minutes, how) or (None, why UNMEASURED).

    A stamp in the future (clock skew, or a forged stamp) is UNMEASURED, not "fresh": a producer
    cannot have finished a pass that has not happened yet.
    """
    stamp, how = read_head_stamp(path, key, head_bytes)
    if stamp is None:
        return None, how
    ref = now or datetime.now(UTC)
    age = (ref - stamp).total_seconds() / 60.0
    if age < -5.0:
        return None, f"UNMEASURED: {how} is {-age:.0f} min in the future"
    return max(0.0, age), how
