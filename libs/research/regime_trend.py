"""Mechanisms from the 2026-08-01 transcript batch that are NOT price-displacement indicators.

The desk already holds thirteen textbook constructions in transcript_candidates.py and measured
what they are worth: 129 of them across 10 liquid pairs on daily bars produced ZERO survivors at a
maximum out-of-sample Sharpe of 0.100. Adding a fourteenth moving-average variant is not a
research plan. So this file takes only the claims from the new transcripts that are STRUCTURALLY
DIFFERENT from what has already been refuted here, and each one carries the mechanism its source
stated, because a mechanism is the only part of a transcript claim that can be falsified.

  1. TIME-IN-DIRECTION (Gebhardt, 10 Dynamics). "Equities have been up for six months and then
     go down for a couple of days. Even if that price movement down was bigger than the movement
     up, the time element is still bullish -- you spent a lot more time going up than going
     down." Every indicator the desk has tested measures DISPLACEMENT: where price ended relative
     to where it was. This measures OCCUPANCY: what fraction of bars moved which way, ignoring
     magnitude entirely. The two disagree exactly when one violent counter-move dominates a long
     quiet drift, which is the case where displacement measures are known to whipsaw. That
     disagreement is the whole hypothesis, and it is why this is worth a slot when a fourteenth
     moving average is not.
     MECHANISM: a slow accumulator (pension flow, corporate buyback, systematic rebalance) buys in
     many small increments; a forced seller (margin call, redemption, liquidation) sells in few
     large ones. Occupancy sees the accumulator that displacement's variance drowns out.
     FALSIFIER: occupancy and displacement signals agree on >95% of bars, or occupancy's edge
     vanishes once holding-period costs are charged.

  2. THE VOLATILITY-TREND QUADRANT (Gebhardt). "Everybody says trend followers make money in high
     volatility. That's actually not exactly right. The ideal for trend following is LOW
     volatility but a strong trend. High volatility tends to work good in bull markets but high
     volatility in bear markets is really tough, because short-covering rallies tend to be really
     fast relative to the downtrend that precedes them."
     This is a directly testable contradiction of a widely-held belief, it names an asymmetry
     (high-vol UP is fine, high-vol DOWN is not), and it states a mechanism for the asymmetry.
     MECHANISM: a short-covering rally is BUYING BY THE FORCED, so it is fast and convex; the
     downtrend that preceded it was selling by the willing, so it is slow. A symmetric trend
     model is short exactly when that convexity fires.
     FALSIFIER: measured strategy Sharpe does not differ across the four quadrants, or the
     high-vol asymmetry between up and down regimes is absent.

  3. CONVICTION GATING (Gebhardt). "If we're relatively lightly positioned in a market, we
     probably shouldn't trade it at all. Why waste the money getting chopped around?"
     The desk's own campaign machinery is equal-weight by construction. This says the smallest
     positions are not small bets on a real edge, they are noise that pays full transaction costs.
     MECHANISM: position size in a trend model is a monotone function of signal strength, and
     signal strength near zero is dominated by estimation error rather than by trend.
     FALSIFIER: returns from the bottom conviction decile are not worse net-of-cost than the rest.

DELIBERATELY NOT BUILT HERE, and recorded rather than silently dropped:
  * Vendor point-in-time revision (Mann) -- a DATA INTEGRITY question, not a mechanism. It belongs
    to the recorder, not to a signal file. Logged as a hypothesis; see the module docstring of
    scripts/measure_alpha_persistence.py for the one that IS measurable today.
  * Only-add-to-winners / the 30% rule (Temiz) -- a POSITION-SCALING law, not a signal. It has no
    meaning for this desk's current book, which does not discretionarily scale into a thesis.
  * The 10:30 "zombie rule" (Temiz) -- a US-equity intraday liquidity effect on small caps. This
    desk trades crypto perpetuals, which have no 09:30 open and no volume cliff at 10:30. The
    mechanism (edge decays when the volume that created it leaves) is real and general; the
    specific clock time is not portable and would be cargo cult.

EVERY FUNCTION RETURNS A POSITION SERIES in [-1, 1] aligned to the input bars, computed only from
information at or before each bar, to be applied to the NEXT bar's return by
transcript_candidates.positions_to_returns. Get that alignment wrong and every number is fiction.
"""

from __future__ import annotations

import numpy as np

__all__ = [
    "CANDIDATES",
    "conviction_gate",
    "occupancy_divergence",
    "quadrant_labels",
    "time_in_direction",
    "vol_trend_quadrant",
]


