"""WQ research-engine adapter (REBUILT, numpy only) -- the BRAIN submission idiom rebuilt as a
DECAY AND TURNOVER profile: an expression is not judged by one horizon's IC but by how its IC
decays across horizons and how much position churn it implies. Each (expression, horizon) is a
charged trial; the profile is a representation and the best horizon is donated as a hypothesis."""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "wq_research_engine"
CAPABILITY_FAMILY = "dsl_program_search"
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


HORIZONS_BARS: tuple[int, ...] = (1, 4, 24)


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    import numpy as np
    frames = [f for f in bundle.frames("H1") if len(f) > 300]
    if not frames:
        return A.unmeasured(SYSTEM, bundle, "no H1 frame carries more than 300 bars")
    deadline = A.Deadline(bundle.compute_budget_s)
    names = A.LAGGED_FEATURE_NAMES
    reps: list[dict[str, Any]] = []
    cands: list[dict[str, Any]] = []
    trials = 0
    for f in frames:
        if deadline.expired():
            break
        profile: list[dict[str, Any]] = []
        for k, col in enumerate(names):
            for hb in HORIZONS_BARS:
                trials += 1
                X, y, _ = A.lagged_design(f, target_bars=hb)
                if X.shape[0] < 60:
                    continue
                sig = X[:, k]
                pos = np.sign(sig)
                turnover = float(np.mean(np.abs(np.diff(pos)))) if pos.shape[0] > 1 else None
                ic = _ic(sig, y)
                profile.append({"expression": col, "horizon_bars": hb,
                                "ic_rank": None if np.isnan(ic) else ic, "turnover": turnover,
                                "n": int(X.shape[0])})
        measured = [r for r in profile if r["ic_rank"] is not None]
        if not measured:
            continue
        reps.append({"kind": "ic_decay_profile", "symbol": f.symbol, "profile": profile,
                     "representation": ("IC by horizon with the position churn each horizon "
                                        "implies -- the submission idiom's own two axes")})
        best = max(measured, key=lambda r: abs(float(r["ic_rank"])))
        ic = float(best["ic_rank"])
        cands.append(A.candidate(
            _family(ic), [f.symbol],
            f"{f.symbol} H1: expression {best['expression']} holds its largest rank IC "
            f"({ic:+.4f}) at {best['horizon_bars']} bars with turnover {best['turnover']} -- "
            f"the horizon its information actually lives at",
            horizon=bundle.horizons[-1], source=SYSTEM,
            evidence={"expression": best["expression"], "horizon_bars": best["horizon_bars"],
                      "ic_rank": ic, "turnover": best["turnover"],
                      "method": "IC decay and turnover profile across horizons"}))
    if not reps:
        return A.unmeasured(SYSTEM, bundle, "no frame produced a measurable decay profile")
    return A.packet(SYSTEM, bundle, trials=trials, representations=reps, candidates=cands,
                    note=f"{trials} (expression, horizon) evaluations")


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
