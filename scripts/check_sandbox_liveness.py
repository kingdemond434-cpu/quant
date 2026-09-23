#!/usr/bin/env python3
"""SANDBOX LIVENESS FENCE (LAWS 5h, L1.28c, L1.32) -- no federated system goes dark, and no
UNMEASURED reason is allowed to sit still.

THE TWO FAILURES THIS CLOSES, both measured on 2026-09-23 before the rotation landed:

 1. A RUNNABLE SYSTEM THAT NEVER GETS THE HOUR. `sandbox_runner` allocated ROI-proportionally
    over everything it could run, so the systems that had produced kept producing and a system
    that had never run could wait forever without anybody deciding it should. That is a frontier
    switched off by arithmetic rather than by evidence (L1.32). `libs/research/sandbox_rotation.py`
    gives every runnable system a scout floor inside a 24h window; THIS fence is what makes that
    a promise instead of an intention -- a runnable system whose last run is older than its
    rotation window (x1.5 grace, so one skipped pass is not a breach) is a FAILURE with its name
    and its age.

 2. AN UNMEASURED REASON THAT HAS NOT MOVED IN A WEEK. 55 of 63 systems read UNMEASURED because
    a library was not installed, each with an INSTALL TASK row, and nothing executed those rows
    for as long as the report existed. "Recorded as a task" is not a disposition; it is a defect
    with a to-do list attached (LAWS 7). A system whose UNMEASURED reason is byte-identical for
    seven days IS a breach UNLESS the install ledger shows the task moving: an attempt inside
    the week, or a settled PERMANENTLY_UNAVAILABLE row that names its exact error AND its cover
    (a REBUILT cell or the adapter's own implementation). A settled row is an answer; a stale
    retryable row is a stall.

WHAT IS NOT A BREACH, on purpose. A system the ledger settled as PERMANENTLY_UNAVAILABLE with an
error and a cover: the desk measured that this interpreter cannot host it and said what carries
the capability instead. A system whose disposition does not execute upstream code (REBUILT,
REJECTED_WITH_EVIDENCE) is not expected to run upstream and is counted separately. Absence of the
runner's report is UNMEASURED, which fails -- a fence that never ran is a claim the desk cannot
cash (L1.49).

    python scripts/check_sandbox_liveness.py [--report-only] [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.ops.fence_exit import fence_exit  # noqa: E402
from libs.ops.lawful import guard as _law_guard  # noqa: E402
from libs.research import sandbox_rotation as ROT  # noqa: E402

DESK = _ROOT / "desks" / "mt5"
RUNNER_REPORT = DESK / "reports" / "SANDBOX_RUNNER.json"
RUNNER_STATE = DESK / "data" / "sandbox_runner_state.json"
INSTALL_LEDGER = DESK / "data" / "sandbox_install_ledger.json"
STATE = DESK / "data" / "sandbox_liveness_state.json"
OUT = DESK / "reports" / "SANDBOX_LIVENESS.json"

_PASSING = frozenset({"OK"})
#: An UNMEASURED reason may stand this long unchanged before it is a stall.
STALE_REASON_S = 7 * 24 * 3600.0
#: One skipped pass is not a breach; a day and a half of them is.
ROTATION_GRACE = 1.5
#: Ledger statuses that SETTLE a system: the desk measured that it cannot be hosted here and
#: named what covers the capability. Never a stall.
SETTLED = frozenset({"PERMANENTLY_UNAVAILABLE"})


def _read(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return default


def _write(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")


def now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def reason_ages(unmeasured: list[dict[str, Any]], prior: dict[str, Any], *,
                at: str | None = None) -> dict[str, dict[str, Any]]:
    """Track WHEN each system's UNMEASURED reason last changed.

    The fence keeps this itself because no other organ records it: a reason is a string in a
    report that is rewritten every hour, so "unchanged for a week" is only knowable if somebody
    remembers the string and the date it first appeared. Returns the NEW state.
    """
    stamp = at or now()
    out: dict[str, dict[str, Any]] = {}
    for row in unmeasured:
        sid = str(row.get("system_id") or "")
        if not sid:
            continue
        why = str(row.get("why") or "")
        was = prior.get(sid) if isinstance(prior.get(sid), dict) else None
        if was and str(was.get("why")) == why:
            out[sid] = {"why": why, "since": was.get("since") or stamp,
                        "seen_at": stamp, "n_seen": int(was.get("n_seen") or 1) + 1}
        else:
            out[sid] = {"why": why, "since": stamp, "seen_at": stamp, "n_seen": 1}
    return out


def task_moved(sid: str, ledger_rows: dict[str, Any], *, at_ts: float | None = None
               ) -> tuple[bool, str]:
    """Did this system's install task MOVE inside the staleness window, or settle with a cover?"""
    row = ledger_rows.get(sid)
    if not isinstance(row, dict):
        return False, ("no install ledger row: sandbox_provision.py has never attempted this "
                       "system's requirement")
    status = str(row.get("status") or "")
    if status == "INSTALLED":
        return True, "the ledger installed it; a stale UNMEASURED reason beside that is a bug"
    if status in SETTLED:
        if row.get("error") and row.get("cover"):
            return True, f"settled {status}: {row.get('why')}; covered by {row.get('cover')}"
        return False, (f"settled {status} without an exact error and a named cover: a terminal "
                       f"row must say what failed and what carries the capability instead")
    age = ROT.age_s(row.get("last_attempt_at"), at=at_ts)
    if age <= STALE_REASON_S:
        return True, (f"attempted {age / 3600:.1f}h ago (attempt #{row.get('attempts')}, "
                      f"{status})")
    return False, (f"status {status or 'UNKNOWN'} and the last attempt was "
                   + ("never" if age == float("inf") else f"{age / 86400:.1f} days ago"))


