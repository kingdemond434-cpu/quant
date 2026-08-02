#!/usr/bin/env python3
"""THE ALLOCATOR -- and, today, mostly a measurement of how little can be allocated.

WHY THIS EXISTS. libs/doctrine/allocate.py, estimate.py and portfolio_law.py landed with full test
suites and no caller. That is the "built but never runs" class this desk keeps finding in itself,
and a governing layer nothing calls governs nothing: the constitution says every subsystem
optimises dÊ[log W]/dx_i, and until something actually computes those derivatives that sentence is
decoration.

WHAT IT REFUSES TO DO. The desk currently has 0 registered alphas, 0 trials, 0 fills and 0 rows of
alpha performance. There is no honest ΔÊ[log W] for any subsystem, and the tempting move -- assign
plausible-looking priors so the allocator "works" -- would produce a confident ranking built
entirely out of my own guesses, dressed in the vocabulary of measurement. That is worse than no
allocator, because a ranking gets acted on.

SO THE OUTPUT IS THE INSTRUMENTATION GAP ITSELF, which is exactly what P11 mandates: where evidence
is insufficient the verdict is INSUFFICIENT-EVIDENCE and the action is to instrument, not to
decide. Every subsystem in the constitution is listed with the artifact that WOULD carry its
contribution estimate and whether that artifact exists yet. The count of uninstrumented subsystems
is the desk's real bottleneck today -- you cannot route the marginal resource to the largest
derivative when no derivative has ever been computed.

WHAT IT DOES DO. Any subsystem that IS instrumented goes through the real machinery:
`Estimate` -> `allocate()` -> VIP ordering, starvation ledger, idle-capacity failure. So the day
the first contribution estimate lands, the allocator is already running and already correct,
rather than being written six weeks later against a codebase that moved.

MAX CADENCE. Every cycle, seconds, no network, no promotion authority.
"""
from __future__ import annotations

import contextlib
import json
import sqlite3
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.doctrine.allocate import (  # noqa: E402
    Action,
    Ledger,
    allocate,
    bottleneck_expansion,
    meta_learning_rate,
)
from libs.doctrine.constitution import SUBSYSTEM_DERIVATIVES  # noqa: E402
from libs.doctrine.estimate import Estimate, retirement_verdict  # noqa: E402

OUT = ROOT / "data/allocator.json"
LEDGER = ROOT / "data/allocator_ledger.json"
CHASE = ROOT / "data/instrumentation_chase.json"
HISTORY = ROOT / "data/instrumentation_coverage.jsonl"
METRICS = ROOT / "data/desk_metrics.sqlite"

#: subsystem -> (artifact that would carry its contribution estimate, what has to be in it).
#: THIS MAP IS THE DELIVERABLE. "Instrument it" is useless advice without naming the artifact; a
#: subsystem that cannot be told WHERE to write its number will not write one. Every entry here is
#: a concrete, buildable thing, and the ones already producing an artifact are marked live below.
_INSTRUMENTS: dict[str, tuple[str, str]] = {
    "research/generation": ("data/hypothesis_queue.jsonl",
                            "hypotheses generated per cycle, and what fraction reached L4"),
    "research/screening": ("data/gauntlet_calibration.json",
                           "detection floor and false-positive rate of the live screen"),
    "research/mining": ("data/moat_mine.json",
                        "cumulative moat coverage %, and holes remaining"),
    "research/features": ("data/ancestors.json",
                          "feature candidates kept vs composed, moat-derived share"),
    "research/knowledge-graph": ("data/research_cio.json",
                                 "entropy reduction over the desk's own search space"),
    "research/data-mining": ("data/breadth_expansion.jsonl",
                             "new sources admitted, weighted by replication cost"),
    "validation": ("data/gauntlet_calibration.json",
                   "P(true edge | passed), measured against planted truth"),
    "risk/allocation": ("data/portfolio_risk.json",
                        "realised vs growth-optimal sizing gap"),
    "portfolio": ("desk_metrics:alpha_performance",
                  "MC_i per sleeve -- E[log W | S] minus E[log W | S without i]"),
    "execution": ("desk_metrics:fills",
                  "theoretical vs realised edge per fill: the X term"),
    "costs": ("desk_metrics:fills",
              "fees, funding, borrow and slippage as a fraction of gross edge"),
    "capacity": ("data/slot_budget_analysis.json",
                 "size at which each edge stops existing"),
    "survival": ("data/portfolio_risk.json",
                 "P(still compounding at T) under the current book"),
    "llm/panel": ("data/external_panel_log.jsonl",
                  "novelty harvested per push round, per seat"),
    "engineering": ("docs/GAP_REGISTER.md",
                    "gaps closed per engineer-day, weighted by the derivative each unblocks"),
    "infrastructure": ("data/panel_budget_state.json",
                       "observed cost per unit of research throughput"),
    "memory": ("desk_metrics:research_memory",
               "duplicate research avoided -- work not repeated"),
    "scheduler": ("data/cadence_state.json",
                  "compute cycles used vs available, and what went unrun"),
    "governance": ("data/max_audit_report.json",
                   "defects caught per governance hour, and throughput unblocked"),
    "meta/self-improvement": ("data/gauntlet_calibration_history.jsonl",
                              "d/dt of the detection floor -- the rate the desk improves"),
}


