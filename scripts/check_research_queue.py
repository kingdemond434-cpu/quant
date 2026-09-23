#!/usr/bin/env python3
"""RESEARCH QUEUE GUARD -- queued intent is earned evidence and may not vanish silently.

WHAT WAS ACTUALLY HAPPENING (measured 2026-08-26). The authority ratchet flagged the queue at
90 rows against a floor of 98 and called it evidence loss. Tracing the count across every commit
that touched the file showed it was not being consumed at all -- it OSCILLATES:

    10 -> 18 -> 26 -> 10 -> 18 -> 26 -> 10 -> 34 -> 42 -> 50 -> 58 -> 66 -> 82 -> 90

Miners add ~8 rows an hour and the count climbs; then it resets to 10. Those resets land exactly
on the hourly sync commits that trampled canon the same night: the desk box pushing a stale copy
over the research box's grown file. Every reset silently discarded hours of queued hypotheses --
work that had been generated, deduplicated and written, and then quietly un-generated.

A queue row is not a cache entry. It is a research intent the desk paid to produce, and it is
finished when something MARKS it done, never when a file copy loses it.

THE GUARD. Every row ever seen is unioned into an append-only archive keyed by executable
identity. If the live queue drops a row that was never marked DONE, it is restored from the
archive. A row that IS marked done stays gone -- completion is a legitimate reason to disappear,
and a guard that could not tell the difference would refill the queue forever.

This does not stop the trample; the canon lease and the money-path fence handle writers. It makes
the trample non-destructive, which is the only property that matters for evidence.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUEUE = ROOT / "desks" / "mt5" / "data" / "research_queue.json"
ARCHIVE = ROOT / "desks" / "mt5" / "data" / "research_queue_archive.json"

#: Statuses that mean a row is legitimately finished and must NOT be restored.
DONE_STATES = {"DONE", "COMPLETE", "COMPLETED", "REJECTED", "RETIRED", "KILLED", "PROMOTED"}


def _read(p: Path, default):
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def _key(row: dict) -> str:
    """Identity by what the row ASKS FOR, not by label -- ids get regenerated, intent does not."""
    return json.dumps({
        "id": row.get("id"),
        "symbol": row.get("symbol") or row.get("sym"),
        "family": row.get("family") or row.get("mechanism"),
        "title": (row.get("title") or "")[:120],
    }, sort_keys=True, default=str)


def main() -> int:
    now = datetime.now(tz=UTC)
    live = _read(QUEUE, [])
    if not isinstance(live, list):
        print("queue guard: queue is not a list -- refusing to touch it")
        return 1
    arch = _read(ARCHIVE, {"rows": {}})
    rows = arch.setdefault("rows", {})

    live_keys = set()
    for r in live:
        if not isinstance(r, dict):
            continue
        k = _key(r)
        live_keys.add(k)
        prior = rows.get(k) or {}
        rows[k] = {"row": r, "first_seen": prior.get("first_seen", now.isoformat(timespec="seconds")),
                   "last_seen": now.isoformat(timespec="seconds"),
                   "status": str(r.get("status") or "PENDING").upper()}

    # A row missing from the live queue is restorable only if it never completed.
    missing = [k for k, v in rows.items()
               if k not in live_keys and str(v.get("status", "")).upper() not in DONE_STATES]
    restored = []
    for k in missing:
        live.append(rows[k]["row"])
        restored.append(str(rows[k]["row"].get("id") or rows[k]["row"].get("title"))[:60])

    arch["updated_at"] = now.isoformat(timespec="seconds")
    arch["archived_rows"] = len(rows)
    ARCHIVE.write_text(json.dumps(arch, indent=1, default=str), "utf-8")

    if restored:
        QUEUE.write_text(json.dumps(live, indent=1, default=str), "utf-8")
        print(f"queue guard: RESTORED {len(restored)} unfinished row(s) lost from the live queue "
              f"-- a row is finished when something marks it done, not when a file copy loses it")
        for r in restored[:6]:
            print(f"   restored: {r}")
        return 1

    done = sum(1 for v in rows.values() if str(v.get("status", "")).upper() in DONE_STATES)
    print(f"queue guard: {len(live)} live, {len(rows)} ever seen, {done} legitimately completed, "
          f"0 lost")
    return 0


if __name__ == "__main__":
    sys.exit(main())
