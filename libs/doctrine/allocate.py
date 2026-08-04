"""HIERARCHICAL GLOBAL -> LOCAL ALLOCATION -- the VIP rule, and nothing starves behind it.

THE PROBLEM THE PRINCIPAL NAMED EXACTLY. Research wants compute, execution wants latency, mining
wants bandwidth. Each is individually correct -- each really does raise its own marginal
contribution -- and together they can lower total growth, because every one of them is optimising
a local objective while the thing that compounds is the global one. Letting subsystems bid
independently is how a desk ends up with nine locally-optimal subsystems and a worse portfolio.

    Global Ê[log W]  >  sum of local objectives

THE VIP RULE, AND THE HALF OF IT THAT USUALLY GETS DROPPED. The global optimiser enters first: the
single highest ΔÊ[log W]/ΔR action takes what it needs before anything else is considered. That
half is easy. The half that decides whether this is a growth mechanism or a bureaucracy is what
happens NEXT -- every remaining subsystem immediately expands to its maximum feasible operating
point inside the residual budget, in descending order of marginal contribution, until no
positive-return capacity remains. Idle compute, idle engineering hours, idle governance bandwidth
and idle capital are OPTIMISATION FAILURES whenever positive expected contribution exists.

    PRIORITY DETERMINES ORDER, NEVER PERMANENT DEPRIVATION.

A subsystem that loses the top slot is not defunded, it is second in line this cycle. This module
tracks consecutive misses and reports starvation explicitly, because "always ranked fourth, four
resources available, never once funded" is a bug that a pure argmax will never notice about
itself -- every individual cycle looked correct.

THE BOTTLENECK ALWAYS SCALES UPWARD. When discovery outruns conversion the optimisation target is
max Q_C, never min Q_D. Surplus discovery is INVENTORY, not waste: an unconverted hypothesis
costs storage, and a hypothesis never generated costs whatever it would have been worth, forever.
Throttling discovery to make a backlog chart look tidy is the single most expensive tidying a
research desk can do.

Pure, dependency-free.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from libs.doctrine.estimate import ADMIT_Z, Estimate, adjusted

__all__ = [
    "STARVATION_CYCLES",
    "Action",
    "Ledger",
    "allocate",
    "bottleneck_expansion",
    "elasticity_shift",
    "meta_learning_rate",
]

#: Consecutive cycles a positive-contribution subsystem may go unfunded before it is reported as
#: STARVED. Three, because one miss is priority working and two is a busy week -- but a positive
#: contributor that has waited three cycles is being permanently deprived by a rule that thinks
#: it is merely ordering, and no single cycle's argmax can see that.
STARVATION_CYCLES = 3


@dataclass(frozen=True)
class Action:
    """One admissible claim on the limiting resource this cycle."""

    name: str
    #: Marginal contribution to E[log W] if funded. An ESTIMATE, never a number.
    contribution: Estimate
    #: Units of the limiting resource required (compute-hours, engineer-days, dollars...).
    cost: float
    subsystem: str = ""
    information_gain: float = 0.0     # the tie-break when contributions are indistinguishable

    @property
    def density(self) -> float:
        """ΔÊ[log W] / ΔR -- the ratio the directive ranks on."""
        return float(self.contribution.value) / max(float(self.cost), 1e-12)


@dataclass
class Ledger:
    """Who has gone unfunded, and for how long. The anti-starvation memory."""

    misses: dict[str, int] = field(default_factory=dict)

    def record(self, considered: list[str], funded: list[str]) -> None:
        for name in considered:
            self.misses[name] = 0 if name in funded else self.misses.get(name, 0) + 1

    def starved(self, *, cycles: int = STARVATION_CYCLES) -> list[str]:
        return sorted(k for k, v in self.misses.items() if v >= cycles)


def allocate(actions: list[Action], budget: float, *, brier: float | None = None,
             ledger: Ledger | None = None) -> dict[str, Any]:
    """Global optimum first, then everyone else to their maximum feasible point.

    SIMULTANEOUS, NOT PAIRWISE. Every admissible action competes against every other in one
    ranking. Pairwise comparison is order-dependent and can hand the budget to a locally-good
    action that a third option dominates -- the directive says "the complete set of all
    admissible actions", and that is what this takes.

    RANKED BY DENSITY, ΔÊ[log W]/ΔR, not by total contribution. A large action that consumes the
    entire budget for a mediocre rate loses to three efficient ones, which is the whole reason the
    limiting resource appears in the denominator.

    UNSPENT BUDGET WITH POSITIVE-CONTRIBUTION CANDIDATES WAITING IS REPORTED AS A FAILURE, in
    those words. Under-utilisation is not prudence: idle capacity that could have compounded is a
    real, permanent, uncollectable cost, and it is invisible precisely because nothing bad happens
    when it occurs.

    STARVATION OUTRANKS DENSITY. A positive contributor that has waited STARVATION_CYCLES is
    promoted ahead of the queue -- priority is meant to decide ORDER, and without this it quietly
    decides entitlement instead.
    """
    admissible = [a for a in actions if a.contribution.value > 0]
    rejected = [{"name": a.name, "reason": "non-positive expected contribution"}
                for a in actions if a.contribution.value <= 0]

    starved = set(ledger.starved()) if ledger else set()
    ranked = sorted(
        admissible,
        key=lambda a: (a.name not in starved, -adjusted(a.contribution, brier=brier) /
                       max(a.cost, 1e-12), -a.information_gain))

    funded: list[Action] = []
    spent = 0.0
    deferred: list[dict[str, Any]] = []
    for a in ranked:
        if spent + a.cost <= budget:
            funded.append(a)
            spent += a.cost
        else:
            deferred.append({"name": a.name, "cost": a.cost,
                             "density": round(a.density, 6),
                             "reason": "budget exhausted this cycle -- DEFERRED, not defunded"})

    residual = round(budget - spent, 6)
    if ledger is not None:
        ledger.record([a.name for a in actions], [a.name for a in funded])

    unspent_with_waiting = residual > 0 and deferred
    return {
        "vip": funded[0].name if funded else None,
        "funded": [a.name for a in funded],
        "spent": round(spent, 6),
        "residual_budget": residual,
        "deferred": deferred,
        "rejected": rejected,
        "starved": sorted(starved),
        "note": ("global optimum first, then every remaining subsystem expands to its maximum "
                 "feasible point inside the residual. Priority decides ORDER, never permanent "
                 "deprivation -- a deferred action is second in line, not defunded."),
        "failure": (
            "IDLE CAPACITY WITH POSITIVE-CONTRIBUTION WORK WAITING. The residual could not fit "
            "the next action whole; split it, or raise the budget. Unspent capacity that could "
            "have compounded is a permanent uncollectable cost and nothing bad visibly happens "
            "when it occurs, which is why it has to be reported rather than noticed."
            if unspent_with_waiting else ""),
        "starvation_alert": (
            f"STARVED (>= {STARVATION_CYCLES} consecutive cycles unfunded while positive): "
            f"{sorted(starved)}. Promoted ahead of density this cycle. No subsystem capable of "
            "raising E[log W] may be permanently neglected."
            if starved else ""),
    }


def elasticity_shift(marginal: Mapping[str, Estimate],
                     second_derivative: Mapping[str, float]) -> dict[str, Any]:
    """Diminishing returns move MORE resource, never ALL of it.

    THE WORD "MORE" IS THE ENTIRE DESIGN. A subsystem whose second derivative has gone negative
    is saturating -- but it is still contributing, and moving its whole budget to the current
    best-marginal subsystem would (a) drive that one into its own saturation immediately and
    (b) destroy the saturating subsystem's ability to recover when conditions change. Gradual
    reallocation tracks a moving optimum; wholesale reallocation oscillates around it forever and
    pays a switching cost on every swing.
    """
    saturating = sorted(k for k, v in second_derivative.items() if float(v) < 0)
    growing = sorted((k for k in marginal if float(second_derivative.get(k, 0.0)) >= 0),
                     key=lambda k: -marginal[k].value)
    return {
        "saturating": saturating,
        "growing": growing,
        "shift_from": saturating,
        "shift_to": growing[:3],
        "note": ("shift MORE, never ALL. A saturating subsystem is still contributing, and "
                 "wholesale reallocation drives the receiving subsystem straight into its own "
                 "saturation while destroying the sender's ability to recover."),
        "blocked": ("" if growing else
                    "every subsystem is saturating -- the binding constraint is not allocation, "
                    "it is TOTAL RESOURCE. The answer is to acquire more, not to reshuffle."),
    }


def bottleneck_expansion(discovery_rate: float, conversion_rate: float) -> dict[str, Any]:
    """When discovery outruns conversion, the target is max Q_C. NEVER min Q_D.

    ZERO ARTIFICIAL THROTTLING. No subsystem may reduce mining, hypothesis generation, feature
    discovery, literature mining or source expansion because downstream utilisation is
    incomplete. Surplus discovery is INVENTORY: an unconverted hypothesis costs storage, and a
    hypothesis never generated costs whatever it would have been worth, permanently. Those are
    not comparable magnitudes, and only one of them shows up on a chart.
    """
    qd, qc = float(discovery_rate), float(conversion_rate)
    backlog = qd - qc
    return {
        "discovery_rate": round(qd, 4),
        "conversion_rate": round(qc, 4),
        "backlog": round(backlog, 4),
        "bottleneck": "conversion" if backlog > 0 else ("discovery" if backlog < 0 else "balanced"),
        "target": ("EXPAND CONVERSION (automation, collector generation, validation, engineering, "
                   "compute, orchestration). Discovery does NOT contract."
                   if backlog > 0 else
                   "EXPAND DISCOVERY -- conversion capacity is idle, which is capacity paid for "
                   "and unused"),
        "forbidden": ("throttling discovery to clear the backlog. The backlog is inventory; "
                      "reducing Q_D converts a storage cost into a permanent opportunity cost."
                      if backlog > 0 else ""),
        "note": ("every discovered item ends converted, validated, deployed, or archived WITH a "
                 "quantitative justification -- never discarded for want of conversion capacity"),
    }


def meta_learning_rate(history: list[float]) -> dict[str, Any]:
    """d/dt of Ê[log W] -- optimise how fast the desk improves, not only where it stands.

    THE SECOND-ORDER TERM, and the one a first-order objective silently drops. A desk at 0.02
    improving by 0.001/cycle overtakes a desk sitting at 0.05 flat, and every cycle spent raising
    the RATE compounds into every cycle after it. Measured over the observed history rather than
    asserted, and reported with its own sample size, because a rate estimated from three points
    is a slope through noise.
    """
    if len(history) < 3:
        return {"state": "INSUFFICIENT-HISTORY", "n": len(history),
                "note": "a rate estimated from fewer than 3 points is a slope through noise"}
    n = len(history)
    xs = list(range(n))
    mx = sum(xs) / n
    my = sum(history) / n
    denom = sum((x - mx) ** 2 for x in xs) or 1e-12
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, history, strict=True)) / denom
    resid = [y - (my + slope * (x - mx)) for x, y in zip(xs, history, strict=True)]
    sse = sum(r * r for r in resid)
    se = ((sse / max(1, n - 2)) / denom) ** 0.5
    est = Estimate(slope, se, n, "d(E[log W])/dt")
    return {
        "state": "MEASURED",
        "rate": round(slope, 6),
        "se": round(se, 6),
        "n": n,
        "improving": est.significant_positive(ADMIT_Z),
        "note": ("the rate of improvement is what compounds into every future cycle. A desk at "
                 "0.02 improving by 0.001/cycle overtakes one sitting at 0.05 flat."
                 if est.significant_positive(ADMIT_Z) else
                 "improvement is NOT statistically distinguishable from flat. The desk's "
                 "capability is not currently compounding, which is a first-order finding about "
                 "the meta-layer rather than a rounding error."),
    }
