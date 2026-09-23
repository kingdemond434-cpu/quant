"""Darts adapter -- a classical forecaster (exponential smoothing) fitted on the first 80% of
each frame and scored on the tail against the naive last-value path; skill vs naive is a
REPRESENTATION of how forecastable the instrument currently is.
"""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "darts"
CAPABILITY_FAMILY = "forecast_zoo"
LICENCE_EXPECTED = "Apache-2.0"
MAX_SYMBOLS = 4


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    darts = A.library("darts")
    dmodels = A.library("darts.models")
    if darts is None or dmodels is None:
        return A.unmeasured(SYSTEM, bundle, "darts is not importable here (pip install "
                                            "u8darts==0.41.0)")
    import numpy as np
    deadline = A.Deadline(bundle.compute_budget_s)
    trials = 0
    reps: list[dict[str, Any]] = []
    for f in bundle.frames("H1")[:MAX_SYMBOLS]:
        if deadline.expired() or len(f) < 500:
            continue
        trials += 1
        c = np.log(np.asarray(f.close[-500:], dtype=float))
        cut = 400
        try:
            series = darts.TimeSeries.from_values(c)
            train, test = series[:cut], series[cut:]
            model = dmodels.ExponentialSmoothing()
            model.fit(train)
            pred = np.asarray(model.predict(len(test)).values(), dtype=float).reshape(-1)
        except Exception as exc:
            reps.append({"kind": "UNMEASURED", "symbol": f.symbol,
                         "why": f"{type(exc).__name__}: {exc}"[:200]})
            continue
        actual = c[cut:]
        err_model = float(np.mean(np.abs(actual - pred)))
        err_naive = float(np.mean(np.abs(actual - c[cut - 1])))
        reps.append({"kind": "forecast_skill", "symbol": f.symbol, "model": "ExponentialSmoothing",
                     "n_test": int(actual.shape[0]), "mae_model": err_model,
                     "mae_naive": err_naive, "skill_vs_naive": 1.0 - err_model / max(err_naive,
                                                                                    1e-12),
                     "representation": "skill vs naive is a forecastability state"})
    return A.packet(SYSTEM, bundle, trials=trials, representations=reps)


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
