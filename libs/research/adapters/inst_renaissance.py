"""Renaissance-style adapter (REBUILT, numpy only) -- the published capability is the COMMON MODEL:
one model over everything rather than a model per instrument. The adapter measures that claim
here by fitting a pooled ridge across all frames and a separate ridge per frame, then comparing
their out-of-sample rank correlations on the same held-out bars. The comparison is a research
method, not a verdict on either."""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "inst_renaissance"
CAPABILITY_FAMILY = "institutional_capability"
LICENCE_EXPECTED = "N/A (public architecture)"
RUNS_WITHOUT_LIBRARY = True


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    import numpy as np
    frames = [f for f in bundle.frames("H1") if len(f) > 400]
    if len(frames) < 2:
        return A.unmeasured(SYSTEM, bundle, "fewer than two long H1 frames to pool")
    parts = [(f.symbol, *A.lagged_design(f)[:2]) for f in frames]
    parts = [(s, X, y) for s, X, y in parts if X.shape[0] > 120]
    if len(parts) < 2:
        return A.unmeasured(SYSTEM, bundle, "fewer than two usable design matrices")
    rows: list[dict[str, Any]] = []
    trials = 0

    def fit(X: Any, y: Any) -> Any:
        return np.linalg.solve(X.T @ X + np.eye(X.shape[1]), X.T @ y)

    def ic(p: Any, y: Any) -> float:
        if p.shape[0] < 30 or float(np.std(p)) <= 0 or float(np.std(y)) <= 0:
            return float("nan")
        return float(np.corrcoef(p, y)[0, 1])

    cuts = [(X.shape[0] * 2) // 3 for _, X, _ in parts]
    Xtr = np.vstack([X[:c] for (_, X, _), c in zip(parts, cuts, strict=True)])
    ytr = np.concatenate([y[:c] for (_, _, y), c in zip(parts, cuts, strict=True)])
    w_pool = fit(Xtr, ytr)
    trials += 1
    for (sym, X, y), c in zip(parts, cuts, strict=True):
        trials += 1
        w_own = fit(X[:c], y[:c])
        rows.append({"symbol": sym, "n_train": int(c), "n_test": int(X.shape[0] - c),
                     "ic_common_model": ic(X[c:] @ w_pool, y[c:]),
                     "ic_own_model": ic(X[c:] @ w_own, y[c:])})
    both = [r for r in rows if np.isfinite(r["ic_common_model"]) and np.isfinite(r["ic_own_model"])]
    return A.packet(
        SYSTEM, bundle, trials=trials,
        research_methods=[{
            "kind": "common_model_comparison", "system": SYSTEM, "per_symbol": rows,
            "n_compared": len(both),
            "mean_ic_common": float(np.mean([r["ic_common_model"] for r in both]))
            if both else None,
            "mean_ic_own": float(np.mean([r["ic_own_model"] for r in both])) if both else None,
            "method": ("one pooled ridge against one ridge per instrument, both measured on the "
                       "same held-out third of each frame")}],
        note=f"common vs per-instrument model over {len(rows)} frames")


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
