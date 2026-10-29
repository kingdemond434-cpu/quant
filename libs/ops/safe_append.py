"""APPEND ONE LINE TO A SHARED LOG, AND NEVER RAISE (2026-10-29).

MEASURED on the box (2026-10-29): MT5-FusionDeadman exited 1 intermittently because
`fusion_deadman.log()` did a bare `BREACH_LOG.open("a")` while the sibling deadman passes, fired by
Task Scheduler in the same second, held the same file -- a Windows sharing violation, reported by
Python as `PermissionError [Errno 13]`. POSIX allows concurrent appends, so nothing off the box
reproduces it. A DIAGNOSTIC log line is never worth a pass: the pass's own work (a stamp, a
gateway reconcile) already happened or is about to, and losing it to a log write is the failure.

`append_line(path, line)`: create the parent, append `line` + newline, retrying a refused open
with a short linear backoff; if every attempt is refused, write the line to stderr (which a
scheduled task's own `>> logs\\<Task>.log 2>&1` redirect captures) and return False. It never
raises. Use it for LOG LINES only. A LEDGER row a reader depends on must not be dropped
silently: keep those on a writer that raises, or count the failure (cf. mt5desk/fusion_rails.line).
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ATTEMPTS = 3
BACKOFF_S = 0.1


def append_line(path: Path | str, line: str, *, encoding: str = "utf-8",
                attempts: int = ATTEMPTS, backoff_s: float = BACKOFF_S) -> bool:
    """Append `line` to `path`; True when written. Never raises (see the module docstring)."""
    p = Path(path)
    last: BaseException | None = None
    for i in range(max(1, attempts)):
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            with p.open("a", encoding=encoding) as fh:
                fh.write(line + "\n")
            return True
        except (OSError, ValueError) as exc:
            last = exc
            if i + 1 < max(1, attempts):
                time.sleep(backoff_s * (i + 1))
    try:
        errno = getattr(last, "errno", None)
        print(f"log write to {p.name} failed ({type(last).__name__}"
              f"{f' errno={errno}' if isinstance(errno, int) else ''}): {line}",
              file=sys.stderr, flush=True)
    except (OSError, ValueError, AttributeError):
        pass
    return False
