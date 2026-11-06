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


class ReplaceFailed(OSError):
    """The rename onto the target never succeeded. The new body is still in `tmp`, which is
    KEPT (audit must-fix on 37bb136b4): an in-place write would be a torn file the next reader
    parses as half a document, so the writer raises and the caller's leg reports it."""

    def __init__(self, path: Path, tmp: Path, last: BaseException) -> None:
        super().__init__(f"could not replace {path} after {REPLACE_TRIES} tries "
                         f"({type(last).__name__}: {last}); the new body is kept at {tmp}")
        self.path = path
        self.tmp = tmp


def write_text(path: Path, body: str) -> None:
    """Write `body` to `path` through a temp file unique to this process and thread. The target
    is only ever replaced whole; never written in place."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}."
                         f"{uuid.uuid4().hex[:8]}.tmp")
    try:
        tmp.write_text(body, encoding="utf-8", newline="")
    except BaseException:
        with contextlib.suppress(OSError):
            tmp.unlink(missing_ok=True)
        raise
    last: BaseException | None = None
    for i in range(REPLACE_TRIES):
        try:
            os.replace(tmp, path)
            return
        except PermissionError as exc:              # WinError 5: a reader holds the target
            last = exc
            time.sleep(0.05 * (i + 1))
    raise ReplaceFailed(path, tmp, last or PermissionError("replace refused"))


def write_json(path: Path, doc: Any, *, indent: int = 1) -> None:
    write_text(path, json.dumps(doc, indent=indent, ensure_ascii=False, default=str) + "\n")


def _break_stale(lock: Path) -> bool:
    """Break a dead holder's lock so that exactly one waiter wins (audit SF3 on 37bb136b4).
    Each waiter RENAMES the stale lock to a name unique to itself; the rename is atomic, so
    only one succeeds, and only that one unlinks it and retries. A plain unlink let two
    waiters each delete the lock -- the second deleting the first's fresh one -- and both
    proceed."""
    try:
        st = lock.stat()
    except OSError:
        return True                                # gone already: retry the create
    if time.time() - st.st_mtime <= STALE_LOCK_S:
        return False
    grave = lock.with_name(f"{lock.name}.{os.getpid()}.{uuid.uuid4().hex[:8]}.stale")
    try:
        os.rename(lock, grave)
    except OSError:
        return False                               # another waiter won; wait for its release
    try:
        moved = grave.stat()
        same = (moved.st_ino, moved.st_mtime) == (st.st_ino, st.st_mtime)
    except OSError:
        same = False
    if not same:
        # Between our stat and our rename another waiter broke the stale lock and took a
        # fresh one, and we moved THAT. Put it back (link fails if yet another lock exists).
        with contextlib.suppress(OSError):
            os.link(grave, lock)
        with contextlib.suppress(OSError):
            grave.unlink(missing_ok=True)
        return False
    with contextlib.suppress(OSError):
        grave.unlink(missing_ok=True)
    return True


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
            if _break_stale(lock):
                continue
            if time.monotonic() > deadline:
                raise TimeoutError(f"{lock} held past {timeout_s}s") from None
            time.sleep(0.05)
    try:
        yield
    finally:
        with contextlib.suppress(OSError):
            lock.unlink(missing_ok=True)