def _rolling_mean(x: np.ndarray, n: int) -> np.ndarray:
    out = np.full(len(x), np.nan)
    if n < 1 or len(x) < n:
        return out
    c = np.cumsum(np.insert(np.nan_to_num(x, nan=0.0), 0, 0.0))
    out[n - 1:] = (c[n:] - c[:-n]) / n
    return out


def _rolling_std(x: np.ndarray, n: int) -> np.ndarray:
    out = np.full(len(x), np.nan)
    for i in range(n - 1, len(x)):
        w = x[i - n + 1:i + 1]
        if np.isfinite(w).all():
            out[i] = float(np.std(w, ddof=1))
    return out


# --------------------------------------------------------------------------- 1. time in direction

def time_in_direction(close: np.ndarray, *, n: int = 60) -> np.ndarray:
    """Fraction of the last `n` bars that closed UP, mapped to [-1, 1]. Magnitude is DISCARDED.

    This is the whole point and it must not be softened. `np.sign` before averaging is what makes
    this occupancy rather than displacement: a single -20% bar and a single -0.01% bar contribute
    identically. That is the property that lets it disagree with every other trend measure the
    desk holds, and a version that weighted by size would collapse into a slow momentum signal and
    be worth nothing new.

    Returned as 2 * up_fraction - 1, so 0.0 means an exact 50/50 split and the sign is the
    direction that occupied more of the window.
    """
    c = np.asarray(close, dtype="float64")
    up = np.sign(np.diff(c, prepend=c[0]))
    up[0] = 0.0
    frac = _rolling_mean(up, n)
    clipped: np.ndarray = np.clip(np.nan_to_num(frac, nan=0.0), -1.0, 1.0)
    return clipped


def occupancy_divergence(close: np.ndarray, *, n: int = 60,
                         min_occ: float = 0.10, min_disp: float = 0.25) -> np.ndarray:
    """Trade the occupancy side ONLY where occupancy and displacement point OPPOSITE ways.

    The pure occupancy signal above is mostly redundant with momentum -- markets that rise usually
    rise on most days. The information that is genuinely new lives in the disagreement, so this
    isolates it and trades nothing else.

    DISAGREEMENT IS DEFINED BY SIGN, and the first version of this got that wrong in a way worth
    recording. It tested ``|occ - disp| > 0.25``, which reads as a sensible distance -- and is not,
    because the two quantities live on different scales. Occupancy is a fraction of up-bars, so in
    practice it stays inside about +/-0.3; displacement is a clipped t-statistic that saturates at
    +/-1. Measured across four simulated regimes the MEDIAN |occ - disp| was 0.700, so a 0.25
    threshold fired on ~87% of bars: it was measuring the scale mismatch, not the disagreement,
    and would have shipped as "a sparse divergence signal" that was nothing of the kind. Sign
    disagreement plus a magnitude floor on each side is scale-free and actually means what the
    name says.

    This makes the signal genuinely sparse, which is the point. A signal that fires constantly is
    one whose edge has already been priced; one that fires only in the configuration its mechanism
    describes -- a patient accumulator drowned out by a single violent counter-move -- is the
    version worth a scarce forward slot.

    SPARSITY IS A PREREQUISITE, NOT A FREE PARAMETER. Measured over 12 simulated series x 1500
    bars across four regimes, firing rate against min_disp:

        min_disp   0.05    0.10    0.15    0.25    0.40
        fire rate  2.14%   1.82%   1.59%   1.20%   0.57%
        events      369     315     274     208      98

    ``validate()`` refuses under 250 observations, so at the mechanism-motivated default of 0.25
    this needs a WIDER PANEL or a LONGER TAPE than 12x1500 to be scorable at all. The default
    stays where the mechanism puts it (displacement must be at least a quarter-saturated before
    "opposed" means anything) and the sample requirement is reported as a named prerequisite.
    Sliding it to 0.15 because that is the value which clears the observation floor would be
    tuning an input to make a gate pass, which is the same defect as relaxing the gate and is
    harder to see.
    """
    c = np.asarray(close, dtype="float64")
    occ = time_in_direction(c, n=n)
    ret = np.diff(c, prepend=c[0]) / np.where(c == 0.0, np.nan, c)
    ret[0] = 0.0
    scale = _rolling_std(ret, n) * np.sqrt(n)
    disp_sum = _rolling_mean(ret, n) * n
    disp = np.divide(disp_sum, scale, out=np.zeros_like(disp_sum),
                     where=np.isfinite(scale) & (scale > 0))
    disp = np.clip(np.nan_to_num(disp, nan=0.0), -1.0, 1.0)
    opposed = (np.sign(occ) * np.sign(disp) < 0) & (np.abs(occ) >= min_occ) \
        & (np.abs(disp) >= min_disp)
    return np.where(opposed, occ, 0.0)


