"""Volatility regime with ASYMMETRIC enter/exit thresholds, so the state cannot flicker.

Reverse-engineered from a public MQL5 product page (MQL5_PRODUCT_193655, 2026-09-01) which
discloses the whole rule family. A ROUTER, NOT AN ALPHA: it emits a state, never a trade.

THE INCREMENTAL CLAIM IS THE ASYMMETRY, and it is the only thing worth testing here. Percentile-
ranked volatility is not new and this desk already has thresholded versions; what is new is that
ENTERING high volatility and LEAVING it use different cutoffs, so a series hovering at the
boundary does not toggle the router on every bar. The dead band between the two thresholds
preserves whatever state was already held.

THE ABLATION IS THE POINT. `fixed` and `persistence` are implemented alongside `hysteresis`
precisely so the comparison is possible: a fixed cutoff, an N-consecutive-bar confirmation, and
the asymmetric band, on identical data. If hysteresis merely reduces state changes without
improving downstream net expectancy after the turnover it saves, it is not worth having -- fewer
switches is a cost claim, not a value claim.

Percentiles use PRIOR observations only. The current bar's ATR is ranked against the window that
ended before it, never against a window containing itself.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

__all__ = ["HIGH", "LOW", "percentile_rank", "regime_series"]

LOW, HIGH = "low_vol", "high_vol"


def percentile_rank(atr: pd.Series, history: int = 250) -> pd.Series:
    """Share of the PRIOR `history` ATR observations below each bar's ATR, in [0, 100].

    STRICTLY PRIOR. `rolling(...).rank()` would include the current observation in its own
    reference window, which inflates every rank and shifts both thresholds by a bar's worth of
    information the desk would not have had.
    """
    prior = atr.shift(1)
    return prior.rolling(history, min_periods=max(30, history // 5)).apply(
        lambda w: float((w < w[-1]).mean() * 100.0) if len(w) else np.nan, raw=True
    ).combine_first(pd.Series(np.nan, index=atr.index))


def regime_series(atr: pd.Series, *, mode: str = "hysteresis", history: int = 250,
                  enter_high: float = 70.0, exit_high: float = 45.0,
                  fixed_threshold: float = 70.0, persistence: int = 3,
                  slope_bars: int = 5) -> pd.DataFrame:
    """Per-bar volatility state. `mode` selects the classifier being tested.

        hysteresis   enter above `enter_high`, leave below `exit_high`, hold in between
        fixed        a single cutoff at `fixed_threshold` -- the thing hysteresis must beat
        persistence  a single cutoff confirmed by `persistence` consecutive bars

    Returns `rank`, `level` (low_vol/high_vol), `rising`, and `state` (level + direction), plus
    `switch` so the turnover each classifier costs is measurable rather than argued about.
    """
    if mode not in ("hysteresis", "fixed", "persistence"):
        raise ValueError(f"unknown mode {mode!r}")
    rank = percentile_rank(atr, history)
    r = rank.to_numpy()
    level = np.empty(len(r), dtype=object)
    cur = LOW
    run = 0
    for i in range(len(r)):
        v = r[i]
        if np.isnan(v):
            level[i] = cur
            continue
        if mode == "hysteresis":
            if cur == LOW and v > enter_high:
                cur = HIGH
            elif cur == HIGH and v < exit_high:
                cur = LOW
        elif mode == "fixed":
            cur = HIGH if v > fixed_threshold else LOW
        else:
            want = HIGH if v > fixed_threshold else LOW
            run = run + 1 if (i and level[i - 1] is not None and want != cur) else (
                1 if want != cur else 0)
            if want != cur and run >= persistence:
                cur, run = want, 0
        level[i] = cur

    # Direction of volatility, not of price: is this regime building or decaying.
    rising = (atr > atr.shift(slope_bars)).to_numpy()
    lvl = pd.Series(level, index=atr.index, dtype=object)
    return pd.DataFrame({
        "rank": rank,
        "level": lvl,
        "rising": rising,
        "state": lvl.astype(str) + np.where(rising, "_rising", "_falling"),
        "switch": lvl.ne(lvl.shift(1)).fillna(False),
    }, index=atr.index)
