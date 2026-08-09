"""Every tradeable mechanism named across the principal-supplied transcripts, as CANDIDATES.

WHY THIS FILE EXISTS AND THE OTHERS SHOULD NOT HAVE. The desk's standing order is that a change
which does not plausibly increase future compounded capital should not be built, and that the
governance layer is finished. Mechanisms are the exception: they are the only artifact class that
can produce a survivor, and a survivor is the only thing that compounds. Everything here is a
hypothesis for the gauntlet, none of it is a recommendation, and none of it reaches capital
without pre-registered forward evidence.

ORDERED BY MEASURED SURVIVAL BASE RATE, not by popularity. An external 131,441-backtest sweep
with walk-forward validation reported these family survival rates:

    volume            38.7%   <- built first
    mean reversion    38.5%   <- built first
    momentum          27.4%
    pattern           22.0%
    trend following   18.2%   <- built last, and it is what retail spends its time on

That ordering is the single most useful thing in any of the transcripts, because it is a prior
over WHERE TO SPEND GAUNTLET SLOTS. The desk's slots are scarce (MAX_FORWARD_SLOTS=12); spending
them in proportion to a measured survival rate rather than to intuition is free expected value.

EVERY FUNCTION RETURNS A POSITION SERIES in [-1, 1], aligned to the input bars, computed from
information available AT OR BEFORE each bar. Positions are applied to the NEXT bar's return by
``positions_to_returns`` -- the decision is made on today's close and earns tomorrow's move, which
is the only alignment that is not lookahead. Get this wrong and every result is fiction.
"""
from __future__ import annotations

import numpy as np


def _sma(x: np.ndarray, n: int) -> np.ndarray:
    """Trailing mean, NaN until enough history. Never centred -- a centred window sees ahead."""
    out = np.full(len(x), np.nan)
    if n < 1 or len(x) < n:
        return out
    c = np.cumsum(np.insert(x, 0, 0.0))
    out[n - 1:] = (c[n:] - c[:-n]) / n
    return out


def _rolling_std(x: np.ndarray, n: int) -> np.ndarray:
    out = np.full(len(x), np.nan)
    for i in range(n - 1, len(x)):
        out[i] = np.std(x[i - n + 1:i + 1], ddof=1)
    return out


def positions_to_returns(pos: np.ndarray, close: np.ndarray, *,
                         cost_per_turn: float = 0.0006) -> np.ndarray:
    """Strategy returns with costs on every change in position.

    COSTS ARE ALWAYS ON. Three of the transcripts independently name ignored fees and slippage as
    the reason a backtest lies, and they are right: at 6 bps per turn a daily-rebalanced strategy
    pays ~150 bps a year, which is most of a marginal edge. `pos[i]` is the position held INTO
    bar i+1, so it earns bar i+1's return.
    """
    p = np.nan_to_num(np.asarray(pos, dtype="float64"), nan=0.0)
    c = np.asarray(close, dtype="float64")
    r = np.zeros(len(c))
    r[1:] = np.diff(c) / c[:-1]
    gross = p[:-1] * r[1:]
    turn = np.abs(np.diff(np.concatenate([[0.0], p[:-1]])))
    return np.asarray(gross - turn * cost_per_turn)


# --------------------------------------------------------------------------------------------
# VOLUME family -- highest measured survival rate (38.7%)
# --------------------------------------------------------------------------------------------

def chaikin_money_flow(high: np.ndarray, low: np.ndarray, close: np.ndarray,
                       volume: np.ndarray, *, n: int = 20, thresh: float = 0.05) -> np.ndarray:
    """CMF: volume weighted by where the close sits inside each bar's range.

    The mechanism is a real microstructure claim rather than a pattern: closing near the high on
    heavy volume means buyers absorbed the day's supply, and absorption is informative in a way
    that price alone is not. The transcript's verified set has this on gold at OOS Sharpe 0.99.
    """
    h, lo, c, v = (np.asarray(x, dtype="float64") for x in (high, low, close, volume))
    rng = np.where((h - lo) > 0, h - lo, np.nan)
    mfm = ((c - lo) - (h - c)) / rng
    mfv = np.nan_to_num(mfm) * v
    cmf = _sma(mfv, n) / np.where(_sma(v, n) > 0, _sma(v, n), np.nan)
    return np.where(np.isnan(cmf), 0.0, np.where(cmf > thresh, 1.0,
                                                 np.where(cmf < -thresh, -1.0, 0.0)))


