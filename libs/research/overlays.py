"""Three overlays that modify an EXISTING signal, from the 2026-08-01 transcript batch.

Overlays rather than new signals, and that is the point. This desk has now measured, twice and by
unrelated methods, that its trend family carries real timing information on crypto
(docs/research/PERMUTATION_NULL_RESULT.md: `time_series_mom[40]` at permutation p = 0.008 and a
monkey beat rate of 0.985) and that its mean-reversion family is anti-informative. The scarce
thing is therefore no longer a signal. It is everything that turns a signal into a position:
sizing, exits, and when to stand aside. The desk has almost none of that -- every generator is an
always-in +1/-1 rule with no exit logic at all.

    volatility_target   Algovibes' vol-targeting study, and Saeed Amen's measured claim that vol
                        scaling roughly DOUBLES trend-following information ratio
    trade_dependence    neurotrader's Donchian study: only take a trade after a LOSING one, which
                        improved profit factor at EVERY lookback tested; the rule the Turtles used
    hawkes_process      neurotrader's self-exciting volatility exit -- "its main power is the exit"

NONE OF THESE IS A GATE and none is adopted on the strength of the source. Each is built here so
it can be MEASURED against the desk's own rules on the desk's own data, which is the only thing
that has ever converted a transcript into anything on this desk.

THE HONEST PRIOR, recorded before measuring so it cannot be adjusted afterwards: Algovibes'
portfolio study found that every added layer -- a regime gate, volatility-based position sizing, a
trend-strength gate, a funding gate -- made the underlying strategy WORSE, and its regime study
found a naive detector actively bled. Overlays are not free. The expected outcome for any given
one of these is that it does nothing or hurts.
"""

from __future__ import annotations

import numpy as np

#: Annualised volatility the position is scaled toward. 15% is the source's figure and is
#: deliberately far below crypto's realised ~57%, which is the entire point: the overlay is a
#: RISK NORMALISER, and on this asset class it will spend most of its time cutting exposure.
DEFAULT_TARGET_VOL = 0.15

#: Hard cap on the scale factor. Without it, a quiet stretch tells you to run 3-4x, which is not
#: a position anyone actually takes and would dominate the measurement with a few calm weeks.
DEFAULT_LEVERAGE_CAP = 1.5

_EPS = 1e-12


def realised_volatility(
    log_returns: np.ndarray, *, window: int = 20, periods_per_year: float = 365.0
) -> np.ndarray:
    """Trailing annualised volatility. NaN until a full window exists.

    TRAILING AND LAGGED BY THE CALLER. This returns the volatility computed from the window ENDING
    at bar i, which includes bar i -- so a caller sizing a position for bar i+1 must shift it.
    `volatility_target` does that shift; anything else using this function owes the same care, and
    `libs/validation/lookahead_audit` is how you check you did it.
    """
    if window < 2:
        raise ValueError(f"window must be >= 2, got {window}")
    r = np.asarray(log_returns, dtype="float64")
    out = np.full(r.size, np.nan)
    if r.size < window:
        return out
    c1 = np.cumsum(np.insert(r, 0, 0.0))
    c2 = np.cumsum(np.insert(r * r, 0, 0.0))
    s1 = c1[window:] - c1[:-window]
    s2 = c2[window:] - c2[:-window]
    var = (s2 - s1 * s1 / window) / (window - 1)
    out[window - 1:] = np.sqrt(np.maximum(var, 0.0)) * np.sqrt(periods_per_year)
    return out


def volatility_target(
    positions: np.ndarray,
    log_returns: np.ndarray,
    *,
    target_vol: float = DEFAULT_TARGET_VOL,
    window: int = 20,
    leverage_cap: float = DEFAULT_LEVERAGE_CAP,
    periods_per_year: float = 365.0,
) -> np.ndarray:
    """Scale an existing position by ``target_vol / realised_vol``, clipped to [0, cap].

    The idea is that risk, not exposure, should be the constant. A +1 position in a 20%-vol
    regime and a +1 position in an 80%-vol regime are the same instruction and wildly different
    bets, and the second one is where trend strategies take their worst losses.

    THE SCALE IS LAGGED ONE BAR. The volatility that sizes bar i is computed from the window
    ending at bar i-1, because the window ending at bar i includes bar i's own return -- which is
    exactly the off-by-one that `lookahead_audit.future_invariance` exists to catch, and it is an
    easy one to write.

    A ZERO OR UNCOMPUTABLE VOLATILITY GIVES ZERO EXPOSURE, not infinite. Dividing by a
    not-yet-warm or frozen volatility estimate would produce the largest position in the run at
    precisely the moment the desk knows least.
    """
    p = np.asarray(positions, dtype="float64")
    r = np.asarray(log_returns, dtype="float64")
    if p.size != r.size:
        raise ValueError(f"positions ({p.size}) and returns ({r.size}) must be the same length")
    if leverage_cap <= 0:
        raise ValueError(f"leverage_cap must be positive, got {leverage_cap}")

    vol = realised_volatility(r, window=window, periods_per_year=periods_per_year)
    lagged = np.full(vol.size, np.nan)
    lagged[1:] = vol[:-1]                       # size bar i from the window ending at i-1

    with np.errstate(divide="ignore", invalid="ignore"):
        scale = np.where(np.isfinite(lagged) & (lagged > _EPS), target_vol / lagged, 0.0)
    scale = np.clip(scale, 0.0, leverage_cap)
    return p * scale


