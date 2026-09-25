#!/usr/bin/env python3
"""A LEG THAT NEVER RAN IS A CLAIM THE DESK CANNOT CASH (L1.49), SO IT IS NAMED HERE.

THE DEFECT THIS FENCE EXISTS FOR, measured 2026-09-23 from the compute ledger (89,986 rows over
503 distinct runs): **19 of 112 CORE_LEGS had never executed once.** Not late, not slow -- zero
rows, ever. `desks/mt5/research/hourly_cycle.py` runs ~325 legs front to back and the scheduled
task that owns the core plan allows it 40 minutes, so a pass that runs out of clock is killed
where it stands and the next hour restarts at the top. The same tail was skipped every hour.

WHY IT WAS INVISIBLE, and why a fence and not a dashboard: a leg that never runs raises no error
and writes no artifact, so it is indistinguishable from a leg that ran and had nothing to write.
Among the nineteen were `clock_liveness` and `clock_ledger` (how the desk knows its forward clocks
are alive), `fill_recorder` (how it learns from real executions) and `evidence_chain` (provenance).
Absence never resolves to a clean verdict (L1.28a), so this reads the rotation's own record and
FAILS on two lists rather than letting either be inferred from silence:

    never_run       legs the compute ledger has never once recorded. Must be empty.
    outside_window  legs with no run inside ROTATION_WINDOW_H. Must be empty.

IT IS NOT A THROTTLE AND CANNOT BECOME ONE. This fence only ever demands that MORE legs run; there
is no threshold here that can be satisfied by attempting less. The rotation it reads
(`libs/ops/leg_rotation.py`) reorders membership inside a budget the scheduler already imposed and
never shrinks the roster -- deleting a leg to pass this fence would raise `never_run` for nothing
and is the one move that makes the number worse.

AN ABSENT RECORD FAILS. `UNMEASURED` is a real answer, and the honest one here is that the cycle
has not published an attendance record -- which is the same silence the fence was built to end.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.ops import leg_rotation as LR  # noqa: E402

#: How long the record itself may stand before the fence stops believing it. The core plan fires
#: hourly; three missed publications is a cycle that is not running, which is its own defect and
#: must not be reported as a clean rotation.
MAX_RECORD_AGE_H: float = 3.0


def check(path: Path | None = None, *, now: object = None) -> dict[str, object]:
    """Read the published rotation and judge it. Never runs the cycle; reads what it wrote."""
    from datetime import UTC, datetime
    t1 = now if isinstance(now, datetime) else datetime.now(tz=UTC)
    rec = LR.load_record(path)
    failures: list[str] = []
    if not rec:
        where = str(path or LR.RECORD)
        return {"ok": False, "n_failed": 1,
                "failures": [f"no rotation record at {where}: the hourly cycle has not published "
                             "leg attendance, so which legs ran is UNMEASURED (L1.28a) -- that "
                             "is the silence this fence exists to end, never a pass"],
                "record": None}
    age_h = None
    try:
        age_h = (t1 - datetime.fromisoformat(str(rec.get("generated")))).total_seconds() / 3600.0
    except (TypeError, ValueError):
        failures.append("rotation record carries no readable `generated` stamp: its age cannot "
                        "be measured, so it cannot be cashed")
    if age_h is not None and age_h > MAX_RECORD_AGE_H:
        failures.append(f"rotation record is {age_h:.1f}h old against a {MAX_RECORD_AGE_H:.0f}h "
                        "bound: the cycle that publishes it is not running on its clock")
    never = [str(x) for x in (rec.get("never_run") or [])]
    outside = [str(x) for x in (rec.get("outside_window") or [])]
    if never:
        failures.append(f"{len(never)} leg(s) have NEVER run: {', '.join(sorted(never)[:40])}"
                        + (" ..." if len(never) > 40 else "")
                        + " -- a leg that never ran is a claim the desk cannot cash (L1.49)")
    if outside:
        win = rec.get("window_h", LR.ROTATION_WINDOW_H)
        failures.append(f"{len(outside)} leg(s) have no run inside the {win}h rotation window: "
                        + ", ".join(sorted(outside)[:40])
                        + (" ..." if len(outside) > 40 else ""))
    return {"ok": not failures, "n_failed": len(failures), "failures": failures,
            "record_age_h": None if age_h is None else round(age_h, 2),
            "n_roster": rec.get("n_roster"), "n_never_run": len(never),
            "n_outside_window": len(outside), "plan": rec.get("plan"),
            "record": str(path or LR.RECORD)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--record", type=Path, default=None,
                    help="the rotation record to judge (default reports/LEG_ROTATION.json)")
    ap.add_argument("--json", action="store_true", help="emit the verdict as JSON")
    args = ap.parse_args(argv)
    rep = check(args.record)
    if args.json:
        print(json.dumps(rep, indent=1))
    else:
        head = "leg rotation: OK" if rep["ok"] else f"leg rotation: {rep['n_failed']} FAILURE(S)"
        print(f"{head} | roster={rep.get('n_roster')} never_run={rep.get('n_never_run')} "
              f"outside_window={rep.get('n_outside_window')} age={rep.get('record_age_h')}h")
        fails = rep["failures"]
        for f in fails if isinstance(fails, list) else []:
            print(f"  FAIL {f}")
    return 0 if rep["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
