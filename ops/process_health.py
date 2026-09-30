"""EVERY PROCESS THIS DESK RUNS, when it last worked, and whether it is healthy.

THE PRINCIPAL'S ASK, 2026-09-12: "make sure theres a section which shows every single process
names in quant and when it last worked n if its healthy, genuinely every single built process we
have so i can monitor everyday n notice if anything ever goes stale or not working reverted etc".

WHY THIS IS NOT `organ_contract.py`. That file holds a curated list of organs to their artifacts
and is the right instrument for "is the desk's work getting done". It is the wrong instrument for
"show me everything", because a curated list can only ever report on what somebody remembered to
curate -- and the failure the principal keeps hitting is a process nobody remembered. So this
enumerates the SCHEDULER, which is the box's own record of what it is supposed to run, and joins
the contracts onto it. A task with no contract is reported as UNCONTRACTED rather than omitted:
that is the gap, named, instead of an absence that reads as health.

THE THREE FACTS THAT DISAGREE, and all three are published because each catches a different lie:

    scheduler     did Windows start it, when, and what did it return
    artifact      did anything actually appear on disk, and how old is it
    contract      how old is it allowed to be before that is a defect

A task can be Ready with LastTaskResult 0 and have produced nothing for a day -- that is the
"green run is weak evidence" shape this desk has been burned by repeatedly, most recently on
2026-09-11 when MT5-Gateway reported success for 84 minutes while the terminal sat in session 0
and every MT5 call timed out. Only the artifact clock catches that, and only the contract says
how long is too long.

RESULT CODES ARE TRANSLATED, because 2147942402 means nothing to a person reading a dashboard at
speed and "the system cannot find the file specified" means everything.
"""
from __future__ import annotations

import csv
import io
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "desks" / "mt5" / "reports" / "process_health.json"

#: Windows scheduled-task result codes this desk has actually seen, in plain words. Anything not
#: here is reported as its raw code rather than guessed at.
RESULT_MEANING: dict[int, str] = {
    0: "OK",
    1: "generic failure (the script itself returned 1)",
    2: "file not found",
    10: "the environment is incorrect",
    267009: "currently running",
    267011: "has not run yet",
    267014: "terminated by the scheduler (time limit or Stop)",
    2147750687: "an instance is already running and the policy said do not start another",
    2147942401: "the system cannot find the file specified",
    2147942402: "the system cannot find the path specified",
    2147942405: "access denied",
    2147943645: "no logged-on interactive session (an Interactive task with nobody signed in)",
    3221225786: "terminated by Ctrl+C / console close",
    # `_normalise_code` folds the signed forms schtasks prints onto these unsigned ones, so each
    # outcome has exactly ONE entry here and a verdict never depends on which tool read the row.
    2147946720: "the operator or administrator refused the request (task stopped or refused)",
    3221225794: "STATUS_DLL_INIT_FAILED -- usually desktop heap exhaustion in session 0",
}


#: Where Windows keeps one file per registered task, named by the task. Listing it is the SECOND
#: opinion on "which tasks exist" when `schtasks` itself cannot answer -- it carries no run
#: results, only existence, which is exactly the fact NOT_SCHEDULED asserts.
TASKS_DIR = Path(r"C:\Windows\System32\Tasks")

#: How long one `schtasks /query /v` may take. The box has measured `schtasks /Change` timing out
#: at 60 s (CRO noon 2026-09-30) and CIM hanging outright, so a slow scheduler is a real state of
#: this machine, not a hypothetical; the bound is what turns it into a named reading.
SCHTASKS_TIMEOUT_S = 180


