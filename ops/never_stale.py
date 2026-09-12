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
}


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


#: The OpenRouter side, organ by organ: (artifact, max age in hours, what it is).
#: EVERY LLM ORGAN IS HERE, not only the two the principal named -- deepseek and kimi are the loud
#: ones, and the quiet ones (the code auditor, the panel, the blind researcher, the hypothesis
#: generator) are exactly the organs that can stop without anyone noticing, because nothing
#: downstream complains when a stream of ideas simply thins.
LLM_ORGANS: tuple[tuple[str, int, str], ...] = (
    ("data/code_audit.jsonl", 48, "the LLM code auditor's findings"),
    ("data/max_audit_report.json", 48, "the maximal audit sweep"),
    ("data/deep_audit.json", 72, "the deep architecture audit"),
    ("data/free_research.json", 24, "the free-tier panel's research"),
    ("data/external_panel_log.jsonl", 24, "the external panel's recommendations"),
    ("data/hypothesis_queue.jsonl", 24, "LLM hypothesis generation"),
    ("data/kimi_hunt.json", 12, "kimi's deep-forest hunt"),
    ("data/intelligence/kimi", 12, "kimi's donations to the compiler"),
    ("data/intelligence/deepseek", 12, "deepseek's donations to the compiler"),
    ("desks/mt5/reports/AUDIT_INTAKE.json", 24, "the classified cold-audit intake the CEO reads"),
)


def _llm_faults() -> list[dict]:
    """The OpenRouter half of "never stale": audits, hypothesis generation, kimi, deepseek.

    THE PRINCIPAL'S INSTRUCTION, 2026-09-12: this fixer checks the OpenRouter side too, and not
    only the two named seats -- everything on that side.

    DARK IS NOT STALE, AND THE DIFFERENCE IS THE WHOLE POINT. If the seat has no key, every LLM
    organ is silent for one reason, and reporting ten stale artifacts sends the reader chasing ten
    ghosts instead of pasting one key. So the seat is checked FIRST and a dark seat short-circuits
    into a single NEEDS_KEY row that names the file and nothing else. That is also why this
    function never prints, logs or returns any part of the key itself: it asks only whether one
    resolves.

    Measured on this box 2026-09-12: `check_llm_seat` resolved 0 seats and all seven cold-audit
    artifacts were absent -- the audit lane had never run here, which read from the outside like
    an audit that kept finding nothing.
    """
    faults: list[dict] = []
    sys.path[:0] = [str(ROOT)]
    n_seats: int | None = None
    try:
        from libs.ops import llm_seat
        n_seats = len(llm_seat.seats())
    except Exception as exc:
        faults.append({"organ": "llm seat", "state": "UNMEASURED",
                       "fault": f"seat layer not importable: {type(exc).__name__}: {exc}",
                       "needs_human": True})
        return faults

    if not n_seats:
        return [{
            "organ": "llm seat", "state": "NEEDS_KEY",
            "fault": ("no LLM seat resolves, so EVERY OpenRouter organ is dark -- audits, "
                      "hypothesis generation, kimi and deepseek alike. Not stale: never ran."),
            "fix": ("paste the OpenRouter key into data/secrets/llm_panel.json (the providers[0] "
                    "'key' field, currently empty). The seat layer re-reads it at every organ "
                    "start, so nothing needs restarting and no task needs re-registering."),
            "needs_human": True,
            "why_only_one_row": ("the ten LLM artifacts below it are all silent for this one "
                                 "reason; listing them separately would be ten ghosts."),
        }]

    now = datetime.now(tz=UTC)
    for rel, max_h, what in LLM_ORGANS:
        p = ROOT / rel
        if p.is_dir():
            files = sorted(p.glob("*.json")) + sorted(p.glob("*.jsonl"))
            newest = max((f.stat().st_mtime for f in files), default=None)
            if newest is None:
                faults.append({"organ": rel, "state": "EMPTY", "is": what, "needs_human": True,
                               "fault": "a seat has a key but this donation directory is empty"})
                continue
            age_h = (now.timestamp() - newest) / 3600.0
        elif not p.exists():
            faults.append({"organ": rel, "state": "ABSENT", "is": what, "needs_human": True,
                           "fault": f"a seat resolves but {rel} has never been produced"})
            continue
        else:
            age_h = (now.timestamp() - p.stat().st_mtime) / 3600.0
        if age_h > max_h:
            faults.append({"organ": rel, "state": "STALE", "is": what, "needs_human": True,
                           "age_hours": round(age_h, 1),
                           "fault": f"{age_h:.0f}h old against a {max_h}h contract, with a "
                                    f"working seat -- so the organ itself stopped"})
    return faults


