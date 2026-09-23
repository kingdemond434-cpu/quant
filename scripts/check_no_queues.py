#!/usr/bin/env python3
"""THE NO-QUEUES FENCE -- nothing is parked; a row is processed on arrival.

THE LAW (principal's standing order, 2026-09-23): "keep no queues, crawl everything, nothing
should be queued in the research system, all immediate tested." Where a budget genuinely runs out
the leftover is the FIRST work of the next pass and its AGE IS PUBLISHED -- never an indefinite
park.

WHAT THIS FENCE ASSERTS, against `desks/mt5/reports/QUEUE_CENSUS.json`:

    BREACH      a queue whose OLDEST ROW is older than ONE CYCLE of the organ that owns it.
                That is the fence's whole sentence. A row that survives a full cycle of its own
                drain was not carried, it was parked.
    PARKED      a queue with open rows and NO DRAINER AT ALL. There is no cycle to measure it
                against because nothing on any clock processes it, which is the worst version of
                the same defect and is reported separately so it cannot hide inside BREACH.
    UNMEASURED  a queue with open rows whose AGE CANNOT BE MEASURED -- rows carrying no enqueue
                timestamp. This FAILS (L1.28a: absence is never a clean verdict). The fix is to
                stamp the rows, and a fence that passed here would make that fix optional
                forever. `miner_deepening` is the live case: 28,450 rows, no per-row time.

WHY IT FAILS LOUD ON DAY ONE, AND WHY THAT IS CORRECT. The first run measured 62,915 rows
waiting across 14 queues, six BREACH, one PARKED and two UNMEASURED, with the oldest row 648 h
(27 days) old in `requeue_named`. None of those numbers were new -- every one of them was already
sitting inside some organ's own report -- and none of them had ever been compared to the law.
A fence that shipped green by lowering its bar to today's state would pin the backlog in place,
which is exactly the failure mode L1.43 names. It ships red and the red is the work.

STALENESS IS A FAILURE TOO. A census older than MAX_AGE_H is not evidence about now, so the
fence reports STALE and fails: a fence reading a week-old artifact is a fence reporting on a
week-old desk.

    python scripts/check_no_queues.py [--json] [--report-only] [--max-age-h 3]

Exit 0 only on CLEAN. `--report-only` prints and exits 0, for a session that wants the census
read without the gate; the law gate never passes it.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.ops.fence_exit import FAIL, fence_exit  # noqa: E402

CENSUS = _ROOT / "desks" / "mt5" / "reports" / "QUEUE_CENSUS.json"
#: One cycle of the census organ itself, plus slack for a long hourly pass. A census older than
#: this describes a desk that has moved on.
MAX_AGE_H = 3.0
#: The ONLY passing status. Everything else -- including a status invented later by someone who
#: never reads this module -- fails closed (R0237).
_PASSING = frozenset({"CLEAN"})


def _read(path: Path) -> dict[str, Any] | None:
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


def _parse(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def build_report(root: Path | None = None, *, now: datetime | None = None,
                 max_age_h: float = MAX_AGE_H) -> dict[str, Any]:
    """The verdict, derived from the census. Never raises; an unreadable census is DARK."""
    base = root or _ROOT
    census_path = base / "desks" / "mt5" / "reports" / "QUEUE_CENSUS.json"
    stamp = now or datetime.now(tz=UTC)
    doc = _read(census_path)
    if doc is None:
        return {"status": "DARK", "scanned": 0, "breaches": [], "parked": [], "unmeasured": [],
                "detail": (f"{census_path.name} is absent or unreadable: the census has never "
                           f"run, so 'no queues' is a claim the desk cannot cash (L1.49). "
                           f"Run `python desks/mt5/research/queue_census.py --once`")}
    generated = _parse(doc.get("at"))
    age_h = None if generated is None else (stamp - generated).total_seconds() / 3600.0
    queues = [q for q in (doc.get("queues") or ()) if isinstance(q, dict)]
    breaches: list[dict[str, Any]] = []
    parked: list[dict[str, Any]] = []
    unmeasured: list[dict[str, Any]] = []
    for q in queues:
        state = str((q.get("verdict") or {}).get("state") or "UNMEASURED")
        row = {"id": q.get("id"), "depth": q.get("depth"), "oldest_age_h": q.get("oldest_age_h"),
               "cycle_h": q.get("cycle_h"), "owner_leg": q.get("owner_leg"),
               "why": (q.get("verdict") or {}).get("why", "")}
        if state == "BREACH":
            breaches.append(row)
        elif state == "PARKED":
            parked.append(row)
        elif state == "UNMEASURED":
            unmeasured.append(row)
    rep: dict[str, Any] = {
        "at": stamp.isoformat(timespec="seconds"),
        "census_at": doc.get("at"), "census_age_h": None if age_h is None else round(age_h, 3),
        "scanned": len(queues),
        "rows_waiting": (doc.get("totals") or {}).get("rows_waiting"),
        "breaches": breaches, "parked": parked, "unmeasured": unmeasured,
        "rule": doc.get("rule", ""),
    }
    if age_h is None:
        rep["status"] = "DARK"
        rep["detail"] = "the census carries no readable `at`: it cannot be dated, so it is not evidence"
        return rep
    if age_h > max_age_h:
        rep["status"] = "STALE"
        rep["detail"] = (f"the census is {age_h:.1f} h old against a {max_age_h} h limit: it "
                         f"describes a desk that has moved on. The queue_census leg is not running")
        return rep
    if not queues:
        rep["status"] = "DARK"
        rep["detail"] = "the census names no queues at all: it measured nothing (L1.57)"
        return rep
    if breaches or parked or unmeasured:
        rep["status"] = "QUEUED"
        worst = max((b for b in breaches + parked
                     if isinstance(b.get("oldest_age_h"), (int, float))),
                    key=lambda b: float(b["oldest_age_h"]), default=None)
        rep["detail"] = (
            f"{len(breaches)} queue(s) past one cycle, {len(parked)} with NO DRAINER, "
            f"{len(unmeasured)} whose row age cannot be measured; "
            f"{rep['rows_waiting']} rows waiting"
            + (f"; oldest {worst['oldest_age_h']} h in {worst['id']}" if worst else ""))
        return rep
    rep["status"] = "CLEAN"
    rep["detail"] = (f"{len(queues)} queues measured, none past one cycle of its owner, "
                     f"{rep['rows_waiting']} rows in carry")
    return rep


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="no-queues fence (LAWS 5e / 2026-09-23)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--report-only", action="store_true",
                    help="print and exit 0; the law gate never passes this")
    ap.add_argument("--max-age-h", type=float, default=MAX_AGE_H)
    args = ap.parse_args(argv)
    rep = build_report(max_age_h=float(args.max_age_h))
    if args.json:
        print(json.dumps(rep, indent=2, default=str))
    else:
        print(f"no-queues fence: {rep['status']} -- {rep.get('detail', '')}")
        for row in rep["parked"]:
            print(f"  PARKED     {row['id']}: {row['why']}")
        for row in rep["breaches"]:
            print(f"  BREACH     {row['id']}: {row['why']}")
        for row in rep["unmeasured"]:
            print(f"  UNMEASURED {row['id']}: {row['why']}")
        print(f"-> {CENSUS}")
    if args.report_only:
        return 0
    return fence_exit(rep["status"], _PASSING, fail=FAIL, scanned=rep["scanned"],
                      of="queues in the census", fence="check_no_queues.py")


if __name__ == "__main__":
    sys.exit(main())
