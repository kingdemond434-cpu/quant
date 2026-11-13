"""Write a forward ledger whole and at once: a reader sees the old file or the new one, never half.

WHY (2026-11-11, the Auditor's condition 4 on the 77 immutable-evidence breaches). The three
forward engines (shadow_forward, qquant_shadow, scalp_shadow) rewrite each
reports/shadow/ledger_*.json in full every pass with a bare `write_text`, which truncates first.
A crash, reboot or kill mid-write (the box logged six unexpected shutdowns between 09-29 and
10-22) leaves a short or empty ledger. The record seal then reads that as moved evidence, and
the promoter reads it as a clock with fewer trades.

Same Windows rule as shadow_forward._atomic_write_text: `os.replace` onto a read-only file, or
one a reader holds open without FILE_SHARE_DELETE, raises WinError 5. So it retries, clears
read-only between tries, and only then writes in place, because an unwritten ledger freezes the
forward book. No dependencies, so every engine can import it.
"""
from __future__ import annotations

import contextlib
import os
import stat
import time
from pathlib import Path


def write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    try:
        for i in range(8):
            try:
                os.replace(tmp, path)
                return
            except PermissionError:
                with contextlib.suppress(OSError):
                    os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
                time.sleep(0.1 * (i + 1))
        path.write_text(text, encoding="utf-8")
    finally:
        with contextlib.suppress(OSError):
            tmp.unlink()
