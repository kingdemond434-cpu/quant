"""AI Scientist v2 adapter -- REBUILT: the agentic EXPERIMENT TREE (idea -> experiment ->
interpretation -> next experiment) with best-first expansion, the interpretation done by
evidence instead of an LLM. The root ideas are the mechanism kinds; a node is (kind, window,
horizon); expanding a node runs its three refinements (half / double window, a different
hold); the frontier is ordered by each node's train-span t-ratio and the best node is expanded
next until the budget of nodes is spent. A node is "interpreted" as supported only when its
VALIDATION span (never used to order the frontier) agrees in sign, and the deepest supported
node of each tree is read once on the holdout and donated with its full ancestry.

WHY NOT THE UPSTREAM. Git-only (SakanaAI/AI-Scientist-v2, no distribution on the box) and its
idea generation, code writing and review are LLM calls the research path does not carry. The
tree search over experiments, with an evaluator deciding, is the transferable mechanism.
"""
from __future__ import annotations

import heapq
from typing import Any

from libs.research import adapter_kit as K
from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "ai_scientist"
CAPABILITY_FAMILY = "automated_science"
LICENCE_EXPECTED = "Apache-2.0"
MODULE = "ai_scientist"
RUNS_WITHOUT_LIBRARY = True
CENSUS_CLASS = "b"
ROLE = "hypothesis generator (best-first experiment tree, rebuilt)"
ROOTS: tuple[str, ...] = ("momentum", "trend", "reversion", "band_reversion", "breakout",
                          "squeeze")
MAX_NODES = 40
HOLDS: tuple[int, ...] = (4, 12, 24)


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    fr = K.frames(bundle, limit=8)
    if not fr:
        return A.unmeasured(SYSTEM, bundle, "no H1 frame carries 300 bars")
    deadline = A.Deadline(bundle.compute_budget_s)
    trials = 0
    reps: list[dict[str, Any]] = []
    cands: list[dict[str, Any]] = []
    for f in fr:
        if deadline.expired():
            break
        a = K.arrays(f)
        n = a["c"].shape[0]
        v0, v1 = int(n * 0.5), int(n * 0.75)
        cost = K.cost_frac(bundle, f.symbol, a["c"])
        seen: dict[tuple[str, int, int], dict[str, Any]] = {}

        def evaluate(node: tuple[str, int, int], parent: Any, a: dict[str, Any] = a,
                     cost: float = cost, v0: int = v0, v1: int = v1,
                     seen: dict[tuple[str, int, int], dict[str, Any]] = seen
                     ) -> dict[str, Any]:
            kind, w, h = node
            s = K.kind_signal(kind, a, w)
            fwd = K.forward_return(a["c"], h)
            tr = K.evidence(s, fwd, cost, 0, v0)
            va = K.evidence(s, fwd, cost, v0, v1)
            rec = {"kind_": kind, "window": w, "hold": h, "parent": parent,
                   "train_t": round(tr["t_ratio"], 3), "validation_t": round(va["t_ratio"], 3),
                   "supported": bool(tr["mean_net"] > 0 and va["mean_net"] > 0),
                   "depth": 0 if parent is None else seen[parent]["depth"] + 1}
            seen[node] = rec
            return rec

        frontier: list[tuple[float, tuple[str, int, int]]] = []
        for k in ROOTS:
            node = (k, 24, 12)
            rec = evaluate(node, None)
            trials += 1
            heapq.heappush(frontier, (-rec["train_t"], node))
        while frontier and len(seen) < MAX_NODES and not deadline.expired():
            _, node = heapq.heappop(frontier)
            kind, w, h = node
            for child in ((kind, max(3, w // 2), h), (kind, min(200, w * 2), h),
                          (kind, w, next(x for x in HOLDS if x != h))):
                if child in seen:
                    continue
                rec = evaluate(child, node)
                trials += 1
                heapq.heappush(frontier, (-rec["train_t"], child))
        supported = [(r["depth"], r["validation_t"], node) for node, r in seen.items()
                     if r["supported"]]
        reps.append({"kind": "experiment_tree", "symbol": f.symbol, "nodes": len(seen),
                     "supported": len(supported),
                     "tree": [{**r, "parent": list(r["parent"]) if r["parent"] else None}
                              for r in seen.values()][:MAX_NODES]})
        if not supported:
            continue
        _, _, best = max(supported)
        kind, w, h = best
        ho = K.evidence(K.kind_signal(kind, a, w), K.forward_return(a["c"], h), cost, v1, n)
        if ho["mean_net"] > 0 and ho["n_active"] >= 10:
            ancestry = []
            cur: Any = best
            while cur is not None:
                ancestry.append(list(cur))
                cur = seen[cur]["parent"]
            cands.append(K.donate(
                A, SYSTEM, kind, f.symbol,
                f"{f.symbol} H1: an AI-Scientist-style experiment tree ({len(seen)} nodes, "
                f"best-first on train evidence, interpreted on an unseen validation span) "
                f"reached {kind} at {w} bars / {h}-bar hold at depth {seen[best]['depth']}, "
                f"which held on the holdout", horizon_label=bundle.horizons[-1],
                ev={"ancestry": ancestry, "holdout": ho}, window=w, horizon=h))
    methods = [K.upstream_row(SYSTEM, MODULE, "agentic experiment tree with an evaluator",
                              "git-only upstream whose ideas, code and review are LLM calls; "
                              "evidence interprets each experiment here")]
    return A.packet(SYSTEM, bundle, trials=trials, representations=reps, candidates=cands,
                    research_methods=methods)


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
