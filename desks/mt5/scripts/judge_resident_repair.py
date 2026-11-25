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

THE VERDICT:
  HELD        the operator stop file exists, or the resident says STOPPED/DONE. Healthy: it is
              stopped on purpose, and nothing is done.
  UNMEASURED  JUDGE_RESIDENT.json is absent or unreadable, or holds no parseable heartbeat; or
              the heartbeat is stale and the second signal cannot be measured. Nothing is done.
  HEALTHY     the heartbeat is at most HEARTBEAT_STALE_S old.
  BUSY        the heartbeat is stale but the sweep child's own beat is fresh, or the process
              tree is working over a live sample. Only the stall pager's page stands.
  WEDGED      the heartbeat is older than HEARTBEAT_STALE_S (or past FUTURE_SKEW_S in the
              future) AND a second signal holds: the pid is not alive as the heartbeat's writer,
              or the whole tree is measured idle (under NO_PROGRESS_CORES and NO_PROGRESS_IO_BPS
              over IDLE_SAMPLE_S). A quiet heartbeat alone never ends anything (audit HOLD of
              75e5ae62c; the rule take_over_stale records from the HOLD of 2832cebd1). The
              heartbeat's measured healthy age: p99 1.5 min, max 2.2 min
              (judge_stall_pager.HEARTBEAT_STALE_MIN).

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
import time
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
SWEEP_HEARTBEAT = BASE / "reports" / "GAUNTLET_HEARTBEAT.json"
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
SCHTASKS_TIMEOUT_S = 10.0
#: THE SECOND SIGNAL (audit HOLD of 75e5ae62c). The resident's heartbeat thread suppresses only
#: RuntimeError, so another exception silences the beats while the sweep keeps judging; a quiet
#: heartbeat alone would end a healthy 18h sweep. The task is ended only when the heartbeat is
#: stale AND the resident is not alive as the heartbeat's writer OR its whole process tree is
#: measured idle over a live sample -- the rule take_over_stale records (audit HOLD of
#: 2832cebd1: kill only on measured idleness) and its thresholds: under NO_PROGRESS_CORES of CPU
#: and NO_PROGRESS_IO_BPS of I/O. A sweep child whose own beat (GAUNTLET_HEARTBEAT.json) is fresh
#: vetoes the end outright. Anything unmeasured, or a busy tree, only pages (the stall pager).
IDLE_SAMPLE_S = 10.0
NO_PROGRESS_CORES = 0.02
NO_PROGRESS_IO_BPS = 65536.0
#: A process created more than this long after the stamp that names its pid is not that process.
PID_START_SKEW_S = 300.0
OPERATOR_STOPPED = ("STOPPED", "DONE")

Runner = Callable[[list[str]], int]
#: (cpu seconds, io bytes) summed over a pid and its descendants; None when not measurable.
TreeSampler = Callable[[int], "tuple[float, float] | None"]
PidAliveAs = Callable[[object, "datetime | None"], "bool | None"]


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
    base = {"status": status, "pid": doc.get("pid"), "heartbeat_utc": doc.get("heartbeat_utc"),
            "started_utc": doc.get("started_utc")}
    if status in OPERATOR_STOPPED:
        return {**base, "verdict": "HELD", "why": f"resident {status} on purpose"}
    hb = _stamp(doc.get("heartbeat_utc"))
    if hb is None:
        return {**base, "verdict": "UNMEASURED", "why": "no parseable heartbeat_utc"}
    age = (at - hb).total_seconds()
    base["heartbeat_age_s"] = round(age, 1)
    if age < -FUTURE_SKEW_S:
        return {**base, "verdict": "STALE",
                "why": f"heartbeat {-age:.0f}s in the future, past the {FUTURE_SKEW_S:g}s skew"}
    if age > HEARTBEAT_STALE_S:
        return {**base, "verdict": "STALE",
                "why": f"heartbeat {age:.0f}s old (limit {HEARTBEAT_STALE_S:g}s)"}
    return {**base, "verdict": "HEALTHY", "why": f"heartbeat {max(age, 0):.0f}s old"}


