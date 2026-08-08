"""CONTINUOUS CAPITAL COMPETITION — no strategy owns its allocation because it got there first.

THE DEFECT THIS REMOVES, and it is an economic one rather than an engineering one. A desk that
promotes an alpha and then leaves it funded has made a decision once and stopped charging for it.
Capital sitting in a strategy whose forward expectation has collapsed is not neutral: it is the
best remaining opportunity being declined, every day, silently. Meanwhile a new survivor with
stronger evidence waits for a review cycle that exists only because somebody scheduled one.

So allocation is re-derived from CURRENT forward evidence on every run, and every alpha --
incumbent or candidate, six months old or six hours -- is scored by the same function. Age confers
no privilege and no penalty. It is not an input.

**CUMULATIVE P&L IS NOT THE CRITERION, AND THIS IS THE MOST IMPORTANT LINE IN THE MODULE.** A
strategy can be +€500 lifetime on luck while its forward expectation is now zero, and a new one can
be slightly negative on variance while carrying excellent evidence. Funding the first and starving
the second is the natural reading of a P&L table and it is backwards. The question is always:

    does continuing to allocate this capital have positive marginal expected log-growth,
    versus giving the same capital to the next-best use?

**WHY LOG-GROWTH AND NOT RETURN.** Two strategies with identical expected return are not
interchangeable if one is correlated with the book and the other is not: the uncorrelated one
raises the geometric mean by reducing variance drag, which is the only thing that compounds. So
correlation and uncertainty enter the score directly rather than as a later adjustment somebody
might skip.

**UNCERTAINTY SHRINKS, IT DOES NOT VETO.** An edge measured over few effective observations is
sized down in proportion to what is actually known about it, so a promising strategy earns real
exposure early and grows it as evidence accumulates. That is the whole point of a canary: learning
while earning rather than waiting to learn and then earning. The alternative -- zero until certain,
then full -- throws away the option value of the learning period and is why lifecycles that look
prudent lose to ones that look aggressive.

NOTHING HERE PLACES AN ORDER OR ARMS ANYTHING. It computes target weights and the reason for each.
Arming live trading remains the principal's act and the Tier-3 rail is untouched.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass

__all__ = [
    "MIN_MEANINGFUL_WEIGHT",
    "AlphaCandidate",
    "allocate",
    "score",
    "summarise",
]

#: Weights below this are reported as ZERO rather than as a tiny position. A 0.02% allocation is
#: an operational cost with no economic content -- it pays fees to express an opinion too small to
#: matter, which is the allocation equivalent of the sub-informative clip size the live ladder
#: already refuses.
MIN_MEANINGFUL_WEIGHT: float = 0.005

#: Shrinkage floor. Even the best-evidenced alpha keeps some estimation discount, because the
#: edge is an estimate and Kelly's penalty for over-betting an estimate is asymmetric.
MAX_CONFIDENCE: float = 0.85


@dataclass(frozen=True)
class AlphaCandidate:
    """One alpha competing for capital. Incumbency is deliberately not a field.

    `edge_bps` is the FORWARD expectation per unit of exposure, not the historical mean, and the
    distinction is the module's whole thesis: history is how the estimate was formed, not what is
    being bet on.
    """

    name: str
    edge_bps: float
    vol_bps: float
    #: Effective INDEPENDENT observations behind the estimate (`evidence_clock.effective_n`).
    effective_n: float
    #: Correlation to the currently-held book. 1.0 = a duplicate of what the desk already owns.
    correlation_to_book: float = 0.0
    #: Quote units this alpha can absorb before its own impact eats the edge. 0 = unmeasured.
    capacity: float = 0.0
    #: Realised execution quality, 0..1. Below 1 the simulator was optimistic about fills.
    execution_quality: float = 1.0
    state: str = "LIVE"
    #: Cumulative realised P&L. RECORDED AND NEVER SCORED -- present so a report can show it
    #: beside the decision it does not drive.
    lifetime_pnl: float = 0.0

    @property
    def measured(self) -> bool:
        return self.effective_n > 0 and self.vol_bps > 0

    @property
    def confidence(self) -> float:
        """Shrinkage from evidence: n/(n+k), capped. Not a gate -- a multiplier.

        k=50 sets the half-way point at 50 effective observations, which is where a Sharpe
        estimate stops being dominated by its own standard error. A strategy with 10 effective
        observations gets ~17% of its estimated edge, which is a real position rather than a
        veto -- and it grows as the canary produces fills.
        """
        if not self.measured:
            return 0.0
        return min(MAX_CONFIDENCE, self.effective_n / (self.effective_n + 50.0))


def score(c: AlphaCandidate) -> tuple[float, str]:
    """(marginal log-growth score, why). Negative means the capital is better used elsewhere.

    THE CORRELATION TERM IS NOT A PREFERENCE. `1 - rho` is what a duplicate of the book actually
    contributes to geometric growth: at rho=1 the alpha adds exposure and no diversification, so
    its marginal contribution is zero however good its standalone Sharpe looks.
    """
    if not c.measured:
        return 0.0, (f"{c.name}: UNMEASURED -- no effective observations or no volatility "
                     "estimate, so no forward claim exists. Zero weight is a statement about "
                     "evidence, not about the alpha")
    sharpe = c.edge_bps / c.vol_bps
    rho = max(0.0, min(1.0, abs(c.correlation_to_book)))
    exq = max(0.0, min(1.0, c.execution_quality))
    # Kelly-shaped: the geometric contribution of an estimated edge, discounted for what is not
    # yet known about it and for the part of it the book already holds.
    s = sharpe * c.confidence * (1.0 - rho) * exq
    if s <= 0:
        return s, (
            f"{c.name}: marginal score {s:+.4f} -- "
            + ("edge is not positive in expectation" if c.edge_bps <= 0 else
               f"rho {rho:.2f} to the book leaves nothing incremental" if rho >= 1.0 else
               "execution destroys the edge")
            + ". Capital here is the next-best opportunity being declined")
    return s, (
        f"{c.name}: score {s:+.4f} = sharpe {sharpe:+.3f} x confidence {c.confidence:.2f} "
        f"(n_eff {c.effective_n:.0f}) x independence {1 - rho:.2f} x execution {exq:.2f}")


def allocate(candidates: list[AlphaCandidate], *, total_risk: float = 1.0,
             ) -> dict[str, float]:
    """Target risk weights. EVERY candidate is re-scored; incumbency is not consulted.

    Weights are proportional to positive marginal score, so an alpha that is twice as good gets
    twice the risk -- and one whose forward expectation has gone gets zero the same day, without
    a review meeting. Capacity caps a weight where it is measured, because an allocation beyond
    what the alpha can absorb is an allocation to its own market impact.
    """
    scored = [(c, score(c)[0]) for c in candidates]
    positive = [(c, s) for c, s in scored if s > 0]
    total = sum(s for _c, s in positive)
    out: dict[str, float] = {c.name: 0.0 for c in candidates}
    if total <= 0:
        return out
    for c, s in positive:
        w = total_risk * s / total
        if c.capacity > 0:
            # Capacity is expressed in the same units as `total_risk` by the caller. Where it
            # binds, the excess is NOT redistributed silently -- see the note in `summarise`.
            w = min(w, c.capacity)
        out[c.name] = 0.0 if w < MIN_MEANINGFUL_WEIGHT else round(w, 5)
    return out


def summarise(candidates: list[AlphaCandidate], *, total_risk: float = 1.0) -> dict[str, object]:
    """Report shape. THE HEADLINE IS WHAT CHANGED HANDS, because that is the decision."""
    if not candidates:
        return {"alphas": 0, "headline": (
            "no candidates -- the book is empty, which is not the same as the book being safe. "
            "Idle capital is the best remaining opportunity being declined")}
    weights = allocate(candidates, total_risk=total_risk)
    rows = []
    for c in sorted(candidates, key=lambda x: -weights.get(x.name, 0.0)):
        s, why = score(c)
        rows.append({"alpha": c.name, "state": c.state, "weight": weights.get(c.name, 0.0),
                     "score": round(s, 5), "why": why,
                     "effective_n": c.effective_n, "rho_to_book": c.correlation_to_book,
                     "lifetime_pnl": c.lifetime_pnl})
    w_of = {str(r["alpha"]): float(weights.get(str(r["alpha"]), 0.0)) for r in rows}
    funded = [r for r in rows if w_of[str(r["alpha"])] > 0]
    defunded = [r for r in rows if w_of[str(r["alpha"])] == 0]
    allocated = sum(w_of.values())
    return {
        "alphas": len(candidates), "tally": dict(Counter(c.state for c in candidates)),
        "funded": len(funded), "defunded": len(defunded),
        "risk_allocated": round(allocated, 5),
        "risk_unallocated": round(max(0.0, total_risk - allocated), 5),
        "headline": (
            f"{len(funded)} of {len(candidates)} alphas funded; {len(defunded)} hold zero. "
            f"{max(0.0, total_risk - allocated):.1%} of the risk budget is UNALLOCATED -- idle "
            "capacity is the best remaining opportunity being declined, not prudence"
            if allocated < total_risk * 0.99 else
            f"{len(funded)} of {len(candidates)} alphas funded; risk budget fully allocated"),
        "rows": rows,
        "note": ("Age is not an input. Cumulative P&L is recorded and NOT scored: a strategy can "
                 "be lifetime-positive on luck while its forward expectation is zero, and a new "
                 "one slightly negative on variance while carrying excellent evidence. Where "
                 "capacity binds, the excess is left UNALLOCATED rather than pushed into the "
                 "next-best alpha -- silently over-funding a weaker mechanism because a stronger "
                 "one filled up is how a capacity limit becomes a sizing error."),
        "authority": "NONE. Computes target weights. Places nothing, arms nothing.",
    }


def render(candidates: list[AlphaCandidate], *, total_risk: float = 1.0) -> str:
    rep = summarise(candidates, total_risk=total_risk)
    lines = [str(rep["headline"])]
    rows = rep.get("rows")
    for r in rows if isinstance(rows, list) else []:
        w = float(str(r["weight"]))
        lines.append(f"  {w:>7.2%}  {r['why']}")
    return "\n".join(lines)


def kelly_fraction(edge_bps: float, vol_bps: float, confidence: float, *,
                   cap: float = 0.25) -> float:
    """Quarter-Kelly-shaped fraction on the SHRUNK edge, capped.

    The shrinkage is applied to the edge BEFORE the Kelly ratio rather than to the result, because
    Kelly's penalty is asymmetric: over-betting an over-estimated edge loses more growth than
    under-betting the same edge gains. Shrinking first is the conservative order of operations and
    it is not the intuitive one.
    """
    if vol_bps <= 0:
        return 0.0
    f = (edge_bps * max(0.0, min(1.0, confidence))) / (vol_bps ** 2) * vol_bps
    return max(0.0, min(cap, f * 0.25))


def half_life_days(edge_now: float, edge_then: float, days: float) -> float | None:
    """Observed decay half-life. None when the edge is not decaying or cannot be measured.

    None rather than infinity: a caller that formats infinity prints something meaningless, while
    None forces the report to say the edge has not been shown to decay -- which is the honest
    statement and also not a promise that it will not.
    """
    if days <= 0 or edge_then <= 0 or edge_now <= 0 or edge_now >= edge_then:
        return None
    ratio = edge_now / edge_then
    return days * math.log(0.5) / math.log(ratio)
