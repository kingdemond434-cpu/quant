"""ALT-DATA FAMILIES -- the DIRECT and INDIRECT uses of every free-stack series.

The principal's rule (2026-09-30): every alt dataset feeds (a) DIRECT cells through new families,
(b) INDIRECT cells through conditioning, regime features and interactions on existing families,
and (c) allocation state. `family_exogenous_conditioner` already bets on a series' LEVEL being
extreme. These two add what that one cannot ask:

  alt_series_momentum   DIRECT. Attention, tone and rank are FLOW variables: what moves a market
      is their CHANGE, not their level (a publisher climbing the charts, a forum turning bearish,
      search interest spiking). The cell enters when the series' `lookback`-observation change,
      z-scored on its own history, CROSSES `threshold` -- once per crossing, not on every bar it
      stays extreme -- in the direction `side_when_up` assigns to a rising series.

  alt_conditioned       INDIRECT. An ordinary price-only family (`base_family`, `base_params`)
      whose signals are kept only while the alt series is in `regime` (high / low / mid of its
      lagged z). The un-conditioned base cell is the control arm and already sits in the docket;
      this asks whether the alt regime is where that entry pays. Base families that need an
      injected input are refused exactly as `family_exit_operated` refuses them.

THE POINT-IN-TIME JOIN is `family_exogenous_conditioner.conditioner`: the series is read on its
own `available_time` clock and held back `lag_hours` (a publication day by default) BEFORE it is
aligned, so the broker clock's UTC offset can never produce a lookahead join. Both families
return [] -- never a price-only fallback -- when the series, the column or its stamp is absent.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from mt5desk.families import Signal, _atr, _h1, get_family_func
from mt5desk.family_exogenous_conditioner import (
    DEFAULT_LAG_HOURS,
    DEFAULT_Z_WINDOW,
    MIN_OBSERVATIONS,
    conditioner,
)

#: Regimes an alt series can gate a base family on.
REGIMES: tuple[str, ...] = ("high", "low", "mid")


def _z(s: pd.Series, window: int) -> pd.Series:
    w = max(5, int(window))
    mu = s.rolling(w, min_periods=5).mean()
    sd = s.rolling(w, min_periods=5).std(ddof=0)
    return ((s - mu) / sd.replace(0.0, np.nan)).replace([np.inf, -np.inf], np.nan).dropna()


def momentum_z(source: str, signal: str, *, lookback: int = 4, z_window: int = DEFAULT_Z_WINDOW,
               lag_hours: int = DEFAULT_LAG_HOURS, root: Path | None = None
               ) -> pd.Series | None:
    """The series' `lookback`-observation change, z-scored, on its lagged availability clock."""
    raw = conditioner(source, signal, "raw", lag_hours=lag_hours, z_window=z_window, root=root)
    if raw is None or len(raw) < MIN_OBSERVATIONS:
        return None
    mom = raw - raw.shift(max(1, int(lookback)))
    z = _z(mom.dropna(), z_window)
    return z if len(z) >= 5 else None


def family_alt_series_momentum(
    df: pd.DataFrame,
    *,
    source: str = "",
    signal: str = "",
    lookback: int = 4,
    threshold: float = 1.0,
    side_when_up: int = 1,
    lag_hours: int = DEFAULT_LAG_HOURS,
    z_window: int = DEFAULT_Z_WINDOW,
    atr_n: int = 20,
    stop_atr: float = 2.0,
    rr: float = 2.0,
    ttl_bars: int = 96,
    series_root: Path | None = None,
) -> list[Signal]:
    """One signal per CROSSING of |momentum z| over `threshold`, at the first bar at or after
    the crossing became available. Rising series -> `side_when_up`; falling -> the opposite."""
    z = momentum_z(source, signal, lookback=lookback, z_window=z_window, lag_hours=lag_hours,
                   root=series_root)
    if z is None:
        return []
    d = _h1(df)
    if d.empty or len(d) <= atr_n + 1:
        return []
    thr = abs(float(threshold))
    zv = z.to_numpy()
    prev = np.concatenate([[0.0], zv[:-1]])
    up = (zv >= thr) & (prev < thr)
    dn = (zv <= -thr) & (prev > -thr)
    events = [(t, 1) for t in z.index[up]] + [(t, -1) for t in z.index[dn]]
    if not events:
        return []
    atr = _atr(d, atr_n).to_numpy()
    close = d["close"].to_numpy()
    idx = d.index
    out: list[Signal] = []
    used: set[int] = set()
    for t, direction in sorted(events):
        try:
            i = int(idx.searchsorted(t, side="left"))
        except (TypeError, ValueError):
            return []           # a series that will not align to the bar clock is UNMEASURED
        if i < atr_n or i >= len(d) - 1 or i in used:
            continue
        a = float(atr[i])
        if not np.isfinite(a) or a <= 0:
            continue
        used.add(i)
        side = int(side_when_up) * direction
        px = float(close[i])
        out.append(Signal(time=idx[i], side=side, stop=px - side * stop_atr * a,
                          target=px + side * stop_atr * a * rr, ttl_bars=ttl_bars,
                          tag="alt_series_momentum", trigger=None, wait_bars=1))
    return out


#: Families whose signals need an injected runtime input (mirrors family_exit_operated).
_UNWRAPPABLE: frozenset[str] = frozenset({
    "carry", "ensemble", "formula", "lead_lag", "style_premia", "relative_value",
    "cross_asset_residual", "pca_residual", "execution_state", "liquidity_regime",
    "orderflow_imbalance", "macro_conditional", "cot_positioning", "cot_net_fade",
    "cot_change_fade", "cot_change_momentum", "cot_comm_follow", "event_reaction",
    "cross_sectional", "discovered", "generic", "joint_genome", "alt_conditioned",
    "exit_operated",
})


def wrappable(name: str) -> bool:
    return bool(name) and name not in _UNWRAPPABLE and get_family_func(name) is not None


def family_alt_conditioned(
    df: pd.DataFrame,
    *,
    base_family: str = "",
    base_params: dict[str, Any] | None = None,
    source: str = "",
    signal: str = "",
    transform: str = "level_z",
    regime: str = "high",
    threshold: float = 1.0,
    lag_hours: int = DEFAULT_LAG_HOURS,
    z_window: int = DEFAULT_Z_WINDOW,
    series_root: Path | None = None,
) -> list[Signal]:
    """`base_family`'s own signals, kept only where the alt series is in `regime` at signal time."""
    if not wrappable(base_family) or regime not in REGIMES or not source or not signal:
        return []
    cond = conditioner(source, signal, transform, lag_hours=lag_hours, z_window=z_window,
                       root=series_root)
    if cond is None or len(cond) < MIN_OBSERVATIONS:
        return []
    fn = get_family_func(base_family)
    if fn is None:
        return []
    params = dict(base_params or {})
    for k in ("timeframe", "session"):
        params.pop(k, None)
    d = _h1(df)
    try:
        raw = fn(d, **params)
    except Exception:
        return []
    sigs = [s for s in (raw or []) if isinstance(s, Signal)]
    if not sigs:
        return []
    times = pd.DatetimeIndex([s.time for s in sigs])
    try:
        at = cond.reindex(cond.index.union(times)).ffill().reindex(times).to_numpy()
    except (TypeError, ValueError):
        return []
    thr = abs(float(threshold))
    keep: list[Signal] = []
    for s, v in zip(sigs, at, strict=True):
        if v is None or not np.isfinite(v):
            continue
        ok = (v >= thr) if regime == "high" else (v <= -thr) if regime == "low" \
            else (abs(v) < thr)
        if ok:
            keep.append(s)
    return keep
