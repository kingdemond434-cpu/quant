"""pyribs adapter -- MAP-Elites over the moving-average cross with measures (trade count,
drawdown): a QUALITY-DIVERSITY archive rather than one optimum. Every evaluation is a
charged trial; the archive's elites are trend_ma_cross hypotheses covering different
behaviours, which is the point -- diversity for the gauntlet, not a single winner.
"""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "pyribs"
CAPABILITY_FAMILY = "quality_diversity"
LICENCE_EXPECTED = "MIT"
MAX_SYMBOLS = 3
ITERS = 12
KEEP = 4


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    archives = A.library("ribs.archives")
    emitters = A.library("ribs.emitters")
    schedulers = A.library("ribs.schedulers")
    if archives is None or emitters is None or schedulers is None:
        return A.unmeasured(SYSTEM, bundle, "ribs is not importable here (pip install "
                                            "ribs==0.12.0)")
    deadline = A.Deadline(bundle.compute_budget_s)
    trials = 0
    cands: list[dict[str, Any]] = []
    for f in bundle.frames("H1")[:MAX_SYMBOLS]:
        if deadline.expired() or len(f) < 300:
            continue
        cost = bundle.cost_pts(f.symbol)
        tick = bundle.costs[f.symbol].tick_size if f.symbol in bundle.costs else 0.0
        try:
            archive = archives.GridArchive(solution_dim=2, dims=[8, 8],
                                           ranges=[(0.0, 60.0), (0.0, 0.2)], seed=bundle.seed)
            emitter = emitters.EvolutionStrategyEmitter(archive, x0=[10.0, 40.0], sigma0=5.0,
                                                        batch_size=8, seed=bundle.seed)
            scheduler = schedulers.Scheduler(archive, [emitter])
            for _ in range(ITERS):
                if deadline.expired():
                    break
                sols = scheduler.ask()
                objs, meas = [], []
                for s in sols:
                    fa, sl = round(abs(float(s[0]))) + 2, round(abs(float(s[1]))) + 3
                    ev = A.ma_cross_objective(f, min(fa, sl), max(fa, sl) + (fa == sl), cost,
                                              tick)
                    trials += 1
                    objs.append(ev["objective_return"])
                    meas.append([min(ev["n_trades"], 60.0), min(ev["objective_drawdown"], 0.2)])
                scheduler.tell(objs, meas)
            data = archive.data(["solution", "objective", "measures"])
            elites = sorted(zip(data["solution"], data["objective"], data["measures"],
                                strict=True), key=lambda t: -float(t[1]))[:KEEP]
        except Exception as exc:
            cands.append(A.candidate("trend_ma_cross", [f.symbol],
                                     f"UNMEASURED: pyribs raised {type(exc).__name__} on "
                                     f"{f.symbol}", horizon=bundle.horizons[0], source=SYSTEM,
                                     evidence={"why": f"{type(exc).__name__}: {exc}"[:200]}))
            continue
        for sol, obj, m in elites:
            fa, sl = round(abs(float(sol[0]))) + 2, round(abs(float(sol[1]))) + 3
            fa, sl = min(fa, sl), max(fa, sl) + (fa == sl)
            cands.append(A.candidate(
                "trend_ma_cross", [f.symbol],
                f"{f.symbol} H1 trend_ma_cross fast {fa} slow {sl}: a MAP-Elites elite (cell "
                f"trades~{float(m[0]):.0f}, drawdown~{float(m[1]):.3f}) with cost-charged "
                f"objective return {float(obj):+.4f} (in-sample; the gauntlet judges)",
                horizon=bundle.horizons[0], source=SYSTEM,
                evidence={"parameters": {"fast": fa, "slow": sl}, "objective_return": float(obj),
                          "measures": [float(m[0]), float(m[1])], "n_evaluated": trials}))
    return A.packet(SYSTEM, bundle, trials=trials, candidates=cands)


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
