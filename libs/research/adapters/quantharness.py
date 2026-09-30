"""QuantHarness adapter (REBUILT, numpy only) -- the harness, not the strategy: the frame is cut
into K contiguous folds, the best moving-average pair is chosen IN SAMPLE in each fold and
measured OUT OF SAMPLE in the next, and what the adapter reports is PARAMETER STABILITY -- how
often the in-sample winner survives the fold boundary. Every (fold, pair) is a charged trial;
the stability number is what the hypothesis carries."""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "quantharness"
CAPABILITY_FAMILY = "walk_forward_harness"
LICENCE_EXPECTED = "N/A (published method)"
RUNS_WITHOUT_LIBRARY = True

PAIRS: tuple[tuple[int, int], ...] = ((5, 20), (10, 50), (20, 100), (50, 200))
FOLDS = 5


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    import numpy as np
    frames = [f for f in bundle.frames("H1") if len(f) > 600]
    if not frames:
        return A.unmeasured(SYSTEM, bundle, "no H1 frame carries more than 600 bars")
    deadline = A.Deadline(bundle.compute_budget_s)
    reps: list[dict[str, Any]] = []
    cands: list[dict[str, Any]] = []
    trials = 0
    for f in frames:
        tick = bundle.costs[f.symbol].tick_size if f.symbol in bundle.costs else 0.0
        cost = bundle.cost_pts(f.symbol)
        n = len(f)
        size = n // FOLDS
        folds: list[dict[str, Any]] = []
        for k in range(FOLDS - 1):
            if deadline.expired():
                break
            a, b, c = k * size, (k + 1) * size, (k + 2) * size

            def cut(i: int, j: int, fr: A.BarFrame = f) -> A.BarFrame:
                return A.BarFrame(fr.symbol, fr.timeframe, fr.time[i:j], fr.open[i:j],
                                  fr.high[i:j], fr.low[i:j], fr.close[i:j], fr.volume[i:j])

            scores = []
            for fast, slow in PAIRS:
                trials += 1
                scores.append((A.ma_cross_objective(cut(a, b), fast, slow, cost,
                                                    tick)["objective_return"], (fast, slow)))
            scores.sort(key=lambda sp: -sp[0])
            chosen = scores[0][1]
            oos = A.ma_cross_objective(cut(b, c), chosen[0], chosen[1], cost, tick)
            trials += 1
            folds.append({"fold": k, "chosen": list(chosen), "in_sample": scores[0][0],
                          "out_of_sample": oos["objective_return"],
                          "oos_trades": oos["n_trades"]})
        if not folds:
            continue
        picks = [tuple(fd["chosen"]) for fd in folds]
        stability = max(picks.count(p) for p in set(picks)) / len(picks)
        oos_vals = [float(fd["out_of_sample"]) for fd in folds]
        reps.append({"kind": "walk_forward_folds", "symbol": f.symbol, "folds": folds,
                     "parameter_stability": round(stability, 4),
                     "oos_mean": float(np.mean(oos_vals)), "oos_positive_folds":
                         int(sum(1 for v in oos_vals if v > 0)),
                     "representation": ("what the harness chose fold by fold and what that "
                                        "choice was worth on the bars it never saw")})
        modal = max(set(picks), key=picks.count)
        cands.append(A.candidate(
            "trend_ma_cross", [f.symbol],
            f"{f.symbol} H1: a {len(folds)}-fold walk-forward chose the {list(modal)} "
            f"moving-average pair in {int(stability * len(folds))} of {len(folds)} folds "
            f"(stability {stability:.2f}) with a mean out-of-sample objective return of "
            f"{np.mean(oos_vals):+.4f} at the bundle's own spread",
            horizon=bundle.horizons[-1], source=SYSTEM,
            evidence={"pair": list(modal), "parameter_stability": stability,
                      "oos_mean": float(np.mean(oos_vals)), "folds": len(folds),
                      "method": "contiguous walk-forward, in-sample choice, out-of-sample "
                                "measurement"}))
    if not reps:
        return A.unmeasured(SYSTEM, bundle, "no frame supported a walk-forward split")
    return A.packet(SYSTEM, bundle, trials=trials, representations=reps, candidates=cands,
                    note=f"{trials} (fold, parameter) evaluations")


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
