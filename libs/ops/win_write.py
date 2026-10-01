"""WRITE A FILE ON WINDOWS WHILE SOMEONE ELSE IS READING IT (2026-09-30).

MEASURED in the last shadow_health.json the box published (2026-09-16T16:37:33Z, status FAILED):

    scalp_bar_refresh:        PermissionError: [Errno 13] Permission denied:
                              'C:\\opt\\quant\\desks\\mt5\\data\\universe\\XAUUSD_M1.parquet'
    external_state_reconcile: PermissionError: [Errno 13] Permission denied:
                              'C:\\opt\\quant\\desks\\mt5\\reports\\shadow\\external_shadow_state.json'

Both are in-place overwrites of files other organs read continuously (the scalp lane, the
gateway resident, the sync's `git add`, the census). On Windows, opening a file for writing while
another process holds it open without FILE_SHARE_WRITE is a SHARING VIOLATION, and Python reports
that as PermissionError errno 13 -- as it does WinError 5 for `os.replace` onto a read-only or
held destination. POSIX allows all of it, so nothing off the box ever reproduces it. One such
error in `shadow_cycle.run` marks the whole census FAILED and exits 1, and stall_watch then logs
"FAILING MT5-Shadow: last result 1 twice in a row" every ten minutes about a lane whose clocks
had in fact advanced.

`write_bytes_resilient` / `write_text_resilient`: write a sibling temp file, `os.replace` it over
the target with a short backoff (clearing a read-only bit between tries), and only if the rename
is still refused fall back to an in-place write, also retried. A reader therefore sees the old
file or the new one, and a transient hold costs a second rather than the pass. The last error is
re-raised only when every attempt failed -- a writer that swallowed it would be the silent
failure this desk keeps paying for.
"""
from __future__ import annotations

import contextlib
import os
import stat
import time
from pathlib import Path

ATTEMPTS = 8
BACKOFF_S = 0.25


def _clear_readonly(path: Path) -> None:
    with contextlib.suppress(OSError):
        os.chmod(path, stat.S_IWRITE | stat.S_IREAD)


def replace_resilient(tmp: Path, dest: Path, *, attempts: int = ATTEMPTS,
                      backoff_s: float = BACKOFF_S) -> None:
    """`os.replace(tmp, dest)`, retried through Windows sharing/read-only refusals.

    If every rename is refused, copies `tmp`'s bytes over `dest` in place (retried), then removes
    `tmp`. Raises the last PermissionError only when that fails too.
    """
    last: OSError | None = None
    for i in range(max(1, attempts)):
        try:
            os.replace(tmp, dest)
            return
        except PermissionError as exc:
            last = exc
            _clear_readonly(dest)
            time.sleep(backoff_s * (i + 1))
    data = Path(tmp).read_bytes()
    try:
        for i in range(max(1, attempts)):
            try:
                with open(dest, "wb") as fh:
                    fh.write(data)
                return
            except PermissionError as exc:
                last = exc
                _clear_readonly(dest)
                time.sleep(backoff_s * (i + 1))
    finally:
        with contextlib.suppress(OSError):
            Path(tmp).unlink()
    assert last is not None
    raise last


def write_bytes_resilient(path: Path | str, data: bytes, *, attempts: int = ATTEMPTS,
                          backoff_s: float = BACKOFF_S) -> None:
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(f".{dest.name}.{os.getpid()}.tmp")
    tmp.write_bytes(data)
    try:
        replace_resilient(tmp, dest, attempts=attempts, backoff_s=backoff_s)
    finally:
        with contextlib.suppress(OSError):
            if tmp.exists():
                tmp.unlink()


def write_text_resilient(path: Path | str, text: str, encoding: str = "utf-8", *,
                         attempts: int = ATTEMPTS, backoff_s: float = BACKOFF_S) -> None:
    write_bytes_resilient(path, text.encode(encoding), attempts=attempts, backoff_s=backoff_s)
