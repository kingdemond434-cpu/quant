"""MARGINAL MARKET BREADTH — where else can this mechanism meet the state it needs?

THE ASYMMETRY THIS MODULE EXISTS TO PRICE, and it is easy to miss because both sides look like
"more research". A desk with a validated mechanism can spend its next hour two ways:

    DEPTH    another parameter set on BTC. Tests the SAME state occurrences again.
    BREADTH  the same rule on a market it has never touched. Creates NEW state occurrences.

Those are not two flavours of the same activity. **A parameter search adds exactly zero
independent observations of the mechanism** -- it re-examines the same history and pays the full
multiplicity price for doing so, which is why the thousandth variant on five coins is
overwhelmingly likely to be a discovery about the sample. A new market where the mechanism can act
adds genuinely new draws from the same generating process, and the evidence per unit of research
compounds instead of deflating.

That is what a CTA's enormous market count actually buys. It is usually described as
diversification, and it is that, but the more valuable half is this: it gives one simple robust
rule far more independent chances to encounter the state in which it works. A small crypto desk
cannot trade four hundred futures markets, but it can ask the same question -- assets, venues,
perps, futures, options, prediction markets, DEX pools and protocol surfaces are all places one
mechanism might express itself.

**NEW EXPRESSIONS ARE NOT AUTOMATICALLY INDEPENDENT.** This is where the idea is oversold.
The same mechanism on BTC-perp and ETH-perp at the same venue in the same hour is close to one
observation, not two. `effective_independent_occurrences` deflates the count by cross-expression
state correlation, so "we added forty markets" cannot be spent as forty times the evidence.

**FEASIBILITY IS A FILTER, NOT A SCORE.** An expression the desk cannot reach -- no data, no venue
access, below minimum size -- is removed before ranking rather than given a low rank. Letting an
infeasible option compete on score is how a plan ends up containing something nobody can execute.

Ranks candidate expressions. Opens nothing, funds nothing.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

__all__ = [
    "INSTRUMENTS",
    "Expression",
    "breadth_versus_depth",
    "effective_independent_occurrences",
    "feasible",
    "marginal_breadth_elog",
    "rank_expressions",
    "summarise",
]

#: Places a crypto mechanism can be expressed. Deliberately wider than "another coin": the point
#: is independent EXPRESSIONS, and a perp, an option and a prediction market on the same asset can
#: encounter genuinely different states.
INSTRUMENTS: tuple[str, ...] = (
    "spot", "perp", "dated_future", "option", "prediction_market", "dex_pool", "protocol_position",
)


@dataclass(frozen=True)
class Expression:
    """One (mechanism, asset, venue, instrument) place the mechanism could act."""

    expression_id: str
    mechanism: str
    asset: str = ""
    venue: str = ""
    instrument: str = "perp"
    #: Times per year the mechanism's required STATE occurs here. This is the breadth number:
    #: it is what a new market adds and what a new parameter does not. 0 = UNMEASURED.
    state_occurrences_per_year: float = 0.0
    #: Expected gross edge per occurrence, in bps of notional. 0 = UNMEASURED.
    edge_bps_per_occurrence: float = 0.0
    #: All-in execution cost per occurrence, in bps: spread, fees, impact.
    execution_cost_bps: float = 0.0
    #: What the desk can actually deploy here per occurrence, in units of portfolio equity.
    capacity_fraction: float = 0.0
    #: Annual data + operational cost of carrying this expression, in units of portfolio equity.
    annual_carrying_cost: float = 0.0
    #: Mean correlation of this expression's STATE OCCURRENCES to those already held. Not return
    #: correlation -- the question is whether the mechanism fires here at the same times.
    state_correlation_to_held: float = 0.0
    #: Feasibility. Each of these is a hard filter, never a score component.
    data_available: bool = True
    venue_accessible: bool = True
    above_minimum_size: bool = True
    notes: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.instrument not in INSTRUMENTS:
            raise ValueError(f"unknown instrument {self.instrument!r}; expected {INSTRUMENTS}")

    @property
    def measured(self) -> bool:
        return self.state_occurrences_per_year > 0 and self.edge_bps_per_occurrence != 0.0

    @property
    def net_bps(self) -> float:
        return self.edge_bps_per_occurrence - self.execution_cost_bps


def feasible(e: Expression) -> tuple[bool, str]:
    """Can the desk actually reach this? A FILTER, applied before anything is ranked."""
    blockers = []
    if not e.data_available:
        blockers.append("no data")
    if not e.venue_accessible:
        blockers.append("venue not accessible")
    if not e.above_minimum_size:
        blockers.append("below venue minimum size")
    if blockers:
        return False, (f"{e.expression_id}: INFEASIBLE ({', '.join(blockers)}). Removed before "
                       "ranking rather than scored low -- an infeasible option that competes on "
                       "score is how a plan ends up containing something nobody can execute")
    return True, f"{e.expression_id}: reachable"


def marginal_breadth_elog(e: Expression) -> tuple[float | None, str]:
    """Annual E[log W] this expression adds, after costs and after dependence deflation.

    The occurrence count is deflated by `state_correlation_to_held` FIRST, because an expression
    that fires at the same times as one already held is not adding independent chances -- it is
    adding notional to a bet the desk already has on.
    """
    if not e.measured:
        return None, (f"{e.expression_id}: occurrence rate or edge UNMEASURED, so its marginal "
                      "contribution is unknown rather than zero. A market added on the assumption "
                      "that the mechanism fires there is an assumption, not breadth")
    rho = max(0.0, min(1.0, e.state_correlation_to_held))
    effective_occ = e.state_occurrences_per_year * (1.0 - rho)
    per_occ = (e.net_bps / 10_000.0) * e.capacity_fraction
    gross = effective_occ * per_occ
    net = gross - e.annual_carrying_cost
    # log1p keeps this an E[log W] contribution rather than an arithmetic one; the two diverge in
    # exactly the direction that matters when a single expression is sized large.
    contribution = math.log1p(net) if net > -1.0 else float("-inf")
    return contribution, (
        f"{e.expression_id} ({e.mechanism} on {e.asset or '?'} {e.instrument}"
        + (f" @{e.venue}" if e.venue else "") + f"): {e.state_occurrences_per_year:.0f} "
        f"occurrence(s)/yr deflated to {effective_occ:.1f} at rho {rho:.2f}, "
        f"{e.net_bps:+.1f}bp net x {e.capacity_fraction:.1%} capacity = {gross:+.4f}/yr gross, "
        f"less {e.annual_carrying_cost:.4f} carrying => {contribution:+.5f} MARGINAL_BREADTH_ELOG"
        + (". The carrying cost exceeds what the mechanism can earn here -- this market is a "
           "subscription, not an edge" if net <= 0 else ""))


def effective_independent_occurrences(expressions: list[Expression]) -> tuple[float, str]:
    """Total INDEPENDENT state encounters per year across a breadth set.

    THE NUMBER A PARAMETER SEARCH CANNOT MOVE. Forty markets that all fire in the same hour are
    close to one observation; forty that fire independently are forty, and the evidence available
    to validate the mechanism scales with this and not with the market count.
    """
    usable = [e for e in expressions if e.measured]
    if not usable:
        return 0.0, ("no expression has a measured occurrence rate -- independent evidence per "
                     "year is UNMEASURED, not zero")
    total = sum(e.state_occurrences_per_year for e in usable)
    eff = sum(e.state_occurrences_per_year * (1.0 - max(0.0, min(1.0, e.state_correlation_to_held)))
              for e in usable)
    return eff, (
        f"{len(usable)} expression(s) see {total:.0f} state occurrence(s)/yr, of which {eff:.0f} "
        f"are INDEPENDENT after deflation"
        + (f". {total - eff:.0f} of them fire at the same times as something already held and are "
           "notional on an existing bet rather than new evidence"
           if total - eff > 1 else
           ". These expressions largely fire at different times, which is the case where breadth "
           "genuinely multiplies the evidence available to validate the mechanism"))


def breadth_versus_depth(candidates: list[Expression], *,
                         depth_hypotheses: int = 0) -> tuple[str, str]:
    """(verdict, why) — the choice Parker's book makes implicitly and this desk makes explicitly.

    A DEPTH search adds `depth_hypotheses` tests against the SAME occurrences and pays full
    multiplicity for them. A BREADTH candidate adds new independent occurrences. This does not
    claim breadth always wins -- an infeasible or unprofitable market loses to any depth search --
    it refuses to let the comparison go unmade, which is the actual failure: depth is the default
    because it needs no new data, no new venue and no new operational surface.
    """
    reachable = [e for e in candidates if feasible(e)[0]]
    priced = [(e, marginal_breadth_elog(e)[0]) for e in reachable]
    positive = [(e, v) for e, v in priced if v is not None and v > 0]
    eff, eff_why = effective_independent_occurrences([e for e, _ in positive])
    if not positive:
        return "DEPTH", (
            f"none of {len(candidates)} candidate expression(s) clears its costs"
            + (f" ({len(candidates) - len(reachable)} were infeasible)"
               if len(reachable) < len(candidates) else "")
            + f". Depth wins by default here: {depth_hypotheses} further hypothes(es) on existing "
              "markets is the better use of the hour, and that is a real answer rather than a "
              "failure to find breadth")
    gain = sum(v for _, v in positive if v is not None)
    return "BREADTH", (
        f"{len(positive)} feasible expression(s) add {gain:+.5f} annual E[log W] and {eff:.0f} "
        f"INDEPENDENT state occurrence(s) per year. {eff_why}. Against this, {depth_hypotheses} "
        "further hypothes(es) on existing markets would add ZERO new occurrences by construction "
        "-- they re-examine the same history and pay the full multiplicity price for it. The "
        "mechanism does not need more parameters, it needs more places to meet the state it works "
        "in")


def rank_expressions(candidates: list[Expression]) -> list[dict[str, object]]:
    """Feasible expressions by marginal E[log W], best first.

    Infeasible ones are listed but never scored.
    """
    rows: list[dict[str, object]] = []
    for e in candidates:
        ok, fwhy = feasible(e)
        val, vwhy = (marginal_breadth_elog(e) if ok else (None, fwhy))
        rows.append({
            "expression_id": e.expression_id, "mechanism": e.mechanism, "asset": e.asset,
            "venue": e.venue, "instrument": e.instrument, "feasible": ok,
            "marginal_breadth_elog": None if val is None else round(val, 6),
            "state_occurrences_per_year": e.state_occurrences_per_year,
            "why": vwhy,
        })
    rows.sort(key=lambda r: (r["feasible"] is True,
                             float(str(r["marginal_breadth_elog"]))
                             if r["marginal_breadth_elog"] is not None else -1e18), reverse=True)
    return rows


def summarise(candidates: list[Expression], *, depth_hypotheses: int = 0) -> dict[str, object]:
    """Report shape for `data/opportunity_books.json`."""
    if not candidates:
        return {"measured": False, "headline": (
            "no candidate expressions recorded -- whether this desk's validated mechanisms could "
            "act anywhere they currently do not is UNMEASURED. The default in that state is DEPTH, "
            "because another parameter needs no new data and no new venue, and it is the default "
            "precisely when it is least likely to be right")}
    rows = rank_expressions(candidates)
    verdict, why = breadth_versus_depth(candidates, depth_hypotheses=depth_hypotheses)
    infeasible = [r for r in rows if r["feasible"] is False]
    eff, eff_why = effective_independent_occurrences(candidates)
    priced = [r for r in rows if r["marginal_breadth_elog"] is not None]
    return {
        "measured": bool(priced),
        "candidates": len(candidates),
        "feasible": len(candidates) - len(infeasible),
        "infeasible": [r["expression_id"] for r in infeasible],
        "rows": rows,
        "effective_independent_occurrences_per_year": round(eff, 2),
        "occurrence_note": eff_why,
        "verdict": verdict,
        "verdict_why": why,
        "headline": why,
        "note": ("A new market adds INDEPENDENT occurrences of the state a mechanism needs; a new "
                 "parameter adds none and pays full multiplicity for re-examining the same "
                 "history. Occurrence counts are deflated by cross-expression state correlation, "
                 "so forty markets that fire in the same hour cannot be spent as forty times the "
                 "evidence. Feasibility filters before ranking, never scores."),
    }