def volume_surge_breakout(close: np.ndarray, volume: np.ndarray, *, n: int = 20,
                          mult: float = 2.0) -> np.ndarray:
    """Long when price makes an n-bar high ON volume well above its own average.

    The volume condition is what separates this from a plain breakout: a level broken on no
    volume is a level nobody defended, and it tends to fail back through.
    """
    c, v = np.asarray(close, dtype="float64"), np.asarray(volume, dtype="float64")
    pos = np.zeros(len(c))
    vbar = _sma(v, n)
    for i in range(n, len(c)):
        if c[i] >= np.max(c[i - n:i]) and vbar[i] > 0 and v[i] > mult * vbar[i]:
            pos[i] = 1.0
    return pos


def obv_trend(close: np.ndarray, volume: np.ndarray, *, n: int = 20) -> np.ndarray:
    """On-balance volume above its own trailing mean -- accumulation, not price."""
    c, v = np.asarray(close, dtype="float64"), np.asarray(volume, dtype="float64")
    sign = np.sign(np.concatenate([[0.0], np.diff(c)]))
    obv = np.cumsum(sign * v)
    m = _sma(obv, n)
    return np.where(np.isnan(m), 0.0, np.where(obv > m, 1.0, -1.0))


# --------------------------------------------------------------------------------------------
# MEAN REVERSION family -- 38.5%, and it dominates the transcript's verified survivor list
# --------------------------------------------------------------------------------------------

def zscore_reversion(close: np.ndarray, *, n: int = 20, entry: float = 2.0,
                     exit_z: float = 0.5) -> np.ndarray:
    """Fade a stretch beyond `entry` sigma, flatten back at `exit_z`.

    Separate entry and exit thresholds on purpose: a single threshold makes the strategy churn
    across the boundary, and turnover is where a thin edge dies.
    """
    c = np.asarray(close, dtype="float64")
    z = (c - _sma(c, n)) / np.where(_rolling_std(c, n) > 0, _rolling_std(c, n), np.nan)
    pos = np.zeros(len(c))
    cur = 0.0
    for i in range(len(c)):
        if np.isnan(z[i]):
            pos[i] = 0.0
            continue
        if cur == 0.0:
            cur = -1.0 if z[i] > entry else (1.0 if z[i] < -entry else 0.0)
        elif abs(z[i]) < exit_z:
            cur = 0.0
        pos[i] = cur
    return pos


def bollinger_reversion(close: np.ndarray, *, n: int = 20, k: float = 2.0) -> np.ndarray:
    """Buy the lower band, sell the upper. The canonical form, kept plain so the gauntlet scores
    the MECHANISM rather than a tuned variant of it."""
    return zscore_reversion(close, n=n, entry=k, exit_z=0.25)


def percent_b_reversion(close: np.ndarray, *, n: int = 20, k: float = 2.0) -> np.ndarray:
    """%B: position inside the band as a fraction. Long under 0, short over 1."""
    c = np.asarray(close, dtype="float64")
    m, s = _sma(c, n), _rolling_std(c, n)
    upper, lower = m + k * s, m - k * s
    width = np.where((upper - lower) > 0, upper - lower, np.nan)
    b = (c - lower) / width
    return np.where(np.isnan(b), 0.0, np.where(b < 0.0, 1.0, np.where(b > 1.0, -1.0, 0.0)))


