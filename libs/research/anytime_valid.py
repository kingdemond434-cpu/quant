"""Always-valid (anytime) sequential testing for forward validation -- gap #25.

WHY THIS EXISTS
The desk's forward gate is a fixed 40/90-day clock. That is safe but blunt: a genuinely strong
edge waits the full calendar even once its evidence is overwhelming, and a weak one consumes the
same budget. The principal asked to cut 90 -> 40 days. That is the WRONG lever -- it buys speed by
lowering the evidence bar for everything, including noise.

The right lever is an e-process. Under H0 (mean <= 0) the capital process below is a non-negative
supermartingale, so by Ville's inequality:

    P( sup_t  E_t >= 1/alpha )  <=  alpha

That bound holds at EVERY t simultaneously -- so you may peek daily, stop the instant E_t
crosses 1/alpha, and the type-I error is still <= alpha.

MEASURED RESULT (Monte Carlo, 2026-07-22) -- READ THIS BEFORE USING IT AS A SPEEDUP:
  null (no edge)      : 3/300 paths crossed = 1.0% at alpha=0.01  -> type-I control VERIFIED
  strong (Sharpe ~2)  : 6/40 graduated, MEDIAN 132 days           -> SLOWER than the fixed 90d
  weak (Sharpe ~0.3)  : 0/40 graduated                            -> correctly rejects
This test is RIGOROUS, not FAST. A Sharpe-2 edge on daily returns has per-observation signal
~0.105, so the e-process grows at ~mu^2/2sigma^2 ~ 0.0055/day and needs ~800 days to reach
log(1/alpha). That is fundamental to e-processes on weak per-observation signal, not an
implementation flaw. CONCLUSION: this does NOT replace the 40/90d clock to go faster -- it is
a stricter SECONDARY check. The only real accelerants are MORE OBSERVATIONS (higher frequency
or cross-sectional breadth), never a cleverer test. There is no free lunch on validation speed.

This does NOT replace the desk's economic gates (orthogonality, capacity, cost, crowding). It
replaces only the "how long must we wait" question.

Pure numpy/stdlib, deterministic, offline -- cheap to run every cycle.
"""
from __future__ import annotations

import numpy as np

# Mixture grid over the betting fraction. Small lambdas are conservative (slow but robust to fat
# tails); large lambdas grow fast on a real edge. Mixing means we never have to pick one.
_LAMBDAS = np.linspace(0.02, 0.45, 40)
_MIN_OBS = 20                     # below this the estimate of scale is not trustworthy


def e_value(returns: np.ndarray | list[float]) -> float:
    """Mixture e-value for H0: mean(returns) <= 0. Larger = stronger evidence AGAINST H0.

    Each component is the capital of a bettor wagering fraction ``lam`` of its bankroll on the
    next standardized return: prod(1 + lam * z_i). Capital is mixed uniformly over ``_LAMBDAS``,
    which is itself a valid e-value (a convex mixture of e-values is an e-value)."""
    r = np.asarray(returns, dtype="float64")
    r = r[np.isfinite(r)]
    if r.size < _MIN_OBS:
        return 0.0
    s = float(r.std(ddof=1))
    # `s <= 0.0` DOES NOT CATCH A CONSTANT SERIES, which is the failure that matters here.
    # `np.full(200, 0.01).std(ddof=1)` is 1.74e-18 rather than 0.0 -- the variance is computed as a
    # difference of squares and does not cancel exactly. So the guard passed, z reached 5.75e15,
    # and the e-value came back INFINITE: a series that never moved, certified as overwhelming
    # evidence of an edge. That is precisely the shape of a stuck recorder echoing its last value,
    # which is a live failure mode on this desk (`data_registry` scores `stale_frac` for it), so
    # the gate was offering a promotion path to a dead feed.
    #
    # The guard is therefore RELATIVE to the data's own magnitude: a standard deviation eighteen
    # orders below the mean is not a small edge, it is no variation at all.
    scale = max(1.0, abs(float(np.mean(r))))
    if not np.isfinite(s) or s <= 1e-12 * scale:
        return 0.0
    z = r / s
    # keep every component strictly positive: 1 + lam*z > 0  <=>  lam < 1/max(-z)
    worst = float(np.min(z))
    lam_max = 0.99 / abs(worst) if worst < 0 else float(_LAMBDAS[-1])
    lams = _LAMBDAS[lam_max > _LAMBDAS]
    if lams.size == 0:
        return 0.0
    # work in logs for numerical stability, then mix
    log_caps = np.array([np.sum(np.log1p(lam * z)) for lam in lams])
    m = float(np.max(log_caps))
    mix = m + np.log(np.mean(np.exp(log_caps - m)))
    # CLAMPED BEFORE exp, because a genuinely strong edge overflows it. At 600 observations of a
    # real edge `mix` exceeds 709 and `np.exp` returns inf with a RuntimeWarning -- and this repo
    # runs `filterwarnings = error`, so the gate RAISED on exactly the candidates it should have
    # passed most confidently. exp(700) is ~1.01e304: finite, and above any threshold a caller
    # could state, so ordering is preserved everywhere it can matter.
    return float(np.exp(min(float(mix), 700.0)))


def graduates(returns: np.ndarray | list[float], *, alpha: float = 0.01) -> dict[str, float | bool]:
    """Anytime-valid verdict. Safe to call every day on the same growing series.

    alpha=0.01 is deliberately stricter than a usual 0.05: this gate can be peeked at daily and
    the desk's whole failure mode is promoting noise."""
    e = e_value(returns)
    thr = 1.0 / alpha
    return {"e_value": round(e, 4), "threshold": thr, "graduates": bool(e >= thr),
            "n": int(np.size(returns)), "alpha": alpha}


def days_to_graduation(returns: np.ndarray | list[float], *, alpha: float = 0.01) -> int | None:
    """First index at which the e-process would have crossed -- i.e. how much calendar the
    always-valid rule would have SAVED versus a fixed clock. None if it never crosses."""
    r = np.asarray(returns, dtype="float64")
    for t in range(_MIN_OBS, r.size + 1):
        if e_value(r[:t]) >= 1.0 / alpha:
            return t
    return None
