"""Descent as a DAG, credit assigned to the step that failed, and the same idea refused twice.

WHY THIS EXISTS (principal blueprint, 2026-08-29)

Three separate ideas from the frontier collapse into one data structure, because all three need
the same thing: the full ancestry of a candidate, not just its parent.

  ALPHAPROBE -- ancestors are chosen by GLOBAL lineage information, not by parent performance.
      A branch whose parent looks mediocre can be the most fertile ground on the desk if its
      descendants keep surviving; a branch with a brilliant parent and forty dead children is
      exhausted. `retrieve_seeds` samples ancestors by posterior FERTILITY -- descendant survival
      per attempt -- so the search stops re-mining the one lucky parent.

  QUANTAALPHA -- credit assignment to the STEP, not the strategy. When a candidate fails, the
      useful question is not "was this strategy bad" but WHICH LINK broke: mechanism, observable,
      proxy, timing, implementation, parameterisation, or market transfer. Mutating the whole
      strategy after a timing failure throws away a sound mechanism. `assign_credit` records the
      failing step so `mutate_target` can name what to change.

  ALPHA JUNGLE -- frequent-subtree avoidance. If a thousand failed candidates all contain
      {momentum + volume acceleration + short horizon}, the desk should downweight that
      CONCEPTUAL SUBGRAPH rather than the exact formulas, which is the only version of the rule
      that generalises. `subtree_penalty` counts conceptual triples across the graveyard.

WHY THIS DESK NEEDS IT SPECIFICALLY. `discovered` produced 10,624 candidates for 7 certificates.
That is not a mechanism failing; it is one mechanism being re-parameterised ten thousand times
because nothing recorded that the previous 10,623 attempts explored the same ground. n_eff ~5.5
across 23 certificates is the same fact seen from the other end.

FAILURE CLASS DECIDES WHAT IS LEARNED, and this is the part that is easy to get backwards. An
`insufficient_power` failure teaches NOTHING about the mechanism -- the sample was small, which
is a fact about the test. Only validity failures reduce a branch's posterior. Getting this wrong
would abandon good mechanisms for having been tested too little, which is precisely how seven
families were labelled "confidently barren" on evidence from a validator later found broken in
four independent ways.
"""
from __future__ import annotations

import random
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from typing import Any

from libs.research.artifacts import POWER_FAILURES, VALIDITY_FAILURES

#: Research steps, in the order a candidate is built. `assign_credit` names ONE of these as the
#: failing link, and `mutate_target` changes only that one.
STEPS = ("mechanism", "observable", "proxy", "timing", "implementation",
         "parameterisation", "market_transfer")

#: Failure class -> the step it indicts. A mapping rather than a heuristic because the whole
#: value of credit assignment is that it is auditable: a reader must be able to check that a
#: `leakage` failure blamed the implementation and not the mechanism.
_CREDIT: dict[str, str] = {
    "invalid_mechanism": "mechanism",
    "no_effect": "mechanism",
    "leakage": "implementation",
    "execution_failure": "implementation",
    "cost_failure": "market_transfer",
    "redundant_alpha": "mechanism",
    "unstable_parameters": "parameterisation",
    "regime_instability": "timing",
    "insufficient_power": "",          # indicts NOTHING -- the test was small, not the idea
    "pbo": "parameterisation",
    "multiplicity": "parameterisation",
    "live_decay": "market_transfer",
}

#: A conceptual triple seen this many times among FAILURES is a rut, not a coincidence.
SUBTREE_RUT_AT = 25

#: Beta prior for branch fertility. Uniform is wrong here for the same reason it was wrong in the
#: funnel census -- an untried branch most likely resembles the desk's average branch, not a coin
#: flip -- but the prior is kept weak so a branch with real evidence dominates it quickly.
_PRIOR_STRENGTH = 3.0


@dataclass
class Node:
    """One artifact in the descent graph."""

    artifact_id: str
    hypothesis_id: str = ""
    parents: tuple[str, ...] = ()
    generation: int = 0
    mechanism: str = ""
    coordinate: str = ""
    concepts: tuple[str, ...] = ()          # conceptual components, for subtree avoidance
    mutation_operation: str = ""
    furthest_stage: str = "IDEA"
    survived: bool = False
    failure_class: str = ""
    failing_step: str = ""
    #: Live outcome, folded back when the sleeve retires or decays. THIS is what closes the loop:
    #: a family that certifies easily and then decays forward must lose future budget, and
    #: nothing else in the desk records that connection.
    live_decay_r: float | None = None


