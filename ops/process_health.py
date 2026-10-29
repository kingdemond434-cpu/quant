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

import contextlib
import csv
import io
import json
import os
import platform
import subprocess
import sys
import time
from datetime import UTC, date, datetime
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
#: The verbose `/fo csv /v` read gets its own bound. Measured on the trading box 2026-10-20
#: 23:4xZ (73 desk tasks, 513 rows): 28.3 s, against 6.2 s for the brief query -- so the shared
#: 45 s left it under 1.6x headroom on a loaded box. About 3x the measurement, rounded up.
SCHTASKS_VERBOSE_TIMEOUT_S = 90

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


#: THE OFF-HOT-PATH RETRY'S BUDGETS (v5f). Measured 2026-10-21 04:01:35Z: every one of the 73
#: tasks read SCHEDULER_UNMEASURED while stall_watch showed 1,654 MB free of 8,186 MB and a
#: 37,950 MB commit -- the box was paging, and a read that returns in 6 s idle did not return in
#: 45. The hourly pass keeps its 45 s / 90 s bounds (it must not overrun its own slot); a timeout
#: hands the read to ONE detached, below-normal-priority child with these longer bounds, which
#: replaces the UNMEASURED report if it lands. 4x and a bit over 3x the hot-path bounds.
RETRY_TIMEOUT_S = 180
RETRY_VERBOSE_TIMEOUT_S = 300
#: A retry lock older than this is a crashed retry, never a live one (180 + 300 s plus build).
RETRY_LOCK_STALE_S = 15 * 60
RETRY_LOCK = ROOT / "desks" / "mt5" / "logs" / "process_health_retry.lock"

#: Set only by the retry child: the bounds `_run_schtasks` uses instead of the hot-path ones.
_BOUNDS_OVERRIDE: tuple[int, int] | None = None
#: Every read that hit its bound this pass, with the memory picture at that instant. Cleared at
#: the top of each `build()`; `_tasks` appends through `_timeout_reason`.
TIMEOUTS: list[dict[str, Any]] = []


def _bound(args: list[str]) -> int:
    brief, verbose = _BOUNDS_OVERRIDE or (SCHTASKS_TIMEOUT_S, SCHTASKS_VERBOSE_TIMEOUT_S)
    return verbose if "/v" in args else brief


def _host() -> str:
    try:
        import socket
        return socket.gethostname() or platform.node() or "UNMEASURED"
    except Exception:
        return platform.node() or "UNMEASURED"


def memory_snapshot() -> dict[str, Any]:
    """Free and total physical memory and the commit charge, from psutil ONLY (never CIM: CIM is
    what hangs on the trading box), stamped with the HOST it was read on.

    EVERY FIGURE CARRIES ITS HOSTNAME AND THE MACHINE'S TOTAL (coordinator, 2026-10-21): the
    "8 GB" reading this desk once argued from was the build box, not the 96 GB trading box, and a
    free-memory figure with no host and no total cannot be told apart from the other machine's.

    The commit charge is exact on Windows (GlobalMemoryStatusEx total minus available page file,
    read through psutil's own extension); elsewhere it is physical used plus swap used, labelled
    as an approximation. Any figure psutil cannot give is None with the reason, never a zero.
    """
    snap: dict[str, Any] = {"host": _host(), "source": "psutil",
                            "at": datetime.now(tz=UTC).isoformat(timespec="seconds")}
    try:
        import psutil  # type: ignore[import-untyped,unused-ignore]
    except Exception as exc:
        snap.update(total_phys_mb=None, free_phys_mb=None, commit_charge_mb=None,
                    why=f"psutil unavailable: {type(exc).__name__}")
        return snap
    mb = 1024 * 1024
    try:
        vm = psutil.virtual_memory()
        snap["total_phys_mb"] = round(vm.total / mb)
        snap["free_phys_mb"] = round(vm.available / mb)
    except Exception as exc:
        snap.update(total_phys_mb=None, free_phys_mb=None,
                    why=f"virtual_memory: {type(exc).__name__}")
        vm = None
    commit: int | None = None
    limit: int | None = None
    how = "UNMEASURED"
    try:
        cext = getattr(getattr(psutil, "_psplatform", None), "cext", None)
        if sys.platform == "win32" and cext is not None and hasattr(cext, "virtual_mem"):
            raw = cext.virtual_mem()   # (total phys, avail phys, total pagefile, avail pagefile)
            limit = round(raw[2] / mb)
            commit = round((raw[2] - raw[3]) / mb)
            how = "exact: commit limit minus available (GlobalMemoryStatusEx via psutil)"
        elif vm is not None:
            sw = psutil.swap_memory()
            commit = round((vm.total - vm.available + sw.used) / mb)
            limit = round((vm.total + sw.total) / mb)
            how = "approx: physical used + swap used"
    except Exception as exc:
        how = f"UNMEASURED: {type(exc).__name__}"
    snap["commit_charge_mb"] = commit
    snap["commit_limit_mb"] = limit
    snap["commit_source"] = how
    return snap


