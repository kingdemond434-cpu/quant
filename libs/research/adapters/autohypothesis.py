"""autohypothesis adapter -- REBUILT: an independent MUTATION LABORATORY with a strict
acceptance rule. A hypothesis is (mechanism kind, window, horizon); a mutation changes ONE of
the three; a mutant replaces its parent only when its evidence improves on a VALIDATION span
the parent's own selection never used (train -> validation -> holdout, chronological). Every
mutant is a charged trial. The final lineage head is read once on the holdout and donated when
it holds -- with its whole mutation lineage riding as evidence, so the gauntlet sees how many
steps the hypothesis took to get there.

WHY NOT THE UPSTREAM. No distribution resolvable on the box (ledger: NO_DISTRIBUTION_PINNED).
The upstream is a hypothesis-mutation harness; the harness is what is reproduced.
"""
from __future__ import annotations

import random
from typing import Any

from libs.research import adapter_kit as K
from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "autohypothesis"
CAPABILITY_FAMILY = "evolutionary_search"
LICENCE_EXPECTED = "UNVERIFIED"
MODULE = "autohypothesis"
RUNS_WITHOUT_LIBRARY = True
CENSUS_CLASS = "b"
ROLE = "hypothesis generator (one-change mutation lab with a validation acceptance rule)"
STEPS = 12
KINDS: tuple[str, ...] = ("momentum", "trend", "reversion", "band_reversion",
                          "range_reversion", "pullback", "breakout", "squeeze", "volume")
HORIZONS: tuple[int, ...] = (4, 8, 12, 24)


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    import numpy as np
    fr = K.frames(bundle, limit=8)
    if not fr:
        return A.unmeasured(SYSTEM, bundle, "no H1 frame carries 300 bars")
    deadline = A.Deadline(bundle.compute_budget_s)
    rng = random.Random(bundle.seed + 31)  # noqa: S311 -- a seeded mutation order
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

        def score(h: tuple[str, int, int], lo: int, hi: int, a: dict[str, Any] = a,
                  cost: float = cost) -> dict[str, float]:
            s = K.kind_signal(h[0], a, h[1])
            return K.evidence(s, K.forward_return(a["c"], h[2]), cost, lo, hi)

        head = (rng.choice(KINDS), rng.choice((12, 24, 48)), rng.choice(HORIZONS))
        best_val = score(head, v0, v1)["t_ratio"]
        trials += 1
        lineage = [{"step": 0, "kind_": head[0], "window": head[1], "horizon": head[2],
                    "validation_t": round(best_val, 3)}]
        for step in range(1, STEPS + 1):
            what = rng.choice(("kind", "window", "horizon"))
            if what == "kind":
                mut = (rng.choice(KINDS), head[1], head[2])
            elif what == "window":
                mut = (head[0], max(3, min(200, int(head[1] * rng.choice((0.5, 0.7, 1.4, 2))))),
                       head[2])
            else:
                mut = (head[0], head[1], rng.choice(HORIZONS))
            trials += 1
            if score(mut, 0, v0)["mean_net"] <= 0:
                continue
            val = score(mut, v0, v1)["t_ratio"]
            if np.isfinite(val) and val > best_val:
                head, best_val = mut, val
                lineage.append({"step": step, "mutated": what, "kind_": mut[0],
                                "window": mut[1], "horizon": mut[2],
                                "validation_t": round(val, 3)})
        ho = score(head, v1, n)
        reps.append({"kind": "mutation_lineage", "symbol": f.symbol, "lineage": lineage,
                     "holdout": ho})
        if len(lineage) > 1 and ho["mean_net"] > 0 and ho["n_active"] >= 10:
            cands.append(K.donate(
                A, SYSTEM, head[0], f.symbol,
                f"{f.symbol} H1: an autohypothesis mutation lab moved a hypothesis through "
                f"{len(lineage) - 1} accepted one-change mutations (each improving an unseen "
                f"validation span) to {head[0]} at {head[1]} bars / {head[2]}-bar hold, which "
                f"held on the final holdout", horizon_label=bundle.horizons[-1],
                ev={"lineage": lineage, "holdout": ho}, window=head[1], horizon=head[2]))
    methods = [K.upstream_row(SYSTEM, MODULE, "one-change hypothesis mutation with validation "
                              "acceptance", "no distribution resolvable on the box; the "
                              "harness is reproduced")]
    return A.packet(SYSTEM, bundle, trials=trials, representations=reps, candidates=cands,
                    research_methods=methods)


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
