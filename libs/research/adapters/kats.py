"""Kats adapter -- CUSUM change points in the return mean per symbol; the change points are a
REPRESENTATION and a recent one yields a vol_transition hypothesis for the gauntlet.
"""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "kats"
CAPABILITY_FAMILY = "change_point"
LICENCE_EXPECTED = "MIT"
WINDOW = 720


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    kc = A.library("kats.consts")
    kd = A.library("kats.detectors.cusum_detection")
    pd = A.library("pandas")
    if kc is None or kd is None or pd is None:
        return A.unmeasured(SYSTEM, bundle, "kats is not importable here (pip install kats==0.2.0)")
    import numpy as np
    deadline = A.Deadline(bundle.compute_budget_s)
    trials = 0
    reps: list[dict[str, Any]] = []
    cands: list[dict[str, Any]] = []
    for f in bundle.frames("H1"):
        if deadline.expired() or len(f) < 300:
            continue
        r = f.log_returns()[-WINDOW:]
        trials += 1
        try:
            ts = kc.TimeSeriesData(time=pd.to_datetime(list(f.time[-WINDOW:])),
                                   value=pd.Series(np.abs(r)))
            cps = kd.CUSUMDetector(ts).detector(change_directions=["increase", "decrease"])
            points = [(str(cp.start_time), str(cp.direction)) for cp in cps]
        except Exception as exc:
            reps.append({"kind": "UNMEASURED", "symbol": f.symbol,
                         "why": f"{type(exc).__name__}: {exc}"[:200]})
            continue
        reps.append({"kind": "change_points", "symbol": f.symbol, "method": "kats CUSUM on |r|",
                     "points": points, "window": WINDOW})
        if points:
            cands.append(A.candidate(
                "vol_transition", [f.symbol],
                f"{f.symbol} H1: Kats CUSUM found a {points[-1][1]} in |return| at "
                f"{points[-1][0]} -- a volatility transition hypothesis",
                horizon=bundle.horizons[-1], source=SYSTEM,
                evidence={"last_change_point": points[-1][0], "direction": points[-1][1],
                          "n_change_points": len(points)}))
    return A.packet(SYSTEM, bundle, trials=trials, representations=reps, candidates=cands)


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
