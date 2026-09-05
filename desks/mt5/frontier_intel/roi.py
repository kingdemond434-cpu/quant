"""FRONTIER ROI: which external capability deserves replication effort, and which is theatre.

    Priority_j = V_j / (Engineering + Compute + Data + ComplexityRent + OperationalRisk)
    V_j        = P(success) x [E(dElog) + EVSI] x Breadth x Persistence x Novelty x Evidence

WHAT THIS FUNCTION IS ACTUALLY FOR, and it is not ranking. Ranking is the easy half. The hard half
is REFUSING, and a frontier miner that cannot refuse will bury this desk in sophisticated modules
that measurably do nothing -- the failure the mandate calls implementation theatre and the desk
has already lived once, as 27 decision-affecting organs no rent line could price.

So three of the six factors exist only to say no:

  COMPLEXITY RENT   every capability costs CPU, memory, latency, maintenance and failure surface
                    for as long as it exists. A gross gain of 0.0001 log-wealth/day that adds a
                    daily failure mode is a LOSS, and netting it here is what stops the repo
                    becoming a museum. Charged BEFORE priority, not after measurement, because
                    after measurement the code is already in.
  SMALL-CAPITAL     a capability designed to move USD 100bn is not automatically valuable at this
                    desk's size, and is sometimes negatively valuable: market-impact machinery for
                    orders that have no impact is pure complexity rent. Capabilities that exploit
                    TINY capacity get a bonus instead, because that is the desk's actual edge.
  EVIDENCE          the grade weight from `registry`. It orders attention and never the verdict.

AND ONE THAT EXISTS TO SAY YES WHEN THE NUMBER CANNOT. `EVSI` -- expected value of the information
produced by learning whether the thing works -- is why a capability whose dElog is UNMEASURABLE
today can still be worth building. Without it the ranking would only ever fund what is already
measurable, which is the definition of a system that cannot learn anything new.

UNMEASURED IS A VERDICT, NOT A ZERO. Where direct dElog cannot be estimated the card carries an
intermediate metric -- information gain, research velocity, breadth -- and says which one. A
capability scored on research velocity is honestly labelled as such, and the mapping from research
improvement to eventual dElog is itself something the desk learns rather than assumes.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from . import ontology, registry

#: The intermediate metrics a card may be scored on when direct dE[log W] is not yet measurable.
#: NAMED, so a reader can never mistake a research-velocity score for a wealth measurement.
INTERMEDIATE = ("information_gain", "research_velocity", "breadth_gain", "execution_gain",
                "reliability_gain")

#: Cost dimensions. `complexity` and `operational_risk` are the two that make this a refusal
#: function rather than a wish list, and they are charged in the SAME denominator as engineering
#: hours so that a cheap-to-write, expensive-to-own capability cannot look free.
COST_DIMENSIONS = ("engineering", "compute", "data", "complexity", "operational_risk")

#: Below this priority a candidate is REFUSED rather than queued. Not a tuning knob: a queue that
#: admits everything is a backlog, and a backlog is how the highest-value gap gets lost among four
#: hundred plausible ones. Set so a candidate must clear roughly "a day of work for a measurable
#: gain, or a week for a large one" -- anything cheaper than that does not need a queue.
MIN_PRIORITY = 0.01

#: Capital the desk actually runs, in the units `capacity_floor` is expressed in. A capability
#: whose minimum useful capacity exceeds this is not for us at any priority.
DESK_CAPITAL_USD = 10_000.0


@dataclass
class Candidate:
    """One frontier capability being considered for replication."""

    frontier_id: str
    firm: str
    capability: str
    evidence_grade: str
    #: MISSING | PARTIAL | COMPLETE | SUPERIOR -- our position against the public observation.
    gap: str
    #: Direct expected dE[log W] per day, or None when it cannot be estimated yet.
    expected_delta_elog: float | None = None
    #: When direct dElog is None, which intermediate metric this is scored on and its size.
    intermediate: str = ""
    intermediate_value: float = 0.0
    #: P(this replicates here at all), in [0, 1]. The single most abused number in any such
    #: formula, so it is required rather than defaulted: a candidate with no stated probability
    #: of success has not been thought about.
    p_success: float = 0.0
    #: Expected value of learning whether it works, in the same units as `expected_delta_elog`.
    evsi: float = 0.0
    #: How broadly it improves the desk: 1.0 = one sleeve, 3.0 = every lane.
    breadth: float = 1.0
    #: How long the gain is expected to persist, in years. A one-quarter edge is worth less than
    #: a permanent capability even at the same size.
    persistence_years: float = 1.0
    #: 0 = we already have this, 1 = the desk has never done anything like it.
    novelty: float = 0.5
    #: Minimum capital at which the capability is useful at all, in USD.
    capacity_floor_usd: float = 0.0
    costs: dict[str, float] = field(default_factory=dict)


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def value(c: Candidate) -> tuple[float, str]:
    """V_j, and the sentence explaining which terms produced it.

    THE UNITS ARE dE[log W] PER DAY where `expected_delta_elog` is given, and the intermediate
    metric's own units otherwise -- which is why `basis` comes back with the number. A caller that
    sums the two has made a category error, and the string is what makes that visible.
    """
    grade_w = registry.grade_weight(c.evidence_grade)
    direct = c.expected_delta_elog
    if direct is None:
        if not c.intermediate:
            return 0.0, ("no direct dE[log W] and no intermediate metric named: the candidate has "
                         "not been valued at all, which is different from being valued at zero")
        if c.intermediate not in INTERMEDIATE:
            return 0.0, f"unknown intermediate metric {c.intermediate!r}"
        core = float(c.intermediate_value)
        basis = f"{c.intermediate} (UNMEASURED in dE[log W])"
    else:
        core = float(direct)
        basis = "dE[log W]/day"
    v = (_clamp01(c.p_success) * (core + float(c.evsi))
         * max(c.breadth, 0.0) * max(c.persistence_years, 0.0)
         * _clamp01(c.novelty) * grade_w)
    return v, (f"P={_clamp01(c.p_success):.2f} x ({core:.3e}+EVSI {c.evsi:.3e}) x breadth "
               f"{c.breadth:.1f} x persist {c.persistence_years:.1f}y x novelty "
               f"{_clamp01(c.novelty):.2f} x grade {c.evidence_grade} ({grade_w:.2f}) "
               f"-- basis {basis}")


def complexity_rent(c: Candidate) -> float:
    """What owning this costs for ever, whether or not it works.

    Charged in the denominator rather than subtracted from the gain, and the difference matters: a
    capability with zero measured benefit and real ongoing cost then scores zero rather than
    negative, so it is REFUSED rather than ranked last -- and a refused candidate does not come
    back the next time the queue is short.
    """
    return sum(max(float(c.costs.get(k, 0.0)), 0.0)
               for k in ("complexity", "operational_risk"))


def capital_fit(c: Candidate) -> tuple[float, str]:
    """Multiplier for whether this capability is useful AT OUR SIZE.

    Three regimes, and the middle one is the point of the whole function: a capability needing
    more capital than the desk has is worthless here however elite its source, and a capability
    that only works at small size is worth MORE here than at the firm it was observed at. That
    asymmetry is the desk's structural advantage and a scorer that ignored it would systematically
    prefer the things this desk is worst placed to exploit.
    """
    floor = float(c.capacity_floor_usd or 0.0)
    if floor > DESK_CAPITAL_USD:
        return 0.0, (f"needs at least ${floor:,.0f} to be useful and the desk runs "
                     f"${DESK_CAPITAL_USD:,.0f}: not for us at any priority")
    if floor <= 0.0 and c.capability in ("CAPACITY", "MARKET_IMPACT"):
        return 0.5, ("capacity and impact machinery is worth less at a size that has no impact; "
                     "kept above zero because knowing our own capacity still bounds sizing")
    if 0.0 < floor <= DESK_CAPITAL_USD * 0.1:
        return 1.5, ("exploits capacity too small for a large firm to care about -- which is this "
                     "desk's actual structural advantage, so it is worth MORE here")
    return 1.0, "no capacity constraint either way"


def priority(c: Candidate) -> dict[str, Any]:
    """The Frontier ROI, with every term it was built from and an explicit verdict.

    QUEUE | REFUSE, never a bare number. A ranking function that only returns a score leaves the
    refusal to a caller's threshold, and the caller will lower it the first time the queue looks
    empty.
    """
    v, why_v = value(c)
    fit, why_fit = capital_fit(c)
    denom = sum(max(float(c.costs.get(k, 0.0)), 0.0) for k in COST_DIMENSIONS)
    if denom <= 0.0:
        return {"frontier_id": c.frontier_id, "priority": 0.0, "verdict": "REFUSE",
                "why": ("no cost was estimated: a candidate whose cost is unstated scores "
                        "infinitely well, which is how a queue fills with unbounded projects"),
                "value": v, "value_why": why_v, "capital_fit": fit}
    p = (v * fit) / denom
    if not math.isfinite(p):
        p = 0.0
    known = ontology.BY_NAME.get(c.capability)
    return {
        "frontier_id": c.frontier_id, "firm": c.firm, "capability": c.capability,
        "level": known.level if known else "",
        "owner": known.owner if known else "",
        "gap": c.gap,
        "priority": round(p, 8), "value": round(v, 10), "value_why": why_v,
        "capital_fit": fit, "capital_fit_why": why_fit,
        "cost_total": round(denom, 4),
        "complexity_rent": round(complexity_rent(c), 4),
        "basis": ("dE[log W]/day" if c.expected_delta_elog is not None
                  else f"{c.intermediate or 'none'} (UNMEASURED)"),
        "verdict": "QUEUE" if p >= MIN_PRIORITY else "REFUSE",
        "why": ("" if p >= MIN_PRIORITY else
                f"priority {p:.5f} below MIN_PRIORITY {MIN_PRIORITY}: the gain it can be argued "
                f"for does not cover what owning it costs. Refused rather than ranked last, so a "
                f"short queue cannot resurrect it"),
    }


def rank(cands: list[Candidate]) -> dict[str, Any]:
    """Every candidate scored, queued ones ordered, refused ones kept with their reason."""
    rows = [priority(c) for c in cands]
    queued = sorted((r for r in rows if r["verdict"] == "QUEUE"),
                    key=lambda r: -r["priority"])
    refused = [r for r in rows if r["verdict"] == "REFUSE"]
    unmeasured = [r for r in queued if "UNMEASURED" in r["basis"]]
    return {
        "queued": queued, "refused": refused,
        "n_queued": len(queued), "n_refused": len(refused),
        "n_scored_on_intermediates": len(unmeasured),
        "best": queued[0]["frontier_id"] if queued else "",
        "rule": ("V/(engineering+compute+data+complexity+operational_risk), with complexity and "
                 "operational risk in the DENOMINATOR so a cheap-to-write capability that is "
                 "expensive to own cannot look free"),
    }
