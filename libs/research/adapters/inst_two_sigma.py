"""Two Sigma-style adapter (REBUILT, numpy only) -- the published capability is FEATURE
ORTHOGONALITY and the hypothesis-evaluation bottleneck. The adapter measures the desk's own
shared design matrix: the feature correlation matrix, its condition number and effective rank,
and each feature's redundancy against the rest. A design whose columns repeat each other spends
the trial budget twice for one question."""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "inst_two_sigma"
CAPABILITY_FAMILY = "institutional_capability"
LICENCE_EXPECTED = "N/A (public architecture)"
RUNS_WITHOUT_LIBRARY = True


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    import numpy as np
    frames = [f for f in bundle.frames("H1") if len(f) > 200]
    if not frames:
        return A.unmeasured(SYSTEM, bundle, "no H1 frame carries more than 200 bars")
    rows: list[dict[str, Any]] = []
    trials = 0
    for f in frames:
        X, _, _ = A.lagged_design(f)
        if X.shape[0] < 60:
            continue
        trials += 1
        C = np.nan_to_num(np.corrcoef(X, rowvar=False), nan=0.0)
        ev = np.maximum(np.linalg.eigvalsh(C), 0.0)
        p = ev / max(float(ev.sum()), 1e-12)
        eff = float(np.exp(-float(np.sum(np.where(p > 0, p * np.log(np.maximum(p, 1e-12)),
                                                  0.0)))))
        off = np.abs(C) - np.eye(C.shape[0])
        rows.append({"symbol": f.symbol, "features": list(A.LAGGED_FEATURE_NAMES),
                     "effective_rank": eff, "n_features": int(X.shape[1]),
                     "condition_number": float(ev.max() / max(ev.min(), 1e-12)),
                     "redundancy": {name: float(off[i].max())
                                    for i, name in enumerate(A.LAGGED_FEATURE_NAMES)}})
    if not rows:
        return A.unmeasured(SYSTEM, bundle, "no frame produced a usable design matrix")
    return A.packet(
        SYSTEM, bundle, trials=trials,
        representations=[{
            "kind": "feature_orthogonality", "system": SYSTEM, "frames": rows,
            "mean_effective_rank": float(np.mean([r["effective_rank"] for r in rows])),
            "representation": ("how independent the desk's shared design columns really are; "
                               "redundancy is each feature's largest correlation with another")}],
        note=f"{len(rows)} design matrices measured")


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
