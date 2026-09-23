"""Merlion adapter -- an isolation-forest anomaly score over returns, trained on the head of
each frame and scored on the tail; the tail's score distribution and the last score are
a REPRESENTATION of how unusual the present is.
"""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "merlion"
CAPABILITY_FAMILY = "anomaly_detection"
LICENCE_EXPECTED = "BSD-3-Clause"
MAX_SYMBOLS = 4


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    mu = A.library("merlion.utils")
    mif = A.library("merlion.models.anomaly.isolation_forest")
    pd = A.library("pandas")
    if mu is None or mif is None or pd is None:
        return A.unmeasured(SYSTEM, bundle, "merlion is not importable here (pip install "
                                            "salesforce-merlion==2.0.4)")
    import numpy as np
    deadline = A.Deadline(bundle.compute_budget_s)
    trials = 0
    reps: list[dict[str, Any]] = []
    for f in bundle.frames("H1")[:MAX_SYMBOLS]:
        if deadline.expired() or len(f) < 600:
            continue
        trials += 1
        r = f.log_returns()[-600:]
        idx = pd.to_datetime(list(f.time[-600:]))
        try:
            ts = mu.TimeSeries.from_pd(pd.DataFrame({"r": r, "a": np.abs(r)}, index=idx))
            train, test = ts.bisect(idx[450])
            model = mif.IsolationForest(mif.IsolationForestConfig())
            model.train(train)
            scores = np.asarray(model.get_anomaly_score(test).to_pd().iloc[:, 0], dtype=float)
        except Exception as exc:
            reps.append({"kind": "UNMEASURED", "symbol": f.symbol,
                         "why": f"{type(exc).__name__}: {exc}"[:200]})
            continue
        reps.append({"kind": "anomaly_scores", "symbol": f.symbol, "model": "IsolationForest",
                     "n_test": int(scores.shape[0]), "last": float(scores[-1]),
                     "p90": float(np.percentile(scores, 90)),
                     "last_is_top_decile": bool(scores[-1] >= np.percentile(scores, 90)),
                     "representation": "an anomalous present is a state for the forge"})
    return A.packet(SYSTEM, bundle, trials=trials, representations=reps)


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
