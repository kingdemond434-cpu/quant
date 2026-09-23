"""aeon adapter -- ClaSP segmentation of the return series (self-supervised change points);
segments are a REPRESENTATION and the current segment's vol ratio yields a vol_transition
or range_reversion hypothesis.
"""
from __future__ import annotations

from itertools import pairwise
from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "aeon"
CAPABILITY_FAMILY = "time_series_mining"
LICENCE_EXPECTED = "BSD-3-Clause"

WINDOW = 720
N_CPS = 3


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    seg = A.library("aeon.segmentation")
    if seg is None:
        return A.unmeasured(SYSTEM, bundle, "aeon is not importable here (pip install aeon==1.6.0)")
    import numpy as np
    deadline = A.Deadline(bundle.compute_budget_s)
    trials = 0
    reps: list[dict[str, Any]] = []
    cands: list[dict[str, Any]] = []
    for f in bundle.frames("H1"):
        if deadline.expired() or len(f) < 400:
            continue
        r = f.log_returns()[-WINDOW:]
        trials += 1
        try:
            cps = [int(c) for c in seg.ClaSPSegmenter(period_length=24, n_cps=N_CPS).fit_predict(
                np.abs(r))]
        except Exception as exc:
            reps.append({"kind": "UNMEASURED", "symbol": f.symbol,
                         "why": f"{type(exc).__name__}: {exc}"[:200]})
            continue
        edges = [0, *sorted(cps), r.shape[0]]
        vols = [float(np.std(r[a:b])) for a, b in pairwise(edges) if b > a + 5]
        reps.append({"kind": "clasp_segments", "symbol": f.symbol, "change_points": cps,
                     "segment_vol": vols, "window": WINDOW})
        if len(vols) >= 2:
            ratio = vols[-1] / max(vols[-2], 1e-12)
            family = "vol_transition" if (ratio > 1.3 or ratio < 0.77) else "range_reversion"
            cands.append(A.candidate(
                family, [f.symbol],
                f"{f.symbol} H1: aeon ClaSP puts the last change point {r.shape[0] - edges[-2]} "
                f"bars ago; current-segment vol is {ratio:.2f}x the previous -- {family}",
                horizon=bundle.horizons[-1], source=SYSTEM,
                evidence={"vol_ratio": ratio, "change_points": cps}))
    return A.packet(SYSTEM, bundle, trials=trials, representations=reps, candidates=cands)


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
