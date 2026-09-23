"""Ray adapter -- the moving-average-cross grid evaluated as Ray tasks (local mode, no
cluster, no dashboard). Every grid point is a charged trial; the best three per symbol are
trend_ma_cross hypotheses. The point is the substrate: the same grid scales to a cluster
without changing the packet.
"""
from __future__ import annotations

import contextlib
from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "ray"
CAPABILITY_FAMILY = "distributed_compute"
LICENCE_EXPECTED = "Apache-2.0"

MAX_SYMBOLS = 4
FAST = (5, 8, 12, 20)
SLOW = (20, 30, 50, 80, 120)
KEEP = 3


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    ray = A.library("ray")
    if ray is None:
        return A.unmeasured(SYSTEM, bundle, "ray is not importable here (pip install ray==2.58.0)")
    deadline = A.Deadline(bundle.compute_budget_s)
    trials = 0
    cands: list[dict[str, Any]] = []
    try:
        ray.init(local_mode=True, ignore_reinit_error=True, include_dashboard=False, num_cpus=2,
                 logging_level="ERROR", log_to_driver=False)
    except Exception as exc:
        return A.unmeasured(SYSTEM, bundle, f"ray.init failed: {type(exc).__name__}: {exc}"[:200])
    try:
        evaluate = ray.remote(A.ma_cross_objective)
        for f in bundle.frames("H1")[:MAX_SYMBOLS]:
            if deadline.expired() or len(f) < 300:
                continue
            cost = bundle.cost_pts(f.symbol)
            tick = bundle.costs[f.symbol].tick_size if f.symbol in bundle.costs else 0.0
            grid = [(fa, sl) for fa in FAST for sl in SLOW if sl > fa]
            refs = [evaluate.remote(f, fa, sl, cost, tick) for fa, sl in grid]
            results = ray.get(refs)
            trials += len(grid)
            ranked = sorted(zip(grid, results, strict=True),
                            key=lambda t: -float(t[1]["objective_return"]))
            for (fa, sl), ev in ranked[:KEEP]:
                cands.append(A.candidate(
                    "trend_ma_cross", [f.symbol],
                    f"{f.symbol} H1 trend_ma_cross fast {fa} slow {sl} from a {len(grid)}-point "
                    f"Ray grid: cost-charged objective return {ev['objective_return']:+.4f} "
                    f"(in-sample; the gauntlet judges)",
                    horizon=bundle.horizons[0], source=SYSTEM,
                    evidence={"parameters": {"fast": fa, "slow": sl}, **ev,
                              "n_evaluated": len(grid)}))
    finally:
        with contextlib.suppress(Exception):
            ray.shutdown()
    return A.packet(SYSTEM, bundle, trials=trials, candidates=cands)


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
