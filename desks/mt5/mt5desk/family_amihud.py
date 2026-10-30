"""AMIHUD IMPACT PER TICK -- how far the price moves per unit of activity, against its own hour.

THE MEASURE. Amihud (2002) illiquidity is |return| / volume: the price concession one unit of
trading buys. This venue has no traded volume, but every H1 bar carries `tick_volume`, the count
of quote updates -- the activity a liquidity provider actually responds to. So the per-bar measure
is |log return| / tick_volume, and because activity has a strong weekly rhythm (the Asian lull is
not the London open) it is NORMALISED BY HOUR OF THE WEEK: the log of the bar's impact minus the
median log impact over the PRIOR `norm_weeks` occurrences of the same hour of the week. Strictly
trailing -- the bar being scored never enters its own baseline.

TWO CLAIMS, both economic statements written down before any data was read:

  premium         a persistently HIGH trailing impact (the market is thin relative to its own
                  hour) predicts a HIGHER forward return, a persistently low one a lower return:
                  holders demand compensation to carry a position they cannot exit cheaply
                  (Amihud 2002; Amihud & Mendelson 1986). Long when the `window_bars` mean of the
                  normalised impact is in the top `band` of its own trailing history, short in
                  the bottom. Payer: the liquidity demander (`axis_registry` range_reversion
                  price_only market -> overextended_liquidity_taker is the nearest named payer).
  shock_reversal  ONE bar whose impact per tick is `spike_mult` times its hour's norm AND that
                  moved at least `min_move_atr` ATR: the move happened in a thin book, so it was a
                  liquidity concession, not information, and it fades as depth returns. Fades the
                  bar's direction for `hold_bars`.

WHY THIS IS NOT `spread_state`, `volume_spike` OR F1 (`family_idio_volume`, alt-seat-cells).
Those condition on the SPREAD or on the COUNT of ticks (high activity). This conditions on PRICE
MOVED PER TICK -- a thin market moves far on little activity, which is the opposite corner of the
activity/impact plane from a volume spike. A spread can be tight while the impact per tick is
large (a one-sided sweep through a quoted-but-thin book).

SHARE CFDs. This time-series family is for the hypothesis lane (indices and the rest). A share CFD
reaches the same two claims ONLY through the class book
`families_cross_sectional.family_cross_sectional_class_illiquidity` (ranked within the `equity`
peer class, `universe_policy.CROSS_SECTIONAL_FAMILIES`), never through this family -- the two-lane
door (`proposer_common._lane_filtered`) refuses it here.

REFUSES without `tick_volume`: an impact measure with no activity column is a volatility family
wearing a better name.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from mt5desk.families import Signal, _atr, _h1

MODES = ("premium", "shock_reversal")

#: Hours in a week -- the normalisation key's cardinality.
_HOW = 168


def normalised_impact(frame: pd.DataFrame, *, norm_weeks: int = 12) -> pd.Series | None:
    """log(|log return| / tick_volume) minus the median of the same quantity over the PRIOR
    `norm_weeks` occurrences of the bar's hour of the week. NaN where undefined; None when the
    frame carries no usable `tick_volume`. Strictly trailing."""
    if frame is None or "tick_volume" not in frame.columns or "close" not in frame.columns:
        return None
    close = pd.to_numeric(frame["close"], errors="coerce").astype(float)
    vol = pd.to_numeric(frame["tick_volume"], errors="coerce").astype(float)
    if not np.isfinite(vol.to_numpy()).any() or float(np.nanmax(vol.to_numpy())) <= 0:
        return None
    with np.errstate(divide="ignore", invalid="ignore"):
        r = np.log(close / close.shift(1)).abs()
        imp = r / vol.where(vol > 0)
        log_imp = np.log(imp.where(imp > 0))
    idx = pd.DatetimeIndex(frame.index)
    how = pd.Series(idx.dayofweek * 24 + idx.hour, index=frame.index)
    weeks = max(2, int(norm_weeks))
    base = log_imp.groupby(how.to_numpy()).transform(
        lambda s: s.shift(1).rolling(weeks, min_periods=max(2, weeks // 2)).median())
    out = log_imp - base
    return out.replace([np.inf, -np.inf], np.nan)


def family_amihud_illiquidity(
    df: pd.DataFrame,
    *,
    mode: str = "premium",
    window_bars: int = 120,
    norm_weeks: int = 12,
    rank_bars: int = 2000,
    band: float = 0.2,
    spike_mult: float = 3.0,
    min_move_atr: float = 0.5,
    hold_bars: int = 24,
    atr_n: int = 20,
    stop_atr: float = 2.0,
    rr: float = 1.5,
) -> list[Signal]:
    """`premium`: long while the trailing normalised impact is in its own top `band`, short in
    the bottom. `shock_reversal`: fade a bar that moved >= `min_move_atr` ATR on an impact per
    tick >= `spike_mult` x its hour-of-week norm. One position per `hold_bars`."""
    if mode not in MODES or not 0.0 < float(band) < 0.5 or int(hold_bars) < 1:
        return []
    d = _h1(df)
    if len(d) < max(int(window_bars), atr_n) * 3:
        return []
    imp = normalised_impact(d, norm_weeks=norm_weeks)
    if imp is None:
        return []
    close = d["close"].astype(float)
    atr = _atr(d, atr_n).to_numpy()
    px_a = close.to_numpy()
    ret = close.diff().to_numpy()
    side_at = np.zeros(len(d), dtype="int64")
    if mode == "premium":
        level = imp.rolling(int(window_bars), min_periods=int(window_bars) // 2).mean()
        prior = level.shift(1)
        rb = max(int(window_bars) * 2, int(rank_bars))
        hi = prior.rolling(rb, min_periods=rb // 2).quantile(1.0 - float(band))
        lo = prior.rolling(rb, min_periods=rb // 2).quantile(float(band))
        lv, h, lw = level.to_numpy(), hi.to_numpy(), lo.to_numpy()
        ok = np.isfinite(lv) & np.isfinite(h) & np.isfinite(lw)
        side_at[ok & (lv >= h)] = 1
        side_at[ok & (lv <= lw)] = -1
    else:
        if float(spike_mult) <= 1.0:
            return []
        thr = float(np.log(float(spike_mult)))
        iv = imp.to_numpy()
        with np.errstate(invalid="ignore"):
            big = np.isfinite(iv) & (iv >= thr) & np.isfinite(ret) & np.isfinite(atr) & (
                np.abs(ret) >= float(min_move_atr) * atr)
        side_at[big & (ret > 0)] = -1
        side_at[big & (ret < 0)] = 1
    signals: list[Signal] = []
    last = -10 ** 9
    idx = d.index
    for i in np.flatnonzero(side_at):
        i = int(i)
        if i - last < int(hold_bars) or i >= len(d) - 1:
            continue
        a = float(atr[i])
        if not np.isfinite(a) or a <= 0:
            continue
        s = int(side_at[i])
        px = float(px_a[i])
        signals.append(Signal(time=idx[i], side=s, stop=px - s * stop_atr * a,
                              target=px + s * stop_atr * a * rr, ttl_bars=int(hold_bars),
                              tag=f"amihud:{mode}", trigger=None, wait_bars=1))
        last = i
    return signals
