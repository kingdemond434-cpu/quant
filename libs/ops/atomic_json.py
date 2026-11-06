"""Atomic JSON writes that survive Windows, and a lock for read-modify-write state.

Audit of 538cb964, SF11: three LLM-lab organs wrote state through a FIXED `<name>.tmp` and a bare
`os.replace`. Two writers sharing that temp name clobber each other's half-written file, and on
the trading box `os.replace` onto a file another process holds open raises WinError 5, so the
write is lost. One of those files is `evidence_start.json`, which the look-ahead trim reads, so a
lost write there is a contaminated window counted as evidence.
"""
from __future__ import annotations

import contextlib
import json
import os
import threading
import time
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

#: A lock older than this is a crashed holder's, and is broken.
STALE_LOCK_S = 120.0
REPLACE_TRIES = 5


def write_text(path: Path, body: str) -> None:
    """Write `body` to `path` through a temp file unique to this process and thread."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}."
                         f"{uuid.uuid4().hex[:8]}.tmp")
    tmp.write_text(body, encoding="utf-8", newline="")
    try:
        for i in range(REPLACE_TRIES):
            try:
                os.replace(tmp, path)
                return
            except PermissionError:                 # WinError 5: a reader holds the target
                time.sleep(0.05 * (i + 1))
        path.write_text(body, encoding="utf-8", newline="")   # last resort: in place, never lost
    finally:
        with contextlib.suppress(OSError):
            tmp.unlink(missing_ok=True)


def write_json(path: Path, doc: Any, *, indent: int = 1) -> None:
    write_text(path, json.dumps(doc, indent=indent, ensure_ascii=False, default=str) + "\n")


@contextlib.contextmanager
def locked(path: Path, *, timeout_s: float = 30.0) -> Iterator[None]:
    """Hold `<path>.lock` (created exclusively) for a read-modify-write of `path`.

    Raises TimeoutError when another live holder keeps it past `timeout_s`; a lock older than
    STALE_LOCK_S is a dead holder's and is broken.
    """
    lock = path.with_name(path.name + ".lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout_s
    while True:
        try:
            fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            break
        except FileExistsError:
            with contextlib.suppress(OSError):
                if time.time() - lock.stat().st_mtime > STALE_LOCK_S:
                    lock.unlink(missing_ok=True)
                    continue
            if time.monotonic() > deadline:
                raise TimeoutError(f"{lock} held past {timeout_s}s") from None
            time.sleep(0.05)
    try:
        yield
    finally:
        with contextlib.suppress(OSError):
            lock.unlink(missing_ok=True)
