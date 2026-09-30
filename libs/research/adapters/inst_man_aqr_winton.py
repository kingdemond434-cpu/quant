"""Man/AQR/Winton-style adapter (REBUILT, numpy only) -- the published research these houses
actually publish: TIME-SERIES MOMENTUM and its volatility-scaled form. The adapter measures both
on this bundle's frames -- the trailing k-bar return, and the same return divided by trailing
realised vol -- against the next bar, and donates each with its measured sign. The construction
is public; the measurement is this desk's own."""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "inst_man_aqr_winton"
CAPABILITY_FAMILY = "institutional_capability"
LICENCE_EXPECTED = "N/A (published research)"
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


LOOKBACKS: tuple[int, ...] = (12, 24, 96)


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
        fwd = np.concatenate([r[1:], [np.nan]])
        vol = A.realised_vol(r, 48)
        for k in LOOKBACKS:
            cum = np.full(r.shape[0], np.nan)
            if r.shape[0] > k:
                cs = np.cumsum(np.insert(r, 0, 0.0))
                cum[k:] = cs[k + 1:] - cs[1:-k] if cs.shape[0] > k + 1 else np.nan
            for name, sig in (("tsmom", cum), ("tsmom_volscaled",
                                               cum / np.maximum(vol, 1e-12))):
                trials += 1
                ic = _ic(sig, fwd)
                reps.append({"kind": "published_factor", "symbol": f.symbol, "factor": name,
                             "lookback_bars": k, "ic_rank": None if np.isnan(ic) else ic})
                if np.isnan(ic):
                    continue
                cands.append(A.candidate(
                    _family(ic), [f.symbol],
                    f"{f.symbol} H1: the published {name} factor over {k} bars scores a rank IC "
                    f"of {ic:+.4f} against the next bar -- "
                    f"{'continuation' if ic > 0 else 'reversal'} at that lookback",
                    horizon=bundle.horizons[0], source=SYSTEM,
                    evidence={"factor": name, "lookback_bars": k, "ic_rank": ic,
                              "method": "published time-series momentum, vol-scaled variant"}))
    return A.packet(SYSTEM, bundle, trials=trials, representations=reps, candidates=cands,
                    note=f"{trials} published-factor cells")


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
