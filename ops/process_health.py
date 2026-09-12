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


def _tasks() -> list[dict[str, str]]:
    """Every scheduled task the box knows about, from schtasks' own CSV.

    `schtasks /query /v /fo CSV` is used rather than the PowerShell cmdlets because it needs no
    module import, returns one flat table, and is the same source the operator sees in the GUI.
    A machine with no scheduler (a Linux box running this for a merged view) yields an empty list
    rather than an error: absence of a scheduler is not a failed desk.
    """
    try:
        proc = subprocess.run(["schtasks", "/query", "/v", "/fo", "CSV"],
                              capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError):
        return []
    if proc.returncode != 0 or not proc.stdout.strip():
        return []
    rows: list[dict[str, str]] = []
    for row in csv.DictReader(io.StringIO(proc.stdout)):
        name = (row.get("TaskName") or "").strip()
        # schtasks repeats the header row per folder; skip those and the Microsoft tree.
        if not name or name == "TaskName" or name.startswith("\\Microsoft"):
            continue
        rows.append(row)
    return rows


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

    for t in _tasks():
        name = (t.get("TaskName") or "").strip().lstrip("\\")
        seen.add(name)
        code = _normalise_code(t.get("Last Result"))
        artifact, max_age, purpose = contracts.get(name, ("", 0, ""))
        age = _age_min(ROOT / artifact) if artifact else None

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
        age = _age_min(ROOT / artifact)
        rows.append({
            "name": organ,
            "verdict": "NOT_SCHEDULED",
            "why": ("this organ has a contract but no scheduled task on this box -- it cannot "
                    "run at all"),
            "state": "ABSENT", "last_run": "", "next_run": "",
            "last_result_code": None, "last_result": "never run on this box",
            "artifact": artifact,
            "artifact_age_min": None if age is None else round(age, 1),
            "contract_max_age_min": max_age, "purpose": purpose,
        })

    order = {"NOT_SCHEDULED": 0, "FAILING": 1, "NO_ARTIFACT": 2, "STALE": 3,
             "DISABLED": 4, "UNCONTRACTED": 5, "OK": 6}
    rows.sort(key=lambda r: (order.get(str(r["verdict"]), 9), str(r["name"])))
    counts: dict[str, int] = {}
    for r in rows:
        counts[str(r["verdict"])] = counts.get(str(r["verdict"]), 0) + 1

    bad = [r for r in rows if r["verdict"] in ("NOT_SCHEDULED", "FAILING", "NO_ARTIFACT", "STALE")]
    return {
        "at": now.isoformat(timespec="seconds"),
        "host": __import__("socket").gethostname(),
        "n_processes": len(rows),
        "counts": counts,
        # The headline is the WORST row, never the proportion that are fine. "38 of 41 healthy"
        # is how a dead gateway hides behind a green majority.
        "status": "OK" if not bad else "ATTENTION",
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