def _timeout_reason(label: str, exc: subprocess.TimeoutExpired) -> str:
    """Record WHICH read timed out, the bound it hit and the memory then; return the sentence."""
    bound = exc.timeout
    mem = memory_snapshot()
    TIMEOUTS.append({"read": label, "bound_s": bound, "memory": mem})

    def _f(v: Any) -> str:
        return "UNMEASURED" if v is None else f"{v:,} MB"

    return (f"{label} TimeoutExpired: timed out at its {bound:g} s bound on {mem['host']} "
            f"({_f(mem.get('free_phys_mb'))} free of {_f(mem.get('total_phys_mb'))} physical, "
            f"commit {_f(mem.get('commit_charge_mb'))})")


def _run_schtasks(args: list[str]) -> tuple[int, str, str]:
    """One `schtasks` call, bounded. Raises OSError/SubprocessError for the caller to name."""
    kw: dict[str, Any] = {}
    if _BOUNDS_OVERRIDE is not None and sys.platform == "win32":
        # The retry's own schtasks child runs below normal too, never at the default class.
        kw["creationflags"] = getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0)
    proc = subprocess.run(["schtasks", *args], capture_output=True, text=True,
                          errors="replace", timeout=_bound(args), **kw)
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


#: Tasks that are DISABLED ON PURPOSE. A DISABLED task raises the headline to ATTENTION on every
#: read (v5b, coordinator ruling 2026-10-21) except one listed here: its row still reads DISABLED
#: and carries `expected_disabled` (this entry), but it is not a fault. Every entry names who
#: decided it and why, and the date; tests/ops/test_process_health_schtasks.py fails without
#: them. Remove the entry when the task is meant to run again.
EXPECTED_DISABLED: dict[str, dict[str, str]] = {
    "MT5-AdoptRelease": {
        "reason": "disabled on purpose by the principal: the box does not self-adopt until the "
                  "release path is resumed",
        "date": "2026-10-21",
    },
}


def expected_disabled(name: str) -> tuple[dict[str, str] | None, str]:
    """(entry, error) for `name` in EXPECTED_DISABLED. NEVER RAISES (v5c). An entry is honoured
    only when it is a mapping with a non-empty str `reason` and an ISO `date`; anything else is
    (None, why) -- so a malformed entry leaves the task an ordinary DISABLED fault (ATTENTION),
    never a silent pass and never a crash of the board."""
    try:
        if not isinstance(EXPECTED_DISABLED, dict):
            return None, f"EXPECTED_DISABLED is a {type(EXPECTED_DISABLED).__name__}, not a mapping"
        entry = EXPECTED_DISABLED.get(name)
        if entry is None:
            return None, ""
        if not isinstance(entry, dict):
            return None, f"EXPECTED_DISABLED[{name!r}] is a {type(entry).__name__}, not a mapping"
        reason, when = entry.get("reason"), entry.get("date")
        if not isinstance(reason, str) or not reason.strip():
            return None, f"EXPECTED_DISABLED[{name!r}] has no reason"
        if not isinstance(when, str):
            return None, f"EXPECTED_DISABLED[{name!r}] has no date"
        date.fromisoformat(when.strip())
        return {"reason": reason.strip(), "date": when.strip()}, ""
    except Exception as exc:   # a bad date, an unhashable name: malformed, never fatal
        return None, f"EXPECTED_DISABLED[{name!r}] malformed ({type(exc).__name__})"


