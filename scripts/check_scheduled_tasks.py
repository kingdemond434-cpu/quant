"""THE DESK'S CLOCKS MUST EXIST. A missing scheduled task is the failure nothing else can see.

WHAT HAPPENED, 2026-09-15, and it is the most expensive thing found in this entire campaign.
`Get-ScheduledTask` on the trading box returned TWO tasks: `MT5-DashMirror` and a disabled
`MT5DataSyncToVps`. The installer declares TWENTY. Eighteen were simply gone -- MT5-Gateway,
MT5-Hourly, MT5-Daily, MT5-AdoptRelease, MT5-Shadow, MT5-Gauntlet, every one of them.

That single fact explains every "operational" complaint made about this desk for a month:

    sync_marker frozen since 2026-08-17      no MT5-Hourly, so no cycle ever completed
    the box never adopted                    no MT5-AdoptRelease
    the box stopped pushing state            no sync task
    gateway_state frozen at 2026-09-12       no MT5-Gateway
    forex sleeves never traded               the gateway that places them was not running
    pf_allocation 32 hours stale             no MT5-AllocatorFast

And NOTHING IN THE REPOSITORY COULD SEE IT. Every fence this desk owns reads an artifact and
judges it. A task that does not exist writes no artifact, produces no error, and fails no check --
it is indistinguishable from a task that ran and found nothing to do. `check_completion` reported
legs as STALE; `check_dead_architecture` reported organs with nothing on the other end. Both were
downstream symptoms of one upstream absence that neither could name.

A SECOND HOLDER OF THE SAME CLASS: a hung `ssh.exe` from 2026-09-12 01:18 held the named mutex
`Local\\MT5-GitWriter` for THREE DAYS. Every adopt since was refused with "another git writer held
the mutex for the full 9 min" -- correct, polite, and permanently wrong. So this also checks for
git writers older than any plausible operation.

THE RULE: the declared task set is the desk's clock, and a clock that is absent is not slow, it is
gone. This check is the only thing standing between "the desk is running" and "the desk looks like
it is running because its artifacts are old but present".

    python scripts/check_scheduled_tasks.py
    python scripts/check_scheduled_tasks.py --json
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DESK = ROOT / "desks" / "mt5"
INSTALLER = DESK / "scripts" / "Install-QuantWindows.ps1"
OUT = DESK / "reports" / "SCHEDULED_TASKS.json"

#: Tasks registered by installers OTHER than the main one, so their absence is still a defect.
EXTRA_DECLARED = ("MT5-AdoptRelease", "MT5-ResearchSupervisor", "MT5-ShadowSync",
                  "MT5-RiskUnitsFence", "MT5-QQuantGatesCertify",
                  "E8-Executor", "E8-Book", "E8-Spreads")

#: A git writer older than this is not working, it is stuck. The adopt script waits nine minutes
#: for the mutex; anything holding it for an hour has failed in a way no timeout will resolve.
STUCK_WRITER_MIN = 60


def declared() -> list[str]:
    """Task names the installer defines, read from the installer itself, never a second list."""
    try:
        src = INSTALLER.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return list(EXTRA_DECLARED)
    names = re.findall(r'Name\s*=\s*"(MT5-[A-Za-z0-9_-]+)"', src)
    names += re.findall(r'-TaskName\s+"(MT5-[A-Za-z0-9_-]+)"', src)
    return sorted({*names, *EXTRA_DECLARED})


def _ps(cmd: str) -> str:
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
                           capture_output=True, text=True, timeout=90, check=False)
        return r.stdout or ""
    except Exception:
        return ""


def present() -> dict[str, str]:
    """name -> state, from the scheduler itself. Empty means the query failed, not that none exist."""
    out = _ps("Get-ScheduledTask | Where-Object {$_.TaskName -like 'MT5*' -or "
              "$_.TaskName -like 'E8-*'} | ForEach-Object { $_.TaskName + '=' + $_.State }")
    got: dict[str, str] = {}
    for ln in out.splitlines():
        ln = ln.strip()
        if "=" in ln:
            k, _, v = ln.partition("=")
            got[k.strip()] = v.strip()
    return got


def stuck_writers() -> list[dict[str, Any]]:
    """git/ssh processes old enough that they are stuck rather than busy."""
    # `ssh.exe` and `git.exe` ONLY. `sshd.exe` is the SSH SERVER: a long-lived daemon by design,
    # and matching it reported a healthy 3.9-day-old service as a stuck writer on the first run.
    # A guard whose first output is a false positive is a guard the next person switches off.
    out = _ps(r"Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^(ssh|git)\.exe$' } | "
              "ForEach-Object { $_.ProcessId.ToString() + '|' + $_.Name + '|' + "
              "((Get-Date) - $_.CreationDate).TotalMinutes.ToString('F0') }")
    rows: list[dict[str, Any]] = []
    for ln in out.splitlines():
        parts = ln.strip().split("|")
        if len(parts) != 3:
            continue
        try:
            age = int(parts[2])
        except ValueError:
            continue
        if age >= STUCK_WRITER_MIN:
            rows.append({"pid": parts[0], "name": parts[1], "age_minutes": age,
                         "why": (f"a {parts[1]} process {age} minutes old. The adopt script waits "
                                 f"nine minutes for Local\\MT5-GitWriter; anything holding it this "
                                 f"long has failed in a way no timeout resolves. A hung ssh from "
                                 f"2026-09-12 held it for THREE DAYS and refused every adopt.")})
    return rows


def check() -> dict[str, Any]:
    want = declared()
    have = present()
    queried = bool(have)
    rows: list[dict[str, Any]] = []
    for name in want:
        state = have.get(name)
        if not queried:
            rows.append({"task": name, "verdict": "UNMEASURED",
                         "why": "the scheduler could not be queried on this host"})
        elif state is None:
            rows.append({"task": name, "verdict": "MISSING",
                         "why": ("declared by the installer and ABSENT from the scheduler. A task "
                                 "that does not exist writes no artifact and fails no check: it "
                                 "is indistinguishable from one that ran and found nothing.")})
        elif str(state).lower() == "disabled":
            rows.append({"task": name, "verdict": "DISABLED", "state": state,
                         "why": "registered and disabled: it will never fire"})
        else:
            rows.append({"task": name, "verdict": "PRESENT", "state": state})

    missing = [r for r in rows if r["verdict"] == "MISSING"]
    disabled = [r for r in rows if r["verdict"] == "DISABLED"]
    writers = stuck_writers()
    return {
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "law": ("the declared task set IS the desk's clock. A clock that is absent is not slow, "
                "it is gone -- and no artifact-reading fence can ever see it, because a task that "
                "does not exist writes nothing to read."),
        "n_declared": len(want), "n_present": sum(1 for r in rows if r["verdict"] == "PRESENT"),
        "n_missing": len(missing), "n_disabled": len(disabled),
        "missing": missing, "disabled": disabled,
        "stuck_git_writers": writers,
        "remedy": ("powershell -ExecutionPolicy Bypass -File "
                   "desks/mt5/scripts/Install-QuantWindows.ps1 restores the whole set; "
                   "install_adopt_release_task.ps1 restores the adopt task alone and runs one "
                   "adoption immediately."),
        "tasks": rows,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    doc = check()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    if args.json:
        print(json.dumps(doc, indent=1))
        return 1 if (doc["missing"] or doc["stuck_git_writers"]) else 0

    print(f"scheduled tasks: {doc['n_present']} present of {doc['n_declared']} declared, "
          f"{doc['n_missing']} MISSING, {doc['n_disabled']} disabled")
    for r in doc["missing"]:
        print(f"  MISSING  {r['task']}")
    for r in doc["disabled"]:
        print(f"  disabled {r['task']}")
    for w in doc["stuck_git_writers"]:
        print(f"  STUCK GIT WRITER pid {w['pid']} {w['name']} {w['age_minutes']}min")
    if doc["missing"] or doc["stuck_git_writers"]:
        print(f"  remedy: {doc['remedy']}")
    print(f"  -> {OUT}")
    return 1 if (doc["missing"] or doc["stuck_git_writers"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
