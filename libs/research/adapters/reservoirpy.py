"""ReservoirPy adapter -- an echo-state network (100 units, ridge readout) fitted on the
lagged-return design; out-of-sample R2 and sign hit rate on the tail are a REPRESENTATION
of short-horizon predictability.
"""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "reservoirpy"
CAPABILITY_FAMILY = "reservoir_computing"
LICENCE_EXPECTED = "MIT"
MAX_SYMBOLS = 4
UNITS = 100


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    nodes = A.library("reservoirpy.nodes")
    if nodes is None:
        return A.unmeasured(SYSTEM, bundle, "reservoirpy is not importable here (pip install "
                                            "reservoirpy==0.4.2)")
    import numpy as np
    deadline = A.Deadline(bundle.compute_budget_s)
    trials = 0
    reps: list[dict[str, Any]] = []
    for f in bundle.frames("H1")[:MAX_SYMBOLS]:
        if deadline.expired():
            break
        X, y, _ = A.lagged_design(f)
        if X.shape[0] < 400:
            continue
        trials += 1
        try:
            esn = nodes.Reservoir(UNITS, lr=0.3, sr=0.9, seed=bundle.seed) >> nodes.Ridge(
                ridge=1e-5)
            esn.fit(X[:-200], y[:-200].reshape(-1, 1), warmup=20)
            pred = np.asarray(esn.run(X[-200:]), dtype=float).reshape(-1)
        except Exception as exc:
            reps.append({"kind": "UNMEASURED", "symbol": f.symbol,
                         "why": f"{type(exc).__name__}: {exc}"[:200]})
            continue
        yt = y[-200:]
        reps.append({"kind": "reservoir_forecast", "symbol": f.symbol, "units": UNITS,
                     "oos_r2": 1.0 - float(np.var(yt - pred) / max(np.var(yt), 1e-18)),
                     "oos_sign_hit": float(np.mean(np.sign(pred) == np.sign(yt))), "n_oos": 200,
                     "representation": "a sign hit rate above chance is a predictability state"})
    return A.packet(SYSTEM, bundle, trials=trials, representations=reps)


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