#: Verdicts a brief-only read (no run history) establishes for certain. Any of them makes a
#: brief-only headline ATTENTION; FAILING cannot arise there (no result code was read) but is
#: listed so a future change that reads one cannot hide it.
BRIEF_DEFINITE_FAULTS = frozenset({"NOT_SCHEDULED", "DISABLED", "STALE", "NO_ARTIFACT",
                                   "FAILING"})


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
    except subprocess.TimeoutExpired as exc:
        errors.append(_timeout_reason("schtasks /query /fo csv", exc))
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
    except subprocess.TimeoutExpired as exc:
        errors.append(_timeout_reason("schtasks /query /fo csv /v", exc))
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


#: Account-key states that are a definite fault: every stamp fails closed until a human restores
#: the key from backup (libs/ops/provenance.RESTORE_STEP). `absent` is not one: a writer creates it.
KEY_FAULT_STATES = frozenset({"short", "unreadable"})


def account_key_file() -> dict[str, Any]:
    """The account key file's STATE (present / short / unreadable / absent) and SIZE, never its
    contents, from libs/ops/provenance.key_state. UNMEASURED if that cannot be read."""
    try:
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from libs.ops import provenance
        state = dict(provenance.key_state())
        if state.get("state") in KEY_FAULT_STATES:
            state["restore"] = provenance.RESTORE_STEP
        return state
    except Exception as exc:
        return {"state": "UNMEASURED", "why": type(exc).__name__}


#: Backup states that are a definite fault. `not_applicable` (off the box, or no live key to
#: compare -- which `account_key_file` already reports) is not.
BACKUP_FAULT_STATES = frozenset({"missing", "mismatch", "unreadable"})


def account_key_backup() -> dict[str, Any]:
    """libs/ops/provenance.key_backup_state: present / size / matches, never contents or hash."""
    try:
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from libs.ops import provenance
        state = dict(provenance.key_backup_state())
        if state.get("state") in BACKUP_FAULT_STATES:
            state["restore"] = ("copy data/secrets/account_key.hmac to the backup (never the "
                                "other way unless the live key is the one lost)")
        return state
    except Exception as exc:
        return {"state": "UNMEASURED", "why": type(exc).__name__}


#: THE DEPENDENCY-LIVENESS VERDICT (Rule 23, 2026-10-29). Written by MT5-AxisIngest
#: (desks/mt5/research/axis_ingest_all.py) on every pass: RED when any external source or series
#: has delivered no data for more than two consecutive passes. A task's exit code cannot carry
#: this -- the ingest exits 0 when ANY axis lands, which is why FRED's empty returns read "OK"
#: here from 2026-09-12 to 2026-10-29 -- so the board reads the streak itself.
DEPENDENCY_LIVENESS = ROOT / "desks" / "mt5" / "reports" / "DEPENDENCY_LIVENESS.json"


def dependency_liveness(path: Path | None = None) -> dict[str, Any]:
    """The streak verdict, summarised: RED / GREEN / UNMEASURED and which dependencies are RED.
    Absent or unreadable is UNMEASURED (a host that never ran the ingest), never GREEN."""
    p = path or DEPENDENCY_LIVENESS
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"verdict": "UNMEASURED", "why": f"{p.name} absent or unreadable on this host"}
    if not isinstance(doc, dict) or doc.get("verdict") not in ("RED", "GREEN", "UNMEASURED"):
        return {"verdict": "UNMEASURED", "why": f"{p.name} carries no verdict"}
    deps = doc.get("dependencies") or {}
    return {
        "verdict": doc["verdict"],
        "at": doc.get("at"),
        "red_after_runs": doc.get("red_after_runs"),
        "red": [{"dependency": k, "empty_streak": (deps.get(k) or {}).get("empty_streak"),
                 "since": (deps.get(k) or {}).get("first_empty_at"),
                 "reason": (deps.get(k) or {}).get("last_reason")}
                for k in (doc.get("red") or [])],
        # EVERY DEPENDENCY NOT DELIVERING, RED OR NOT YET, WITH ITS CAUSE. DEPENDENCY_LIVENESS.json
        # itself stays on the box (`**/reports/*` is ignored); this board is published, so the
        # per-series reason (TIMEOUT, RESET, HTTP_4xx, EMPTY, NEEDS_KEY) reaches every reader.
        "not_delivering": {k: {"empty_streak": d.get("empty_streak"),
                               "reason": str(d.get("last_reason") or "")[:240]}
                           for k, d in sorted(deps.items())
                           if isinstance(d, dict) and d.get("verdict") in ("RED", "AMBER")},
        "sources": doc.get("sources") or {},
        "artifact": "desks/mt5/reports/DEPENDENCY_LIVENESS.json",
    }


