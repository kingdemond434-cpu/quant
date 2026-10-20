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


#: One budget for each scheduler read. The verbose query has been measured hanging past two
#: minutes on the trading box under load, and the PowerShell cmdlets this used to call first
#: (Get-ScheduledTask/Get-ScheduledTaskInfo, CIM underneath -- CIM is what hangs on that box)
#: timed out at this same 45 s on every pass of 2026-10-20, which marked all 73 tasks
#: SCHEDULER_UNMEASURED. The brief CSV query returns there in about 6 s.
SCHTASKS_TIMEOUT_S = 45

#: The columns the verdict reads. The brief query (`/fo csv`) carries the first three; the
#: verbose one (`/fo csv /v`) adds the run history. A row with no "Last Result" column is
#: reported with that fact UNMEASURED, never as a clean 0.
BRIEF_FIELDS = ("TaskName", "Next Run Time", "Status")
VERBOSE_FIELDS = ("Last Run Time", "Last Result", "Scheduled Task State")

#: Task states, lower-cased, in the locales a Windows box is plausibly installed in. schtasks
#: prints the state in the OS language, so a bare `== "disabled"` read a German "Deaktiviert"
#: as healthy (audit 2026-10-14). A state in none of these sets is UNMEASURED, never assumed
#: enabled: a monitor that cannot read whether a task can run does not get to say it can.
STATE_DISABLED = frozenset({
    "disabled", "deaktiviert", "désactivé", "desactivado", "deshabilitado", "disabilitato",
    "desabilitado", "desativado", "uitgeschakeld", "wyłączone", "отключено",
})
STATE_RUNNING = frozenset({
    "running", "wird ausgeführt", "en cours d'exécution", "en ejecución", "in esecuzione",
    "em execução", "wordt uitgevoerd", "uruchomione", "выполняется",
})
STATE_LIVE = STATE_RUNNING | frozenset({
    # "Could not start" is deliberately absent: it is a start that failed, so it reads
    # UNMEASURED (no state this file can vouch for), never live (audit v2, 2026-10-14).
    "ready", "enabled", "queued",
    "bereit", "aktiviert", "in warteschlange",
    "prêt", "activé", "en file d'attente",
    "listo", "preparado", "habilitado", "activado", "en cola",
    "pronto", "abilitato", "in coda", "ativado",
    "gereed", "ingeschakeld", "gotowe", "włączone", "готово", "включено",
})


class SchtasksUnreadable(ValueError):
    """schtasks answered, but not in a shape this parser can read as an inventory."""


def _run_schtasks(args: list[str]) -> tuple[int, str, str]:
    """One `schtasks` call, bounded. Raises OSError/SubprocessError for the caller to name."""
    proc = subprocess.run(["schtasks", *args], capture_output=True, text=True,
                          errors="replace", timeout=SCHTASKS_TIMEOUT_S)
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def parse_schtasks_csv(text: str) -> list[dict[str, str]]:
    """The non-Microsoft tasks in a `schtasks /query /fo csv [/v]` dump, one row per task.

    Parsed with the csv module: task names, paths and "Task To Run" commands carry commas and
    quotes. schtasks repeats the header row once per task folder (skipped), may print a
    "Folder: ..." line in some builds (skipped: a real task name always starts with a backslash)
    and, verbose, prints one row PER TRIGGER (the first row of each task is kept).

    Non-empty text with no `TaskName` header raises SchtasksUnreadable rather than returning
    []. Both shapes the audit of 2026-10-14 probed land here -- a localised header
    ("Aufgabenname") and the access-denied "INFO: There are no scheduled tasks presently
    available at your access level." at exit 0 -- and an empty list would read as an empty
    scheduler, which turns every contracted organ into the false claim NOT_SCHEDULED.
    """
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    reader = csv.reader(io.StringIO(text.lstrip("\ufeff")))
    header: list[str] | None = None
    col = 0
    for rec in reader:
        if not rec or not any(c.strip() for c in rec):
            continue
        cells = [c.strip() for c in rec]
        if "TaskName" in cells:  # the verbose dump puts HostName first, so find the column
            header, col = cells, cells.index("TaskName")
            continue
        if header is None:
            continue
        name = cells[col] if col < len(cells) else ""
        if not name.startswith("\\"):
            continue
        if name.startswith("\\Microsoft") or name in seen:
            continue
        seen.add(name)
        rows.append({k: (rec[i].strip() if i < len(rec) else "") for i, k in enumerate(header)})
    if header is None and text.strip():
        raise SchtasksUnreadable("no TaskName header in: " + " ".join(text.split())[:160])
    return rows


