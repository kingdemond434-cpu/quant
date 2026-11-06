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

#: A temp file a failed replace kept (ReplaceFailed) is swept after this long.
TMP_SWEEP_S = 86400.0
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


def _sweep_kept(path: Path) -> None:
    """Remove this target's temp files older than TMP_SWEEP_S (audit should-fix 2 on
    4e4cdc972): a body ReplaceFailed kept is for the pass that raised it, and over many passes
    they would pile up beside the target."""
    cutoff = time.time() - TMP_SWEEP_S
    for old in path.parent.glob(f"{path.name}.*.tmp"):
        with contextlib.suppress(OSError):
            if old.stat().st_mtime < cutoff:
                old.unlink()


def write_text(path: Path, body: str) -> None:
    """Write `body` to `path` through a temp file unique to this process and thread. The target
    is only ever replaced whole; never written in place."""
    path.parent.mkdir(parents=True, exist_ok=True)
    _sweep_kept(path)
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


@contextlib.contextmanager
def locked(path: Path, *, timeout_s: float = 30.0) -> Iterator[None]:
    """Hold an OS lock on `<path>.lock` for a read-modify-write of `path`.

    THE KERNEL HOLDS IT, NOT A FILE'S EXISTENCE (audit should-fix 1 on 4e4cdc972). An O_EXCL
    lockfile needs a stale-lock breaker, and every breaker leaves a window in which a third
    waiter can take a lock while a live holder still writes. An fcntl/msvcrt lock is released
    by the OS the moment its holder exits, however it dies, so nothing is ever "stale" and
    nothing is ever broken. The lock FILE is left in place on release on purpose: unlinking it
    would let a waiter lock an inode that a newcomer can no longer see.

    Raises TimeoutError when another live holder keeps it past `timeout_s`.
    """
    lock = path.with_name(path.name + ".lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout_s
    fd = os.open(str(lock), os.O_CREAT | os.O_RDWR)
    try:
        while not _try_lock(fd):
            if time.monotonic() > deadline:
                raise TimeoutError(f"{lock} held past {timeout_s}s")
            time.sleep(0.05)
        try:
            yield
        finally:
            _unlock(fd)
    finally:
        os.close(fd)


def _try_lock(fd: int) -> bool:
    try:
        if os.name == "nt":
            import msvcrt
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)   # type: ignore[attr-defined]
        else:
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        return False


def _unlock(fd: int) -> None:
    with contextlib.suppress(OSError):
        if os.name == "nt":
            import msvcrt
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)   # type: ignore[attr-defined]
        else:
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_UN)