def build() -> dict[str, Any]:
    contracts = _contracts()
    now = datetime.now(tz=UTC)
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    TIMEOUTS.clear()
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
            _exp, _exp_err = expected_disabled(name)
            if _exp is not None:
                why = f"EXPECTED (since {_exp['date']}): {_exp['reason']}"
            elif _exp_err:
                why += f"; {_exp_err}, so it is not excused"
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
            "expected_disabled": (expected_disabled(name)[0] if verdict == "DISABLED"
                                  else None),
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

    # DISABLED IS A FAULT (v5b ruling) unless the task is EXPECTED_DISABLED.
    bad = [r for r in rows if r["verdict"] in ("NOT_SCHEDULED", "SCHEDULER_UNMEASURED",
                                             "FAILING", "NO_ARTIFACT", "STALE")
           or (r["verdict"] == "DISABLED" and not r.get("expected_disabled"))]
    run_history_read = scheduler_status == "OK schtasks"
    brief_faults = [r for r in rows if r["verdict"] in BRIEF_DEFINITE_FAULTS
                    and not r.get("expected_disabled")]
    key = account_key_file()
    backup = account_key_backup()
    key_fault = key.get("state") in KEY_FAULT_STATES
    backup_fault = backup.get("state") in BACKUP_FAULT_STATES
    deps = dependency_liveness()
    dep_fault = deps.get("verdict") == "RED"
    status = ("UNMEASURED" if not rows or not scheduler_status.startswith("OK ")
              else ("ATTENTION" if brief_faults else "UNMEASURED")
              if not run_history_read
              else "OK" if not bad else "ATTENTION")
    if key_fault or backup_fault or dep_fault:
        status = "ATTENTION"   # a definite fault: the worst finding wins over UNMEASURED too
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
        # A BRIEF-ONLY READ (v5b, coordinator ruling 2026-10-21): the inventory landed but the
        # verbose read (last run, last result) failed or timed out. A DEFINITE fault the brief
        # read can still see (NOT_SCHEDULED, DISABLED, STALE, NO_ARTIFACT) headlines ATTENTION --
        # the worst finding wins. With no such fault the headline is UNMEASURED, never OK: an
        # all-OK board there would be OK about results nobody read.
        # A SHORT OR UNREADABLE ACCOUNT KEY (v5d) is ATTENTION too: every ledger stamp then
        # fails closed (account_key None), and fail-closed must never be silent.
        "status": status,
        "run_history": "MEASURED" if run_history_read else "UNMEASURED",
        "n_needing_attention": len(bad) + int(key_fault) + int(backup_fault) + int(dep_fault),
        "account_key_file": key,
        # THE BACKUP (v5e): present, size, and whether it matches the live key -- a hash compare
        # done in-process; no hash is ever printed or written. Missing or mismatched: ATTENTION.
        "account_key_backup": backup,
        # A PUBLISHER THAT RETURNS NOTHING, PASS AFTER PASS, WHILE ITS TASK EXITS 0 (Rule 23).
        "dependency_liveness": deps,
        # WHICH READ TIMED OUT, ITS BOUND, AND THE MEMORY THEN (v5f), each figure stamped with
        # the host it was read on and that host's total. Empty when every read answered.
        "scheduler_timeouts": list(TIMEOUTS),
        "scheduler_retry": {"state": "NOT_NEEDED"} if not TIMEOUTS else {"state": "PENDING"},
        "processes": rows,
    }


def _rank(doc: dict[str, Any] | None) -> int:
    """How much of the scheduler a report read: 0 nothing, 1 the inventory, 2 the run history."""
    if not isinstance(doc, dict):
        return -1
    status = str(doc.get("scheduler_status") or "")
    if status == "OK schtasks" or doc.get("run_history") == "MEASURED":
        return 2
    return 1 if status.startswith("OK ") else 0


