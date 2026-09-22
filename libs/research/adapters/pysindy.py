"""PySINDy adapter -- sparse identification of governing equations -> mechanism packets.

State per symbol: demeaned log price, 24-bar realised volatility, 24-bar momentum. SINDy with a
degree-2 polynomial library and STLSQ at each threshold is one charged trial; the discovered
equations, active-term counts and in-sample fit go to the desk as MECHANISM candidates -- a
proposed dynamical law to be tested, never a fitted model to be trusted.
"""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "pysindy"
THRESHOLDS: tuple[float, ...] = (0.05, 0.1, 0.2)
WINDOW = 24


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    ps = A.library("pysindy")
    if ps is None:
        return A.unmeasured(SYSTEM, bundle, "pysindy is not importable in this environment")
    import numpy as np
    deadline = A.Deadline(bundle.compute_budget_s)
    trials = 0
    mechs: list[dict[str, Any]] = []
    for f in bundle.frames("H1"):
        c = np.asarray(f.close, dtype=float)
        if c.shape[0] < 4 * WINDOW:
            continue
        lp = np.log(np.maximum(c, 1e-12))
        r = np.diff(lp)
        vol = A.realised_vol(r, WINDOW)
        mom = np.concatenate([np.full(WINDOW, np.nan), lp[WINDOW:] - lp[:-WINDOW]])[1:]
        X = np.column_stack([(lp[1:] - lp[1:].mean()), vol, mom])
        X = X[~np.isnan(X).any(axis=1)][-600:]
        for th in THRESHOLDS:
            if deadline.expired():
                break
            trials += 1
            try:
                model = ps.SINDy(optimizer=ps.STLSQ(threshold=th),
                                 feature_library=ps.PolynomialLibrary(degree=2),
                                 feature_names=["p", "v", "m"])
                model.fit(X, t=1.0)
                eqs = [str(e) for e in model.equations(precision=3)]
                coef = np.asarray(model.coefficients(), dtype=float)
                r2 = float(model.score(X, t=1.0))
            except Exception as exc:
                mechs.append({"kind": "UNMEASURED", "symbol": f.symbol, "threshold": th,
                              "why": f"{type(exc).__name__}: {exc}"[:200]})
                continue
            mechs.append({"kind": "governing_equation", "symbol": f.symbol,
                          "timeframe": f.timeframe, "state": ["p: demeaned log price",
                                                              f"v: {WINDOW}-bar realised vol",
                                                              f"m: {WINDOW}-bar momentum"],
                          "library": "polynomial degree 2", "threshold": th,
                          "equations": eqs, "n_active_terms": int((np.abs(coef) > 0).sum()),
                          "fit_r2_in_sample": r2, "n_obs": int(X.shape[0]),
                          "mechanism": "a sparse ODE the engine proposes for the state; test "
                                       "whether its implied drift predicts out of sample"})
    return A.packet(SYSTEM, bundle, trials=trials, mechanisms=mechs)


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
