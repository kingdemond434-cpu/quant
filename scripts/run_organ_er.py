#!/usr/bin/env python3
"""ORGAN ER (R0215) -- a dark organ gets DIAGNOSED AND TREATED the same day, not merely counted.

PRINCIPAL ORDER (2026-07-31): *"make sure they're all started, always make sure all r running
everyday -- if someone is in coma revive them same day like hospital."*

THE GAP, and it is the shape of half the defects found today. The desk DETECTS coma well:
check_exploration reports the family DARK, check_organ_liveness separates NEVER-PRODUCED from
STALE, check_miner_runway watches the seats. Three organs have been reported dark for days and
every one of those reports was correct. NOTHING TREATED THEM. Detection without treatment is a
monitor, not a hospital -- and a ward whose alarms nobody answers eventually gets its alarms
turned off (L1.43).

organ_catchup.py is the closest thing that existed and it is deliberately narrow: it re-fires
QUOTA-KILLED organs, one per tick, for six named seats. That leaves the whole rest of the
diagnosis space untreated -- an organ that is dark because it was never scheduled, because its
auth expired, because it writes an artifact nobody reads, or because it crashes on start, gets
the same silence as one that was merely rate-limited. Different diseases, one non-treatment.

TRIAGE FIRST, because the treatment depends entirely on the cause and a wrong treatment is worse
than none. Every dark organ is diagnosed into exactly one of:

  UNSCHEDULED     no manifest line -> it was never going to run. Treatment: the scheduler
                  manifest, not a re-fire. Re-firing this by hand hides the real fault forever.
  BLOCKED         a NAMED external dependency is missing (an unfunded seat, an absent key). No
                  amount of re-firing fixes it, so it ESCALATES with the exact blocker and price
                  rather than burning a slot per tick pretending.
  MISWIRED        the organ RAN but its declared artifact never appeared -- so it is alive and
                  reported dead. The fix is the wiring or the registry, and re-firing a healthy
                  organ forever is the most expensive possible response.
  STARVED         it ran, failed, and the log names a transient cause (quota, 5xx, timeout).
                  Treatment: re-fire, which is what organ_catchup already does well.
  CRASHED         it ran and died on a non-transient error. Treatment: re-fire once, then
                  escalate with the error text -- a second identical crash is a bug, not a blip.
  UNKNOWN         dark with no log at all. Treatment: re-fire once to PRODUCE a log, because a
                  diagnosis needs evidence and the cheapest way to get it is to run the thing.

SAME-DAY IS THE STANDARD, and it is measured. Any organ dark longer than COMA_HOURS with no
treatment attempt recorded is a DEFECT this fence names -- not backlog. "It is on the list" is
exactly the state the principal's instruction forbids.

TREATMENT IS RECORDED, ALWAYS. Every attempt appends to data/organ_er_log.jsonl with its
diagnosis, action and outcome, so "we tried" is a dated fact rather than an impression -- and so
a treatment that never works becomes visible as a pattern instead of repeating forever.

REFUSES TO FAKE A CURE: an organ is only DISCHARGED when its artifact actually appears. A
re-fire that returns 0 but produces nothing stays ADMITTED, because exit status is the organ's
opinion of itself and the artifact is the evidence.

    python scripts/run_organ_er.py [--treat] [--json]
"""
from __future__ import annotations

import argparse
import contextlib
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from libs.ops.lawful import guard as _law_guard  # noqa: E402

_STATE = "data/organ_er.json"
_LOG = "data/organ_er_log.jsonl"

#: How long an organ may stay dark before it is a DEFECT rather than a delay. 24h because the
#: principal's standard is same-day and every organ in the ward has a cadence at or under a day;
#: an organ silent past its own cadence plus a full day is not late, it is down.
COMA_HOURS = 24.0

#: Transient markers in a log that make a re-fire the right treatment rather than an escalation.
#: Same list organ_catchup uses -- one vocabulary for one phenomenon.
_TRANSIENT = ("429", "529", "502", "503", "504", "overloaded", "rate limit", "quota",
              "timed out", "timeout", "connection reset", "temporarily")