def _read_report() -> dict[str, Any] | None:
    try:
        doc = json.loads(OUT.read_text(encoding="utf-8"))
        return doc if isinstance(doc, dict) else None
    except (OSError, ValueError):
        return None


def _write_report(doc: dict[str, Any]) -> None:
    """Temp file then os.replace, retried: a reader holding the file open on Windows makes the
    replace raise PermissionError, and the retry child must never leave a half-written report."""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_name(f".{OUT.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    for attempt in range(10):
        try:
            os.replace(tmp, OUT)
            return
        except PermissionError:
            if attempt == 9:
                tmp.unlink(missing_ok=True)
                raise
            time.sleep(0.2)


def _retry_lock() -> Path:
    return ROOT / "desks" / "mt5" / "logs" / "process_health_retry.lock"


def _take_retry_lock() -> bool:
    """ONE retry at a time. A lock older than RETRY_LOCK_STALE_S is a crashed retry and is
    removed -- the FILE, never the process: nothing here kills or signals anything."""
    lock = _retry_lock()
    lock.parent.mkdir(parents=True, exist_ok=True)
    for _ in range(2):
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                if time.time() - lock.stat().st_mtime > RETRY_LOCK_STALE_S:
                    lock.unlink(missing_ok=True)
                    continue
            except OSError:
                pass
            return False
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
                                 "pid": os.getpid()}))
        return True
    return False


def _release_retry_lock() -> None:
    with contextlib.suppress(OSError):
        _retry_lock().unlink(missing_ok=True)


def _spawn_retry(for_at: str) -> subprocess.Popen[bytes]:
    """Start the retry DETACHED and BELOW NORMAL priority, so it outlives this pass and never
    competes with mining. The child lowers itself again on start (`_lower_priority`), which is
    what holds on POSIX and if a job object refuses the creation flag."""
    cmd = [sys.executable, str(Path(__file__).resolve()), "--retry-scheduler", "--for", for_at]
    common: dict[str, Any] = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL,
                              "stderr": subprocess.DEVNULL, "close_fds": True, "cwd": str(ROOT)}
    if sys.platform == "win32":
        base = (getattr(subprocess, "DETACHED_PROCESS", 0x8)
                | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x200)
                | getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0x4000))
        try:   # leave the scheduler's job object if it allows it, so the pass ending is no kill
            return subprocess.Popen(cmd, creationflags=base | 0x01000000, **common)
        except OSError:
            return subprocess.Popen(cmd, creationflags=base, **common)
    return subprocess.Popen(cmd, start_new_session=True, **common)


def _lower_priority() -> str:
    """Lower THIS process's CPU and I/O priority. Touches no other process, ever."""
    done: list[str] = []
    try:
        import psutil  # type: ignore[import-untyped,unused-ignore]
        me = psutil.Process()
        if sys.platform == "win32":
            me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
            done.append("cpu below_normal")
            try:
                me.ionice(psutil.IOPRIO_LOW)
                done.append("io low")
            except Exception:
                pass
        else:
            me.nice(max(me.nice(), 15))
            done.append(f"cpu nice {me.nice()}")
            try:
                me.ionice(psutil.IOPRIO_CLASS_IDLE)
                done.append("io idle")
            except Exception:
                pass
    except Exception as exc:
        try:
            os.nice(15)
            done.append("cpu nice +15")
        except Exception:
            done.append(f"UNMEASURED: {type(exc).__name__}")
    return ", ".join(done)


