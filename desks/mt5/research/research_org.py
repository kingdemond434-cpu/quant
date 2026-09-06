#!/usr/bin/env python3
"""P53 / P54 / P60 / P62 -- THE RESEARCH ORGANISATION ITSELF.

A desk staffed by agents is still an organisation, and organisations fail in organisational ways
that no amount of statistical rigour inside any single agent will catch.

P54 -- THE ROLES ARE SEPARATE, AND THE SEPARATION IS THE MECHANISM. Four roles, and no agent may
hold two of them on the same claim:

    ADVOCATE    builds the strongest case FOR
    SKEPTIC     builds the strongest case AGAINST, and is scored on finding real problems
    REPLICATOR  re-runs it independently, from the specification rather than the code
    VALIDATOR   rules, and may rule for neither

An advocate who also validates will validate. That is not a character flaw, it is what happens to
anyone asked to grade their own work, and the only reliable fix is structural: the same identity
may not appear twice on one claim. This module REFUSES such a review rather than flagging it,
because a flagged conflict in a busy week is a conflict that ships.

P53 -- REPUTATION IS TRACKED PER AGENT AND IT IS EARNED ON CALIBRATION, NOT ON VOLUME. An agent
that proposes forty candidates and is right about two has a worse record than one that proposes
three and is right about two, and a reputation built on throughput rewards exactly the wrong
behaviour. A skeptic's reputation is separate again: it rises when the problems it raised turn
out to have been real, which is the only way to make skepticism worth doing.

P60 -- FRONTIER OF FRONTIERS: transferable METHODS from adjacent sciences, never their claims.
Sequential testing came from clinical trials; false-discovery control came from genomics;
change-point detection came from quality control. What transfers is the METHOD and its
assumptions; what does not transfer is a finding about a different domain. A method is admitted
only with its assumptions restated in this desk's terms, because a technique borrowed without its
preconditions is a technique applied where it does not hold.

P62 -- THE AUTONOMOUS IMPLEMENTER: gap -> branch -> build -> tests -> canaries -> merge. It may
close a gap the register named, and every step is a GATE rather than a stage: no branch without a
named gap, no build without a branch, no merge without both tests and canaries green. The canary
step is the one that matters -- an implementer that can merge without the poison canaries passing
can silently disable the gates it was built to serve.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
REPORT = BASE / "reports" / "RESEARCH_ORG.json"
LEDGER = BASE / "data" / "agent_reputation.jsonl"

#: The four roles. No identity may hold two of them on the same claim.
ROLES: tuple[str, ...] = ("ADVOCATE", "SKEPTIC", "REPLICATOR", "VALIDATOR")

#: Steps of the autonomous implementer, in order. Each is a GATE, not a stage.
PIPELINE: tuple[str, ...] = ("gap", "branch", "build", "tests", "canaries", "merge")

#: Minimum resolved claims before an agent's reputation is allowed to mean anything. Below it a
#: single lucky call reads as a perfect record.
MIN_CLAIMS_FOR_REPUTATION = 8


@dataclass(frozen=True)
class Review:
    """One claim under review, and who holds which role on it."""

    claim: str
    assignments: dict[str, str] = field(default_factory=dict)   # role -> agent id

    def conflicts(self) -> list[str]:
        """Every violation of role separation. Empty means the review may proceed."""
        out: list[str] = []
        missing = [r for r in ROLES if not self.assignments.get(r)]
        if missing:
            out.append(f"unfilled role(s) {', '.join(missing)} -- a review missing its skeptic "
                       "or its replicator is not a review, it is an endorsement")
        seen: dict[str, list[str]] = {}
        for role, agent in self.assignments.items():
            if agent:
                seen.setdefault(agent, []).append(role)
        for agent, roles in seen.items():
            if len(roles) > 1:
                out.append(f"{agent} holds {' and '.join(sorted(roles))} on the same claim -- "
                           "anyone asked to grade their own work grades it favourably, and the "
                           "only reliable fix is structural")
        return out


def open_review(r: Review) -> dict[str, Any]:
    """REFUSE a conflicted review rather than flagging it.

    A flagged conflict in a busy week is a conflict that ships. The refusal is the mechanism.
    """
    bad = r.conflicts()
    return {"claim": r.claim, "admissible": not bad, "assignments": dict(r.assignments),
            "conflicts": bad,
            "why": ("roles are separate; the review may proceed" if not bad
                    else "REFUSED -- " + "; ".join(bad))}


# --------------------------------------------------------------------------- P53
@dataclass
class Record:
    """One agent's history. Proposals and skeptic calls are scored SEPARATELY."""

    agent: str
    proposed: int = 0
    proposed_correct: int = 0
    objections: int = 0
    objections_upheld: int = 0

    def reputation(self) -> dict[str, Any]:
        """Calibration, never volume.

        An agent that proposes forty candidates and is right about two has a WORSE record than
        one that proposes three and is right about two. A reputation built on throughput rewards
        exactly the wrong behaviour, and on a research desk the wrong behaviour is cheap.
        """
        n = self.proposed + self.objections
        if n < MIN_CLAIMS_FOR_REPUTATION:
            return {"agent": self.agent, "status": "UNRATED", "claims": n,
                    "why": (f"{n} resolved claim(s), below the {MIN_CLAIMS_FOR_REPUTATION} a "
                            "rating needs; a single lucky call would otherwise read as a "
                            "perfect record")}
        prop = (self.proposed_correct / self.proposed) if self.proposed else None
        skep = (self.objections_upheld / self.objections) if self.objections else None
        parts = [p for p in (prop, skep) if p is not None]
        return {
            "agent": self.agent, "status": "RATED", "claims": n,
            "proposal_precision": None if prop is None else round(prop, 3),
            "skeptic_precision": None if skep is None else round(skep, 3),
            "reputation": round(sum(parts) / len(parts), 3) if parts else None,
            "why": ("scored on precision, not throughput: being right about two of three beats "
                    "being right about two of forty, and the second is what a volume metric "
                    "rewards"),
        }


