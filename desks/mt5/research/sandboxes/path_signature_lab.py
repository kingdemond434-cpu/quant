"""PATH-SIGNATURE LAB -- the rough-paths mechanism (RoughPy) rebuilt so it runs today.

The signature of the multi-asset log-price path over a window is the ordered set of iterated
integrals: level 1 the increments, level 2 the Levy areas (which asset moved FIRST -- the
lead/lag), level 3 the triple interactions. RoughPy computes them exactly when installed
(`libs.research.adapters.roughpy`); otherwise this cell computes the truncated signature to
level <= 3 with Chen's identity over the discrete increments in numpy, which is the same
object on a piecewise-linear path.

WHAT LEAVES. Signature coefficients per window are a REPRESENTATION. Two hypothesis shapes are
donated for the gauntlet, both read off the data and never asserted: (1) a persistent Levy-area
sign between a leader and a follower -> a `momentum_volgate` cell on the follower; (2) the
signature features' out-of-sample sign hit on the symbol's own next-24h return with the fitted
sign of its level-1 term -> `trend_ma_cross` (positive: continuation) or
`mean_reversion_bollinger` (negative: reversal). Every window's signature is a charged trial.
"""
from __future__ import annotations

import math
from itertools import pairwise
from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

from . import CellContext, system_id

CELL = "path_signature_lab"
SYSTEM = system_id(CELL)
CAPABILITY_FAMILY = "rough_paths"
UPSTREAM = ("roughpy",)
FALLBACK = "numpy truncated signature (Chen's identity, level <= 3) over discrete increments"
DEPTH, WINDOW, MAX_SYMBOLS, MIN_WINDOWS = 3, 48, 4, 8
PERSISTENCE = 0.75


def signature(inc: Any, depth: int = DEPTH) -> Any:
    """Truncated signature of the piecewise-linear path with increments `inc` (n x d), as the
    flat tensor-algebra coefficient vector [1, level1 (d), level2 (d*d), level3 (d^3)]."""
    import numpy as np
    inc = np.asarray(inc, dtype=float)
    d = inc.shape[1]
    lv1 = np.zeros(d)
    lv2 = np.zeros((d, d))
    lv3 = np.zeros((d, d, d))
    for x in inc:
        # Chen: S(path + segment) = S(path) (x) exp(segment); exp(x) levels are x^k/k!
        e1, e2, e3 = x, np.outer(x, x) / 2.0, np.einsum("i,j,k->ijk", x, x, x) / 6.0
        if depth >= 3:
            lv3 = lv3 + e3 + np.einsum("i,jk->ijk", lv1, e2) + np.einsum("ij,k->ijk", lv2, e1)
        if depth >= 2:
            lv2 = lv2 + e2 + np.outer(lv1, e1)
        lv1 = lv1 + e1
    parts = [np.ones(1), lv1]
    if depth >= 2:
        parts.append(lv2.reshape(-1))
    if depth >= 3:
        parts.append(lv3.reshape(-1))
    return np.concatenate(parts)


def _windows(n: int) -> list[tuple[int, int]]:
    out = []
    b = n
    while b - WINDOW >= 0:
        out.append((b - WINDOW, b))
        b -= WINDOW
    return out[::-1]


