"""Labels (targets).

Labels are *deliberately* forward-looking — a label at t encodes future outcomes. That is
why a label must never be registered as a feature: doing so is hindsight leakage, which the
feature leakage test rejects. Keep labels strictly on the target side of training.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from libs.features.errors import FeatureError

LABEL_PREFIX = "label_"


def forward_log_return(bars: pd.DataFrame, *, horizon: int = 1) -> pd.Series:
    """The forward log return over ``horizon`` bars (a target; look-ahead by design)."""
    if horizon < 1:
        raise FeatureError("label horizon must be >= 1")
    future_close = bars["close"].shift(-horizon)
    label = np.log(future_close / bars["close"])
    label.name = f"{LABEL_PREFIX}fwd_logret_{horizon}"
    return label


def forward_direction(bars: pd.DataFrame, *, horizon: int = 1) -> pd.Series:
    """The sign of the forward return: +1 up, -1 down, 0 flat (a classification target)."""
    label = np.sign(forward_log_return(bars, horizon=horizon))
    label.name = f"{LABEL_PREFIX}fwd_dir_{horizon}"
    return label


def triple_barrier_labels(
    close: pd.Series,
    *,
    horizon: int,
    upper: float,
    lower: float,
    vol: pd.Series | None = None,
) -> pd.Series:
    """Triple-barrier labels (López de Prado, *Advances in Financial ML* ch. 3).

    Method extracted from hudson-and-thames/mlfinlab and implemented from the book directly (the
    directive's caution: open ports of that library have known-incorrect pieces, and a subtly wrong
    labeller is exactly the leak this desk exists to catch — so this is an owned, verifiable port).

    For each bar ``t``, look forward up to ``horizon`` bars and set two horizontal barriers as
    fractional returns from ``close[t]``: a profit-take at ``+upper * w`` and a stop at
    ``-lower * w`` where ``w = vol[t]`` if a volatility series is given (barriers scale with local
    vol) else ``1.0`` (``upper``/``lower`` are then direct return widths). The label is:

      * ``+1`` if the upper barrier is touched first,
      * ``-1`` if the lower barrier is touched first,
      * ``0``  if neither is touched before the vertical (time) barrier at ``t + horizon``.

    A bar whose forward path is truncated by end-of-data *and* touched no barrier is labelled
    ``NaN`` (undetermined — never fabricate a ``0`` from an unobservable outcome). Forward-looking
    by design: a target, never a feature.

    Raises:
        FeatureError: if ``horizon < 1`` or either barrier width is non-positive.
    """
    if horizon < 1:
        raise FeatureError("label horizon must be >= 1")
    if upper <= 0.0 or lower <= 0.0:
        raise FeatureError("barrier widths (upper, lower) must be > 0")
    px = close.to_numpy(dtype="float64")
    n = len(px)
    w = vol.to_numpy(dtype="float64") if vol is not None else np.ones(n, dtype="float64")
    out = np.full(n, np.nan, dtype="float64")
    for t in range(n):
        end = min(n - 1, t + horizon)
        up_b, dn_b = upper * w[t], lower * w[t]
        touched = False
        for s in range(t + 1, end + 1):
            r = px[s] / px[t] - 1.0
            if r >= up_b:
                out[t], touched = 1.0, True
                break
            if r <= -dn_b:
                out[t], touched = -1.0, True
                break
        if not touched and (t + horizon) <= n - 1:
            out[t] = 0.0  # full path observed, no barrier hit -> genuine flat (0)
    return pd.Series(out, index=close.index, name=f"{LABEL_PREFIX}triple_barrier_{horizon}")
