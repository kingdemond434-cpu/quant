"""Rotate the desk's append-only logs before they eat the disk and every tail read -- and keep
every byte of them.

Measured on the trading box 2026-09-29: MT5-Gauntlet.log 1.48 GB, deepening_worker.log 629 MB,
a convert-lane log 583 MB, and nothing ever rotated any of them. Every diagnostic that reads a
log tail seeks through them, and they only grow.

WHY RENAME, NEVER TRUNCATE IN PLACE. Scheduled tasks append with `cmd >> log`, and that handle
keeps its own file position: truncating under it makes the next write land at the old offset,
back-filling the file with zeros. A log is therefore rotated only when a rename succeeds, which
Windows allows only while no process holds it open -- between runs of a task. A log that is busy
is skipped and retried on the next run; nothing is lost and nothing is corrupted.

NOTHING IS DISCARDED (2026-11-13, standing rule "never delete ledgers or evidence"). The version
before this kept only the last 200 MB of a rotated log and REPLACED the previous rotation, so
every rotation destroyed history. Now the WHOLE rotated file is gzip-compressed into
`logs/archive/<name>.<UTC stamp>.gz`, never overwriting an existing archive, and the uncompressed
staging copy is removed only after the archive has been read back and its SHA-256 and length
match the original byte for byte. Any failure leaves the staging file in place (named
`<log>.rotating`), and the next run archives it first. Logs compress ~10x, so the disk still
gets back ~90% of what rotation used to free; the archive folder grows without bound by design
and is visible to the disk monitors.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO

DESK = Path(__file__).resolve().parents[1] / "desks" / "mt5"
LOG_DIRS = (DESK / "logs",)
MAX_BYTES = 256 * 1024 * 1024
CHUNK = 8 * 1024 * 1024


def _digest(fh: BinaryIO | gzip.GzipFile) -> tuple[str, int]:
    h, n = hashlib.sha256(), 0
    while chunk := fh.read(CHUNK):
        h.update(chunk)
        n += len(chunk)
    return h.hexdigest(), n


def _archive_path(archive_dir: Path, name: str, now: datetime) -> Path:
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    p = archive_dir / f"{name}.{stamp}.gz"
    i = 1
    while p.exists():  # never overwrite an archive
        p = archive_dir / f"{name}.{stamp}.{i}.gz"
        i += 1
    return p


def archive(staging: Path, archive_dir: Path, name: str, now: datetime) -> Path:
    """gzip `staging` into a new archive, verify it, then remove `staging`. Raises on mismatch."""
    archive_dir.mkdir(parents=True, exist_ok=True)
    dst = _archive_path(archive_dir, name, now)
    tmp = dst.with_name(dst.name + ".partial")
    with open(staging, "rb") as src, gzip.open(tmp, "wb", compresslevel=6) as gz:
        shutil.copyfileobj(src, gz, CHUNK)
    with open(staging, "rb") as a, gzip.open(tmp, "rb") as b:
        if _digest(a) != _digest(b):
            tmp.unlink()
            raise OSError(f"archive of {staging.name} did not read back identical; staging kept")
    os.replace(tmp, dst)
    staging.unlink()
    return dst


def rotate(path: Path, *, max_bytes: int = MAX_BYTES, now: datetime | None = None) -> str:
    now = now or datetime.now(UTC)
    archive_dir = path.parent / "archive"
    staging = path.with_name(path.name + ".rotating")
    try:
        if staging.exists():  # a previous run stopped before its archive was verified
            archive(staging, archive_dir, path.name, now)
    except OSError:
        return "stuck"
    try:
        if path.stat().st_size <= max_bytes:
            return "small"
    except OSError:
        return "gone"
    try:
        os.replace(path, staging)  # fails while any process holds the log open
    except OSError:
        return "busy"
    try:
        archive(staging, archive_dir, path.name, now)
    except OSError:
        return "stuck"
    return "rotated"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-mb", type=int, default=MAX_BYTES // (1024 * 1024))
    ap.add_argument("--dir", type=Path, action="append", help="log folder (default: desk logs)")
    args = ap.parse_args(argv)
    stuck = 0
    for d in args.dir or LOG_DIRS:
        if not d.is_dir():
            continue
        # a leftover `<log>.rotating` whose log is gone must still be archived (or reported stuck)
        bases = set(d.glob("*.log")) | {s.with_suffix("") for s in d.glob("*.log.rotating")}
        for p in sorted(bases):
            verdict = rotate(p, max_bytes=args.max_mb * 1024 * 1024)
            if verdict in ("rotated", "busy", "stuck"):
                print(f"{verdict:8s} {p.name}")
            stuck += verdict == "stuck"
    # a log that cannot be archived is a failure the scheduler must see, never a quiet exit 0
    return 2 if stuck else 0


if __name__ == "__main__":
    raise SystemExit(main())