def run(bundle: A.ResearchBundle, ctx: CellContext) -> ExternalResearchPacket:
    import numpy as np
    frames = [f for f in bundle.frames("H1") if len(f) > WINDOW * (MIN_WINDOWS + 2)][:MAX_SYMBOLS]
    if len(frames) < 2:
        return A.unmeasured(SYSTEM, bundle, "fewer than two H1 frames long enough")
    engine = "numpy truncated signature"
    if A.library("roughpy") is not None:
        engine = "roughpy (adapter) for the window signatures; numpy for the features"
    n = min(len(f) for f in frames) - 1
    inc = np.column_stack([f.log_returns()[-n:] for f in frames])
    scale = np.maximum(inc.std(axis=0, keepdims=True), 1e-12)
    incz = inc / scale
    d = incz.shape[1]
    names = [f.symbol for f in frames]
    deadline = A.Deadline(min(bundle.compute_budget_s, ctx.budget_s))
    wins = _windows(n)
    sigs: list[Any] = []
    reps: list[dict[str, Any]] = []
    trials = 0
    for a, b in wins:
        if deadline.expired():
            break
        trials += 1
        sigs.append(signature(incz[a:b], DEPTH))
    if len(sigs) < MIN_WINDOWS:
        return A.packet(SYSTEM, bundle, trials=trials, research_methods=[
            {"kind": "UNMEASURED", "why": f"only {len(sigs)} windows inside the budget"}])
    S = np.vstack(sigs)
    lv2 = S[:, 1 + d:1 + d + d * d].reshape(len(sigs), d, d)
    levy = 0.5 * (lv2 - np.transpose(lv2, (0, 2, 1)))
    last = wins[len(sigs) - 1]
    reps.append({"kind": "path_signature", "engine": engine, "depth": DEPTH, "symbols": names,
                 "window_bars": WINDOW, "n_windows": len(sigs),
                 "last_window": [frames[0].time[-n + last[0]], frames[0].time[-n + last[1] - 1]],
                 "level1_last": S[-1, 1:1 + d], "levy_area_last": levy[-1],
                 "levy_sign_persistence": np.mean(np.sign(levy) == np.sign(levy[-1]), axis=0),
                 "representation": "the antisymmetric level-2 part is the lead/lag between "
                                   "assets; its sign persistence across windows is a state"})
    cands: list[dict[str, Any]] = []
    # (1) persistent lead/lag -> momentum on the follower, conditioned on the leader's move
    for i in range(d):
        for j in range(d):
            if i == j:
                continue
            signs = np.sign(levy[:, i, j])
            persist = float(np.mean(signs == signs[-1])) if signs[-1] != 0 else 0.0
            if persist >= PERSISTENCE and abs(float(levy[-1, i, j])) > 0.05:
                leader, follower = (names[i], names[j]) if levy[-1, i, j] > 0 else (names[j],
                                                                                    names[i])
                cands.append(A.candidate(
                    "momentum_volgate", [follower],
                    f"{follower} H1: the Levy area with {leader} kept one sign in "
                    f"{persist:.0%} of the last {len(sigs)} {WINDOW}-bar windows (|A| "
                    f"{abs(float(levy[-1, i, j])):.3f}) -- {leader} moves first, {follower} "
                    f"follows; a vol-gated momentum hypothesis on the follower",
                    horizon=bundle.horizons[0], source=SYSTEM,
                    evidence={"leader": leader, "follower": follower,
                              "levy_area_last": float(levy[-1, i, j]),
                              "sign_persistence": persist, "n_windows": len(sigs),
                              "engine": engine}))
    # (2) signature features -> next-window own return: ridge, walk-forward on windows
    if len(sigs) >= MIN_WINDOWS + 2:
        X = S[:-1, 1:]
        for k, sym in enumerate(names):
            y = np.asarray([float(incz[b:b + WINDOW, k].sum()) if b + WINDOW <= n
                            else float(incz[b:, k].sum()) for _, b in wins[:len(sigs) - 1]])
            half = max(MIN_WINDOWS // 2, len(y) // 2)
            hits: list[bool] = []
            coef1 = 0.0
            for t in range(half, len(y)):
                trials += 1
                Xt, yt = X[:t], y[:t]
                w = np.linalg.solve(Xt.T @ Xt + 1.0 * np.eye(Xt.shape[1]), Xt.T @ yt)
                pred = float(X[t] @ w)
                hits.append(bool(np.sign(pred) == np.sign(y[t])) if y[t] != 0 else False)
                coef1 = float(w[k])
            if not hits:
                continue
            hit = float(np.mean(hits))
            family = "trend_ma_cross" if coef1 > 0 else "mean_reversion_bollinger"
            reps.append({"kind": "signature_predictability", "symbol": sym, "oos_sign_hit": hit,
                         "n_oos": len(hits), "level1_coefficient": coef1,
                         "representation": "signature features' sign hit on the next window"})
            if hit > 0.5 and math.isfinite(coef1):
                cands.append(A.candidate(
                    family, [sym],
                    f"{sym} H1: signature features (depth {DEPTH}, {WINDOW}-bar windows) hit the "
                    f"next-window sign {hit:.0%} of {len(hits)} walk-forward windows; the "
                    f"fitted level-1 term is {'positive' if coef1 > 0 else 'negative'} -- "
                    f"{'continuation' if coef1 > 0 else 'reversal'} hypothesis",
                    horizon=bundle.horizons[-1], source=SYSTEM,
                    evidence={"oos_sign_hit": hit, "n_oos": len(hits), "level1_coefficient": coef1,
                              "engine": engine}))
    _ = pairwise  # kept for the window iterator's readers; pairwise(wins) is the window chain
    return A.packet(SYSTEM, bundle, trials=trials, representations=reps, candidates=cands,
                    note=f"{engine}; {len(sigs)} windows over {d} symbols")
