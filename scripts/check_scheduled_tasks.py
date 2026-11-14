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
#: THE CRO CYCLE'S OWN CLOCK WAS THE ONE CLOCK THIS FENCE COULD NOT SEE (measured 2026-11-14).
#: `Install-QuantWindows.ps1` deliberately keeps the two lanes OUT of its table -- they run S4U as
#: the account holding the claude/codex logins rather than SYSTEM, and fire hourly behind a
#: Europe/Dublin window -- and says so at the table's edge, handing them to
#: `install_cro_cycle_tasks.ps1`. Nothing then added them here, so `declared()` read 26 names, all
#: present, and reported a complete clock while `MT5-CycleMidnight` HAD NEVER RUN ONCE: no
#: `desks/mt5/data/cycle_state_midnight.json` has ever existed on the box and
#: `cro_cycle_ledger.jsonl` holds 108 rows, every one of them the noon lane's. The procedure both
#: lanes execute makes each lane the independent check on the other's material work (CRO_CYCLE
#: step 2), so for the whole life of the midnight lane this desk's governing cycle has been
#: half-staffed and unverified -- and this file's own rule is that a clock which is absent is not
#: slow, it is gone, and that no artifact-reading fence can ever see it. Read from the installer
#: that owns them, never a second list, exactly as `declared()` reads the main one.
CRO_INSTALLER = DESK / "scripts" / "install_cro_cycle_tasks.ps1"
OUT = DESK / "reports" / "SCHEDULED_TASKS.json"

#: Tasks registered by installers OTHER than the main one, so their absence is still a defect.
EXTRA_DECLARED = ("MT5-AdoptRelease", "MT5-ResearchSupervisor", "MT5-ShadowSync",
                  "MT5-RiskUnitsFence", "MT5-QQuantGatesCertify",
                  # The law battery's rotation clock (install_law_gate_task.ps1) and the plumbing
                  # watchdog's own (install_plumbing_watchdog_task.ps1): both are registered by
                  # their own installers, so their absence has to be a defect here or nothing
                  # would ever notice the gate going quiet again.
                  "MT5-LawGate", "MT5-PlumbingWatchdog",
                  "E8-Executor", "E8-Book", "E8-Spreads")

#: A git writer older than this is not working, it is stuck. The adopt script waits nine minutes
#: for the mutex; anything holding it for an hour has failed in a way no timeout will resolve.
STUCK_WRITER_MIN = 60


def _cro_lanes() -> set[str]:
    """The two CRO lanes, read from `install_cro_cycle_tasks.ps1` (see CRO_INSTALLER).

    Its table quotes the names in single quotes, which the main installer's double-quoted scan
    cannot see; an unreadable installer declares nothing rather than guessing a name.
    """
    try:
        src = CRO_INSTALLER.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set()
    return set(re.findall(r"Name\s*=\s*'(MT5-[A-Za-z0-9_-]+)'", src)) | set(
        re.findall(r'Name\s*=\s*"(MT5-[A-Za-z0-9_-]+)"', src))


def declared() -> list[str]:
    """Task names the installer defines, read from the installer itself, never a second list."""
    cro = _cro_lanes()
    try:
        src = INSTALLER.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return sorted({*EXTRA_DECLARED, *cro})
    table = set(re.findall(r'Name\s*=\s*"(MT5-[A-Za-z0-9_-]+)"', src))
    registered = set(re.findall(r'Register-ScheduledTask\s+-TaskName\s+"(MT5-[A-Za-z0-9_-]+)"',
                                src))
    named = set(re.findall(r'-TaskName\s+"(MT5-[A-Za-z0-9_-]+)"', src))
    # A TASK THE INSTALLER DELETES IS NOT A TASK THE INSTALLER DECLARES (2026-09-23). The name
    # scan could not tell `Register-ScheduledTask -TaskName "X"` from
    # `Unregister-ScheduledTask -TaskName "X"`, so MT5-ArtifactSync -- which the installer
    # UNREGISTERS on purpose, its Hetzner sync decommissioned 2026-08-23 and its block saying so
    # in as many words -- was reported ABSENT from the scheduler on every pass. A defect
    # generated by the reader of the declaration, sitting in the same list as the five clocks
    # that really were gone, is how a real absence gets read as noise.
    unregister_only = {n for n in named if n not in table and n not in registered}
    return sorted(({*table, *named, *EXTRA_DECLARED, *cro}) - unregister_only)


