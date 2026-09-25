"""Optiver/IMC/HRT-style adapter (REBUILT, numpy only) -- the published capability is PROBABILISTIC
ORDER-FLOW reasoning. This bundle carries bars, not books, so the adapter measures the only flow
proxy bars can honestly carry: signed volume (the bar's tick volume times the sign of its
return), its own persistence, and its association with the next bar's return. A proxy named as a
proxy is a measurement; a proxy called a book is not."""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "inst_optiver_imc_hrt"
CAPABILITY_FAMILY = "institutional_capability"
LICENCE_EXPECTED = "N/A (public architecture)"
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
        r = f.log_returns()
        v = np.asarray(f.volume, dtype=float)[1:]
        if v.shape[0] != r.shape[0] or r.shape[0] < 120:
            continue
        signed = np.sign(r) * v
        norm = signed / np.maximum(A.realised_vol(np.abs(signed), 24), 1e-12)
        fwd = np.concatenate([r[1:], [np.nan]])
        trials += 2
        persistence = float(np.corrcoef(signed[:-1], signed[1:])[0, 1]) \
            if float(np.std(signed)) > 0 else float("nan")
        ic = _ic(norm, fwd)
        reps.append({"kind": "order_flow_proxy", "symbol": f.symbol,
                     "proxy": "sign(return) * tick volume, normalised by its trailing scale",
                     "persistence_lag1": None if np.isnan(persistence) else persistence,
                     "ic_rank": None if np.isnan(ic) else ic, "n": int(r.shape[0]),
                     "representation": ("a bar-level flow proxy named as a proxy: the book is "
                                        "not in this bundle and is not pretended into it")})
        if np.isnan(ic):
            continue
        cands.append(A.candidate(
            "volume_spike" if ic > 0 else "range_reversion", [f.symbol],
            f"{f.symbol} H1: normalised signed volume scores a rank IC of {ic:+.4f} against the "
            f"next bar with lag-1 persistence {persistence:+.3f} over {r.shape[0]} bars",
            horizon=bundle.horizons[0], source=SYSTEM,
            evidence={"ic_rank": ic, "persistence_lag1": None if np.isnan(persistence)
                      else persistence, "n": int(r.shape[0]),
                      "method": "signed-volume flow proxy from bars, numpy only"}))
    if not reps:
        return A.unmeasured(SYSTEM, bundle, "no frame carried usable volume")
    return A.packet(SYSTEM, bundle, trials=trials, representations=reps, candidates=cands,
                    note=f"{len(reps)} flow proxies measured")


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
