"""D. E. Shaw-style adapter (REBUILT, numpy only) -- the published capability is the CROSS-STRATEGY
EXPOSURE VIEW: what three mechanisms add jointly rather than one at a time. The adapter builds
three independent rule streams on each frame (trend, breakout, reversion), measures their
pairwise correlation and the effective rank of the set, and reports what the combination's
overlap actually is. Capacity discipline starts with this number."""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "inst_deshaw"
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
        r = f.log_returns()
        if r.shape[0] < 150:
            continue
        c = np.asarray(f.close, dtype=float)[1:]
        ma_f = np.convolve(c, np.ones(10) / 10, mode="same")
        ma_s = np.convolve(c, np.ones(50) / 50, mode="same")
        vol = A.realised_vol(r, 24)
        streams = {
            "trend": np.sign(ma_f - ma_s),
            "breakout": np.sign(r - 1.5 * np.nan_to_num(vol, nan=0.0)),
            "reversion": -np.sign(np.concatenate([[0.0], r[:-1]])),
        }
        pnl = {k: np.nan_to_num(v[:-1] * r[1:], nan=0.0) for k, v in streams.items()}
        keys = list(pnl)
        M = np.column_stack([pnl[k] for k in keys])
        trials += len(keys)
        C = np.nan_to_num(np.corrcoef(M, rowvar=False), nan=0.0)
        ev = np.maximum(np.linalg.eigvalsh(C), 0.0)
        p = ev / max(float(ev.sum()), 1e-12)
        eff = float(np.exp(-float(np.sum(np.where(p > 0, p * np.log(np.maximum(p, 1e-12)),
                                                  0.0)))))
        rows.append({"symbol": f.symbol, "streams": keys,
                     "pairwise_corr": {f"{keys[i]}|{keys[j]}": float(C[i, j])
                                       for i in range(len(keys)) for j in range(i + 1, len(keys))},
                     "effective_rank": eff,
                     "independence": round(eff / len(keys), 4),
                     "stream_sum": {k: float(v.sum()) for k, v in pnl.items()}})
    if not rows:
        return A.unmeasured(SYSTEM, bundle, "no frame supported three rule streams")
    return A.packet(
        SYSTEM, bundle, trials=trials,
        representations=[{
            "kind": "cross_strategy_exposure", "system": SYSTEM, "frames": rows,
            "mean_independence": float(np.mean([r["independence"] for r in rows])),
            "representation": ("how much of three mechanisms is actually one mechanism, per "
                               "instrument: the effective rank of their return streams")}],
        note=f"{len(rows)} exposure views")


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
