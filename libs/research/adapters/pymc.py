"""PyMC adapter -- a Student-t return model per symbol sampled with NUTS: the posterior over
drift, scale and tail weight, and P(drift > 0), donated as REPRESENTATIONS of the
instrument's current state (never a forecast to act on).
"""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "pymc"
CAPABILITY_FAMILY = "probabilistic_programming"
LICENCE_EXPECTED = "Apache-2.0"
MAX_SYMBOLS = 3
WINDOW = 500
DRAWS = 200


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    pm = A.library("pymc")
    if pm is None:
        return A.unmeasured(SYSTEM, bundle, "pymc is not importable here (pip install pymc==6.3.2)")
    import numpy as np
    deadline = A.Deadline(bundle.compute_budget_s)
    trials = 0
    reps: list[dict[str, Any]] = []
    for f in bundle.frames("H1")[:MAX_SYMBOLS]:
        if deadline.expired() or len(f) < WINDOW + 1:
            continue
        r = f.log_returns()[-WINDOW:]
        trials += 1
        try:
            with pm.Model():
                mu = pm.Normal("mu", 0.0, 0.01)
                sigma = pm.HalfNormal("sigma", 0.05)
                nu = pm.Exponential("nu", 1.0 / 10.0)
                pm.StudentT("r", nu=nu, mu=mu, sigma=sigma, observed=r)
                idata = pm.sample(draws=DRAWS, tune=DRAWS, chains=1, progressbar=False,
                                  random_seed=bundle.seed, compute_convergence_checks=False)
            post = idata.posterior
            mu_s = np.asarray(post["mu"]).reshape(-1)
            reps.append({"kind": "bayesian_posterior", "symbol": f.symbol, "window": WINDOW,
                         "mu_mean": float(mu_s.mean()), "p_mu_positive": float((mu_s > 0).mean()),
                         "sigma_mean": float(np.asarray(post["sigma"]).mean()),
                         "nu_mean": float(np.asarray(post["nu"]).mean()), "draws": DRAWS,
                         "representation": "tail weight (nu) and P(drift>0) are states; a low "
                                           "nu says the last window was fat-tailed"})
        except Exception as exc:
            reps.append({"kind": "UNMEASURED", "symbol": f.symbol,
                         "why": f"{type(exc).__name__}: {exc}"[:200]})
    return A.packet(SYSTEM, bundle, trials=trials, representations=reps)


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
