"""MAPIE adapter -- conformal intervals around an existing (ridge) forecast -> uncertainty
representations.

The forecast is a ridge regression of the next H1 return on three lags and realised vol; MAPIE
wraps it in split-conformal intervals at each confidence level (one charged trial per level per
symbol). The desk receives measured coverage and width on a held-out tail -- an uncertainty
representation for the forge, never a forecast to act on.
"""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "mapie"
LEVELS: tuple[float, ...] = (0.8, 0.9)
WINDOW = 24


def _intervals(mapie_reg: Any, ridge: Any, X: Any, y: Any, level: float,
               cut: tuple[int, int]) -> tuple[Any, Any, str]:
    """(point, [lo, hi], api): MAPIE 1.x split conformal, falling back to the 0.x regressor."""
    a, b = cut
    if hasattr(mapie_reg, "SplitConformalRegressor"):
        scr = mapie_reg.SplitConformalRegressor(estimator=ridge, confidence_level=level,
                                                prefit=False)
        scr.fit(X[:a], y[:a])
        scr.conformalize(X[a:b], y[a:b])
        pt, pis = scr.predict_interval(X[b:])
        return pt, pis[:, :, 0], "mapie>=1 SplitConformalRegressor"
    reg = mapie_reg.MapieRegressor(estimator=ridge, method="base", cv="split")
    reg.fit(X[:b], y[:b])
    pt, pis = reg.predict(X[b:], alpha=1.0 - level)
    return pt, pis[:, :, 0], "mapie<1 MapieRegressor(split)"


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    mapie_reg = A.library("mapie.regression")
    lin = A.library("sklearn.linear_model")
    if mapie_reg is None or lin is None:
        return A.unmeasured(SYSTEM, bundle, "mapie (or scikit-learn) is not importable here")
    import numpy as np
    deadline = A.Deadline(bundle.compute_budget_s)
    trials = 0
    reps: list[dict[str, Any]] = []
    for f in bundle.frames("H1"):
        r = f.log_returns()
        if r.shape[0] < 300:
            continue
        vol = A.realised_vol(r, WINDOW)
        idx = np.arange(WINDOW + 3, r.shape[0])
        X = np.column_stack([r[idx - 1], r[idx - 2], r[idx - 3], vol[idx - 1]])
        y = r[idx]
        n = X.shape[0]
        cut = (int(n * 0.6), int(n * 0.8))
        for level in LEVELS:
            if deadline.expired():
                break
            trials += 1
            try:
                pt, pis, api = _intervals(mapie_reg, lin.Ridge(alpha=1.0), X, y, level, cut)
                lo, hi = np.asarray(pis[:, 0], float), np.asarray(pis[:, 1], float)
                yt = y[cut[1]:]
            except Exception as exc:
                reps.append({"kind": "UNMEASURED", "symbol": f.symbol, "level": level,
                             "why": f"{type(exc).__name__}: {exc}"[:200]})
                continue
            reps.append({"kind": "conformal_interval", "symbol": f.symbol,
                         "timeframe": f.timeframe, "api": api, "confidence_level": level,
                         "n_test": int(yt.shape[0]),
                         "coverage_measured": float(np.mean((yt >= lo) & (yt <= hi))),
                         "mean_width": float(np.mean(hi - lo)),
                         "width_over_vol": float(np.mean(hi - lo) / max(float(yt.std()), 1e-12)),
                         "last_interval": [float(lo[-1]), float(hi[-1])],
                         "last_point": float(np.asarray(pt, float)[-1]),
                         "representation": "interval width relative to realised vol is an "
                                           "uncertainty state; coverage says whether the "
                                           "exchangeability assumption held on the tail"})
    return A.packet(SYSTEM, bundle, trials=trials, representations=reps)


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
