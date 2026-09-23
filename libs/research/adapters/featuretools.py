"""Featuretools adapter -- deep feature synthesis over the bar table (transform primitives at
depth 1). Every synthesised feature is a charged trial; the ten most related to the next
return (absolute rank correlation on the tail) are donated as REPRESENTATIONS.
"""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "featuretools"
CAPABILITY_FAMILY = "feature_synthesis"
LICENCE_EXPECTED = "BSD-3-Clause"
MAX_SYMBOLS = 3
PRIMITIVES = ("percent_change", "diff", "cum_mean", "cum_max", "cum_min")


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    ft = A.library("featuretools")
    pd = A.library("pandas")
    if ft is None or pd is None:
        return A.unmeasured(SYSTEM, bundle, "featuretools (or pandas) is not importable here "
                                            "(pip install featuretools==1.31.0)")
    import numpy as np
    deadline = A.Deadline(bundle.compute_budget_s)
    trials = 0
    reps: list[dict[str, Any]] = []
    for f in bundle.frames("H1")[:MAX_SYMBOLS]:
        if deadline.expired() or len(f) < 500:
            continue
        df = pd.DataFrame({"bar_id": np.arange(len(f)), "time": pd.to_datetime(list(f.time)),
                           "open": f.open, "high": f.high, "low": f.low, "close": f.close,
                           "volume": f.volume})
        try:
            es = ft.EntitySet("bars")
            es = es.add_dataframe(dataframe_name="bars", dataframe=df, index="bar_id",
                                  time_index="time")
            fm, _ = ft.dfs(entityset=es, target_dataframe_name="bars",
                               trans_primitives=PRIMITIVES, max_depth=1, verbose=False)
        except Exception as exc:
            reps.append({"kind": "UNMEASURED", "symbol": f.symbol,
                         "why": f"{type(exc).__name__}: {exc}"[:200]})
            continue
        y = np.append(f.log_returns(), np.nan)
        scored: list[tuple[float, str]] = []
        for col in fm.columns:
            x = pd.to_numeric(fm[col], errors="coerce").to_numpy(dtype=float)
            ok = np.isfinite(x[:-1]) & np.isfinite(y[1:])
            if ok.sum() < 200 or np.nanstd(x[:-1][ok]) == 0:
                continue
            trials += 1
            rx = np.argsort(np.argsort(x[:-1][ok])).astype(float)
            ry = np.argsort(np.argsort(y[1:][ok])).astype(float)
            scored.append((float(np.corrcoef(rx, ry)[0, 1]), str(col)))
        scored.sort(key=lambda t: -abs(t[0]))
        reps.append({"kind": "synthesised_features", "symbol": f.symbol, "n_features": len(scored),
                     "top": [{"feature": c, "rank_corr_next_return": v} for v, c in scored[:10]],
                     "primitives": list(PRIMITIVES),
                     "representation": "a synthesised feature's rank correlation with the next "
                                       "return is a candidate state; in-sample, for the forge"})
    return A.packet(SYSTEM, bundle, trials=trials, representations=reps)


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