class LineageDAG:
    """The whole descent graph. Cycles are refused: descent is a DAG by definition."""

    def __init__(self) -> None:
        self.nodes: dict[str, Node] = {}
        self._children: dict[str, list[str]] = defaultdict(list)

    def add(self, node: Node) -> None:
        for p in node.parents:
            if p not in self.nodes:
                raise KeyError(
                    f"{node.artifact_id}: parent {p!r} is not in the graph. A node whose ancestry "
                    f"cannot be walked defeats the entire purpose -- global lineage retrieval, "
                    f"branch fertility and credit assignment all need the full path to the root.")
        if node.artifact_id in self.nodes:
            raise ValueError(f"{node.artifact_id} already present; artifacts are immutable")
        if self._would_cycle(node):
            raise ValueError(f"{node.artifact_id} would create a cycle; descent is a DAG")
        self.nodes[node.artifact_id] = node
        for p in node.parents:
            self._children[p].append(node.artifact_id)

    def _would_cycle(self, node: Node) -> bool:
        seen, q = set(), deque(node.parents)
        while q:
            cur = q.popleft()
            if cur == node.artifact_id:
                return True
            if cur in seen:
                continue
            seen.add(cur)
            q.extend(self.nodes[cur].parents if cur in self.nodes else ())
        return False

    def descendants(self, artifact_id: str) -> list[str]:
        out, q = [], deque(self._children.get(artifact_id, ()))
        seen = set()
        while q:
            cur = q.popleft()
            if cur in seen:
                continue
            seen.add(cur)
            out.append(cur)
            q.extend(self._children.get(cur, ()))
        return out

    def branch_stats(self, artifact_id: str) -> dict[str, Any]:
        """Fertility of a branch, counting only failures that actually indict it.

        `attempts_that_count` excludes power failures: a descendant that ran out of sample says
        nothing about whether this branch is fertile, and counting it would penalise exactly the
        branches the desk has explored least.
        """
        kids = self.descendants(artifact_id)
        survived = sum(1 for k in kids if self.nodes[k].survived)
        counted = [k for k in kids
                   if self.nodes[k].survived
                   or self.nodes[k].failure_class in VALIDITY_FAILURES]
        power_only = [k for k in kids if self.nodes[k].failure_class in POWER_FAILURES]
        decayed: list[float] = [d for k in kids
                                if (d := self.nodes[k].live_decay_r) is not None]
        return {
            "artifact_id": artifact_id,
            "descendants": len(kids),
            "survived": survived,
            "attempts_that_count": len(counted),
            "excluded_power_failures": len(power_only),
            "fertility": (survived / len(counted)) if counted else None,
            "mean_live_decay_r": (sum(decayed) / len(decayed)) if decayed else None,
            "n_live_observations": len(decayed),
        }


def assign_credit(failure_class: str) -> tuple[str, str]:
    """Which research STEP does this failure indict? Returns (step, why).

    An empty step means the failure indicts nothing -- and that is a real answer, not a gap.
    """
    if failure_class not in _CREDIT:
        return "", (f"failure class {failure_class!r} is unmapped; it indicts no step until "
                    f"someone decides which one it means. Guessing would attribute a failure to "
                    f"a component that was never at fault.")
    step = _CREDIT[failure_class]
    if not step:
        return "", (f"{failure_class} is a POWER failure: the sample was too small, which is a "
                    f"fact about the test and not about any research step. Nothing is mutated "
                    f"and no branch posterior moves (LAWS L1.49).")
    return step, (f"{failure_class} indicts the {step} step; mutate that and leave the rest of "
                  f"the trajectory intact")


def mutate_target(node: Node) -> tuple[str, str]:
    """What should change in the next descendant of this node?

    QuantaAlpha's surgical evolution: after a timing failure, change the timing and KEEP the
    mechanism. Randomly re-rolling the whole candidate discards the parts that worked and is why
    a parameter sweep produces ten thousand cousins of one idea.
    """
    step, why = assign_credit(node.failure_class)
    if not step:
        return "", why
    if step == "mechanism":
        return "mechanism", ("the mechanism itself is indicted -- do not mutate within this "
                             "branch, EXPLORE a different region of the semantic space")
    return step, why


