"""pymoo adapter -- NSGA-II Pareto search over an existing family's parameters -> descendants.

The family is `trend_ma_cross`; the two objectives are the bundle's own cost-charged
moving-average-cross objective (return maximised, drawdown minimised). Every `_evaluate` call is
counted and charged -- population x generations, plus whatever the algorithm re-evaluates. The
Pareto set leaves as descendant candidates carrying their parameters as evidence.
"""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "pymoo"
POP, GENS, MAX_SYMBOLS, MAX_FRONT = 12, 6, 3, 5


def _problem(core: Any, f: A.BarFrame, cost: float, tick: float,
             counter: dict[str, int]) -> Any:
    """The two-objective problem over (fast, slow), counting every evaluation."""
    import numpy as np

    class Problem(core.ElementwiseProblem):  # type: ignore[misc]
        def __init__(self) -> None:
            super().__init__(n_var=2, n_obj=2, xl=np.array([3.0, 10.0]),
                             xu=np.array([30.0, 120.0]))

        def _evaluate(self, x: Any, out: dict[str, Any], *args: Any, **kw: Any) -> None:
            fast = round(float(x[0]))
            slow = max(round(float(x[1])), fast + 2)
            ev = A.ma_cross_objective(f, fast, slow, cost, tick)
            counter["n"] += 1
            out["F"] = [-ev["objective_return"], ev["objective_drawdown"]]

    return Problem()


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    core = A.library("pymoo.core.problem")
    nsga = A.library("pymoo.algorithms.moo.nsga2")
    opt = A.library("pymoo.optimize")
    if core is None or nsga is None or opt is None:
        return A.unmeasured(SYSTEM, bundle, "pymoo is not importable in this environment")
    import numpy as np
    deadline = A.Deadline(bundle.compute_budget_s)
    trials = 0
    cands: list[dict[str, Any]] = []
    methods: list[dict[str, Any]] = []
    for f in bundle.frames("H1")[:MAX_SYMBOLS]:
        if deadline.expired() or len(f) < 300:
            continue
        cost, tick = bundle.cost_pts(f.symbol), (bundle.costs[f.symbol].tick_size
                                                 if f.symbol in bundle.costs else 0.0)
        counter = {"n": 0}
        try:
            res = opt.minimize(_problem(core, f, cost, tick, counter),
                               nsga.NSGA2(pop_size=POP), ("n_gen", GENS),
                               seed=bundle.seed, verbose=False)
            X = np.atleast_2d(np.asarray(res.X, dtype=float))
            F = np.atleast_2d(np.asarray(res.F, dtype=float))
        except Exception as exc:
            trials += counter["n"]
            methods.append({"kind": "UNMEASURED", "symbol": f.symbol,
                            "why": f"{type(exc).__name__}: {exc}"[:200]})
            continue
        trials += counter["n"]
        order = np.argsort(F[:, 0])[:MAX_FRONT]
        methods.append({"kind": "pareto_front", "symbol": f.symbol, "family": "trend_ma_cross",
                        "algorithm": f"NSGA-II pop {POP} x {GENS} generations",
                        "n_evaluated": counter["n"], "n_front": int(X.shape[0]),
                        "front": [{"fast": round(X[i, 0]), "slow": round(X[i, 1]),
                                   "objective_return": float(-F[i, 0]),
                                   "objective_drawdown": float(F[i, 1])} for i in order]})
        for i in order:
            fast, slow = round(X[i, 0]), max(round(X[i, 1]), round(X[i, 0]) + 2)
            cands.append(A.candidate(
                "trend_ma_cross", [f.symbol],
                f"{f.symbol} H1 trend_ma_cross descendant from pymoo's Pareto front: fast {fast} "
                f"slow {slow}, cost-charged objective return {-F[i, 0]:+.4f} with drawdown "
                f"{F[i, 1]:.4f} in the bundle window (in-sample; the gauntlet judges)",
                horizon=bundle.horizons[0], source=SYSTEM,
                evidence={"parameters": {"fast": fast, "slow": slow},
                          "objective_return": float(-F[i, 0]),
                          "objective_drawdown": float(F[i, 1]), "n_evaluated": counter["n"]}))
    return A.packet(SYSTEM, bundle, trials=trials, candidates=cands, research_methods=methods)


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
