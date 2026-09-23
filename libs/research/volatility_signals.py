"""DIRECTION-AGNOSTIC SIGNALS -- built on the one prior in the transcript batch that should
change what this desk hunts, not merely add to it.

THE CLAIM, and it is the most strategically loaded sentence in any transcript mined so far
(Lachezar, freeCodeCamp quant course, 2026-08-01 batch). Ranked by how hard each is to predict:

    price / return level      HARDEST
    return SIGN (direction)   still very hard
    economic indicators       hard
    VOLATILITY                "not that hard, quite straightforward"

This is not one practitioner's opinion; it is the standard finding of the volatility-forecasting
literature and it is why GARCH is a solved, teachable, textbook technique while return prediction
is not. It matters here because THIS DESK HAS BEEN HUNTING ALMOST ENTIRELY IN THE HARDEST ROW.
Every one of the 129 mechanisms in the 2026-08-01 campaign predicted direction. All 129 failed,
at a maximum out-of-sample Sharpe of 0.100. Meanwhile the one family that has ever repeat-survived
here -- funding/carry -- is not a directional bet at all.

So the adoption is not "add a volatility indicator". It is: spend some of a scarce forward slot
budget on the row where prediction is known to be tractable, and build signals whose edge does not
require calling direction.

WHAT IS BUILT:

  1. GARMAN-KLASS VOLATILITY. A range-based variance estimator using the full OHLC bar rather
     than close-to-close. Roughly 7x more efficient than close-to-close at the same sample size,
     because a bar's high and low carry information about the path that its close throws away.
     Free accuracy on data the desk already stores -- and a better volatility estimate improves
     every vol-target, every risk gate and every regime label downstream, not just this file.

  2. PREDICTION PREMIUM. Forecast next-period variance, compare it to realised variance, and
     trade the standardised gap: (forecast - realised) / realised, thresholded at k rolling
     standard deviations. The transcript pairs a GARCH(1,3) forecast with an intraday
     mean-reversion trigger and takes a position only when both fire.
     MECHANISM: when a forecast conditioned on recent shocks sits far above what actually
     realised, the market has been PRICING a risk that did not arrive -- and the compensation for
     bearing risk that does not arrive is the oldest real premium there is. That is the same
     economic story as the funding carry this desk already knows works, which is a point in its
     favour rather than a coincidence.
     FALSIFIER: the premium's sign carries no information about forward returns once the vol
     level itself is controlled for -- i.e. it is a repackaged volatility factor.

WHY EWMA AND NOT GARCH. `arch` is not installed and adding a dependency to test a hypothesis is
backwards. EWMA (RiskMetrics) is the standard baseline that GARCH must BEAT to justify itself, so
if the premium carries no signal under EWMA there is no reason to install anything; and if it
does, the GARCH upgrade becomes a measured improvement over a recorded baseline rather than an
untested assumption. `ewma_variance` exposes lambda so that comparison is a one-line change.

NOT ADOPTED FROM THE SAME SOURCE, recorded rather than dropped:
  * The Fama-French 5-factor rolling betas as features. The factors are equity constructs and this
    desk trades crypto perpetuals; the portable part is the PATTERN (rolling factor betas as
    features, missing betas imputed with the asset's own mean rather than zero), and the crypto
    analog would be rolling betas to BTC, to a size proxy and to a funding factor. Logged as a
    hypothesis, not built blind.
  * Efficient-frontier max-Sharpe monthly rebalancing. Max-Sharpe on 12 months of daily data is
    famously unstable -- the transcript's own code hits solver failure often enough to need an
    equal-weight fallback, which is the estimation error announcing itself. This desk's allocator
    question is slot admission by EV rank, not mean-variance weights.
  * K-means over a monthly cross-section of engineered features. It is clustering, not a
    mechanism, and cluster membership is not a reason anyone is forced to trade against you.
"""

from __future__ import annotations

import numpy as np

__all__ = [
    "PREMIUM_Z",
    "dvol_to_variance",
    "ewma_variance",
    "garman_klass",
    "invalid_bars",
    "prediction_premium",
    "premium_signal",
    "realised_variance",
]

#: Threshold in rolling standard deviations of the premium before a position is taken. Held at the
#: source's value rather than swept: sweeping it here would be fitting a threshold on the same data
#: the hypothesis is about, and the gauntlet counts every swept cell as a trial anyway.
PREMIUM_Z = 1.5

#: RiskMetrics daily decay. The industry default, used so the baseline is a recognised one rather
#: than a fitted one.
EWMA_LAMBDA = 0.94

