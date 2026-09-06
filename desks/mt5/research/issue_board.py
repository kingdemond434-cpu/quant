#!/usr/bin/env python3
"""EVERY ISSUE THE DESK CAN SEE, IN ONE PLACE, WITH THE REPAIR THAT CLOSES IT.

    "all info n also errors staleness identity brokens n all issues so we can catch them too
     and unlimited fixers n watchers on it to always fix pipeline etc ... no edge search
     staleness this that fully ever"          -- the principal, 2026-09-06

DETECTION WAS NEVER THE GAP. This tree carries 121 `check_*` scripts and they mostly work. What
it did not carry was one place that runs them, one surface that shows the aggregate, and one
actuator that acts on it. So a real breach could be detected correctly, written to an alarm file,
and read by nobody -- which is precisely what happened with `monitor_mt5_shadow_sync` returning
FAILED every thirty minutes for ten days into a systemd timer whose exit code nobody reads.

This module aggregates and ACTS. It does not reimplement a single detector.

THE STALENESS CONTRACT IS THE GENERALISATION OF THE EDGE-SEARCH BUG. That bug was not "edge
search broke". It was that the dashboard called something an hourly leg while nothing made it
hourly, and the only thing that noticed was a human reading an age on a tile. The cure is not to
watch edge_search harder -- it is to give EVERY producer a declared cadence and to treat an
artifact older than its cadence as an issue with a known repair:

    artifact older than TOLERANCE x cadence  ->  STALE  ->  repair = run its producer

That rule catches the next leg to stall without anybody having thought of it, which is the only
kind of fix worth making after being bitten twice.

SEVERITY IS ABOUT CONSEQUENCE, NOT VOLUME:

    CAPITAL   the desk could size or trade wrongly right now
    BLIND     the desk believes something false about itself
    STALLED   a producer has stopped and the pipeline is starved downstream
    DEGRADED  working, but below the standard it declares

AUTO-REPAIR IS BOUNDED AND HONEST. An issue is auto-repairable only when the repair is idempotent,
cheap and reversible -- rerunning a producer, clearing a lock whose owner is gone. Anything that
touches capital, loosens a gate or resolves a merge is NEVER auto-repaired, and says so. An
actuator that can quietly fix a gate is an actuator that can quietly disable one.
"""
from __future__ import annotations

import contextlib
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
REPORT = BASE / "reports" / "ISSUE_BOARD.json"

#: How many multiples of its declared cadence an artifact may age before it is STALE. Two, not
#: one: a single missed pass is a hiccup and paging on it teaches everyone to ignore the board
#: (L1.37). Two consecutive misses is a pattern.
STALE_TOLERANCE = 2.0

#: Every producer with a declared cadence, its artifact, and the command that refreshes it.
#: A producer absent from this table is a producer nothing can notice going quiet, so adding a
#: leg to the hourly cycle without adding it here is itself a defect the fence catches.
CADENCE: tuple[tuple[str, str, int, str], ...] = (
    ("edge_search", "desks/mt5/data/hypotheses/edge_search_results.json", 3600,
     "research/edge_search.py"),
    ("orthogonal_sweep", "desks/mt5/data/hypotheses/orthogonal_candidates.json", 3600,
     "research/orthogonal_sweep.py"),
    ("shadow_health", "desks/mt5/reports/shadow/shadow_health.json", 3600, None),
    ("build_dashboard", "web/desk_state.json", 3600, "scripts/build_zentech_state.py"),
    ("opportunity_gap", "desks/mt5/reports/OPPORTUNITY_GAP.json", 3600,
     "research/opportunity_gap.py"),
    ("adversary_canaries", "desks/mt5/reports/ADVERSARY.json", 3600, "research/adversary.py"),
    ("market_intelligence", "desks/mt5/reports/MARKET_INTELLIGENCE.json", 3600,
     "research/market_intelligence.py"),
    ("model_zoo", "desks/mt5/reports/MODEL_ZOO.json", 3600, "research/model_zoo.py"),
    ("forecast_contract", "desks/mt5/reports/FORECAST_CONTRACT.json", 3600,
     "research/forecast_contract.py"),
    ("experiment_design", "desks/mt5/reports/EXPERIMENT_DESIGN.json", 3600,
     "research/experiment_design.py"),
    ("edge_confidence", "desks/mt5/reports/EDGE_CONFIDENCE.json", 3600,
     "research/edge_confidence.py"),
    ("miner_conversion", "data/miner_conversion.json", 86400,
     "scripts/check_miner_conversion.py"),
    ("ceiling_audit", "desks/mt5/reports/ABSOLUTE_CEILING_STATUS.json", 86400,
     "scripts/check_absolute_ceiling.py"),
)

