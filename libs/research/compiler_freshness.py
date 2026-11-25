"""How old is the compiled candidate file, read without parsing the 40 MB of it.

WHY (2026-11-25). `desks/mt5/data/hypotheses/miner_candidates.json` was not recompiled after
2026-10-03 10:11Z. The compiler's only clock was the `compile_candidates` leg, killed at its
720 s cap every pass, so the old file stayed in place and every reader (the merger, the
conversion audit, the judge's never-judged supply) kept consuming it as if it were current.
A stale artifact that looks like a current one is the failure; this module is how it is told
apart. `compiled_at` is the file's first key and `freshness` its second, so a 4 KB head read is
enough. An unreadable or unstamped file is UNMEASURED, never fresh (L1.28a).
"""
from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

#: The age past which the compiler is read as dead. Two hours = two missed hourly clocks.
MAX_AGE_S = 7200
_HEAD_BYTES = 4096
_STAMP = re.compile(r'"compiled_at"\s*:\s*"([^"]+)"')


def compiled_at(path: Path) -> datetime | None:
    """`compiled_at` of the artifact at `path`, or None when absent, unreadable or unstamped."""
    try:
        with open(path, "rb") as handle:
            head = handle.read(_HEAD_BYTES).decode("utf-8", errors="replace")
        hit = _STAMP.search(head)
        if not hit:
            return None
        stamp = datetime.fromisoformat(hit.group(1))
    except (OSError, ValueError):
        return None
    return stamp if stamp.tzinfo else stamp.replace(tzinfo=UTC)


def age_s(path: Path, now: datetime | None = None) -> float | None:
    """Seconds since `compiled_at`; None means UNMEASURED (absent / unreadable / unstamped)."""
    stamp = compiled_at(path)
    if stamp is None:
        return None
    return max(0.0, ((now or datetime.now(UTC)) - stamp).total_seconds())


def is_fresh(path: Path, now: datetime | None = None, max_age_s: float = MAX_AGE_S) -> bool:
    """True only on a MEASURED age within `max_age_s`; UNMEASURED is never fresh."""
    age = age_s(path, now)
    return age is not None and age <= max_age_s
