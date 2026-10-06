"""IMPLIED-VOL FAMILIES -- an MT5 underlying conditioned on the options market's own state.

WHY THESE EXIST (completion audit 2026-10-06, repair rank 2). `options_implied` was one of six
empty alpha clusters, and `research/empty_cluster_forcer` filed it UNREACHABLE BY VENUE on the
grounds that Fusion quotes no options. That conclusion was right about the venue and wrong about
the cluster: the cluster's payer is "dealers who are short gamma and must hedge into the move,
and the risk premium in implied against realised volatility" (`libs/research/alpha_clusters`),
and the UNDERLYING of those options -- XAUUSD, US500, NAS100, US30, EURUSD, XTIUSD -- is on this
account. A trade on the underlying CONDITIONED on the implied state is not an options trade and
needs no options venue. What it needs is the implied series, point-in-time, and
`recorders/vol_archive.py` has been archiving exactly that (CBOE GVZ/OVX/VIX/VXN/VXD/EVZ and the
VIX 9D/30D/3M/6M curve) since 2026-09-05.

TWO FAMILIES, the same DIRECT / INDIRECT split `family_alt_series` uses:

  implied_vol_state        DIRECT. Enter on the bar the implied state BECOMES true -- IV in the
      top or bottom of its own year, the variance risk premium (IV minus THIS broker's realised
      vol) changing sign, a five-day IV spike or crush, the VIX curve inverting -- once per
      episode, in `direction`. The bet is the payer's forced hedge, not a price pattern.

  implied_vol_conditioned  INDIRECT. A price-only base family on the same instrument, its own
      signals kept only while the implied state holds. The un-conditioned base cell is the
      control arm and already sits in the docket; this asks whether the implied state is where
      that entry pays.

THE SERIES each reads is `data/lake/series/oi_<SYMBOL>.parquet`, written hourly by
`research/options_implied.py` with an `available_time` column that is ALREADY conservative: the
CBOE close for date D is stamped knowable at D+1 00:00 UTC (`libs/data/pit_stamp`'s daily lag)
plus `world_model.CLOCK_PAD_H`. The bar index is broker time under a UTC label (+2 winter, +3
summer, `libs/research/bar_clock`), so a UTC stamp reindexed straight onto it lands up to three
hours EARLY; `lag_hours` (default `MAX_BROKER_OFFSET_H`) holds the value back by that offset
BEFORE the forward fill, the same rule `family_exogenous_conditioner` enforces for its packs.

NOTHING HERE PROMOTES. These are hypotheses with exactly the privilege every other family has,
which is none: the sealed gauntlet builds them through its ordinary `fn(h1, **params)` call and
the ten gates decide. Both refuse -- return [] -- without the series, the column, the stamp or
enough observations; they never fall back to price.
"""
from __future__ import annotations

import operator
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from mt5desk.families import Signal, _atr, _h1, get_family_func

# `wrappable` refuses base families needing an injected runtime input the gauntlet's
# `fn(h1, **params)` call does not carry -- the one list `family_alt_series` keeps.
from mt5desk.family_alt_series import wrappable
from mt5desk.family_exogenous_conditioner import SERIES_DIR

#: The broker clock's largest offset from UTC (summer, UTC+3). A UTC `available_time` must be
#: held back at least this far before it is aligned to a broker-labelled bar, or it is lookahead.
MAX_BROKER_OFFSET_H = 3

#: The comparison a condition applies to the feature. Named, never eval'd.
OPS: dict[str, Callable[[Any, Any], Any]] = {"ge": operator.ge, "le": operator.le,
                                             "gt": operator.gt, "lt": operator.lt}

#: The feature columns `research/options_implied.py` publishes. A cell naming anything else is
#: refused rather than read, so a renamed column cannot silently become an absent condition.
FEATURES: tuple[str, ...] = ("iv_level", "iv_pct_1y", "iv_chg_1d", "iv_chg_5d", "iv_chg_5d_z",
                             "term_slope_short", "term_slope_long", "term_inverted",
                             "rv_21d", "vrp", "vrp_pct_1y")

#: Feature observations needed before a family will emit anything. Below it: UNMEASURED.
MIN_OBSERVATIONS = 60

def series_path(source: str, root: Path | None = None) -> Path | None:
    """`oi_<SYMBOL>` -> its parquet (or csv), or None. Absence is UNMEASURED and emits nothing."""
    if not source or "/" in str(source) or "\\" in str(source) or ".." in str(source):
        return None
    base = root or SERIES_DIR
    for suffix in (".parquet", ".csv"):
        p = base / f"{source}{suffix}"
        if p.exists():
            return p
    return None


