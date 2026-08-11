"""CAPACITY CURVE -- gate items 11/12/13: how edge decays with capital, measured not asserted.

WHY A NEW MODULE RATHER THAN MORE capacity_policy. libs/research/capacity_policy answers a
POLICY question -- given a book and a sleeve count, what allocation is permitted, and does a
candidate clear the headroom rule. It is a gate. This module answers an ECONOMIC question: across
the whole range of deployable capital, what does the net edge actually look like, where is it
maximised, and where does it go to zero. One is a threshold, the other is a function, and the
mandate's XIV/XV need the function: item 12 asks for a curve, item 11 asks that no institutional
floor rejects a small-capacity edge, item 13 asks that two strategies sharing a venue cannot both
claim the same liquidity.

THE FAILURE THIS PREVENTS, and it is the one that quietly kills a solo desk's best ideas. A
candidate with a $3,000 capacity and a strong net edge at that size is, at this desk's ~$13k
equity, worth more than a $5,000,000-capacity candidate with a thinner one -- but every
institutional habit says the opposite, because institutions cannot deploy $3,000 meaningfully.
Rejecting an edge for being small is rejecting it for a reason that does not apply here. So
capacity enters as a CONTINUOUS input to marginal E[log W], never as a floor a candidate must
clear (mandate XIV: "never reject genuine alpha merely because its capacity is too small for an
institution").

THE COST MODEL is deliberately explicit and deliberately conservative. Gross edge is what the
candidate measured; from it comes half-spread on entry and exit, then impact, then fees. Impact
uses the square-root law -- impact ~ k * sigma * sqrt(Q / ADV) -- which is the standard empirical
form (Almgren et al.; Kyle's lambda in its concave regime). It is a MODEL and it is labelled one:
the desk's own passive-impact fit (libs/execution/passive_impact) is the measured alternative, and
where a fitted coefficient exists it should be passed in rather than defaulted here.

NOTHING HERE SIZES ANYTHING. The curve is a measurement that an allocator may read. It cannot
promote, cannot allocate, and returns UNMEASURED rather than a number whenever an input is
missing -- a fabricated capacity estimate is worse than none, because it would be believed.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "CapacityCurve", "CapacityPoint", "PairCapacity",
    "capacity_curve", "portfolio_adjusted_capacity", "rank_by_marginal_value",
]

#: Square-root-law coefficient when the desk has not fitted its own. Conservative (higher = more
#: impact = smaller capacity), because the asymmetry is not symmetric: over-estimating impact
#: costs a slightly smaller position, under-estimating it books an edge that execution eats.
DEFAULT_IMPACT_K = 0.6

#: Fraction of the round trip paid as spread. 1.0 = cross on both legs (taker in, taker out).
#: The maker path is cheaper and the desk's execution research owns that number; the default
#: assumes the expensive path so a curve is never optimistic by omission.
DEFAULT_SPREAD_LEGS = 2.0


@dataclass(frozen=True)
class CapacityPoint:
    capital_usd: float
    gross_edge_bps: float
    spread_cost_bps: float
    impact_bps: float
    fee_bps: float
    net_edge_bps: float
    net_usd_per_period: float
    marginal_log_growth: float

    def as_dict(self) -> dict[str, Any]:
        return {k: round(v, 6) for k, v in self.__dict__.items()}


@dataclass(frozen=True)
class CapacityCurve:
    status: str
    points: tuple[CapacityPoint, ...] = ()
    optimum_usd: float | None = None
    minimum_economic_usd: float | None = None
    maximum_economic_usd: float | None = None
    saturation_usd: float | None = None
    why: str = ""
    inputs: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {"status": self.status, "optimum_usd": self.optimum_usd,
                "minimum_economic_usd": self.minimum_economic_usd,
                "maximum_economic_usd": self.maximum_economic_usd,
                "saturation_usd": self.saturation_usd, "why": self.why,
                "inputs": self.inputs, "points": [p.as_dict() for p in self.points],
                "authority": "MEASUREMENT ONLY -- sizes nothing, promotes nothing."}


def _grid(adv_usd: float, n: int = 24) -> list[float]:
    """Log-spaced capital grid from $100 to 5% of ADV. Log-spaced because the interesting
    structure is at the small end for this desk, and a linear grid would spend most of its points
    describing sizes the desk will never deploy."""
    hi = max(1_000.0, adv_usd * 0.05)
    lo = 100.0
    if hi <= lo:
        return [lo]
    step = (math.log(hi) - math.log(lo)) / max(1, n - 1)
    return [math.exp(math.log(lo) + i * step) for i in range(n)]


def capacity_curve(*, name: str, gross_edge_bps: float | None, adv_usd: float | None,
                   spread_bps: float | None, volatility: float | None,
                   fee_bps: float = 0.0, impact_k: float = DEFAULT_IMPACT_K,
                   spread_legs: float = DEFAULT_SPREAD_LEGS,
                   periods_per_year: float = 365.0) -> CapacityCurve:
    """GATE ITEM 12. capital -> gross edge -> costs -> net edge -> marginal log growth.

    Returns UNMEASURED with the missing input named whenever an input is absent. A curve built on
    a guessed ADV would be a confident-looking fiction, and capacity fictions are precisely how a
    backtest that cannot be executed reaches capital.
    """
    missing = [n for n, v in (("gross_edge_bps", gross_edge_bps), ("adv_usd", adv_usd),
                              ("spread_bps", spread_bps), ("volatility", volatility))
               if v is None]
    if missing:
        return CapacityCurve(
            "UNMEASURED", why=f"{name}: missing {missing} -- a capacity curve on guessed inputs "
                              "is a fiction that would be believed. Measure them or leave the "
                              "candidate's capacity UNKNOWN (L1.41)",
            inputs={"name": name})
    assert gross_edge_bps is not None and adv_usd is not None
    assert spread_bps is not None and volatility is not None

    pts: list[CapacityPoint] = []
    for cap in _grid(adv_usd):
        # Square-root law, expressed in bps: k * sigma * sqrt(participation) * 1e4.
        participation = cap / adv_usd if adv_usd > 0 else 0.0
        impact = impact_k * volatility * math.sqrt(max(0.0, participation)) * 1e4
        spread = spread_bps * spread_legs / 2.0
        net = gross_edge_bps - spread - impact - fee_bps
        net_usd = cap * net / 1e4
        # MARGINAL LOG GROWTH, not raw PnL: the desk's objective is E[log W], so a bigger dollar
        # number on a bigger stake is not automatically better. log1p keeps it finite and correct
        # for the small-fraction regime this desk actually trades in.
        eq = max(cap, 1.0)
        g = math.log1p(max(-0.999999, net_usd / eq)) * periods_per_year
        pts.append(CapacityPoint(cap, gross_edge_bps, spread, impact, fee_bps, net, net_usd, g))

    positive = [p for p in pts if p.net_edge_bps > 0]
    if not positive:
        return CapacityCurve(
            "NO-CAPACITY", points=tuple(pts),
            why=f"{name}: net edge is negative at every size on the grid -- costs exceed the "
                "gross edge before capital is even a constraint. This is a COST verdict, not a "
                "capacity one, and the candidate fails for that reason",
            inputs={"name": name, "adv_usd": adv_usd, "gross_edge_bps": gross_edge_bps})

    # The optimum maximises TOTAL net dollars subject to the edge staying positive -- growth rate
    # per dollar is highest at the smallest size, so optimising the rate alone would recommend
    # trading $100 forever.
    best = max(positive, key=lambda p: p.net_usd_per_period)
    return CapacityCurve(
        "MEASURED", points=tuple(pts),
        optimum_usd=best.capital_usd,
        minimum_economic_usd=min(p.capital_usd for p in positive),
        maximum_economic_usd=max(p.capital_usd for p in positive),
        saturation_usd=max(p.capital_usd for p in positive),
        why=(f"{name}: net edge positive from ${min(p.capital_usd for p in positive):,.0f} to "
             f"${max(p.capital_usd for p in positive):,.0f}; total net dollars peak at "
             f"${best.capital_usd:,.0f}. Impact modelled by the square-root law (k={impact_k}) -- "
             "a MODEL, superseded by a fitted coefficient where one exists"),
        inputs={"name": name, "adv_usd": adv_usd, "gross_edge_bps": gross_edge_bps,
                "spread_bps": spread_bps, "volatility": volatility, "fee_bps": fee_bps,
                "impact_k": impact_k, "impact_model": "square-root law (Almgren-style)"})


def rank_by_marginal_value(candidates: list[dict[str, Any]], *,
                           current_capital_usd: float) -> list[dict[str, Any]]:
    """GATE ITEM 11. Rank at the capital the desk ACTUALLY HAS -- no institutional floor.

    A candidate is scored by its net edge at `current_capital_usd` (or at its own maximum
    economic size, whichever is smaller). A $3k-capacity candidate is therefore ranked on what it
    delivers at $3k rather than penalised for what it cannot deliver at $5M. Capacity enters as a
    CEILING on deployable size, never as an admission floor -- which is the whole of item 11.
    """
    out: list[dict[str, Any]] = []
    for c in candidates:
        curve: CapacityCurve = c["curve"]
        if curve.status != "MEASURED":
            out.append({"name": c["name"], "deployable_usd": None, "net_edge_bps": None,
                        "net_usd": None, "status": curve.status,
                        "why": "UNMEASURED capacity -- ranked last, NOT rejected: unknown is not "
                               "zero, and the fix is a measurement rather than a verdict"})
            continue
        deployable = min(current_capital_usd, curve.maximum_economic_usd or 0.0)
        at = min((p for p in curve.points if p.capital_usd <= deployable + 1e-9),
                 key=lambda p: abs(p.capital_usd - deployable), default=None)
        if at is None or at.net_edge_bps <= 0:
            out.append({"name": c["name"], "deployable_usd": deployable, "net_edge_bps": None,
                        "net_usd": None, "status": "UNECONOMIC-AT-THIS-SIZE",
                        "why": "net edge is not positive at the capital this desk can deploy"})
            continue
        out.append({"name": c["name"], "deployable_usd": at.capital_usd,
                    "net_edge_bps": at.net_edge_bps, "net_usd": at.net_usd_per_period,
                    "marginal_log_growth": at.marginal_log_growth, "status": "RANKED",
                    "capacity_ceiling_usd": curve.maximum_economic_usd,
                    "why": "scored at the capital the desk actually has; capacity is a CEILING on "
                           "size, never a floor for admission (mandate XIV)"})
    ranked = sorted([r for r in out if r["status"] == "RANKED"],
                    key=lambda r: -(r["net_usd"] or 0.0))
    return ranked + [r for r in out if r["status"] != "RANKED"]


@dataclass(frozen=True)
class PairCapacity:
    a: str
    b: str
    shared_liquidity: bool
    standalone_sum_usd: float
    portfolio_adjusted_usd: float
    cannibalisation_usd: float
    why: str

    def as_dict(self) -> dict[str, Any]:
        return {k: (round(v, 2) if isinstance(v, float) else v) for k, v in self.__dict__.items()}


def portfolio_adjusted_capacity(strategies: list[dict[str, Any]]) -> dict[str, Any]:
    """GATE ITEM 13. Two strategies on the same venue+asset cannot both claim the same book.

    SHARED LIQUIDITY IS THE DEFAULT ASSUMPTION when venue and asset match and the signal windows
    overlap, because that is the conservative direction: assuming independence when it is false
    over-states total capacity and the error shows up as impact nobody budgeted for. Overlap is
    declared by the caller (`window`), because whether two signals trade at the same time is a
    property of the signals, not something this module can infer from a name.

    The adjusted total is bounded by the LARGEST single capacity on the shared pool rather than
    the sum -- they are drawing on one order book, so the book's depth is the constraint however
    many strategies point at it.
    """
    pools: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for s in strategies:
        pools.setdefault((str(s.get("venue")), str(s.get("asset"))), []).append(s)

    pairs: list[PairCapacity] = []
    adjusted_total = 0.0
    standalone_total = sum(float(s.get("capacity_usd") or 0.0) for s in strategies)
    for (venue, asset), members in pools.items():
        caps = [float(m.get("capacity_usd") or 0.0) for m in members]
        windows = [set(m.get("window") or ()) for m in members]
        n_m = len(members)
        overlapping = n_m > 1 and any(
            windows[i] & windows[j] for i in range(n_m) for j in range(i + 1, n_m))
        if overlapping:
            pool_cap = max(caps)                     # one order book, one depth
            adjusted_total += pool_cap
            for i in range(len(members)):
                for j in range(i + 1, len(members)):
                    if windows[i] & windows[j]:
                        pairs.append(PairCapacity(
                            a=str(members[i].get("name")), b=str(members[j].get("name")),
                            shared_liquidity=True,
                            standalone_sum_usd=caps[i] + caps[j],
                            portfolio_adjusted_usd=max(caps[i], caps[j]),
                            cannibalisation_usd=min(caps[i], caps[j]),
                            why=(f"same venue ({venue}) and asset ({asset}) with overlapping "
                                 f"windows {sorted(windows[i] & windows[j])} -- they draw on ONE "
                                 "order book, so the book's depth constrains the pair however "
                                 "many strategies point at it. Summing them would book the same "
                                 "liquidity twice")))
        else:
            adjusted_total += sum(caps)
    return {
        "standalone_sum_usd": round(standalone_total, 2),
        "portfolio_adjusted_usd": round(adjusted_total, 2),
        "cannibalisation_usd": round(standalone_total - adjusted_total, 2),
        "pairs": [p.as_dict() for p in pairs],
        "law": ("Shared liquidity is assumed whenever venue+asset match and windows overlap. "
                "Assuming independence when it is false over-states capacity, and that error "
                "arrives as impact nobody budgeted for."),
        "authority": "MEASUREMENT ONLY -- allocates nothing.",
    }
