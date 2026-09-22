"""TensorLy adapter -- CP decomposition of asset x feature x time -> latent representations.

The tensor holds, for every bundle symbol, four bar features (return, realised vol, range over
close, log-volume z-score) over the last 200 H1 bars. Each CP rank is one charged trial; the
desk receives asset loadings, feature loadings, the tail of the time factors and the relative
reconstruction error -- latent structure for the forge.
"""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "tensorly"
RANKS: tuple[int, ...] = (2, 3)
T, WINDOW = 200, 24
FEATURES = ("return", "realised_vol", "range_over_close", "log_volume_z")


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    tl = A.library("tensorly")
    dec = A.library("tensorly.decomposition")
    if tl is None or dec is None:
        return A.unmeasured(SYSTEM, bundle, "tensorly is not importable in this environment")
    import numpy as np
    frames = [f for f in bundle.frames("H1") if len(f) > T + WINDOW + 1]
    if len(frames) < 2:
        return A.unmeasured(SYSTEM, bundle, f"fewer than two H1 frames with {T + WINDOW}+ bars")
    slabs = []
    for f in frames:
        r = f.log_returns()
        vol = A.realised_vol(r, WINDOW)
        c = np.asarray(f.close, float)[1:]
        rng = (np.asarray(f.high, float)[1:] - np.asarray(f.low, float)[1:]) / np.maximum(c,
                                                                                         1e-12)
        lv = np.log(np.maximum(np.asarray(f.volume, float)[1:], 1.0))
        lvz = (lv - lv.mean()) / max(float(lv.std()), 1e-12)
        slab = np.vstack([r, vol, rng, lvz])[:, -T:]
        slab = (slab - np.nanmean(slab, axis=1, keepdims=True)) / np.maximum(
            np.nanstd(slab, axis=1, keepdims=True), 1e-12)
        slabs.append(np.nan_to_num(slab))
    tensor = np.stack(slabs)
    deadline = A.Deadline(bundle.compute_budget_s)
    trials = 0
    reps: list[dict[str, Any]] = []
    for rank in RANKS:
        if deadline.expired():
            break
        trials += 1
        try:
            weights, factors = dec.parafac(tl.tensor(tensor), rank=rank, init="random",
                                           random_state=bundle.seed, n_iter_max=200)
            recon = tl.cp_to_tensor((weights, factors))
            err = float(tl.norm(tl.tensor(tensor) - recon) / tl.norm(tl.tensor(tensor)))
            fa = [np.asarray(tl.to_numpy(x)) for x in factors]
        except Exception as exc:
            reps.append({"kind": "UNMEASURED", "rank": rank,
                         "why": f"{type(exc).__name__}: {exc}"[:200]})
            continue
        reps.append({"kind": "cp_latent_factors", "rank": rank, "shape": list(tensor.shape),
                     "symbols": [f.symbol for f in frames], "features": list(FEATURES),
                     "asset_loadings": {f.symbol: fa[0][i, :] for i, f in enumerate(frames)},
                     "feature_loadings": {feat: fa[1][i, :] for i, feat in enumerate(FEATURES)},
                     "time_factor_tail": fa[2][-12:, :].T,
                     "relative_reconstruction_error": err,
                     "representation": "shared latent structure across assets and bar "
                                       "features; a time factor is a state series candidate"})
    return A.packet(SYSTEM, bundle, trials=trials, representations=reps)


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
