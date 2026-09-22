"""pyextremes adapter -- peaks-over-threshold on absolute returns -> tail-exceedance states and
cells.

Each (symbol, threshold quantile) is one charged trial: exceedances are declustered over 24
hours and a GPD is fitted by MLE. The desk receives the tail state (shape, scale, count, last
exceedance) and, where the last exceedance is recent, a vol-mean-reversion hypothesis.
"""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "pyextremes"
QUANTILES: tuple[float, ...] = (0.95, 0.98)
RECENT_BARS = 48


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    pe = A.library("pyextremes")
    pd = A.library("pandas")
    if pe is None or pd is None:
        return A.unmeasured(SYSTEM, bundle, "pyextremes (or pandas) is not importable here")
    import numpy as np
    deadline = A.Deadline(bundle.compute_budget_s)
    trials = 0
    reps: list[dict[str, Any]] = []
    cands: list[dict[str, Any]] = []
    for f in bundle.frames("H1"):
        r = f.log_returns()
        if r.shape[0] < 400:
            continue
        idx = pd.to_datetime(list(f.time[1:]), utc=True).tz_convert(None)
        s = pd.Series(np.abs(r), index=idx)
        for q in QUANTILES:
            if deadline.expired():
                break
            trials += 1
            thr = float(np.quantile(s.to_numpy(), q))
            try:
                model = pe.EVA(s)
                model.get_extremes(method="POT", threshold=thr, r="24h")
                model.fit_model()
                params = dict(model.distribution.mle_parameters)
                extremes = model.extremes
                n_exc = len(extremes)
                last = extremes.index[-1] if n_exc else None
            except Exception as exc:
                reps.append({"kind": "UNMEASURED", "symbol": f.symbol, "quantile": q,
                             "why": f"{type(exc).__name__}: {exc}"[:200]})
                continue
            bars_since = int((idx[-1] - last) / pd.Timedelta(hours=1)) if last is not None \
                else None
            reps.append({"kind": "tail_exceedance_state", "symbol": f.symbol,
                         "timeframe": f.timeframe, "threshold_quantile": q,
                         "threshold_abs_return": thr, "n_exceedances": n_exc,
                         "decluster": "24h", "gpd_shape": float(params.get("c", float("nan"))),
                         "gpd_scale": float(params.get("scale", float("nan"))),
                         "last_exceedance": str(last) if last is not None else None,
                         "bars_since_last_exceedance": bars_since})
            if q == QUANTILES[0] and bars_since is not None and bars_since <= RECENT_BARS:
                cands.append(A.candidate(
                    "vol_mean_reversion", [f.symbol],
                    f"{f.symbol} H1: pyextremes marks an absolute-return exceedance of the "
                    f"{q:.0%} threshold {bars_since} bars ago (GPD shape "
                    f"{params.get('c', float('nan')):.3f}); a vol mean reversion hypothesis "
                    f"after a tail event", horizon=bundle.horizons[-1], source=SYSTEM,
                    evidence={"threshold": thr, "bars_since_last_exceedance": bars_since,
                              "n_exceedances": n_exc, "gpd_shape": params.get("c")}))
    return A.packet(SYSTEM, bundle, trials=trials, representations=reps, candidates=cands)


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
