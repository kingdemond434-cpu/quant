#!/usr/bin/env python
"""THE BOX MUST HAVE ADOPTED WITHIN ITS OWN CADENCE -- the fence for the four-day silence.

`Adopt-And-Seal.ps1` is the ONLY durable path from origin to the machine that trades. When it
stops, nothing else breaks: the gateway keeps placing risk, every organ keeps writing artifacts,
every task table still reads "Ready", and the desk runs last week's code with a straight face.
That is not hypothetical twice over -- it lasted four days in September 2026, and it happened
again on 2026-09-24 with a full night of shipped work sitting on origin.

WHAT THE SECOND OUTAGE ACTUALLY WAS, because the fence is shaped by it.

`MT5-AdoptRelease` carried `ExecutionTimeLimit = PT50M` against an HOURLY trigger. A cold
adoption -- the box was 443 commits behind -- does not fit in fifty minutes, because a chunked
`git add` that loses the index.lock race falls back to one `git add --all -- <path>` per path and
each of those re-scans a 24,000-path worktree. So every hour the scheduler STOPPED the run
mid-write and recorded

    LastTaskResult = 2147946720 == 0x800710E0 == Win32 4320
                     "The operator or administrator has refused the request"

and, on the run before it, 267014 == 0x41306 == SCHED_S_TASK_TERMINATED. Both are the
SCHEDULER's codes for an instance it stopped. Neither is produced by any line of the adoption,
and that is the whole problem: the kill lands BETWEEN statements, so the log of a killed run is
byte-identical to the log of a run still in progress, and the artifact of a killed run is the
artifact the previous success left behind. Every signal the desk had said "in progress".

(Measured the same night, because the obvious reading was wrong and cost time: 0x800710E0 is NOT
0x80070520/1312 "a specified logon session does not exist". 0x80070520 is 2147943712, a different
number, and ZERO tasks on the box carried it. Of the 31 tasks carrying 0x800710E0, thirty ran as
SYSTEM/ServiceAccount, which has no logon session to lose. An S4U/interactive-principal theory
fits neither the code nor the principal, and `MT5-AdoptRelease` has always been S-1-5-18.)

SO THE FENCE READS A POSITIVE FACT, NOT AN ABSENCE. `Adopt-And-Seal.ps1` stamps
`ADOPTION_HEARTBEAT.json` with `started_at` when it begins and `finished_at` when it ends. A run
that was killed leaves the first and never the second -- a thing that can be SEEN, rather than a
silence that has to be inferred. Three breaches, each one of them sufficient:

  (a) NO SUCCESS WITHIN THE GRACE. The cadence is read from the task's own trigger where the
      scheduler can be asked, so the fence cannot drift from the clock it judges. Grace is three
      cadences: one missed hour is a contended lock and heals itself, three in a row is an
      outage. `ok` in the heartbeat, the last success line in `adopt_and_seal.log`, and
      `ADOPTION_STATE.measured_at` are all accepted as evidence of a success, because the
      heartbeat only exists on boxes running the code that writes it.
  (b) A RUN THAT STARTED AND NEVER FINISHED, older than one execution time limit. That is the
      signature of the kill above, and it is the one the four days of silence never had.
  (c) HEAD BEHIND origin FOR LONGER THAN THE GRACE. The end that matters: adoption can be
      "succeeding" every hour and still leave the box behind if it succeeds by refusing.

UNMEASURED IS NOT A PASS, AND NOT-APPLICABLE IS NOT UNMEASURED. A host with the adoption task or
any adoption artifact is an ADOPTING host and must produce evidence; if it produces none, that is
UNMEASURED and it FAILS, because "no artifact" is exactly what the outage looks like (L1.28a). A
host with neither -- CI, a fresh clone, the VPS -- is NOT_APPLICABLE and passes saying so, since
a gate red on every machine that was never supposed to adopt is a gate that gets switched off
(L1.43).

THIS FENCE NEVER REDUCES ANYTHING. It caps no risk and gates no capital; it fails a check when
the trading box is running code that is not the shipped code. Registered in
`scripts/run_law_gate.py` `_STATE_FENCES`.

Artifact: `desks/mt5/reports/ADOPTION_FRESHNESS.json`.

    python scripts/check_adoption_freshness.py
    python scripts/check_adoption_freshness.py --json
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DESK = ROOT / "desks" / "mt5"
OUT = DESK / "reports" / "ADOPTION_FRESHNESS.json"

HEARTBEAT = DESK / "reports" / "ADOPTION_HEARTBEAT.json"
ADOPTION_STATE = DESK / "reports" / "ADOPTION_STATE.json"
ADOPT_LOG = DESK / "logs" / "adopt_and_seal.log"
ADOPT_SCRIPT = DESK / "scripts" / "Adopt-And-Seal.ps1"

TASK = "MT5-AdoptRelease"

#: Fallback cadence when the scheduler cannot be asked. The task is registered hourly at :12.
DEFAULT_CADENCE_S = 3600
#: Consecutive missed adoptions tolerated. One is a contended index lock and heals itself.
GRACE_CADENCES = 3
#: Fallback for "how long may a run legitimately be in flight" when the limit cannot be read.
DEFAULT_LIMIT_S = 7200

UNMEASURED = "UNMEASURED"

#: Exit codes that belong to the TASK SCHEDULER, not to the adoption. 2147946720 is 0x800710E0
#: (Win32 4320, "the operator or administrator has refused the request") and 267014 is
#: SCHED_S_TASK_TERMINATED; both mean an instance was stopped from outside. Any OTHER non-zero
#: code is the script's own exit and must not be explained as a scheduler kill.
_SCHEDULER_KILL_CODES = frozenset({"2147946720", "267014"})

#: Lines `Adopt-And-Seal.ps1` writes on a SUCCESSFUL pass. "nothing to seal" is a success: it is
#: what an already-current box says, and counting it as a failure would red every healthy hour.
_SUCCESS_LINE = re.compile(r"adopt-and-seal:\s+(sealed\s+\w+\s+from|HEAD\s+\w+\s+is\s+(already\s+the\s+sealed|the\s+sealed\s+release))")
_LOG_STAMP = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})Z")
_ISO_DUR = re.compile(r"^P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$")


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _parse_iso(text: str) -> datetime | None:
    raw = (text or "").strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        stamp = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return stamp if stamp.tzinfo else stamp.replace(tzinfo=UTC)


def _parse_duration(text: str) -> int | None:
    """ISO-8601 duration as the scheduler writes it (PT50M, PT2H, P1D) -> seconds."""
    m = _ISO_DUR.match((text or "").strip())
    if not m or not any(m.groups()):
        return None
    days, hours, minutes, seconds = (int(g) if g else 0 for g in m.groups())
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def _age_s(stamp: datetime | None, now: datetime) -> float | None:
    return None if stamp is None else (now - stamp).total_seconds()


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError):
        return None
    return loaded if isinstance(loaded, dict) else None


def _git(root: Path, *args: str, timeout: float = 120.0) -> tuple[int, str]:
    try:
        r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True,
                           errors="replace", timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return -1, ""
    return r.returncode, r.stdout


def _powershell(script: str, timeout: float = 90.0) -> str:
    """Empty string when the scheduler cannot be asked -- never read as a clean answer."""
    if sys.platform != "win32":
        return ""
    try:
        r = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                           capture_output=True, text=True, errors="replace", timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return ""
    return r.stdout if r.returncode == 0 else ""


def read_task(doc: dict[str, Any]) -> None:
    """Cadence, execution limit and last result, from the scheduler that owns the clock."""
    out = _powershell(
        f'$t = Get-ScheduledTask -TaskName "{TASK}" -ErrorAction SilentlyContinue; '
        'if ($null -eq $t) { "ABSENT" } else { '
        '$i = Get-ScheduledTaskInfo -TaskName $t.TaskName -TaskPath $t.TaskPath '
        '-ErrorAction SilentlyContinue; '
        '"state=" + $t.State; "limit=" + $t.Settings.ExecutionTimeLimit; '
        '"logon=" + $t.Principal.LogonType; "user=" + $t.Principal.UserId; '
        'foreach ($g in $t.Triggers) { "repeat=" + $g.Repetition.Interval }; '
        'if ($i) { "lastresult=" + $i.LastTaskResult; "lastrun=" + '
        '$i.LastRunTime.ToUniversalTime().ToString("o") } }')
    task: dict[str, Any] = {"name": TASK, "present": False}
    if not out.strip():
        task["queried"] = False
        doc["task"] = task
        return
    task["queried"] = True
    if "ABSENT" in out:
        doc["task"] = task
        return
    task["present"] = True
    for line in out.splitlines():
        key, _, value = line.strip().partition("=")
        if key and value:
            task[key] = value.strip()
    cadence = _parse_duration(str(task.get("repeat", "")))
    if cadence:
        task["cadence_s"] = cadence
    limit = _parse_duration(str(task.get("limit", "")))
    if limit:
        task["limit_s"] = limit
    doc["task"] = task


def read_evidence(root: Path, doc: dict[str, Any], now: datetime) -> None:
    """Every independent witness of a successful adoption, and the in-flight run."""
    hb = _read_json(HEARTBEAT)
    doc["heartbeat"] = {"present": hb is not None}
    successes: list[dict[str, Any]] = []
    if hb is not None:
        started, finished = _parse_iso(str(hb.get("started_at", ""))), _parse_iso(str(hb.get("finished_at") or ""))
        doc["heartbeat"].update({
            "started_at": hb.get("started_at"), "finished_at": hb.get("finished_at"),
            "exit_code": hb.get("exit_code"), "stage": hb.get("stage"), "ok": bool(hb.get("ok")),
            "head_before": hb.get("head_before"), "head_after": hb.get("head_after"),
            "started_age_s": _age_s(started, now),
            "unfinished": finished is None and started is not None,
        })
        if hb.get("ok") and finished is not None:
            successes.append({"source": "heartbeat", "at": finished.isoformat(),
                              "age_s": _age_s(finished, now)})

    state = _read_json(ADOPTION_STATE)
    doc["adoption_state"] = {"present": state is not None}
    if state is not None:
        measured = _parse_iso(str(state.get("measured_at", "")))
        doc["adoption_state"].update({"measured_at": state.get("measured_at"),
                                      "ok": bool(state.get("ok")),
                                      "age_s": _age_s(measured, now)})
        if state.get("ok") and measured is not None:
            successes.append({"source": "adoption_state", "at": measured.isoformat(),
                              "age_s": _age_s(measured, now)})

    # The log is the oldest witness and the only one a box running pre-heartbeat code has.
    doc["log"] = {"present": ADOPT_LOG.exists()}
    if ADOPT_LOG.exists():
        try:
            lines = ADOPT_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            lines = []
        doc["log"]["lines"] = len(lines)
        for line in reversed(lines[-4000:]):
            if not _SUCCESS_LINE.search(line):
                continue
            m = _LOG_STAMP.match(line)
            stamp = _parse_iso(m.group(1) + "Z") if m else None
            if stamp is not None:
                doc["log"]["last_success"] = stamp.isoformat()
                successes.append({"source": "adopt_log", "at": stamp.isoformat(),
                                  "age_s": _age_s(stamp, now)})
            break

    doc["successes"] = successes
    ages = [s["age_s"] for s in successes if isinstance(s.get("age_s"), (int, float))]
    doc["last_success_age_s"] = min(ages) if ages else None

    branch = ""
    try:
        text = ADOPT_SCRIPT.read_text(encoding="utf-8", errors="replace")
        m = re.search(r'\$Branch\s*=\s*"([^"]+)"', text)
        branch = m.group(1) if m else ""
    except OSError:
        branch = ""
    lag: dict[str, Any] = {"branch": branch or UNMEASURED}
    if branch:
        rc, out = _git(root, "rev-list", "--count", f"HEAD..origin/{branch}")
        if rc == 0 and out.strip().isdigit():
            lag["behind"] = int(out.strip())
        else:
            lag["behind"] = None
            lag["why"] = f"could not count HEAD..origin/{branch}"
        # HOW LONG THE BOX HAS BEEN REFUSING, measured by the MERGE BASE and nothing else.
        # `behind` alone cannot answer it: origin gains commits all night, so a perfectly
        # healthy box reads behind>0 almost always, and HEAD alone cannot either, because the
        # box commits its own state every fifteen minutes and so moves HEAD without adopting a
        # single line of origin's code. What a box that "succeeds by refusing" never does is
        # ADVANCE ITS MERGE BASE: it logs `nothing to seal` every hour while the base stays
        # pinned. That is the positive fact, so it is the one carried forward.
        rc, out = _git(root, "merge-base", "HEAD", f"origin/{branch}")
        base_sha = out.strip() if rc == 0 and out.strip() else ""
        lag["merge_base"] = base_sha or None
        prev = _read_json(OUT) or {}
        prev_lag = prev.get("lag") if isinstance(prev.get("lag"), dict) else {}
        prev_base = str((prev_lag or {}).get("merge_base") or "")
        prev_since = _parse_iso(str((prev_lag or {}).get("merge_base_since") or ""))
        if base_sha and prev_base == base_sha and prev_since is not None:
            lag["merge_base_since"] = prev_since.isoformat()
        elif base_sha:
            # First sighting of this base (or the base just advanced, which is an adoption
            # working): the clock starts now.
            lag["merge_base_since"] = now.isoformat()
        stuck_since = _parse_iso(str(lag.get("merge_base_since") or ""))
        lag["merge_base_age_s"] = _age_s(stuck_since, now)
    doc["lag"] = lag


def judge(doc: dict[str, Any]) -> None:
    task = doc.get("task", {})
    cadence = int(task.get("cadence_s") or DEFAULT_CADENCE_S)
    limit = int(task.get("limit_s") or DEFAULT_LIMIT_S)
    grace = cadence * GRACE_CADENCES
    doc["cadence_s"], doc["grace_s"], doc["limit_s"] = cadence, grace, limit

    adopting = bool(task.get("present")) or any(
        doc.get(k, {}).get("present") for k in ("heartbeat", "adoption_state", "log"))
    doc["adopting_host"] = adopting
    problems: list[str] = doc.setdefault("problems", [])
    notes: list[str] = doc.setdefault("notes", [])

    if not adopting:
        doc["verdict"] = "NOT_APPLICABLE"
        doc["ok"] = True
        notes.append(
            f"no {TASK} task and no adoption artifact on this host: it is not an adopting box, "
            "so there is nothing here to judge. NOT_APPLICABLE is not UNMEASURED")
        return

    age = doc.get("last_success_age_s")
    if age is None:
        doc["verdict"] = UNMEASURED
        doc["ok"] = False
        problems.append(
            "this host adopts, and NO witness of a successful adoption could be read "
            "(heartbeat, ADOPTION_STATE.json, adopt_and_seal.log all silent). An absent "
            "artifact is exactly what the outage looks like, so UNMEASURED fails (L1.28a)")
    elif age > grace:
        doc["ok"] = False
        doc["verdict"] = "STALE"
        problems.append(
            f"the last successful adoption was {age / 3600:.1f}h ago, past the "
            f"{grace / 3600:.1f}h grace ({GRACE_CADENCES} x {cadence / 3600:.1f}h cadence). "
            "The gateway is running code that is not the shipped code")
    else:
        doc["verdict"] = "FRESH"
        doc["ok"] = True

    hb = doc.get("heartbeat", {})
    started_age = hb.get("started_age_s")
    if hb.get("unfinished") and isinstance(started_age, (int, float)) and started_age > limit:
        doc["ok"] = False
        problems.append(
            f"an adoption started {started_age / 3600:.1f}h ago at stage "
            f"'{hb.get('stage')}' and never recorded finishing -- longer than the task's own "
            f"{limit / 3600:.1f}h execution limit. That is the signature of a run the SCHEDULER "
            "stopped (0x800710E0 / SCHED_S_TASK_TERMINATED), which no line of the adoption can "
            "report for itself")

    behind = doc.get("lag", {}).get("behind")
    base_age = doc.get("lag", {}).get("merge_base_age_s")
    if behind is None:
        notes.append("commits-behind could not be counted, so the lag half is UNMEASURED")
    elif behind > 0 and isinstance(base_age, (int, float)) and base_age > grace:
        # BREACH (c), AND IT NO LONGER HIDES BEHIND BREACH (a). This clause used to read
        # `behind > 0 and age > grace`, so it could only fire in the one case where the STALE
        # branch above had already failed the check -- which made the end that matters
        # unreachable on its own.
        #
        # MEASURED ON THE TRADING BOX, 2026-09-24, and the numbers are the argument. Merge
        # records that actually landed came 1.4 h, 2.4 h and 2.3 h apart overnight and then
        # STOPPED FOR 7.4 HOURS (05:41 -> 13:03 box local). Through the whole of that gap
        # `adopt_and_seal.log` kept recording successes -- "HEAD ... is the sealed release ...
        # nothing to seal" at 06:51, 07:34, 08:49 and 09:17 UTC -- and `_SUCCESS_LINE` counts
        # those, correctly, because an already-current box says exactly that. So at 09:55:39Z
        # this fence measured `last_success_age_s` = 2295 s (0.6 h) against a 3 h grace and
        # published verdict FRESH, while the last merge to land was 6.2 h old and the merge base
        # had been pinned at b8ab5342 since 11:17. The box drifted from 1 to 9 commits behind
        # with the gate green. That is "succeeding by refusing", which the docstring says this
        # clause exists for, and the old form could not see it.
        doc["ok"] = False
        problems.append(
            f"HEAD is {behind} commit(s) behind origin/{doc['lag'].get('branch')} and the merge "
            f"base has not advanced for {base_age / 3600:.1f}h, past the {grace / 3600:.1f}h "
            "grace. Adoption may be reporting success every hour and still not landing origin's "
            "code: a success that never moves the merge base is a refusal with a green light")
    elif behind > 0:
        notes.append(f"HEAD is {behind} commit(s) behind origin/{doc['lag'].get('branch')}; "
                     "inside the grace, so an adoption in flight still covers it")

    last = task.get("lastresult")
    # THE SCHEDULER'S CODES AND THE SCRIPT'S OWN ARE NOT THE SAME DIAGNOSIS, and this note used
    # to give the scheduler's explanation for BOTH. Measured 2026-09-24: `MT5-AdoptRelease` read
    # `lastresult = 3`, which is `Adopt-And-Seal.ps1` exiting on its own after refusing to seal
    # (`dirty-code-path`) -- and the fence explained it as "the SCHEDULER stopped the run --
    # raise ExecutionTimeLimit, do not hunt the script", which is the exact opposite of where
    # the defect was. A wrong reason costs a session, so the two are now separated by code.
    if last in _SCHEDULER_KILL_CODES:
        notes.append(
            f"{TASK} last exited {last}; 2147946720 (0x800710E0, Win32 4320 'the operator or "
            "administrator has refused the request') and 267014 (SCHED_S_TASK_TERMINATED) both "
            "mean the SCHEDULER stopped the run -- raise ExecutionTimeLimit, do not hunt the "
            "script")
    elif last not in (None, "0", "267009", "267011"):
        notes.append(
            f"{TASK} last exited {last}, which is not one of the scheduler's own codes -- it is "
            "the adoption script's own exit status. Read `desks/mt5/logs/adopt_and_seal.log` and "
            "`ADOPTION_HEARTBEAT.stage` for the reason; the scheduler did not stop this run")


def scan(root: Path | None = None) -> dict[str, Any]:
    base = Path(root or ROOT)
    now = _now()
    doc: dict[str, Any] = {
        "generated": now.isoformat(timespec="seconds"), "root": str(base),
        "problems": [], "notes": [], "ok": True,
    }
    read_task(doc)
    read_evidence(base, doc, now)
    judge(doc)
    return doc


def write_artifact(doc: dict[str, Any], target: Path | None = None) -> Path:
    path = Path(target or OUT)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, default=str) + "\n", encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--json", action="store_true", help="print the artifact as JSON")
    ap.add_argument("--no-write", action="store_true", help="do not write the artifact")
    args = ap.parse_args(argv)

    doc = scan()
    if not args.no_write:
        write_artifact(doc)
    if args.json:
        print(json.dumps(doc, indent=2, default=str))
        return 0 if doc["ok"] else 2

    age = doc.get("last_success_age_s")
    age_txt = f"{age / 3600:.1f}h ago" if isinstance(age, (int, float)) else UNMEASURED
    behind = doc.get("lag", {}).get("behind")
    print(f"adoption: {doc.get('verdict')}; last success {age_txt}; "
          f"behind origin {behind if behind is not None else UNMEASURED}; "
          f"grace {doc.get('grace_s', 0) / 3600:.1f}h")
    for note in doc["notes"]:
        print(f"  note: {note}")
    for problem in doc["problems"]:
        print(f"  FAIL: {problem}")
    if doc["ok"]:
        print("check_adoption_freshness: OK -- the box has adopted within its own cadence")
        return 0
    print("check_adoption_freshness: FAILED -- the trading box is not running the shipped code")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
