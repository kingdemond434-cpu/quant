"""Execution policy is an alpha: choose HOW to enter by expected log-wealth, not by habit.

    A_t = argmax_a  E[ dlog W | signal, state, a ]

over a registry of order plans (VeighNa's algorithm registry, translated to what an MT5 CFD
venue can execute):

    MARKET              fill now at the quote, pay the spread and the modelled slip
    PASSIVE_LIMIT       rest inside the spread; pays less, may not fill
    AGGRESSIVE_LIMIT    rest at the touch; pays the spread, refuses a bad print
    PULLBACK            rest a fraction of ATR behind the quote; better price, lower P(fill)
    STOP                the bracket's pending stop at the level (entry on confirmation)
    SPREAD_CONDITIONED  wait until the spread is inside its own norm, then MARKET
    EVENT_DELAY         wait past a scheduled release, then MARKET
    SPLIT               two half-size orders: half MARKET, half PULLBACK
    SKIP                the utility of every action is below zero: do not trade

Each plan's utility is  P(fill) x E[edge | fill] - E[cost | plan]  with P(fill) and the cost
posterior from `fill_surface`, the edge from the sleeve's posterior in R converted to fractions
of price by the stop distance. `choose` returns the plan and every alternative's utility, so the
counterfactual ledger can score the road not taken.

NOTHING HERE SENDS AN ORDER. The gateway's bracket path places pending stops today; this is the
optimiser that would replace "always MARKET" on the family-market path once the box has enough
fills for the surface to be fitted. Until then it runs, reports and is scored -- shadow first.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mt5desk.fill_surface import FillSurface

POLICIES: tuple[str, ...] = ("MARKET", "PASSIVE_LIMIT", "AGGRESSIVE_LIMIT", "PULLBACK", "STOP",
                             "SPREAD_CONDITIONED", "EVENT_DELAY", "SPLIT", "SKIP")


@dataclass(frozen=True)
class Context:
    symbol: str
    side: str                      # "buy" | "sell"
    quote: float                   # bid for sell, ask for buy
    spread_frac: float             # spread / price
    atr_frac: float                # ATR / price
    stop_frac: float               # stop distance / price
    edge_r: float                  # posterior expected R for the entry, net of nothing
    hour: int
    lot: float
    spread_rank: float = 0.5       # trailing percentile of the spread
    event_within_h: float | None = None
    fill_edge_decay: float = 0.3   # fraction of the edge lost while a resting order waits


@dataclass(frozen=True)
class Plan:
    policy: str
    p_fill: float
    edge_frac: float               # expected edge if filled, as a fraction of price
    cost_frac: float               # expected cost, fraction of price
    utility: float                 # p_fill * edge - cost
    detail: dict[str, Any]


def _edge_frac(c: Context) -> float:
    return c.edge_r * c.stop_frac


def _row(c: Context, distance_frac: float, order_type: str) -> dict[str, Any]:
    return {"spread_at_decision": c.spread_frac * c.quote, "intended": c.quote,
            "atr_frac": c.atr_frac, "time": f"2000-01-01T{c.hour:02d}:00:00+00:00",
            "lot": c.lot, "side": c.side, "distance_frac": distance_frac,
            "order_type": order_type}


def plans(c: Context, surface: FillSurface | None = None) -> list[Plan]:
    fs = surface or FillSurface()
    edge = _edge_frac(c)
    slip_mu, _ = fs.expected_slip(_row(c, 0.0, "market"), c.spread_frac)
    out: list[Plan] = []

    def add(policy: str, p_fill: float, edge_f: float, cost: float, **detail: Any) -> None:
        # NO EDGE, NO TRADE, WHATEVER THE EXECUTION. Price improvement on a resting order is a
        # cost saving on a trade worth making, never an edge of its own: a signal with zero or
        # negative expectancy has every plan's utility at minus its cost, and SKIP wins.
        u = (p_fill * edge_f - cost) if edge > 0 else -abs(cost) - 1e-6
        out.append(Plan(policy, round(p_fill, 4), round(edge_f, 6), round(cost, 6),
                        round(u, 6), detail))

    add("MARKET", 1.0, edge, c.spread_frac + max(slip_mu, 0.0))
    for name, dist_atr in (("PASSIVE_LIMIT", 0.0), ("AGGRESSIVE_LIMIT", 0.0),
                           ("PULLBACK", 0.5)):
        d = (c.spread_frac * 0.5 if name == "PASSIVE_LIMIT" else 0.0) + dist_atr * c.atr_frac
        p = fs.p_fill(_row(c, d, "limit"))
        # A resting order that fills gets a better price by `d` but loses part of the edge to
        # the wait, and pays no spread on the passive side.
        e = edge * (1.0 - c.fill_edge_decay * (0.5 if d == 0 else 1.0)) + d
        cost = (0.0 if name == "PASSIVE_LIMIT" else c.spread_frac) * p
        add(name, p, e, cost, distance_frac=round(d, 6))
    add("STOP", fs.p_fill(_row(c, 0.5 * c.atr_frac, "pending_stop")), edge * 0.9,
        (c.spread_frac + max(slip_mu, 0.0)) * 0.9, note="entry on confirmation, pays slip")
    if c.spread_rank > 0.8:
        # Waiting for the spread to normalise: pay the median spread instead of this one.
        add("SPREAD_CONDITIONED", 0.85, edge * (1.0 - c.fill_edge_decay * 0.5),
            c.spread_frac * 0.6 + max(slip_mu, 0.0), spread_rank=c.spread_rank)
    if c.event_within_h is not None and c.event_within_h <= 1.0:
        add("EVENT_DELAY", 0.9, edge * (1.0 - c.fill_edge_decay), c.spread_frac,
            event_within_h=c.event_within_h)
    mkt = out[0]
    pb = next(p for p in out if p.policy == "PULLBACK")
    add("SPLIT", 0.5 * (1.0 + pb.p_fill), 0.5 * (mkt.edge_frac + pb.edge_frac),
        0.5 * (mkt.cost_frac + pb.cost_frac))
    out.append(Plan("SKIP", 0.0, 0.0, 0.0, 0.0, {}))
    return out


def choose(c: Context, surface: FillSurface | None = None) -> dict[str, Any]:
    ps = plans(c, surface)
    best = max(ps, key=lambda p: p.utility)
    return {"policy": best.policy, "utility": best.utility, "p_fill": best.p_fill,
            "alternatives": {p.policy: p.utility for p in ps},
            "would_have_traded": best.policy != "SKIP",
            "surface": (surface.note if surface else "prior: spread model")}