def _missing(rows: list[dict[str, str]], fields: tuple[str, ...]) -> list[str]:
    """The required columns the dump's header did not carry (every row shares one header)."""
    return [f for f in fields if rows and f not in rows[0]]


def _tasks() -> tuple[list[dict[str, str]], str]:
    """Read the scheduler, distinguishing a failed inventory from an empty one.

    Brief first: it is the INVENTORY (which tasks exist, their state, next run) and it is the
    read that returns under load. Then the verbose query, on its own bound, adds each task's last
    run and last result. If only the brief read lands, the inventory stands -- so NOT_SCHEDULED,
    DISABLED, NO_ARTIFACT and STALE are all still judged -- and every row says its result code
    was not read. If neither lands the status is UNMEASURED, and an unreadable inventory never
    turns a contracted organ into the false claim NOT_SCHEDULED.
    """
    errors: list[str] = []
    brief: list[dict[str, str]] | None = None
    try:
        rc, out, err = _run_schtasks(["/query", "/fo", "csv"])
        if rc == 0 and out.strip():
            parsed = parse_schtasks_csv(out)
            # A box with no task of its own is not this desk's box: zero non-Microsoft rows is
            # a read that saw nothing (wrong account, filtered view), never "nothing scheduled".
            if not parsed:
                errors.append("schtasks /fo csv listed no non-Microsoft task")
            elif lost := _missing(parsed, BRIEF_FIELDS):
                errors.append(f"schtasks /fo csv header lacks {', '.join(lost)}")
            else:
                brief = parsed
        else:
            errors.append(f"schtasks /fo csv exit {rc}: {err.strip()[:160]}")
    except SchtasksUnreadable as exc:
        errors.append(f"schtasks /fo csv unreadable: {exc}")
    except (OSError, subprocess.SubprocessError) as exc:
        errors.append(f"schtasks /fo csv {type(exc).__name__}: {exc}")
    if brief is None:
        return [], "UNMEASURED: " + "; ".join(errors)

    verbose: dict[str, dict[str, str]] = {}
    try:
        rc, out, err = _run_schtasks(["/query", "/fo", "csv", "/v"])
        if rc == 0 and out.strip():
            parsed = parse_schtasks_csv(out)
            # Without "Last Result" the code would normalise to 0 and read OK, so a verbose dump
            # missing any column the verdict reads is treated as not having answered at all.
            if not parsed:
                errors.append("schtasks /v listed no non-Microsoft task")
            elif lost := _missing(parsed, VERBOSE_FIELDS):
                errors.append(f"schtasks /v header lacks {', '.join(lost)}")
            else:
                verbose = {r["TaskName"]: r for r in parsed}
        else:
            errors.append(f"schtasks /v exit {rc}: {err.strip()[:160]}")
    except SchtasksUnreadable as exc:
        errors.append(f"schtasks /v unreadable: {exc}")
    except (OSError, subprocess.SubprocessError) as exc:
        errors.append(f"schtasks /v {type(exc).__name__}: {exc}")

    rows: list[dict[str, str]] = []
    for r in brief:
        v = verbose.get(r["TaskName"])
        if v is not None:
            rows.append({**v, **{k: r[k] for k in BRIEF_FIELDS if r.get(k)}})
        else:
            rows.append({**r, "ResultUnmeasured": "the verbose query did not return this task"})
    if verbose:
        return rows, "OK schtasks"
    return rows, ("OK schtasks (brief: last run and last result UNMEASURED -- "
                  + "; ".join(errors) + ")")


