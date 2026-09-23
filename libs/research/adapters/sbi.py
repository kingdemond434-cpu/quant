"""sbi adapter -- neural posterior estimation over the parameters of a GARCH(1,1) world from
summary statistics of the observed returns; the posterior over persistence is a
REPRESENTATION of the latent volatility regime.
"""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "sbi"
CAPABILITY_FAMILY = "simulation_based_inference"
LICENCE_EXPECTED = "Apache-2.0"
MAX_SYMBOLS = 2
T = 400
SIMS = 300


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    sbi_inf = A.library("sbi.inference")
    sbi_utils = A.library("sbi.utils")
    torch = A.library("torch")
    if sbi_inf is None or sbi_utils is None or torch is None:
        return A.unmeasured(SYSTEM, bundle, "sbi (or torch) is not importable here (pip install "
                                            "sbi==0.27.0)")
    import numpy as np
    rng = np.random.default_rng(bundle.seed)

    def simulate(theta: Any) -> Any:
        omega, alpha, beta = (float(v) for v in np.asarray(theta, dtype=float).reshape(-1))
        h, r = 1e-4, np.zeros(T)
        for t in range(T):
            r[t] = rng.standard_normal() * np.sqrt(h)
            h = omega + alpha * r[t] ** 2 + beta * h
        return summary(r)

    def summary(r: Any) -> Any:
        r = np.asarray(r, dtype=float)
        r2 = r * r
        ac = float(np.corrcoef(r2[:-1], r2[1:])[0, 1]) if r2.std() > 0 else 0.0
        return torch.tensor([np.log(r.std() + 1e-12), float(((r - r.mean()) ** 4).mean()
                                                            / max(r.var() ** 2, 1e-24)), ac],
                            dtype=torch.float32)

    NPE = getattr(sbi_inf, "NPE", None) or getattr(sbi_inf, "SNPE", None)
    if NPE is None:
        return A.unmeasured(SYSTEM, bundle, "sbi carries neither NPE nor SNPE")
    deadline = A.Deadline(bundle.compute_budget_s)
    trials = 0
    reps: list[dict[str, Any]] = []
    for f in bundle.frames("H1")[:MAX_SYMBOLS]:
        r = f.log_returns()
        if deadline.expired() or r.shape[0] < T:
            continue
        trials += SIMS
        try:
            prior = sbi_utils.BoxUniform(low=torch.tensor([1e-6, 0.01, 0.5]),
                                         high=torch.tensor([1e-4, 0.3, 0.98]))
            theta = prior.sample((SIMS,))
            x = torch.stack([simulate(th) for th in theta])
            inference = NPE(prior)
            inference.append_simulations(theta, x).train(max_num_epochs=20,
                                                          show_train_summary=False)
            posterior = inference.build_posterior()
            samples = posterior.sample((200,), x=summary(r[-T:]), show_progress_bars=False)
            s = np.asarray(samples.numpy(), dtype=float)
        except Exception as exc:
            reps.append({"kind": "UNMEASURED", "symbol": f.symbol,
                         "why": f"{type(exc).__name__}: {exc}"[:200]})
            continue
        reps.append({"kind": "sbi_posterior", "symbol": f.symbol, "world": "GARCH(1,1)",
                     "alpha_mean": float(s[:, 1].mean()), "beta_mean": float(s[:, 2].mean()),
                     "persistence_mean": float((s[:, 1] + s[:, 2]).mean()),
                     "persistence_p90": float(np.percentile(s[:, 1] + s[:, 2], 90)),
                     "simulations": SIMS,
                     "representation": "posterior persistence near 1 is a sticky-vol regime"})
    return A.packet(SYSTEM, bundle, trials=trials, representations=reps)


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
