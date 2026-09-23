"""CROWDING DECAY HAZARD — finding dead alpha before the P&L says so.

BY THE TIME A STRATEGY'S RETURNS CONFIRM IT IS CROWDED, THE MONEY IS ALREADY GONE. A decayed edge
does not announce itself; it produces a run of mediocre months that is statistically
indistinguishable from bad luck until the sample is large enough to be sure, and by then the desk
has funded a year of it. So the question is whether decay can be predicted from the MARKET rather
than from the returns.

It frequently can, because crowding leaves fingerprints on the book before it reaches the P&L::

    the spread compresses          more participants competing to quote the same thing
    the basis and funding compress the carry the trade harvested is being arbitraged away
    the queue lengthens            more orders resting at the same price for the same reason
    fills deteriorate              you are later in every queue than you used to be
    impact rises                   the liquidity that absorbed you is being consumed by others
    the strategy diffuses publicly repos, videos, forks, discussion

**THE LAST ONE IS A HYPOTHESIS, NOT A LAW, AND IS TREATED AS ONE.** "Publication destroys edge" is
widely believed and rarely measured. Some published effects persist for decades; some die before
the paper is printed. `diffusion_pressure` is computed and reported as a candidate feature, and
`hazard` states in its own output that the diffusion term is unvalidated on this desk. Assuming it
would be borrowing a conclusion the desk has not earned.

**THIS IS NOT `libs/alpha_factory/crowding_intelligence.py`.** That module steers RESEARCH away
from concepts that are already crowded -- a question about where to look. This asks whether a
strategy the desk is ALREADY RUNNING is being competed away, which is a question about whether to
keep paying for it. Different input, different consumer, no overlap.

Measures and warns. Retires nothing -- `strategy_pool` and the allocator own that.

**WHO CALLS IT (2026-09-05).** This module was correct and had NO IMPORTER on the desk for as
long as it existed: a leading decay indicator nothing read, which is the same as not having one.
`desks/mt5/research/drift_monitor.crowding` now builds a `CrowdingState` per instrument from the
desk's own book evidence -- the spread rank this pass already forecasts against its long-run
baseline, and the execution twin's realised fill rate and slip against what the simulator
charged -- and `hazard()` becomes the CROWDING channel of the per-sleeve edge hazard written into
reports/DRIFT.json. The 60-observation floor is respected there rather than worked around: below
it this module returns None with its reason and the channel reads UNMEASURED.

The horizon conversion is the caller's, not this module's: `libs.research.perishability` inverts
the probability returned here back through the SAME `rate = pressure / 120` scale declared below,
so the crowding channel weighs exactly what the other eight monitored channels do and does not
silently change weight when the horizon moves.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

__all__ = [
    "MIN_OBSERVATIONS",
    "PRESSURE_SOURCES",
    "CrowdingState",
    "diffusion_pressure",
    "hazard",
    "microstructure_pressure",
    "summarise",
]

#: Where crowding shows up before it shows up in returns. Grouped so the report can say WHICH kind
#: of pressure is rising -- a book-side signal and a publicity signal are very different evidence.
PRESSURE_SOURCES: tuple[str, ...] = (
    "SPREAD_COMPRESSION", "BASIS_COMPRESSION", "FUNDING_COMPRESSION",
    "QUEUE_COMPETITION", "FILL_DETERIORATION", "IMPACT_GROWTH", "PUBLIC_DIFFUSION",
)

#: Below this many paired observations, a trend in any of these is noise with a direction.
MIN_OBSERVATIONS: int = 60


@dataclass(frozen=True)
class CrowdingState:
    """A strategy's competitive environment now against its own baseline.

    Every field is a RATIO to the strategy's own historical normal, not an absolute. A 1bp spread
    is tight for one instrument and enormous for another, and only the change relative to the
    conditions the edge was validated under carries information about competition.
    """

    strategy_id: str
    observations: int = 0
    #: Current / baseline. Below 1.0 means compression, which is the crowding direction.
    spread_ratio: float = 1.0
    basis_ratio: float = 1.0
    funding_ratio: float = 1.0
    #: Current / baseline. ABOVE 1.0 is the crowding direction for these three.
    queue_length_ratio: float = 1.0
    impact_ratio: float = 1.0
    #: Realised fill rate now / at validation. BELOW 1.0 is the crowding direction.
    fill_rate_ratio: float = 1.0
    #: Public diffusion counts over the trailing window against the prior window.
    public_mentions_ratio: float = 1.0
    repo_forks_ratio: float = 1.0
    #: Realised edge now / validated edge. Used only to CHECK the hazard, never to compute it --
    #: a hazard that reads the P&L is a lagging indicator wearing a leading indicator's name.
    realised_edge_ratio: float | None = None

    @property
    def measured(self) -> bool:
        return self.observations >= MIN_OBSERVATIONS


def microstructure_pressure(c: CrowdingState) -> tuple[float | None, dict[str, float], str]:
    """Book-side crowding, 0-1. The evidence the desk can actually stand behind.

    Each component is the fraction of the way from "unchanged" to a fully-competed state, clipped
    to [0,1]. They are averaged rather than multiplied: these are alternative symptoms of the same
    process and any one of them alone is real evidence, so a product would let one unchanged
    component silence five that moved.
    """
    if not c.measured:
        return None, {}, (
            f"{c.strategy_id}: {c.observations} observation(s) against a floor of "
            f"{MIN_OBSERVATIONS}. A trend in any of these over a shorter window is noise with a "
            "direction")
    parts = {
        "SPREAD_COMPRESSION": max(0.0, min(1.0, 1.0 - c.spread_ratio)),
        "BASIS_COMPRESSION": max(0.0, min(1.0, 1.0 - c.basis_ratio)),
        "FUNDING_COMPRESSION": max(0.0, min(1.0, 1.0 - c.funding_ratio)),
        "QUEUE_COMPETITION": max(0.0, min(1.0, c.queue_length_ratio - 1.0)),
        "IMPACT_GROWTH": max(0.0, min(1.0, c.impact_ratio - 1.0)),
        "FILL_DETERIORATION": max(0.0, min(1.0, 1.0 - c.fill_rate_ratio)),
    }
    score = sum(parts.values()) / len(parts)
    leaders = sorted(parts, key=lambda k: -parts[k])[:2]
    return score, parts, (
        f"{c.strategy_id}: book-side crowding {score:.2f}, led by {leaders[0]} "
        f"({parts[leaders[0]]:.2f}) and {leaders[1]} ({parts[leaders[1]]:.2f})")


def diffusion_pressure(c: CrowdingState) -> tuple[float, str]:
    """Public diffusion, 0-1. A CANDIDATE FEATURE and explicitly not a validated one.

    "Publication destroys edge" is widely believed and rarely measured. Some published effects
    persist for decades and some die before the paper is printed, so this number is computed,
    reported, and kept OUT of the hazard until this desk has measured the relationship in its own
    data. Borrowing the conclusion would be adopting a belief as a law.
    """
    mentions = max(0.0, min(1.0, (c.public_mentions_ratio - 1.0) / 4.0))
    forks = max(0.0, min(1.0, (c.repo_forks_ratio - 1.0) / 4.0))
    score = (mentions + forks) / 2.0
    return score, (
        f"{c.strategy_id}: public diffusion {score:.2f} (mentions x{c.public_mentions_ratio:.1f}, "
        f"forks x{c.repo_forks_ratio:.1f}). UNVALIDATED on this desk -- reported as a candidate "
        "feature and deliberately excluded from the hazard until the relationship between "
        "diffusion and realised decay has been measured here rather than assumed")


def hazard(c: CrowdingState, *, horizon_days: float = 90.0) -> tuple[float | None, str]:
    """P(the edge is materially competed away within the horizon). None when unmeasured.

    Built from BOOK EVIDENCE ONLY. The realised-edge ratio is deliberately excluded from the
    computation and used afterwards only to check the hazard against what happened -- a hazard that
    reads the P&L is a lagging indicator wearing a leading indicator's name, and it would be
    perfectly accurate and completely useless.
    """
    micro, _parts, mwhy = microstructure_pressure(c)
    if micro is None:
        return None, mwhy
    # Exponential hazard: pressure maps to a decay rate, integrated over the horizon. A pressure of
    # 0 gives zero hazard; 1.0 gives near-certainty over 90 days. The scale is declared rather than
    # fitted because the desk has no decay history to fit it to yet, and an invented fit would look
    # more precise while being no better founded.
    rate = micro / 120.0                       # per day at full pressure, ~1 in 4 months
    p = 1.0 - math.exp(-rate * horizon_days)
    _diff, dwhy = diffusion_pressure(c)
    check = ""
    if c.realised_edge_ratio is not None:
        check = (f" Realised edge is at {c.realised_edge_ratio:.0%} of validated, which is a CHECK "
                 "on this hazard and was not an input to it")
    return p, (
        f"{c.strategy_id}: {p:.0%} probability of material decay within {horizon_days:g} days on "
        f"book evidence alone. {mwhy}. {dwhy}.{check}")


def summarise(states: list[CrowdingState], *, horizon_days: float = 90.0) -> dict[str, object]:
    """Report shape for `data/opportunity_books.json`. Leads with the highest hazard."""
    if not states:
        return {"strategies": 0, "headline": (
            "no crowding states recorded -- decay on this desk can only be discovered from "
            "returns, which means discovering it after a year of funding it")}
    rows = []
    for c in states:
        h, why = hazard(c, horizon_days=horizon_days)
        micro, parts, _ = microstructure_pressure(c)
        diff, _ = diffusion_pressure(c)
        rows.append({
            "strategy_id": c.strategy_id,
            "decay_hazard": None if h is None else round(h, 4),
            "microstructure_pressure": None if micro is None else round(micro, 4),
            "pressure_by_source": {k: round(v, 3) for k, v in parts.items()},
            "diffusion_pressure_UNVALIDATED": round(diff, 4),
            "why": why,
        })
    rows.sort(key=lambda r: -(float(str(r["decay_hazard"]))
                              if r["decay_hazard"] is not None else -1.0))
    at_risk = [r for r in rows if r["decay_hazard"] is not None
               and float(str(r["decay_hazard"])) >= 0.3]
    unmeasured = [r for r in rows if r["decay_hazard"] is None]
    return {
        "strategies": len(states),
        "rows": rows,
        "at_risk": len(at_risk),
        "unmeasured": len(unmeasured),
        "headline": (
            f"{len(at_risk)} strategy(ies) carry a decay hazard above 30% over {horizon_days:g} "
            f"days on book evidence alone: {[r['strategy_id'] for r in at_risk[:3]]}. Acting on "
            "this before the returns confirm it is the entire point"
            if at_risk else
            f"{len(unmeasured)} of {len(rows)} strategy(ies) carry no crowding measurement, so "
            "their decay is UNMEASURED and will be discovered from P&L"),
        "note": ("The hazard uses BOOK evidence only -- spread, basis, funding, queue, fills, "
                 "impact. Public diffusion is computed and reported but excluded, because "
                 "'publication destroys edge' is widely believed and unmeasured here. The "
                 "realised edge ratio is a CHECK on the hazard and never an input: a hazard that "
                 "reads the P&L is a lagging indicator wearing a leading indicator's name."),
    }
