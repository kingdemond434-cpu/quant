"""FIX THE STALENESS, DO NOT JUST REPORT IT.

THE PRINCIPAL'S ASK, 2026-09-12, after a day spent resurrecting organs by hand: "make sure nothing
ever ever goes stale permanently... never ever let anything revert go stale or fail ever again".

`organ_contract` and `process_health` both answer "what is broken". Neither repairs anything, so
every failure waits for a human to notice -- and the failures found today had been waiting for
DAYS. MT5-IdentityHealer had never once run. The gauntlet docket had not rotated since it was
built. Seven data sources were silently failing TLS. None of that needed a decision; all of it
needed somebody to look.

THE REMEDIES HERE ARE THE ONES ACTUALLY APPLIED TODAY, and each is bound to the failure SHAPE it
cures rather than to a task name, so a future organ with the same shape is fixed without anybody
adding it to a list:

    NOT_SCHEDULED   an organ with a contract and no task           -> report; registering a task
                                                                      needs its command, which
                                                                      only a human has
    STALE           the task runs but the artifact does not move   -> start the task once
    NO_ARTIFACT     never produced its output                      -> start the task once
    FAILING (2)     "file not found" -- almost always a relative
                    path with no working directory                 -> report with the diagnosis
    FAILING (kill)  0x800710E0 / 0xC000013A on a LONG-RUNNING job  -> report as a daemon
                                                                      registered as periodic

WHY IT ONLY EVER STARTS THINGS. A watchdog that edits task definitions, kills processes or
rewrites config is a second actor on the money path with no review, and this desk has a law about
exactly that. Starting a scheduled task is idempotent, reversible and cannot change what the task
DOES -- so that is the whole of its authority. Everything it cannot fix it NAMES, with the
diagnosis attached, so the human act is thirty seconds rather than an hour of bisection.

IT NEVER REPORTS A CLEAN BOARD IT DID NOT MEASURE. If process_health itself is missing or stale,
this says UNMEASURED and exits non-zero. An absent reading is not a healthy desk (L1.28a).

    python ops/never_stale.py [--apply]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
HEALTH = ROOT / "desks" / "mt5" / "reports" / "process_health.json"
OUT = ROOT / "desks" / "mt5" / "reports" / "NEVER_STALE.json"

#: How old the health reading may be before this refuses to act on it. Acting on a stale board is
#: how a watchdog restarts things that are already fine.
HEALTH_MAX_AGE_MIN = 90

#: Verdicts a restart can plausibly cure. A DISABLED task is a DECISION and is never restarted --
#: today's migration disabled thirty tasks on purpose, and a watchdog that undid that would have
#: resurrected the exact reverters the principal spent the day killing.
RESTARTABLE = {"STALE", "NO_ARTIFACT"}

#: Result codes whose cure is a registration change, not a restart. Named so the report carries
#: the diagnosis rather than the code.
DIAGNOSIS = {
    2: ("relative script path with no working directory -- the scheduler starts it in System32. "
        "Re-register with the ABSOLUTE interpreter and an explicit -WorkingDirectory. "
        "(L0294: MT5-IdentityHealer had never once run for this reason.)"),
    2147942401: ("the system cannot find the file specified -- same shape as code 2: check the "
                 "working directory before the script."),
    2147946720: ("killed by the scheduler. If the job is a DAEMON this is a registration error, "
                 "not a failure: give it an at-startup trigger and ExecutionTimeLimit zero. "
                 "(L0295: MT5-NewsDesk and MT5-ResearchReports both reported this forever.)"),
    3221225786: ("terminated by console close -- the daemon shape again; see L0295."),
    2147943645: ("no logged-on interactive session. An Interactive task cannot run headless; "
                 "either a user must stay signed in or the task needs a service principal."),
    3: ("ENROLMENT GAP, not a failure. The organ completed its work and is reporting a "
        "deficiency it measured: certificates exist that hold no forward clock. Read the count "
        "in the organ's own health artifact and enrol them -- this never means restart."),
}

#: REMEDIES THAT ONLY MAKE SENSE FOR ONE ORGAN, keyed (task, code).
#:
#: `DIAGNOSIS` above is keyed by exit code ALONE, which works for the Windows scheduler codes --
#: 2147946720 means the same thing whoever raised it. It cannot work for the small codes. Exit 1
#: is "a Python process returned non-zero" and belongs to no organ, so nothing could ever be
#: keyed to it and every code-1 failure on this desk reported "no standing remedy for this
#: shape" forever -- which is the same as having no healer at all for the most common code there
#: is.
#:
#: Measured 2026-09-13: MT5-Shadow had been escalating as NEEDS_HUMAN on code 1 for a truthful
#: enrolment census. The generic table had no answer and structurally could not have one. This
#: table is where an answer goes.
#:
#: THE RULE THIS ENCODES: a remedy discovered once is written down here, not re-derived. The
#: escalation message already says so; it had nowhere to say it TO.
TASK_DIAGNOSIS = {
    ("MT5-Shadow", 1): (
        "check `errors` in desks/mt5/reports/shadow/shadow_health.json BEFORE restarting. If it "
        "is empty the cycle SUCCEEDED and this is the pre-2026-09-13 build collapsing an "
        "enrolment gap into FAILED; the fix shipped -- the gap now exits 3. A genuine code 1 "
        "here means a traceback in the shadow cycle, so read the tail of MT5-Shadow.log."),
    ("MT5-NewsDesk", 1): (
        "the news desk exits non-zero when its schedule is empty, which is the LICENSED CALENDAR "
        "being absent rather than a fault -- its log says so in words. Nothing to restart: the "
        "RSS capture half works. Wiring a calendar source is principal-gated work."),
    ("MT5-ResearchReports", 1): (
        "subprocess timeout, not a crash: a report script outran BUDGET_S. Same shape as the "
        "daily cycle's 3h limit (raised to 10h 2026-09-13). Raise the budget for the specific "
        "script or split it; restarting reproduces the timeout."),
}


#: VERDICTS A RESTART CANNOT CURE, with the reason a human needs. Reported, never started.
VERDICT_DIAGNOSIS = {
    "UNMEASURED": (
        "the artifact carries no stamp process_health can read, so its freshness is UNMEASURED -- "
        "not stale, not fine. A restart cannot cure a missing stamp and would loop: name the "
        "artifact's stamp in ops/organ_contract.STAMP_SPEC (or make the organ write one)."),
    "ALERTS_UNARMED": (
        "no alert channel is armed, so every red row on the board reaches no one. Arming needs a "
        "credential only the owner types on the box: create data/secrets/alert_channels.json "
        "(shapes in libs/ops/alert_channels.py). Nothing here can or should invent one."),
}

#: ONE START PER ORGAN PER SHAPE PER WINDOW. A start that did not cure the verdict is evidence the
#: cause is not "it stopped", and starting it again every pass is a loop, not a remedy. Inside the
#: window the row is escalated with that finding instead.
RESTART_COOLDOWN_H = 6.0
STARTS = ROOT / "desks" / "mt5" / "logs" / "never_stale_starts.json"


def _read(p: Path) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _age_min(p: Path) -> float | None:
    try:
        return (datetime.now(tz=UTC).timestamp() - p.stat().st_mtime) / 60.0
    except OSError:
        return None


def _start(task: str) -> tuple[bool, str]:
    """Start a scheduled task. The ONLY mutation this file is allowed to make."""
    try:
        r = subprocess.run(["schtasks", "/run", "/tn", task],
                           capture_output=True, text=True, timeout=90)
        return r.returncode == 0, (r.stdout or r.stderr).strip()[:160]
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"{type(exc).__name__}: {exc}"


def _capital_faults() -> list[dict]:
    """LIVE sleeves that cannot actually trade. The capital half of "never stale".

    A row written LIVE in data/sleeves.json is a claim the gateway will trade it. If no lane on
    this tree can construct its signals, or it names no symbol, the claim is false -- and it is
    the quietest failure the desk has, because the row still counts toward every sleeve count,
    every heat figure and every dashboard tile while placing nothing.

    Found today by exactly this check: a sleeve on dav_range_filter_adx read as "family has no
    constructor" to one lane and resolved cleanly in another, because get_family_func fell through
    to ORTHOGONAL_FAMILIES but never to hunt16 while executables.resolve_family checks hunt16
    FIRST. Two lanes disagreeing about whether a live sleeve can be executed at all.

    ASKS EVERY LANE, because a row answered by a lane you did not think of is not a defect. The
    bracket lane runs the gold windows from GOLD_WINDOWS and carries no family by design.
    """
    import json as _json
    faults: list[dict] = []
    sl = ROOT / "desks" / "mt5" / "data" / "sleeves.json"
    try:
        doc = _json.loads(sl.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [{"sleeve": "(all)", "fault": f"sleeves.json unreadable: {type(exc).__name__}",
                 "needs_human": True}]
    rows = doc if isinstance(doc, list) else (doc.get("sleeves") or [])
    live = [r for r in rows if isinstance(r, dict)
            and str(r.get("status", "")).upper() == "LIVE"]
    sys.path[:0] = [str(ROOT / "desks" / "mt5"), str(ROOT)]
    resolvers = []
    try:
        from mt5desk.executables import resolve_family
        resolvers.append(resolve_family)
    except Exception:
        pass
    try:
        from mt5desk.families import get_family_func
        resolvers.append(get_family_func)
    except Exception:
        pass
    # THE SCALP LANE IS A FOURTH RESOLVER, and leaving it out made this cry wolf on its first run.
    # It reported xau_m15_anti_breakout as placing nothing -- the desk's TOP promotion candidate,
    # 20/14 days with n=101, demonstrably trading. Those families live in
    # `scalp_family_expansion._base_signals` and are reached through mt5desk.scalp_families, which
    # neither of the two resolvers above knows about. Asking every lane is the whole point: a row
    # answered by a lane you did not think of is not a defect (L0297).
    try:
        from mt5desk.scalp_families import _families as _scalp_families

        def _scalp(fam: str):
            try:
                import pandas as _pd
                return fam if fam in _scalp_families()._base_signals(
                    _pd.DataFrame({"open": [], "high": [], "low": [], "close": []})) else None
            except KeyError:
                return None
            except Exception:
                # The probe frame is empty, so a family that exists may still raise on it. That
                # is not evidence of absence -- only a KeyError names a missing family.
                return fam
        resolvers.append(_scalp)
    except Exception:
        pass
    if not resolvers:
        return [{"sleeve": "(all)", "fault": "no family resolver importable -- UNMEASURED, which "
                                             "is not the same as no fault", "needs_human": True}]
    bracket = ("gold_asia", "gold_london_am", "gold_afternoon", "gold_ny_open")
    for r in live:
        name = str(r.get("name") or "?")
        fam = str(r.get("family") or "")
        if not str(r.get("symbol") or "").strip():
            faults.append({"sleeve": name, "fault": "LIVE with no symbol -- cannot be priced, "
                                                    "sized or sent", "needs_human": True})
            continue
        if not fam:
            if not name.startswith(bracket):
                faults.append({"sleeve": name,
                               "fault": "LIVE with no family and not a bracket-lane row",
                               "needs_human": True})
            continue
        if not any(_safe(fn, fam) for fn in resolvers):
            faults.append({"sleeve": name,
                           "fault": f"family {fam!r} resolves in NO lane -- this row places "
                                    f"nothing while counting toward every heat figure",
                           "needs_human": True})
    return faults


def _safe(fn, fam: str) -> bool:
    try:
        return fn(fam) is not None
    except Exception:
        return False


def _health_age_min(doc: Any) -> float | None:
    """The board's age by its own `at` stamp; the mtime only when it carries none."""
    if isinstance(doc, dict):
        try:
            t = datetime.fromisoformat(str(doc.get("at")).replace("Z", "+00:00"))
            if t.tzinfo is None:
                t = t.replace(tzinfo=UTC)
            return max(0.0, (datetime.now(tz=UTC) - t).total_seconds() / 60.0)
        except ValueError:
            pass
    return _age_min(HEALTH)


