"""PySR adapter -- symbolic regression (Julia backend) of the next H1 return on lagged
returns and realised vol. Every equation on the Pareto front is a charged trial; each is
donated as a MECHANISM with its complexity, loss and out-of-sample R2.
"""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "pysr"
CAPABILITY_FAMILY = "symbolic_regression"
LICENCE_EXPECTED = "Apache-2.0"
MAX_SYMBOLS = 2
ITERATIONS = 20


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    lib = A.library("pysr")
    if lib is None:
        return A.unmeasured(SYSTEM, bundle, "pysr is not importable here (pip install pysr; the "
                                            "first run installs its Julia runtime)")
    import numpy as np
    deadline = A.Deadline(bundle.compute_budget_s)
    trials = 0
    mechs: list[dict[str, Any]] = []
    for f in bundle.frames("H1")[:MAX_SYMBOLS]:
        if deadline.expired():
            break
        X, y, _ = A.lagged_design(f)
        if X.shape[0] < 300:
            continue
        try:
            model = lib.PySRRegressor(niterations=ITERATIONS, binary_operators=["+", "-", "*", "/"],
                                      unary_operators=["tanh"], maxsize=12, verbosity=0,
                                      progress=False, temp_equation_file=True,
                                      random_state=bundle.seed, deterministic=True, procs=0,
                                      multithreading=False,
                                      timeout_in_seconds=max(30, int(deadline.left())))
            model.fit(X[:-200], y[:-200], variable_names=list(A.LAGGED_FEATURE_NAMES))
            eqs = model.equations_
            pred = np.asarray(model.predict(X[-200:]), dtype=float)
        except Exception as exc:
            mechs.append({"kind": "UNMEASURED", "symbol": f.symbol,
                          "why": f"{type(exc).__name__}: {exc}"[:200]})
            continue
        r2 = 1.0 - float(np.var(y[-200:] - pred) / max(np.var(y[-200:]), 1e-18))
        n_eq = len(eqs) if eqs is not None else 0
        trials += max(1, n_eq)
        for i in range(n_eq):
            row = eqs.iloc[i]
            mechs.append({"kind": "symbolic_equation", "symbol": f.symbol,
                          "expression": str(row.get("equation")),
                          "complexity": int(row.get("complexity", 0)),
                          "loss": float(row.get("loss", float("nan"))),
                          "best_oos_r2": r2, "mechanism": "Pareto-front equation for the next "
                                                          "H1 return (in-sample fit; OOS R2 is "
                                                          "the selected equation's)"})
    return A.packet(SYSTEM, bundle, trials=trials, mechanisms=mechs)


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
