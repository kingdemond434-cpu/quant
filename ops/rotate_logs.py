"""Rotate the desk's append-only logs before they eat the disk and every tail read.

Measured on the trading box 2026-09-29: MT5-Gauntlet.log 1.48 GB, deepening_worker.log 629 MB,
a convert-lane log 583 MB, and nothing ever rotated any of them. Every diagnostic that reads a
log tail seeks through them, and they only grow.

WHY RENAME, NEVER TRUNCATE IN PLACE. Scheduled tasks append with `cmd >> log`, and that handle
keeps its own file position: truncating under it makes the next write land at the old offset,
back-filling the file with zeros. A log is therefore rotated only when a rename succeeds, which
Windows allows only while no process holds it open -- between runs of a task. A log that is busy
is skipped and retried on the next tick; nothing is lost and nothing is corrupted.

The rotated copy keeps its last KEEP_BYTES (the recent history a human or a probe actually
reads); the previous rotation is replaced.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

LOG_DIRS = (Path(r"C:\opt\quant\desks\mt5\logs"),)
MAX_BYTES = 256 * 1024 * 1024
KEEP_BYTES = 200 * 1024 * 1024


def _keep_tail(path: Path, keep: int) -> None:
    size = path.stat().st_size
    if size <= keep:
        return
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(path, "rb") as src, open(tmp, "wb") as dst:
        src.seek(size - keep)
        src.readline()  # start on a whole line
        while chunk := src.read(8 * 1024 * 1024):
            dst.write(chunk)
    os.replace(tmp, path)


def rotate(path: Path, *, max_bytes: int = MAX_BYTES, keep: int = KEEP_BYTES) -> str:
    try:
        if path.stat().st_size <= max_bytes:
            return "small"
    except OSError:
        return "gone"
    rotated = path.with_name(path.name + ".1")
    staging = path.with_name(path.name + ".rotating")
    try:
        os.replace(path, staging)  # fails while any process holds the log open
    except OSError:
        return "busy"
    _keep_tail(staging, keep)
    os.replace(staging, rotated)
    return "rotated"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-mb", type=int, default=MAX_BYTES // (1024 * 1024))
    ap.add_argument("--keep-mb", type=int, default=KEEP_BYTES // (1024 * 1024))
    args = ap.parse_args(argv)
    for d in LOG_DIRS:
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.log")):
            verdict = rotate(p, max_bytes=args.max_mb * 1024 * 1024,
                             keep=args.keep_mb * 1024 * 1024)
            if verdict in ("rotated", "busy"):
                print(f"{verdict:8s} {p.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
