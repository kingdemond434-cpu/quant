"""TICK-FLOW FAMILIES -- order flow and liquidity state read off THIS broker's own quote tape.

WHY THESE EXIST (flow factory, principal 2026-10-11). `orderflow_imbalance` and
`liquidity_regime` already read the tape, but the sealed gauntlet hands them ONE flow series --
the net sign of mid changes per bar -- so every other order-flow construction the tape supports
(the tick rule, Cont-Kukanov-Stoikov order-flow imbalance from bid/ask revisions, quote intensity,
the residual of flow against the price response it bought) had no family a cell could name. These
two families load a per-symbol series that `research/flow_factory.py` builds from the tape
every hour, by `source` and `feature` on the recipe, so the gauntlet's ordinary
`fn(h1, **params)` call rebuilds them with no change to the gauntlet (the same pattern as
`family_implied_vol`).

  tick_flow       DIRECT. The feature, aggregated onto the cell's chart, z-scored on its own
      trailing `lookback` bars. `follow`/`fade` take the side from the feature's sign (signed
      features only); `move_follow`/`move_fade` take it from the bar's own return and use the
      feature as the STATE gate (a spread or intensity spike).

  flow_residual   OrderFlow - PriceResponse. A trailing OLS of the bar's return on its flow
      (fit on bars strictly before the one being judged) prices the move the flow should have
      bought; the residual is what price did beyond it. `unabsorbed`: strong flow that price did
      NOT follow -- trade in the flow's direction, the response is owed. `exhaustion`: a large
      price move with no flow behind it -- fade it, nobody paid for it.

THE SERIES is `data/lake/series/tf_<SYMBOL>.parquet`, one row per five-minute bucket of the
broker's tick clock: `bucket` (bucket START, broker time under a UTC label -- the same clock the
bars carry, because both come from MT5's `time_msc`), the features, and `available` = bucket end.
A bar labelled T on a chart of length L aggregates buckets whose start lies in [T, T+L): every
one of them has ended by the bar's close, which is when a signal on that bar is acted on. Buckets
are written only once complete and never rewritten, so the series is a vintage, not a restatement.

WHAT THE FLOW IS NOT. Fusion publishes no depth of market (`data/tape/depth_probe.json`: levels 0
on every symbol probed) and no trade side, so `quote_ofi` is OFI at UNIT depth -- sign(dBid) +
sign(dAsk) per revision -- and `tick_rule` is the tick test applied to the MID. Both are named
proxies for aggressor flow, never sold as it.

`source` IS REQUIRED: it names the series on the recipe (the factory names it and the judge
charges its own grid), so a sweep with no source classifies both families as needing source
evidence instead of calling them blind.

NOTHING HERE PROMOTES. Both refuse -- return [] -- without the series, the column, or enough
buckets; they never fall back to price.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from mt5desk.families import Signal, _atr

SERIES_DIR = Path(__file__).resolve().parents[1] / "data" / "lake" / "series"
#: Minutes per bucket in the series. A chart finer than this cannot be expressed.
BUCKET_MIN = 5
#: Features the factory publishes. SIGNED features carry a direction; the rest are states.
SIGNED: tuple[str, ...] = ("tick_rule", "quote_ofi", "mid_sign")
STATES: tuple[str, ...] = ("spread_bp", "spread_max_bp", "quote_rate")
FEATURES: tuple[str, ...] = SIGNED + STATES
#: How each feature folds from buckets onto a bar: counts add, levels average, extremes max.
AGG: dict[str, str] = {"tick_rule": "sum", "quote_ofi": "sum", "mid_sign": "sum",
                       "spread_bp": "mean", "spread_max_bp": "max", "quote_rate": "sum"}
MODES_DIRECT: tuple[str, ...] = ("follow", "fade", "move_follow", "move_fade")
MODES_RESIDUAL: tuple[str, ...] = ("unabsorbed", "exhaustion")
#: Bars with a measured feature needed before either family emits anything.
MIN_BARS = 60


def series_path(source: str, root: Path | None = None) -> Path | None:
    """`tf_<SYMBOL>` -> its parquet, or None. A path-like name is refused, never resolved."""
    if not source or not str(source).startswith("tf_") or any(c in str(source)
                                                                for c in "/\\") \
            or ".." in str(source):
        return None
    p = (root or SERIES_DIR) / f"{source}.parquet"
    return p if p.exists() else None


def load_series(source: str, root: Path | None = None) -> pd.DataFrame | None:
    p = series_path(source, root)
    if p is None:
        return None
    try:
        f = pd.read_parquet(p)
    except Exception:
        return None
    if "bucket" not in f.columns:
        return None
    f = f.copy()
    f["bucket"] = pd.to_datetime(f["bucket"], utc=True)
    return f.sort_values("bucket").drop_duplicates("bucket", keep="first").set_index("bucket")


def on_bars(series: pd.DataFrame, index: pd.DatetimeIndex, feature: str) -> pd.Series | None:
    """The feature folded onto the bars of `index` (left-labelled), NaN where no bucket fell.

    The bar length is the index's own modal step; a chart finer than a bucket is refused.
    """
    if feature not in FEATURES or feature not in series.columns or len(index) < 3:
        return None
    step = pd.Series(index).diff().dropna()
    if step.empty:
        return None
    bar = step.mode().iloc[0]
    if bar < pd.Timedelta(minutes=BUCKET_MIN):
        return None
    col = pd.to_numeric(series[feature], errors="coerce").dropna()
    if col.empty:
        return None
    # Bucket b belongs to bar T iff T <= b < T + bar. searchsorted on the bar starts.
    starts = index.asi8
    pos = np.searchsorted(starts, col.index.asi8, side="right") - 1
    ok = pos >= 0
    ok &= col.index.asi8 < (starts[np.clip(pos, 0, None)] + bar.value)
    s = pd.Series(col.to_numpy()[ok], index=pos[ok])
    how = AGG.get(feature, "mean")
    agg = s.groupby(level=0).agg(how)
    out = pd.Series(np.nan, index=index, dtype="float64")
    out.iloc[agg.index.to_numpy()] = agg.to_numpy()
    return out


def _z(x: pd.Series, lookback: int) -> pd.Series:
    """z of each bar against the PRIOR `lookback` bars -- the bar itself is not in its own norm."""
    prior = x.shift(1)
    mu = prior.rolling(lookback, min_periods=max(10, lookback // 2)).mean()
    sd = prior.rolling(lookback, min_periods=max(10, lookback // 2)).std(ddof=1)
    return (x - mu) / sd.where(sd > 0)


def _signal(d: pd.DataFrame, i: int, side: int, atr: np.ndarray, stop_atr: float, rr: float,
            ttl_bars: int, tag: str) -> Signal | None:
    a = float(atr[i])
    if not np.isfinite(a) or a <= 0:
        return None
    px = float(d["close"].iat[i])
    return Signal(time=d.index[i], side=side, stop=px - side * stop_atr * a,
                  target=px + side * stop_atr * a * rr, ttl_bars=ttl_bars, tag=tag,
                  trigger=None, wait_bars=1)


def family_tick_flow(
    df: pd.DataFrame,
    *,
    source: str,
    feature: str = "tick_rule",
    mode: str = "follow",
    lookback: int = 48,
    z_in: float = 2.0,
    atr_n: int = 20,
    stop_atr: float = 1.5,
    rr: float = 1.5,
    ttl_bars: int = 12,
    series: pd.DataFrame | None = None,
) -> list[Signal]:
    """Enter when the tape feature leaves its own trailing norm. See the module docstring."""
    if mode not in MODES_DIRECT or (mode in ("follow", "fade") and feature not in SIGNED):
        return []
    f = series if series is not None else load_series(source)
    if f is None or df.empty:
        return []
    d = df.sort_index()
    x = on_bars(f, d.index, feature)
    if x is None or int(x.notna().sum()) < MIN_BARS:
        return []
    z = _z(x, lookback).to_numpy()
    ret = d["close"].astype(float).pct_change().to_numpy()
    atr = _atr(d, atr_n).to_numpy()
    out: list[Signal] = []
    for i in range(1, len(d) - 1):
        zi = z[i]
        if not np.isfinite(zi):
            continue
        if mode in ("follow", "fade"):
            if abs(zi) < z_in:
                continue
            side = (1 if zi > 0 else -1) * (1 if mode == "follow" else -1)
        else:
            if zi < z_in or not np.isfinite(ret[i]) or ret[i] == 0:
                continue
            side = (1 if ret[i] > 0 else -1) * (1 if mode == "move_follow" else -1)
        s = _signal(d, i, side, atr, stop_atr, rr, ttl_bars, f"tick_flow:{feature}:{mode}")
        if s is not None:
            out.append(s)
    return out


def family_flow_residual(
    df: pd.DataFrame,
    *,
    source: str,
    feature: str = "tick_rule",
    mode: str = "unabsorbed",
    lookback: int = 96,
    z_in: float = 2.0,
    calm_z: float = 1.0,
    atr_n: int = 20,
    stop_atr: float = 1.5,
    rr: float = 1.5,
    ttl_bars: int = 12,
    series: pd.DataFrame | None = None,
) -> list[Signal]:
    """OrderFlow - PriceResponse: trade the flow price has not paid for, or fade the move no flow
    paid for. The response coefficient is fit on bars strictly BEFORE the bar it prices."""
    if mode not in MODES_RESIDUAL or feature not in SIGNED:
        return []
    f = series if series is not None else load_series(source)
    if f is None or df.empty:
        return []
    d = df.sort_index()
    x = on_bars(f, d.index, feature)
    if x is None or int(x.notna().sum()) < MIN_BARS:
        return []
    r = np.log(d["close"].astype(float)).diff()
    mp = max(10, lookback // 2)
    xp, rp = x.shift(1), r.shift(1)
    cov = (xp * rp).rolling(lookback, min_periods=mp).mean() - \
        xp.rolling(lookback, min_periods=mp).mean() * rp.rolling(lookback, min_periods=mp).mean()
    var = xp.rolling(lookback, min_periods=mp).var(ddof=0)
    beta = cov / var.where(var > 0)
    resid = r - beta * x
    rz = _z(resid, lookback).to_numpy()
    fz = _z(x, lookback).to_numpy()
    xv, rv = x.to_numpy(), r.to_numpy()
    atr = _atr(d, atr_n).to_numpy()
    out: list[Signal] = []
    for i in range(1, len(d) - 1):
        if not (np.isfinite(rz[i]) and np.isfinite(fz[i]) and np.isfinite(xv[i])
                and np.isfinite(rv[i])):
            continue
        if mode == "unabsorbed":
            # Strong flow, and price under-delivered against it (residual leans the other way).
            if abs(fz[i]) < z_in or xv[i] == 0 or np.sign(rz[i]) != -np.sign(xv[i]):
                continue
            side = 1 if xv[i] > 0 else -1
        else:
            # A large unexplained move with the flow inside its normal band.
            if abs(rz[i]) < z_in or abs(fz[i]) >= calm_z or rv[i] == 0:
                continue
            side = -1 if rv[i] > 0 else 1
        s = _signal(d, i, side, atr, stop_atr, rr, ttl_bars, f"flow_residual:{feature}:{mode}")
        if s is not None:
            out.append(s)
    return out
