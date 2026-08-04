"""CONTRIBUTION ESTIMATES -- dÊ[log W]/dC_i per subsystem, with the provenance attached.

THE BOTTLENECK THIS CLOSES, NAMED BY THE ALLOCATOR ITSELF. run_allocator has reported the same
binding constraint every cycle it has ever run: "CONTRIBUTION ESTIMATES". Twelve of twenty
subsystems can point at an artifact; none of them can state what a marginal unit of resource does
to E[log W]. P4 says the marginal resource goes to argmax_i |dE[log W]/dC_i|, and that expression
is not computable when no term in it has ever been computed. Every allocation the desk has made
was therefore a guess wearing a formula.

WHY ABSENCE WAS THE WRONG ANSWER, AND SO IS PRETENDING. The desk has never traded, so three
subsystems -- costs, execution, portfolio -- have no live observations at all. The response so far
was to report them as BLOCKED and exclude them from ranking. That is timidity in the exact form
P23 forbids: refusing to estimate is not neutral, it silently assigns those subsystems a
contribution of zero and routes every marginal resource elsewhere forever. But asserting a
live-quality number from a backtest is the opposite failure, and P8 forbids that one.

THE RESOLUTION IS PROVENANCE. An estimate is admitted from whatever evidence exists, and the
evidence's PROVENANCE inflates its standard error. A backtest-derived contribution is a real
estimate with wide error bars; a never-executed one is an estimate so wide it cannot clear any
action threshold by construction. Both are strictly more informative than absence, because both
appear in the ranking with an honest width instead of being silently treated as zero.

SE IS INFLATED, THE VALUE IS NEVER SHRUNK. Multiplying the point estimate toward zero would be
double-counting -- it corrupts the quantity being estimated to express doubt ABOUT that quantity,
and it makes a confident-but-unproven claim indistinguishable from a measured-and-small one.
Widening the interval says exactly the right thing: we believe this is the value, and we do not
yet know it well.

Pure, dependency-free, no I/O. The organs that OWN each subsystem write their own contribution;
this module only defines what one is and how they compare.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from libs.doctrine.estimate import ADMIT_Z, Estimate, uncertainty_penalty

__all__ = [
    "PROVENANCE",
    "Contribution",
    "credibility",
    "rank",
    "unestimated",
]

#: Evidence class -> the factor its standard error is MULTIPLIED by. 1.0 means the measurement
#: speaks for itself; larger means the number is real but the desk should not act on it as though
#: it were observed. The ladder is ordered and the gaps are deliberate rather than smooth: each
#: step down removes a specific thing that makes an estimate trustworthy, and the sizes say which
#: removals matter most.
PROVENANCE: dict[str, tuple[float, str]] = {
    # Observed in production with real money at risk. Nothing is inflated: this IS the quantity.
    "LIVE": (1.0,
             "observed in production -- the estimand itself, not a proxy for it"),
    # Real market data, real signals, no capital. Loses fill realism and adverse selection, which
    # is exactly the term that makes execution estimates optimistic.
    "SHADOW": (1.6,
               "real-time on real data but unfilled -- loses adverse selection and queue "
               "position, the two terms that make paper execution flattering"),
    # Historical replay. Loses everything shadow loses, plus the market never reacted to us and
    # the researcher chose the period.
    "BACKTEST": (2.5,
                 "historical replay -- the market never responded to our orders and the sample "
                 "was chosen after the fact; both bias the estimate the same direction"),
    # Reasoned from mechanism, structure or a comparable system. A real belief, not a measurement.
    "PRIOR": (4.0,
              "reasoned from mechanism or a comparable system -- a belief with a basis, which is "
              "worth strictly more than treating the subsystem as contributing zero"),
    # The producing code path has never run. Included so the subsystem is RANKED rather than
    # silently zeroed, and inflated hard enough that it can never clear an action threshold.
    "NEVER_EXECUTED": (12.0,
                       "the producing path has never run once. Ranked so the gap stays visible "
                       "and costed, never so it can be acted upon as evidence"),
}


def credibility(provenance: str) -> tuple[float, str]:
    """Inflation factor and its justification. An unknown provenance is treated as the WORST case
    rather than the best -- a typo must not silently promote an estimate to live quality."""
    return PROVENANCE.get(provenance.upper(), PROVENANCE["NEVER_EXECUTED"])


@dataclass(frozen=True)
class Contribution:
    """One subsystem's dÊ[log W]/dC, with everything needed to judge whether to act on it.

    `basis` is required and free-text on purpose: an estimate whose author cannot say what was
    measured is not an estimate, and the field is what stops this becoming a table of numbers
    nobody can audit six weeks later.
    """

    subsystem: str
    derivative: str          # e.g. "dE[log W] / d(hypotheses generated)"
    value: float             # point estimate, in E[log W] units per unit of resource
    se: float                # standard error BEFORE provenance inflation
    n: int                   # observations behind it
    provenance: str
    basis: str               # what was actually measured, in one sentence
    cost_unit: str = "cycle"
    tags: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.basis.strip():
            raise ValueError(
                f"{self.subsystem}: basis is required -- an estimate nobody can trace to a "
                "measurement is a number, and the allocator must never rank on those")
        if self.se < 0:
            raise ValueError(f"{self.subsystem}: standard error cannot be negative")
        # A PATH THAT HAS NEVER RUN CANNOT HAVE OBSERVATIONS. Caught by this module's own tests:
        # SE inflation multiplies a SELF-REPORTED standard error, so an author claiming se=0.0001
        # on a value of 99 sails through every credibility factor the ladder can apply. The
        # incoherence is in the n, not the width -- observations of what? -- and clamping it
        # silently would leave the same false confidence in the artifact for a reader to trust.
        if self.provenance.upper() == "NEVER_EXECUTED" and self.n > 0:
            raise ValueError(
                f"{self.subsystem}: provenance NEVER_EXECUTED with n={self.n}. A code path that "
                "has never executed cannot have observations behind it -- either the path HAS "
                "run (use PRIOR, BACKTEST, SHADOW or LIVE) or n is 0. Inflating the standard "
                "error cannot fix a fabricated sample size.")

    @property
    def factor(self) -> float:
        return credibility(self.provenance)[0]

    @property
    def why_inflated(self) -> str:
        return credibility(self.provenance)[1]

    def estimate(self) -> Estimate:
        """The Estimate the rest of the desk compares on -- SE already inflated by provenance.

        A zero-observation estimate keeps a positive width rather than a zero one: se=0 with n=0
        would read as infinite precision and would win every ranking it entered.
        """
        se = self.se * self.factor
        if self.n <= 0 or se <= 0:
            se = max(se, abs(self.value) * self.factor, 1e-9)
        return Estimate(self.value, se, max(self.n, 1), self.derivative)

    def actionable(self, z: float = ADMIT_Z) -> bool:
        """Is the evidence strong enough to MOVE resource toward this? NEVER_EXECUTED cannot
        reach this by construction, which is the point -- it stays visible without being
        mistaken for a finding."""
        return self.estimate().significant_positive(z)

    def density(self, closure_cost: float = 1.0,
                calibration_brier: float | None = None) -> float:
        """Uncertainty-penalised contribution per unit of cost -- the ranking quantity.

        Penalised BEFORE dividing by cost, so a wide estimate cannot buy its way up the ranking by
        being cheap. Cheapness is a reason to try something, never a reason to believe it.
        """
        est = self.estimate()
        lam = uncertainty_penalty(calibration_brier)
        adj = est.value - lam * est.se
        return adj / max(closure_cost, 1e-9)

    def to_dict(self) -> dict[str, Any]:
        est = self.estimate()
        return {
            "subsystem": self.subsystem,
            "derivative": self.derivative,
            "value": round(self.value, 6),
            "se_raw": round(self.se, 6),
            "se_effective": round(est.se, 6),
            "n": self.n,
            "provenance": self.provenance.upper(),
            "credibility_factor": self.factor,
            "why_inflated": self.why_inflated,
            "basis": self.basis,
            "cost_unit": self.cost_unit,
            "actionable": self.actionable(),
            "tags": list(self.tags),
        }


def rank(contributions: list[Contribution],
         costs: dict[str, float] | None = None,
         calibration_brier: float | None = None) -> list[dict[str, Any]]:
    """Subsystems ordered by penalised contribution density -- P4's argmax, made computable.

    Everything is ranked, including what cannot be acted on. A subsystem excluded from the
    ranking is a subsystem assigned zero, and zero is a much stronger claim than "unmeasured".
    """
    costs = costs or {}
    rows = []
    for c in contributions:
        cost = float(costs.get(c.subsystem, 1.0))
        rows.append({
            **c.to_dict(),
            "closure_cost": cost,
            "density": round(c.density(cost, calibration_brier), 6),
        })
    rows.sort(key=lambda r: (-r["density"], r["subsystem"]))
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return rows


def unestimated(all_subsystems: set[str],
                contributions: list[Contribution]) -> list[str]:
    """Subsystems with NO contribution at all -- the residual bottleneck, reported by name.

    Distinct from a NEVER_EXECUTED contribution, and the distinction is the whole point of having
    both: NEVER_EXECUTED is a subsystem whose owner has stated a belief and labelled it unproven,
    while this list is a subsystem nobody has said anything about. The first is instrumented; the
    second is the gap.
    """
    return sorted(all_subsystems - {c.subsystem for c in contributions})


def summarise(contributions: list[Contribution], all_subsystems: set[str]) -> dict[str, Any]:
    """The one-line state of P4: can the desk compute its own argmax yet?"""
    missing = unestimated(all_subsystems, contributions)
    live = [c for c in contributions if c.provenance.upper() == "LIVE"]
    actionable = [c for c in contributions if c.actionable()]
    total = max(1, len(all_subsystems))
    return {
        "subsystems": len(all_subsystems),
        "estimated": len(contributions),
        "estimated_pct": round(100.0 * len(contributions) / total, 1),
        "live_evidence": len(live),
        "actionable": len(actionable),
        "unestimated": missing,
        "argmax_computable": not missing,
        "note": (
            "every subsystem states a contribution, so argmax_i |dE[log W]/dC_i| is computable "
            "-- the remaining work is narrowing the error bars, not filling the table"
            if not missing else
            f"{len(missing)} subsystem(s) state no contribution at all, so P4's argmax is taken "
            "over a partial set and any allocation from it silently assigns the rest zero"),
    }


def widen_for_disagreement(base: Contribution, competing: list[float]) -> Contribution:
    """Widen an estimate when independent methods disagree about it.

    Two methods that agree tell you more than one; two that disagree tell you the SE was
    understated, not that the average is right. Averaging away the disagreement is how a desk
    reports precision it does not have -- so the spread is folded into the width instead.
    """
    if not competing:
        return base
    vals = [base.value, *competing]
    mean = sum(vals) / len(vals)
    var = sum((v - mean) ** 2 for v in vals) / max(1, len(vals) - 1)
    spread = math.sqrt(var)
    return Contribution(
        subsystem=base.subsystem, derivative=base.derivative, value=mean,
        se=math.sqrt(base.se ** 2 + spread ** 2), n=base.n, provenance=base.provenance,
        basis=(f"{base.basis} [widened for disagreement across {len(vals)} independent "
               f"methods, spread {spread:.4g}]"),
        cost_unit=base.cost_unit, tags=(*base.tags, "disagreement-widened"))