#: Variance floor below which a series is treated as having NO measurable variance.
#:
#: A `> 0` guard is worthless here and this constant exists because it let a bug through. On a
#: constant return series numpy's variance returns floating-point dust (~5e-38) rather than
#: exactly zero, which passes `> 0`, and dividing forecast dust by realised dust produced a
#: prediction premium of 1.4e31 -- a colossal, entirely fictional signal that fired constantly.
#: The assets where that happens are real and common: a pegged pair, a halted market, a dead
#: altcoin, any symbol whose feed froze. Those are exactly the series a backtest sweep will
#: happily include and exactly the ones whose fake edge nobody questions, because a stablecoin
#: showing an enormous Sharpe looks like a bug in someone else's code.
#: 1e-20 in variance is 1e-10 in return standard deviation -- far below any real price increment
#: and far above float dust.
_VAR_FLOOR = 1e-20


def garman_klass(high: np.ndarray, low: np.ndarray, close: np.ndarray,
                 open_: np.ndarray) -> np.ndarray:
    """Per-bar variance from the full OHLC range.

        0.5 * (ln(H/L))^2 - (2*ln2 - 1) * (ln(C/O))^2

    Uses the whole bar's path rather than only its endpoint, which is where the efficiency gain
    comes from -- a bar that travelled 4% and closed flat is not the same as one that never moved,
    and close-to-close cannot tell them apart.

    A NEGATIVE VALUE PROVES THE BAR IS INVALID, and this is worth more than the estimator.
    Because open and close both lie inside [low, high] on any real bar, |ln(C/O)| <= ln(H/L)
    always, so

        GK >= (0.5 - (2*ln2 - 1)) * ln(H/L)^2 = 0.1137 * ln(H/L)^2 >= 0

    identically. There is no market condition that makes this negative. A negative output
    therefore means the DATA is broken -- a close or open outside its own bar's range, from a
    misaligned join, a bad merge, a venue's partial candle, or a corrupted backfill. That is a
    free integrity check on every bar the desk stores, and on a desk whose own measurement says
    53% of refutations were measurement failures rather than absent alpha, it is the more valuable
    half of this function. Negatives are RETURNED, never clipped: clipping would convert a loud,
    findable data defect into a silently slightly-wrong volatility estimate. Use `invalid_bars`
    to count them.
    """
    h = np.asarray(high, dtype="float64")
    lo = np.asarray(low, dtype="float64")
    c = np.asarray(close, dtype="float64")
    o = np.asarray(open_, dtype="float64")
    with np.errstate(divide="ignore", invalid="ignore"):
        hl = np.log(np.where(lo > 0, h / lo, np.nan))
        co = np.log(np.where(o > 0, c / o, np.nan))
    gk: np.ndarray = 0.5 * hl ** 2 - (2.0 * np.log(2.0) - 1.0) * co ** 2
    return gk


def invalid_bars(high: np.ndarray, low: np.ndarray, close: np.ndarray,
                 open_: np.ndarray) -> np.ndarray:
    """Bars whose Garman-Klass value is negative -- i.e. bars that cannot exist.

    See `garman_klass`: the estimator is non-negative for every valid OHLC bar, so a negative
    result is a proof of corruption rather than a statistical outlier. Cheap enough to run over
    an entire lake and specific enough that a hit is always worth chasing.
    """
    gk = garman_klass(high, low, close, open_)
    return np.asarray(np.isfinite(gk) & (gk < 0.0))


def ewma_variance(returns: np.ndarray, *, lam: float = EWMA_LAMBDA) -> np.ndarray:
    """One-step-ahead variance forecast, RiskMetrics recursion.

    `out[i]` is the variance forecast FOR bar i, built only from returns strictly before it. The
    off-by-one here is the difference between a forecast and a description, and getting it wrong
    produces a spectacular backtest that is simply reading the answer.
    """
    r = np.asarray(returns, dtype="float64")
    out = np.full(len(r), np.nan)
    if len(r) < 2:
        return out
    var = float(np.nanvar(r[:min(20, len(r))]))
    if not np.isfinite(var) or var <= 0:
        var = float(np.nanvar(r[np.isfinite(r)])) if np.isfinite(r).any() else 0.0
    for i in range(1, len(r)):
        out[i] = var                                    # forecast for i, from data before i
        prev = r[i - 1]
        if np.isfinite(prev):
            var = lam * var + (1.0 - lam) * prev * prev
    return out


