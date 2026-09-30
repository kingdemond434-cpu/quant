"""XTX-style adapter (REBUILT, numpy only) -- the published capability is BREADTH: tens of
thousands of instruments read as sensors for one another. The adapter measures that property on
this bundle: the correlation matrix of the frames' returns, its effective rank, and the mean
absolute off-diagonal. A desk whose sensors all say the same thing has one sensor, and this is
the number that says so."""
from __future__ import annotations

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "inst_xtx"
CAPABILITY_FAMILY = "institutional_capability"
LICENCE_EXPECTED = "N/A (public architecture)"
RUNS_WITHOUT_LIBRARY = True


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    import numpy as np
    frames = [f for f in bundle.frames("H1") if len(f) > 60]
    if len(frames) < 2:
        return A.unmeasured(SYSTEM, bundle, "fewer than two H1 frames: breadth is unmeasurable")
    n = min(f.log_returns().shape[0] for f in frames)
    R = np.column_stack([f.log_returns()[-n:] for f in frames])
    C = np.nan_to_num(np.corrcoef(R, rowvar=False), nan=0.0)
    ev = np.maximum(np.linalg.eigvalsh(C), 0.0)
    p = ev / max(float(ev.sum()), 1e-12)
    eff = float(np.exp(-float(np.sum(np.where(p > 0, p * np.log(np.maximum(p, 1e-12)), 0.0)))))
    off = C[~np.eye(len(frames), dtype=bool)]
    return A.packet(
        SYSTEM, bundle, trials=len(frames),
        representations=[{
            "kind": "sensor_breadth", "system": SYSTEM, "n_sensors": len(frames),
            "symbols": [f.symbol for f in frames], "bars_used": int(n),
            "effective_rank": eff, "independence": round(eff / len(frames), 4),
            "mean_abs_offdiagonal": float(np.mean(np.abs(off))),
            "max_abs_offdiagonal": float(np.max(np.abs(off))),
            "universe_declared": len(bundle.universe),
            "representation": ("how many INDEPENDENT sensors this bundle really carries: the "
                               "effective rank of the return correlation matrix")}],
        note=f"effective rank {eff:.2f} of {len(frames)} sensors")


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
