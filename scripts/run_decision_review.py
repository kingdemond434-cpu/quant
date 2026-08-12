"""Give every logged decision a review date, and publish the matured-and-unscored worklist.

Measured 2026-07-26: 189 decisions, 3 scored, 14 carrying a `review_due`. The ledger's own policy
promises that "the monthly governance review scores each matured entry so decision QUALITY
compounds" -- but nothing defined maturity, so 175 decisions could never come due and the monthly
review had an empty queue to work from. The self-improvement loop was not neglected; it was
structurally unable to fire.

This backfills the missing dates and writes the worklist. It does NOT score anything. Deciding
that a past decision turned out correct, wrong, or unclear is a judgement about the world, and a
calibration ledger full of machine-guessed outcomes is strictly worse than an empty one -- the
Brier score would then be confidently wrong about how well the desk decides, which is the precise
failure the ledger was created to catch. Backfilled dates are stamped `review_due_source` so a
derived horizon is never mistaken for one a human chose.

    python scripts/run_decision_review.py [--dry-run]
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from libs.research.decision_review import (
    backfill_plan,
    confidence_profile,
    health,
    reviews,
)

_ROOT = Path(__file__).resolve().parent.parent
_LEDGER = _ROOT / "data" / "decision_ledger.json"
_REPORT = _ROOT / "data" / "decision_review.json"


def _load() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    try:
        d = json.loads(_LEDGER.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, []
    if isinstance(d, dict):
        rows = d.get("decisions", [])
        return d, [r for r in rows if isinstance(r, dict)]
    return {}, [r for r in d if isinstance(r, dict)]


def main() -> int:
    dry = "--dry-run" in sys.argv
    doc, rows = _load()
    if not rows:
        print("decision ledger empty or unreadable -- nothing to review")
        return 0

    today = date.today()  # noqa: DTZ011 -- calendar date for a filename/stamp, never compared to an instant
    plan = backfill_plan(rows, today)

    if plan and not dry:
        by_id = {str(r.get("id")): r for r in rows}
        for rid, iso, source in plan:
            r = by_id.get(rid)
            if r is not None:
                r["review_due"] = iso
                r["review_due_source"] = source      # never let derived look deliberate
        if isinstance(doc, dict):
            doc["decisions"] = rows
            # ensure_ascii=False for the same reason as scripts/recommendations.py:_save (R0368):
            # this ledger's escapes are `§`, `→`, `λ`/`μ` and `≈` -- the notation its own rows
            # argue in. Fixed here rather than left as the sibling instance, because half a fix
            # leaves the next reader believing the class was closed.
            _LEDGER.write_text(json.dumps(doc, indent=1, ensure_ascii=False), "utf-8")

    rv = reviews(rows, today)
    h = health(rows, today)
    due = sorted((r for r in rv if r.state == "due"), key=lambda r: -r.days_overdue)

    report = {
        "ts": datetime.now(tz=UTC).isoformat(),
        "total": h.total,
        "scored": h.scored,
        "scored_pct": h.scored_pct,
        "due_unscored": h.due,
        "maturing": h.maturing,
        "undatable": h.undatable,
        "oldest_overdue_days": h.oldest_overdue_d,
        "verdict": h.verdict,
        "backfilled_this_run": 0 if dry else len(plan),
        "confidence_profile": confidence_profile(rows),
        # the actual worklist a human scores, worst-overdue first
        "worklist": [{"id": r.row_id, "due": r.due.isoformat() if r.due else None,
                      "days_overdue": r.days_overdue, "horizon_d": r.horizon_d,
                      "horizon_source": r.source} for r in due[:60]],
        "note": ("Review dates are DERIVED where none was set (source recorded per row). Outcomes "
                 "are never written by this script -- scoring a decision is a judgement, and a "
                 "calibration ledger of guessed outcomes is worse than an empty one."),
    }
    _REPORT.parent.mkdir(parents=True, exist_ok=True)
    _REPORT.write_text(json.dumps(report, indent=2), "utf-8")

    cp = report["confidence_profile"]
    print(f"decision review: {h.scored}/{h.total} scored ({h.scored_pct}%), "
          f"{h.due} due, {h.maturing} maturing, {h.undatable} undatable"
          f"{'' if dry else f', {len(plan)} review dates backfilled'}")
    print(f"  {h.verdict}")
    if isinstance(cp, dict) and cp.get("n"):
        print(f"  stated confidence: mean {cp['mean']}, "
              f"{cp['modal_share_pct']}% in the {cp['modal_bucket']} bucket "
              "-- untestable until outcomes exist")
    if due:
        print(f"  oldest due: {due[0].row_id} ({due[0].days_overdue}d past its "
              f"{due[0].horizon_d}d horizon)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
