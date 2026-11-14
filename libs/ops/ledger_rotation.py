"""APPEND-ONLY LEDGERS ROTATE; THEY NEVER TRUNCATE.

A decision ledger that outgrows its size bound used to be cut to its newest half, which discarded
the oldest decisions -- the very before/after records a feedback-loop proof is computed from.
`rotate_if_over` instead MOVES the whole file to a dated archive beside it
(`<stem>.<YYYYMMDDTHHMMSS>.jsonl`) and leaves the live path empty for the next append. No row is
ever discarded. An archive sits in the same directory under the same stem, so a `.gitignore`
rule that covers the live file by directory or by `*.jsonl` covers its archives too.

Readers that compute a proof read `ledger_files(path)` (every archive oldest first, then the live
file) so a window that straddles a rotation still sees its rows.
"""
from __future__ import annotations

import os
import re
from datetime import UTC, datetime
from pathlib import Path

STAMP_FMT = "%Y%m%dT%H%M%S"


def _archive_rx(path: Path) -> re.Pattern[str]:
    return re.compile(rf"^{re.escape(path.stem)}\.(\d{{8}}T\d{{6}})(?:_(\d+))?"
                      rf"{re.escape(path.suffix)}$")


def archive_path(path: Path, now: datetime | None = None) -> Path:
    """The dated archive name for `path`, never one that already exists."""
    stamp = (now or datetime.now(tz=UTC)).astimezone(UTC).strftime(STAMP_FMT)
    cand = path.with_name(f"{path.stem}.{stamp}{path.suffix}")
    n = 1
    while cand.exists():
        cand = path.with_name(f"{path.stem}.{stamp}_{n}{path.suffix}")
        n += 1
    return cand


def rotate_if_over(path: Path, max_bytes: int, *, now: datetime | None = None) -> Path | None:
    """Move `path` whole to a dated archive once it exceeds `max_bytes`; return the archive.

    The move is a rename (no row is rewritten, none is dropped); the next append recreates the
    live file. Raises OSError like any file operation -- the caller decides whether that may fail
    its organ."""
    try:
        size = path.stat().st_size
    except FileNotFoundError:
        return None
    if size <= max_bytes:
        return None
    dest = archive_path(path, now)
    os.replace(path, dest)
    return dest


def archives(path: Path) -> list[Path]:
    """Every rotated archive of `path`, oldest first."""
    rx = _archive_rx(path)
    try:
        names = [(m.group(1), int(m.group(2) or 0), p) for p in path.parent.iterdir()
                 if (m := rx.match(p.name))]
    except OSError:
        return []
    return [p for _s, _n, p in sorted(names, key=lambda t: (t[0], t[1]))]


def ledger_files(path: Path) -> list[Path]:
    """The whole ledger in append order: archives oldest first, then the live file."""
    out = archives(path)
    if path.exists():
        out.append(path)
    return out
