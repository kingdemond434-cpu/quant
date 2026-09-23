"""Deep Symbolic Optimization adapter -- RL over expression trees. `DeepSymbolicRegressor`
(sklearn-shaped) is fitted on the lagged-return design of each frame; the best program is
a MECHANISM (an equation for the next return), never a signal.
"""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "dso"
CAPABILITY_FAMILY = "symbolic_regression"
LICENCE_EXPECTED = "BSD-3-Clause"
MAX_SYMBOLS = 3


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    lib = A.library("dso")
    if lib is None or not hasattr(lib, "DeepSymbolicRegressor"):
        return A.unmeasured(SYSTEM, bundle, "dso is not importable here (git-only upstream "
                                            "dso-org/deep-symbolic-optimization)")
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
        trials += 1
        try:
            model = lib.DeepSymbolicRegressor()
            model.fit(X[:-200], y[:-200])
            pred = np.asarray(model.predict(X[-200:]), dtype=float)
            r2 = 1.0 - float(np.var(y[-200:] - pred) / max(np.var(y[-200:]), 1e-18))
            expr = str(getattr(getattr(model, "program_", None), "pretty", lambda: "?")())
        except Exception as exc:
            mechs.append({"kind": "UNMEASURED", "symbol": f.symbol,
                          "why": f"{type(exc).__name__}: {exc}"[:200]})
            continue
        mechs.append({"kind": "symbolic_equation", "symbol": f.symbol, "expression": expr,
                      "inputs": A.LAGGED_FEATURE_NAMES, "oos_r2": r2, "n_oos": 200,
                      "mechanism": "next-return equation found by RL over expression trees"})
    return A.packet(SYSTEM, bundle, trials=trials, mechanisms=mechs)


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
