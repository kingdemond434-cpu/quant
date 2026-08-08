"""THE MAXIMUM ECONOMIC FRONTIER — one ranking for every use of every scarce resource.

WHAT THIS REPLACES. The desk already ranks work: `run_max_push` merges six "what is left" artifacts
into a queue by declared leverage weights. That queue answers "what is furthest from 100%". It does
NOT answer the question the terminal law actually asks, which is:

    given everything we know right now, which FEASIBLE SET of actions -- across capital, risk,
    compute, data spend, engineering time and latency -- most increases long-run realised net
    retained E[log W], after accounting for every competing use of those same resources?

Those differ in a way that decides days. A queue ordered by distance-from-ceiling will rank a
research module above deploying a validated survivor, because the module is 0% and the survivor is
"done". The frontier will not, because the survivor's marginal contribution is larger and its
opportunity cost is a euro of compute rather than a euro of capital.

SIX PROPERTIES, EACH FIXING A SPECIFIC WAY THIS GOES WRONG:

**1. SHADOW PRICES, AND NO DOUBLE-COUNTED OPPORTUNITY COST.** Each scarce resource carries a
current marginal value. An action's surplus subtracts `sum(lambda_j * usage_j)` and NOT a separate
generic "opportunity cost" term, because when the shadow prices are doing their job that term is
already in there and adding it charges the same loss twice.

**2. UNCERTAINTY HAS A PRICE, SO DISTRIBUTIONS RANK, NOT POINT ESTIMATES.** A high but wildly
uncertain expected value must not automatically dominate a slightly lower, well-calibrated one.
`risk_adjusted` shrinks by posterior width AND by the proposer's historical calibration, so an
estimator with a record of optimism is discounted by its own record rather than by an argument.
This is not conservatism -- an uncertain action with a large enough edge still wins.

**3. FEASIBILITY IS A FILTER, NOT A SCORE.** Illegal, impossible, privilege-violating and
survival-breaking actions are removed BEFORE optimisation. They never receive a negative number and
compete, because a sufficiently optimistic estimate would eventually outbid the risk kernel, and
that is precisely the failure mode a risk kernel exists to make impossible.

**4. BUNDLES, NOT GREEDY SINGLES.** Buy the dataset / build the feature / run the experiment can
each look weak alone and be strongly positive together. Likewise fix the websocket + raise the
cadence. `best_bundle` evaluates declared bundles against the same budget and takes the best total
surplus, so a greedy pick cannot beat a better set.

**5. FRONTIER REGRET IS THE KPI.** The gap between the best feasible action set KNOWN at the time
and what was actually done, decomposed by category. It lets the desk learn not only that a trade
was bad but that the whole day's resources went to the wrong place.

**6. ANTI-GOODHART.** These are models, not truth. When estimated value and realised descendants
diverge, realised evidence dominates and the estimator is recalibrated -- `calibration` returns the
multiplier, and no component may improve its priority by improving its own estimate.

Ranks and reports. Spends nothing, deploys nothing, and cannot: the feasibility filter is an input
it does not own.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = [
    "INFEASIBLE_REASONS",
    "REGRET_CATEGORIES",
    "RESOURCES",
    "Action",
    "Bundle",
    "ResourcePrices",
    "best_bundle",
    "calibration",
    "economic_surplus",
    "feasible",
    "frontier_regret",
    "rank",
    "risk_adjusted",
    "summarise",
]

#: Everything that can be scarce. No resource is free merely because it is currently available --
#: idle CPU during a research bottleneck is a different economic object from idle CPU when no
#: useful experiment exists, and only the shadow price can tell them apart.
RESOURCES: tuple[str, ...] = (
    "capital", "risk_budget", "drawdown_capacity", "liquidity", "venue_capacity",
    "compute", "storage", "market_data_budget", "api_budget", "llm_tokens",
    "engineering_time", "research_attention", "latency_budget", "operational_complexity",
)

#: Why an action is removed BEFORE optimisation. Not scores: a filter.
INFEASIBLE_REASONS: tuple[str, ...] = (
    "ILLEGAL", "IMPOSSIBLE", "PRIVILEGE_VIOLATION", "SURVIVAL_BREAKING",
    "DEPENDENCY_UNMET", "RESOURCE_UNAVAILABLE",
)

#: Where the day's resources went wrong, when they did.
REGRET_CATEGORIES: tuple[str, ...] = (
    "RESEARCH_REGRET", "CAPITAL_REGRET", "EXECUTION_REGRET", "LATENCY_REGRET",
    "INFRASTRUCTURE_REGRET", "MODEL_SELECTION_REGRET", "IDLE_RESOURCE_REGRET",
)


@dataclass(frozen=True)
class ResourcePrices:
    """Current marginal value of one more unit of each resource. THE ANTI-DOUBLE-COUNT DEVICE.

    An empty price is UNMEASURED and priced at zero, which is optimistic and is reported as such:
    an action consuming an unpriced resource looks free, and the summary names every resource it
    consumed without a price rather than letting the total read as a full accounting.
    """

    prices: dict[str, float] = field(default_factory=dict)

    def price(self, resource: str) -> float:
        return max(0.0, float(self.prices.get(resource, 0.0)))

    @property
    def unpriced(self) -> tuple[str, ...]:
        return tuple(r for r in RESOURCES if r not in self.prices)


@dataclass(frozen=True)
class Action:
    """One candidate use of resources, with its uncertainty carried rather than dropped."""

    action_id: str
    category: str
    #: Posterior mean of the incremental log-wealth contribution. Not a point estimate that pretends
    #: to be a fact -- `elogw_sigma` is required for it to be rankable at all.
    elogw_mean: float = 0.0
    elogw_sigma: float = 0.0
    #: Probability the action succeeds economically at all. Separate from the magnitude: a 5%
    #: chance of a large win and a certain small win are different objects.
    p_success: float = 1.0
    #: Resource consumption, keyed by RESOURCES.
    resources: dict[str, float] = field(default_factory=dict)
    #: Direct and ongoing costs already expressed in log-wealth units.
    direct_cost: float = 0.0
    maintenance_cost: float = 0.0
    complexity_cost: float = 0.0
    #: Days until the value is realised, and the half-life of the opportunity itself. Together
    #: these decide urgency: an action whose opportunity expires before it can be delivered is
    #: not a slow win, it is a loss.
    time_to_value_days: float = 0.0
    opportunity_half_life_days: float = 0.0
    #: Who or what produced the estimate. Feeds the calibration discount.
    proposer: str = ""
    #: Set to remove this action from optimisation entirely.
    infeasible_reason: str = ""
    #: Value from improving future DECISIONS rather than from immediate P&L (§EVSI).
    information_value: float = 0.0
    dependencies: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.infeasible_reason and self.infeasible_reason not in INFEASIBLE_REASONS:
            raise ValueError(f"infeasible_reason must be one of {INFEASIBLE_REASONS}")
        for r in self.resources:
            if r not in RESOURCES:
                raise ValueError(f"unknown resource {r!r}; the basis is closed: {RESOURCES}")

    @property
    def measured(self) -> bool:
        return self.elogw_sigma > 0 and self.elogw_mean != 0.0


@dataclass(frozen=True)
class Bundle:
    """Actions whose combined surplus differs from the sum of their parts."""

    bundle_id: str
    action_ids: tuple[str, ...]
    #: Extra surplus (positive) or interference (negative) from doing them together.
    synergy: float = 0.0
    rationale: str = ""


def feasible(actions: list[Action]) -> tuple[list[Action], list[dict[str, str]]]:
    """(feasible, removed). THE FILTER RUNS FIRST AND IS NOT A SCORE.

    An infeasible action never receives a number, because any number can be outbid by a
    sufficiently optimistic estimate somewhere else -- and the whole purpose of a survival
    constraint is that it cannot be outbid.
    """
    ok, removed = [], []
    for a in actions:
        if a.infeasible_reason:
            removed.append({"action_id": a.action_id, "reason": a.infeasible_reason})
        else:
            ok.append(a)
    return ok, removed


def calibration(proposer: str, history: dict[str, tuple[float, float]]) -> tuple[float, str]:
    """Multiplier from a proposer's record: realised / predicted. §ANTI-GOODHART.

    `history` maps proposer -> (total predicted ΔElogW, total realised). A proposer that has
    consistently overestimated is discounted by ITS OWN RECORD rather than by an argument, and the
    discount cannot be improved by improving the estimate -- only by producing realised value.

    Returns 1.0 with a reason when there is no history. That is deliberately neutral: penalising an
    unproven proposer would freeze the exploration the frontier depends on.
    """
    rec = history.get(proposer)
    if not rec or rec[0] <= 0:
        return 1.0, (f"{proposer or 'unattributed'}: no calibration history, multiplier 1.0. "
                     "Neutral rather than penalised -- discounting an unproven proposer would "
                     "freeze the exploration this frontier depends on")
    predicted, realised = rec
    m = max(0.05, min(2.0, realised / predicted))
    return m, (f"{proposer}: realised {realised:.4f} against predicted {predicted:.4f} "
               f"=> x{m:.2f}. Improving this requires realised descendants, not better estimates")


def risk_adjusted(a: Action, *, calib: float = 1.0) -> tuple[float | None, str]:
    """Uncertainty- and calibration-adjusted expected contribution. NOT conservatism.

    Shrinks the mean by one posterior standard deviation and by the proposer's calibration, then
    applies success probability and opportunity decay over the delivery time. An uncertain action
    with a large enough edge still wins; what it cannot do is win merely by being uncertain in the
    optimistic direction.
    """
    if not a.measured:
        return None, (
            f"{a.action_id}: no posterior width recorded, so the estimate cannot be ranked against "
            "a calibrated one. UNMEASURED -- and an unmeasured estimate treated as measured is how "
            "the loudest guess wins the day")
    shrunk = (a.elogw_mean - a.elogw_sigma) * calib * max(0.0, min(1.0, a.p_success))
    decay = 1.0
    if a.opportunity_half_life_days > 0 and a.time_to_value_days > 0:
        decay = 0.5 ** (a.time_to_value_days / a.opportunity_half_life_days)
    value = shrunk * decay + a.information_value
    note = (f"{a.action_id}: mean {a.elogw_mean:+.4f} less sigma {a.elogw_sigma:.4f}, "
            f"x calibration {calib:.2f}, x P(success) {a.p_success:.2f}")
    if decay < 0.99:
        note += (f", x {decay:.2f} opportunity decay over {a.time_to_value_days:g}d against a "
                 f"{a.opportunity_half_life_days:g}d half-life")
        if decay < 0.25:
            note += (". MOST OF THIS OPPORTUNITY EXPIRES BEFORE DELIVERY -- redesign for speed or "
                     "reject; a slow win on a fast-decaying edge is a loss")
    if a.information_value:
        note += f", plus {a.information_value:+.4f} information value"
    return value, note


def economic_surplus(a: Action, prices: ResourcePrices, *,
                     calib: float = 1.0) -> tuple[float | None, str]:
    """Risk-adjusted value MINUS shadow-priced resource use and direct costs.

        surplus = E[dlogW]_adj - sum_j lambda_j * usage_j - direct - maintenance - complexity

    NO separate generic opportunity-cost term. When the shadow prices are doing their job that cost
    is already inside the sum, and adding it again charges the same loss twice -- which
    systematically kills cheap high-value actions in favour of ones whose resources nobody priced.
    """
    value, why = risk_adjusted(a, calib=calib)
    if value is None:
        return None, why
    resource_cost = sum(prices.price(r) * max(0.0, u) for r, u in a.resources.items())
    total = value - resource_cost - a.direct_cost - a.maintenance_cost - a.complexity_cost
    unpriced = [r for r in a.resources if r not in prices.prices]
    return total, (
        f"{why}; less shadow-priced resources {resource_cost:.4f} and costs "
        f"{a.direct_cost + a.maintenance_cost + a.complexity_cost:.4f} => surplus {total:+.4f}"
        + (f". UNPRICED resources consumed: {unpriced} -- those look free here and are not"
           if unpriced else ""))


def rank(actions: list[Action], prices: ResourcePrices, *,
         history: dict[str, tuple[float, float]] | None = None) -> list[dict[str, object]]:
    """Feasible actions ordered by economic surplus, best first. Unmeasured sort last."""
    hist = history or {}
    ok, _ = feasible(actions)
    rows: list[dict[str, object]] = []
    for a in ok:
        calib, cwhy = calibration(a.proposer, hist)
        s, why = economic_surplus(a, prices, calib=calib)
        rows.append({
            "action_id": a.action_id, "category": a.category,
            "surplus": None if s is None else round(s, 6),
            "elogw_mean": a.elogw_mean, "elogw_sigma": a.elogw_sigma,
            "p_success": a.p_success,
            "calibration": round(calib, 3), "calibration_note": cwhy,
            "time_to_value_days": a.time_to_value_days,
            "why": why, "measured": a.measured,
        })
    rows.sort(key=lambda r: (0 if r["measured"] else 1,
                             -(float(str(r["surplus"])) if r["surplus"] is not None else -1e18)))
    return rows


def best_bundle(actions: list[Action], bundles: list[Bundle], prices: ResourcePrices,
                *, budget: dict[str, float] | None = None,
                history: dict[str, tuple[float, float]] | None = None) -> dict[str, object]:
    """The highest-surplus FEASIBLE SET, comparing declared bundles against greedy singles.

    A greedy pick of the single best action is a special case and is evaluated as one, so this can
    only ever match or beat it. Bundles that breach the budget are reported as infeasible under
    the current constraint rather than silently dropped -- "we could not afford it" and "it was not
    worth it" are different findings.
    """
    hist = history or {}
    ok, removed = feasible(actions)
    by_id = {a.action_id: a for a in ok}
    cap = budget or {}

    def _score(ids: tuple[str, ...], synergy: float) -> tuple[float | None, dict[str, float]]:
        total = 0.0
        used: dict[str, float] = {}
        for i in ids:
            a = by_id.get(i)
            if a is None:
                return None, {}
            calib, _ = calibration(a.proposer, hist)
            s, _ = economic_surplus(a, prices, calib=calib)
            if s is None:
                return None, {}
            total += s
            for r, u in a.resources.items():
                used[r] = used.get(r, 0.0) + u
        return total + synergy, used

    candidates: list[dict[str, object]] = []
    for b in bundles:
        s, used = _score(b.action_ids, b.synergy)
        if s is None:
            continue
        over = {r: u for r, u in used.items() if r in cap and u > cap[r]}
        candidates.append({"bundle_id": b.bundle_id, "action_ids": list(b.action_ids),
                           "surplus": round(s, 6), "synergy": b.synergy,
                           "rationale": b.rationale, "resources_used": used,
                           "over_budget": over, "affordable": not over})
    for a in ok:
        s, used = _score((a.action_id,), 0.0)
        if s is None:
            continue
        over = {r: u for r, u in used.items() if r in cap and u > cap[r]}
        candidates.append({"bundle_id": f"single::{a.action_id}",
                           "action_ids": [a.action_id], "surplus": round(s, 6), "synergy": 0.0,
                           "rationale": "single action", "resources_used": used,
                           "over_budget": over, "affordable": not over})

    affordable = [c for c in candidates if c["affordable"]]
    affordable.sort(key=lambda c: -float(str(c["surplus"])))
    best = affordable[0] if affordable else None
    singles = [c for c in affordable if str(c["bundle_id"]).startswith("single::")]
    beat_greedy = bool(best and singles and float(str(best["surplus"]))
                       > float(str(singles[0]["surplus"])) + 1e-12)
    return {
        "selected": best,
        "candidates": candidates[:20],
        "removed_infeasible": removed,
        "bundle_beats_greedy": beat_greedy,
        "note": ("A greedy single is evaluated as a one-element bundle, so this can only match or "
                 "beat it. Unaffordable candidates are reported rather than dropped: 'could not "
                 "afford' and 'not worth it' are different findings and only one of them is a "
                 "verdict on the action."),
    }


def frontier_regret(*, best_known_surplus: float, selected_surplus: float,
                    by_category: dict[str, float] | None = None) -> dict[str, object]:
    """THE KPI. What the best feasible set known at the time would have produced, minus what was.

    Measured against what was KNOWN, not against hindsight. Regret against the best action
    identifiable only afterwards is not a decision failure -- it is the cost of operating under
    uncertainty, and charging it would make the metric unimprovable and therefore ignored.
    """
    regret = max(0.0, best_known_surplus - selected_surplus)
    cat = {k: round(v, 6) for k, v in (by_category or {}).items() if k in REGRET_CATEGORIES}
    unknown = sorted(set(by_category or {}) - set(REGRET_CATEGORIES))
    return {
        "FRONTIER_REGRET": round(regret, 6),
        "best_known_surplus": round(best_known_surplus, 6),
        "selected_surplus": round(selected_surplus, 6),
        "by_category": cat,
        "unrecognised_categories": unknown,
        "headline": (
            f"FRONTIER_REGRET {regret:.4f}: the best feasible set known at the time would have "
            f"produced {best_known_surplus:.4f} and the desk realised {selected_surplus:.4f}"
            + (f"; largest component {max(cat, key=lambda k: cat[k])}" if cat else "")
            if regret > 0 else
            "no frontier regret: the desk selected the best feasible action set it knew about"),
        "note": ("Measured against what was KNOWN at decision time, never against hindsight. "
                 "Regret against an action identifiable only afterwards is the cost of operating "
                 "under uncertainty rather than a decision failure, and charging it would make "
                 "this metric unimprovable and therefore ignored."),
    }


def summarise(actions: list[Action], prices: ResourcePrices, *,
              bundles: list[Bundle] | None = None,
              budget: dict[str, float] | None = None,
              history: dict[str, tuple[float, float]] | None = None) -> dict[str, object]:
    """Report shape for `data/economic_frontier.json`."""
    if not actions:
        return {"actions": 0, "headline": (
            "no candidate actions enumerated -- the economic frontier is UNMEASURED, so today's "
            "work was chosen by something other than expected marginal contribution")}
    ranked = rank(actions, prices, history=history)
    sel = best_bundle(actions, bundles or [], prices, budget=budget, history=history)
    measured = [r for r in ranked if r["measured"]]
    unpriced = list(prices.unpriced)
    best = sel.get("selected")
    return {
        "actions": len(actions),
        "feasible": len(ranked),
        "removed_infeasible": sel["removed_infeasible"],
        "ranked": ranked,
        "selection": sel,
        "unpriced_resources": unpriced,
        "headline": (
            (f"selected {best['bundle_id']} at surplus {best['surplus']}"      # type: ignore[index]
             + ("; a BUNDLE beat the single best action, which a greedy ranker would have missed"
                if sel["bundle_beats_greedy"] else "")
             if best else
             "no affordable feasible action set -- every candidate breaches the budget or lacks a "
             "posterior width")
            + (f". {len(ranked) - len(measured)} action(s) carry no posterior width and cannot be "
               "ranked" if len(measured) < len(ranked) else "")
            + (f". {len(unpriced)} resource(s) have no shadow price and therefore look free"
               if unpriced else "")),
        "note": ("Feasibility is a FILTER applied before optimisation, never a negative score: a "
                 "sufficiently optimistic estimate must never be able to outbid a survival "
                 "constraint. Opportunity cost enters ONCE, through the shadow prices. These are "
                 "models rather than truth -- when estimates and realised descendants diverge, "
                 "realised evidence dominates and the estimator is recalibrated."),
    }