#: Markers that mean no re-fire will ever help: the organ needs something bought or configured.
#: Escalating these instead of retrying is what stops the ward burning a slot per tick on a
#: patient whose treatment is a credit card.
_BLOCKED = ("402", "payment required", "insufficient credit", "no api key", "unauthorized",
            "401", "403", "missing key", "not funded")


def _age_hours(p: Path, now: float) -> float | None:
    """Age from the artifact's own `generated` stamp where it has one, else mtime.

    Content outranks mtime for the same reason L1.44 gives: a deploy rewrites mtime, so mtime
    lies FRESH -- the dangerous direction for a liveness check."""
    try:
        if p.is_dir():
            kids = [c for c in p.iterdir() if c.is_file()]
            return min(((now - c.stat().st_mtime) / 3600.0 for c in kids), default=None)
        raw = p.read_text("utf-8", errors="ignore")
    except OSError:
        return None
    # A non-JSON or unstamped artifact falls through to mtime BY DESIGN -- some produced files
    # are plain text and some predate the `generated` convention. contextlib.suppress rather than
    # `except: pass` because the two read identically to a human and differently to the fence,
    # and this one genuinely has a defined next step rather than a swallowed failure.
    with contextlib.suppress(ValueError, TypeError):
        data = json.loads(raw)
        if isinstance(data, dict) and data.get("generated"):
            at = datetime.fromisoformat(str(data["generated"]))
            at = at.replace(tzinfo=UTC) if at.tzinfo is None else at
            return max(0.0, (datetime.now(tz=UTC) - at).total_seconds() / 3600.0)
    try:
        return max(0.0, (now - p.stat().st_mtime) / 3600.0)
    except OSError:
        return None


def _tail_log(root: Path, name: str, n: int = 4000) -> str:
    """Whatever the organ last said about itself. No log is itself a diagnosis (UNKNOWN)."""
    best, newest = "", -1.0
    logdir = root / "data/cro_ai_logs"
    try:
        for p in logdir.glob(f"*{name.split('_')[0]}*"):
            try:
                m = p.stat().st_mtime
            except OSError:
                continue
            if m > newest:
                newest, best = m, p.read_text("utf-8", errors="ignore")[-n:]
    except OSError:
        return ""
    return best


def diagnose(root: Path, name: str, artifact: str, max_age_h: float,
             *, now: float | None = None, manifest: str = "") -> dict[str, Any]:
    """Why is this organ dark? The treatment depends entirely on the answer."""
    now = now if now is not None else time.time()
    age = _age_hours(root / artifact, now)
    if age is not None and age <= max_age_h:
        return {"organ": name, "state": "HEALTHY", "age_hours": round(age, 2),
                "artifact": artifact}

    log = _tail_log(root, name).lower()
    scheduled = name in manifest or artifact in manifest or f"run_{name}" in manifest
    produced_ever = age is not None

    # SECONDARY ARTIFACTS ARE NOT PATIENTS. data/hunt_coverage.json is written by kimi_hunter and
    # by nothing else, yet check_exploration lists it as its own organ -- so kimi's silence was
    # counted TWICE in the desk's dark total ("3 of 6 dark" is really two patients, one of them
    # double-billed), and this artifact would report UNSCHEDULED forever because it has no runner
    # to schedule. Attributing it to its producer is what makes the ward count mean something.
    producer = _SECONDARY.get(name)
    if producer:
        return {"organ": name, "state": "SECONDARY", "artifact": artifact,
                "age_hours": None if age is None else round(age, 2),
                "max_age_hours": max_age_h, "produced_ever": produced_ever,
                "scheduled": True, "producer": producer,
                "action": (f"not an organ -- {artifact} is written by {producer} and by nothing "
                           f"else. Treat {producer}; this file follows. It can never have a "
                           "manifest line of its own, so reporting it UNSCHEDULED is a permanent "
                           "false alarm and double-counts one patient as two."),
                "treatable_here": False, "coma": False}

    if not scheduled:
        dx, action = "UNSCHEDULED", ("add a manifest line -- re-firing by hand would hide the "
                                     "real fault, which is that nothing was ever going to run it")
    elif any(m in log for m in _BLOCKED):
        dx, action = "BLOCKED", ("a NAMED external dependency is missing; escalate with the "
                                 "blocker -- no re-fire fixes a patient whose treatment is a "
                                 "credit card")
    elif log and not produced_ever and "traceback" not in log and not any(
            m in log for m in _TRANSIENT):
        dx, action = "MISWIRED", ("the organ RAN but its declared artifact never appeared -- it "
                                  "is alive and reported dead. Fix the wiring or the registry; "
                                  "re-firing a healthy organ forever is the worst response")
    elif any(m in log for m in _TRANSIENT):
        dx, action = "STARVED", "transient cause in the log -- re-fire"
    elif "traceback" in log or "error" in log:
        dx, action = "CRASHED", ("re-fire once, then escalate with the error text -- a second "
                                 "identical crash is a bug, not a blip")
    else:
        dx, action = "UNKNOWN", ("dark with no log -- re-fire once to PRODUCE one, because a "
                                 "diagnosis needs evidence and running it is the cheapest way "
                                 "to get some")
    return {"organ": name, "state": dx, "artifact": artifact,
            "age_hours": None if age is None else round(age, 2),
            "max_age_hours": max_age_h, "produced_ever": produced_ever,
            "scheduled": scheduled, "action": action,
            "treatable_here": dx in ("STARVED", "CRASHED", "UNKNOWN"),
            "coma": age is None or age > max_age_h + COMA_HOURS}


