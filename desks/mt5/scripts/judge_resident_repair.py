#!/usr/bin/env python3
"""THE JUDGE RESIDENT REPAIR: a wedged gauntlet resident is restarted, not only paged.

    python desks/mt5/scripts/judge_resident_repair.py            # rides MT5-BoxHeartbeat (5 min)
    python desks/mt5/scripts/judge_resident_repair.py --dry-run  # measure and print, act on nothing

WHY (2026-11-19). `judge_stall_pager.py` already reads the resident's heartbeat and pages
`resident_dead`, but nothing acted on it. The scheduler cannot either: MT5-Gauntlet repeats every
minute with IgnoreNew, so while a wedged resident process is still alive every repetition is
REFUSED (result 0x800710E0; 79 of them in one 24h window), and the control plane's
`restart_resident` is `schtasks /Run`, which is refused the same way. A hung judge therefore sat
hung until a human ended it. This ends it.

WHAT IT READS: `desks/mt5/reports/JUDGE_RESIDENT.json` (`heartbeat_utc`, `status`, `pid`) and
whether `desks/mt5/data/RESIDENT_STOP` exists. Nothing else.

THE VERDICT, one of four:
  HELD        the operator stop file exists, or the resident says STOPPED/DONE. Healthy: it is
              stopped on purpose, and nothing is done.
  UNMEASURED  JUDGE_RESIDENT.json is absent or unreadable, or holds no parseable heartbeat.
              A verdict, never a licence to act (L1.28a): nothing is done.
  HEALTHY     the heartbeat is at most HEARTBEAT_STALE_S old.
  WEDGED      the heartbeat is older than HEARTBEAT_STALE_S, or further in the future than
              FUTURE_SKEW_S. The heartbeat thread re-stamps every 30 s; its measured age over 491
              healthy snapshots was p99 1.5 min, max 2.2 min
              (judge_stall_pager.HEARTBEAT_STALE_MIN).
              A long sweep does NOT stale it -- the thread beat straight through the 18h sweeps --
              so this never ends a legitimate sweep, which a pass-age threshold would.

THE REPAIR, on WEDGED only, on the box only: `schtasks /End /TN MT5-Gauntlet`, then
`schtasks /Run /TN MT5-Gauntlet`. The new resident's own `take_over_stale()` then records or kills
the prior sweep child and clears its locks, so the restart never waits behind a corpse. Rate
limit: at most one attempt per REPAIR_MIN_INTERVAL_S. Postcondition, read on the next run: a
heartbeat stamped after the attempt, from a pid other than the wedged one, is CONFIRMED; still
stale after the interval is FAILED, counted in `consecutive_failed`, and the pager's
`resident_dead` page keeps standing for the human.

Off the trading host (libs.ops.host_identity `may_be_trading` false, or unreadable) it measures
and prints and never acts: every checkout holds a published copy of JUDGE_RESIDENT.json whose
heartbeat is hours old.

Clock: MT5-BoxHeartbeat (every 5 minutes; box_heartbeat.main invokes it as a 40 s-bounded
subprocess BEFORE the stall pager, so both fit the task's 2-minute limit).
Artifact: `desks/mt5/reports/JUDGE_RESIDENT_REPAIR.json`. State
(box-local, gitignored): `desks/mt5/logs/judge_resident_repair.json`.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import subprocess
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parent.parent
for _p in (str(ROOT),):
    if _p not in sys.path:
        sys.path.insert(0, _p)

RESIDENT = BASE / "reports" / "JUDGE_RESIDENT.json"
RESIDENT_STOP = BASE / "data" / "RESIDENT_STOP"
OUT = BASE / "reports" / "JUDGE_RESIDENT_REPAIR.json"
STATE = BASE / "logs" / "judge_resident_repair.json"
TASK = "MT5-Gauntlet"

#: Seconds before the heartbeat is stale: judge_stall_pager.HEARTBEAT_STALE_MIN (10 min), whose
#: measurement is quoted in the module docstring.
HEARTBEAT_STALE_S = 600.0
#: How far ahead of this clock a stamp may sit and still be read (the repo's existing tolerance).
FUTURE_SKEW_S = 300.0
#: At most one End+Run per hour: a resident needs minutes to start and beat, and a restart that
#: did not take is a human's problem after the first try, not a loop's.
REPAIR_MIN_INTERVAL_S = 3600.0
#: Each schtasks call is bounded; the whole script sits inside box_heartbeat's 40 s budget.
SCHTASKS_TIMEOUT_S = 15.0
OPERATOR_STOPPED = ("STOPPED", "DONE")

Runner = Callable[[list[str]], int]


def _stamp(txt: object) -> datetime | None:
    s = str(txt or "").strip()
    if not s:
        return None
    try:
        at = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    return at.astimezone(UTC) if at.tzinfo else None


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def measure(now: datetime | None = None, *, resident: Path = RESIDENT,
            stop: Path = RESIDENT_STOP) -> dict[str, Any]:
    """The verdict on the resident's liveness. Pure read; never raises."""
    at = now or datetime.now(UTC)
    if stop.exists():
        return {"verdict": "HELD", "why": f"operator stop file {stop.name} is in force"}
    doc = _read_json(resident)
    if not isinstance(doc, dict):
        return {"verdict": "UNMEASURED", "why": f"{resident.name} absent or unreadable"}
    status = str(doc.get("status") or "")
    base = {"status": status, "pid": doc.get("pid"), "heartbeat_utc": doc.get("heartbeat_utc")}
    if status in OPERATOR_STOPPED:
        return {**base, "verdict": "HELD", "why": f"resident {status} on purpose"}
    hb = _stamp(doc.get("heartbeat_utc"))
    if hb is None:
        return {**base, "verdict": "UNMEASURED", "why": "no parseable heartbeat_utc"}
    age = (at - hb).total_seconds()
    base["heartbeat_age_s"] = round(age, 1)
    if age < -FUTURE_SKEW_S:
        return {**base, "verdict": "WEDGED",
                "why": f"heartbeat {-age:.0f}s in the future, past the {FUTURE_SKEW_S:g}s skew"}
    if age > HEARTBEAT_STALE_S:
        return {**base, "verdict": "WEDGED",
                "why": f"heartbeat {age:.0f}s old (limit {HEARTBEAT_STALE_S:g}s)"}
    return {**base, "verdict": "HEALTHY", "why": f"heartbeat {max(age, 0):.0f}s old"}


