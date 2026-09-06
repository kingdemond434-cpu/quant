#!/usr/bin/env python3
"""THE THREE-HOURLY MINER MAINTAINER -- runs every miner and seat check, and REPAIRS what it can.

    "make sure the fund miner and implementer crawler all miners r always optimal and the
     3 hr every local fixer here maintains them"          -- the principal, 2026-09-05

WHY A MAINTAINER AND NOT A SEVENTH CHECKER. This desk already has six miner and seat fences and
they work: `check_miner_health` (a source whose rows are all fetch errors is DOWN),
`check_miner_conversion`, `check_miner_runway`, `check_organ_liveness`, `check_organ_readiness`,
`check_seat_launch_yield`. Measured 2026-09-05, two of the six were on NO SCHEDULE at all --
`check_miner_health` and `check_organ_readiness`, the two that answer "is this miner producing
anything real" and "could this seat even start" -- and no single thing ran the set or acted on
what any of them found. Detection without an actuator is this desk's most repeated defect class,
and `check_miner_health`'s own docstring says so about the fence it replaced.

So this runs all six on one clock and then DOES something about the answers.

WHAT IT REPAIRS, and every repair is bounded and reversible:

    stale job lock, owner dead      remove it -- a dead owner's lock starves the next run for
                                    STALE_SECONDS and is the single cheapest miner outage there is
    stale job lock, owner ALIVE     LEFT ALONE and reported. Liveness vetoes age: reclaiming a
                                    live holder's lock is what produced two concurrent sweeps on
                                    an 8GB box and saturated it so completely that ssh could not
                                    complete. A long job is not an abandoned one.
    admission figure inflated by    the outlier ages out of the peak window on its own now
    one pathological run            (job_lock admits on p75), so this only REPORTS the tail
    miner all-errors for 7d         reported with its wall verdict; a §13 refusal or an anti-bot
                                    challenge is a decision the desk already made, not a fault
    seat never launched today       reported for organ_catchup, which owns re-firing

WHAT IT WILL NEVER DO. It does not restart the gateway, touch live positions, widen a gate,
re-arm a killed seat, or write into the trading path. A maintainer that can act on capital is a
second trading system with none of the governance; everything here is confined to the research
lane's own scaffolding -- locks, schedules, and reports.

THE THREE STATES ARE KEPT APART, because collapsing them is how a fixer becomes a liar:

    REPAIRED        something was wrong, this fixed it, and the report says exactly what it did
    UNREPAIRABLE    something is wrong and this cannot fix it -- NAMED, with the reason, never
                    silently skipped and never counted as healthy
    OK              nothing was wrong

A run in which every check errors and nothing is repairable reports UNREPAIRABLE, not OK. Absence
of a repair is not evidence of health (L1.28a).

    python scripts/run_miner_maintenance.py [--json] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REPORT = ROOT / "desks" / "mt5" / "reports" / "MINER_MAINTENANCE.json"
LOCK_ROOT = ROOT / "desks" / "mt5" / "data" / ".job_locks"

#: Every miner and seat fence on the desk, run on one clock. A check missing from here is a check
#: nothing runs at this cadence -- which is how two of the six ended up on no schedule at all.
CHECKS: tuple[tuple[str, str], ...] = (
    ("miner_health", "scripts/check_miner_health.py"),
    ("miner_conversion", "scripts/check_miner_conversion.py"),
    ("miner_runway", "scripts/check_miner_runway.py"),
    ("organ_liveness", "scripts/check_organ_liveness.py"),
    ("organ_readiness", "scripts/check_organ_readiness.py"),
    ("seat_launch_yield", "scripts/check_seat_launch_yield.py"),
)

#: Seconds a lock may be held before its age is even considered. Matches
#: `job_lock.STALE_SECONDS`; restated rather than imported so this script runs on a box where the
#: desk package is not importable, which is the state a maintainer most needs to work in.
STALE_SECONDS = 45 * 60

#: Per-check wall clock. Generous -- these fences read artifacts rather than compute -- but bounded,
#: because a maintainer that hangs is an outage of the thing that was supposed to notice outages.
CHECK_TIMEOUT_SEC = 240


def _run(rel: str) -> dict[str, Any]:
    """One fence, bounded, with its verdict captured rather than inferred."""
    path = ROOT / rel
    if not path.exists():
        return {"status": "MISSING", "why": f"{rel} does not exist on this tree"}
    try:
        r = subprocess.run([sys.executable, "-u", str(path)], capture_output=True, text=True,
                           cwd=str(ROOT), timeout=CHECK_TIMEOUT_SEC, check=False)
    except subprocess.TimeoutExpired:
        return {"status": "TIMEOUT", "why": f"exceeded {CHECK_TIMEOUT_SEC}s"}
    except Exception as exc:
        return {"status": "ERROR", "why": f"{type(exc).__name__}: {exc}"}
    out = (r.stdout or "") + (r.stderr or "")
    return {
        "status": "OK" if r.returncode == 0 else "FAILING",
        "exit_code": r.returncode,
        "tail": out.strip().splitlines()[-4:] if out.strip() else [],
    }


def _owner_alive(pid: int) -> bool | None:
    """True / False / None-if-unknowable. The third state is why this is not a bool.

    A maintainer that cannot tell "the owner is gone" from "I cannot ask" must not delete a lock:
    on a host where liveness is unreadable, every lock would look abandoned and the fixer would
    become the outage. Unknown is treated as ALIVE everywhere below.
    """
    if pid <= 0:
        return None
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True            # exists, owned by another user
    except OSError:
        return None
    return True


def sweep_locks(dry_run: bool = False) -> list[dict[str, Any]]:
    """Remove job locks whose owner is provably dead. Leave every other lock exactly alone.

    THE CHEAPEST MINER OUTAGE THERE IS. A job killed by the OOM killer, a reboot, or a `kill -9`
    leaves its lock file behind; every subsequent run of that job then refuses to start until the
    lock ages past STALE_SECONDS, and on a 45-minute stale timer with an hourly trigger that is a
    guaranteed missed hour and often several.

    LIVENESS VETOES AGE, and this is the half that must not be got wrong. An old lock whose owner
    is RUNNING is not abandoned, it is busy -- sweeps here legitimately run 60-90 minutes against
    a 45-minute timer. Reclaiming one produced two concurrent external_gauntlet processes on an
    8GB box that also runs the live terminal, and saturated it so completely that ssh could not
    complete. So this deletes only on PROOF of death, and treats an unreadable pid as alive.
    """
    out: list[dict[str, Any]] = []
    if not LOCK_ROOT.is_dir():
        return out
    now = time.time()
    for p in sorted(LOCK_ROOT.glob("*.json")):
        if p.name.endswith(".peaks.json"):
            continue
        try:
            row = json.loads(p.read_text("utf-8"))
            age = now - p.stat().st_mtime
        except (OSError, json.JSONDecodeError) as exc:
            out.append({"lock": p.name, "action": "UNREPAIRABLE",
                        "why": f"unreadable ({type(exc).__name__}) -- a torn write, not an "
                               f"abandoned job; left in place for a human"})
            continue
        pid = int(row.get("pid") or 0)
        alive = _owner_alive(pid)
        if alive is False:
            if not dry_run:
                try:
                    p.unlink()
                except OSError as exc:
                    out.append({"lock": p.name, "action": "UNREPAIRABLE", "why": str(exc)})
                    continue
            out.append({"lock": p.name, "action": "REPAIRED", "pid": pid,
                        "age_min": round(age / 60, 1),
                        "why": "owner pid is gone; the lock would have starved the next "
                               f"{max(0, STALE_SECONDS - age) / 60:.0f}min of triggers"})
        elif age > STALE_SECONDS:
            out.append({"lock": p.name, "action": "LEFT_ALONE", "pid": pid,
                        "age_min": round(age / 60, 1),
                        "why": "older than the stale timer but its owner is "
                               f"{'ALIVE' if alive else 'UNKNOWABLE'} -- a long job is not an "
                               "abandoned one, and reclaiming a live holder's lock is how two "
                               "concurrent sweeps once saturated the box"})
    return out


def admission_tails() -> list[dict[str, Any]]:
    """Jobs whose recent memory peaks have a long tail, reported rather than repaired.

    Nothing to fix here since `job_lock.measured_need_mb` moved to p75 -- a single pathological
    run now ages out of the window instead of setting the admission figure for the next eight.
    What is worth SAYING is which jobs have a tail at all: a job whose worst run is several times
    its typical one will still lose admission races on a busy box, and that is a research-cost
    signal rather than a fault.
    """
    out: list[dict[str, Any]] = []
    if not LOCK_ROOT.is_dir():
        return out
    for p in sorted(LOCK_ROOT.glob("*.peaks.json")):
        try:
            peaks = [int(v) for v in json.loads(p.read_text("utf-8")) if v]
        except (OSError, ValueError, TypeError):
            continue
        if len(peaks) < 3:
            continue
        ordered = sorted(peaks)
        typical = ordered[min(len(ordered) - 1, int(0.75 * len(ordered)))]
        if ordered[-1] > 2 * typical:
            out.append({"job": p.name.replace(".peaks.json", ""),
                        "typical_mb": typical, "worst_mb": ordered[-1], "runs": len(peaks),
                        "note": "worst run is more than twice the typical one -- it will lose "
                                "admission races on a busy box even though it is admitted on "
                                "the p75. A tail worth explaining, not a fault to repair."})
    return out


def run(dry_run: bool = False) -> dict[str, Any]:
    checks = {name: _run(rel) for name, rel in CHECKS}
    locks = sweep_locks(dry_run)
    tails = admission_tails()

    failing = sorted(n for n, v in checks.items() if v["status"] not in ("OK",))
    repaired = [row for row in locks if row["action"] == "REPAIRED"]
    unrepairable = [row for row in locks if row["action"] == "UNREPAIRABLE"]

    if unrepairable or failing:
        status = "UNREPAIRABLE"
    elif repaired:
        status = "REPAIRED"
    else:
        status = "OK"

    return {
        "at": datetime.now(UTC).isoformat(),
        "status": status,
        "dry_run": bool(dry_run),
        "checks": checks,
        "checks_failing": failing,
        "locks": locks,
        "repaired": len(repaired),
        "unrepairable": len(unrepairable),
        "admission_tails": tails,
        "law": ("REPAIRED, UNREPAIRABLE and OK are three different answers. A run that repairs "
                "nothing because it could repair nothing is UNREPAIRABLE, never OK -- absence of "
                "a repair is not evidence of health."),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would be repaired; touch nothing")
    args = ap.parse_args(argv)
    doc = run(dry_run=args.dry_run)
    try:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    except OSError:
        pass
    if args.json:
        print(json.dumps(doc, indent=1, default=str))
    else:
        print(f"miner maintenance: {len(CHECKS)} check(s), {doc['repaired']} repaired, "
              f"{doc['unrepairable']} unrepairable -- {doc['status']}")
        for name, v in doc["checks"].items():
            print(f"  {v['status']:9s} {name}")
            for line in v.get("tail", [])[-2:]:
                print(f"              {line[:110]}")
        for row in doc["locks"]:
            print(f"  {row['action']:13s} {row.get('lock', '')} -- {row['why'][:96]}")
        for row in doc["admission_tails"]:
            print(f"  TAIL          {row['job']}: typical {row['typical_mb']}MB, "
                  f"worst {row['worst_mb']}MB over {row['runs']} runs")
    # NON-ZERO ONLY ON UNREPAIRABLE. A run that fixed something did its job and must not page:
    # a maintainer whose success exits non-zero teaches its scheduler to ignore it.
    return 2 if doc["status"] == "UNREPAIRABLE" else 0


if __name__ == "__main__":
    raise SystemExit(main())
