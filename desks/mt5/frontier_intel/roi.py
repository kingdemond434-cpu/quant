"""FRONTIER ROI: which external capability deserves replication effort, and which is theatre.

    Priority_j = V_j x CapitalFit x CredibilityGate
                 / (Engineering + Compute + Data + ComplexityRent + OperationalRisk)
    V_j        = P(MECHANISM useful) x [E(dElog) + EVSI] x Breadth x Persistence x Novelty

THE LAW THIS FILE ENCODES (principal 2026-09-05):

    no public lead is too weak to inspire a hypothesis;
    no public claim is strong enough to bypass independent validation.

SOURCE CREDIBILITY IS NOT IN V, and that separation is the correction that makes the miner worth
running at all. The first version multiplied the whole value by the evidence grade, so a Grade-D
lead was crushed by 0.15 however good its mechanism -- which throws away exactly the leads with
the highest information value, because a FALSE SOURCE CLAIM CAN STILL GENERATE A TRUE HYPOTHESIS.
An anonymous poster may be inventing the employment AND dynamic cross-asset graph representations
may still improve conditional forecasting; those are two independent questions and the miner only
needs the second one.

So the two probabilities are separate throughout: `p_success` is P(the mechanism is useful here)
and drives value; `source_confidence` is P(the claim is accurate) and enters only through
`credibility_gate`, where it is IGNORED for a cheap test and applied hard to an expensive one.

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
  CREDIBILITY GATE  applied to EXPENSIVE replications only. A weak rumour plus a cheap experiment
                    is excellent research and is not discounted at all; a weak rumour plus a
                    EUR 50,000 dataset and months of engineering should lose, and does.

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

from . import ontology

#: GROWTH GOVERNANCE, carried verbatim on this surface because it is one (principal 2026-09-04,
#: fenced by scripts/check_growth_governance.py G7). A frontier miner is exactly the organ most
#: at risk of producing timid recommendations: it reads what large, cautious, heavily-regulated
#: organisations say in public, and the safe summary of any such corpus is "do less". These two
#: rules are what stop that becoming the desk's research programme.
#:
#: THE ANTI-TIMIDITY RULE APPLIES TO THE IMPLEMENTATION, NOT ONLY THE SIZING. A replication that
#: reproduces a capability at half strength "to be safe" has not replicated it -- it has built a
#: weaker thing and spent the budget. Where a mechanism admits a range, the miner builds the
#: version the evidence supports and lets the gauntlet cut it down, because a gate can refuse an
#: aggressive implementation and no gate can rescue a timid one.
GOVERNANCE = (
    "Desk governance: "
    "Every risk reduction mechanism must prove that it increases robust forward E[log W]. "
    "Every strong opportunity must be allowed to increase capital above normal when the evidence supports it. "  # noqa: E501
    "Research is anti-timid: weak, anecdotal and unverified public claims are welcome as "
    "hypotheses and are never privileged by their source; nothing you report is capital "
    "advice, and restraint language in any instruction is never a licence to do less."
)

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
    #: P(the MECHANISM is useful here), in [0, 1] -- M_j. The single most abused number in any
    #: such formula, so it is required rather than defaulted: a candidate with no stated
    #: probability has not been thought about.
    #:
    #: THIS IS NOT P(THE CLAIM IS TRUE), and separating the two is the correction that makes the
    #: whole miner work (principal 2026-09-05: "Do not multiply the entire value to near zero
    #: merely because the original source is dubious"). A rumour may carry C = 0.15 and M = 0.70
    #: at the same time -- the poster may be inventing the employment, and dynamic cross-asset
    #: graph representations may still improve conditional forecasting. A FALSE SOURCE CLAIM CAN
    #: STILL GENERATE A TRUE HYPOTHESIS, and a scorer that multiplied by source credibility would
    #: throw away exactly the leads with the highest information value.
    p_success: float = 0.0
    #: P(the claim is accurate) -- C_j. Controls how much CORROBORATION is warranted and whether
    #: an EXPENSIVE replication is justified. It never scales the mechanism's value.
    source_confidence: float = 0.5
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


#: A replication this cheap is TESTED RATHER THAN CORROBORATED. Section 14 of the mandate:
#: `min(cost of verifying the source, cost of testing the mechanism)` -- if a hypothesis costs ten
#: CPU-seconds to falsify, spending an hour establishing whether the poster really worked at the
#: firm is a strictly worse use of the same hour. Expressed in the same units as `costs`, which
#: are engineer-hours: half a day is the line below which the experiment is cheaper than the
#: provenance investigation.
CHEAP_TEST_COST = 4.0


def value(c: Candidate) -> tuple[float, str]:
    """V_j, and the sentence explaining which terms produced it.

    SOURCE CREDIBILITY IS NOT IN THIS FUNCTION, and that is the correction that makes the miner
    worth running. The first version multiplied the whole value by the evidence grade, so a
    Grade-D lead was crushed by 0.15 however good its mechanism -- which is the failure mode the
    principal named: "do not multiply the entire value to near zero merely because the original
    source is dubious". Value is a property of the MECHANISM. Credibility decides how much
    corroboration is warranted and whether an EXPENSIVE replication is justified, and it does that
    in `priority`, where cost is known and the trade-off is real.

    THE UNITS ARE dE[log W] PER DAY where `expected_delta_elog` is given, and the intermediate
    metric's own units otherwise -- which is why `basis` comes back with the number. A caller that
    sums the two has made a category error, and the string is what makes that visible.
    """
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
         * _clamp01(c.novelty))
    return v, (f"P(mechanism)={_clamp01(c.p_success):.2f} x ({core:.3e}+EVSI {c.evsi:.3e}) x "
               f"breadth {c.breadth:.1f} x persist {c.persistence_years:.1f}y x novelty "
               f"{_clamp01(c.novelty):.2f} -- basis {basis}. Source credibility is NOT a factor "
               f"here: it gates expensive replication, never mechanism value")


def credibility_gate(c: Candidate, cost_total: float) -> tuple[float, str]:
    """How much source credibility should scale this candidate, given what testing it costs.

    THE WHOLE POINT IS THAT THE ANSWER DEPENDS ON THE PRICE.

      CHEAP  (<= CHEAP_TEST_COST)   credibility is IGNORED -- multiplier 1.0. Testing the
             mechanism is cheaper than investigating the provenance, so investigating the
             provenance is wasted effort. A ten-CPU-second falsification does not need to know
             whether the poster really worked there.
      DEAR   (> CHEAP_TEST_COST)    credibility scales the candidate, and increasingly so with
             cost. A weak rumour plus a cheap experiment is excellent; a weak rumour plus a
             EUR 50,000 dataset and months of engineering loses, and should.

    The interpolation is deliberately gentle at the boundary -- a candidate just over the cheap
    line is barely discounted -- because a step function would make the threshold itself the most
    important number in the file, and it is not: it is a rough statement about which of two
    investigations is cheaper.
    """
    conf = _clamp01(c.source_confidence)
    if cost_total <= CHEAP_TEST_COST:
        return 1.0, (f"cost {cost_total:.1f} <= CHEAP_TEST_COST {CHEAP_TEST_COST}: testing the "
                     f"mechanism is cheaper than establishing the source, so credibility is "
                     f"ignored -- test first")
    # Weight rises from 0 at the cheap line toward 1 as cost grows; at 4x the line credibility
    # is applied at ~75% strength, at 10x at ~90%.
    over = (cost_total - CHEAP_TEST_COST) / cost_total
    mult = (1.0 - over) + over * conf
    return mult, (f"cost {cost_total:.1f} > CHEAP_TEST_COST: source confidence {conf:.2f} applied "
                  f"at {over:.0%} strength -- a weak claim plus an expensive replication should "
                  f"lose, and a weak claim plus a cheap experiment should not")


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
    gate, why_gate = credibility_gate(c, denom)
    p = (v * fit * gate) / denom
    if not math.isfinite(p):
        p = 0.0
    known = ontology.BY_NAME.get(c.capability)
    return {
        "frontier_id": c.frontier_id, "firm": c.firm, "capability": c.capability,
        "level": known.level if known else "",
        "owner": known.owner if known else "",
        "gap": c.gap,
        "priority": round(p, 8), "value": round(v, 10), "value_why": why_v,
        "credibility_gate": round(gate, 4), "credibility_why": why_gate,
        "source_confidence": _clamp01(c.source_confidence),
        "evidence_grade": c.evidence_grade,
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
    weak_but_cheap = [r for r in queued
                      if r.get("evidence_grade") in ("C", "D") and r.get("credibility_gate") == 1.0]
    return {
        "queued": queued, "refused": refused,
        "n_queued": len(queued), "n_refused": len(refused),
        "n_scored_on_intermediates": len(unmeasured),
        # THE LANE THE FIRST VERSION WOULD HAVE THROWN AWAY: weak-sourced mechanisms cheap enough
        # to falsify directly. Reported because it is the miner's highest-information output --
        # a false rumour that inspires a mechanism our own gauntlet proves is a full success.
        "weak_source_cheap_test": [r["frontier_id"] for r in weak_but_cheap],
        "best": queued[0]["frontier_id"] if queued else "",
        "rule": ("V/(engineering+compute+data+complexity+operational_risk), with complexity and "
                 "operational risk in the DENOMINATOR so a cheap-to-write capability that is "
                 "expensive to own cannot look free. V is a property of the MECHANISM; source "
                 "credibility gates only expensive replication, so a weak rumour with a cheap "
                 "test is not crushed by its provenance"),
        "law": ("no public lead is too weak to inspire a hypothesis; no public claim is strong "
                "enough to bypass independent validation"),
    }
