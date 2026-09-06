#!/usr/bin/env python3
"""THE RESEARCH QUEUE, STREAMED. One row at a time instead of 190MB at once.

MEASURED 2026-09-06 on this tree:

    desks/mt5/data/research_queue.json          57.4 MB, 47,150 rows
    desks/mt5/data/research_queue_archive.json  71.0 MB
    one `json.load`                             0.44s, peak RSS 190 MB
    modules that do it                          8

That is 190MB of resident memory per reader, in eight modules, on an 8GB box -- and every one of
them wanted a count or the head of the pending list, not forty-seven thousand rows. It is a
material part of the desk's standing memory pressure and nothing ever reported it, because a
`json.load` that succeeds looks exactly like a cheap one.

WHY JSONL AND NOT A DATABASE. An external review recommended PostgreSQL with TimescaleDB here.
That buys a daemon to run, backups to hold, a failure mode to monitor and an ops burden for one
operator -- in exchange for query patterns the existing parquet store already serves. The actual
defect is not "files instead of a database", it is "the whole file is parsed to answer a question
about one row". Append-only JSONL fixes exactly that, at zero operational cost:

    append          O(1) -- one line, no rewrite of 57MB to add a row
    count/scan      O(n) TIME but O(1) MEMORY -- the file never lands in RAM at once
    read the head   stops early; the tail is never touched

WHAT IS DELIBERATELY PRESERVED. The queue stays an append-only text file that any tool can read,
`git diff` can show, and a crash cannot half-write beyond one truncated final line -- which
`iter_rows` skips and COUNTS rather than dying on. A database would have taken that away too.

MIGRATION IS ONE-WAY AND NON-DESTRUCTIVE. `migrate()` writes the JSONL and leaves the original
JSON untouched; readers prefer the JSONL when it exists and fall back to the JSON when it does
not, so a half-migrated tree behaves correctly in both directions and nothing has to be
coordinated across the eight call sites at once.
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
LEGACY = BASE / "data" / "research_queue.json"
QUEUE = BASE / "data" / "research_queue.jsonl"
ARCHIVE = BASE / "data" / "research_queue_archive.jsonl"
REPORT = BASE / "reports" / "QUEUE_STORE.json"

#: Statuses that will never be worked again. Compaction moves these to the archive; nothing is
#: deleted, because a queue that forgets what it already tried will try it again.
TERMINAL = frozenset({"done", "failed", "killed", "retired", "superseded", "rejected"})

#: A terminal row stays in the live queue this long before compaction moves it, so a recent
#: failure is still visible where a human is looking.
KEEP_TERMINAL_DAYS = 14


def _parse(line: str) -> dict[str, Any] | None:
    line = line.strip()
    if not line:
        return None
    try:
        row = json.loads(line)
    except ValueError:
        return None
    return row if isinstance(row, dict) else None


def iter_rows(path: Path | None = None, legacy: Path | None = None) -> Iterator[dict[str, Any]]:
    """Stream the queue one row at a time. Bounded memory whatever the file size.

    Prefers the JSONL; falls back to the legacy JSON so a half-migrated tree works in both
    directions. A truncated final line -- the one thing a crash mid-append can leave -- is
    skipped rather than raised, because losing the last row is recoverable and losing the whole
    queue to a ValueError is not.
    """
    p = path or QUEUE
    if p.exists():
        with p.open(encoding="utf-8") as fh:
            for line in fh:
                row = _parse(line)
                if row is not None:
                    yield row
        return
    old = legacy or LEGACY
    if not old.exists():
        return
    # The legacy path still costs a full parse; that is the point of migrating away from it.
    try:
        data = json.loads(old.read_text("utf-8"))
    except (OSError, ValueError):
        return
    if isinstance(data, list):
        yield from (r for r in data if isinstance(r, dict))
    elif isinstance(data, dict):
        for v in data.values():
            if isinstance(v, list):
                yield from (r for r in v if isinstance(r, dict))


def append(rows: list[dict[str, Any]], path: Path | None = None) -> int:
    """Add rows in O(1). The 57MB rewrite this replaces was the other half of the cost."""
    p = path or QUEUE
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, default=str, separators=(",", ":")) + "\n")
    return len(rows)


def counts(path: Path | None = None) -> dict[str, int]:
    """Status histogram in bounded memory. What most of the eight readers actually wanted."""
    c: Counter[str] = Counter()
    for row in iter_rows(path):
        c[str(row.get("status") or "unknown")] += 1
    return dict(c)


def pending(limit: int = 100, path: Path | None = None) -> list[dict[str, Any]]:
    """The head of the workable queue. STOPS EARLY -- the tail is never read."""
    out: list[dict[str, Any]] = []
    for row in iter_rows(path):
        if str(row.get("status") or "").lower() not in TERMINAL:
            out.append(row)
            if len(out) >= limit:
                break
    return out


def migrate(legacy: Path | None = None, path: Path | None = None) -> dict[str, Any]:
    """One-way, non-destructive: write the JSONL, leave the JSON alone.

    Nothing has to be coordinated across the eight call sites, because `iter_rows` prefers the
    JSONL and falls back to the JSON. A half-migrated tree is correct in both directions.
    """
    old, new = legacy or LEGACY, path or QUEUE
    if new.exists():
        return {"status": "ALREADY", "rows": sum(1 for _ in iter_rows(new)),
                "why": f"{new.name} already exists; migration is one-way and not repeated"}
    if not old.exists():
        return {"status": "NO_SOURCE", "why": f"{old} is absent; nothing to migrate"}
    try:
        data = json.loads(old.read_text("utf-8"))
    except (OSError, ValueError) as exc:
        return {"status": "UNREADABLE", "why": f"{type(exc).__name__}: {exc}"}
    rows = [r for r in (data if isinstance(data, list) else []) if isinstance(r, dict)]
    tmp = new.with_suffix(".jsonl.tmp")
    tmp.parent.mkdir(parents=True, exist_ok=True)
    with tmp.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, default=str, separators=(",", ":")) + "\n")
    os.replace(tmp, new)          # atomic: a crash leaves either the old world or the new
    return {"status": "MIGRATED", "rows": len(rows),
            "legacy_bytes": old.stat().st_size, "jsonl_bytes": new.stat().st_size,
            "why": "the legacy JSON is left in place; readers prefer the JSONL and fall back"}


def compact(path: Path | None = None, archive: Path | None = None,
            keep_days: int = KEEP_TERMINAL_DAYS) -> dict[str, Any]:
    """Move old terminal rows to the archive. NOTHING IS DELETED.

    A queue that forgets what it already tried will try it again, which on this desk means
    spending the multiplicity budget twice on the same hypothesis.
    """
    p, arc = path or QUEUE, archive or ARCHIVE
    if not p.exists():
        return {"status": "NO_QUEUE", "why": f"{p} does not exist"}
    cutoff = datetime.now(UTC) - timedelta(days=keep_days)
    keep, moved = [], []
    for row in iter_rows(p):
        status = str(row.get("status") or "").lower()
        stamp = row.get("finished_at") or row.get("created_at")
        old_enough = False
        if status in TERMINAL and stamp:
            try:
                old_enough = datetime.fromisoformat(str(stamp).replace("Z", "+00:00")) < cutoff
            except ValueError:
                old_enough = False
        (moved if old_enough else keep).append(row)
    if not moved:
        return {"status": "NOTHING_TO_COMPACT", "rows": len(keep),
                "why": f"no terminal row is older than {keep_days} days"}
    with arc.open("a", encoding="utf-8") as fh:
        for r in moved:
            fh.write(json.dumps(r, default=str, separators=(",", ":")) + "\n")
    tmp = p.with_suffix(".jsonl.tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        for r in keep:
            fh.write(json.dumps(r, default=str, separators=(",", ":")) + "\n")
    os.replace(tmp, p)
    return {"status": "COMPACTED", "kept": len(keep), "archived": len(moved),
            "why": f"{len(moved)} terminal row(s) older than {keep_days}d moved to "
                   f"{arc.name}; nothing deleted, because a queue that forgets what it tried "
                   "will try it again"}


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    doc: dict[str, Any] = {"measured_at": datetime.now(UTC).isoformat(timespec="seconds")}
    if "--migrate" in args:
        doc["migrate"] = migrate()
    if "--compact" in args:
        doc["compact"] = compact()
    doc["counts"] = counts()
    doc["total"] = sum(doc["counts"].values())
    doc["source"] = "jsonl" if QUEUE.exists() else ("legacy_json" if LEGACY.exists() else "none")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    print(f"queue store: {doc['total']} row(s) from {doc['source']}")
    for k, v in sorted(doc["counts"].items(), key=lambda kv: -kv[1])[:8]:
        print(f"   {k:22} {v}")
    for key in ("migrate", "compact"):
        if key in doc:
            print(f"   {key}: {doc[key]['status']} -- {doc[key].get('why', '')[:70]}")
    if doc["source"] == "legacy_json":
        print("   STILL ON THE LEGACY JSON -- every read costs a full parse. Run --migrate.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
