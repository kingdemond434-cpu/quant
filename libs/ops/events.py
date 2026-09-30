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

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "desks" / "mt5" / "data" / "events.jsonl"
ACK_PATH = ROOT / "desks" / "mt5" / "data" / "event_acknowledgements.jsonl"
TAIL_BYTES = 4 * 1024 * 1024

#: The vocabulary. A name outside it is still written (with `unknown_kind: true`) so a new
#: producer is never silenced, but the test that pins this tuple is where a new kind is declared.
KINDS = (
    "LEG_DONE", "LEG_FAILED",
    "DATA_UPDATED", "TAPE_RECORDED", "INTEL_MINED",
    "CANDIDATES_COMPILED", "DOCKET_MERGED", "GAUNTLET_SWEPT", "FALSIFIERS_RUN",
    "CLOCKS_ENROLLED", "PROMOTION_DECIDED", "ALLOCATION_DECIDED",
    "RELEASE_IDENTIFIED", "STATE_PUBLISHED",
    "EXPRESSIONS_SCREENED", "MATH_CARDS_JUDGED",
    # THE PLUMBING SPEAKS HERE TOO (principal 2026-09-23). A plumbing defect that survives a pass
    # escalates to three surfaces a human meets without asking, and this log is one of them: the
    # dashboard renders `plumbing`, docs/research/PLUMBING_ALERTS.md lists it, and a
    # PLUMBING_DEFECT row lands here with the organ, its age and its evidence. PLUMBING_CLEAR is
    # written on a clean pass so the absence of defects is itself recorded rather than inferred
    # from an absence of rows -- which is the silence the watchdog exists to end.
    "PLUMBING_DEFECT", "PLUMBING_CLEAR",
    # The 24/7 maximiser's verdict: which of the four standing bottlenecks bound this hour, and
    # by how much its owning department's compute was raised.
    "BOTTLENECK_BOUND",
    # What the desk charges itself against what the broker quotes and what the account paid
    # (principal 2026-09-23). Carries the overcharged-symbol count and how many refusals the
    # measured cost restored, so "the cost model was re-measured" is a transition with a time
    # on it and not a file that quietly changed.
    "COST_TRUTH_MEASURED",
    # A destructive pass REFUSED to remove because its reference was empty, stale beyond its lease
    # or unreadable (LAWS 7, `libs/ops/reference_freshness.py`). It carries the reference, the
    # verdict and the why, so a refusal is a transition with a time on it rather than a quiet
    # no-op -- which is the only way an operator learns that a writer upstream has gone silent.
    "REFERENCE_STAND_DOWN",
    # A stage-1-ranked cell has waited >= 24h for a SEALED judgement: the screen's window now
    # biases WHICH cells the sealed judge ever reaches. Carries the window and the oldest age.
    "STAGE1_ORDERING_BIAS",
    # Stage 1's walk-forward bound is not proven equal to the sealed gauntlet's actual cut: the run
    # fell back to the pre_wf window (research/stage1_judge.wf_cut_check).
    "STAGE1_WINDOW_MISMATCH",
    # The sealed judge could not read stage 1's order (the record) or its trial union (the
    # experiment ledger) and fell back -- written by the two-stage sealed patch, never silent.
    "STAGE1_FALLBACK",
    # The box's state is fresh on the box and stale on origin: delivery is broken, the desk is not
    # idle (libs/ops/state_publication.py). Written by publish_state; read by stall_watch.
    "STATE_FLOW_STALLED",
)

#: Legs whose completion IS a domain transition. Every other leg emits only LEG_DONE.
LEG_EVENT = {
    "refresh_bars": "DATA_UPDATED", "record_tape": "TAPE_RECORDED", "mine": "INTEL_MINED",
    "compile_candidates": "CANDIDATES_COMPILED", "merge_docket": "DOCKET_MERGED",
    "external_gauntlet": "GAUNTLET_SWEPT", "falsifier_run": "FALSIFIERS_RUN",
    "enrol_clocks": "CLOCKS_ENROLLED", "promoter": "PROMOTION_DECIDED",
    "pf_allocator": "ALLOCATION_DECIDED", "release_identity": "RELEASE_IDENTIFIED",
    "publish_state": "STATE_PUBLISHED",
    "expression_factory": "EXPRESSIONS_SCREENED",
}


def emit(kind: str, path: Path | None = None, **fields: Any) -> dict[str, Any] | None:
    """Append one typed event while retaining the original lightweight API."""
    at = datetime.now(tz=UTC).isoformat(timespec="seconds")
    producer = str(fields.pop("producer", fields.get("leg") or "unknown"))
    allowed = fields.pop("allowed_consumers", ("*",))
    base = {"at": at, "kind": str(kind), "producer": producer,
            "schema_version": str(fields.pop("schema_version", "1")),
            "topic": str(fields.pop("topic", str(kind).lower())),
            "evidence_grade": str(fields.pop("evidence_grade", "OPERATIONAL_EVENT")),
            "priority": int(fields.pop("priority", 0)),
            "allowed_consumers": list(allowed), **fields}
    raw = json.dumps(base, sort_keys=True, default=str, separators=(",", ":")).encode()
    artifact_id = str(base.pop("artifact_id", "") or hashlib.sha256(raw).hexdigest()[:24])
    row = {**base, "artifact_id": artifact_id, "ack_state": "UNACKNOWLEDGED"}
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


def acknowledge(artifact_id: str, consumer: str, *, status: str = "CONSUMED",
                path: Path | None = None) -> dict[str, Any] | None:
    """Append a consumer acknowledgement without mutating the source event."""
    if not artifact_id or not consumer:
        raise ValueError("artifact_id and consumer are required")
    row = {"at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
           "artifact_id": artifact_id, "consumer": consumer, "status": status}
    p = path or ACK_PATH
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, default=str, separators=(",", ":")) + "\n")
        return row
    except OSError as exc:
        print(f"events: acknowledgement NOT written ({type(exc).__name__}: {exc})", flush=True)
        return None


def unacknowledged(*, consumer: str, events_path: Path | None = None,
                   ack_path: Path | None = None) -> list[dict[str, Any]]:
    """Return events this allowed consumer has not acknowledged."""
    event_rows = _tail_rows(events_path or PATH)
    ack_rows = _tail_rows(ack_path or ACK_PATH)
    seen = {str(row.get("artifact_id")) for row in ack_rows
            if row.get("consumer") == consumer}
    out: list[dict[str, Any]] = []
    for row in event_rows:
        allowed = tuple(row.get("allowed_consumers") or ("*",))
        if str(row.get("artifact_id")) not in seen and ("*" in allowed or consumer in allowed):
            out.append(row)
    return out


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