#: Alarm files any detector on this tree may raise. Presence IS the issue; the file's first line
#: carries the reason. Collected rather than re-derived, so a detector stays the single authority
#: on its own subject.
ALARMS: tuple[tuple[str, str, str], ...] = (
    ("CANARY_ALARM.txt", "CAPITAL",
     "a poison canary was ACCEPTED -- a gate has stopped gating and every certificate issued "
     "since is suspect"),
    ("AUTHORITY_ALARM.txt", "CAPITAL", "capital authority is in an unexpected state"),
    ("MINER_YIELD_ALARM.txt", "DEGRADED", "miners are producing rows and no survivors"),
    ("JOB_MANIFEST_ALARM.txt", "STALLED", "the job manifest disagrees with what runs"),
    ("DESK_TASKS_ALARM.txt", "STALLED", "a scheduled desk task is missing or failing"),
    ("SAMEDAY_ALARM.txt", "BLIND", "the same-day pipeline fence is breached"),
    ("FENCE_ALARM.txt", "BLIND", "a standing fence is breached"),
    ("PROMPT_PREFIX_ALARM.txt", "DEGRADED", "the prompt prefix drifted"),
)

#: Repairs that may NEVER be automated, and why. An actuator that can quietly fix one of these
#: is an actuator that can quietly break it.
NEVER_AUTO = {
    "CAPITAL": "touches sizing or authority; a human decides",
    "merge_conflict": "two histories disagree about live trading code; picking a winner nobody "
                      "chose is the one thing a fixer may not do",
    "gate_threshold": "loosening a gate to clear an alarm is how a desk stops measuring",
}


@dataclass(frozen=True)
class Issue:
    """One problem, its consequence, and what would close it."""

    key: str
    severity: str
    what: str
    detail: str
    repair: str | None = None
    auto: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {"key": self.key, "severity": self.severity, "what": self.what,
                "detail": self.detail, "repair": self.repair, "auto_repairable": self.auto}


def _age(p: Path) -> float | None:
    try:
        return max(0.0, datetime.now(UTC).timestamp() - p.stat().st_mtime)
    except OSError:
        return None


def stale_producers(root: Path | None = None) -> list[Issue]:
    """THE GENERALISATION OF THE EDGE-SEARCH BUG.

    Every producer declares a cadence. An artifact older than TOLERANCE x that cadence is an
    issue with a known repair, whether or not anyone thought to watch that particular leg. A
    MISSING artifact is worse than a stale one and is graded so: stale means the producer ran and
    stopped, missing means it may never have run at all.
    """
    r = root or ROOT
    out: list[Issue] = []
    for name, rel, cadence, producer in CADENCE:
        age = _age(r / rel)
        repair = f"python {producer}" if producer else None
        if age is None:
            out.append(Issue(
                f"missing:{name}", "STALLED", f"{name} has never produced its artifact",
                f"{rel} does not exist on this host. Missing is worse than stale: a stale "
                f"artifact proves the producer ran once, this proves nothing.",
                repair, auto=bool(producer)))
        elif age > cadence * STALE_TOLERANCE:
            out.append(Issue(
                f"stale:{name}", "STALLED",
                f"{name} is {age / 3600:.1f}h old against a {cadence / 3600:.1f}h cadence",
                f"{rel} has not been rewritten in {age / 3600:.1f}h. Past "
                f"{STALE_TOLERANCE}x the declared cadence that is a pattern, not a hiccup, and "
                f"everything downstream of {name} is running on what it last produced.",
                repair, auto=bool(producer)))
    return out


