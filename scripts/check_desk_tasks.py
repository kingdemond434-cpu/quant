#!/usr/bin/env python3
"""DESK-BOX SCHEDULER FENCE -- a disabled task is a silently stopped organ.

WHY (measured 2026-08-26). Stopping the gauntlet process mid-sweep left its Windows scheduled task
in the Disabled state. The task then had an enabled trigger and a valid next-run time and still
would never have fired again -- hourly CONVERSION would have stopped permanently while every
artifact on the research box stayed exactly as fresh as the last successful run, and nothing
anywhere would have said so. It was found by reading the task state by hand.

That is the same shape as every other silent-stop this desk has hit: the tape recorder exiting 0
on ModuleNotFoundError, shadow_cycle exiting 1 for an unknown period, promotion_gate publishing
NO-PRODUCER and returning 0. The pattern is always an organ whose FAILURE MODE IS SILENCE, and
the answer is always the same -- check the thing that actually matters rather than the exit code.

Here that thing is the task STATE on the box that runs it. The research box cannot see Windows
Task Scheduler from its own systemd, so this asks over the SSH identity already used for deploys.

An UNREACHABLE desk box is reported as UNREACHABLE, never as healthy: "we could not check" and
"it checks out" are different answers (L1.28a), and treating the first as the second is how a
dead box looks fine for a week.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "desk_tasks.json"
ALARM = ROOT / "data" / "DESK_TASKS_ALARM.txt"
REMOTE = "contabo-mt5"

#: task -> what stops if it stops. Named so an alarm says what is lost, not just what is off.
CRITICAL = {
    "MT5-Gauntlet": "hourly CONVERSION -- certificates stop being produced entirely",
    "MT5-Shadow": "forward clocks stop accruing; evidence freezes while day counters run",
    "MT5-Hourly": "the tick tape and bar refresh stop; every downstream input goes stale",
    "MT5-DeskState": "the dashboard stops reflecting the live account",
}
HEALTHY = {"Ready", "Running"}


def main() -> int:
    now = datetime.now(tz=UTC)
    # A DEPLOYED SCRIPT, NOT AN INLINE COMMAND. Passing PowerShell through ssh from Python mangles
    # the nested quoting -- the same query that works by hand returned nothing here, and the
    # fence read that as UNREACHABLE. A check whose own transport is fragile manufactures the
    # alarm it exists to detect, so the query lives in a file on the box.
    try:
        r = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=25", REMOTE,
             "powershell -ExecutionPolicy Bypass -File C:/opt/quant/task_states.ps1"],
            capture_output=True, text=True, timeout=90, check=False)
        raw = " ".join(x for x in r.stdout.split() if "=" in x)
    except (OSError, subprocess.SubprocessError) as exc:
        # The exception text goes into the artifact rather than a dropped local: an UNREACHABLE
        # report that cannot say WHY is one an operator has to reproduce by hand.
        raw = ""
        transport_error = f"{type(exc).__name__}: {exc}"
    else:
        transport_error = None
    if not raw:
        why = ("desk box UNREACHABLE -- this is not a clean bill of health. Every conversion "
               "organ lives on that box, so an unanswered check means the desk's certificate "
               "production is in an UNKNOWN state, not a working one.")
        OUT.write_text(json.dumps({"checked_at": now.isoformat(timespec="seconds"),
                                   "status": "UNREACHABLE", "why": why,
                                   "transport_error": transport_error}, indent=1), "utf-8")
        ALARM.write_text(f"DESK TASKS UNREACHABLE {now.isoformat(timespec='seconds')}\n\n{why}\n",
                         "utf-8")
        print(f"desk tasks: UNREACHABLE -- {why}")
        return 1

    states = {}
    for part in raw.replace(";", " ").split():
        if "=" in part:
            k, v = part.split("=", 1)
            states[k] = v
    bad = {k: v for k, v in states.items() if v not in HEALTHY}

    OUT.write_text(json.dumps({"checked_at": now.isoformat(timespec="seconds"),
                               "states": states, "unhealthy": bad,
                               "status": "OK" if not bad else "STOPPED"}, indent=1), "utf-8")
    if not bad:
        if ALARM.exists():
            ALARM.unlink()
        print(f"desk tasks: all {len(states)} critical task(s) healthy {states}")
        return 0

    lines = [f"  - {k} is {v} -- {CRITICAL.get(k, 'unknown organ')}" for k, v in sorted(bad.items())]
    body = (f"DESK TASKS STOPPED {now.isoformat(timespec='seconds')}\n\n" + "\n".join(lines) +
            "\n\n  A Disabled task keeps an enabled trigger and a valid next-run time and still "
            "never fires. Re-enable with:\n"
            "    ssh contabo-mt5 \"powershell -Command Enable-ScheduledTask -TaskName <name>\"\n")
    ALARM.write_text(body, "utf-8")
    print(body)
    return 1


if __name__ == "__main__":
    sys.exit(main())
