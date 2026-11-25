"""ONE WRITER AT A TIME ON A FORWARD LEDGER, AND NO WRITER DROPS ANOTHER'S ROWS (invariant I1).

The forward ledgers -- reports/shadow/shadow_state.json, scalp_shadow_state.json and
qquant_shadow_state.json -- have many writers: the engines (`shadow_forward`, `scalp_shadow`,
`qquant_shadow`), the certification transaction and the coverage backfill
(`clock_coverage`), the orchestrator's forward_start stamp (`shadow_cycle`), the reconciler
(`forward_reconcile`), the retired-row evacuator (`retired_clocks`), the liveness retirer
(`clock_liveness`), the identity stamper (`certificate_truth`), the promoter (sealed; its hunk
is in the clock-coverage SEAL_CLEAR patch) and the one-shot repair scripts.

Every one of them used to READ the file, work, and REPLACE the whole file. Two of them
overlapping is a LOST UPDATE: the later replace carries the earlier reader's stale copy, so a
clock the other writer opened in between -- a freshly certified clock, say -- silently
disappears. That is a certified survivor without a clock, the exact fault I1 forbids.

So every writer now goes through one of two doors, both under `state_lock(path)`:

  * `update(path, mutate)`   -- read the file FRESH under the lock, apply `mutate`, write. For a
                                writer whose change is local to the rows it finds.
  * `merge_write(path, base, after)` -- a THREE-WAY merge for a writer that read long before it
                                writes: only the keys it CHANGED, ADDED or REMOVED relative to
                                its own `base` snapshot are applied to the file as it is NOW;
                                every other key -- including rows another writer added meanwhile
                                -- is kept. Nested row containers (`sleeves`) merge one level in.

The lock is a sibling `.<name>.lock` file (O_CREAT|O_EXCL), broken when older than `stale_s`
(a dead writer). A lock that cannot be had in `timeout_s` is logged and the write proceeds:
an unwritten ledger froze the forward book before, and a row lost that way is re-opened by the
hourly clock backfill and reported RED on CLOCK_COVERAGE.json until it is.
"""
from __future__ import annotations

import contextlib
import copy
import json
import os
import stat
import sys
import time
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

#: Containers whose VALUES are clock rows, merged one level in (scalp keeps its clocks here).
NESTED = ("sleeves",)


def _log(msg: str) -> None:
    print(f"ledger_lock: {msg}", file=sys.stderr, flush=True)


@contextlib.contextmanager
def state_lock(path: Path | str, timeout_s: float = 30.0,
               stale_s: float = 300.0) -> Iterator[bool]:
    """Hold the ledger's lock for one read-merge-write. Yields whether it was acquired."""
    path = Path(path)
    lock = path.with_name(f".{path.name}.lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout_s
    fd: int | None = None
    while True:
        try:
            fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, f"{os.getpid()} {datetime.now(UTC).isoformat()}".encode())
            break
        except FileExistsError:
            try:
                age = time.time() - lock.stat().st_mtime
            except OSError:
                continue                  # released between the two calls: try again
            if age > stale_s:
                with contextlib.suppress(OSError):
                    lock.unlink()
                continue
            if time.monotonic() >= deadline:
                _log(f"{lock.name} not acquired in {timeout_s:.0f}s; writing unlocked")
                break
            time.sleep(0.05)
        except OSError as exc:
            _log(f"{lock.name} unavailable ({type(exc).__name__}); writing unlocked")
            break
    try:
        yield fd is not None
    finally:
        if fd is not None:
            os.close(fd)
            with contextlib.suppress(OSError):
                lock.unlink()


def read(path: Path | str, attempts: int = 3) -> dict | None:
    """The ledger on disk; {} when absent; None when it exists and cannot be read."""
    path = Path(path)
    for i in range(max(1, attempts)):
        if not path.exists():
            return {}
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
            return doc if isinstance(doc, dict) else None
        except (OSError, ValueError):
            if i + 1 < attempts:
                time.sleep(0.2)
    return None


def write_text(path: Path | str, text: str) -> None:
    """Write-then-replace, Windows-safe (retries a sharing/read-only refusal, then in place)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(text, encoding="utf-8")
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


def snapshot(doc: Any) -> Any:
    """The writer's `base` for `merge_write`: a deep copy of what it read."""
    return copy.deepcopy(doc)


_ABSENT = object()


def merge(disk: dict, base: dict, after: dict, nested: tuple[str, ...] = NESTED) -> dict:
    """Apply to `disk` exactly the changes `after` makes relative to `base`."""
    out = dict(disk)
    for key in set(base) | set(after):
        b = base.get(key, _ABSENT)
        a = after.get(key, _ABSENT)
        if a is _ABSENT:
            if b is not _ABSENT:
                out.pop(key, None)                 # the writer removed it
            continue
        if b is not _ABSENT and a == b:
            continue                               # untouched by this writer: disk wins
        if (key in nested and isinstance(a, dict) and isinstance(b, dict)
                and isinstance(out.get(key), dict)):
            out[key] = merge(out[key], b, a, ())
        else:
            out[key] = a
    return out


def merge_write(path: Path | str, base: dict | None, after: dict, *, indent: int | None = 2,
                nested: tuple[str, ...] = NESTED) -> dict:
    """Three-way merge `after` onto the ledger as it is NOW, under the lock. `base` None (the
    writer had no readable snapshot) writes `after` whole, the pre-lock behaviour."""
    path = Path(path)
    with state_lock(path):
        disk = read(path)
        doc = dict(after) if (disk is None or base is None) else merge(disk, base, after, nested)
        write_text(path, json.dumps(doc, indent=indent, default=str))
    return doc


def update(path: Path | str, mutate: Callable[[dict], Any], *, indent: int | None = 2) -> Any:
    """Read the ledger FRESH under the lock, let `mutate(doc)` change it in place, and write it
    when `mutate` returns a truthy value. Returns that value. An unreadable ledger is never
    overwritten: `mutate` is not called and None is returned."""
    path = Path(path)
    with state_lock(path):
        doc = read(path)
        if doc is None:
            _log(f"{path.name} unreadable; not rewritten")
            return None
        changed = mutate(doc)
        if changed:
            write_text(path, json.dumps(doc, indent=indent, default=str))
        return changed
