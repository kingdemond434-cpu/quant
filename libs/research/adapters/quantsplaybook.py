"""QuantsPlaybook adapter (REBUILT, numpy only) -- the Chinese broker research-reproduction corpus
answered the only way this desk can honour it: by REPRODUCING one of its standard constructions
on the desk's own bars. The construction is the ATR-filtered Donchian channel break (a staple of
the 期货 research notes): an N-bar high taken only when the break exceeds a multiple of the
average true range. Its forward association is measured and donated; the reproduction's
parameters travel with it."""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "quantsplaybook"
CAPABILITY_FAMILY = "research_reproduction"
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


LOOKBACKS: tuple[int, ...] = (20, 55)
ATR_MULTS: tuple[float, ...] = (0.0, 0.5, 1.0)


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    import numpy as np
    frames = [f for f in bundle.frames("H1") if len(f) > 200]
    if not frames:
        return A.unmeasured(SYSTEM, bundle, "no H1 frame carries more than 200 bars")
    reps: list[dict[str, Any]] = []
    cands: list[dict[str, Any]] = []
    trials = 0
    for f in frames:
        h = np.asarray(f.high, dtype=float)
        lo = np.asarray(f.low, dtype=float)
        c = np.asarray(f.close, dtype=float)
        tr = np.full(c.shape[0], np.nan)
        tr[1:] = np.maximum.reduce([h[1:] - lo[1:], np.abs(h[1:] - c[:-1]),
                                    np.abs(lo[1:] - c[:-1])])
        atr = A.realised_vol(np.nan_to_num(tr[1:], nan=0.0), 14)
        fwd = _fwd(f)
        for n in LOOKBACKS:
            roll_max = np.full(c.shape[0], np.nan)
            for i in range(n, c.shape[0]):
                roll_max[i] = h[i - n:i].max()
            for mult in ATR_MULTS:
                trials += 1
                pad = np.concatenate([[np.nan], atr])[:c.shape[0]]
                excess = c - (roll_max + mult * np.nan_to_num(pad, nan=0.0))
                sig = np.where(np.isfinite(excess), excess, np.nan)
                ic = _ic(sig, fwd)
                n_breaks = int(np.nansum(sig > 0))
                reps.append({"kind": "reproduced_construction", "symbol": f.symbol,
                             "construction": "ATR-filtered Donchian channel break",
                             "lookback": n, "atr_mult": mult, "n_breaks": n_breaks,
                             "ic_rank": None if np.isnan(ic) else ic})
                if np.isnan(ic) or n_breaks == 0:
                    continue
                cands.append(A.candidate(
                    "level_breakout" if ic > 0 else "failed_breakout", [f.symbol],
                    f"{f.symbol} H1: the {n}-bar Donchian break filtered at {mult} ATR fires "
                    f"{n_breaks} times and scores a rank IC of {ic:+.4f} against the next bar "
                    f"-- a {'breakout' if ic > 0 else 'failed-breakout'} reproduction",
                    horizon=bundle.horizons[0], source=SYSTEM,
                    evidence={"lookback": n, "atr_mult": mult, "n_breaks": n_breaks,
                              "ic_rank": ic, "method": "reproduced broker-research "
                                                       "construction, numpy only"}))
    return A.packet(SYSTEM, bundle, trials=trials, representations=reps, candidates=cands,
                    note=f"{trials} (lookback, ATR filter) reproductions")


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