def _rewritten_not_advancing(row: dict[str, Any]) -> bool:
    """STALE by the stamp inside the artifact while the FILE was rewritten inside its contract:
    the task is running and producing a file, just not doing its work. Starting it again starts
    the same non-advancing writer -- so this shape is escalated, never restarted."""
    basis = str(row.get("age_basis") or "")
    mt = row.get("artifact_mtime_age_min")
    lim = row.get("contract_max_age_min")
    return (basis.startswith("stamp:") and isinstance(mt, (int, float))
            and isinstance(lim, (int, float)) and mt <= lim)


def _recent_start(starts: dict[str, Any], name: str, verdict: str) -> str | None:
    prev = starts.get(name) if isinstance(starts, dict) else None
    if not isinstance(prev, dict) or prev.get("verdict") != verdict:
        return None
    try:
        at = datetime.fromisoformat(str(prev.get("at")))
    except ValueError:
        return None
    if (datetime.now(tz=UTC) - at).total_seconds() / 3600 < RESTART_COOLDOWN_H:
        return str(prev.get("at"))
    return None


def run(apply: bool) -> dict:
    doc = _read(HEALTH)
    age = _health_age_min(doc) if doc is not None else None
    if doc is None or age is None:
        return {"at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
                "status": "UNMEASURED",
                "why": (f"{HEALTH.relative_to(ROOT)} is absent or unreadable. No reading is not a "
                        f"healthy desk -- run ops/process_health.py first."),
                "acted": [], "escalated": []}
    if age > HEALTH_MAX_AGE_MIN:
        return {"at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
                "status": "UNMEASURED",
                "why": (f"the health reading is {age:.0f} min old against a "
                        f"{HEALTH_MAX_AGE_MIN} min bar. Acting on a stale board restarts things "
                        f"that are already fine."),
                "acted": [], "escalated": []}

    acted: list[dict[str, Any]] = []
    escalated: list[dict[str, Any]] = []
    unmeasured: list[dict[str, Any]] = []
    uncontracted: list[str] = []
    starts = _read(STARTS)
    starts = starts if isinstance(starts, dict) else {}
    for row in (doc.get("processes") or []):
        verdict = str(row.get("verdict") or "")
        name = str(row.get("name") or "")
        if not name or verdict in ("OK", "RUNNING", "DISABLED"):
            continue
        # UNCONTRACTED IS A BOOKKEEPING GAP, NOT A BREAKAGE. The organ runs fine; nobody wrote it
        # an artifact contract, so nothing would notice if it stopped. That is worth fixing and
        # worth listing, but escalating it as NEEDS_HUMAN beside a dead gateway is precisely the
        # cry-wolf failure that teaches an operator to stop reading the board (L0311).
        if verdict == "UNCONTRACTED":
            uncontracted.append(name)
            continue

        if verdict in VERDICT_DIAGNOSIS:
            # REPORT-ONLY SHAPES. UNMEASURED is listed apart so it never reads as healthy and
            # never escalates beside a dead gateway; ALERTS_UNARMED is the owner's step.
            if verdict == "UNMEASURED":
                unmeasured.append({"task": name, "why": row.get("why"),
                                   "diagnosis": VERDICT_DIAGNOSIS[verdict]})
            else:
                escalated.append({"task": name, "verdict": verdict, "code": None,
                                  "why": row.get("why"),
                                  "diagnosis": VERDICT_DIAGNOSIS[verdict], "needs_human": True})
            continue

        if verdict in RESTARTABLE and _rewritten_not_advancing(row):
            escalated.append({
                "task": name, "verdict": verdict, "code": row.get("last_result_code"),
                "why": row.get("why"),
                "diagnosis": ("REWRITTEN BUT NOT ADVANCING: the artifact's file was rewritten "
                              "inside its contract while the stamp inside it is old. The task "
                              "runs; a start would run the same writer again. Read the organ's "
                              "log for why its work is skipped (a lock, an early return, an "
                              "input that never changes) -- never restarted from here."),
                "needs_human": True})
            continue

        if verdict in RESTARTABLE:
            started_at = _recent_start(starts, name, verdict)
            if started_at:
                escalated.append({
                    "task": name, "verdict": verdict, "code": row.get("last_result_code"),
                    "why": row.get("why"),
                    "diagnosis": (f"STARTED AT {started_at} FOR THIS SAME VERDICT AND IT DID NOT "
                                  f"CURE IT. Not starting again inside {RESTART_COOLDOWN_H:g}h: "
                                  f"a start that does not cure is a loop. Read the task's log."),
                    "needs_human": True})
                continue
            if not apply:
                acted.append({"task": name, "verdict": verdict, "action": "would start",
                              "why": row.get("why")})
                continue
            ok, msg = _start(name)
            if ok:
                starts[name] = {"verdict": verdict,
                                "at": datetime.now(tz=UTC).isoformat(timespec="seconds")}
            acted.append({"task": name, "verdict": verdict,
                          "action": "started" if ok else "start FAILED",
                          "detail": msg, "why": row.get("why")})
            continue

        code = row.get("last_result_code")
        # PER-ORGAN FIRST, then the generic code table. The specific answer beats the general one
        # whenever both exist, and for the small exit codes only the specific one can exist.
        diag = TASK_DIAGNOSIS.get((name, code)) if isinstance(code, int) else None
        if diag is None and isinstance(code, int):
            diag = DIAGNOSIS.get(code)
        escalated.append({
            "task": name, "verdict": verdict, "code": code,
            "why": row.get("why"),
            # THE DIAGNOSIS IS THE POINT. A list of broken task names costs an hour of bisection;
            # a list with the cure attached costs thirty seconds.
            "diagnosis": diag or ("no standing remedy for this shape -- inspect the task's own "
                                  "log. If a remedy is found, add it to DIAGNOSIS so the next "
                                  "occurrence arrives with its answer."),
            "needs_human": True,
        })

    if apply and starts:
        try:
            STARTS.parent.mkdir(parents=True, exist_ok=True)
            STARTS.write_text(json.dumps(starts, indent=1), encoding="utf-8")
        except OSError:
            pass
    capital = _capital_faults()
    # UNMEASURED IS NOT OK (L1.28a): a board with unmeasured rows and nothing else wrong says so.
    status = ("NEEDS_HUMAN" if (escalated or capital) else
              "UNMEASURED" if unmeasured else "OK")
    return {
        "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "health_age_min": round(age, 1),
        "status": status,
        "n_acted": len(acted), "n_escalated": len(escalated),
        "n_unmeasured": len(unmeasured),
        "applied": bool(apply),
        "acted": acted, "escalated": escalated, "unmeasured": unmeasured,
        "capital_faults": capital,
        "uncontracted": uncontracted,
        "uncontracted_note": ("these run but have no artifact contract, so nothing would notice "
                              "if they stopped. Not broken -- unwatched. Add each to "
                              "ops/organ_contract.CONTRACTS."),
        "authority": ("This watchdog may START a scheduled task and nothing else. It never edits "
                      "a task, kills a process, rewrites config or re-enables a DISABLED task -- "
                      "a disabled task is a DECISION, and undoing those would resurrect the very "
                      "reverters the migration killed."),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="actually start what it can")
    a = ap.parse_args(argv)
    doc = run(a.apply)
    print(f"never-stale: {doc['status']}"
          + (f" -- {doc['why']}" if doc.get("why") else ""))
    for r in doc.get("acted", []):
        print(f"  {r['action']:<14} {r['task']:<28} ({r['verdict']})")
    for r in doc.get("escalated", []):
        print(f"  NEEDS HUMAN    {r['task']:<28} ({r['verdict']}, code {r['code']})")
        print(f"                 {str(r['diagnosis'])[:110]}")
    for r in doc.get("capital_faults", []):
        print(f"  CAPITAL FAULT  {str(r['sleeve'])[:28]:<28} {str(r['fault'])[:70]}")
    if doc.get("uncontracted"):
        print(f"  unwatched      {len(doc['uncontracted'])} organ(s) with no artifact contract: "
              f"{', '.join(doc['uncontracted'][:6])}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    print(f"-> {OUT}")
    return 0 if doc["status"] in ("OK",) else 1


if __name__ == "__main__":
    raise SystemExit(main())
