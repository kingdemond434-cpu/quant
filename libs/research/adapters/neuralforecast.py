"""NeuralForecast adapter -- N-HiTS from the Nixtla zoo fitted briefly on each symbol's log
price; the forecast path relative to the last close is a REPRESENTATION. One charged trial
per symbol (the model's own steps are one search).
"""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "neuralforecast"
CAPABILITY_FAMILY = "forecast_zoo"
LICENCE_EXPECTED = "Apache-2.0"
MAX_SYMBOLS = 3
H = 24
STEPS = 30


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    nf_mod = A.library("neuralforecast")
    models = A.library("neuralforecast.models")
    pd = A.library("pandas")
    if nf_mod is None or models is None or pd is None:
        return A.unmeasured(SYSTEM, bundle, "neuralforecast (or pandas) is not importable here "
                                            "(pip install neuralforecast==3.2.2; torch)")
    import numpy as np
    deadline = A.Deadline(bundle.compute_budget_s)
    trials = 0
    reps: list[dict[str, Any]] = []
    for f in bundle.frames("H1")[:MAX_SYMBOLS]:
        if deadline.expired() or len(f) < 600:
            continue
        trials += 1
        c = np.log(np.asarray(f.close[-600:], dtype=float))
        df = pd.DataFrame({"unique_id": f.symbol, "ds": pd.to_datetime(list(f.time[-600:])),
                           "y": c})
        try:
            nf = nf_mod.NeuralForecast(models=[models.NHITS(h=H, input_size=96, max_steps=STEPS,
                                                             enable_progress_bar=False,
                                                             logger=False)], freq="h")
            nf.fit(df)
            fc = nf.predict()
            path = np.asarray(fc["NHITS"], dtype=float)[:H]
        except Exception as exc:
            reps.append({"kind": "UNMEASURED", "symbol": f.symbol,
                         "why": f"{type(exc).__name__}: {exc}"[:200]})
            continue
        reps.append({"kind": "zoo_forecast_path", "symbol": f.symbol, "model": "NHITS",
                     "steps": STEPS, "horizon_bars": H, "path_rel": np.exp(path - c[-1]) - 1.0,
                     "representation": "the zoo's path; its sign agreement across models is a "
                                       "state, its level is not a signal"})
    return A.packet(SYSTEM, bundle, trials=trials, representations=reps)


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