def subtree_penalty(failed: list[Node]) -> dict[tuple[str, ...], dict[str, Any]]:
    """Conceptual triples that recur across failures -- ruts to downweight, not formulas to ban.

    Alpha Jungle's frequent-subtree avoidance, lifted from formula subtrees to CONCEPT triples so
    it generalises. Banning the exact expressions would be trivially evaded by renaming; the
    thing worth avoiding is the idea, and the idea is the combination of concepts.
    """
    counts: Counter[tuple[str, ...]] = Counter()
    for n in failed:
        # Power failures are not evidence that the CONCEPT is bad -- see the module docstring.
        if n.failure_class in POWER_FAILURES:
            continue
        cs = sorted(set(n.concepts))
        for i in range(len(cs)):
            for j in range(i + 1, len(cs)):
                for k in range(j + 1, len(cs)):
                    counts[(cs[i], cs[j], cs[k])] += 1
    return {t: {"failures": n, "penalty": round(1.0 / (1.0 + n / SUBTREE_RUT_AT), 4),
                "why": (f"this conceptual triple appears in {n} validity failures; the desk is "
                        f"re-exploring a rut, and the penalty applies to the IDEA rather than to "
                        f"any formula that expresses it")}
            for t, n in counts.items() if n >= SUBTREE_RUT_AT}


def retrieve_seeds(dag: LineageDAG, k: int, *, seed: int,
                   candidates: list[str] | None = None) -> list[tuple[str, float]]:
    """Sample `k` ancestors worth revisiting, by posterior fertility. AlphaPROBE's retriever.

    THOMPSON, NOT ARGMAX. Taking the top-k fertile branches would re-mine the same ground the
    moment one branch got lucky -- exactly the concentration that produced n_eff 5.5. Sampling
    from each branch's Beta posterior lets a barely-explored branch win sometimes and lose
    usually, which is what its uncertainty should buy it.

    `seed` is REQUIRED: an ancestor selection nobody can reproduce cannot be audited, and this
    decides where research effort goes.
    """
    rng = random.Random(seed)  # noqa: S311 -- Thompson sampling, not crypto
    pool = candidates if candidates is not None else list(dag.nodes)
    if not pool:
        return []

    # Empirical prior from the whole graph, for the same reason the funnel census uses one: an
    # unexplored branch most likely resembles the desk's average branch, not a coin flip.
    all_stats = [dag.branch_stats(a) for a in dag.nodes]
    tot_s = sum(s["survived"] for s in all_stats)
    tot_n = sum(s["attempts_that_count"] for s in all_stats)
    base = (tot_s / tot_n) if tot_n else 0.05
    base = min(max(base, 1e-3), 0.5)

    draws: list[tuple[str, float]] = []
    for aid in pool:
        s = dag.branch_stats(aid)
        a = _PRIOR_STRENGTH * base + s["survived"]
        b = _PRIOR_STRENGTH * (1 - base) + max(0, s["attempts_that_count"] - s["survived"])
        score = rng.betavariate(a, b)
        # LIVE DECAY IS THE LOOP CLOSING. A branch whose descendants certified and then decayed
        # forward has been telling the gauntlet something untrue; certification yield alone would
        # keep rewarding it forever.
        decay = s["mean_live_decay_r"]
        if decay is not None and decay < 0:
            score *= 1.0 / (1.0 + abs(decay))
        draws.append((aid, score))
    draws.sort(key=lambda t: -t[1])
    return draws[:k]


def branch_report(dag: LineageDAG) -> dict[str, Any]:
    """What the graph has learned. Fertility, ruts, and where the live loop has closed."""
    stats = [dag.branch_stats(a) for a in dag.nodes]
    measured = [s for s in stats if s["fertility"] is not None]
    failed = [n for n in dag.nodes.values() if not n.survived and n.failure_class]
    ruts = subtree_penalty(failed)
    with_live = [s for s in stats if s["n_live_observations"]]
    return {
        "nodes": len(dag.nodes),
        "branches_with_measurable_fertility": len(measured),
        "most_fertile": sorted(measured, key=lambda s: -(s["fertility"] or 0))[:5],
        "conceptual_ruts": len(ruts),
        "ruts": [{"concepts": list(t), **v} for t, v in
                 sorted(ruts.items(), key=lambda kv: -kv[1]["failures"])[:5]],
        "branches_with_live_evidence": len(with_live),
        "credit_assignment": dict(Counter(n.failing_step or "unattributed"
                                          for n in dag.nodes.values())),
        "note": ("power failures are excluded from every fertility denominator: an underpowered "
                 "descendant is evidence about the test, never about the branch (LAWS L1.49)"),
    }