def build_report(*, at_ts: float | None = None, at: str | None = None) -> dict[str, Any]:
    report = _read(RUNNER_REPORT)
    state = _read(RUNNER_STATE, {}) or {}
    ledger = _read(INSTALL_LEDGER, {}) or {}
    ledger_rows = {str(k): v for k, v in (ledger.get("systems") or {}).items()}
    prior = _read(STATE, {}) or {}
    prior_rows = {str(k): v for k, v in (prior.get("reasons") or {}).items()}
    if not isinstance(report, dict):
        return {"status": "UNMEASURED", "n_scanned": 0, "dark": [], "stalled": [],
                "detail": f"{RUNNER_REPORT} is absent or unreadable: the sandbox runner has "
                          f"never produced, so liveness cannot be measured (L1.49)",
                "law": "LAWS 5h / L1.28c", "at": at or now()}

    tried = [r for r in (report.get("systems_tried") or []) if isinstance(r, dict)]
    runnable = [str(r.get("system_id")) for r in tried
                if str(r.get("status")) == "RUNNABLE" and r.get("system_id")]
    rows = {str(k): v for k, v in (state.get("systems") or {}).items()}
    window = float((report.get("rotation") or {}).get("window_s") or ROT.ROTATION_WINDOW_S)
    dark = ROT.due_violations(runnable, rows, window_s=window, at=at_ts, grace=ROTATION_GRACE)

    unmeasured = [r for r in (report.get("unmeasured") or []) if isinstance(r, dict)]
    reasons = reason_ages(unmeasured, prior_rows, at=at)
    stalled: list[dict[str, Any]] = []
    settled: list[str] = []
    for row in unmeasured:
        sid = str(row.get("system_id") or "")
        if not sid:
            continue
        held = ROT.age_s((reasons.get(sid) or {}).get("since"), at=at_ts)
        moved, why_moved = task_moved(sid, ledger_rows, at_ts=at_ts)
        if moved:
            settled.append(sid)
            continue
        if held >= STALE_REASON_S:
            stalled.append({"system_id": sid, "why": str(row.get("why") or "")[:200],
                            "unchanged_since": (reasons.get(sid) or {}).get("since"),
                            "held_days": round(held / 86400.0, 2),
                            "install_task": why_moved})
    status = "OK" if not dark and not stalled else ("DARK" if dark else "STALLED")
    n_scanned = len(runnable) + len(unmeasured)
    return {
        "at": at or now(), "status": status, "law": "LAWS 5h / L1.28c / L1.32",
        "generator": "check_sandbox_liveness",
        "n_scanned": n_scanned, "n_runnable": len(runnable), "n_unmeasured": len(unmeasured),
        "rotation_window_s": window, "grace": ROTATION_GRACE,
        "stale_reason_s": STALE_REASON_S,
        "dark": dark, "stalled": stalled, "settled": sorted(settled),
        "reasons": reasons,
        "detail": (f"{len(runnable)} runnable, {len(dark)} past their rotation window; "
                   f"{len(unmeasured)} unmeasured, {len(stalled)} with a reason that has not "
                   f"moved in {STALE_REASON_S / 86400:.0f} days"),
        "next_action": (
            "a DARK row is a runnable system the rotation did not reach -- check the "
            "sandbox_runner leg's budget and its scout slots, never by removing systems. A "
            "STALLED row is an install task nobody executed: run "
            "`python desks/mt5/research/sandbox_provision.py --once --only <system>`, and if "
            "it cannot be hosted here record it PERMANENTLY_UNAVAILABLE with the exact error "
            "and the cover that carries its capability."),
    }


def main(argv: list[str] | None = None) -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    rep = build_report()
    _write(OUT, rep)
    _write(STATE, {"at": rep["at"], "reasons": rep.get("reasons") or {}})
    print(json.dumps(rep, indent=2) if args.json else
          f"sandbox liveness (LAWS 5h): {rep['status']} -- {rep['detail']}\n-> {OUT}")
    if args.report_only:
        return 0
    return fence_exit(rep["status"], _PASSING, scanned=rep["n_scanned"],
                      of="federated sandbox systems (runnable + unmeasured)",
                      fence="check_sandbox_liveness.py")


if __name__ == "__main__":
    sys.exit(main())