def feature_series(source: str, feature: str, *, lag_hours: int = MAX_BROKER_OFFSET_H,
                   root: Path | None = None) -> pd.Series | None:
    """The feature on its own `available_time` clock, held back `lag_hours`. None if unusable."""
    if feature not in FEATURES:
        return None
    path = series_path(source, root)
    if path is None:
        return None
    try:
        df = pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)
    except Exception:
        return None
    if df is None or df.empty or feature not in df.columns or "available_time" not in df.columns:
        return None             # no PIT stamp means no honest join; never guess one
    stamp = pd.to_datetime(df["available_time"], errors="coerce", utc=True)
    value = pd.to_numeric(df[feature], errors="coerce")
    s = pd.Series(value.to_numpy(dtype=float), index=stamp)
    s = s[s.index.notna()].dropna()
    if s.empty:
        return None
    s = s.sort_index()
    s = s[~s.index.duplicated(keep="last")]
    s = s.replace([np.inf, -np.inf], np.nan).dropna()
    if len(s) < MIN_OBSERVATIONS:
        return None
    return s.shift(freq=pd.Timedelta(hours=max(MAX_BROKER_OFFSET_H, int(lag_hours))))


def state_mask(source: str, feature: str, op: str, threshold: float, index: pd.DatetimeIndex,
               *, lag_hours: int = MAX_BROKER_OFFSET_H, root: Path | None = None
               ) -> np.ndarray | None:
    """Boolean per bar of `index`: the condition held on the newest value knowable at that bar.

    A bar before the first knowable value is False, never NaN-as-True. None when the condition
    cannot be measured at all (no series, unknown op), which callers treat as "emit nothing".
    """
    fn = OPS.get(str(op))
    if fn is None:
        return None
    s = feature_series(source, feature, lag_hours=lag_hours, root=root)
    if s is None:
        return None
    try:
        idx = pd.DatetimeIndex(index)
        if idx.tz is None:
            idx = idx.tz_localize("UTC")
        pos = s.index.searchsorted(idx, side="right") - 1
    except (TypeError, ValueError):
        return None             # a series that will not align to the bar clock is UNMEASURED
    vals = s.to_numpy()
    out = np.zeros(len(idx), dtype=bool)
    ok = pos >= 0
    if ok.any():
        v = vals[pos[ok]]
        out[ok] = np.asarray(fn(v, float(threshold)), dtype=bool) & np.isfinite(v)
    return out


def family_implied_vol_state(
    df: pd.DataFrame,
    *,
    source: str,
    feature: str,
    op: str,
    threshold: float,
    direction: int = 1,
    lag_hours: int = MAX_BROKER_OFFSET_H,
    atr_n: int = 20,
    stop_atr: float = 2.0,
    rr: float = 2.0,
    ttl_bars: int = 24,
    series_root: Path | None = None,
) -> list[Signal]:
    """One signal per EPISODE: the first bar on which `feature op threshold` becomes true."""
    d = _h1(df)
    if d.empty or len(d) <= atr_n + 1 or int(direction) not in (1, -1):
        return []
    mask = state_mask(source, feature, op, threshold, pd.DatetimeIndex(d.index),
                      lag_hours=lag_hours, root=series_root)
    if mask is None or not mask.any():
        return []
    prev = np.concatenate([[False], mask[:-1]])
    onset = np.flatnonzero(mask & ~prev)
    atr = _atr(d, atr_n).to_numpy()
    close = d["close"].to_numpy()
    out: list[Signal] = []
    for i in onset:
        if i < atr_n or i >= len(d) - 1:
            continue
        a = float(atr[i])
        if not np.isfinite(a) or a <= 0:
            continue
        side = int(direction)
        px = float(close[i])
        out.append(Signal(time=d.index[i], side=side, stop=px - side * stop_atr * a,
                          target=px + side * stop_atr * a * rr, ttl_bars=int(ttl_bars),
                          tag="implied_vol_state", trigger=None, wait_bars=1))
    return out


def family_implied_vol_conditioned(
    df: pd.DataFrame,
    *,
    base_family: str,
    source: str,
    feature: str,
    op: str,
    threshold: float,
    base_params: dict[str, Any] | None = None,
    lag_hours: int = MAX_BROKER_OFFSET_H,
    series_root: Path | None = None,
) -> list[Signal]:
    """`base_family`'s own signals, kept only where the implied state holds at signal time."""
    if not wrappable(base_family):
        return []
    fn = get_family_func(base_family)
    if fn is None:
        return []
    d = _h1(df)
    if d.empty:
        return []
    params = dict(base_params or {})
    for k in ("timeframe", "session"):
        params.pop(k, None)
    try:
        raw = fn(d, **params)
    except Exception:
        return []
    sigs = [s for s in (raw or []) if isinstance(s, Signal)]
    if not sigs:
        return []
    mask = state_mask(source, feature, op, threshold, pd.DatetimeIndex([s.time for s in sigs]),
                      lag_hours=lag_hours, root=series_root)
    if mask is None:
        return []
    return [s for s, keep in zip(sigs, mask, strict=True) if keep]
