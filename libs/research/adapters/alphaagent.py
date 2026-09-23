"""AlphaAgent adapter (REBUILT, numpy only) -- the anti-decay claim rebuilt as a STRUCTURAL NOVELTY
measurement: a factor's worth is not its IC alone but how much of it is already carried by the
factors beside it. The adapter builds a small factor panel, measures the pairwise absolute rank
correlation, reports the panel's effective rank, and donates the MOST ORTHOGONAL factor -- the
one whose information nothing else in the panel holds."""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "alphaagent"
CAPABILITY_FAMILY = "structural_novelty"
LICENCE_EXPECTED = "N/A (published method)"
RUNS_WITHOUT_LIBRARY = True


def _rank(v: Any) -> Any:
    """Ranks in [0, 1] -- the transform every formulaic-alpha family is written in."""
    import numpy as np
    x = np.asarray(v, dtype=float)
    return np.argsort(np.argsort(x)).astype(float) / max(x.shape[0] - 1, 1)


def _ic(a: Any, b: Any) -> float:
    """Rank correlation of two aligned series, non-finite rows dropped. A MEASUREMENT of
    association, never a verdict: the sign picks the family and the gauntlet judges it."""
    import numpy as np
    x, y = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    m = np.isfinite(x) & np.isfinite(y)
    if int(m.sum()) < 30 or float(np.std(x[m])) <= 0.0 or float(np.std(y[m])) <= 0.0:
        return float("nan")
    return float(np.corrcoef(_rank(x[m]), _rank(y[m]))[0, 1])


def _fwd(frame: A.BarFrame) -> Any:
    """Next-bar log return, aligned to the bar the signal is known at (NaN in the last slot)."""
    import numpy as np
    return np.concatenate([frame.log_returns(), [np.nan]])


def _family(ic: float) -> str:
    """The SIGN chooses: a positive association is momentum, a negative one reversion. Never a
    strength threshold -- a weak association is donated exactly like a strong one."""
    return "trend_ma_cross" if ic > 0 else "mean_reversion_rsi"


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    import numpy as np
    frames = [f for f in bundle.frames("H1") if len(f) > 200]
    if not frames:
        return A.unmeasured(SYSTEM, bundle, "no H1 frame carries more than 200 bars")
    reps: list[dict[str, Any]] = []
    cands: list[dict[str, Any]] = []
    trials = 0
    for f in frames:
        X, y, _ = A.lagged_design(f)
        if X.shape[0] < 60:
            continue
        names = [*A.LAGGED_FEATURE_NAMES, "r1_x_vol", "r1_minus_r2"]
        panel = np.column_stack([X, X[:, 0] * X[:, 3], X[:, 0] - X[:, 1]])
        ranks = np.column_stack([_rank(panel[:, i]) for i in range(panel.shape[1])])
        corr = np.corrcoef(ranks, rowvar=False)
        corr = np.nan_to_num(corr, nan=0.0)
        off = np.abs(corr) - np.eye(corr.shape[0])
        novelty = 1.0 - off.max(axis=1)
        ev = np.maximum(np.linalg.eigvalsh(corr), 0.0)
        p = ev / max(float(ev.sum()), 1e-12)
        eff_rank = float(np.exp(-float(np.sum(np.where(p > 0, p * np.log(np.maximum(p, 1e-12)),
                                                       0.0)))))
        rows: list[dict[str, Any]] = []
        for i, nm in enumerate(names):
            trials += 1
            ic = _ic(panel[:, i], y)
            rows.append({"factor": nm, "novelty": float(novelty[i]),
                         "max_abs_corr_with_others": float(off[i].max()),
                         "ic_rank": None if np.isnan(ic) else ic})
        reps.append({"kind": "structural_novelty", "symbol": f.symbol, "factors": rows,
                     "effective_rank": eff_rank, "n_factors": len(names),
                     "representation": ("how much of each factor the panel already carries; "
                                        "novelty is 1 - its largest absolute correlation")})
        measured = [r for r in rows if r["ic_rank"] is not None]
        if not measured:
            continue
        best = max(measured, key=lambda r: float(str(r["novelty"])))
        ic = float(str(best["ic_rank"]))
        cands.append(A.candidate(
            _family(ic), [f.symbol],
            f"{f.symbol} H1: factor {best['factor']} is the most structurally novel of the "
            f"panel (novelty {best['novelty']:.3f}, largest correlation with any sibling "
            f"{best['max_abs_corr_with_others']:.3f}) and scores a rank IC of {ic:+.4f}",
            horizon=bundle.horizons[0], source=SYSTEM,
            evidence={"factor": best["factor"], "novelty": best["novelty"], "ic_rank": ic,
                      "effective_rank": eff_rank,
                      "method": "panel rank-correlation novelty, numpy only"}))
    if not reps:
        return A.unmeasured(SYSTEM, bundle, "no frame produced a usable factor panel")
    return A.packet(SYSTEM, bundle, trials=trials, representations=reps, candidates=cands,
                    note=f"{len(reps)} factor panels measured")


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