def _scheduler_read() -> tuple[list[dict[str, str]], dict[str, Any]]:
    """Every scheduled task the box knows about, AND whether that answer was actually read.

    `schtasks /query /v /fo CSV` is used rather than the PowerShell cmdlets because it needs no
    module import, returns one flat table, and is the same source the operator sees in the GUI.

    THE DEFECT THIS SPLIT ENDS (CRO noon 2026-09-30: "101 silent scheduled failures, 71
    NOT_SCHEDULED"). The old reader returned `[]` for a timeout, a non-zero exit and an empty
    table alike, and `build()` then reported EVERY contracted organ as NOT_SCHEDULED -- "it cannot
    run at all" -- because none of them appeared in a list nobody had read. The contract table
    held exactly 71 organs that day, and exactly 71 were reported NOT_SCHEDULED, including the
    hourly cycle that was writing the very ledger the review read. A failed read is UNMEASURED
    (L1.28a), never a verdict about the organs, so the read's own outcome now rides beside the
    rows and the join refuses to convert its absence into 71 defects.

    When `schtasks` cannot answer, the task directory is listed as a second opinion: it proves
    which tasks EXIST (enough to rule NOT_SCHEDULED in or out) while run results stay UNMEASURED.
    """
    meta: dict[str, Any] = {"source": "schtasks", "read": False, "why": ""}
    rows: list[dict[str, str]] = []
    try:
        proc = subprocess.run(["schtasks", "/query", "/v", "/fo", "CSV"],
                              capture_output=True, text=True, timeout=SCHTASKS_TIMEOUT_S)
    except FileNotFoundError:
        meta["why"] = "no schtasks on this host (not a Windows box): nothing to join against"
        proc = None
    except subprocess.TimeoutExpired:
        meta["why"] = f"schtasks /query did not answer within {SCHTASKS_TIMEOUT_S}s"
        proc = None
    except (OSError, subprocess.SubprocessError) as exc:
        meta["why"] = f"schtasks /query could not start: {type(exc).__name__}: {exc}"
        proc = None
    if proc is not None:
        if proc.returncode != 0:
            meta["why"] = (f"schtasks /query exited {proc.returncode}: "
                           f"{(proc.stderr or proc.stdout or '').strip()[:200]}")
        elif not proc.stdout.strip():
            meta["why"] = "schtasks /query returned an empty table"
        else:
            for row in csv.DictReader(io.StringIO(proc.stdout)):
                name = (row.get("TaskName") or "").strip()
                # schtasks repeats the header row per folder; skip those and the Microsoft tree.
                if not name or name == "TaskName" or name.startswith("\\Microsoft"):
                    continue
                rows.append(row)
            if rows:
                meta["read"] = True
            else:
                meta["why"] = ("schtasks /query answered but no row carried a TaskName column -- "
                               "a localised or changed CSV header")
    if meta["read"]:
        return rows, meta
    # THE SECOND OPINION: existence only. A row built from a file name has no result and no
    # state, so it can prove "scheduled" and can never prove "healthy".
    try:
        names = sorted(e.name for e in TASKS_DIR.iterdir() if e.is_file())
    except OSError:
        names = []
    if names:
        meta.update({"source": "tasks_dir", "existence_only": True,
                     "why": meta["why"] + f"; existence read from {TASKS_DIR} instead"})
        rows = [{"TaskName": "\\" + n, "_existence_only": "1"} for n in names]
    return rows, meta


def _tasks() -> list[dict[str, str]]:
    """The task rows alone (kept for callers that only want the table)."""
    return _scheduler_read()[0]


def owner_task(organ: str) -> str:
    """The scheduled task that OWNS a contract row.

    A contract named `MT5-FrontierAudit (orthogonality)` is one artifact of the MT5-FrontierAudit
    task, not a task of its own -- `organ_contract.py` says so of its own suffix convention. The
    join compared the whole string to the scheduler's names, so all 31 suffixed rows read
    NOT_SCHEDULED on every pass even when the scheduler read succeeded: the `MT5-Gauntlet-Rotation`
    scar that file records, repeated thirty-one times by the convention written to cure it.
    """
    return organ.split(" (", 1)[0].strip()


def _normalise_code(raw: Any) -> int:
    """One task result, as ONE number, whichever tool printed it.

    THE BUG THIS ENDS, found on this file's own first day (2026-09-12). `schtasks` prints result
    codes SIGNED and the PowerShell cmdlets print them UNSIGNED, so the same outcome appears as
    -2147020576 and 2147946720 -- two entries in any lookup table, and a verdict that depends on
    which tool happened to read the row. The first run of this module reported MT5-Hourly,
    MT5-LocalDashboard and MT5-MoatRecorder-Watchdog as FAILING when all three were simply
    RUNNING: 267009 ("currently running") was recognised, and its signed sibling was not.

    A monitor that cries wolf is worse than no monitor, because the operator learns to scroll
    past it -- which is exactly the attention this board exists to spend well.
    """
    try:
        code = int(str(raw or "0").strip() or 0)
    except ValueError:
        return 0
    return code + 0x1_0000_0000 if code < 0 else code