def _schtasks(args: list[str]) -> int:
    try:
        r = subprocess.run(["schtasks", *args], capture_output=True, check=False,
                           timeout=SCHTASKS_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return -2
    except OSError:
        return -1
    return int(r.returncode)


def _postcondition(prev: dict[str, Any], reading: dict[str, Any], at: datetime) -> str | None:
    """CONFIRMED / FAILED / None (still pending, or nothing to check) for the last attempt."""
    attempt = prev.get("last_attempt") if isinstance(prev, dict) else None
    if not isinstance(attempt, dict) or attempt.get("outcome") not in (None, "PENDING"):
        return None
    tried = _stamp(attempt.get("at"))
    if tried is None:
        return "FAILED"
    hb = _stamp(reading.get("heartbeat_utc"))
    if (reading.get("verdict") == "HEALTHY" and hb is not None and hb > tried
            and str(reading.get("pid")) != str(attempt.get("wedged_pid"))):
        return "CONFIRMED"
    if reading.get("verdict") == "HELD":
        return "CONFIRMED" if hb is not None and hb > tried else None
    if (at - tried).total_seconds() >= REPAIR_MIN_INTERVAL_S:
        return "FAILED"
    return None


def run(*, dry_run: bool = False, now: datetime | None = None, on_box: bool | None = None,
        runner: Runner = _schtasks, resident: Path = RESIDENT, stop: Path = RESIDENT_STOP,
        out: Path = OUT, state: Path = STATE) -> dict[str, Any]:
    at = now or datetime.now(UTC)
    reading = measure(at, resident=resident, stop=stop)
    prev = _read_json(state)
    prev = prev if isinstance(prev, dict) else {}
    doc: dict[str, Any] = {"at": at.isoformat(timespec="seconds"), "reading": reading,
                           "task": TASK, "action": None}
    if on_box is None:
        try:
            from libs.ops import host_identity
            on_box = bool(host_identity.identify().may_be_trading)
        except Exception:
            on_box = False      # never End a task on a machine that cannot name itself
    if dry_run or not on_box:
        doc["action"] = {"taken": False, "reason": "dry run" if dry_run else "off box"}
        return doc
    new = dict(prev)
    outcome = _postcondition(prev, reading, at)
    if outcome is not None:
        new["last_attempt"] = {**prev["last_attempt"], "outcome": outcome,
                               "checked_at": doc["at"]}
        new["consecutive_failed"] = (int(prev.get("consecutive_failed") or 0) + 1
                                     if outcome == "FAILED" else 0)
    if reading["verdict"] == "WEDGED":
        last = _stamp((prev.get("last_attempt") or {}).get("at"))
        if last is not None and (at - last).total_seconds() < REPAIR_MIN_INTERVAL_S:
            doc["action"] = {"taken": False,
                             "reason": f"rate limited: last attempt {last.isoformat()}"}
        else:
            end_rc = runner(["/End", "/TN", TASK])
            run_rc = runner(["/Run", "/TN", TASK])
            new["last_attempt"] = {"at": doc["at"], "wedged_pid": reading.get("pid"),
                                   "why": reading.get("why"), "end_rc": end_rc,
                                   "run_rc": run_rc, "outcome": "PENDING"}
            new["attempts"] = int(prev.get("attempts") or 0) + 1
            doc["action"] = {"taken": True, "end_rc": end_rc, "run_rc": run_rc}
    else:
        doc["action"] = {"taken": False, "reason": f"resident {reading['verdict']}"}
    doc["state"] = new
    for path, body in ((state, new), (out, doc)):
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
        try:
            tmp.write_text(json.dumps(body, indent=1, default=str), "utf-8")
            os.replace(tmp, path)
        finally:
            with contextlib.suppress(OSError):
                tmp.unlink(missing_ok=True)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    doc = run(dry_run=a.dry_run)
    print(json.dumps({"verdict": doc["reading"]["verdict"], "why": doc["reading"].get("why"),
                      "action": doc["action"]}, default=str))
    return 0


__all__ = ["HEARTBEAT_STALE_S", "REPAIR_MIN_INTERVAL_S", "main", "measure", "run"]


if __name__ == "__main__":
    raise SystemExit(main())