def treat(root: Path, dx: dict[str, Any], runner: str | None,
          *, run=subprocess.run, timeout: int = 900) -> dict[str, Any]:
    """Attempt the treatment, then check the ARTIFACT -- never the exit status.

    A re-fire that returns 0 and produces nothing is not a cure; exit status is the organ's
    opinion of itself and the artifact is the evidence. DISCHARGED requires the evidence."""
    if not dx.get("treatable_here"):
        return {"organ": dx["organ"], "attempted": False, "outcome": "ESCALATED",
                "why": dx.get("action", "")}
    if not runner:
        return {"organ": dx["organ"], "attempted": False, "outcome": "NO-RUNNER",
                "why": "no runner registered -- the ER cannot treat what it cannot invoke"}
    before = _age_hours(root / dx["artifact"], time.time())
    try:
        r = run([sys.executable, str(root / runner)] if runner.endswith(".py")
                else ["bash", str(root / runner)],
                cwd=root, capture_output=True, text=True, timeout=timeout)
        rc, err = r.returncode, (r.stderr or "")[-400:]
    except (OSError, subprocess.SubprocessError) as exc:
        rc, err = -1, f"{type(exc).__name__}: {exc}"
    after = _age_hours(root / dx["artifact"], time.time())
    cured = after is not None and (before is None or after < before)
    return {"organ": dx["organ"], "attempted": True, "runner": runner, "rc": rc,
            "outcome": "DISCHARGED" if cured else "STILL-ADMITTED",
            "why": ("artifact refreshed -- the evidence, not the exit code"
                    if cured else
                    f"re-fire returned {rc} and the artifact did NOT refresh; exit status is the "
                    f"organ's opinion of itself{': ' + err if err else ''}")}


