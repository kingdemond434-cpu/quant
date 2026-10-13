"""Ehlers smoothing channels and causal support/resistance clusters, from hummingbot/quants-lab.

Source: github.com/hummingbot/quants-lab, `core/features/candles/mean_reversion_channel.py`
(`supersmoother`, `sak_smoothing`: Ehlers SuperSmoother, Gaussian and Butterworth two-pole
filters, bands at mean-range x pi) and `core/features/candles/peak_analyzer.py` (prominence peaks
clustered into price levels). Apache License 2.0, Copyright the Hummingbot Foundation; the notice
is `libs/features/LICENSE_quants-lab`. Only the research methods are taken: quants-lab's venue
connectors are crypto exchanges, which the mandate never hunts.

WHAT CHANGED IN THE PORT, AND WHY.
  * The filters are the upstream recursions written as `scipy.signal.lfilter` coefficients, so a
    10,000-bar series is one C call instead of a Python loop over `iloc`. They are IIR filters on
    past values only, and so causal as upstream.
  * The peak analyzer is NOT causal upstream: its prominence threshold is a share of the whole
    sample's high-low range, and `find_peaks` inside a window marks a peak a few bars before the
    window ends, i.e. one that later bars have not yet confirmed. Here prominence is in units of
    the PAST true range, the scan for bar t ends `confirm` bars before t (a peak is usable only
    once `confirm` later bars have failed to exceed it), and the level clustering is a 1-D gap
    rule (adjacent peaks within `merge_atr` true ranges merge) with no global fit.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.signal import find_peaks, lfilter

LENGTHS: tuple[int, ...] = (20, 60)


def _coeffs(kind: str, length: int) -> tuple[np.ndarray, np.ndarray]:
    cycle = 2.0 * np.pi / length
    if kind == "supersmoother":
        a1 = np.exp(-np.sqrt(2.0) * np.pi / length)
        c2 = 2.0 * a1 * np.cos(np.sqrt(2.0) * np.pi / length)
        c3 = -a1 * a1
        return np.array([1.0 - c2 - c3]), np.array([1.0, -c2, -c3])
    beta = 2.415 * (1.0 - np.cos(cycle))
    alpha = -beta + np.sqrt(beta * beta + 2.0 * beta)
    a1, a2 = 2.0 * (1.0 - alpha), -(1.0 - alpha) ** 2
    if kind == "gaussian":
        return np.array([alpha * alpha]), np.array([1.0, -a1, -a2])
    if kind == "butterworth":
        return alpha * alpha / 4.0 * np.array([1.0, 2.0, 1.0]), np.array([1.0, -a1, -a2])
    raise ValueError(f"unknown filter {kind!r}")


def smooth(x: pd.Series, length: int, kind: str = "supersmoother") -> pd.Series:
    """The two-pole filter of `x`, started at its first finite value (NaN before it)."""
    v = x.astype(float).to_numpy()
    out = np.full(v.size, np.nan)
    ok = np.flatnonzero(np.isfinite(v))
    if ok.size == 0:
        return pd.Series(out, index=x.index)
    start = int(ok[0])
    seg = pd.Series(v[start:]).ffill().to_numpy()
    b, a = _coeffs(kind, length)
    zi = np.zeros(max(len(a), len(b)) - 1)
    # steady state at the first value, so the filter does not ring up from zero
    y0 = seg[0]
    for _ in range(4 * length):
        _, zi = lfilter(b, a, [y0], zi=zi)
    out[start:], _ = lfilter(b, a, seg, zi=zi)
    return pd.Series(out, index=x.index)


def true_range(df: pd.DataFrame) -> pd.Series:
    h, lo, c = (df[k].astype(float) for k in ("high", "low", "close"))
    pc = c.shift(1)
    return pd.concat([h - lo, (h - pc).abs(), (lo - pc).abs()], axis=1).max(axis=1)


def channel(df: pd.DataFrame, lengths: tuple[int, ...] = LENGTHS) -> pd.DataFrame:
    """Position of the close inside each filter's channel, in mean-range x pi units (upstream's
    band scale), and the mean line's one-bar slope in the same units."""
    src = (df["high"].astype(float) + df["low"].astype(float) + df["close"].astype(float)) / 3.0
    tr = true_range(df)
    out: dict[str, pd.Series] = {}
    for n in lengths:
        rng = smooth(tr, n).replace(0.0, np.nan) * np.pi
        for kind, tag in (("supersmoother", "ss"), ("butterworth", "bw"), ("gaussian", "ga")):
            mean = smooth(src, n, kind)
            out[f"{tag}{n}_pos"] = (df["close"].astype(float) - mean) / rng
            if kind == "supersmoother":
                out[f"{tag}{n}_slope"] = mean.diff() / rng
    return pd.DataFrame(out, index=df.index)


def levels(df: pd.DataFrame, *, window: int = 240, confirm: int = 6, prominence_atr: float = 2.0,
           merge_atr: float = 0.5, step: int = 6) -> pd.DataFrame:
    """Distance from the close to the nearest confirmed resistance above and support below, in
    past-true-range units, and how many confirmed peaks built each level. Recomputed every
    `step` bars on the `window` bars that end `confirm` bars ago."""
    h = df["high"].astype(float).to_numpy()
    lo = df["low"].astype(float).to_numpy()
    c = df["close"].astype(float).to_numpy()
    atr = true_range(df).rolling(48, min_periods=24).mean().to_numpy()
    n = c.size
    res_d, sup_d, res_n, sup_n = (np.full(n, np.nan) for _ in range(4))
    held: tuple[list[tuple[float, int]], list[tuple[float, int]]] = ([], [])
    for t in range(window + confirm, n):
        a = atr[t]
        if not (np.isfinite(a) and a > 0):
            continue
        if (t - window - confirm) % step == 0 or not (held[0] or held[1]):
            end = t - confirm
            hw, lw = h[end - window:end], lo[end - window:end]
            hp, _ = find_peaks(hw, prominence=prominence_atr * a)
            lp, _ = find_peaks(-lw, prominence=prominence_atr * a)
            held = (_cluster(hw[hp], merge_atr * a), _cluster(lw[lp], merge_atr * a))
        above = [(p, k) for p, k in held[0] + held[1] if p > c[t]]
        below = [(p, k) for p, k in held[0] + held[1] if p < c[t]]
        if above:
            p, k = min(above)
            res_d[t], res_n[t] = (p - c[t]) / a, k
        if below:
            p, k = max(below)
            sup_d[t], sup_n[t] = (c[t] - p) / a, k
    return pd.DataFrame({"res_dist": res_d, "sup_dist": sup_d, "res_touches": res_n,
                         "sup_touches": sup_n}, index=df.index)


def _cluster(prices: np.ndarray, gap: float) -> list[tuple[float, int]]:
    """Adjacent sorted peaks within `gap` merge; each level is (mean price, peak count)."""
    if prices.size == 0:
        return []
    p = np.sort(prices)
    groups, cur = [], [p[0]]
    for x in p[1:]:
        if x - cur[-1] <= gap:
            cur.append(x)
        else:
            groups.append(cur)
            cur = [x]
    groups.append(cur)
    return [(float(np.mean(g)), len(g)) for g in groups]


def features(df: pd.DataFrame) -> pd.DataFrame:
    return pd.concat([channel(df), levels(df)], axis=1)