def raised_alarms(root: Path | None = None) -> list[Issue]:
    """Collect what the existing detectors have already found. Never re-derive their verdict."""
    r = root or ROOT
    out: list[Issue] = []
    for fname, severity, meaning in ALARMS:
        p = r / "data" / fname
        if not p.exists():
            continue
        try:
            first = p.read_text("utf-8", errors="ignore").strip().splitlines()
        except OSError:
            first = []
        out.append(Issue(
            f"alarm:{fname}", severity, meaning,
            " ".join(first[:6])[:400] or f"{fname} is present but empty",
            repair=None if severity == "CAPITAL" else "see the detector that raised it",
            auto=False))
    return out


def desk_state_issues(root: Path | None = None) -> list[Issue]:
    """Issues the published desk state already knows about: box liveness, unrunnables, gap."""
    r = root or ROOT
    out: list[Issue] = []
    try:
        d = json.loads((r / "web" / "desk_state.json").read_text("utf-8"))
    except (OSError, ValueError):
        return [Issue("missing:desk_state", "BLIND", "no published desk state",
                      "web/desk_state.json is absent, so the board cannot see the desk at all",
                      "python scripts/build_zentech_state.py", auto=True)]
    box = (d.get("health") or {}).get("box") or {}
    if box.get("status") in {"LATE", "SILENT"}:
        out.append(Issue(
            "box:not_reporting", "BLIND",
            f"the box is {box['status']}",
            box.get("why", ""), repair=None, auto=False))
    pipe = d.get("pipeline") or {}
    if pipe.get("certificates_unrunnable"):
        out.append(Issue(
            "certs:unrunnable", "DEGRADED",
            f"{pipe['certificates_unrunnable']} certificate(s) cannot be executed",
            pipe.get("unrunnable_reason", ""),
            "python research/survivor_publication.py", auto=True))
    # A CERTIFICATE ACCRUING NOTHING IS THE FUNNEL'S MOST EXPENSIVE SILENT STATE. It passed ten
    # gates, it can be run, and it is gathering no forward evidence -- so it can never mature,
    # never reach capital, and nothing anywhere reports a failure. Gate-failed and unrunnable
    # rows are subtracted first: neither is a work item, and lumping them in is what made the
    # published gap (55 certified vs 19 clocks) look like 36 lost sleeves when two thirds of it
    # was rows that never qualified. NOT auto-repairable: the cause is upstream (publication
    # dropped the params, or the family has no resolvable constructor) and rerunning the forward
    # engine would re-refuse them identically.
    certified, clocks = pipe.get("certified"), pipe.get("forward_clocks")
    if isinstance(certified, int) and isinstance(clocks, int):
        runnable = certified - (pipe.get("certificates_unrunnable") or 0)
        if runnable - clocks > 0:
            out.append(Issue(
                "certs:clockless", "DEGRADED",
                f"{runnable - clocks} runnable certificate(s) are on no forward clock",
                f"{certified} certified, {pipe.get('certificates_unrunnable') or 0} unrunnable, "
                f"{clocks} on a clock -- the remainder passed every gate and is accruing no "
                f"out-of-sample evidence, so it can never mature into capital. Check the "
                f"shadow_forward log for ENROL-GAP lines naming each refusal.",
                repair=None, auto=False))
    # ROWS THAT FAILED A GATE, SITTING IN THE FILE THE DESK CALLS ITS CERTIFICATES. Not a
    # correctness bug now that the census counts the ten-gate verdict, but it IS a standing
    # invitation to the same defect: any future reader that does `len(survivors)` re-publishes
    # gate failures as certificates. Reported so the population is known rather than discovered.
    if pipe.get("certified_gate_failed"):
        out.append(Issue(
            "certs:gate_failed_rows", "DEGRADED",
            f"{pipe['certified_gate_failed']} row(s) in the survivors file failed a gate",
            "They are correctly refused at admission and correctly excluded from `certified`. "
            "They remain in UNIVERSAL_SURVIVORS.json, so any reader taking len(survivors) as a "
            "certificate count will over-report the desk's edge -- which is exactly how the "
            "dashboard came to publish them as certified.",
            repair=None, auto=False))
    gap = None
    with contextlib.suppress(OSError, ValueError):
        gap = json.loads((r / "desks/mt5/reports/OPPORTUNITY_GAP.json").read_text("utf-8"))
    if gap and gap.get("first_binding"):
        out.append(Issue(
            f"gap:{gap['first_binding']}", "DEGRADED",
            f"the binding constraint is {gap['first_binding']}",
            gap.get("next_action", ""), repair=None, auto=False))
    return out


