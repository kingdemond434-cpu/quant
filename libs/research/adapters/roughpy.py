"""RoughPy adapter -- path signatures of the multi-asset log-price path -> signature
representations.

The path is the log price of up to four bundle symbols; signatures to depth 3 are taken over
trailing windows (one charged trial per window). The desk receives levels one and two (the
increments and the Levy areas -- the lead/lag structure between assets) as a representation.
"""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "roughpy"
DEPTH, WINDOW, N_WINDOWS, MAX_SYMBOLS = 3, 48, 6, 4


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    rp = A.library("roughpy")
    if rp is None:
        return A.unmeasured(SYSTEM, bundle, "roughpy is not importable in this environment")
    import numpy as np
    frames = [f for f in bundle.frames("H1") if len(f) > WINDOW * (N_WINDOWS + 1)][:MAX_SYMBOLS]
    if len(frames) < 2:
        return A.unmeasured(SYSTEM, bundle, "fewer than two H1 frames long enough")
    n = min(len(f) for f in frames) - 1
    inc = np.column_stack([f.log_returns()[-n:] for f in frames])
    inc = inc / np.maximum(inc.std(axis=0, keepdims=True), 1e-12)
    d = inc.shape[1]
    deadline = A.Deadline(bundle.compute_budget_s)
    trials = 0
    reps: list[dict[str, Any]] = []
    try:
        ctx = rp.get_context(width=d, depth=DEPTH, coeffs=rp.DPReal)
        stream = rp.LieIncrementStream.from_increments(inc, indices=np.arange(n, dtype=float),
                                                       ctx=ctx)
    except Exception as exc:
        return A.packet(SYSTEM, bundle, trials=0, representations=[
            {"kind": "UNMEASURED", "why": f"{type(exc).__name__}: {exc}"[:200]}])
    for w in range(N_WINDOWS):
        if deadline.expired():
            break
        b = n - w * WINDOW
        a = b - WINDOW
        trials += 1
        try:
            sig = stream.signature(rp.RealInterval(float(a), float(b)), depth=DEPTH)
            coeffs = np.asarray(list(sig), dtype=float).reshape(-1)
        except Exception as exc:
            reps.append({"kind": "UNMEASURED", "window": [a, b],
                         "why": f"{type(exc).__name__}: {exc}"[:200]})
            continue
        lvl1 = coeffs[1:1 + d]
        lvl2 = coeffs[1 + d:1 + d + d * d].reshape(d, d) if coeffs.shape[0] >= 1 + d + d * d \
            else np.zeros((d, d))
        levy = 0.5 * (lvl2 - lvl2.T)
        reps.append({"kind": "path_signature", "timeframe": "H1", "depth": DEPTH,
                     "symbols": [f.symbol for f in frames],
                     "window": [frames[0].time[a + 1], frames[0].time[min(b, n)]],
                     "level1": lvl1, "levy_area": levy,
                     "representation": "level-2 antisymmetric part is the lead/lag (Levy area) "
                                       "between assets over the window; a state for the forge"})
    return A.packet(SYSTEM, bundle, trials=trials, representations=reps)


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
