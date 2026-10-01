"""intelligent-trading-bot's feature generators and top/bottom labeler, ported for the model search.

Source: github.com/asavinov/intelligent-trading-bot, `common/gen_features_rolling_agg.py`,
`common/gen_features.py` (`fmax_fn`, `lsbm_fn`) and `common/gen_labels_topbot.py`, by Alexandr
Savinov. MIT License; the upstream notice (which names no copyright holder) is kept verbatim in
`libs/features/LICENSE_intelligent-trading-bot`.

WHAT CHANGED IN THE PORT, AND WHY.
  * The FEATURES are the upstream functions with scipy dropped (the slope is the closed-form OLS
    slope, identical to `stats.linregress`) and a zero-area window returning NaN instead of
    dividing by zero. Every one is a PAST window that includes the current bar, as upstream.
  * The LABELER is bounded. Upstream `find_all_extremums` searches the whole series, so a bar's
    top/bottom label can depend on prices arbitrarily far ahead; used as a walk-forward target it
    leaks across the fold boundary by an unbounded amount. Here a bar is a top when it is within
    `tolerance` of the highest close in [t - h, t + h] and the close falls at least `level` below
    that high on BOTH sides of it inside the window -- ITB's level/tolerance definition, confined
    to the same `h` bars of future the sign target already uses. `level` and `tolerance` are in
    units of the PAST volatility of an h-bar move, so one setting reads alike on EURUSD and on
    XAUUSD.

Labels here are targets, never features (`libs/features/labels.py`).
"""

from __future__ import annotations

import itertools

import numpy as np
import pandas as pd

#: Windows (H1 bars) the ITB representation aggregates over: half a day and two days.
WINDOWS: tuple[int, ...] = (12, 48)


def area_fn(x: np.ndarray) -> float:
    """Share of the window's area above the NEWEST value, scaled to [-1, +1] (upstream, past)."""
    d = x - x[-1]
    b = float(np.nansum(np.abs(d)))
    if b <= 0:
        return float("nan")
    return 2.0 * ((b + float(np.nansum(d))) / 2.0) / b - 1.0


def slope_fn(x: np.ndarray) -> float:
    """OLS slope of the window against its bar index (upstream `stats.linregress` slope)."""
    ok = np.isfinite(x)
    if int(ok.sum()) < 2:
        return float("nan")
    t = np.arange(x.size, dtype=float)[ok]
    y = x[ok]
    tc = t - t.mean()
    den = float((tc * tc).sum())
    return float((tc * (y - y.mean())).sum() / den) if den > 0 else float("nan")


def fmax_fn(x: np.ndarray) -> float:
    """Where in the window its maximum sits, 0 = oldest bar, near 1 = the current bar."""
    return float(np.argmax(x)) / x.size if x.size else float("nan")


def lsbm_fn(x: np.ndarray) -> float:
    """Longest consecutive run of values below the window mean (tsfresh's
    longest_strike_below_mean), as a fraction of the window."""
    if x.size == 0:
        return float("nan")
    below = x < np.mean(x)
    runs = [len(list(g)) for v, g in itertools.groupby(below) if v]
    return float(max(runs, default=0)) / x.size


def _roll(s: pd.Series, w: int, fn: object) -> pd.Series:
    return s.rolling(w, min_periods=max(1, w // 2)).apply(fn, raw=True)


def features(df: pd.DataFrame, windows: tuple[int, ...] = WINDOWS) -> pd.DataFrame:
    """ITB's rolling-aggregation feature set on H1 bars, every column a past window."""
    c = df["close"].astype(float)
    lc = np.log(c)
    ret = lc.diff()
    vol = ret.rolling(48, min_periods=24).std().replace(0.0, np.nan)
    tv = (df["tick_volume"].astype(float) if "tick_volume" in df.columns
          else pd.Series(1.0, index=df.index))
    out: dict[str, pd.Series] = {}
    for w in windows:
        mp = max(1, w // 2)
        out[f"area_{w}"] = _roll(c, w, area_fn)
        out[f"trend_{w}"] = _roll(lc, w, slope_fn) / vol
        out[f"mean_rel_{w}"] = (c.rolling(w, min_periods=mp).mean() - c) / c
        vw = (c * tv).rolling(w, min_periods=mp).sum() / tv.rolling(w, min_periods=mp).sum()
        out[f"vwmean_rel_{w}"] = (vw - c) / c
    w = max(windows)
    out[f"fmax_{w}"] = _roll(c, w, fmax_fn)
    out[f"lsbm_{w}"] = _roll(c, w, lsbm_fn)
    return pd.DataFrame(out, index=df.index)


def extremum_labels(close: pd.Series, *, is_max: bool, horizon: int, level_k: float = 1.0,
                    tolerance_k: float = 0.25, vol_window: int = 240) -> pd.Series:
    """1.0 where the bar is a top (or bottom) in ITB's level/tolerance sense within +-`horizon`
    bars, 0.0 where it is not, NaN where the window or the past volatility is incomplete."""
    lc = np.log(close.astype(float))
    v = lc.to_numpy()
    n = v.size
    sd = (lc.diff(horizon).rolling(vol_window, min_periods=vol_window // 2).std()).to_numpy()
    out = np.full(n, np.nan)
    sgn = 1.0 if is_max else -1.0
    for i in range(horizon, n - horizon):
        s = sd[i]
        if not (np.isfinite(s) and s > 0):
            continue
        win = sgn * v[i - horizon:i + horizon + 1]
        if not np.isfinite(win).all():
            continue
        j = int(np.argmax(win))
        peak = float(win[j])
        left, right = win[:j], win[j + 1:]
        near = sgn * v[i] >= peak - tolerance_k * s
        deep = (left.size > 0 and right.size > 0
                and peak - float(left.min()) >= level_k * s
                and peak - float(right.min()) >= level_k * s)
        out[i] = 1.0 if (near and deep) else 0.0
    return pd.Series(out, index=close.index,
                     name=f"label_{'top' if is_max else 'bot'}_{horizon}")
