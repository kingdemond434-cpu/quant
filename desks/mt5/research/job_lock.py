"""Cross-controller, cross-shell single-instance locks for heavy MT5 research writers."""
from __future__ import annotations

import json
import os
import socket
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
LOCK_ROOT = BASE / "data" / ".job_locks"
STALE_SECONDS = 45 * 60


@contextmanager
def exclusive_job(name: str):
    """Yield True to one writer, False to concurrent duplicates; recover stale crash locks."""
    LOCK_ROOT.mkdir(parents=True, exist_ok=True)
    path = LOCK_ROOT / f"{name}.json"
    token = uuid.uuid4().hex
    payload = json.dumps({
        "token": token, "pid": os.getpid(), "host": socket.gethostname(),
        "started_at": datetime.now(UTC).isoformat(),
    })
    owned = False
    for _attempt in range(2):
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                stale = datetime.now(UTC).timestamp() - path.stat().st_mtime > STALE_SECONDS
            except OSError:
                stale = False
            if stale:
                try:
                    path.unlink()
                except OSError:
                    pass
                continue
            print(f"{name}: REFUSED duplicate writer; active lock {path}")
            yield False
            return
        else:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
            owned = True
            break
    if not owned:
        print(f"{name}: REFUSED writer; stale lock could not be recovered")
        yield False
        return
    try:
        yield True
    finally:
        # Never delete a successor's lock after a stale-owner race.
        try:
            current = json.loads(path.read_text("utf-8"))
            if current.get("token") == token:
                path.unlink()
        except (OSError, ValueError, AttributeError):
            pass