# --------------------------------------------------------------- 2. the volatility-trend quadrant

#: Row = volatility tercile (low/mid/high), column = trend state (down/range/up). The claim under
#: test is that (low, up) and (low, down) are the desk's best cells and (high, down) is its worst.
quadrant_labels = ("lowvol-down", "lowvol-range", "lowvol-up",
                   "midvol-down", "midvol-range", "midvol-up",
                   "highvol-down", "highvol-range", "highvol-up")


def vol_trend_quadrant(close: np.ndarray, *, n: int = 60,
                       lookback: int = 252) -> np.ndarray:
    """Label each bar 0-8 by (volatility tercile, trend state); -1 where history is short.

    Terciles are computed against a TRAILING window, never against the whole sample. Ranking a bar
    against the full history is the classic in-sample leak: it uses the fact that 2026 was a
    high-vol year to classify a bar in January of it, which no live system could know. This is the
    error the desk's own lesson L0015 is about, and it is invisible in results -- it just makes
    every regime study look better than it is.
    """
    c = np.asarray(close, dtype="float64")
    ret = np.diff(c, prepend=c[0]) / np.where(c == 0.0, np.nan, c)
    ret[0] = 0.0
    vol = _rolling_std(ret, n)
    occ = time_in_direction(c, n=n)
    out = np.full(len(c), -1, dtype="int64")
    for i in range(len(c)):
        if i < lookback or not np.isfinite(vol[i]):
            continue
        hist = vol[max(0, i - lookback):i]
        hist = hist[np.isfinite(hist)]
        if len(hist) < 30:
            continue
        lo, hi = np.percentile(hist, [33.0, 67.0])
        vt = 0 if vol[i] <= lo else (2 if vol[i] > hi else 1)
        st = 0 if occ[i] < -0.10 else (2 if occ[i] > 0.10 else 1)
        out[i] = vt * 3 + st
    return out


def conviction_gate(pos: np.ndarray, *, n: int = 252,
                    floor_pct: float = 30.0) -> np.ndarray:
    """Zero out the weakest `floor_pct` of positions by absolute size, ranked against the past.

    Gebhardt's claim in one line: the smallest positions a trend model takes are not small bets on
    a real edge, they are estimation noise paying full transaction costs, so the portfolio is
    better off flat there.

    The threshold is a TRAILING percentile for the same reason the terciles above are: comparing
    today's conviction against the whole sample's distribution leaks the future into the gate.

    This is a strict reduction in exposure -- it can only remove trades, never add or flip one. So
    if measured returns get WORSE after gating, that is a clean refutation of the claim rather
    than a confounded result, which is exactly the property a filter should have.
    """
    p = np.nan_to_num(np.asarray(pos, dtype="float64"), nan=0.0)
    mag = np.abs(p)
    out: np.ndarray = p.copy()
    for i in range(len(p)):
        if i < n:
            continue
        hist = mag[i - n:i]
        hist = hist[hist > 0]
        if len(hist) < 30:
            continue
        if mag[i] <= np.percentile(hist, floor_pct):
            out[i] = 0.0
    return out


def _asymmetric_vol_trend(close: np.ndarray, *, n: int = 60) -> np.ndarray:
    """Trade the occupancy trend, but stand aside in HIGH-VOL DOWNTRENDS specifically.

    This is the asymmetry claim as a mechanism, not as a fitted mask. The exclusion is one named
    cell out of nine, chosen in advance for a stated reason -- short-covering rallies are buying
    by the forced, so they are fast and convex, and a symmetric trend model is short precisely
    when that convexity fires. Excluding the worst cell found by search would be curve-fitting;
    excluding the cell whose mechanism predicts the loss is a test of the mechanism.
    """
    occ = time_in_direction(close, n=n)
    q = vol_trend_quadrant(close, n=n)
    return np.where(q == 6, 0.0, occ)   # 6 == highvol-down


#: name -> callable(close) -> position series. Kept OHLCV-free on purpose: the recorded moat tape
#: and daily bars both provide close, so these run on either without an adapter.
CANDIDATES = {
    "time_in_direction": time_in_direction,
    "occupancy_divergence": occupancy_divergence,
    "asymmetric_vol_trend": _asymmetric_vol_trend,
}
