"""QuantaAlpha adapter (REBUILT, numpy only) -- whole RESEARCH TRAJECTORIES evolved rather than
parameters: a genome is (lag, window, threshold, direction), a generation mutates and crosses
the survivors, and every genome evaluated is a charged trial. The lineage is the representation
-- what was tried, what it scored, what it came from -- and the fittest genome is donated as a
hypothesis with its ancestry attached."""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "quantaalpha"
CAPABILITY_FAMILY = "trajectory_evolution"
LICENCE_EXPECTED = "N/A (published method)"
RUNS_WITHOUT_LIBRARY = True

GENERATIONS = 4
POP = 8
LAGS: tuple[int, ...] = (1, 2, 3, 5, 8)
WINDOWS: tuple[int, ...] = (12, 24, 48, 96)
THRESHOLDS: tuple[float, ...] = (0.0, 0.5, 1.0, 1.5)


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    import random

    import numpy as np
    frames = [f for f in bundle.frames("H1") if len(f) > 300]
    if not frames:
        return A.unmeasured(SYSTEM, bundle, "no H1 frame carries more than 300 bars")
    deadline = A.Deadline(bundle.compute_budget_s)
    rng = random.Random(bundle.seed + 7)  # noqa: S311 -- a seeded mutation order
    reps: list[dict[str, Any]] = []
    cands: list[dict[str, Any]] = []
    trials = 0
    for f in frames:
        r = f.log_returns()
        if r.shape[0] < 200:
            continue

        def fitness(g: tuple[int, int, float, int], rr: Any = r) -> float:
            lag, win, thr, direction = g
            vol = A.realised_vol(rr, win)
            sig = np.full(rr.shape[0], 0.0)
            idx = np.arange(lag, rr.shape[0])
            z = rr[idx - lag] / np.maximum(vol[idx - 1], 1e-12)
            sig[idx] = np.where(np.abs(z) > thr, np.sign(z) * direction, 0.0)
            pnl = sig[:-1] * rr[1:]
            pnl = pnl[np.isfinite(pnl)]
            return float(pnl.sum()) if pnl.size else float("nan")

        pop = [(rng.choice(LAGS), rng.choice(WINDOWS), rng.choice(THRESHOLDS),
                rng.choice((1, -1))) for _ in range(POP)]
        lineage: list[dict[str, Any]] = []
        scored: list[tuple[float, tuple[int, int, float, int]]] = []
        for gen in range(GENERATIONS):
            if deadline.expired():
                break
            scored = []
            for g in pop:
                trials += 1
                scored.append((fitness(g), g))
            scored = [(s, g) for s, g in scored if not np.isnan(s)]
            if not scored:
                break
            scored.sort(key=lambda sg: -sg[0])
            lineage.append({"generation": gen,
                            "best": {"genome": list(scored[0][1]), "objective": scored[0][0]},
                            "evaluated": len(pop)})
            elite = [g for _, g in scored[:max(2, POP // 3)]]
            pop = list(elite)
            while len(pop) < POP:
                a, b = rng.choice(elite), rng.choice(elite)
                child = (a[0], b[1], a[2], b[3])
                if rng.random() < 0.5:
                    child = (rng.choice(LAGS), child[1], rng.choice(THRESHOLDS), child[3])
                pop.append(child)
        if not lineage or not scored:
            continue
        best_obj, best = scored[0]
        reps.append({"kind": "trajectory_lineage", "symbol": f.symbol, "lineage": lineage,
                     "genome_fields": ["lag", "vol_window", "threshold_z", "direction"],
                     "representation": ("the evolved procedure and everything it descended "
                                        "from, evaluated on one frame")})
        family = "momentum_volgate" if best[3] > 0 else "vol_mean_reversion"
        cands.append(A.candidate(
            family, [f.symbol],
            f"{f.symbol} H1: an evolved trajectory (lag {best[0]}, vol window {best[1]}, "
            f"z threshold {best[2]}, direction {best[3]}) accumulates {best_obj:+.4f} log "
            f"return over {len(lineage)} generations of mutation and crossover",
            horizon=bundle.horizons[-1], source=SYSTEM,
            evidence={"genome": list(best), "objective_return": best_obj,
                      "generations": len(lineage), "population": POP,
                      "method": "mutation/crossover over research trajectories, numpy only"}))
    if not reps:
        return A.unmeasured(SYSTEM, bundle, "no frame supported a generation of evolution")
    return A.packet(SYSTEM, bundle, trials=trials, representations=reps, candidates=cands,
                    note=f"{trials} genomes evaluated over {len(reps)} frames")


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