def realised_variance(returns: np.ndarray, *, n: int = 21) -> np.ndarray:
    """Trailing realised variance over `n` bars, ending at each bar."""
    r = np.asarray(returns, dtype="float64")
    out = np.full(len(r), np.nan)
    for i in range(n, len(r)):
        w = r[i - n:i]
        w = w[np.isfinite(w)]
        if len(w) >= max(3, n // 2):
            out[i] = float(np.var(w, ddof=1))
    return out


def prediction_premium(returns: np.ndarray, *, n: int = 21,
                       lam: float = EWMA_LAMBDA,
                       implied_variance: np.ndarray | None = None) -> np.ndarray:
    """(forecast variance - realised variance) / realised variance.

    Scaled by realised variance rather than left as a difference so it is comparable across assets
    and across regimes -- an absolute variance gap is dominated by whichever asset happens to be
    the most volatile, which would make any cross-sectional use of this a volatility ranking
    wearing a premium's name.

    SUPPLY `implied_variance` AND THE PREMIUM BECOMES THE REAL ONE. The BRAIN options webinar is
    blunt about why: "what happened in the past has happened in the past; what CAN happen in the
    future is being currently priced in by the market, and that is what implied volatility gives
    you." EWMA is an extrapolation of realised returns -- a backward-looking estimate of a
    forward-looking quantity. Implied variance is the market's actual forecast, paid for in real
    money by people who lose if it is wrong.

    That upgrade turns this from a statistical artefact into the VARIANCE RISK PREMIUM, which is
    one of the most durable documented premia in any asset class and shares its economics with the
    financing carry this desk already knows works: both pay for bearing a risk that usually does
    not arrive. On the MT5 universe the implied leg is a quoted volatility index CFD (the VIX
    complex) or an option-implied series for an index the desk already trades, so the upgrade is a
    DATA ACQUISITION and is named as one here rather than assumed to be a wiring job.

    EWMA REMAINS THE DEFAULT ON PURPOSE. It is the baseline any implied-vol version must BEAT to
    justify the dependency, so a null result here needs no feed at all, and a positive one makes
    the IV upgrade a measured improvement over a recorded baseline rather than an assumption.
    `implied_variance` must be in the same units and alignment as realised variance -- an
    annualised vol index like DVOL is a PERCENTAGE ANNUAL VOLATILITY and has to be converted
    ((dvol/100)**2 / periods_per_year) before it is comparable. Passing it raw would inflate the
    premium by roughly the number of periods in a year, which is exactly the sort of units error
    that produces a spectacular and entirely fictional signal.
    """
    fc = (ewma_variance(returns, lam=lam) if implied_variance is None
          else np.asarray(implied_variance, dtype="float64"))
    if len(fc) != len(np.asarray(returns)):
        raise ValueError("implied_variance must align 1:1 with returns")
    rv = realised_variance(returns, n=n)
    with np.errstate(divide="ignore", invalid="ignore"):
        prem = np.where(np.isfinite(rv) & (rv > _VAR_FLOOR), (fc - rv) / rv, np.nan)
    return np.asarray(prem, dtype="float64")


def dvol_to_variance(dvol: np.ndarray, *, periods_per_year: float) -> np.ndarray:
    """Deribit's DVOL index -> per-period variance, in the units realised_variance produces.

    DVOL is quoted as an ANNUALISED VOLATILITY IN PERCENT. Three conversions are needed and
    skipping any of them produces a premium wrong by orders of magnitude: percent -> fraction,
    volatility -> variance, annual -> per-period. This function exists so that arithmetic lives in
    one place with a test on it, rather than being re-derived at each call site.
    """
    d = np.asarray(dvol, dtype="float64")
    if periods_per_year <= 0:
        raise ValueError("periods_per_year must be positive")
    return (d / 100.0) ** 2 / periods_per_year


def premium_signal(returns: np.ndarray, *, n: int = 21, window: int = 126,
                   z: float = PREMIUM_Z,
                   implied_variance: np.ndarray | None = None) -> np.ndarray:
    """Position in [-1, 1] when the premium exceeds +/- `z` rolling standard deviations.

    SIGN CONVENTION, stated because it is the whole economic claim and an inverted sign would
    quietly test the opposite hypothesis: a premium far ABOVE its own recent range means the
    forecast is pricing much more risk than has been realised, and the position taken is the one
    that gets PAID for supplying that insurance -- long. Far below means realised risk is running
    ahead of what is priced, and the position is short. If the measured edge is significant with
    the sign reversed, the mechanism is refuted even though the strategy "works", and that must be
    reported as a refutation rather than banked as a discovery.

    The rolling standard deviation uses only trailing data, so the threshold a bar is judged
    against never contains that bar's own future.
    """
    prem = prediction_premium(returns, n=n, implied_variance=implied_variance)
    out = np.zeros(len(prem))
    for i in range(window, len(prem)):
        w = prem[i - window:i]
        w = w[np.isfinite(w)]
        if len(w) < window // 2 or not np.isfinite(prem[i]):
            continue
        sd = float(np.std(w, ddof=1))
        if sd <= 0:
            continue
        if prem[i] > z * sd:
            out[i] = 1.0
        elif prem[i] < -z * sd:
            out[i] = -1.0
    return out
