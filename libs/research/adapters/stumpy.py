"""STUMPY adapter -- matrix-profile motifs and discords -> pattern representations and cells.

For each H1 frame and window length the matrix profile is computed once (one charged trial);
the closest pair of windows is the motif, the farthest window the discord. The desk receives
both as a representation and a cell per symbol: continuation when the two motif occurrences
were followed by same-signed drift, a range reversion otherwise.
"""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "stumpy"
WINDOWS: tuple[int, ...] = (24, 48)
POST = 24


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    st = A.library("stumpy")
    if st is None:
        return A.unmeasured(SYSTEM, bundle, "stumpy (numba-backed) is not importable here")
    import numpy as np
    deadline = A.Deadline(bundle.compute_budget_s)
    trials = 0
    reps: list[dict[str, Any]] = []
    cands: list[dict[str, Any]] = []
    for f in bundle.frames("H1"):
        r = f.log_returns()
        if r.shape[0] < 200:
            continue
        for m in WINDOWS:
            if deadline.expired():
                break
            trials += 1
            try:
                mp = st.stump(np.ascontiguousarray(r, dtype=float), m)
                dist = np.asarray(mp[:, 0], dtype=float)
                nn = np.asarray(mp[:, 1], dtype=int)
            except Exception as exc:
                reps.append({"kind": "UNMEASURED", "symbol": f.symbol, "m": m,
                             "why": f"{type(exc).__name__}: {exc}"[:200]})
                continue
            finite = np.where(np.isfinite(dist), dist, np.inf)
            i = int(np.argmin(finite))
            j = int(nn[i])
            d = int(np.argmax(np.where(np.isfinite(dist), dist, -np.inf)))
            post = [float(np.sum(r[k + m:k + m + POST])) for k in (i, j)
                    if k + m + POST <= r.shape[0]]
            reps.append({"kind": "matrix_profile", "symbol": f.symbol, "timeframe": f.timeframe,
                         "m": m, "motif_idx": [i, j], "motif_time": [f.time[i + 1], f.time[j + 1]],
                         "motif_distance": float(dist[i]), "discord_idx": d,
                         "discord_time": f.time[d + 1], "discord_distance": float(dist[d]),
                         "profile_mean": float(np.nanmean(dist)),
                         "post_motif_drift": post})
            if len(post) == 2 and m == WINDOWS[0]:
                same = (post[0] > 0) == (post[1] > 0)
                family = "momentum_volgate" if same else "range_reversion"
                cands.append(A.candidate(
                    family, [f.symbol],
                    f"{f.symbol} H1: STUMPY's closest {m}-bar motif pair (distance "
                    f"{dist[i]:.2f}) was followed by {POST}-bar drifts of {post[0]:+.4f} and "
                    f"{post[1]:+.4f}; a {family.replace('_', ' ')} hypothesis on recurrence",
                    horizon=bundle.horizons[-1], source=SYSTEM,
                    evidence={"m": m, "motif_time": [f.time[i + 1], f.time[j + 1]],
                              "post_motif_drift": post, "discord_time": f.time[d + 1]}))
    return A.packet(SYSTEM, bundle, trials=trials, representations=reps, candidates=cands)


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
