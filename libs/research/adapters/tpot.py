"""TPOT adapter -- genetic programming over whole sklearn pipelines for the next-return
regression; the evolved pipeline and its out-of-sample R2 are a research method (the
search width, generations x population, is the charged trial count).
"""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "tpot"
CAPABILITY_FAMILY = "program_evolution"
LICENCE_EXPECTED = "LGPL-3.0"
MAX_SYMBOLS = 2
GENS = 2
POP = 8


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    tp = A.library("tpot")
    if tp is None:
        return A.unmeasured(SYSTEM, bundle, "tpot is not importable here (pip install "
                                            "TPOT==0.12.2)")
    import numpy as np
    deadline = A.Deadline(bundle.compute_budget_s)
    trials = 0
    rows: list[dict[str, Any]] = []
    for f in bundle.frames("H1")[:MAX_SYMBOLS]:
        if deadline.expired():
            break
        X, y, _ = A.lagged_design(f)
        if X.shape[0] < 400:
            continue
        trials += GENS * POP
        try:
            model = tp.TPOTRegressor(generations=GENS, population_size=POP, verbosity=0,
                                     random_state=bundle.seed, n_jobs=1,
                                     max_time_mins=max(1, int(deadline.left() // 60)))
            model.fit(X[:-200], y[:-200])
            pred = np.asarray(model.predict(X[-200:]), dtype=float)
            r2 = 1.0 - float(np.var(y[-200:] - pred) / max(np.var(y[-200:]), 1e-18))
            rows.append({"kind": "evolved_pipeline", "symbol": f.symbol,
                         "pipeline": str(getattr(model, "fitted_pipeline_", "?"))[:400],
                         "oos_r2": r2, "generations": GENS, "population": POP})
        except Exception as exc:
            rows.append({"kind": "UNMEASURED", "symbol": f.symbol,
                         "why": f"{type(exc).__name__}: {exc}"[:200]})
    return A.packet(SYSTEM, bundle, trials=trials, research_methods=rows)


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
