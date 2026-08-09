"""CAPITAL RECYCLING — the difference between a large gain and a kept one is what happened next.

THE OBSERVED BEHAVIOUR THIS GENERALISES: take large risk-on exposure, harvest a substantial part of
the gain into purchasing power, then redeploy that purchasing power during later weakness. Done
well it is the single most valuable habit in the benchmarked operator's public record. Done by
rule -- "sell 20%", "buy back after -15%" -- it is a coin flip with extra steps, because the rule
fires on the state it was written for and on every other state too.

**SO THE RULES ARE NOT HERE AND CANNOT BE ADDED.** What this computes is a comparison, at every
point, between five things the capital could be doing::

    KEEP      continuation value: what the position earns if left alone
    REDUCE    trim, keeping the mechanism
    HARVEST   realise into reserve, buying option value on future dislocations
    ROTATE    same risk budget, better opportunity
    REDEPLOY  reserve back into risk because the opportunity set improved

Each is an E[log W] estimate. The action is whichever is largest, and when they are within noise of
each other the honest answer is KEEP -- churn has a cost and indecision should not pay it.

**THE METRIC THAT SETTLES WHETHER ANY OF THIS WORKED** is `CAPITAL_RECYCLING_ALPHA`: realised log
growth of the recycling path minus the log growth of simply holding the same exposure throughout,
after all costs. It can be NEGATIVE, and the module reports that plainly. A desk that harvests and
redeploys busily while underperforming a static hold has found an expensive hobby, and the number
that says so is the only defence against never looking.

**LARGE UNREALISED GAIN CREATES NO OWNERSHIP PRIVILEGE.** The comparison is forward-looking and
takes no input from what the position has already made. `harvest_value` prices the option value of
reserve against the continuation value of exposure; neither term contains the entry price.

Compares and reports. Trades nothing, and the allocator owns what the comparison buys.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

__all__ = [
    "ACTIONS",
    "CYCLE_STAGES",
    "MIN_PATH_FOR_ALPHA",
    "PositionState",
    "capital_recycling_alpha",
    "compare",
    "continuation_value",
    "harvest_value",
    "stage_of",
    "summarise",
]

#: The five things capital can do. Ordered by how much they disturb an existing position, so a tie
#: resolves toward the cheapest -- churn costs money and indecision must not pay for it.
ACTIONS: tuple[str, ...] = ("KEEP", "REDUCE", "HARVEST", "ROTATE", "REDEPLOY")

#: The economic cycle this book tracks. A stage is DESCRIPTIVE -- it says where the capital is, not
#: what to do, because "we are in APPRECIATION" is not a reason to harvest.
CYCLE_STAGES: tuple[str, ...] = (
    "ENTRY", "APPRECIATION", "HARVEST", "RESERVE", "DISLOCATION", "REDEPLOY",
)

#: Below this many marks, recycling alpha is a comparison of two short paths and means nothing.
MIN_PATH_FOR_ALPHA: int = 30


@dataclass(frozen=True)
class PositionState:
    """One position and the forward state that decides what its capital should do next.

    NOTE WHAT IS ABSENT: there is no entry price and no unrealised gain. Both are facts about the
    past and neither belongs in a forward marginal decision -- including them is precisely how a
    winner acquires the ownership privilege this module denies it.
    """

    name: str
    #: Fraction of the book currently in this position.
    weight: float = 0.0
    #: Forward expected log-return per period if held, net of costs. 0 = UNMEASURED.
    forward_edge: float = 0.0
    #: Posterior width of that estimate. Required -- an edge with no width cannot be compared.
    edge_sigma: float = 0.0
    #: Per-period variance of the position.
    variance: float = 0.0
    #: P(the regime that supports this position ends within the horizon). 0 = unmeasured.
    transition_hazard: float = 0.0
    #: How crowded the trade is, 0-1. Crowding raises the cost of exiting later, not now.
    crowding: float = 0.0
    #: Momentum exhaustion proxy, 0-1. 1 = the move looks finished.
    exhaustion: float = 0.0
    #: Round-trip cost of trimming or exiting, as a fraction. THE REASON KEEP WINS TIES.
    round_trip_cost: float = 0.0
    #: Best available alternative use of the same risk budget, in the same units as forward_edge.
    best_alternative_edge: float = 0.0


def stage_of(*, weight: float, reserve_fraction: float, drawdown: float,
             recently_harvested: bool = False) -> tuple[str, str]:
    """Where the capital currently sits in the cycle. DESCRIPTIVE, never prescriptive.

    Naming the stage is useful for reporting and dangerous as a trigger: "we are in APPRECIATION"
    is not a reason to harvest, and a book that acted on stage labels would have re-invented the
    fixed rule this module exists to replace.
    """
    if drawdown >= 0.15 and reserve_fraction >= 0.2:
        return "DISLOCATION", (f"{drawdown:.0%} below the high-water mark with "
                               f"{reserve_fraction:.0%} in reserve -- the state reserve was held "
                               "for. Whether to deploy is a marginal question, not a stage one")
    if reserve_fraction >= 0.5 and weight <= 0.2:
        return "RESERVE", f"{reserve_fraction:.0%} in reserve, {weight:.0%} at risk"
    if recently_harvested:
        return "HARVEST", "a harvest was taken this period"
    if weight >= 0.5 and drawdown <= 0.05:
        return "APPRECIATION", f"{weight:.0%} at risk near the high-water mark"
    if weight <= 0.05:
        return "ENTRY", "little or nothing at risk"
    return "REDEPLOY", f"{weight:.0%} at risk with {reserve_fraction:.0%} held back"


def continuation_value(p: PositionState, *, horizon_periods: float = 1.0) -> tuple[float | None,
                                                                                  str]:
    """E[log W] from leaving the position alone. None when unmeasured.

    Charges the regime hazard against the whole horizon: an edge that depends on a regime with a
    30% chance of ending is not a 30%-smaller edge, it is an edge that stops existing partway
    through, and the geometric cost of that is what the survival term prices.
    """
    if p.edge_sigma <= 0 or p.variance <= 0:
        return None, (f"{p.name}: no posterior width or no variance, so continuation cannot be "
                      "priced. An unmeasured edge held because it is already held is the "
                      "incumbency this desk has a law against")
    shrunk = p.forward_edge - p.edge_sigma
    survival = (1.0 - max(0.0, min(1.0, p.transition_hazard)) * 0.5)
    value = (shrunk * p.weight - 0.5 * p.variance * p.weight ** 2) * survival * horizon_periods
    return value, (
        f"{p.name}: shrunk edge {shrunk:+.5f} at weight {p.weight:.0%}, less variance drag, "
        f"times {survival:.2f} regime survival => continuation {value:+.6f}")


def harvest_value(p: PositionState, *, reserve_option_value: float,
                  harvest_fraction: float = 1.0) -> tuple[float | None, str]:
    """E[log W] from realising into reserve. Pays the round trip, buys the option value.

    `reserve_option_value` comes from `libs/portfolio/wealth_retention.reserve_option_value` and is
    the whole reason harvesting can win: cash is a call on every dislocation that has not happened
    yet, and a book that prices it at zero can never justify holding any.
    """
    if p.edge_sigma <= 0:
        return None, f"{p.name}: unmeasured edge, so harvesting cannot be compared against holding"
    f = max(0.0, min(1.0, harvest_fraction))
    freed = p.weight * f
    cost = freed * p.round_trip_cost
    value = freed * reserve_option_value - cost
    return value, (
        f"{p.name}: harvesting {f:.0%} frees {freed:.0%} of the book, buying "
        f"{freed * reserve_option_value:+.6f} of reserve option value for {cost:.6f} in round-trip "
        f"cost => {value:+.6f}. Note this contains no entry price and no unrealised gain: a large "
        "winner earns no privilege here")


def compare(p: PositionState, *, reserve_option_value: float = 0.0,
            horizon_periods: float = 1.0,
            indifference: float = 1e-6) -> tuple[str, str, dict[str, float | None]]:
    """(action, why, values). The largest E[log W], with ties resolving to KEEP.

    TIES GO TO KEEP AND THAT IS A DESIGN DECISION, not a default. Every other action pays a round
    trip, so when the estimates are within noise of each other the cheapest is correct -- and a
    module that broke ties toward action would generate churn that looks like decisiveness and
    charges like a fee.
    """
    cont, cwhy = continuation_value(p, horizon_periods=horizon_periods)
    if cont is None:
        return "KEEP", (f"UNMEASURED -- {cwhy}. KEEP by default because every alternative pays a "
                        "round trip, and paying one on an unmeasured comparison is a certain cost "
                        "against an unknown benefit"), {"continuation": None}
    harv, hwhy = harvest_value(p, reserve_option_value=reserve_option_value)
    reduce_v, _ = harvest_value(p, reserve_option_value=reserve_option_value,
                                harvest_fraction=0.5)
    rotate = ((p.best_alternative_edge - p.forward_edge) * p.weight
              - p.weight * p.round_trip_cost) if p.best_alternative_edge else None
    # REDEPLOY is the mirror of harvest and is only meaningful when reserve exists to deploy; the
    # caller signals that by supplying an alternative edge above the current one at low weight.
    redeploy = ((p.best_alternative_edge - p.round_trip_cost) * (1.0 - p.weight)
                if p.weight < 1.0 and p.best_alternative_edge > 0 else None)

    values: dict[str, float | None] = {
        "KEEP": cont, "REDUCE": (None if reduce_v is None else cont * 0.5 + reduce_v),
        "HARVEST": (None if harv is None else harv), "ROTATE": rotate, "REDEPLOY": redeploy,
    }
    scored = {k: v for k, v in values.items() if v is not None}
    best = max(scored, key=lambda k: scored[k])
    if scored[best] - scored["KEEP"] <= indifference:
        best = "KEEP"
    exhaust = ""
    if p.exhaustion >= 0.7 or p.crowding >= 0.7:
        exhaust = (f" State note: exhaustion {p.exhaustion:.0%}, crowding {p.crowding:.0%} -- both "
                   "raise the cost of exiting LATER and neither is a reason to exit now; they "
                   "belong in the edge estimate, not in a trigger")
    return best, (
        f"{p.name}: {best} at {scored[best]:+.6f} against KEEP {scored['KEEP']:+.6f}. {cwhy}. "
        f"{hwhy}.{exhaust}"), values


def capital_recycling_alpha(recycled_nav: tuple[float, ...],
                            static_hold_nav: tuple[float, ...]) -> tuple[float | None, str]:
    """Realised log growth of recycling MINUS holding the same exposure throughout. THE VERDICT.

    Can be negative and frequently will be. A desk that harvests and redeploys busily while
    underperforming a static hold has found an expensive hobby, and this is the only number that
    would ever say so -- every other metric on the recycling path measures the recycling path.
    """
    n = min(len(recycled_nav), len(static_hold_nav))
    if n < MIN_PATH_FOR_ALPHA:
        return None, (f"{n} common mark(s) against a floor of {MIN_PATH_FOR_ALPHA}. UNMEASURED -- "
                      "a comparison of two short paths says more about the window than about the "
                      "policy")
    if recycled_nav[0] <= 0 or static_hold_nav[0] <= 0:
        return None, "a starting NAV is non-positive; log growth is undefined"
    g_r = math.log(recycled_nav[n - 1] / recycled_nav[0])
    g_s = math.log(static_hold_nav[n - 1] / static_hold_nav[0])
    alpha = g_r - g_s
    return alpha, (
        f"CAPITAL_RECYCLING_ALPHA {alpha:+.5f}: recycled path {g_r:+.5f} log growth against "
        f"{g_s:+.5f} for holding the same exposure throughout, over {n} marks. "
        + ("The recycling is EARNING its costs" if alpha > 0 else
           "The recycling is COSTING more than it earns -- busy harvesting and redeploying that "
           "underperforms a static hold is an expensive hobby, and no other metric on this path "
           "would have said so"))


def summarise(positions: list[PositionState], *, reserve_option_value: float = 0.0,
              recycled_nav: tuple[float, ...] = (),
              static_hold_nav: tuple[float, ...] = (),
              reserve_fraction: float = 0.0,
              drawdown: float = 0.0) -> dict[str, object]:
    """Report shape for `data/opportunity_books.json`."""
    if not positions:
        return {"positions": 0, "headline": (
            "no positions recorded -- the desk holds nothing, so KEEP/HARVEST/REDEPLOY is not a "
            "live question. CAPITAL_RECYCLING_ALPHA is UNMEASURED and will stay so until there is "
            "a path to compare against a static hold")}
    rows = []
    for p in positions:
        action, why, values = compare(p, reserve_option_value=reserve_option_value)
        rows.append({"name": p.name, "weight": p.weight, "action": action, "why": why,
                     "values": {k: (None if v is None else round(v, 8))
                                for k, v in values.items()}})
    total_weight = sum(p.weight for p in positions)
    stage, swhy = stage_of(weight=total_weight, reserve_fraction=reserve_fraction,
                           drawdown=drawdown)
    alpha, awhy = capital_recycling_alpha(recycled_nav, static_hold_nav)
    acting = [r for r in rows if r["action"] != "KEEP"]
    return {
        "positions": len(positions),
        "cycle_stage": stage, "stage_why": swhy,
        "rows": rows,
        "actions_recommended": len(acting),
        "CAPITAL_RECYCLING_ALPHA": None if alpha is None else round(alpha, 6),
        "recycling_alpha_note": awhy,
        "headline": (
            f"stage {stage}; {len(acting)} of {len(rows)} position(s) have a non-KEEP action"
            + (f"; CAPITAL_RECYCLING_ALPHA {alpha:+.4f}" if alpha is not None else
               "; recycling alpha UNMEASURED")),
        "note": ("No fixed profit-taking or re-entry rule exists in this module and none can be "
                 "added: every action is an E[log W] comparison and ties resolve to KEEP, because "
                 "each alternative pays a round trip. Cycle stages are DESCRIPTIVE -- 'we are in "
                 "APPRECIATION' is not a reason to harvest. No entry price or unrealised gain "
                 "enters any calculation here."),
    }
