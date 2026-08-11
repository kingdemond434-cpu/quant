"""OWED-WORK FIRING GATE -- decide whether a queue-drainer session is worth its cost.

THE ARITHMETIC THAT MADE THIS NECESSARY, measured 2026-08-11. The owed-work worker was scheduled
every 20 minutes (72 sessions/day) and later hourly (24/day). It drains a BATCH -- 8 ledger rows
per session, self-tuned -- and the ledger is fed at roughly 5 rows/day by cycles and audits. So
hourly supplies 24 x 8 = 192 row-slots a day against a 5-row refill: THIRTY-EIGHT TIMES more
capacity than the work arriving. The backlog hid it. With 113 open rows the queue was never empty,
the worker's existing "nothing owed" early-exit never triggered, and a 38x over-provision looked
exactly like a busy desk.

WHY NOT EVENT-TRIGGERING, which is the obvious answer and the wrong one. Firing on every ledger
append sounds precise and is strictly worse here: it would start a session for ONE row and throw
away the batching that makes the worker efficient in the first place. Eight rows in one session
share the repo context, the doctrine prompt and the test run; eight sessions pay all three eight
times. The event is not "a row arrived", it is "enough work has accumulated to be worth a session"
-- and that is a threshold on state, not a hook on a write.

THE GATE, therefore, is three OR-ed reasons to spend, and silence otherwise:

  * FULL BATCH   -- at least `batch` rows are open. Spend now; the session is running at full
                    efficiency and waiting longer buys nothing.
  * AGE FLOOR    -- the oldest open row has waited longer than `max_age_h`. This is what stops a
                    lone row rotting forever behind a batch that never fills, which is the failure
                    mode a pure threshold would introduce. Latency is bounded by construction.
  * LIVE DEFECT  -- max_audit is reporting a live defect. Those are not queue rows to be
                    accumulated; they are the desk telling itself something is broken now.

Everything else HOLDS, and a hold states its own arithmetic -- how many rows, how old the oldest,
what would flip it. A gate that just said "no" would be indistinguishable from a broken worker,
which is the exact confusion a bound spend-cap already creates elsewhere on this desk.

WHAT THIS DOES NOT DO. It never drops a row, never reprioritises one, and never decides a row is
unworthy -- the ledger's own disposition rules are untouched. It decides only WHEN the drainer
runs. Deferring work whose refill rate is 38x below capacity costs latency measured in hours and
saves 96% of the sessions.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

__all__ = ["DEFAULT_BATCH", "MAX_ROW_AGE_H", "GateVerdict", "decide", "gate_from_repo"]

_ROOT = Path(__file__).resolve().parents[2]

#: Rows per session when the tuning file is absent. Mirrors the worker's own default so the gate
#: and the drainer cannot disagree about what "a full batch" means.
DEFAULT_BATCH = 8

#: THE LATENCY CEILING, and it is the half of this gate that protects ROI rather than cost.
#: 20 hours, chosen so that a row raised at any point in a day is worked within the next day even
#: if the batch never fills. Lower and the gate stops saving anything on a slow week; much higher
#: and a genuine finding could sit through a weekend. This is the number to move if the desk ever
#: feels slow -- not the cadence, which is now a consequence rather than a choice.
MAX_ROW_AGE_H = 20.0


@dataclass(frozen=True)
class GateVerdict:
    fire: bool
    reason: str
    n_open: int
    oldest_age_h: float
    n_live_defects: int
    batch: int

    def as_dict(self) -> dict[str, Any]:
        return {"fire": self.fire, "reason": self.reason, "n_open": self.n_open,
                "oldest_age_h": round(self.oldest_age_h, 2),
                "n_live_defects": self.n_live_defects, "batch": self.batch}


def decide(*, n_open: int, oldest_age_h: float, n_live_defects: int,
           batch: int = DEFAULT_BATCH, max_age_h: float = MAX_ROW_AGE_H) -> GateVerdict:
    """Pure decision, so the arithmetic is testable without a repo or a clock."""
    def v(fire: bool, reason: str) -> GateVerdict:
        return GateVerdict(fire, reason, n_open, oldest_age_h, n_live_defects, batch)

    if n_live_defects > 0:
        return v(True, f"LIVE DEFECT: {n_live_defects} open defect(s) from max_audit -- these are "
                       "not queue rows to accumulate, they are the desk reporting something broken")
    if n_open <= 0:
        return v(False, "nothing owed")
    if n_open >= batch:
        return v(True, f"FULL BATCH: {n_open} rows open >= batch {batch}; the session runs at full "
                       "efficiency and waiting buys nothing")
    if oldest_age_h >= max_age_h:
        return v(True, f"AGE FLOOR: oldest open row waited {oldest_age_h:.1f}h >= {max_age_h}h. "
                       "A lone row must not rot behind a batch that never fills")
    need = batch - n_open
    wait = max_age_h - oldest_age_h
    return v(False, f"HOLD: {n_open}/{batch} rows open, oldest {oldest_age_h:.1f}h. Fires when "
                    f"{need} more row(s) arrive or in {wait:.1f}h, whichever comes first -- "
                    "batching 8 rows in one session beats 8 sessions of one")


def _age_h(row: dict[str, Any], now: datetime) -> float:
    try:
        raised = datetime.fromisoformat(str(row["raised"]))
        if raised.tzinfo is None:
            raised = raised.replace(tzinfo=UTC)
        return (now - raised).total_seconds() / 3600.0
    except (KeyError, ValueError, TypeError):
        # A row with no readable timestamp is treated as OLD, never as new. Unknown age must not
        # let a row hide below the floor forever (L1.41: unknown is not zero).
        return float("inf")


def gate_from_repo(root: Path | None = None, *, now: datetime | None = None) -> GateVerdict:
    """Read the real ledger, tuning file and audit report. Never raises -- a gate that dies on a
    malformed artifact would silently stop the drainer, which is the outage it exists to avoid.
    On any read failure it FIRES: spending one session is cheaper than stalling the queue."""
    base = root or _ROOT
    now = now or datetime.now(tz=UTC)

    try:
        raw = json.loads((base / "docs/research/recommendation_ledger.json").read_text("utf-8"))
        rows = raw["recommendations"] if isinstance(raw, dict) else raw
        open_rows = [r for r in rows if str(r.get("status")) == "open"]
    except Exception as exc:
        return GateVerdict(True, f"ledger unreadable ({type(exc).__name__}) -- firing rather than "
                                 "stalling the queue on a read error", -1, 0.0, 0, DEFAULT_BATCH)

    try:
        tune = json.loads((base / "data/owed_worker_tuning.json").read_text("utf-8"))
        batch = max(3, int(tune.get("batch", DEFAULT_BATCH)))
    except Exception:
        batch = DEFAULT_BATCH

    n_live = 0
    try:
        rep = json.loads((base / "data/max_audit_report.json").read_text("utf-8"))
        n_live = len([d for d in rep.get("live", [])
                      if not str(d.get("id", "")).startswith("rec-")])
    except Exception:
        n_live = 0                      # absent audit report is not a defect claim either way

    oldest = max((_age_h(r, now) for r in open_rows), default=0.0)
    return decide(n_open=len(open_rows), oldest_age_h=oldest,
                  n_live_defects=n_live, batch=batch)


if __name__ == "__main__":
    print(json.dumps(gate_from_repo().as_dict(), indent=1))