def _pid_alive_as(pid: object, started: datetime | None) -> bool | None:
    """Is `pid` the process `started` names? psutil only (os.kill TERMINATES on Windows).
    False: gone, or created after `started` + skew (a reused pid). None: unmeasurable."""
    try:
        n = int(pid)  # type: ignore[call-overload]
    except (TypeError, ValueError):
        return None
    if n <= 0:
        return None
    try:
        import psutil  # type: ignore[import-untyped]
    except ImportError:
        return None
    try:
        if not psutil.pid_exists(n):
            return False
        if started is None:
            return None
        created = float(psutil.Process(n).create_time())
    except psutil.NoSuchProcess:
        return False
    except Exception:
        return None
    return created <= started.timestamp() + PID_START_SKEW_S


def _tree_sample(pid: int) -> tuple[float, float] | None:
    """CPU seconds and I/O bytes of `pid` and every descendant. ONE UNREADABLE PROCESS MAKES THE
    TREE UNMEASURED (the rule of run_sharded_gauntlet._sample_tree, audit of be522dd44)."""
    try:
        import psutil
        root = psutil.Process(pid)
        procs = [root, *root.children(recursive=True)]
    except Exception:
        return None
    cpu = io = 0.0
    for p in procs:
        try:
            t = p.cpu_times()
            c = p.io_counters()
        except psutil.NoSuchProcess:
            continue
        except Exception:
            return None
        cpu += float(t.user) + float(t.system)
        io += float(c.read_bytes) + float(c.write_bytes)
    return cpu, io


def second_signal(reading: dict[str, Any], at: datetime, *, sweep: Path = SWEEP_HEARTBEAT,
                  alive_as: PidAliveAs = _pid_alive_as, tree: TreeSampler = _tree_sample,
                  sleep: Callable[[float], Any] = time.sleep,
                  sample_s: float = IDLE_SAMPLE_S) -> dict[str, Any]:
    """WEDGED (end it), BUSY (page only) or UNMEASURED (page only) for a STALE reading."""
    sw = _read_json(sweep)
    if isinstance(sw, dict) and sw.get("status") == "RUNNING":
        beat = _stamp(sw.get("beat_utc"))
        if beat is not None and abs((at - beat).total_seconds()) <= HEARTBEAT_STALE_S:
            return {"verdict": "BUSY", "signal": "sweep_beat_fresh",
                    "why": f"the sweep child's own beat {sw.get('beat_utc')} is fresh"}
    alive = alive_as(reading.get("pid"), _stamp(reading.get("started_utc")))
    if alive is False:
        return {"verdict": "WEDGED", "signal": "pid_not_writer",
                "why": f"pid {reading.get('pid')} is not alive as the heartbeat's writer"}
    if alive is None:
        return {"verdict": "UNMEASURED", "signal": None,
                "why": f"pid {reading.get('pid')} liveness unmeasurable"}
    pid = int(reading["pid"])
    first = tree(pid)
    sleep(sample_s)
    second = tree(pid) if first is not None else None
    if first is None or second is None:
        return {"verdict": "UNMEASURED", "signal": None, "why": "process tree unmeasurable"}
    span = max(sample_s, 1e-6)
    cores = (second[0] - first[0]) / span
    bps = (second[1] - first[1]) / span
    measured = {"cores": round(cores, 4), "io_bps": round(bps, 1), "sample_s": sample_s}
    if cores < 0 or bps < 0:
        return {"verdict": "BUSY", "signal": None, **measured,
                "why": "tree totals fell (processes exited): activity, not idleness"}
    if cores < NO_PROGRESS_CORES and bps < NO_PROGRESS_IO_BPS:
        return {"verdict": "WEDGED", "signal": "tree_idle", **measured,
                "why": f"tree idle over {sample_s:g}s: {cores:.3f} cores, {bps:.0f} B/s"}
    return {"verdict": "BUSY", "signal": None, **measured,
            "why": f"tree working over {sample_s:g}s: {cores:.3f} cores, {bps:.0f} B/s"}


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
        sweep: Path = SWEEP_HEARTBEAT, alive_as: PidAliveAs = _pid_alive_as,
        tree: TreeSampler = _tree_sample, sleep: Callable[[float], Any] = time.sleep,
        sample_s: float = IDLE_SAMPLE_S,
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
    if reading["verdict"] == "STALE":
        sig = second_signal(reading, at, sweep=sweep, alive_as=alive_as, tree=tree,
                            sleep=sleep, sample_s=sample_s)
        reading["second_signal"] = sig
        reading["verdict"] = sig["verdict"]
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
