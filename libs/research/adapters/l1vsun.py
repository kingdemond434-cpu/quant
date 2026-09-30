"""l1vsun adapter (REBUILT, numpy only) -- forced-flow and funding mechanics rebuilt on the only
forced flow this bundle can see: the SESSION GAP. Every bar whose open leaves the previous close
is a flow that had to happen somewhere else; the adapter measures the gap distribution, the
association between a gap and the bar that follows it, and donates an overnight_drift hypothesis
per symbol with the measured sign."""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "l1vsun"
CAPABILITY_FAMILY = "information_acquisition"
LICENCE_EXPECTED = "N/A (method only)"
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
    frames = [f for f in bundle.frames("H1") if len(f) > 120]
    if not frames:
        return A.unmeasured(SYSTEM, bundle, "no H1 frame carries more than 120 bars")
    reps: list[dict[str, Any]] = []
    cands: list[dict[str, Any]] = []
    trials = 0
    for f in frames:
        trials += 1
        o = np.asarray(f.open, dtype=float)
        c = np.asarray(f.close, dtype=float)
        gap = np.full(o.shape[0], np.nan)
        gap[1:] = np.log(np.maximum(o[1:], 1e-12)) - np.log(np.maximum(c[:-1], 1e-12))
        fwd = _fwd(f)
        big = np.abs(gap) > np.nanpercentile(np.abs(gap), 80) if np.isfinite(gap).any() else None
        ic = _ic(gap, fwd)
        ic_big = _ic(np.where(big, gap, np.nan), fwd) if big is not None else float("nan")
        reps.append({"kind": "forced_flow_gap", "symbol": f.symbol,
                     "n_gaps": int(np.isfinite(gap).sum()),
                     "gap_abs_median": float(np.nanmedian(np.abs(gap)))
                     if np.isfinite(gap).any() else None,
                     "ic_all": None if np.isnan(ic) else ic,
                     "ic_largest_quintile": None if np.isnan(ic_big) else ic_big,
                     "representation": "the gap a forced flow leaves, and what follows it"})
        if np.isnan(ic):
            continue
        cands.append(A.candidate(
            "overnight_drift", [f.symbol],
            f"{f.symbol} H1: the open-to-previous-close gap scores a rank IC of {ic:+.4f} "
            f"against the bar that follows it ({ic_big:+.4f} in the largest quintile) -- the "
            f"{'continuation' if ic > 0 else 'decay'} of a forced flow",
            horizon=bundle.horizons[0], source=SYSTEM,
            evidence={"ic_all": ic, "ic_largest_quintile": None if np.isnan(ic_big) else ic_big,
                      "n_gaps": int(np.isfinite(gap).sum()),
                      "method": "session-gap association with the following bar"}))
    return A.packet(SYSTEM, bundle, trials=trials, representations=reps, candidates=cands,
                    note=f"{len(reps)} frames measured for forced-flow gaps")


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