def build_report(root: Path | None = None, *, do_treat: bool = False,
                 family: dict[str, tuple[str, float, str]] | None = None,
                 runners: dict[str, str] | None = None, run=subprocess.run) -> dict[str, Any]:
    root = root or _ROOT
    if family is None:
        from scripts.check_exploration import _FAMILY as family
    runners = runners if runners is not None else _RUNNERS
    try:
        manifest = (root / "ops/crontab.manifest").read_text("utf-8", errors="ignore")
    except OSError:
        manifest = ""

    log_error = ""
    ward = [diagnose(root, n, rel, mx, manifest=manifest) for n, (rel, mx, _h) in family.items()]
    sick = [d for d in ward if d["state"] != "HEALTHY"]
    comas = [d for d in sick if d["coma"]]
    treatments = []
    if do_treat:
        treatments = [treat(root, d, runners.get(d["organ"]), run=run) for d in sick]
        path = root / _LOG
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                stamp = datetime.now(tz=UTC).isoformat()
                for d, t in zip(sick, treatments, strict=False):
                    fh.write(json.dumps({"at": stamp, "diagnosis": d, "treatment": t}) + "\n")
        except OSError as exc:
            # Never block a treatment on telemetry -- but never swallow it either. An unwritable
            # ward log means "we tried" stops being a dated fact, which is precisely how a
            # treatment that never works hides as a fresh attempt every tick.
            log_error = (f"ward log unwritable ({type(exc).__name__}: {exc}) -- treatment "
                         "history is NOT being recorded, so a never-working treatment cannot be "
                         "seen as a pattern")

    untreated = [d["organ"] for d in comas
                 if not any(t["organ"] == d["organ"] and t.get("attempted") for t in treatments)]
    return {
        "generated": datetime.now(tz=UTC).isoformat(),
        "law": "L1.32/L1.28a -- a dark organ is DIAGNOSED AND TREATED the same day. Detection "
               "without treatment is a monitor, not a hospital, and a ward whose alarms nobody "
               "answers gets its alarms switched off (L1.43).",
        "status": ("OK" if not sick else
                   "COMA-UNTREATED" if untreated else
                   "TREATED" if do_treat else "SICK-UNTREATED"),
        "n_organs": len(ward), "n_healthy": len(ward) - len(sick),
        "n_sick": len(sick), "n_coma": len(comas),
        "coma_hours": COMA_HOURS,
        "ward": ward,
        "treatments": treatments,
        "escalate": [{"organ": d["organ"], "state": d["state"], "action": d["action"]}
                     for d in sick if not d["treatable_here"]],
        "untreated_comas": untreated,
        "log_error": log_error,
        "detail": (f"{len(ward) - len(sick)}/{len(ward)} organs healthy"
                   + (f"; {len(comas)} in coma >{COMA_HOURS:.0f}h" if comas else "")
                   + (f"; {sum(1 for t in treatments if t['outcome'] == 'DISCHARGED')} discharged"
                      if treatments else "")
                   + (f"; UNTREATED: {', '.join(untreated)}" if untreated else "")),
    }


#: Artifacts that belong to ANOTHER organ. Verified by grep before listing: hunt_coverage.json is
#: written at kimi_hunter.py:50 and referenced nowhere else that writes. Listing it here is what
#: stops one silent organ being reported as two dead ones.
_SECONDARY: dict[str, str] = {"hunt_coverage": "kimi_hunter"}

#: organ -> the script that re-fires it. Only organs the ER can actually invoke appear; a missing
#: runner is reported as NO-RUNNER rather than silently skipped, because an untreatable patient
#: nobody names is the failure this organ exists to end.
#
# THE TWO BLINDSPOT PATHS WERE WRONG FROM THE DAY THEY WERE WRITTEN, 2026-09-05. They read
# `scripts/run_blindspot_max.py` and `scripts/run_blindspot_prober.py`; neither name has ever
# existed in this repository's history -- the organs are `scripts/blindspot_max.py` and
# `scripts/blindspot_prober.py`, which is how daily_research_cycle.py and build_enforcement_matrix
# both spell them. The ER therefore reported NO-RUNNER for exactly the two organs it COULD have
# treated, and a triage that files its two treatable patients as untreatable is worse than one
# that admits it has no ward: the miss reads as a fact about the desk rather than a typo.
_RUNNERS: dict[str, str] = {
    "capability_hunt": "ops/run_capability_hunt.sh",
    "blindspot_max": "scripts/blindspot_max.py",
    "blindspot_prober": "scripts/blindspot_prober.py",
    "kimi_hunter": "scripts/kimi_hunter.py",
    "deep_sweep_meta": "ops/run_deep_sweep.sh",
}


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--treat", action="store_true", help="attempt treatment, not just triage")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = build_report(_ROOT, do_treat=args.treat)
    out = _ROOT / _STATE
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2), "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"organ ER (L1.32): {rep['status']} -- {rep['detail']}")
        for d in rep["ward"]:
            if d["state"] != "HEALTHY":
                print(f"  {d['state']:<12} {d['organ']:<20} {str(d['action'])[:78]}")
    return 0 if rep["status"] in ("OK", "TREATED") else 2


if __name__ == "__main__":
    sys.exit(main())
