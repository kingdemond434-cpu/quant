"""INTERMARKET DIFFERENCING -- remove the common factor, trade what is left.

PROVENANCE. neurotrader, "Intramarket Indicator Differences" (2026-08-01 batch). Adopted because
it lands exactly on this desk's largest MEASURED defect, not because it is a nice idea.

THE DEFECT IT ADDRESSES, with the numbers. reports/live_book_concentration.json measured 28 OKX
perps at mean pairwise daily correlation 0.682 and concluded: the live 4-position book is worth
1.31 EFFECTIVE positions against a floor of 2.0, none of the 20,475 possible 4-name books clears
that floor, and -- the part that matters -- "adding names cannot fix this, the equicorrelation
ceiling is 1/rho = 1.47. REMOVE THE COMMON FACTOR." The same report measured the counterfactual:
cross-sectionally de-meaned, those same books run at ~3.9 effective positions. This module is the
producer for that counterfactual. It is the difference between a book of four bets and a book of
one bet held four times.

WHAT THE DESK ALREADY HAD, AND WHY IT WAS NOT THIS. `generators._cross_asset` is the entire
existing cross-asset surface and it computes ``-sign(ref_close pct-change)`` -- fade whatever BTC
did on the last bar. That is not a relative-value measure: it never compares the two instruments,
it is not scale-free, and its answer is identical whether the traded symbol outperformed the
reference by 10% or lagged it by 10%. It is kept (deleting it would erase the record of what was
tested) and this is added alongside it.

THE NORMALISATION IS THE WHOLE TRICK, and it is why raw indicator differencing fails. Subtracting
one symbol's indicator from another's is only meaningful if the indicator is on the SAME SCALE for
both. Two things break that: price level (a $60,000 instrument's close-minus-average dwarfs a
$0.15 one's) and volatility (a 2%/day instrument and a 12%/day one produce incomparable
deviations at identical levels of "unusual"). Log prices fix the first. Dividing by ATR fixes the
second. The ``sqrt(lookback)`` term fixes a third that is easy to miss: the deviation of a random
walk from its own n-bar moving average has standard deviation ``sigma * sqrt(n/3)``, so WITHOUT
it the indicator's dispersion grows with the lookback and a difference taken between two different
lookbacks -- or compared against a fixed threshold across lookbacks -- is comparing different
units. With it, CMMA is dimensionless and stable in both n and sigma. That is testable and it is
tested.

WHAT THE SOURCE MEASURED, RECORDED WITH ITS CAVEAT. ETH-vs-BTC hourly, lookback 24, threshold
0.25: profit factor 1.08 over ~4,400 trades, both sides slightly above 50% win rate, and a
parameter heat map above 1.0 nearly everywhere. NO TRANSACTION COSTS WERE INCLUDED. A profit
factor of 1.08 on 4,400 hourly round trips is roughly 8 basis points of gross edge per trade; the
desk's own cost assumption in `generators.net_returns` is 3bp per unit of turnover, so half that
gross edge is gone before slippage. The robustness across parameters is the real finding here; the
1.08 is not a promise, and this module makes no claim to it.
"""

from __future__ import annotations

import numpy as np

#: Per the source: the ATR lookback should be long enough to characterise the market's general
#: volatility rather than the current week's, and materially longer than the moving-average
#: lookback it normalises. 168 bars (one week of hourly) in the source; expressed here as a
#: multiple so it stays correct when the desk runs this on daily bars.
DEFAULT_ATR_MULTIPLE = 7

_EPS = 1e-12


def true_range(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> np.ndarray:
    """max(h-l, |h-c_prev|, |l-c_prev|). In LOG space when handed log prices, which is the point.

    The gap terms are not decoration: a market that opens 5% away and then trades a quiet 1% range
    had a 5% day, and a range-only estimate would call it calm and inflate every normalised
    deviation measured against it.
    """
    h, low_, c = (np.asarray(x, dtype="float64") for x in (high, low, close))
    if not len(h) == len(low_) == len(c):
        raise ValueError("high/low/close must be the same length")
    prev = np.empty_like(c)
    prev[0] = c[0]
    prev[1:] = c[:-1]
    tr: np.ndarray = np.maximum(h - low_, np.maximum(np.abs(h - prev), np.abs(low_ - prev)))
    return tr


def atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, *, lookback: int) -> np.ndarray:
    """Trailing mean true range. NaN until a full window exists.

    A partial window is not a shorter estimate, it is a DIFFERENT estimator with a different bias,
    and letting it through would make the first bars of every backtest quietly non-comparable to
    the rest.
    """
    if lookback < 2:
        raise ValueError(f"atr lookback must be >= 2, got {lookback}")
    tr = true_range(high, low, close)
    out = np.full(len(tr), np.nan)
    if len(tr) < lookback:
        return out
    csum = np.cumsum(np.insert(tr, 0, 0.0))
    out[lookback - 1:] = (csum[lookback:] - csum[:-lookback]) / lookback
    return out


