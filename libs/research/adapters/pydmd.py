"""PyDMD adapter -- dynamic mode decomposition of the cross-section -> Koopman-mode
representations.

The snapshot matrix is the standardised H1 return of every bundle symbol (symbols x time); each
SVD rank is one charged trial. The desk receives the eigenvalue moduli (growth/decay), implied
periods in bars and per-symbol mode loadings -- a representation of shared dynamics, offered to
the representation forge, never a forecast.
"""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "pydmd"
RANKS: tuple[int, ...] = (2, 4)


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    pydmd = A.library("pydmd")
    if pydmd is None:
        return A.unmeasured(SYSTEM, bundle, "pydmd is not importable in this environment")
    import numpy as np
    frames = [f for f in bundle.frames("H1") if len(f) > 200]
    if len(frames) < 2:
        return A.unmeasured(SYSTEM, bundle, "fewer than two H1 frames with 200+ bars")
    n = min(len(f) for f in frames) - 1
    R = np.vstack([f.log_returns()[-n:] for f in frames])
    R = (R - R.mean(axis=1, keepdims=True)) / np.maximum(R.std(axis=1, keepdims=True), 1e-12)
    deadline = A.Deadline(bundle.compute_budget_s)
    trials = 0
    reps: list[dict[str, Any]] = []
    for rank in RANKS:
        if deadline.expired() or rank > len(frames):
            break
        trials += 1
        try:
            dmd = pydmd.DMD(svd_rank=rank)
            dmd.fit(R)
            eigs = np.asarray(dmd.eigs)
            modes = np.asarray(dmd.modes)
            amps = np.asarray(dmd.amplitudes)
        except Exception as exc:
            reps.append({"kind": "UNMEASURED", "rank": rank,
                         "why": f"{type(exc).__name__}: {exc}"[:200]})
            continue
        angle = np.abs(np.angle(eigs))
        reps.append({"kind": "koopman_modes", "timeframe": "H1", "rank": rank,
                     "symbols": [f.symbol for f in frames], "n_snapshots": int(n),
                     "eig_modulus": np.abs(eigs), "eig_period_bars":
                     [float(2 * np.pi / a) if a > 1e-9 else None for a in angle],
                     "amplitude_abs": np.abs(amps),
                     "mode_loadings": {f.symbol: np.abs(modes[i, :]) for i, f in
                                       enumerate(frames)},
                     "representation": "shared cross-sectional dynamics; a mode with modulus "
                                       "near 1 and a period of hours is a candidate state"})
    return A.packet(SYSTEM, bundle, trials=trials, representations=reps)


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
