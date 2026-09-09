"""THE EVENT LOG: what happened, named, in order -- the vocabulary the desk never had.

MEASURED 2026-09-08 (Tier-1 programme item I2): timers fire on wall clocks and the cycle's
legs run in hard-coded source order, so a transition such as DATA_UPDATED or GAUNTLET_SWEPT
exists only as the position of a line in `hourly_cycle.py`. Nothing can subscribe to it,
nothing can ask "what has happened since I last looked", and a leg that should run BECAUSE
something happened runs because it is :00 instead.

THIS IS THE SMALLEST REAL EVENT BUS: an append-only line per event, a fixed vocabulary, and
two readers. It is not a queue with workers -- the box is one 8 GB machine and the cycle is
one process -- it is the LOG such a queue would consume, written now so that when a consumer
exists the history already does. Every hourly leg emits LEG_DONE / LEG_FAILED through
`_costed`; the legs that mark a domain transition emit that transition too (LEG_EVENT).

    emit("GAUNTLET_SWEPT", leg="external_gauntlet", wall_s=412.3)
    since("2026-09-09T00:00:00+00:00", kinds=("GAUNTLET_SWEPT",))   -> rows
    latest("DATA_UPDATED")                                           -> row | None

Bounded: `since` and `latest` read the tail of the file (TAIL_BYTES) so a year of events costs
the reader nothing. The writer never raises -- an event log that can take down the leg it
records would be removed within a week.
"""
from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "desks" / "mt5" / "data" / "events.jsonl"
TAIL_BYTES = 4 * 1024 * 1024

#: The vocabulary. A name outside it is still written (with `unknown_kind: true`) so a new
#: producer is never silenced, but the test that pins this tuple is where a new kind is declared.
KINDS = (
    "LEG_DONE", "LEG_FAILED",
    "DATA_UPDATED", "TAPE_RECORDED", "INTEL_MINED",
    "CANDIDATES_COMPILED", "DOCKET_MERGED", "GAUNTLET_SWEPT", "FALSIFIERS_RUN",
    "CLOCKS_ENROLLED", "PROMOTION_DECIDED", "ALLOCATION_DECIDED",
    "RELEASE_IDENTIFIED", "STATE_PUBLISHED",
)

#: Legs whose completion IS a domain transition. Every other leg emits only LEG_DONE.
LEG_EVENT = {
    "refresh_bars": "DATA_UPDATED", "record_tape": "TAPE_RECORDED", "mine": "INTEL_MINED",
    "compile_candidates": "CANDIDATES_COMPILED", "merge_docket": "DOCKET_MERGED",
    "external_gauntlet": "GAUNTLET_SWEPT", "falsifier_run": "FALSIFIERS_RUN",
    "enrol_clocks": "CLOCKS_ENROLLED", "promoter": "PROMOTION_DECIDED",
    "pf_allocator": "ALLOCATION_DECIDED", "release_identity": "RELEASE_IDENTIFIED",
    "publish_state": "STATE_PUBLISHED",
}


def emit(kind: str, path: Path | None = None, **fields: Any) -> dict[str, Any] | None:
    """Append one event. Returns the row, or None if it could not be written (already printed)."""
    row = {"at": datetime.now(tz=UTC).isoformat(timespec="seconds"), "kind": str(kind), **fields}
    if kind not in KINDS:
        row["unknown_kind"] = True
    p = path or PATH
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, default=str, separators=(",", ":")) + "\n")
        return row
    except OSError as exc:
        print(f"events: {kind} NOT written ({type(exc).__name__}: {exc})", flush=True)
        return None


def leg_events(leg: str, outcome: str, path: Path | None = None, **fields: Any) -> list[str]:
    """What `_costed` calls when a leg ends: LEG_DONE or LEG_FAILED, plus the leg's domain
    transition when it has one and the leg succeeded. Returns the kinds emitted."""
    kinds = ["LEG_DONE" if outcome == "ok" else "LEG_FAILED"]
    if outcome == "ok" and leg in LEG_EVENT:
        kinds.append(LEG_EVENT[leg])
    for k in kinds:
        emit(k, path=path, leg=leg, outcome=outcome, **fields)
    return kinds


def _tail_rows(path: Path) -> list[dict[str, Any]]:
    try:
        size = path.stat().st_size
        with path.open("rb") as fh:
            if size > TAIL_BYTES:
                fh.seek(size - TAIL_BYTES, os.SEEK_SET)
                fh.readline()  # drop the partial line
            data = fh.read().decode("utf-8", errors="replace")
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for line in data.splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def since(stamp: str | datetime | None, kinds: tuple[str, ...] | None = None,
          path: Path | None = None) -> list[dict[str, Any]]:
    """Events after `stamp` (ISO string or datetime; None = everything in the tail), oldest
    first, optionally filtered by kind. This is the subscriber's read."""
    if isinstance(stamp, datetime):
        stamp = stamp.isoformat(timespec="seconds")
    rows = _tail_rows(path or PATH)
    return [r for r in rows if (stamp is None or str(r.get("at", "")) > str(stamp))
            and (kinds is None or r.get("kind") in kinds)]


def latest(kind: str, path: Path | None = None) -> dict[str, Any] | None:
    for r in reversed(_tail_rows(path or PATH)):
        if r.get("kind") == kind:
            return r
    return None


def census(path: Path | None = None) -> dict[str, Any]:
    """Counts per kind in the tail, and the newest stamp per kind -- the bus's own health line."""
    rows = _tail_rows(path or PATH)
    counts: dict[str, int] = {}
    newest: dict[str, str] = {}
    for r in rows:
        k = str(r.get("kind"))
        counts[k] = counts.get(k, 0) + 1
        newest[k] = max(newest.get(k, ""), str(r.get("at", "")))
    return {"rows_in_tail": len(rows), "counts": counts, "newest": newest,
            "silent_kinds": [k for k in KINDS if k not in counts]}