def runs_test_z(signs: np.ndarray) -> float:
    """Wald-Wolfowitz runs test. POSITIVE z means losers tend to be followed by winners.

    A run is a maximal streak of one sign. Fewer runs than chance means streaks (winners cluster);
    MORE runs than chance means alternation, which in trade-outcome terms is exactly the Turtle
    rule's premise: take the trade after a loss, skip the one after a win.

    The source measured z = 2.7 on hourly Donchian and found z positive across the whole lookback
    range -- consistent, not a single lucky parameter.
    """
    s = np.asarray(signs, dtype="float64")
    s = s[np.isfinite(s) & (s != 0)]
    n_pos = int(np.sum(s > 0))
    n_neg = int(np.sum(s < 0))
    n = n_pos + n_neg
    if n_pos < 2 or n_neg < 2:
        return float("nan")
    runs = 1 + int(np.sum(s[1:] != s[:-1]))
    mean = 2.0 * n_pos * n_neg / n + 1.0
    var = (2.0 * n_pos * n_neg * (2.0 * n_pos * n_neg - n)) / (n * n * (n - 1.0))
    if var <= _EPS:
        return float("nan")
    return float((runs - mean) / np.sqrt(var))


def trade_outcomes(positions: np.ndarray, log_returns: np.ndarray) -> list[dict[str, float]]:
    """Split a position series into discrete trades with their realised returns.

    A trade runs from a change in position to the next change. Needed because trade dependence is
    a statement about TRADES, not bars -- and a bar-level autocorrelation would answer a different
    question and give a different number.
    """
    p = np.asarray(positions, dtype="float64")
    r = np.asarray(log_returns, dtype="float64")
    if p.size != r.size:
        raise ValueError("positions and returns must be the same length")
    out: list[dict[str, float]] = []
    i = 0
    n = p.size
    while i < n:
        if p[i] == 0.0:
            i += 1
            continue
        j = i
        while j + 1 < n and p[j + 1] == p[i]:
            j += 1
        # Return accrues on bars i+1..j+1 for a position held from i, lag-1.
        lo, hi = i + 1, min(j + 2, n)
        pnl = float(p[i] * np.sum(r[lo:hi])) if hi > lo else 0.0
        out.append({"start": float(i), "end": float(j), "direction": float(p[i]), "pnl": pnl})
        i = j + 1
    return out


def trade_dependence_filter(
    positions: np.ndarray, log_returns: np.ndarray, *, take_after: str = "loss"
) -> np.ndarray:
    """Zero out trades that do not follow the requested prior outcome.

    ``take_after="loss"`` is the Turtle rule the source tested: skip the trade after a winner,
    take the one after a loser. ``"win"`` is its inverse and is included because the source
    measured BOTH -- the inverse being unprofitable at almost every lookback is what makes the
    main result a finding rather than a coin flip.

    THE FIRST TRADE IS ALWAYS TAKEN. There is no prior outcome to condition on, and dropping it
    would silently shorten every backtest by one trade in a way that depends on the parameter.
    """
    if take_after not in ("loss", "win"):
        raise ValueError(f"take_after must be 'loss' or 'win', got {take_after!r}")
    p = np.asarray(positions, dtype="float64")
    trades = trade_outcomes(p, log_returns)
    out = np.zeros_like(p)
    prev: float | None = None
    for t in trades:
        lo, hi = int(t["start"]), int(t["end"])
        keep = prev is None or ((prev < 0) if take_after == "loss" else (prev > 0))
        if keep:
            out[lo:hi + 1] = t["direction"]
        prev = t["pnl"]
    return out


def hawkes_process(values: np.ndarray, *, kappa: float = 0.1) -> np.ndarray:
    """Self-exciting decay: ``out[i] = out[i-1] * exp(-kappa) + x[i]``, scaled by kappa.

    Volatility and volume are self-exciting -- a large value makes the next large value more
    likely -- and this is the standard cheap way to express that. It rises fast when the input
    spikes and decays slowly, which is what makes it useful as an EXIT: the trend is over when
    the excitation has decayed, not when price crosses a line.

    Smaller kappa means slower decay and more lag.
    """
    if kappa <= 0:
        raise ValueError(f"kappa must be positive, got {kappa}")
    x = np.asarray(values, dtype="float64")
    alpha = float(np.exp(-kappa))
    out = np.full(x.size, np.nan)
    prev = np.nan
    for i, v in enumerate(x):
        if not np.isfinite(v):
            continue
        prev = v if not np.isfinite(prev) else prev * alpha + v
        out[i] = prev * kappa
    return out


def normalised_range(
    high: np.ndarray, low: np.ndarray, close: np.ndarray, *, atr_window: int = 336
) -> np.ndarray:
    """(log high - log low) / ATR. The self-exciting input the Hawkes exit is built on.

    Normalised by a LONG trailing ATR so the series is comparable across volatility regimes --
    without that the Hawkes output would just track the volatility level and its quantile
    thresholds would mean something different in every year.
    """
    h, low_, c = (np.asarray(x, dtype="float64") for x in (high, low, close))
    if not h.size == low_.size == c.size:
        raise ValueError("high/low/close must be the same length")
    if np.any(h <= 0) or np.any(low_ <= 0) or np.any(c <= 0):
        raise ValueError("non-positive prices -- the log range is undefined")
    lh, ll = np.log(h), np.log(low_)
    rng_ = lh - ll
    out = np.full(rng_.size, np.nan)
    if rng_.size < atr_window:
        return out
    cs = np.cumsum(np.insert(rng_, 0, 0.0))
    atr = (cs[atr_window:] - cs[:-atr_window]) / atr_window
    denom = atr[:-1]                                  # lag one bar: ATR through i-1 sizes bar i
    vals = rng_[atr_window:]
    out[atr_window:] = np.where(denom > _EPS, vals / denom, np.nan)
    return out