def _ps(cmd: str) -> str:
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
                           capture_output=True, text=True, timeout=90, check=False)
        return r.stdout or ""
    except Exception:
        return ""


#: THE SCHEDULER'S OWN WORD FOR "NEVER LAUNCHED": SCHED_S_TASK_HAS_NOT_RUN, 0x00041303.
#: `LastRunTime` for such a task is the 1999-11-30 sentinel, not a date anyone chose.
NEVER_RUN_RESULT = 267011
NEVER_RUN_SENTINEL_YEAR = 1999


def task_info() -> dict[str, dict[str, str]]:
    """name -> {state, next_run, last_run, last_result}, from the scheduler itself.

    A TASK CAN BE PRESENT, ENABLED, "READY" AND STILL NEVER TICK, AND THAT IS WHAT THIS ADDS
    (measured 2026-11-14). `check` classified a task by presence and by the single word Windows
    calls its State, so MT5-CycleMidnight -- one of the two lanes of this desk's own governing
    cycle -- read PRESENT/Ready in a report whose headline was 26 of 26 present, 0 missing. The
    scheduler's own record for it was:

        LastRunTime  11/30/1999 00:00:00   (the sentinel: never)
        LastTaskResult 267011              (SCHED_S_TASK_HAS_NOT_RUN)
        NextRunTime  null                  (nothing will fire it)
        NumberOfMissedRuns 0               (never even came due)

    A registered clock with no next run time that has never run is not slow and not idle: it will
    never tick, and every artifact-reading fence downstream is blind to it in exactly the way this
    file's opening paragraph describes. The lane had produced no checkpoint and no ledger row in
    its entire existence, and nothing in the repository could say why.

    WHY THE RULE IS THREE CONDITIONS AND NOT ONE, measured on this box's 117 MT5/E8 tasks: seven
    carry no NextRunTime and only ONE of them is a defect. Four are long-running residents
    (E8-Spreads, MT5-DeskDashboard, MT5-DeskTunnel, MT5-NewsDesk) with State `Running` and
    LastTaskResult 267009 (SCHED_S_TASK_RUNNING) -- no next run because they are running now.
    Two have genuinely run and finished (MT5-FetchUniverse-Repair, result 0, 2026-09-21;
    MT5-PushBacklog, result 1, 2026-09-25). So the rule excludes anything Running and anything
    that has ever run, and on this box it fires on exactly one task. A guard whose first output
    is a false positive is a guard the next person switches off -- this file learned that from its
    own `stuck_writers`, and the same discipline applies here.
    """
    out = _ps("Get-ScheduledTask | Where-Object {$_.TaskName -like 'MT5*' -or "
              "$_.TaskName -like 'E8-*'} | ForEach-Object { $i = $_ | Get-ScheduledTaskInfo; "
              "$_.TaskName + '|' + $_.State + '|' + $i.NextRunTime + '|' + $i.LastRunTime + "
              "'|' + $i.LastTaskResult }")
    got: dict[str, dict[str, str]] = {}
    for ln in out.splitlines():
        parts = [p.strip() for p in ln.strip().split("|")]
        if len(parts) < 5 or not parts[0]:
            continue
        got[parts[0]] = {"state": parts[1], "next_run": parts[2],
                         "last_run": parts[3], "last_result": parts[4]}
    return got


