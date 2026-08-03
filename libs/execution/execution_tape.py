"""Append-only EXECUTION TAPE -- the desk's own fill history, kept forever.

WHY THIS EXISTS (found 2026-07-26): `data/cashcarry_trades.json` is a rolling `log[-500:]` buffer.
At the observed ~27 events/day it retains only ~18.6 days of tape, while the executor had already
run 23.8 days -- so ~141 real fills had been silently destroyed, and every new event evicted an
older one. Three consequences, all load-bearing:

  1. GATE 0 WAS STRUCTURALLY UNREACHABLE. The freeze exit requires ">=4 weeks of live fills" and an
     execution-cost model "populated from live measurements". A 18.6-day buffer evicts fills faster
     than 28 days can accrue, so that criterion could never be met -- the desk would have waited at
     the gate forever with no visible cause.
  2. FORENSICS/TCA SILENTLY REPORTED A WINDOW AS A TOTAL. Every consumer of the rolling file
     (run_trade_forensics, live_book, run_deadman_reconciliation) computed bps attribution over
     "whatever survived truncation" while presenting it as the book's history.
  3. IT IS THE DATA MOAT. Own-fill history is the one dataset no vendor sells and no free source
     replaces; truncating it destroys the exact evidence the cost model is built from.

DESIGN: purely ADDITIVE. The rolling hot file keeps its existing shape and every existing consumer
keeps working unchanged; this module appends the same record to a never-truncated JSONL alongside
it. `append()` is exception-swallowing BY DESIGN -- the tape is an observer, and a full disk or a
bad record must never take down the live executor that feeds it.
"""
from __future__ import annotations

import contextlib
import json
import shutil
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_TAPE = Path("data/moat/execution_tape/cashcarry_trades.jsonl")
_DISK_MAX_FRAC = 0.80  # same guard as the moat recorders -- never fill the disk for a log


def _disk_ok(path: Path = _TAPE) -> bool:
    """Is there room on the filesystem that actually HOLDS THE TAPE?

    It used to measure `/` unconditionally, which is the wrong device whenever data/ is a separate
    mount -- the arrangement the VPS deploy notes assume. That gets it wrong in both directions: a
    full root refuses writes to a data volume with terabytes free, and a full data volume passes
    because root is empty. The guard exists to stop the tape filling a disk, so it has to look at
    the disk the tape is on.

    Falls back to the nearest existing ancestor, because the tape's own directory may not exist
    yet on the first write.
    """
    p = path if path.exists() else next(
        (a for a in path.parents if a.exists()), Path(path.anchor or "."))
    try:
        u = shutil.disk_usage(p)
    except OSError:
        return True          # unmeasurable is not full; the observer must never block the executor
    return (u.used / u.total) < _DISK_MAX_FRAC


def _key(rec: dict[str, Any]) -> str:
    """Identity of a fill event -- used to make backfill/replay idempotent.

    The identity is the FULL record content (minus the tape's own stamp), not a field subset: two
    top-ups of the same position share (event, symbol, opened) and differ only in notional/qty, so
    any narrower key silently collapses real distinct fills -- which is the exact data loss this
    module exists to stop.
    """
    return json.dumps({k: v for k, v in rec.items() if k != "_taped"},
                      sort_keys=True, default=str)


def append(rec: dict[str, Any], *, path: Path = _TAPE) -> bool:
    """Append one fill event to the permanent tape. Never raises -- returns success."""
    try:
        if not _disk_ok(path):
            return False
        path.parent.mkdir(parents=True, exist_ok=True)
        out = dict(rec)
        out.setdefault("_taped", datetime.now(tz=UTC).isoformat())
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(out, default=str) + "\n")
        return True
    except Exception:  # observer must never break the executor
        return False


def read(*, path: Path = _TAPE) -> list[dict[str, Any]]:
    """Read the full tape. Tolerates a partial trailing line (crash mid-append)."""
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text("utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # torn trailing write -- skip, never lose the rest
    return out


def backfill(records: list[dict[str, Any]], *, path: Path = _TAPE) -> int:
    """Seed the tape from the surviving rolling buffer, skipping anything already taped.

    Dedupe is by MULTIPLICITY, not set membership. The executor legitimately emits byte-identical
    records (observed: the same COOKIEUSDT top-up logged 4x), and live `append()` tapes every one
    of them -- so a set-based backfill would collapse real fills and quietly disagree with the live
    path. Counting occurrences keeps backfill faithful AND idempotent: re-running adds only the
    shortfall. Returns the number of NEW records written.
    """
    have = Counter(_key(r) for r in read(path=path))
    n = 0
    for rec in records:
        k = _key(rec)
        if have[k] > 0:
            have[k] -= 1  # already on the tape -- consume one occurrence
            continue
        if append(rec, path=path):
            n += 1
    return n


def coverage(*, path: Path = _TAPE) -> dict[str, Any]:
    """Tape depth -- the number Gate 0's '>=4 weeks of live fills' is actually measured against."""
    recs = read(path=path)
    stamps = []
    for r in recs:
        for k in ("closed", "opened"):
            if r.get(k):
                with contextlib.suppress(ValueError):
                    stamps.append(datetime.fromisoformat(str(r[k])))
    if not stamps:
        return {"n": len(recs), "days": 0.0, "first": None, "last": None}
    first, last = min(stamps), max(stamps)
    return {"n": len(recs), "days": round((last - first).total_seconds() / 86400, 2),
            "first": first.isoformat(), "last": last.isoformat()}
