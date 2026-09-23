"""tslearn adapter -- DTW k-means over return windows -> motif-cluster representations and
cells.

Windows of 24 H1 returns are clustered under dynamic time warping for each k (one charged trial
per k per symbol). The desk receives the cluster centroids, sizes and the mean drift that
followed each cluster's windows; the cluster whose members were followed by the largest drift
leaves as a continuation or pullback hypothesis.
"""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "tslearn"
KS: tuple[int, ...] = (3, 4)
WINDOW, POST, MAX_WINDOWS, MAX_SYMBOLS = 24, 12, 120, 4


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    clu = A.library("tslearn.clustering")
    pre = A.library("tslearn.preprocessing")
    if clu is None or pre is None:
        return A.unmeasured(SYSTEM, bundle, "tslearn is not importable in this environment")
    import numpy as np
    deadline = A.Deadline(bundle.compute_budget_s)
    trials = 0
    reps: list[dict[str, Any]] = []
    cands: list[dict[str, Any]] = []
    for f in bundle.frames("H1")[:MAX_SYMBOLS]:
        r = f.log_returns()
        if r.shape[0] < WINDOW * 6:
            continue
        starts = list(range(max(0, r.shape[0] - POST - MAX_WINDOWS * WINDOW), r.shape[0] - WINDOW
                            - POST, WINDOW))[-MAX_WINDOWS:]
        W = np.stack([r[a:a + WINDOW] for a in starts])[:, :, None]
        post = np.array([float(np.sum(r[a + WINDOW:a + WINDOW + POST])) for a in starts])
        trend = np.array([float(np.sum(r[a:a + WINDOW])) for a in starts])
        Ws = pre.TimeSeriesScalerMeanVariance().fit_transform(W)
        for k in KS:
            if deadline.expired():
                break
            trials += 1
            try:
                km = clu.TimeSeriesKMeans(n_clusters=k, metric="dtw", max_iter=5,
                                          random_state=bundle.seed, n_jobs=1).fit(Ws)
                labels = np.asarray(km.labels_)
                centers = np.asarray(km.cluster_centers_)[:, :, 0]
            except Exception as exc:
                reps.append({"kind": "UNMEASURED", "symbol": f.symbol, "k": k,
                             "why": f"{type(exc).__name__}: {exc}"[:200]})
                continue
            by: list[dict[str, Any]] = []
            for c in range(k):
                mask = labels == c
                by.append({"cluster": int(c), "n": int(mask.sum()),
                           "post_drift_mean": float(post[mask].mean()) if mask.any() else None,
                           "window_trend_mean": float(trend[mask].mean()) if mask.any()
                           else None})
            reps.append({"kind": "dtw_motif_cluster", "symbol": f.symbol,
                         "timeframe": f.timeframe, "k": k, "window_bars": WINDOW,
                         "n_windows": int(W.shape[0]), "inertia": float(km.inertia_),
                         "centroids": centers, "clusters": by})
            if k == KS[0]:
                strongest = max((b for b in by if b["post_drift_mean"] is not None),
                                key=lambda b: abs(float(b["post_drift_mean"])), default=None)
                if strongest is None or strongest["n"] < 5:
                    continue
                same = (float(strongest["post_drift_mean"]) > 0) == (
                    float(strongest["window_trend_mean"]) > 0)
                family = "momentum_volgate" if same else "pullback_entry"
                cands.append(A.candidate(
                    family, [f.symbol],
                    f"{f.symbol} H1: tslearn DTW cluster {strongest['cluster']} of {k} "
                    f"({strongest['n']} windows) was followed by mean {POST}-bar drift "
                    f"{float(strongest['post_drift_mean']):+.4f}; a "
                    f"{family.replace('_', ' ')} hypothesis on shape recurrence",
                    horizon=bundle.horizons[0], source=SYSTEM,
                    evidence={"k": k, "cluster": strongest, "window_bars": WINDOW}))
    return A.packet(SYSTEM, bundle, trials=trials, representations=reps, candidates=cands)


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