def _exists(artifact: str) -> bool:
    """Does the artifact that would carry this subsystem's estimate exist AND hold rows?

    EXISTENCE IS NOT ENOUGH and this is the distinction that matters. An empty table and a missing
    table are the same fact for this purpose: no contribution can be computed from either. The
    desk has learned this shape repeatedly -- a file present, a process exiting clean, and nothing
    produced all read as success to anything that only checks for the file.
    """
    if artifact.startswith("desk_metrics:"):
        table = artifact.split(":", 1)[1]
        if not METRICS.exists():
            return False
        try:
            with sqlite3.connect(f"file:{METRICS}?mode=ro", uri=True) as c:
                return bool(c.execute(f"select count(*) from {table}").fetchone()[0])
        except sqlite3.Error:
            return False
    p = ROOT / artifact
    try:
        return p.exists() and p.stat().st_size > 2
    except OSError:
        return False


#: How many cycles an instrumentation gap may stand before it is promoted ahead of everything
#: else. Same discipline as the starvation rule it borrows from: priority decides ORDER, never
#: entitlement, and a gap that is always ranked fifth is being permanently neglected by a rule
#: that believes it is merely ordering.
CHASE_STARVATION_CYCLES = 3

#: Cost model for closing an instrumentation gap, in the only units available today that are
#: MEASURED rather than guessed: does an organ already write this artifact, and does that organ
#: already run every cycle? Ranking by 1/cost is the constitution's own density rule
#: (dE[log W]/dR) applied to the one resource that is actually binding here -- engineering time.
_COST_ORGAN_RUNS = 1.0       # organ exists and runs at cadence: add the estimate, nothing else
_COST_ORGAN_IDLE = 3.0       # organ exists but never runs: wire it, then add the estimate
_COST_NO_ORGAN = 8.0         # nothing writes this at all: build the organ first


def _writers(artifact: str) -> list[str]:
    """Scripts that reference this artifact path. Measured from the repo, never assumed."""
    needle = (artifact.split(":", 1)[1] if artifact.startswith("desk_metrics:") else artifact)
    out = []
    for f in sorted((ROOT / "scripts").glob("*.py")):
        if f.name == "run_allocator.py":
            continue                      # this file names every artifact; it writes none of them
        try:
            if needle in f.read_text("utf-8", errors="ignore"):
                out.append(f.name)
        except OSError:
            continue
    return out


def _closure_cost(artifact: str, cadence_src: str) -> tuple[float, str]:
    """(cost, why). Cheapest gaps first -- that IS the density rule, not impatience.

    A gap whose organ already runs every cycle needs one number added to an existing artifact; a
    gap with no organ at all needs an organ designed, built, tested and wired. Treating those as
    equally urgent is how an instrumentation programme stalls on its hardest item while eight
    one-line wins sit untouched.
    """
    writers = _writers(artifact)
    if not writers:
        return _COST_NO_ORGAN, "no script writes this artifact -- an organ has to be built first"
    running = [w for w in writers if f"scripts/{w}" in cadence_src]
    if running:
        return _COST_ORGAN_RUNS, (
            f"{running[0]} is already scheduled and writes this -- the gap is one estimate, "
            "not an organ")
    return _COST_ORGAN_IDLE, (
        f"{writers[0]} writes this but is NOT wired into the cadence -- wire it, then add the "
        "estimate")


def _load_chase() -> dict[str, int]:
    """Cycles each gap has stood open. Persisted, because a gap that is always ranked fifth is
    only visible as neglect across runs -- within any single cycle the ranking looked correct."""
    try:
        d = json.loads(CHASE.read_text("utf-8"))
        return {str(k): int(v) for k, v in d.get("cycles_owed", {}).items()}
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return {}


def _load_ledger() -> Ledger:
    try:
        return Ledger(misses=json.loads(LEDGER.read_text("utf-8")).get("misses", {}))
    except (OSError, json.JSONDecodeError, TypeError):
        return Ledger()