def cmma(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    *,
    lookback: int,
    atr_lookback: int | None = None,
) -> np.ndarray:
    """Close-Minus-Moving-Average, normalised to be comparable ACROSS symbols and lookbacks.

        (log C - SMA(log C, n)) / (ATR_log(m) * sqrt(n))

    ALL THREE DIVISIONS ARE LOAD-BEARING and each removes one reason two symbols' readings would
    not be comparable: log removes price level, ATR removes volatility, sqrt(n) removes the
    lookback (a random walk's deviation from its own n-bar mean scales as sigma*sqrt(n/3), so the
    raw statistic grows with n and a fixed threshold would mean something different at every
    lookback). The result is dimensionless and its dispersion is stable in both n and sigma --
    which is exactly the precondition for subtracting one symbol's reading from another's.

    Inputs are PRICES; the log is taken here. Non-positive prices raise rather than producing
    -inf and propagating a silent NaN mask through the difference.
    """
    if lookback < 2:
        raise ValueError(f"lookback must be >= 2, got {lookback}")
    arrs = [np.asarray(x, dtype="float64") for x in (high, low, close)]
    if any(np.any(a <= 0.0) for a in arrs):
        raise ValueError("non-positive prices -- the log normalisation is undefined")
    lh, ll, lc = (np.log(a) for a in arrs)

    m = int(atr_lookback if atr_lookback is not None else lookback * DEFAULT_ATR_MULTIPLE)
    a = atr(lh, ll, lc, lookback=m)

    out = np.full(len(lc), np.nan)
    if len(lc) < lookback:
        return out
    csum = np.cumsum(np.insert(lc, 0, 0.0))
    sma = (csum[lookback:] - csum[:-lookback]) / lookback
    dev = lc[lookback - 1:] - sma
    denom = a[lookback - 1:] * np.sqrt(lookback)
    # A zero ATR means a frozen feed, not a market of infinite unusualness. NaN, not inf.
    with np.errstate(divide="ignore", invalid="ignore"):
        vals = np.where(denom > _EPS, dev / denom, np.nan)
    out[lookback - 1:] = vals
    return out


def intermarket_difference(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    ref_high: np.ndarray,
    ref_low: np.ndarray,
    ref_close: np.ndarray,
    *,
    lookback: int,
    atr_lookback: int | None = None,
) -> np.ndarray:
    """CMMA(symbol) - CMMA(reference): how unusually this symbol sits versus the reference.

    ZERO IS THE EQUILIBRIUM AND IT IS EARNED, not assumed. Both terms are individually centred by
    their own moving average and individually scaled by their own volatility, so a reading of zero
    means "both instruments are equally far from their own normal", not "the prices are equal".
    That is what lets a fixed threshold mean the same thing on a BTC/ETH pair and on a BTC/altcoin
    pair whose volatilities differ by 4x.

    THIS IS THE COMMON-FACTOR REMOVAL the concentration report demanded. A book built on these
    differences is long the residual and flat the market factor that drove 28 perps to 0.682 mean
    pairwise correlation and the live 4-name book to 1.31 effective positions.
    """
    a = cmma(high, low, close, lookback=lookback, atr_lookback=atr_lookback)
    b = cmma(ref_high, ref_low, ref_close, lookback=lookback, atr_lookback=atr_lookback)
    if len(a) != len(b):
        raise ValueError("symbol and reference series must be the same length -- align them "
                         "on timestamps before differencing, do not rely on broadcasting")
    diff: np.ndarray = a - b
    return diff


def threshold_revert(indicator: np.ndarray, *, threshold: float) -> np.ndarray:
    """Enter on a threshold crossing, exit when the indicator returns to zero. Stateful by design.

    +1 above +threshold, -1 below -threshold, flat once the indicator crosses back through zero.
    The position PERSISTS between those events, which is the whole construction: the entry is a
    relative-momentum bet (outperformance tends to continue) and the exit is the equilibrium the
    indicator is centred on, so holding periods are set by the market rather than by a second
    tuned parameter. A stateless ``sign(|x| > threshold)`` rule would exit as soon as the reading
    cooled below the threshold and would be a different, much twitchier strategy.

    NaN LEAVES THE POSITION UNCHANGED rather than flattening it. During the warm-up there is no
    reading at all; treating "not yet computable" as "the signal said exit" would manufacture a
    round trip at the first valid bar of every backtest.
    """
    if threshold <= 0:
        raise ValueError(f"threshold must be positive, got {threshold}")
    x = np.asarray(indicator, dtype="float64")
    out = np.zeros(len(x), dtype="float64")
    pos = 0.0
    for i, v in enumerate(x):
        if np.isnan(v):
            out[i] = pos
            continue
        if v > threshold:
            pos = 1.0
        elif v < -threshold:
            pos = -1.0
        elif (pos > 0 and v <= 0.0) or (pos < 0 and v >= 0.0):
            pos = 0.0
        out[i] = pos
    return out