def rsi_mean_reversion(close: np.ndarray, *, n: int = 14, low: float = 30.0,
                       high: float = 70.0) -> np.ndarray:
    """The transcript's most-replicated survivor -- verified independently on four uncorrelated
    assets, which is consistency evidence rather than one lucky dataset."""
    c = np.asarray(close, dtype="float64")
    d = np.concatenate([[0.0], np.diff(c)])
    gain, loss = _sma(np.clip(d, 0, None), n), _sma(-np.clip(d, None, 0), n)
    rs = gain / np.where(loss > 0, loss, np.nan)
    rsi = 100.0 - 100.0 / (1.0 + rs)
    return np.where(np.isnan(rsi), 0.0, np.where(rsi < low, 1.0, np.where(rsi > high, -1.0, 0.0)))


def range_position_dip(high: np.ndarray, low: np.ndarray, close: np.ndarray, *,
                       pct: float = 0.10, trend_n: int = 200, hold: int = 3) -> np.ndarray:
    """Close in the bottom `pct` of the day's range WHILE above the long trend -- buy, hold N.

    The trend filter is what makes this different from catching a falling knife: a weak close
    inside an uptrend is supply being absorbed; the same close inside a downtrend is just a
    downtrend. Exits on a strong close or after `hold` bars.
    """
    h, lo, c = (np.asarray(x, dtype="float64") for x in (high, low, close))
    trend = _sma(c, trend_n)
    rng = np.where((h - lo) > 0, h - lo, np.nan)
    loc = (c - lo) / rng
    pos, left = np.zeros(len(c)), 0
    for i in range(len(c)):
        if left > 0:
            left -= 1
            pos[i] = 1.0
            if not np.isnan(loc[i]) and loc[i] > 0.75:
                left = 0
        elif (not np.isnan(loc[i]) and not np.isnan(trend[i])
              and loc[i] < pct and c[i] > trend[i]):
            pos[i], left = 1.0, hold - 1
    return pos


# --------------------------------------------------------------------------------------------
# MOMENTUM (27.4%) and TREND (18.2%) -- built last, deliberately
# --------------------------------------------------------------------------------------------

def squeeze_momentum(high: np.ndarray, low: np.ndarray, close: np.ndarray, *,
                     n: int = 20, bb_k: float = 2.0, kc_k: float = 1.5) -> np.ndarray:
    """Bollinger bands inside Keltner channels = compression; trade the release.

    The transcript's single best result (ETH, OOS Sharpe 0.84, max DD -6.4%). Volatility
    compression is one of the few genuinely non-stationary regularities: variance clusters, so a
    quiet period really does raise the odds of a loud one -- though it says nothing about
    direction, which is why the release sign supplies it.
    """
    h, lo, c = (np.asarray(x, dtype="float64") for x in (high, low, close))
    m, s = _sma(c, n), _rolling_std(c, n)
    tr = np.maximum(h - lo, np.maximum(np.abs(h - np.roll(c, 1)), np.abs(lo - np.roll(c, 1))))
    tr[0] = h[0] - lo[0]
    atr = _sma(tr, n)
    squeezed = (m + bb_k * s) < (m + kc_k * atr)
    mom = c - _sma(c, n)
    released = ~squeezed
    return np.where(np.isnan(mom) | np.isnan(atr), 0.0,
                    np.where(released & (mom > 0), 1.0,
                             np.where(released & (mom < 0), -1.0, 0.0)))


def donchian_breakout(high: np.ndarray, low: np.ndarray, close: np.ndarray,
                      *, n: int = 20) -> np.ndarray:
    c, h, lo = (np.asarray(x, dtype="float64") for x in (close, high, low))
    pos = np.zeros(len(c))
    cur = 0.0
    for i in range(n, len(c)):
        if c[i] >= np.max(h[i - n:i]):
            cur = 1.0
        elif c[i] <= np.min(lo[i - n:i]):
            cur = -1.0
        pos[i] = cur
    return pos


def golden_cross(close: np.ndarray, *, fast: int = 50, slow: int = 200) -> np.ndarray:
    c = np.asarray(close, dtype="float64")
    f, s = _sma(c, fast), _sma(c, slow)
    return np.where(np.isnan(f) | np.isnan(s), 0.0, np.where(f > s, 1.0, -1.0))