def never_fires(info: dict[str, str]) -> bool:
    """Is this a registered clock that will never tick? See `task_info` for why three conditions.

    UNREADABLE FIELDS ARE NOT A DEFECT: a task whose info query returned nothing reads False
    here, so a failed PowerShell read can never manufacture a red.
    """
    state = str(info.get("state") or "").lower()
    if not state or state in ("running", "disabled"):
        return False            # running: no next run BECAUSE it is running. disabled: its own row
    if str(info.get("next_run") or "").strip():
        return False            # it has a next tick
    last_run, last_result = str(info.get("last_run") or ""), str(info.get("last_result") or "")
    if not last_run and not last_result:
        return False            # nothing measured about its history: not a defect, just unread
    if last_result.strip() == str(NEVER_RUN_RESULT):
        return True
    return f"/{NEVER_RUN_SENTINEL_YEAR} " in f"{last_run} " or last_run.startswith(
        str(NEVER_RUN_SENTINEL_YEAR))


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
    info = task_info()
    have = {name: row["state"] for name, row in info.items()} or present()
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
        elif never_fires(info.get(name) or {}):
            row = info.get(name) or {}
            rows.append({"task": name, "verdict": "NEVER_FIRED", "state": state,
                         "last_run": row.get("last_run"), "last_result": row.get("last_result"),
                         "why": ("registered and enabled with NO next run time, and it has never "
                                 "run: the scheduler has never launched it "
                                 f"(LastTaskResult {row.get('last_result')}, LastRunTime "
                                 f"{row.get('last_run')}). A clock that will never tick is not "
                                 "slow and not idle, and every artifact-reading fence downstream "
                                 "is blind to it.")})
        else:
            rows.append({"task": name, "verdict": "PRESENT", "state": state})

    missing = [r for r in rows if r["verdict"] == "MISSING"]
    disabled = [r for r in rows if r["verdict"] == "DISABLED"]
    never_fired = [r for r in rows if r["verdict"] == "NEVER_FIRED"]
    writers = stuck_writers()
    return {
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "law": ("the declared task set IS the desk's clock. A clock that is absent is not slow, "
                "it is gone -- and no artifact-reading fence can ever see it, because a task that "
                "does not exist writes nothing to read. NOR IS A CLOCK THAT WILL NEVER TICK: a "
                "task present, enabled and 'Ready' with no next run time, which has never run, "
                "is the same blindness wearing a healthy state (2026-11-14)."),
        "n_declared": len(want), "n_present": sum(1 for r in rows if r["verdict"] == "PRESENT"),
        "n_missing": len(missing), "n_disabled": len(disabled),
        "n_never_fired": len(never_fired),
        "missing": missing, "disabled": disabled, "never_fired": never_fired,
        "stuck_git_writers": writers,
        "remedy": ("powershell -ExecutionPolicy Bypass -File "
                   "desks/mt5/scripts/Install-QuantWindows.ps1 restores the whole set; "
                   "install_adopt_release_task.ps1 restores the adopt task alone and runs one "
                   "adoption immediately; install_cro_cycle_tasks.ps1 re-registers the two CRO "
                   "lanes, which is the remedy for a NEVER_FIRED lane -- re-registering rebuilds "
                   "the trigger that a task with no next run time is missing."),
        "tasks": rows,
    }


def _defects(doc: dict[str, Any]) -> bool:
    """A clock that will never tick counts with the ones that are gone (2026-11-14)."""
    return bool(doc["missing"] or doc["never_fired"] or doc["stuck_git_writers"])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    doc = check()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    if args.json:
        print(json.dumps(doc, indent=1))
        return 1 if _defects(doc) else 0

    print(f"scheduled tasks: {doc['n_present']} present of {doc['n_declared']} declared, "
          f"{doc['n_missing']} MISSING, {doc['n_disabled']} disabled, "
          f"{doc['n_never_fired']} NEVER FIRED")
    for r in doc["missing"]:
        print(f"  MISSING  {r['task']}")
    for r in doc["disabled"]:
        print(f"  disabled {r['task']}")
    for r in doc["never_fired"]:
        print(f"  NEVER FIRED {r['task']} -- no next run time, last result "
              f"{r.get('last_result')}, last run {r.get('last_run')}")
    for w in doc["stuck_git_writers"]:
        print(f"  STUCK GIT WRITER pid {w['pid']} {w['name']} {w['age_minutes']}min")
    if _defects(doc):
        print(f"  remedy: {doc['remedy']}")
    print(f"  -> {OUT}")
    return 1 if _defects(doc) else 0


if __name__ == "__main__":
    raise SystemExit(main())
