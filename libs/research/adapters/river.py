"""River adapter -- an online learner's residual stream -> residual-signal representations.

A scaler + SGD linear model learns one bar at a time from lagged returns and realised vol; the
residual of each one-step prediction is the signal, and ADWIN over the residuals marks drift.
Each learning-rate configuration per symbol is one charged trial. Nothing here forecasts for the
desk: the residual and drift states are representations for the forge.
"""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "river"
RATES: tuple[float, ...] = (0.01, 0.05)
WINDOW = 24


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    mods = {n: A.library(f"river.{n}") for n in ("drift", "linear_model", "optim",
                                                  "preprocessing")}
    if any(m is None for m in mods.values()):
        return A.unmeasured(SYSTEM, bundle, "river is not importable in this environment")
    M: dict[str, Any] = dict(mods)
    drift, linear_model, optim, preprocessing = (M["drift"], M["linear_model"], M["optim"],
                                                 M["preprocessing"])
    import numpy as np
    deadline = A.Deadline(bundle.compute_budget_s)
    trials = 0
    reps: list[dict[str, Any]] = []
    for f in bundle.frames("H1"):
        r = f.log_returns()
        if r.shape[0] < 200:
            continue
        vol = A.realised_vol(r, WINDOW)
        for lr in RATES:
            if deadline.expired():
                break
            trials += 1
            try:
                model = preprocessing.StandardScaler() | linear_model.LinearRegression(
                    optimizer=optim.SGD(lr))
                adwin = drift.ADWIN()
                residuals: list[float] = []
                drifts: list[str] = []
                for i in range(WINDOW + 3, r.shape[0]):
                    x = {"r1": float(r[i - 1]), "r2": float(r[i - 2]), "r3": float(r[i - 3]),
                         "v": float(vol[i - 1])}
                    y = float(r[i])
                    pred = float(model.predict_one(x) or 0.0)
                    model.learn_one(x, y)
                    res = y - pred
                    residuals.append(res)
                    adwin.update(res)
                    if adwin.drift_detected:
                        drifts.append(f.time[i + 1])
            except Exception as exc:
                reps.append({"kind": "UNMEASURED", "symbol": f.symbol, "lr": lr,
                             "why": f"{type(exc).__name__}: {exc}"[:200]})
                continue
            arr = np.asarray(residuals)
            reps.append({"kind": "online_residual_signal", "symbol": f.symbol,
                         "timeframe": f.timeframe,
                         "model": f"StandardScaler | LinearRegression(SGD lr={lr})",
                         "features": ["r1", "r2", "r3", f"v{WINDOW}"],
                         "residual_std": float(arr.std()), "residual_mae": float(
                             np.abs(arr).mean()), "residual_tail": arr[-24:],
                         "n_drifts": len(drifts), "drift_times": drifts[-10:],
                         "representation": "one-step residuals and ADWIN drift marks; a "
                                           "state series for the forge, not a forecast"})
    return A.packet(SYSTEM, bundle, trials=trials, representations=reps)


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