def _age_min(path: Path) -> float | None:
    try:
        return (datetime.now(tz=UTC).timestamp() - path.stat().st_mtime) / 60.0
    except OSError:
        return None


def _contracts() -> dict[str, tuple[str, int, str]]:
    """The curated organ -> (artifact, max_age_min, purpose) map, if it is importable."""
    try:
        sys.path.insert(0, str(ROOT / "ops"))
        from organ_contract import CONTRACTS  # type: ignore[import-not-found]
        return dict(CONTRACTS)
    except Exception:
        return {}


def build() -> dict[str, Any]:
    contracts = _contracts()
    now = datetime.now(tz=UTC)
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    tasks, sched = _scheduler_read()
    existence_only = bool(sched.get("existence_only"))
    for t in tasks:
        name = (t.get("TaskName") or "").strip().lstrip("\\")
        seen.add(name)
        code = _normalise_code(t.get("Last Result"))
        artifact, max_age, purpose = contracts.get(name, ("", 0, ""))
        age = _age_min(ROOT / artifact) if artifact else None
        if existence_only and not artifact:
            # A file name proves the task exists and nothing else; without a contract there is
            # no second fact to judge it by, so it is not a row worth a verdict.
            continue

        # THE VERDICT IS THE WORST OF THE THREE FACTS, never an average of them. A task that is
        # Disabled is not "half healthy" because its artifact happens to be fresh; a task that
        # returned 0 is not healthy if nothing appeared. Averaging is how a board reassures.
        _state = str(t.get("Scheduled Task State") or t.get("Status") or "").strip().lower()
        if _state == "disabled":
            verdict, why = "DISABLED", "the scheduler will never start this"
        elif artifact and age is None:
            verdict, why = "NO_ARTIFACT", f"{artifact} does not exist"
        elif artifact and max_age and age is not None and age > max_age:
            verdict, why = "STALE", f"{age:.0f} min old against a {max_age} min contract"
        elif existence_only:
            # A file name proves the task exists; it says nothing about how its last run ended.
            # A fresh artifact is one fact of three, and the verdict is the worst of the facts it
            # has, so the run result stays UNMEASURED rather than being read as OK (audit R-ph).
            verdict, why = ("UNMEASURED",
                            "scheduled (task file present), artifact current; run result "
                            "UNMEASURED -- " + str(sched.get("why") or ""))
        elif code not in (0, 267009, 267011):
            verdict, why = "FAILING", RESULT_MEANING.get(code, f"exit code {code}")
        elif not artifact:
            verdict, why = "UNCONTRACTED", ("no artifact contract: this process could stop and "
                                            "nothing would notice")
        else:
            verdict, why = "OK", ""

        rows.append({
            "name": name,
            "verdict": verdict,
            "why": why,
            "state": (t.get("Scheduled Task State") or t.get("Status") or "").strip(),
            "last_run": (t.get("Last Run Time") or "").strip(),
            "next_run": (t.get("Next Run Time") or "").strip(),
            "last_result_code": code,
            "last_result": RESULT_MEANING.get(code, f"code {code}"),
            "artifact": artifact or None,
            "artifact_age_min": None if age is None else round(age, 1),
            "contract_max_age_min": max_age or None,
            "purpose": purpose or None,
        })

    # A CONTRACTED ORGAN WITH NO SCHEDULED TASK IS THE LOUDEST ROW ON THE BOARD. It means the desk
    # believes something runs that the scheduler has never heard of -- a task deleted by hand, a
    # rename, or a box that was migrated and left an organ behind. That is exactly the "reverted"
    # class the principal keeps reporting, and it is invisible to any check that starts from the
    # scheduler.
    for organ, (artifact, max_age, purpose) in contracts.items():
        if organ in seen:
            continue
        owner = owner_task(organ)
        age = _age_min(ROOT / artifact)
        stale = age is None or (max_age and age > max_age)
        if not sched.get("read") and not existence_only:
            # NO SCHEDULER READING, SO NO SCHEDULING VERDICT. The artifact clock is still a fact
            # and is still judged: an organ whose artifact is fresh is working whatever the
            # scheduler said, and one whose artifact is stale is STALE on its own evidence.
            if age is None:
                verdict, why = "NO_ARTIFACT", f"{artifact} does not exist"
            elif stale:
                verdict, why = "STALE", f"{age:.0f} min old against a {max_age} min contract"
            else:
                verdict, why = "UNMEASURED", ("artifact current; scheduler unreadable -- "
                                              + str(sched.get("why") or ""))
        elif owner != organ and owner in seen and existence_only:
            verdict, why = (("NO_ARTIFACT", f"{artifact} does not exist") if age is None else
                            ("STALE", f"{age:.0f} min old against a {max_age} min contract")
                            if stale else
                            ("UNMEASURED", f"owned by {owner}, which is scheduled; its run "
                                           "result is UNMEASURED -- "
                                           + str(sched.get("why") or "")))
        elif owner != organ and owner in seen:
            # An ASPECT of a task that is scheduled: judged on its own artifact only.
            if age is None:
                verdict, why = "NO_ARTIFACT", (f"{artifact} does not exist; owned by {owner}, "
                                               "which is scheduled")
            elif stale:
                verdict, why = "STALE", (f"{age:.0f} min old against a {max_age} min contract; "
                                         f"owned by {owner}")
            else:
                verdict, why = "OK", f"owned by {owner}, which is scheduled"
        else:
            verdict, why = "NOT_SCHEDULED", (
                f"this organ has a contract but no scheduled task named {owner} on this box -- "
                "it cannot run at all")
        rows.append({
            "name": organ,
            "task": owner,
            "verdict": verdict,
            "why": why,
            "state": "ABSENT" if verdict == "NOT_SCHEDULED" else "",
            "last_run": "", "next_run": "",
            "last_result_code": None,
            "last_result": "never run on this box" if verdict == "NOT_SCHEDULED" else "",
            "artifact": artifact,
            "artifact_age_min": None if age is None else round(age, 1),
            "contract_max_age_min": max_age, "purpose": purpose,
        })

    order = {"NOT_SCHEDULED": 0, "FAILING": 1, "NO_ARTIFACT": 2, "STALE": 3,
             "UNMEASURED": 4, "DISABLED": 5, "UNCONTRACTED": 6, "OK": 7}
    rows.sort(key=lambda r: (order.get(str(r["verdict"]), 9), str(r["name"])))
    counts: dict[str, int] = {}
    for r in rows:
        counts[str(r["verdict"])] = counts.get(str(r["verdict"]), 0) + 1

    bad = [r for r in rows if r["verdict"] in ("NOT_SCHEDULED", "FAILING", "NO_ARTIFACT", "STALE")]
    return {
        "at": now.isoformat(timespec="seconds"),
        "host": __import__("socket").gethostname(),
        "n_processes": len(rows),
        # WHETHER THE SCHEDULER WAS READ AT ALL. `read: false` means no row below carries a
        # scheduling verdict, and a reader must say UNMEASURED rather than count absences.
        "scheduler": sched,
        "counts": counts,
        # The headline is the WORST row, never the proportion that are fine. "38 of 41 healthy"
        # is how a dead gateway hides behind a green majority.
        "status": ("ATTENTION" if bad else "UNMEASURED" if not sched.get("read") else "OK"),
        "n_needing_attention": len(bad),
        "processes": rows,
    }


def main(argv: list[str] | None = None) -> int:
    doc = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    print(f"process health: {doc['n_processes']} process(es), status {doc['status']}, "
          f"{doc['n_needing_attention']} needing attention")
    for r in doc["processes"]:
        if r["verdict"] != "OK":
            age = "" if r["artifact_age_min"] is None else f"{r['artifact_age_min']:.0f}m"
            print(f"  {r['verdict']:<14} {r['name']:<32} {age:>7}  {r['why'][:70]}")
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