def trend_gated_rotation(risk_close: np.ndarray, defensive_close: np.ndarray,
                         *, n: int = 200) -> np.ndarray:
    """Hold the risk asset above its own long average, the defensive asset below it.

    Returned as a position in the RISK asset; -1 encodes "in the defensive leg". The mechanism is
    not that the average predicts, it is that the two legs carry opposite regime exposure, so the
    pair harvests the regime rather than the direction. The transcript's only survivor after its
    own stress tests was this shape.
    """
    r = np.asarray(risk_close, dtype="float64")
    m = _sma(r, n)
    return np.where(np.isnan(m), 0.0, np.where(r > m, 1.0, -1.0))


def absolute_momentum(close: np.ndarray, *, lookback: int = 252) -> np.ndarray:
    """Long only when the trailing return over `lookback` is positive -- time-series momentum."""
    c = np.asarray(close, dtype="float64")
    pos = np.zeros(len(c))
    pos[lookback:] = np.where(c[lookback:] > c[:-lookback], 1.0, 0.0)
    return pos


# --------------------------------------------------------------------------------------------
# OVERLAYS -- these modify a position rather than generating one
# --------------------------------------------------------------------------------------------

def vol_target(pos: np.ndarray, close: np.ndarray, *, target_ann: float = 0.20,
               n: int = 20, ppy: float = 365.0, cap: float = 3.0) -> np.ndarray:
    """Scale an existing position toward a constant portfolio volatility.

    Named in two transcripts and it is the one overlay with a mechanical rather than predictive
    justification: it does not claim to know direction, it equalises the risk contributed per
    unit of time, which raises the geometric mean for any edge at all. Capped, because unbounded
    inverse-vol levers hardest into the quiet period immediately before a break.
    """
    c = np.asarray(close, dtype="float64")
    r = np.zeros(len(c))
    r[1:] = np.diff(c) / c[:-1]
    rv = _rolling_std(r, n) * np.sqrt(ppy)
    # Guard the DIVISOR, not the result: np.where evaluates both branches, so dividing first and
    # selecting afterwards still divides by zero on a flat tape. A dead-quiet window is exactly
    # where an inverse-vol lever wants infinite size, so this is the case that matters.
    safe = np.where(np.isnan(rv) | (rv <= 0), np.inf, rv)
    scale = np.minimum(target_ann / safe, cap)
    return np.asarray(np.nan_to_num(pos) * scale)


def regime_filter(pos: np.ndarray, close: np.ndarray, *, n: int = 20,
                  bull: float = 0.05, bear: float = -0.05) -> np.ndarray:
    """Gate an existing strategy by the market state, rather than trading the state directly.

    The "filter mode" the Markov transcript describes: longs only in a bull state, shorts only in
    a bear state, flat in chop. Keeps the strategy's own edge and removes the regime in which it
    has no business being on.
    """
    c = np.asarray(close, dtype="float64")
    p = np.nan_to_num(np.asarray(pos, dtype="float64"))
    ret_n = np.full(len(c), np.nan)
    ret_n[n:] = c[n:] / c[:-n] - 1.0
    out = np.zeros(len(c))
    for i in range(len(c)):
        if np.isnan(ret_n[i]):
            continue
        if ret_n[i] > bull:
            out[i] = max(0.0, p[i])
        elif ret_n[i] < bear:
            out[i] = min(0.0, p[i])
    return out


#: Every candidate, tagged with its measured family survival rate so the campaign can spend its
#: scarce forward slots in proportion to evidence rather than to intuition.
FAMILY_SURVIVAL = {"volume": 0.387, "mean_reversion": 0.385, "momentum": 0.274,
                   "pattern": 0.220, "trend": 0.182}

CANDIDATES: dict[str, str] = {
    "chaikin_money_flow": "volume", "volume_surge_breakout": "volume", "obv_trend": "volume",
    "zscore_reversion": "mean_reversion", "bollinger_reversion": "mean_reversion",
    "percent_b_reversion": "mean_reversion", "rsi_mean_reversion": "mean_reversion",
    "range_position_dip": "mean_reversion",
    "squeeze_momentum": "momentum", "absolute_momentum": "momentum",
    "donchian_breakout": "trend", "golden_cross": "trend", "trend_gated_rotation": "trend",
}
