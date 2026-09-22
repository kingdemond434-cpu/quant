"""BoTorch adapter -- Bayesian optimisation proposes the next experiments over a family's
parameters -> active-experiment proposals and descendant candidates.

A GP is fitted to an initial design over (fast, slow) of `trend_ma_cross` and log-EI proposes
the next point; each evaluated design is charged. What leaves is the observed design, the
proposals with their acquisition values, and the best designs as candidates. CPU only.
"""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "botorch"
INIT, ROUNDS = 8, 3


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    torch = A.library("torch")
    models = A.library("botorch.models")
    fit = A.library("botorch.fit")
    acq_mod = A.library("botorch.acquisition")
    optim = A.library("botorch.optim")
    mlls = A.library("gpytorch.mlls")
    if any(m is None for m in (torch, models, fit, acq_mod, optim, mlls)):
        return A.unmeasured(SYSTEM, bundle, "botorch/gpytorch/torch are not importable here")
    import numpy as np
    frames = [f for f in bundle.frames("H1") if len(f) >= 300]
    if not frames:
        return A.unmeasured(SYSTEM, bundle, "no H1 frame with 300+ bars")
    f = frames[0]
    cost, tick = bundle.cost_pts(f.symbol), (bundle.costs[f.symbol].tick_size
                                             if f.symbol in bundle.costs else 0.0)
    rng = np.random.default_rng(bundle.seed)

    def design(u: Any) -> tuple[int, int]:
        fast = round(3 + 27 * float(u[0]))
        return fast, max(round(10 + 110 * float(u[1])), fast + 2)

    def evaluate(u: Any) -> float:
        fast, slow = design(u)
        return float(A.ma_cross_objective(f, fast, slow, cost, tick)["objective_return"])

    X = rng.random((INIT, 2))
    Y = np.array([evaluate(u) for u in X])
    trials = INIT
    proposals: list[dict[str, Any]] = []
    deadline = A.Deadline(bundle.compute_budget_s)
    try:
        assert torch is not None and models is not None and fit is not None
        assert acq_mod is not None and optim is not None and mlls is not None
        bounds = torch.tensor([[0.0, 0.0], [1.0, 1.0]], dtype=torch.double)
        for _ in range(ROUNDS):
            if deadline.expired():
                break
            tx = torch.tensor(X, dtype=torch.double)
            ty = torch.tensor(Y.reshape(-1, 1), dtype=torch.double)
            gp = models.SingleTaskGP(tx, ty)
            fit.fit_gpytorch_mll(mlls.ExactMarginalLogLikelihood(gp.likelihood, gp))
            acq = acq_mod.LogExpectedImprovement(gp, best_f=ty.max())
            cand, val = optim.optimize_acqf(acq, bounds=bounds, q=1, num_restarts=4,
                                            raw_samples=64)
            u = cand.detach().numpy().reshape(-1)
            y = evaluate(u)
            trials += 1
            fast, slow = design(u)
            proposals.append({"fast": fast, "slow": slow, "log_ei": float(val),
                              "objective_return": y})
            X = np.vstack([X, u.reshape(1, 2)])
            Y = np.append(Y, y)
    except Exception as exc:
        return A.packet(SYSTEM, bundle, trials=trials, research_methods=[
            {"kind": "UNMEASURED", "symbol": f.symbol,
             "why": f"{type(exc).__name__}: {exc}"[:200]}])
    observed = [{"fast": design(u)[0], "slow": design(u)[1], "objective_return": float(y)}
                for u, y in zip(X, Y, strict=True)]
    best = sorted(observed, key=lambda r: -r["objective_return"])[:2]
    cands = [A.candidate(
        "trend_ma_cross", [f.symbol],
        f"{f.symbol} H1 trend_ma_cross design chosen by BoTorch log-EI after {trials} "
        f"evaluations: fast {b['fast']} slow {b['slow']}, cost-charged objective return "
        f"{b['objective_return']:+.4f} (in-sample; the gauntlet judges)",
        horizon=bundle.horizons[0], source=SYSTEM,
        evidence={"parameters": {"fast": b["fast"], "slow": b["slow"]},
                  "objective_return": b["objective_return"], "n_evaluated": trials})
        for b in best]
    return A.packet(SYSTEM, bundle, trials=trials, candidates=cands, research_methods=[
        {"kind": "active_experiment_proposal", "symbol": f.symbol, "family": "trend_ma_cross",
         "model": "SingleTaskGP + LogExpectedImprovement", "observed": observed,
         "proposals": proposals, "n_evaluated": trials}])


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