def main() -> int:
    t0 = time.time()

    # EVERY SCHEDULER, NOT JUST THE CADENCE. The desk fires organs from run_cadence.py AND from
    # ops/run_*.sh, so reading only the first mislabels anything the shell runners drive as
    # "never runs" -- and an incorrect cost model sends the chase at the wrong gap first, which is
    # exactly the failure the ranking exists to prevent. Found the first time this ranked
    # max_audit's artifact as unwired while ops/run_cro_ai.sh has been running it all along.
    cadence_src = ""
    with contextlib.suppress(OSError):
        cadence_src = (ROOT / "scripts/run_cadence.py").read_text("utf-8", errors="ignore")
    for sh in sorted((ROOT / "ops").glob("run_*.sh")):
        with contextlib.suppress(OSError):
            cadence_src += sh.read_text("utf-8", errors="ignore")
    chase = _load_chase()

    instrumented: list[str] = []
    uninstrumented: list[dict] = []
    for name in SUBSYSTEM_DERIVATIVES:
        artifact, needs = _INSTRUMENTS.get(name, ("<none declared>", ""))
        if _exists(artifact):
            instrumented.append(name)
            chase.pop(name, None)          # closed gaps leave the chase; they do not linger
            continue
        cost, why = _closure_cost(artifact, cadence_src)
        owed = int(chase.get(name, 0)) + 1
        chase[name] = owed
        # P25, DETECT IMPLIES REPAIR. A gap is not a status: cost-1 means an organ already runs
        # and writes the artifact, so the fix is one estimate and is PATCH_READY with the exact
        # change named. cost-8 means no organ exists, so the fix cannot be written until one is
        # designed -- BLOCKED, with the organ itself as the named next step. Nothing lands in
        # "investigate".
        tier = "PATCH_READY" if cost <= _COST_ORGAN_IDLE else "BLOCKED"
        uninstrumented.append({
            "tier": tier,
            "fix": (f"add the contribution estimate to {artifact} -- {why}"
                    if tier == "PATCH_READY" else
                    f"build the organ that writes {artifact} first; until it exists no estimate "
                    "can be added and no allocation involving this subsystem is real"),
            "subsystem": name,
            "derivative": SUBSYSTEM_DERIVATIVES[name][0],
            "artifact_needed": artifact,
            "must_contain": needs,
            "closure_cost": cost,
            "how": why,
            "cycles_owed": owed,
            "starved": owed >= CHASE_STARVATION_CYCLES,
        })

    # RANKED, NOT LISTED. Cheapest first is the density rule applied to engineering time, and
    # STARVATION OUTRANKS IT: a gap that has stood for CHASE_STARVATION_CYCLES goes to the front
    # regardless of cost, because "always ranked fifth, never once worked" is permanent neglect
    # wearing the costume of prioritisation -- and no single cycle's ranking can see that.
    uninstrumented.sort(key=lambda u: (not u["starved"], u["closure_cost"], u["subsystem"]))

    # No contribution estimates exist yet for ANY subsystem, and none are invented here. Each
    # instrumented subsystem gets an explicitly uninformative Estimate (n=0), which the governing
    # layer's own machinery then classifies as INSUFFICIENT-EVIDENCE rather than as a ranking.
    # That is the point: the same code path that will rank real numbers refuses to rank absent
    # ones, so nobody has to remember which mode it is in.
    verdicts = [retirement_verdict(Estimate(0.0, se=0.0, n=0, label=s)) for s in instrumented]
    unmeasured = [v for v in verdicts if v["verdict"] == "INSUFFICIENT-EVIDENCE"]

    actions: list[Action] = []          # deliberately empty: no measured contribution exists
    ledger = _load_ledger()
    alloc = allocate(actions, budget=0.0, ledger=ledger)
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps({"misses": ledger.misses}, indent=1), "utf-8")

    # Discovery vs conversion, from what IS measurable: the funnel's own artifacts.
    flow = bottleneck_expansion(discovery_rate=0.0, conversion_rate=0.0)

    total = len(SUBSYSTEM_DERIVATIVES)
    coverage_pct = round(100.0 * len(instrumented) / max(1, total), 1)

    # THE RATE, NOT ONLY THE LEVEL (P18). A coverage number that does not move is a gap nobody is
    # chasing, and it looks identical in any single report to a gap being closed slowly. Measured
    # over the recorded history with its own standard error, so "not distinguishable from flat" is
    # a finding about the chase rather than a rounding error.
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    with HISTORY.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"ts": datetime.now(tz=UTC).isoformat(),
                             "coverage_pct": coverage_pct,
                             "instrumented": len(instrumented),
                             "owed": len(uninstrumented)}, separators=(",", ":")) + "\n")
    series: list[float] = []
    with contextlib.suppress(OSError, json.JSONDecodeError):
        series = [float(json.loads(x)["coverage_pct"])
                  for x in HISTORY.read_text("utf-8").strip().splitlines() if x][-60:]
    rate = meta_learning_rate(series)

    CHASE.write_text(json.dumps({
        "_": ("cycles each instrumentation gap has stood open. Never reset except by CLOSING the "
              "gap -- a counter that resets on its own lets permanent neglect look like a fresh "
              "start every cycle."),
        "updated": datetime.now(tz=UTC).isoformat(),
        "cycles_owed": dict(sorted(chase.items())),
    }, indent=1), "utf-8")

    starved = [u for u in uninstrumented if u["starved"]]
    out = {
        "ts": datetime.now(tz=UTC).isoformat(),
        "seconds": round(time.time() - t0, 2),
        "subsystems": total,
        "instrumented": sorted(instrumented),
        "uninstrumented": uninstrumented,
        "coverage_pct": coverage_pct,
        "closure_rate": rate,
        "starved": [u["subsystem"] for u in starved],
        "next_action": (uninstrumented[0] if uninstrumented else None),
        "allocation": alloc,
        "flow": flow,
        "bottleneck": (
            "INSTRUMENTATION" if len(uninstrumented) > total / 2 else
            "CONTRIBUTION ESTIMATES"),
        "verdict": (
            f"{len(uninstrumented)} of {total} subsystems cannot state their contribution to "
            "E[log W] at all -- the artifact that would carry it does not exist or is empty. No "
            "allocation computed here is real, and none is offered: routing the marginal resource "
            "to the largest derivative is impossible when no derivative has ever been computed. "
            "The binding constraint is INSTRUMENTATION, and it outranks every subsystem's request "
            "for resources until it is closed."
            if uninstrumented else
            "every subsystem reports an artifact; the remaining gap is turning those artifacts "
            "into contribution ESTIMATES with standard errors"),
        "why_no_ranking": (
            f"{len(unmeasured)} instrumented subsystem(s) still return INSUFFICIENT-EVIDENCE "
            "(n=0). Assigning plausible priors so the allocator 'works' would produce a confident "
            "ranking made entirely of guesses, wearing the vocabulary of measurement -- worse "
            "than no allocator, because a ranking gets acted on."),
        "next": [u["artifact_needed"] for u in uninstrumented][:8],
        "chase": (
            f"{len(uninstrumented)} gap(s) open, {len(starved)} STARVED "
            f"(>= {CHASE_STARVATION_CYCLES} cycles). Ranked cheapest-first, starvation ahead of "
            "cost. This runs every cycle and the counters never reset except by closing a gap."
            if uninstrumented else "no gap open at this level"),
        # P20, ZERO CEILING. Reaching 100% on this measure is not completion, it is arrival at the
        # next ceiling -- and naming it here is what stops the organ going quiet the day it turns
        # green. "Done" is a status this constitution does not recognise for any component.
        "next_ceiling": (
            "close the remaining artifact gaps" if uninstrumented else
            "every artifact exists -- the next ceiling is turning them into ESTIMATES with "
            "standard errors, then into estimates with enough n to clear MIN_N_FOR_ACTION, then "
            "into a live allocation. Optimisation does not terminate here."),
    }
    OUT.write_text(json.dumps(out, indent=1), "utf-8")

    print(f"allocator: {len(instrumented)}/{total} subsystems instrumented "
          f"({coverage_pct}%) | bottleneck: {out['bottleneck']} | {out['seconds']}s")
    if rate.get("state") == "MEASURED":
        arrow = "closing" if rate["improving"] else "FLAT"
        print(f"  closure rate {rate['rate']:+.2f} pp/cycle ({arrow}, n={rate['n']})")
        if not rate["improving"]:
            print("  THE GAP IS NOT CLOSING. Coverage is not distinguishable from flat over the "
                  "recorded history -- nobody is chasing this, and the constitution does not "
                  "permit a subsystem to sit below its evidence-supported maximum.")
    for u in uninstrumented[:6]:
        mark = "STARVED" if u["starved"] else f"owed x{u['cycles_owed']}"
        print(f"  [{mark:>9}] cost {u['closure_cost']:.0f}  {u['subsystem']:<26} "
              f"-> {u['artifact_needed']}")
        print(f"              {u['how']}")
    if len(uninstrumented) > 6:
        print(f"  ... and {len(uninstrumented) - 6} more (see {OUT.name})")
    print(f"  NEXT CEILING: {out['next_ceiling'][:130]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
