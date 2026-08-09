#!/usr/bin/env python3
"""IS THE STUDY ALIVE, AND IS IT WORKING? -- one command, no shell interpolation to get wrong.

THE DEFECT THIS REPLACES, and it is a small bug with a large cost. The status check handed to the
operator was::

    ps -o pid,etime,time,%cpu,rss -p "$(pgrep -f run_full_sweep | head -1)"

which produced::

    pgrep: invalid option -- 'p'

The command spans a line break in a chat window; the terminal received the tail as a separate
argument and `-p` reached `pgrep` instead of `ps`. The operator then could not tell a running
study from a dead one -- during the exact window when that was the only question worth answering,
and immediately after a dropped connection had already destroyed one run.

The general fault is not the typo. It is that PROCESS STATUS WAS A SHELL EXPRESSION rather than a
command: every invocation re-derived it, so every invocation could get it wrong, and the failure
mode is a confusing error rather than a wrong answer that announces itself.

**ALIVE IS NOT THE SAME AS WORKING, so this reports both.** A study that is alive at 0% CPU with a
log that has not grown in an hour is stalled, and the distinction is invisible to `pgrep`. CPU
time and log mtime are read together because either alone is misleading: a niced study yields CPU
freely, and a log can be silent for a whole cell.

    python scripts/study_status.py [--pattern run_full_sweep] [--log data/full_sweep_run.log]
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Proc:
    pid: int
    etime: str
    cpu_time: str
    cpu_pct: float
    rss_kb: int
    cmd: str


def find(pattern: str) -> list[int]:
    """PIDs whose full command line matches. Empty list when none -- never an error.

    Uses `pgrep -f <pattern>` with the pattern as a SEPARATE argv entry, so no amount of quoting
    or line wrapping in a chat window can turn part of it into an option. That is the whole fix.
    """
    if not shutil.which("pgrep"):
        return []
    try:
        r = subprocess.run(["pgrep", "-f", pattern], capture_output=True, text=True,
                           timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return []
    out: list[int] = []
    for line in (r.stdout or "").split():
        try:
            out.append(int(line))
        except ValueError:
            continue
    return out


def describe(pids: list[int]) -> list[Proc]:
    """`ps` for the given pids. NEVER called with an empty pid list.

    That call is what produced the original error's sibling: `ps -p` with nothing after it is a
    usage error, and the guard is a real fix rather than defensive noise -- the empty case is the
    common one, since the whole point is to ask about a process that may not exist.
    """
    if not pids or not shutil.which("ps"):
        return []
    try:
        r = subprocess.run(
            ["ps", "-o", "pid=,etime=,time=,%cpu=,rss=,args=", "-p", ",".join(map(str, pids))],
            capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return []
    out: list[Proc] = []
    for line in (r.stdout or "").splitlines():
        parts = line.split(None, 5)
        if len(parts) < 6:
            continue
        try:
            out.append(Proc(int(parts[0]), parts[1], parts[2], float(parts[3]), int(parts[4]),
                            parts[5]))
        except ValueError:
            continue
    return out


def log_age_seconds(path: Path) -> float | None:
    """Seconds since the log was last written. None when absent -- not zero, not infinity."""
    try:
        return max(0.0, time.time() - path.stat().st_mtime)
    except OSError:
        return None


def verdict(procs: list[Proc], log_age: float | None, *, stall_seconds: float) -> tuple[str, str]:
    """(state, why). RUNNING | STALLED | ABSENT | UNMEASURED.

    STALLED exists because ALIVE IS NOT WORKING. A process at 0% CPU whose log has been silent
    longer than a plausible unit of work is the failure `pgrep` alone reports as healthy, and it
    is the one an operator most needs to distinguish from progress.
    """
    if not procs:
        return "ABSENT", ("no matching process. If a report artifact exists the run FINISHED; if "
                          "not, it died -- and a dropped SSH session is the likeliest cause when "
                          "the study was not started detached")
    p = procs[0]
    busy = p.cpu_pct >= 1.0
    if log_age is None:
        return ("RUNNING" if busy else "UNMEASURED"), (
            f"pid {p.pid} up {p.etime}, cpu {p.cpu_pct:.0f}%, cpu-time {p.cpu_time}. No log to "
            "check, so progress is inferred from CPU alone -- which a niced study can yield "
            "freely, making this weaker evidence than it looks")
    if busy or log_age < stall_seconds:
        return "RUNNING", (f"pid {p.pid} up {p.etime}, cpu {p.cpu_pct:.0f}%, cpu-time "
                           f"{p.cpu_time}, log written {log_age:.0f}s ago")
    return "STALLED", (
        f"pid {p.pid} is ALIVE but idle: cpu {p.cpu_pct:.0f}% and the log has not moved for "
        f"{log_age:.0f}s (> {stall_seconds:.0f}s). Alive is not working, and this is the state a "
        "process check alone reports as healthy")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pattern", default="run_full_sweep",
                    help="matched against the full command line, passed as one argv entry")
    ap.add_argument("--log", type=Path, default=Path("data/full_sweep_run.log"))
    ap.add_argument("--stall-seconds", type=float, default=1800.0,
                    help="log silence beyond which an idle process is called STALLED. Default 30 "
                         "minutes: a sweep cell has taken ~8 minutes on the live box, so a "
                         "shorter window would call ordinary progress a stall")
    ap.add_argument("--out", type=Path, default=Path("data/study_status.json"),
                    help="machine-readable status artifact consumed by the research cycle")
    a = ap.parse_args()

    procs = describe(find(a.pattern))
    age = log_age_seconds(a.log)
    state, why = verdict(procs, age, stall_seconds=a.stall_seconds)
    print(f"study-status [{state}] {why}")
    for p in procs[1:]:
        print(f"  also: pid {p.pid} up {p.etime} cpu {p.cpu_pct:.0f}% -- {p.cmd[:90]}")
    artifact = {
        "state": state,
        "reason": why,
        "pattern": a.pattern,
        "log": str(a.log),
        "log_age_seconds": age,
        "processes": [p.__dict__ for p in procs],
        "measured_at_unix": time.time(),
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(artifact, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