# --------------------------------------------------------------------------- P60
@dataclass(frozen=True)
class Method:
    """A technique borrowed from an adjacent science, with the assumptions it needs HERE."""

    name: str
    origin: str
    transfers: str
    assumptions: tuple[str, ...]
    holds_here: bool
    note: str = ""


TRANSFERABLE: tuple[Method, ...] = (
    Method("sequential_probability_ratio", "clinical trials",
           "stopping a test as soon as the evidence is decisive, without inflating error",
           ("the stopping rule is fixed BEFORE data is seen",
            "observations are exchangeable within the arm"),
           True, "maps onto forward clocks: a sleeve can be stopped early on either side"),
    Method("false_discovery_rate", "genomics",
           "controlling the share of false positives among many simultaneous tests",
           ("the test statistics' dependence structure is known or bounded",
            "the family of tests is declared in advance, not chosen after"),
           True, "the desk tests thousands of candidates; per-test alpha is meaningless here"),
    Method("change_point_detection", "industrial quality control",
           "detecting when a process's parameters shifted, rather than assuming stationarity",
           ("the pre-change distribution is estimable",
            "the cost of a false alarm is stated"),
           True, "regime transition is the same problem under a different name"),
    Method("survival_analysis", "epidemiology",
           "modelling time-to-event with censored observations",
           ("censoring is independent of the outcome",),
           False, "sleeve retirement is NOT independent of performance -- the desk kills losers, "
                  "so censoring is informative and the standard estimator is biased. The method "
                  "is listed as NOT holding rather than omitted, because the reason is the "
                  "interesting part"),
)


def frontier_methods() -> dict[str, Any]:
    """P60. Methods, with their preconditions restated in this desk's terms.

    WHAT TRANSFERS IS THE METHOD AND ITS ASSUMPTIONS. A finding about a different domain does
    not transfer at all, and a technique borrowed without its preconditions is a technique
    applied where it does not hold -- which is worse than not borrowing it, because it arrives
    with borrowed credibility.
    """
    return {
        "methods": [{"name": m.name, "origin": m.origin, "transfers": m.transfers,
                     "assumptions": list(m.assumptions), "holds_here": m.holds_here,
                     "note": m.note} for m in TRANSFERABLE],
        "admitted": [m.name for m in TRANSFERABLE if m.holds_here],
        "refused": [m.name for m in TRANSFERABLE if not m.holds_here],
        "rule": ("A method is admitted only with its assumptions restated in this desk's terms. "
                 "Claims from another domain never transfer; only techniques and their "
                 "preconditions do."),
    }