def collect(root: Path | None = None) -> list[Issue]:
    return stale_producers(root) + raised_alarms(root) + desk_state_issues(root)


def repair(issues: list[Issue], apply: bool = False,
           timeout_s: int = 900) -> list[dict[str, Any]]:
    """Run the repairs that are safe to automate. REPORTS what it did, never guesses.

    Only idempotent, cheap, reversible repairs are automated: rerunning a producer, rebuilding a
    view. Anything touching capital, a gate threshold or a merge is refused with its reason --
    an actuator that can quietly fix one of those is an actuator that can quietly break it.
    """
    done: list[dict[str, Any]] = []
    for i in issues:
        if not i.auto or not i.repair:
            done.append({"key": i.key, "action": "REFUSED",
                         "why": NEVER_AUTO.get(i.severity,
                                               "no automated repair is defined for this issue")})
            continue
        if not apply:
            done.append({"key": i.key, "action": "WOULD_RUN", "cmd": i.repair})
            continue
        script = i.repair.replace("python ", "", 1)
        for base in (BASE, ROOT):
            target = base / script
            if target.exists():
                break
        else:
            done.append({"key": i.key, "action": "SCRIPT_MISSING", "cmd": i.repair})
            continue
        try:
            r = subprocess.run([sys.executable, "-u", str(target)], cwd=str(base),
                               capture_output=True, text=True, timeout=timeout_s, check=False)
            done.append({"key": i.key, "action": "RAN", "cmd": i.repair,
                         "exit_code": r.returncode,
                         "tail": (r.stdout or r.stderr or "").strip().splitlines()[-2:]})
        except subprocess.TimeoutExpired:
            done.append({"key": i.key, "action": "TIMEOUT", "cmd": i.repair,
                         "why": f"exceeded {timeout_s}s"})
        except Exception as exc:
            done.append({"key": i.key, "action": "ERROR", "cmd": i.repair,
                         "why": f"{type(exc).__name__}: {exc}"})
    return done


def run(apply: bool = False) -> dict[str, Any]:
    issues = collect()
    by_sev: dict[str, int] = {}
    for i in issues:
        by_sev[i.severity] = by_sev.get(i.severity, 0) + 1
    actions = repair(issues, apply=apply)
    return {
        "measured_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "issues": [i.as_dict() for i in issues],
        "count": len(issues), "by_severity": by_sev,
        "auto_repairable": sum(1 for i in issues if i.auto),
        "actions": actions, "applied": apply,
        "stale_tolerance": STALE_TOLERANCE,
        "watched_producers": len(CADENCE),
        "contract": ("Every producer declares a cadence and an artifact. An artifact older than "
                     f"{STALE_TOLERANCE}x its cadence is an issue with a known repair, whether "
                     "or not anybody thought to watch that leg. That is what catches the NEXT "
                     "leg to stall, which is the only fix worth making after being bitten "
                     "twice."),
        "never_automated": NEVER_AUTO,
    }


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    doc = run(apply="--apply" in args)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    print(f"issue board: {doc['count']} issue(s) {doc['by_severity']} across "
          f"{doc['watched_producers']} watched producer(s)")
    for i in doc["issues"][:20]:
        mark = "AUTO" if i["auto_repairable"] else "----"
        print(f"   [{mark}] {i['severity']:8} {i['what'][:78]}")
    ran = [a for a in doc["actions"] if a["action"] == "RAN"]
    if ran:
        print(f"   repaired {len(ran)}: "
              + ", ".join(f"{a['key']}(exit {a['exit_code']})" for a in ran[:6]))
    elif doc["applied"]:
        print("   nothing auto-repairable this pass")
    return 1 if any(i["severity"] == "CAPITAL" for i in doc["issues"]) else 0


if __name__ == "__main__":
    sys.exit(main())
