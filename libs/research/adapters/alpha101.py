"""Alpha101 adapter (REBUILT, numpy only) -- six of the published formulaic alphas (Kakushadze
2015) evaluated as PARENT GENOMES on this bundle's own bars. Each (alpha, frame) is one charged
trial; the measurement is the rank information coefficient against the next bar's return, and
the SIGN of that IC chooses the family the hypothesis is donated under. Nothing here ranks,
sizes or approves -- the ten gates do."""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "alpha101"
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


def _d(x: Any, k: int) -> Any:
    """delta(x, k) with a NaN pad, so an index never borrows a value it could not know."""
    import numpy as np
    out = np.full(x.shape[0], np.nan)
    if x.shape[0] > k:
        out[k:] = x[k:] - x[:-k]
    return out


def _roll_mean(x: Any, w: int) -> Any:
    import numpy as np
    out = np.full(x.shape[0], np.nan)
    if x.shape[0] >= w:
        c = np.cumsum(np.insert(x, 0, 0.0))
        out[w - 1:] = (c[w:] - c[:-w]) / w
    return out


def _sdiv(a: Any, b: Any) -> Any:
    import numpy as np
    return a / np.where(np.abs(b) < 1e-12, np.nan, b)


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    import numpy as np
    frames = [f for f in bundle.frames("H1") if len(f) > 120]
    if not frames:
        return A.unmeasured(SYSTEM, bundle, "no H1 frame carries more than 120 bars")
    deadline = A.Deadline(bundle.compute_budget_s)
    reps: list[dict[str, Any]] = []
    cands: list[dict[str, Any]] = []
    trials = 0
    for f in frames:
        if deadline.expired():
            break
        o = np.asarray(f.open, dtype=float)
        h = np.asarray(f.high, dtype=float)
        lo = np.asarray(f.low, dtype=float)
        c = np.asarray(f.close, dtype=float)
        v = np.asarray(f.volume, dtype=float)
        fwd = _fwd(f)
        with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
            vwap = (h + lo + c) / 3.0
            alphas: dict[str, Any] = {
                "alpha012": np.sign(_d(v, 1)) * -_d(c, 1),
                "alpha023": np.where(_roll_mean(h, 20) < h, -_d(h, 2), 0.0),
                "alpha041": np.sqrt(np.maximum(h * lo, 0.0)) - vwap,
                "alpha053": -_d(_sdiv((c - lo) - (h - c), np.maximum(c - lo, 1e-9)), 9),
                "alpha054": -_sdiv((lo - c) * np.power(o, 5.0), (lo - h) * np.power(c, 5.0)),
                "alpha101": _sdiv(c - o, h - lo + 1e-3),
            }
        for name, sig in alphas.items():
            trials += 1
            ic = _ic(sig, fwd)
            row = {"kind": "formulaic_alpha", "alpha": name, "symbol": f.symbol,
                   "timeframe": f.timeframe, "ic_rank": None if np.isnan(ic) else ic,
                   "n_bars": len(f), "source": "Kakushadze (2015) 101 Formulaic Alphas, "
                                               "single-series variant on this bundle"}
            reps.append(row)
            if np.isnan(ic):
                continue
            cands.append(A.candidate(
                _family(ic), [f.symbol],
                f"{f.symbol} {f.timeframe}: published formulaic alpha {name} scores a rank IC of "
                f"{ic:+.4f} against the next bar's return over {len(f)} bars -- "
                f"{'momentum' if ic > 0 else 'mean reversion'} at that horizon",
                horizon=bundle.horizons[0], source=SYSTEM,
                evidence={"alpha": name, "ic_rank": ic, "n_bars": len(f),
                          "method": "rank IC of a published formulaic alpha, single series"}))
    return A.packet(SYSTEM, bundle, trials=trials, representations=reps, candidates=cands,
                    note=f"{len(reps)} (alpha, frame) evaluations")


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