def retry_scheduler(for_at: str = "") -> dict[str, Any]:
    """THE OFF-HOT-PATH RETRY (v5f): the same read on the longer bounds, at low priority.

    A result that read MORE of the scheduler than the report on disk replaces it, unless a newer
    pass already measured the run history (that report is better than ours and stays). A retry
    that reads no more annotates the report it was spawned for -- and only that one -- so the
    board says the retry ran and why it did not help. The lock is released whatever happens.
    """
    global _BOUNDS_OVERRIDE
    outcome: dict[str, Any] = {"state": "FAILED"}
    try:
        priority = _lower_priority()
        _BOUNDS_OVERRIDE = (RETRY_TIMEOUT_S, RETRY_VERBOSE_TIMEOUT_S)
        try:
            doc = build()
        finally:
            _BOUNDS_OVERRIDE = None
        meta = {"at": doc["at"], "bounds_s": [RETRY_TIMEOUT_S, RETRY_VERBOSE_TIMEOUT_S],
                "priority": priority, "for_report_at": for_at or None,
                "scheduler_status": doc["scheduler_status"]}
        current = _read_report()
        if _rank(current) < 2 and _rank(doc) > _rank(current):
            doc["scheduler_retry"] = {"state": "REPLACED", **meta,
                                      "replaced_report_at": (current or {}).get("at")}
            _write_report(doc)
            outcome = doc["scheduler_retry"]
        elif current is not None and for_at and current.get("at") == for_at:
            current["scheduler_retry"] = {
                "state": "NO_BETTER", **meta, "timeouts": doc.get("scheduler_timeouts", [])}
            _write_report(current)
            outcome = current["scheduler_retry"]
        else:
            outcome = {"state": "SUPERSEDED", **meta}
    except Exception as exc:
        outcome = {"state": "FAILED", "why": f"{type(exc).__name__}: {exc}"[:200]}
    finally:
        _release_retry_lock()
    return outcome


def _backup_state() -> str:
    """Publish BACKUP_STATE.json (ops/backup_state.py) on this hourly task's clock (v5f).

    Only against the real tree: a caller that moved ROOT (a test's temp box) gets nothing, so a
    test can never write the real report or reach the real alert channels. NEVER RAISES."""
    if Path(__file__).resolve().parent.parent != ROOT:
        return "SKIPPED (ROOT is not this checkout)"
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "backup_state", Path(__file__).resolve().parent / "backup_state.py")
        assert spec is not None and spec.loader is not None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return str(mod.write()["status"])
    except Exception as exc:
        return f"FAILED ({type(exc).__name__})"


def _deliver_account_key_alerts() -> str:
    """The hourly second deliverer of the account-key alert outbox (v5f; MT5-BoxHeartbeat is
    the 5-minute one). Real tree only, like `_backup_state`. NEVER RAISES."""
    if Path(__file__).resolve().parent.parent != ROOT:
        return "SKIPPED (ROOT is not this checkout)"
    try:
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from libs.ops import provenance
        res = provenance.deliver_pending()
        return f"{res.get('rows', 0)} row(s), {len(res.get('sent') or [])} send(s)" + (
            f", {res['error']}" if res.get("error") else "")
    except Exception as exc:
        return f"FAILED ({type(exc).__name__})"


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--retry-scheduler" in args:
        for_at = args[args.index("--for") + 1] if "--for" in args[:-1] else ""
        print(f"process health retry: {retry_scheduler(for_at).get('state')}")
        return 0
    doc = build()
    if doc["scheduler_timeouts"]:
        # A READ TIMED OUT. Hand it to the detached retry and get off the hot path: this pass
        # never waits on the longer bound itself. The report is written BEFORE the spawn, so the
        # retry always finds the report it was spawned for on disk.
        if _take_retry_lock():
            doc["scheduler_retry"] = {"state": "SPAWNED",
                                      "bounds_s": [RETRY_TIMEOUT_S, RETRY_VERBOSE_TIMEOUT_S],
                                      "priority": "below_normal"}
            _write_report(doc)
            try:
                _spawn_retry(str(doc["at"]))
            except Exception as exc:
                _release_retry_lock()
                doc["scheduler_retry"] = {"state": "SPAWN_FAILED",
                                          "why": f"{type(exc).__name__}: {exc}"[:200]}
                _write_report(doc)
        else:
            doc["scheduler_retry"] = {"state": "ALREADY_RUNNING"}
            _write_report(doc)
    else:
        _write_report(doc)
    print(f"process health: {doc['n_processes']} process(es), status {doc['status']}, "
          f"{doc['n_needing_attention']} needing attention")
    for r in doc["processes"]:
        if r["verdict"] != "OK":
            age = "" if r["artifact_age_min"] is None else f"{r['artifact_age_min']:.0f}m"
            print(f"  {r['verdict']:<14} {r['name']:<32} {age:>7}  {r['why'][:70]}")
    print(f"-> {OUT}")
    print(f"backup state: {_backup_state()}")
    print(f"account key alerts: {_deliver_account_key_alerts()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
