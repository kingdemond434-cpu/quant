"""ruptures adapter -- change-point segmentation -> regime-boundary representations and cells.

The engine (Pelt over an RBF cost on log returns) finds where the return distribution changed;
each (frame, penalty) is one charged trial. The desk receives the boundaries and per-segment
volatility as a representation, and one hypothesis per symbol about the CURRENT segment: a
volatility transition when the last segment's vol differs materially from the previous one's,
a range reversion otherwise. The gauntlet judges both; ruptures judges nothing.
"""
from __future__ import annotations

from itertools import pairwise
from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "ruptures"
PENALTIES: tuple[float, ...] = (1.0, 3.0, 10.0, 30.0)


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    rpt = A.library("ruptures")
    if rpt is None:
        return A.unmeasured(SYSTEM, bundle, "ruptures is not importable in this environment")
    import numpy as np
    deadline = A.Deadline(bundle.compute_budget_s)
    trials = 0
    reps: list[dict[str, Any]] = []
    cands: list[dict[str, Any]] = []
    for f in bundle.frames("H1"):
        r = f.log_returns()
        if r.shape[0] < 120:
            continue
        best: dict[str, Any] | None = None
        for pen in PENALTIES:
            if deadline.expired():
                break
            trials += 1
            try:
                algo = rpt.Pelt(model="rbf", min_size=24, jump=4).fit(r.reshape(-1, 1))
                bkps = [int(b) for b in algo.predict(pen=pen)]
            except Exception as exc:
                reps.append({"kind": "UNMEASURED", "symbol": f.symbol, "penalty": pen,
                             "why": f"{type(exc).__name__}: {exc}"[:200]})
                continue
            edges = [0, *bkps]
            seg_vol = [float(np.std(r[a:b])) for a, b in pairwise(edges)
                       if b > a]
            row = {"kind": "regime_boundaries", "symbol": f.symbol, "timeframe": f.timeframe,
                   "method": "ruptures.Pelt(rbf, min_size=24, jump=4)", "penalty": pen,
                   "n_segments": len(seg_vol),
                   "boundaries": [f.time[min(b, len(f) - 1)] for b in bkps[:-1]],
                   "segment_vol": seg_vol, "last_segment_bars": int(bkps[-1] - edges[-2])}
            reps.append(row)
            if len(seg_vol) >= 2 and (best is None or len(seg_vol) <= best["n_segments"]):
                best = row
        if best is None:
            continue
        ratio = best["segment_vol"][-1] / max(best["segment_vol"][-2], 1e-12)
        family = "vol_transition" if (ratio > 1.3 or ratio < 0.77) else "range_reversion"
        cands.append(A.candidate(
            family, [f.symbol],
            f"{f.symbol} H1: ruptures found a change point {best['last_segment_bars']} bars ago "
            f"(penalty {best['penalty']}); the current segment's realised vol is {ratio:.2f}x "
            f"the previous segment's -- a {family.replace('_', ' ')} hypothesis",
            horizon=bundle.horizons[-1], source=SYSTEM,
            evidence={"vol_ratio": ratio, "last_boundary": best["boundaries"][-1],
                      "penalty": best["penalty"], "n_segments": best["n_segments"]}))
    return A.packet(SYSTEM, bundle, trials=trials, representations=reps, candidates=cands,
                    note=f"{len(reps)} segmentations over {len(bundle.frames('H1'))} frames")


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
