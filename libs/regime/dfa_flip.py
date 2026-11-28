"""Hurst/DFA regime-flip state: a rolling DFA exponent per symbol and dated flips across 0.5.

DETRENDED FLUCTUATION ANALYSIS (Peng et al. 1994). Integrate the demeaned return series into a
profile, cut it into boxes of size s, remove a least-squares line from each box, and measure the
residual RMS F(s). F(s) ~ s^alpha. alpha ~ 0.5 is a random walk in returns; alpha > 0.5 means
returns persist (TRENDING); alpha < 0.5 means they anti-persist (MEAN-REVERTING). DFA is used
rather than rescaled-range Hurst because the box detrending removes local drifts that R/S reads
as persistence.

THE SAMPLING IS DAILY, ON PURPOSE. The desk's own finding (improvement_inbox 2026-08-12, Nuclear
Phynance 161299): variance-ratio and Hurst instruments manufacture phantom mean reversion on
last-traded prices sampled below ~15 minutes -- bid/ask bounce reads as anti-persistence. Daily
closes from the held H1 bars sit far above that floor, and they are also the clock
`family_regime_transition` already reads its hazard on.

HYSTERESIS, so a series hovering at 0.5 cannot emit a flip every day. The state becomes TRENDING
only when alpha reaches `upper` and MEAN-REVERTING only when it reaches `lower`; inside the band
the held state stands. The first exit from the band SETS the state and is not a flip -- a flip is
a change of a state that was already held.

CLOSED BARS ONLY. Every value is a function of the daily closes up to and including that day and
nothing after it, and each is stamped with `asof`, the timestamp of the last bar of the day that
made it. A consumer may act strictly after `asof`. `daily_closes` can drop the final day of a
frame (`drop_last=True`) because the newest day of a live file may still be forming.

Pure numpy/pandas. No I/O, no fetching: the caller hands in bars the desk already holds.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

__all__ = ["DEFAULT_LOWER", "DEFAULT_SCALES", "DEFAULT_UPPER", "DEFAULT_WINDOW", "MEAN_REVERTING",
           "TO_REVERTING", "TO_TRENDING", "TRENDING", "daily_closes", "dfa_exponent", "dfa_path",
           "flip_events", "flip_events_from_bars", "state_path"]

TRENDING, MEAN_REVERTING = "trending", "mean_reverting"
TO_TRENDING, TO_REVERTING = "to_trending", "to_reverting"

#: Daily returns per DFA estimate: about half a trading year, enough boxes at the top scale.
DEFAULT_WINDOW = 120
#: Box sizes in days. The top scale keeps at least four boxes inside the window.
DEFAULT_SCALES: tuple[int, ...] = (4, 6, 8, 12, 16, 24, 30)
#: The hysteresis band around 0.5.
DEFAULT_UPPER, DEFAULT_LOWER = 0.55, 0.45


def daily_closes(bars: pd.DataFrame, *, drop_last: bool = False) -> pd.DataFrame:
    """One row per calendar day: that day's last close and the timestamp of its last bar.

    `drop_last` removes the newest day, which in a live file may still be forming.
    """
    if bars is None or bars.empty or "close" not in bars.columns:
        return pd.DataFrame(columns=["close", "asof"])
    c = bars["close"].astype(float)
    idx = pd.DatetimeIndex(c.index)
    days = idx.date
    out = pd.DataFrame({"close": c.groupby(days).last(),
                        "asof": pd.Series(idx, index=idx).groupby(days).last()})
    out = out[np.isfinite(out["close"]) & (out["close"] > 0)]
    if drop_last and len(out):
        out = out.iloc[:-1]
    return out


def dfa_exponent(returns: np.ndarray, scales: tuple[int, ...] = DEFAULT_SCALES) -> float:
    """DFA-1 exponent of a return series; NaN when there is too little to fit a slope."""
    x = np.asarray(returns, dtype=float)
    x = x[np.isfinite(x)]
    n = x.size
    if n < 16 or float(np.std(x)) <= 0:
        return float("nan")
    y = np.cumsum(x - x.mean())
    log_s: list[float] = []
    log_f: list[float] = []
    for s in scales:
        boxes = n // s
        if s < 4 or boxes < 4:
            continue
        seg = y[: boxes * s].reshape(boxes, s)
        t = np.arange(s, dtype=float)
        tc = t - t.mean()
        slope = (seg - seg.mean(axis=1, keepdims=True)) @ tc / float(tc @ tc)
        fit = seg.mean(axis=1, keepdims=True) + np.outer(slope, tc)
        f = float(np.sqrt(np.mean((seg - fit) ** 2)))
        if f > 0 and np.isfinite(f):
            log_s.append(np.log(s))
            log_f.append(np.log(f))
    if len(log_s) < 3:
        return float("nan")
    return float(np.polyfit(log_s, log_f, 1)[0])


def dfa_path(closes: pd.Series, *, window: int = DEFAULT_WINDOW,
             scales: tuple[int, ...] = DEFAULT_SCALES) -> pd.Series:
    """Rolling DFA exponent: row t uses the `window` log returns ending at close t, never later."""
    c = closes.astype(float)
    r = np.diff(np.log(c.to_numpy()))
    out = np.full(c.size, np.nan)
    for t in range(window, c.size):
        out[t] = dfa_exponent(r[t - window:t], scales)
    return pd.Series(out, index=c.index, name="dfa_alpha")


def state_path(alpha: pd.Series, *, upper: float = DEFAULT_UPPER,
               lower: float = DEFAULT_LOWER) -> pd.Series:
    """The held regime per row under hysteresis; None until alpha first leaves the band."""
    if not lower < 0.5 < upper:
        raise ValueError("the hysteresis band must straddle 0.5")
    state: str | None = None
    out: list[str | None] = []
    for a in alpha.to_numpy(dtype=float):
        if np.isfinite(a):
            if a >= upper:
                state = TRENDING
            elif a <= lower:
                state = MEAN_REVERTING
        out.append(state)
    return pd.Series(out, index=alpha.index, name="dfa_state", dtype=object)


def flip_events(alpha: pd.Series, asof: pd.Series | None = None, *,
                upper: float = DEFAULT_UPPER, lower: float = DEFAULT_LOWER) -> list[dict[str, Any]]:
    """Dated flips: each row where the held state CHANGES (never its first setting)."""
    states = state_path(alpha, upper=upper, lower=lower)
    events: list[dict[str, Any]] = []
    prev: str | None = None
    for day, st in states.items():
        if st is not None and prev is not None and st != prev:
            stamp = asof.get(day) if asof is not None else day
            events.append({
                "day": str(day),
                "asof": pd.Timestamp(stamp).isoformat(),
                "direction": TO_TRENDING if st == TRENDING else TO_REVERTING,
                "from": prev, "to": st,
                "alpha": round(float(alpha.get(day)), 4),
            })
        if st is not None:
            prev = st
    return events


def flip_events_from_bars(bars: pd.DataFrame, *, window: int = DEFAULT_WINDOW,
                          scales: tuple[int, ...] = DEFAULT_SCALES, upper: float = DEFAULT_UPPER,
                          lower: float = DEFAULT_LOWER, drop_last: bool = False,
                          ) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """(daily frame with close, asof, dfa_alpha, dfa_state; flip events) from intraday bars."""
    daily = daily_closes(bars, drop_last=drop_last)
    if len(daily) <= window:
        daily = daily.assign(dfa_alpha=np.nan, dfa_state=None)
        return daily, []
    alpha = dfa_path(daily["close"], window=window, scales=scales)
    daily = daily.assign(dfa_alpha=alpha, dfa_state=state_path(alpha, upper=upper, lower=lower))
    return daily, flip_events(alpha, daily["asof"], upper=upper, lower=lower)
