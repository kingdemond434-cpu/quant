"""AgonAlpha adapter (REBUILT, numpy only) -- artifact-level alpha search with the MCTS ALLOCATION
rebuilt as UCB1 over a parameter arena: each arm is a moving-average pair, each visit evaluates
it on a seeded random window of the frame at the bundle's own spread, and the budget is spent
where the upper confidence bound is highest. Visits and bounds are the representation; the
most-visited arm is donated as a hypothesis, never as a choice."""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "agonalpha"
CAPABILITY_FAMILY = "artifact_search"
LICENCE_EXPECTED = "N/A (published architecture)"
RUNS_WITHOUT_LIBRARY = True

ARMS: tuple[tuple[int, int], ...] = ((5, 20), (10, 50), (20, 100), (50, 200), (8, 34), (13, 55))
WINDOW = 240


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    import math
    import random

    import numpy as np
    frames = [f for f in bundle.frames("H1") if len(f) > WINDOW + 50]
    if not frames:
        return A.unmeasured(SYSTEM, bundle, "no H1 frame long enough for a search window")
    deadline = A.Deadline(bundle.compute_budget_s)
    rng = random.Random(bundle.seed)  # noqa: S311 -- a seeded search order, never a secret
    reps: list[dict[str, Any]] = []
    cands: list[dict[str, Any]] = []
    trials = 0
    for f in frames:
        tick = bundle.costs[f.symbol].tick_size if f.symbol in bundle.costs else 0.0
        cost = bundle.cost_pts(f.symbol)
        visits = [0] * len(ARMS)
        total = [0.0] * len(ARMS)
        for t in range(len(ARMS) * 6):
            if deadline.expired():
                break
            if t < len(ARMS):
                arm = t
            else:
                n = sum(visits)
                arm = max(range(len(ARMS)), key=lambda i: (
                    total[i] / max(visits[i], 1)
                    + 1.4 * math.sqrt(math.log(max(n, 2)) / max(visits[i], 1))))
            start = rng.randint(0, len(f) - WINDOW - 1)
            sl = A.BarFrame(f.symbol, f.timeframe, f.time[start:start + WINDOW],
                            f.open[start:start + WINDOW], f.high[start:start + WINDOW],
                            f.low[start:start + WINDOW], f.close[start:start + WINDOW],
                            f.volume[start:start + WINDOW])
            fast, slow = ARMS[arm]
            obj = A.ma_cross_objective(sl, fast, slow, cost, tick)
            trials += 1
            visits[arm] += 1
            total[arm] += float(obj["objective_return"])
        if not sum(visits):
            continue
        rows = [{"arm": list(ARMS[i]), "visits": visits[i],
                 "mean_objective_return": (total[i] / visits[i]) if visits[i] else None}
                for i in range(len(ARMS))]
        reps.append({"kind": "ucb_search_tree", "symbol": f.symbol, "arms": rows,
                     "window_bars": WINDOW, "cost_pts": None if np.isnan(cost) else cost,
                     "representation": ("where a UCB1 budget went over a parameter arena; "
                                        "visits are attention, never approval")})
        best = max(rows, key=lambda r: (r["visits"], r["mean_objective_return"] or 0.0))
        cands.append(A.candidate(
            "trend_ma_cross", [f.symbol],
            f"{f.symbol} H1: a UCB1 artifact search spent {best['visits']} of {sum(visits)} "
            f"visits on the {best['arm']} moving-average pair, mean objective return "
            f"{best['mean_objective_return']} over {WINDOW}-bar windows at the bundle's spread",
            horizon=bundle.horizons[-1], source=SYSTEM,
            evidence={"arm": best["arm"], "visits": best["visits"], "total_visits": sum(visits),
                      "mean_objective_return": best["mean_objective_return"],
                      "method": "UCB1 allocation over a parameter arena, seeded windows"}))
    if not reps:
        return A.unmeasured(SYSTEM, bundle, "the budget expired before any arm was visited")
    return A.packet(SYSTEM, bundle, trials=trials, representations=reps, candidates=cands,
                    note=f"{trials} arm visits over {len(reps)} frames")


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