def _normalise_code(raw: Any) -> int | None:
    """One task result, as ONE number, whichever tool printed it.

    THE BUG THIS ENDS, found on this file's own first day (2026-09-12). `schtasks` prints result
    codes SIGNED and the PowerShell cmdlets print them UNSIGNED, so the same outcome appears as
    -2147020576 and 2147946720 -- two entries in any lookup table, and a verdict that depends on
    which tool happened to read the row. The first run of this module reported MT5-Hourly,
    MT5-LocalDashboard and MT5-MoatRecorder-Watchdog as FAILING when all three were simply
    RUNNING: 267009 ("currently running") was recognised, and its signed sibling was not.

    A monitor that cries wolf is worse than no monitor, because the operator learns to scroll
    past it -- which is exactly the attention this board exists to spend well.

    An absent, blank or non-numeric result is None, not 0: the audit of 2026-10-14 probed a
    verbose header without "Last Result" and got a clean OK for a run nobody had read. A `0x`
    code is parsed as hex, as `desks/mt5/scripts/check_desk_health.py:_result_code` does, so the
    two readers of one scheduler never disagree about the same row.
    """
    text = str(raw if raw is not None else "").strip()
    try:
        code = int(text, 16) if text.lower().startswith("0x") else int(text)
    except ValueError:
        return None
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
    tasks, scheduler_status = _tasks()

    for t in tasks:
        name = (t.get("TaskName") or "").strip().lstrip("\\")
        seen.add(name)
        # A brief-only row carries no result column. Reading its absence as 0 would publish
        # "OK" for a task whose last run was never read (L1.28a), so the code stays None.
        result_unmeasured = str(t.get("ResultUnmeasured") or "")
        code: int | None = None if result_unmeasured else _normalise_code(t.get("Last Result"))
        # The verbose query ANSWERED for this row but its code is blank, "N/A" or garbage: that
        # is an unread result on a row that claimed to have one, so the row is UNMEASURED below,
        # unlike a brief-only row whose history was simply not asked for this pass.
        code_unreadable = code is None and not result_unmeasured
        if code_unreadable:
            result_unmeasured = f"last result {str(t.get('Last Result') or 'absent')!r} not a code"
        artifact, max_age, purpose = contracts.get(name, ("", 0, ""))
        age = _age_min(ROOT / artifact) if artifact else None

        # THE VERDICT IS THE WORST OF THE THREE FACTS, never an average of them. A task that is
        # Disabled is not "half healthy" because its artifact happens to be fresh; a task that
        # returned 0 is not healthy if nothing appeared. Averaging is how a board reassures.
        # Both state columns are read: verbose "Scheduled Task State" says Enabled/Disabled and
        # brief "Status" says Ready/Running/Disabled, in the OS language either way.
        _states = {str(t.get(k) or "").strip().lower() for k in ("Scheduled Task State", "Status")}
        _states.discard("")
        _running = bool(_states & STATE_RUNNING)
        if t.get("TaskInfoError"):
            verdict, why = "SCHEDULER_UNMEASURED", str(t["TaskInfoError"])
        elif _states & STATE_DISABLED:
            verdict, why = "DISABLED", "the scheduler will never start this"
        elif not _states or not _states <= STATE_LIVE:
            verdict, why = "SCHEDULER_UNMEASURED", (
                f"task state {sorted(_states) or 'blank'} not recognised: whether the scheduler "
                "will start this is UNMEASURED")
        elif artifact and age is None:
            verdict, why = "NO_ARTIFACT", f"{artifact} does not exist"
        elif artifact and max_age and age is not None and age > max_age:
            verdict, why = "STALE", f"{age:.0f} min old against a {max_age} min contract"
        elif code_unreadable:
            verdict, why = "SCHEDULER_UNMEASURED", (result_unmeasured + ": whether the last run "
                                                    "succeeded is UNMEASURED")
        elif code is not None and code not in (0, 267009, 267011) and not _running:
            verdict, why = "FAILING", RESULT_MEANING.get(code, f"exit code {code}")
        elif not artifact:
            verdict, why = "UNCONTRACTED", ("no artifact contract: this process could stop and "
                                            "nothing would notice")
        else:
            verdict, why = "OK", ("" if code is not None else
                                  "artifact fresh; last result not read this pass")

        rows.append({
            "name": name,
            "verdict": verdict,
            "why": why,
            "state": (t.get("Scheduled Task State") or t.get("Status") or "").strip(),
            "last_run": (t.get("Last Run Time") or "").strip(),
            "next_run": (t.get("Next Run Time") or "").strip(),
            "last_result_code": code,
            "last_result": ("UNMEASURED: " + result_unmeasured if code is None
                            else RESULT_MEANING.get(code, f"code {code}")),
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
        age = _age_min(ROOT / artifact)
        inventory_ok = scheduler_status.startswith("OK ")
        # Parenthesised contracts describe an artifact of an existing scheduled task, not a
        # second Windows task. Treating the name as a task manufactured 31 NOT_SCHEDULED alarms
        # on this box and buried real gateway/allocator failures beneath them.
        parent = organ.split(" (", 1)[0] if " (" in organ else ""
        is_component = bool(parent and parent in seen)
        if not inventory_ok:
            verdict, why = "SCHEDULER_UNMEASURED", scheduler_status
        elif is_component and age is None:
            verdict, why = "NO_ARTIFACT", f"{artifact} does not exist"
        elif is_component and age is not None and max_age and age > max_age:
            verdict, why = "STALE", f"{age:.0f} min old against a {max_age} min contract"
        elif is_component:
            verdict, why = "OK", f"artifact of scheduled task {parent}"
        else:
            verdict, why = ("NOT_SCHEDULED", "this organ has a contract but no scheduled task "
                            "on this box -- it cannot run at all")
        rows.append({
            "name": organ,
            "verdict": verdict,
            "why": why,
            "state": ("COMPONENT" if is_component else
                      ("ABSENT" if inventory_ok else "UNMEASURED")),
            "last_run": "", "next_run": "",
            "last_result_code": None, "last_result": "never run on this box",
            "artifact": artifact,
            "artifact_age_min": None if age is None else round(age, 1),
            "contract_max_age_min": max_age, "purpose": purpose,
        })

    order = {"NOT_SCHEDULED": 0, "SCHEDULER_UNMEASURED": 0, "FAILING": 1,
             "NO_ARTIFACT": 2, "STALE": 3,
             "DISABLED": 4, "UNCONTRACTED": 5, "OK": 6}
    rows.sort(key=lambda r: (order.get(str(r["verdict"]), 9), str(r["name"])))
    counts: dict[str, int] = {}
    for r in rows:
        counts[str(r["verdict"])] = counts.get(str(r["verdict"]), 0) + 1

    bad = [r for r in rows if r["verdict"] in ("NOT_SCHEDULED", "SCHEDULER_UNMEASURED",
                                             "FAILING", "NO_ARTIFACT", "STALE")]
    return {
        "at": now.isoformat(timespec="seconds"),
        "host": __import__("socket").gethostname(),
        "scheduler_status": scheduler_status,
        "n_processes": len(rows),
        "counts": counts,
        # The headline is the WORST row, never the proportion that are fine. "38 of 41 healthy"
        # is how a dead gateway hides behind a green majority. An unread scheduler, or a board
        # with no rows at all (UNMEASURED inventory and `_contracts()` swallowing a failed
        # import), is UNMEASURED: zero rows of trouble out of zero rows read is not "OK".
        "status": ("UNMEASURED" if not rows or not scheduler_status.startswith("OK ")
                   else "OK" if not bad else "ATTENTION"),
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
