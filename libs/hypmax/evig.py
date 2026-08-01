"""EVIG -- Expected Validated Information Gain. What the funnel ranks by, instead of volume.

GPT'S OWN TOP CORRECTION, and it is the right one: "Don't optimize for hypotheses/day. Optimize
for Expected Validated Information Gain. One brilliant hypothesis worth 100 mediocre ones should
consume the compute."

Without a ranking function, a funnel that produces 20,000 ideas/day hands L4 whatever happens to
survive the filters, in arrival order. The filters answer "is this hopeless?"; nothing answers
"of the survivors, which deserves the compute FIRST?" -- and L4 capacity is the scarcest thing
the desk has. Volume without prioritisation just moves the bottleneck rather than relieving it.

    EVIG = P(validate) x information_gain x moat_advantage / cost

FOUR TERMS, and each is scored from something the desk has MEASURED rather than from theory:

  P(validate)      the desk's own base rate, conditioned on what it knows. Its measured prior is
                   brutal -- 420 tested, 0 survived -- so the absolute number is small and the
                   term earns its keep through RELATIVE differences: a mechanism class with
                   historical survival beats one with a family kill against it.

  information_gain what the desk LEARNS from the test regardless of outcome. This is the term
                   people omit, and omitting it is why research programmes drift toward safe
                   restatements of what already works: a hypothesis certain to confirm the
                   deployed edge has near-zero information gain even at high P(validate).
                   Maximised at P=0.5 -- a coin-flip question teaches the most.

  moat_advantage   the desk's replication-difficulty score for the data the test needs. Its own
                   ranking puts owned order-book data at 1.03 and the next source at 0.37, so a
                   hypothesis testable ONLY on data nobody else has is worth several testable on
                   public feeds -- both because the edge persists and because a competitor cannot
                   follow.

  cost             L4 compute plus data acquisition. Denominator, so cheap tests of equal merit
                   rank first and the funnel drains its queue faster.

WHY MULTIPLICATIVE. Any term at zero should zero the score: a hypothesis that cannot validate, or
teaches nothing, or needs data the desk cannot get, is worth nothing however good the rest looks.
An additive score would let a strong moat term rescue a hypothesis with no chance of validating,
which is exactly the trade that fills L4 with expensive nothing.

ZERO PROMOTION AUTHORITY. EVIG orders a queue. It never decides what passes -- L4 does that, on
evidence, and a high EVIG buys a candidate nothing except its place in line.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

__all__ = ["EVIG_FLOOR", "EvigScore", "evig", "information_gain", "rank_by_evig"]

#: Below this the candidate is not worth L4 compute TODAY -- it is not rejected, it is deferred,
#: and it re-enters the ranking free of charge the moment any input changes (a new dataset lands,
#: a mechanism class gets its first survivor, a cost model improves). A deferred hypothesis is
#: still alive; the desk's own law is that negative knowledge is reversible.
EVIG_FLOOR = 0.01


def information_gain(p_validate: float) -> float:
    """Binary entropy of the outcome, in bits: what the desk learns by RUNNING the test.

    Peaks at p=0.5 and falls to zero at both extremes, which is the whole point. A hypothesis
    certain to fail teaches nothing; so does one certain to succeed -- and the second is the
    seductive one, because it looks like productivity. This term is what stops a research
    programme drifting into safe restatements of the edge it already has.
    """
    p = min(max(float(p_validate), 1e-9), 1.0 - 1e-9)
    return -(p * math.log2(p) + (1 - p) * math.log2(1 - p))


@dataclass(frozen=True)
class EvigScore:
    evig: float
    p_validate: float
    info_gain: float
    moat: float
    cost: float
    worth_compute: bool
    note: str = ""


def evig(*, p_validate: float, moat_advantage: float, cost: float = 1.0,
         floor: float = EVIG_FLOOR) -> EvigScore:
    """Expected validated information gain per unit of compute.

    `cost` is relative, not currency: 1.0 is a routine L4 run, 5.0 something five times as
    expensive. Absolute units would go stale the first time compute prices moved -- a fossilised
    budget figure, which is a named failure mode here.
    """
    p = min(max(float(p_validate), 0.0), 1.0)
    moat = max(0.0, float(moat_advantage))
    c = max(1e-6, float(cost))
    ig = information_gain(p)
    score = (p * ig * moat) / c
    note = ""
    if p <= 0.0:
        note = "P(validate)=0 -- multiplicative by design: no term can rescue a dead hypothesis"
    elif moat <= 0.0:
        note = "no data advantage -- testable by anyone, so any edge found is already priced"
    elif score < floor:
        note = (f"below the compute floor ({score:.4f} < {floor}) -- DEFERRED, not rejected; "
                "re-enters free when any input changes")
    return EvigScore(round(score, 6), round(p, 4), round(ig, 4), round(moat, 4), round(c, 4),
                     score >= floor, note)


#: Inputs that must be present for a candidate to be SCORED rather than merely listed.
_REQUIRED = ("p_validate", "moat_advantage")


def rank_by_evig(candidates: list[dict], *, floor: float = EVIG_FLOOR) -> list[dict]:
    """Order SCORED survivors by EVIG, then list unscored ones separately. Never mixed.

    UNSCORED CANDIDATES ARE NOT GIVEN NEUTRAL PRIORS, and the first version of this function did
    exactly that -- p=0.5, moat=0.5 -- which scored an unassessed hypothesis at 0.25 while a real
    moat candidate with a measured P(validate) of 0.20 scored 0.149. Ignorance outranked evidence,
    so the funnel would have spent its scarcest resource on whatever nobody had got round to
    looking at. Caught by this module's own demo on the first run.

    Scoring them pessimistically instead would be the mirror error: the desk's measured base rate
    is 0 survivors in 420, so an honest default prior buries every unscored candidate permanently,
    and a ranking that buries things IS a filter -- which this has no authority to be.

    So they are neither flattered nor buried. Unscored candidates are returned AFTER the scored
    ones with `evig_scored: False`, which says the true thing: you cannot compare a measured
    candidate to an unmeasured one on the same axis, and the fix is to measure it.
    """
    scored, unscored = [], []
    for c in candidates:
        if not all(k in c for k in _REQUIRED):
            d = dict(c)
            d["evig_scored"] = False
            d["evig_note"] = (
                f"unscored -- needs {', '.join(k for k in _REQUIRED if k not in c)}. Not ranked "
                "against measured candidates: neutral priors would let ignorance jump the queue, "
                "and the desk's true base rate (0/420) would bury it permanently.")
            unscored.append(d)
            continue
        s = evig(p_validate=float(c["p_validate"]),
                 moat_advantage=float(c["moat_advantage"]),
                 cost=float(c.get("cost", 1.0)), floor=floor)
        d = dict(c)
        d["evig"] = s.evig
        d["evig_scored"] = True
        d["evig_terms"] = {"p_validate": s.p_validate, "info_gain": s.info_gain,
                           "moat": s.moat, "cost": s.cost}
        d["worth_compute"] = s.worth_compute
        if s.note:
            d["evig_note"] = s.note
        scored.append(d)
    return sorted(scored, key=lambda d: -d["evig"]) + unscored
