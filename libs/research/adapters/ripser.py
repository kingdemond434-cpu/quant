"""Ripser adapter -- persistent homology of a delay-embedded return cloud per window; the
maximum H1 persistence per window is a REPRESENTATION of cyclic structure, and a spike in
the latest window yields a vol_transition hypothesis.
"""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "ripser"
CAPABILITY_FAMILY = "topology"
LICENCE_EXPECTED = "MIT"
MAX_SYMBOLS = 4
WINDOW = 120
N_WINDOWS = 6
DIM = 3
SPIKE = 1.5


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    rp = A.library("ripser")
    if rp is None:
        return A.unmeasured(SYSTEM, bundle, "ripser is not importable here (pip install "
                                            "ripser==0.6.15)")
    import numpy as np
    deadline = A.Deadline(bundle.compute_budget_s)
    trials = 0
    reps: list[dict[str, Any]] = []
    cands: list[dict[str, Any]] = []
    for f in bundle.frames("H1")[:MAX_SYMBOLS]:
        r = f.log_returns()
        if deadline.expired() or r.shape[0] < WINDOW * N_WINDOWS + DIM:
            continue
        pers: list[float] = []
        for w in range(N_WINDOWS):
            b = r.shape[0] - w * WINDOW
            seg = r[b - WINDOW - DIM + 1:b]
            cloud = np.column_stack([seg[i:i + WINDOW] for i in range(DIM)])
            trials += 1
            try:
                dg = rp.ripser(cloud, maxdim=1)["dgms"][1]
                life = (dg[:, 1] - dg[:, 0]) if dg.size else np.asarray([0.0])
                pers.append(float(np.max(life[np.isfinite(life)])) if np.isfinite(life).any()
                            else 0.0)
            except Exception as exc:
                reps.append({"kind": "UNMEASURED", "symbol": f.symbol, "window": w,
                             "why": f"{type(exc).__name__}: {exc}"[:200]})
                break
        if not pers:
            continue
        pers = pers[::-1]  # oldest first
        reps.append({"kind": "persistent_homology", "symbol": f.symbol, "dim": DIM,
                     "window": WINDOW, "h1_max_persistence": pers,
                     "representation": "H1 persistence measures cyclic structure in the "
                                       "delay embedding; a spike is a regime state"})
        med = float(np.median(pers[:-1])) if len(pers) > 1 else 0.0
        if med > 0 and pers[-1] > SPIKE * med:
            cands.append(A.candidate(
                "vol_transition", [f.symbol],
                f"{f.symbol} H1: H1 persistence {pers[-1]:.4f} is "
                f"{pers[-1] / med:.1f}x the median of the previous windows -- a topology-dated "
                f"volatility transition hypothesis",
                horizon=bundle.horizons[-1], source=SYSTEM,
                evidence={"persistence_last": pers[-1], "persistence_median": med}))
    return A.packet(SYSTEM, bundle, trials=trials, representations=reps, candidates=cands)


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
