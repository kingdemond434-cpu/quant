"""THE RESEARCHER MARKET AND THE COMPUTE OPERATING SYSTEM (Tier S layers 4, 8, 13, 40).

Every research process (a leg, a department, a miner, a sandbox) competes for budget. Its record
is kept as Beta posteriors over the stages the desk can count:

    P(novel)               share of its candidates that were new species (novelty gate)
    P(pass cheap)          share that survived the cheap falsifier
    P(pass full)           share that cleared the full gauntlet
    P(forward holds)       share of its certificates whose forward clock agrees

and its measured cost in every resource the host meters -- CPU seconds, peak RAM, LLM tokens.
Its VALUE per hour is

    E[validated independent information] = rate x P(novel) x P(pass full) x P(forward holds)
                                           x mean novelty (ancestry-discounted)

and its PRICE is that value divided by a resource-weighted cost. Allocation is Thompson sampling
over the posteriors (so an under-explored researcher gets a real chance) solved as a MILP over the
resource budgets with `scipy.optimize.milp` -- a deterministic operations-research solver doing the
allocation, not a heuristic.

THE STANDING RULE: NEVER STARVE A MINER. Every researcher keeps its FLOOR (its current budget, or a
scout minimum): the market only distributes the HEADROOM above the floors, and the total never
falls. Researchers whose productivity deteriorates stop receiving headroom; they are never cut
below their floor by this organ.

BLIND COHORTS AND INDEPENDENT DISCOVERY (layer 4). Researchers are tagged with a cohort; a
mechanism found by two cohorts that cannot read each other's output is INDEPENDENTLY DISCOVERED,
and that event is counted separately -- independent rediscovery is stronger evidence than 25
agents copying the same idea.
"""
from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np

STAGES: tuple[str, ...] = ("novel", "cheap", "full", "forward")
RESOURCES: tuple[str, ...] = ("cpu_s", "ram_mb", "tokens")
#: relative price of one unit of each resource (a CPU-second is the numeraire)
RESOURCE_PRICE = {"cpu_s": 1.0, "ram_mb": 0.002, "tokens": 0.0005}


@dataclass
class Researcher:
    name: str
    cohort: str = ""
    epistemology: str = ""
    candidates: int = 0
    successes: dict[str, int] = field(default_factory=dict)
    trials: dict[str, int] = field(default_factory=dict)
    cost: dict[str, float] = field(default_factory=dict)
    hours: float = 0.0
    mean_novelty: float = 1.0
    floor_s: float = 60.0
    #: backtest-vs-reality haircut from prediction accounting (1 = honest, <1 = exaggerates)
    honesty: float = 1.0

    def posterior(self, stage: str) -> tuple[float, float]:
        s = self.successes.get(stage, 0)
        n = self.trials.get(stage, 0)
        return 1.0 + s, 1.0 + max(0, n - s)

    def mean(self, stage: str) -> float:
        a, b = self.posterior(stage)
        return a / (a + b)

    def rate(self) -> float:
        return self.candidates / self.hours if self.hours > 0 else 0.0

    def value(self, draws: Mapping[str, float] | None = None) -> float:
        p = 1.0
        for st in STAGES:
            p *= (draws or {}).get(st, self.mean(st))
        return self.rate() * p * max(0.0, self.mean_novelty) * max(0.0, self.honesty)

    def unit_cost(self) -> float:
        if self.hours <= 0:
            return 1.0
        c = sum(RESOURCE_PRICE[r] * self.cost.get(r, 0.0) for r in RESOURCES) / self.hours
        return max(c, 1e-6)


def thompson(researchers: Sequence[Researcher], rng: np.random.Generator) -> dict[str, float]:
    out: dict[str, float] = {}
    for r in researchers:
        draws = {st: float(rng.beta(*r.posterior(st))) for st in STAGES}
        out[r.name] = r.value(draws) / r.unit_cost()
    return out


def allocate(researchers: Sequence[Researcher], headroom_s: float, *, seed: int = 0,
             max_share: float = 0.35, samples: int = 64) -> dict[str, Any]:
    """Split `headroom_s` CPU-seconds above everyone's floor. Thompson draws average the price;
    a MILP picks integer 10-second slices maximising priced value with a per-researcher cap
    (max_share) so no single researcher can take the whole hour."""
    rng = np.random.default_rng(seed)
    names = [r.name for r in researchers]
    if not researchers:
        return {"allocations": {}, "headroom_s": headroom_s}
    prices = np.zeros(len(researchers))
    for _ in range(samples):
        d = thompson(researchers, rng)
        prices += np.array([d[n] for n in names])
    prices /= samples
    slice_s = 10.0
    n_slices = int(max(0.0, headroom_s) // slice_s)
    alloc = np.zeros(len(researchers))
    solver = "none"
    if n_slices > 0:
        try:
            from scipy.optimize import Bounds, LinearConstraint, milp
            cap = max(1, math.ceil(max_share * n_slices))
            # diminishing returns: value of k slices ~ price * sqrt(k); linearise with
            # per-slice decreasing marginal value by splitting each researcher into cap pieces
            m = len(researchers)
            piece_val = []
            for i in range(m):
                for k in range(cap):
                    piece_val.append(prices[i] * (math.sqrt(k + 1) - math.sqrt(k)))
            c = -np.asarray(piece_val)
            a_tot = np.ones((1, m * cap))
            res = milp(c=c, constraints=[LinearConstraint(a_tot, 0, n_slices)],
                       integrality=np.ones(m * cap), bounds=Bounds(0, 1))
            if res.success and res.x is not None:
                x = np.round(res.x).reshape(m, cap)
                alloc = x.sum(axis=1) * slice_s
                solver = "scipy.milp"
        except Exception:
            solver = "proportional"
        if solver != "scipy.milp":
            w = np.clip(prices, 0, None)
            w = w / w.sum() if w.sum() > 0 else np.ones_like(w) / len(w)
            alloc = np.floor(w * n_slices) * slice_s
            solver = "proportional"
    rows = {}
    for i, r in enumerate(researchers):
        rows[r.name] = {"floor_s": r.floor_s, "headroom_s": float(alloc[i]),
                        "budget_s": r.floor_s + float(alloc[i]),
                        "price": round(float(prices[i]), 8),
                        "posteriors": {st: round(r.mean(st), 4) for st in STAGES},
                        "cohort": r.cohort, "epistemology": r.epistemology,
                        "honesty": r.honesty, "unit_cost": round(r.unit_cost(), 4)}
    total_floor = sum(r.floor_s for r in researchers)
    return {"allocations": rows, "headroom_s": headroom_s, "solver": solver,
            "total_floor_s": total_floor, "total_budget_s": total_floor + float(alloc.sum()),
            "rule": "floors are never cut; only headroom above them is priced"}


def independent_discoveries(sightings: Iterable[tuple[str, str]],
                            cohorts: Mapping[str, str]) -> dict[str, Any]:
    """sightings: (researcher, mechanism_species). A species found by >= 2 blind cohorts."""
    by_species: dict[str, set[str]] = {}
    for researcher, species in sightings:
        c = cohorts.get(researcher, researcher)
        by_species.setdefault(species, set()).add(c)
    multi = {s: sorted(c) for s, c in by_species.items() if len(c) >= 2}
    return {"n_species": len(by_species), "independently_discovered": len(multi),
            "examples": dict(sorted(multi.items())[:20])}
