"""Trajectories: evolve the RESEARCH PATH, and mutate the step that actually failed.

THE IDEA WORTH STEALING (QuantaAlpha). A candidate is not one object, it is a PATH -- evidence,
mechanism, measurement, condition, horizon, implementation, experiment, verdict. When it dies,
one of those steps killed it, and the others may have been fine. Regenerating the whole path
throws away the work that was correct; mutating a random step is a lottery. Locating the failed
step and mutating THAT is the difference between search and evolution.

WHY THIS DESK NEEDS IT SPECIFICALLY. The anomaly miner now proposes tens of thousands of cells and
the adapters attach candidate causes to most of them. That is supply, not progress: without credit
assignment every failure teaches nothing and the next generation repeats it at scale. The desk has
already measured what undirected volume produces -- 1,607 candidates tested, 66 certificates, and
zero of the eight uncashable ones caught until they were counted by hand.

CREDIT ASSIGNMENT IS THE WHOLE MECHANISM. Each stage records which step it judged, so a verdict
names its own cause: a gate-0 refusal indicts MEASUREMENT, a deflated-Sharpe failure indicts the
CONDITION's width, a stress-cost failure indicts the HORIZON, a walk-forward failure indicts the
mechanism's stability. `mutation_target` reads the failure class and returns the step to change --
never a random one, and never the whole path.

WHAT IT REFUSES. A mutation may not touch a step downstream of the failure, because that step's
evidence was never reached and mutating it would be guessing. It may not resurrect a fingerprint
the store has already KILLED, which is how a search loops forever on the same dead idea. And no
mutation promotes anything: every descendant re-enters at PROPOSED and walks the same ten gates.

PARENT SELECTION IS PROBABILISTIC, NOT GREEDY (AlphaPROBE). Choosing the best-scoring parent
collapses the search onto one lineage; choosing uniformly wastes the information the DAG holds.
Parents are drawn with weight proportional to fertility x uncertainty x novelty, so a line that
has produced survivors is favoured WITHOUT the search abandoning ground it has not yet explored.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime
from typing import Any

from libs.research import research_state as store

#: The steps of a research path, in order. A failure at step i tells you nothing about step i+1,
#: because step i+1 never ran.
STEPS = ("evidence", "mechanism", "measurement", "condition", "horizon",
         "implementation", "experiment")

#: Failure class -> the step it indicts. Derived from what each gate actually tests, so the
#: mapping is a claim about the gates rather than a convention.
FAILURE_STEP: dict[str, str] = {
    "economic_prior": "mechanism",        # no named cause, or one this desk cannot measure
    "measurement": "measurement",         # the observable was a proxy too weak to attribute
    "in_sample_screen": "condition",      # the condition does not separate anything
    "deflated_sharpe": "condition",       # it separates, but not beyond the search's width
    "pbo": "condition",                   # the split that worked was the one that was fitted
    "reality_check_spa": "condition",     # beaten by the best of the other trials
    "cpcv": "horizon",                    # unstable across purged folds -- wrong holding period
    "walk_forward": "mechanism",          # worked then stopped: the cause was not durable
    "stress_costs": "horizon",            # the edge is inside the cost of holding it
    "lockbox": "mechanism",               # did not survive untouched data
    "expected_value": "horizon",          # positive but not worth the exposure time
    "untradeable": "evidence",            # the instrument itself was never ownable
}


@dataclass(frozen=True)
class Trajectory:
    """One research path, whole. Frozen: a mutation returns a NEW trajectory."""

    steps: dict[str, Any]
    generator: str
    generation: int = 0
    parent: str | None = None
    mutation_op: str = ""
    failure_class: str = ""
    failed_step: str = ""
    history: tuple[dict[str, Any], ...] = field(default_factory=tuple)

    def fingerprint(self) -> str:
        """Identity over the steps that make this a DIFFERENT experiment."""
        blob = json.dumps({k: self.steps.get(k) for k in STEPS}, sort_keys=True, default=str)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:20]

    def as_record(self) -> dict[str, Any]:
        d = asdict(self)
        d["fingerprint"] = self.fingerprint()
        return d


def from_anomaly(anomaly: dict[str, Any], explanation: dict[str, Any],
                 generator: str = "anomaly_miner") -> Trajectory:
    """Build a trajectory from a mined anomaly and one of its candidate explanations."""
    return Trajectory(
        generator=generator,
        steps={
            "evidence": {"symbol": anomaly.get("symbol"), "against": anomaly.get("against"),
                         "n": anomaly.get("n"), "t_stat": anomaly.get("t_stat")},
            "mechanism": explanation.get("mechanism"),
            "measurement": explanation.get("measurement_class"),
            "condition": anomaly.get("condition"),
            "horizon": anomaly.get("horizon"),
            "implementation": None,       # the compiler's job, under its own rule
            "experiment": None,           # the ten gates
        })


def mutation_target(failure_class: str) -> str:
    """Which step to change, given how this trajectory died. Never a guess.

    An unrecognised failure indicts MECHANISM -- the earliest step whose revision is always
    meaningful -- rather than defaulting to whatever is cheapest to change. Mutating a late step
    for an unknown reason is how a search spends a generation learning nothing.
    """
    return FAILURE_STEP.get(str(failure_class or "").strip().lower(), "mechanism")


def mutate(t: Trajectory, failure_class: str, proposal: Any, *,
           op: str = "surgical") -> Trajectory | None:
    """Change the step the failure indicts, keeping everything upstream. None when refused.

    REFUSES A DOWNSTREAM MUTATION. If the path died at `condition`, its `implementation` and
    `experiment` never ran, so there is no evidence about them to act on and changing them would
    be superstition wearing the shape of a method.
    """
    step = mutation_target(failure_class)
    if step not in STEPS:
        return None
    idx = STEPS.index(step)
    if t.failed_step and STEPS.index(t.failed_step) < idx:
        return None                       # never mutate downstream of the real failure
    new_steps = dict(t.steps)
    new_steps[step] = proposal
    for later in STEPS[idx + 1:]:
        new_steps[later] = None           # everything after the change must be re-derived
    child = replace(
        t, steps=new_steps, generation=t.generation + 1, parent=t.fingerprint(),
        mutation_op=f"{op}:{step}", failure_class="", failed_step="",
        history=(*t.history, {"at": datetime.now(UTC).isoformat(timespec="seconds"),
                              "died_of": failure_class, "mutated": step}))
    if store.get(child.fingerprint()) is not None:
        return None                       # already tried; a search that revisits is not searching
    return child


def crossover(a: Trajectory, b: Trajectory, steps: tuple[str, ...]) -> Trajectory | None:
    """Take `steps` from `b` into `a`. Segment recombination, not blind averaging."""
    if not steps or any(s not in STEPS for s in steps):
        return None
    new_steps = dict(a.steps)
    for s in steps:
        new_steps[s] = b.steps.get(s)
    first = min(STEPS.index(s) for s in steps)
    for later in STEPS[first + 1:]:
        if later not in steps:
            new_steps[later] = None
    child = replace(a, steps=new_steps, generation=max(a.generation, b.generation) + 1,
                    parent=a.fingerprint(), mutation_op=f"crossover:{'+'.join(steps)}",
                    failure_class="", failed_step="")
    return None if store.get(child.fingerprint()) is not None else child


def parent_weights(rows: list[dict[str, Any]]) -> list[float]:
    """fertility x uncertainty x novelty, for probabilistic parent draw.

    GREEDY SELECTION COLLAPSES THE SEARCH. Always breeding the best-scoring line abandons every
    other, and this desk has already measured what one dominant line costs: six funded mechanisms,
    a family cap binding at 40%, and concentration worth 4x more to relax than heat is to raise.
    Uncertainty is highest where a line has been tried LEAST, so a young line competes with a
    proven one instead of being buried by it.
    """
    out = []
    for r in rows:
        tried = float(r.get("proposed") or 0)
        cashed = float(r.get("cashed") or 0)
        fertility = (cashed + 0.5) / (tried + 1.0)
        uncertainty = 1.0 / math.sqrt(tried + 1.0)
        novelty = 1.0 / (1.0 + float(r.get("recent_children") or 0))
        out.append(max(1e-6, fertility * uncertainty * novelty))
    return out


def draw_parents(rows: list[dict[str, Any]], k: int, *, seed: int | None = None
                 ) -> list[dict[str, Any]]:
    """Draw k parents without replacement, weighted. Deterministic when seeded."""
    if not rows:
        return []
    # Not cryptographic and must not be: parent selection has to be REPRODUCIBLE from a seed, so
    # a research generation can be replayed exactly when its results are questioned.
    rng = random.Random(seed)  # noqa: S311
    pool, weights = list(rows), parent_weights(rows)
    picked: list[dict[str, Any]] = []
    for _ in range(min(k, len(pool))):
        total = sum(weights)
        if total <= 0:
            break
        r = rng.random() * total
        acc = 0.0
        for i, w in enumerate(weights):
            acc += w
            if acc >= r:
                picked.append(pool.pop(i))
                weights.pop(i)
                break
    return picked


def register(t: Trajectory, *, trials: int = 0) -> bool:
    """Put a trajectory into the canonical store, with its lineage edge."""
    new = store.record(
        t.fingerprint(), kind="trajectory", generator=t.generator, payload=t.as_record(),
        mechanism=str(t.steps.get("mechanism") or "") or None,
        symbol=str((t.steps.get("evidence") or {}).get("symbol") or "") or None,
        trials=trials)
    if t.parent:
        store.link(t.fingerprint(), t.parent, t.mutation_op or "derived")
    return new