def _uncovered_certificates() -> list[dict]:
    """Certificates with no forward clock. Capital the desk EARNED and is not deploying.

    A ten-gate certificate is the most expensive object this desk produces -- it costs a share of
    a fixed family-wise error budget that every other hypothesis then has to clear. A certificate
    with no clock is that cost paid and the position never taken, and it is invisible in every
    count the desk publishes: `missing_sleeves: 0` is true, because from the shadow lane's point
    of view nothing is missing -- the certificate was never enrolled to begin with.

    Measured 2026-09-12: 63 of 67 certificates hold a LIVE clock; four do not.
    """
    import json as _json
    try:
        surv = _json.loads((ROOT / "desks/mt5/reports/UNIVERSAL_SURVIVORS.json")
                           .read_text(encoding="utf-8"))["survivors"]
        reg = _json.loads((ROOT / "desks/mt5/data/sleeve_registry.json")
                          .read_text(encoding="utf-8"))["sleeves"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return [{"cert": "(all)", "needs_human": True,
                 "fault": f"unreadable: {type(exc).__name__}"}]
    keys = set()
    for v in reg.values():
        i = (v or {}).get("identity") or {}
        keys.add((i.get("symbol"), i.get("family"), i.get("selector")))

    # ASK THE ENGINE, DO NOT GUESS. `certified_sleeves()` is the exact function `shadow_forward`
    # enrols from, and it already prints an ENROL-GAP line naming why it dropped a certificate.
    # Reading the registry alone would say "no clock" and stop there, which is a symptom; the
    # engine's own reason is the defect. Measured 2026-09-12: six certificates were dropped with
    # "shadow_spec.params is NoneType, not a mapping" -- a certificate written without the
    # parameterisation that passed the gates, which the engine correctly refuses to guess.
    enrollable: set[tuple] = set()
    engine_note: str | None = None
    try:
        sys.path[:0] = [str(ROOT / "desks" / "mt5"), str(ROOT / "desks" / "mt5" / "research")]
        import shadow_forward as _sf
        for row in _sf.certified_sleeves():
            enrollable.add((row[0], row[3] if len(row) > 3 else None, row[1]))
    except Exception as exc:
        engine_note = (f"forward engine not importable here ({type(exc).__name__}: {exc}) -- "
                       f"enrollability is the ENGINE's fact and is UNMEASURED, not assumed")

    out = []
    for name, c in surv.items():
        s = c.get("shadow_spec") or {}
        k = (s.get("symbol"), s.get("family"), s.get("selector"))
        if k in keys:
            continue
        if engine_note is None and k in enrollable:
            # The engine WILL enrol it; it simply has not run since the certificate was written.
            # That is a cadence fact, not a defect, and the next shadow pass closes it.
            continue
        why = (engine_note or
               (f"params is {type(s.get('params')).__name__}, not a mapping"
                if not isinstance(s.get("params"), dict)
                else "the forward engine does not make this certificate enrollable"))
        out.append({"cert": name[:80], "symbol": s.get("symbol"), "family": s.get("family"),
                    "selector": s.get("selector"), "side": s.get("side"), "needs_human": True,
                    "engine_reason": why,
                    "fault": ("a ten-gate certificate with NO forward clock and none coming -- "
                              "the family-wise trial budget was spent and no capital rides on it"),
                    "fix": ("fix the WRITER of the certificate so it records the parameterisation "
                            "that passed, then re-run the shadow pass. Never hand-enrol it: "
                            "guessing the parameters enrols a different strategy under a "
                            "certificate that was earned by another one.")})
    return out


def _safe(fn, fam: str) -> bool:
    try:
        return fn(fam) is not None
    except Exception:
        return False


def run(apply: bool) -> dict:
    age = _age_min(HEALTH)
    doc = _read(HEALTH)
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

    acted: list[dict] = []
    escalated: list[dict] = []
    uncontracted: list[str] = []
    for row in (doc.get("processes") or []):
        verdict = str(row.get("verdict") or "")
        name = str(row.get("name") or "")
        if not name or verdict in ("OK", "RUNNING", "DISABLED"):
            continue
        # UNCONTRACTED IS A BOOKKEEPING GAP, NOT A BREAKAGE. The organ runs fine; nobody wrote it
        # an artifact contract, so nothing would notice if it stopped. That is worth fixing and
        # worth listing, but escalating it as NEEDS_HUMAN beside a dead gateway is precisely the
        # cry-wolf failure that teaches an operator to stop reading the board (L0296).
        if verdict == "UNCONTRACTED":
            uncontracted.append(name)
            continue

        if verdict in RESTARTABLE:
            if not apply:
                acted.append({"task": name, "verdict": verdict, "action": "would start",
                              "why": row.get("why")})
                continue
            ok, msg = _start(name)
            acted.append({"task": name, "verdict": verdict,
                          "action": "started" if ok else "start FAILED",
                          "detail": msg, "why": row.get("why")})
            continue

        code = row.get("last_result_code")
        diag = DIAGNOSIS.get(code) if isinstance(code, int) else None
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

    capital = _capital_faults()
    llm = _llm_faults()
    uncovered = _uncovered_certificates()
    return {
        "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "health_age_min": round(age, 1),
        "status": ("OK" if not (escalated or capital or llm or uncovered) else "NEEDS_HUMAN"),
        "n_acted": len(acted), "n_escalated": len(escalated),
        "applied": bool(apply),
        "acted": acted, "escalated": escalated,
        "capital_faults": capital,
        "llm_faults": llm,
        "uncovered_certificates": uncovered,
        "uncovered_note": ("a ten-gate certificate with no forward clock is the desk's most "
                           "expensive object left on the shelf: the family-wise error budget was "
                           "spent to earn it and no capital is riding on it."),
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
    for r in doc.get("llm_faults", []):
        print(f"  {r['state']!s:<14} {str(r['organ'])[:28]:<28} {str(r['fault'])[:72]}")
        if r.get("fix"):
            print(f"  {'':<14} FIX: {str(r['fix'])[:100]}")
    unc = doc.get("uncovered_certificates") or []
    if unc:
        print(f"  NO CLOCK       {len(unc)} certificate(s) earned and not deployed:")
        for r in unc[:8]:
            print(f"  {'':<14} {r['symbol']!s:<10} {str(r['family'])[:24]:<24} "
                  f"{r['selector']!s}")
    if doc.get("uncontracted"):
        print(f"  unwatched      {len(doc['uncontracted'])} organ(s) with no artifact contract: "
              f"{', '.join(doc['uncontracted'][:6])}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    print(f"-> {OUT}")
    return 0 if doc["status"] in ("OK",) else 1


if __name__ == "__main__":
    raise SystemExit(main())