# --------------------------------------------------------------------------- P62
def implement(gap: str, state: dict[str, bool]) -> dict[str, Any]:
    """P62. Advance a gap through the pipeline. EVERY STEP IS A GATE.

    The canary gate is the one that matters. An implementer that can merge without the poison
    canaries passing can silently disable the very gates it was built to serve -- and it would
    look, from every report, like an unusually productive week.
    """
    if not gap.strip():
        return {"status": "REFUSED", "reached": None,
                "why": "no named gap -- an implementer that may start work nobody asked for is "
                       "an implementer that writes whatever it likes"}
    reached, blocked = [], None
    for step in PIPELINE:
        if step == "gap":
            reached.append(step)
            continue
        if not state.get(step):
            blocked = step
            break
        reached.append(step)
    merged = blocked is None and "merge" in reached
    why = ("all gates green: gap named, branch cut, build clean, tests and CANARIES passing"
           if merged else
           f"stopped at `{blocked}` -- "
           + ("the poison canaries did not all reject, so a gate has stopped gating and merging "
              "now could silently disable the validation this desk runs on"
              if blocked == "canaries" else
              f"`{blocked}` is not green, and every step here is a gate rather than a stage"))
    return {"status": "MERGED" if merged else "BLOCKED", "gap": gap,
            "reached": reached, "blocked_at": blocked, "pipeline": list(PIPELINE), "why": why}


# --------------------------------------------------------------------------- runner
def run() -> dict[str, Any]:
    demo_conflict = open_review(Review("gold scalp is promotable", {
        "ADVOCATE": "agent_a", "SKEPTIC": "agent_b",
        "REPLICATOR": "agent_c", "VALIDATOR": "agent_a"}))
    demo_clean = open_review(Review("gold scalp is promotable", {
        "ADVOCATE": "agent_a", "SKEPTIC": "agent_b",
        "REPLICATOR": "agent_c", "VALIDATOR": "agent_d"}))
    records = [
        Record("volume_proposer", proposed=40, proposed_correct=2),
        Record("careful_proposer", proposed=3, proposed_correct=2, objections=6,
               objections_upheld=5),
        Record("newcomer", proposed=2, proposed_correct=2),
    ]
    return {
        "measured_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "roles": list(ROLES),
        "review_refused_example": demo_conflict,
        "review_admissible_example": demo_clean,
        "reputations": [r.reputation() for r in records],
        "frontier_methods": frontier_methods(),
        "implementer": {
            "blocked_on_canaries": implement("13 certificates unrunnable", {
                "branch": True, "build": True, "tests": True, "canaries": False, "merge": True}),
            "clean": implement("13 certificates unrunnable", {
                "branch": True, "build": True, "tests": True, "canaries": True, "merge": True}),
        },
        "min_claims_for_reputation": MIN_CLAIMS_FOR_REPUTATION,
    }


def main(argv: list[str] | None = None) -> int:
    doc = run()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    print(f"research org: {len(ROLES)} separated roles, "
          f"{len(doc['frontier_methods']['admitted'])} method(s) admitted, "
          f"{len(doc['frontier_methods']['refused'])} refused")
    for r in doc["reputations"]:
        if r["status"] == "RATED":
            print(f"   {r['agent']:20} reputation {r['reputation']}  "
                  f"(proposal {r['proposal_precision']}, skeptic {r['skeptic_precision']})")
        else:
            print(f"   {r['agent']:20} UNRATED -- {r['why'][:66]}")
    print(f"   conflicted review: {doc['review_refused_example']['why'][:88]}")
    print(f"   implementer on red canaries: "
          f"{doc['implementer']['blocked_on_canaries']['status']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
