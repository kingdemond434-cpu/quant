"""Candidate signal generators for the MT5 research desk.

Every family_* function is a pure H1-bar consumer: (closed bars in, signals
out) so backtest == production path.

ZERO-HARDcoding ARCHITECTURE:
  - Every family_* function auto-registers via FAMILY_REGISTRY
  - Each entry declares: function, default params, param grid for sweeping
  - Converter and backtest auto-discover from registry — no whitelists
  - Adding a family = adding a function + registry entry. Nothing else changes.
"""
from __future__ import annotations

import inspect
from collections.abc import Callable

import numpy as np
import pandas as pd
from mt5desk.engine import Signal

try:
    from libs.research.bar_span import is_out_of_calendar
except ModuleNotFoundError:  # desk entrypoints put desks/mt5 on sys.path, not the repo root
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[3]))
    # Windows Python's OWN install dir ships a `libs\` folder (C linker stubs) that namespace-
    # packages into `import libs` and caches BEFORE this fallback runs -- the retry then asks
    # the cached wrong package for `.research` forever. Purge it so the repo-root regular
    # package (with __init__.py) wins the fresh resolution.
    for _m in [k for k in _sys.modules if k == "libs" or k.startswith("libs.")]:
        del _sys.modules[_m]
    from libs.research.bar_span import is_out_of_calendar

__all__ = [
    "FAMILY_REGISTRY",
    "get_all_family_names",
    "get_family_func",
    "get_param_grid",
]


# ---------------------------------------------------------------------------
# Auto-registry: every family_* function that follows the convention gets
# registered with its default params and a param grid for sweeping.
# ---------------------------------------------------------------------------

FAMILY_REGISTRY: dict[str, dict] = {}


def register_family(
    *,
    param_grid: dict[str, list] | None = None,
    tags: list[str] | None = None,
):
    """Decorator that registers a family_* function into FAMILY_REGISTRY.

    Usage:
        @register_family(param_grid={"rr": [1.5, 2.0], "ttl_bars": [8, 12]})
        def family_my_thing(df, *, rr=1.8, ttl_bars=12, ...):
            ...
    """
    def decorator(func: Callable):
        sig = inspect.signature(func)
        defaults = {
            k: v.default
            for k, v in sig.parameters.items()
            if k != "df" and v.default is not inspect.Parameter.empty
        }
        grid = dict(param_grid) if param_grid else {}
        name = func.__name__
        if name.startswith("family_"):
            name = name[7:]
        FAMILY_REGISTRY[name] = {
            "func": func,
            "name": name,
            "defaults": defaults,
            "param_grid": grid,
            "tags": tags or [],
        }
        return func
    return decorator


def get_family_func(name: str) -> Callable | None:
    entry = FAMILY_REGISTRY.get(name)
    return entry["func"] if entry else None


def get_all_family_names() -> list[str]:
    return sorted(FAMILY_REGISTRY.keys())


def get_param_grid(name: str) -> dict[str, list]:
    entry = FAMILY_REGISTRY.get(name)
    return entry["param_grid"] if entry else {}


def generate_test_grid(
    symbols: list[str],
    source: str = "",
    family_filter: list[str] | None = None,
) -> list[dict]:
    """Auto-generate a test grid from the registry.

    For each symbol x each family x each param combination in the grid,
    produce a test cell. No hardcoding anywhere — the registry IS the source
    of truth.
    """
    grid = []
    families = family_filter if family_filter else get_all_family_names()
    for fname in families:
        entry = FAMILY_REGISTRY.get(fname)
        if not entry:
            continue
        func = entry["func"]
        defaults = entry["defaults"]
        param_grid = entry["param_grid"]

        # If grid is empty, just use defaults
        if not param_grid:
            for sym in symbols:
                grid.append({
                    "symbol": sym,
                    "family": fname,
                    "params": dict(defaults),
                    "source_hypothesis": source,
                })
            continue

        # Cartesian product of param grid
        keys = list(param_grid.keys())
        values = [param_grid[k] for k in keys]
        from itertools import product
        for combo in product(*values):
            params = dict(defaults)
            params.update(dict(zip(keys, combo)))
            for sym in symbols:
                grid.append({
                    "symbol": sym,
                    "family": fname,
                    "params": params,
                    "source_hypothesis": source,
                })
    return grid


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    """Average True Range."""
    h, l, c = df["high"], df["low"], df["close"].shift(1)
    tr = pd.concat([(h - l), (h - c).abs(), (l - c).abs()], axis=1).max(axis=1)
    return tr.rolling(n, min_periods=1).mean()


def _h1(df: pd.DataFrame) -> pd.DataFrame:
    """Resample to H1 if not already. The index leaves here tz-aware UTC, always.

    A producer rewrote the universe parquets with a tz-NAIVE datetime64[ms] index (caught
    2026-08-27: every comparison against an aware stamp -- lookahead guards, forward boundaries,
    session windows -- raised or, worse, silently disagreed about which hour a bar is). Bars on
    this desk are stamped +00:00, so naive input is localized, aware input is converted, and no
    caller ever has to guess again about the OFFSET ARITHMETIC.

    THE STAMP IS NOT UTC AND THIS DOCSTRING USED TO SAY IT WAS ("broker-UTC by contract").
    MEASURED 2026-08-29 on the live parquets: 446 of 452 weeks in EURUSD_H1 begin Monday 00:00
    and end Friday 23:00, in summer and winter alike. A true-UTC FX tape cannot do that -- its
    week boundary walks between 21:00 and 22:00 Sunday with DST. These are broker EET stamps
    (UTC+3 summer / UTC+2 winter) wearing a +00:00 label.

    WHAT THAT COSTS, AND WHAT IT DOES NOT. It costs nothing arithmetically: the stamps are
    self-consistent and every family below compares stamp-hours to stamp-hours. It costs a
    MECHANISM CLAIM, which is gate 1's entire subject. `ts.hour == 16` is 13:00 UTC in summer,
    so a family named for the London close is trading the London afternoon, and gate 1 passes
    it on the strength of a name that does not describe the window. Hour constants are NOT
    changed here -- several were evidently chosen in broker time and land correctly (comex
    settle_hour 20 is 17:00 UTC, the real COMEX settlement) -- because silently re-timing a
    certified cell is a worse defect than a wrong label. The labels are corrected in place and
    the re-timing question is carded, not performed.
    """
    if len(df) == 0:
        return df
    if isinstance(df.index, pd.DatetimeIndex):
        df = df.copy()
        df.index = (df.index.tz_localize("UTC") if df.index.tz is None
                    else df.index.tz_convert("UTC"))
        # AND ONE RESOLUTION. A ms-resolution index makes `asi8` return milliseconds while every
        # Timestamp.value is nanoseconds, which silently voided every backtest fill (see
        # engine.run_backtest). Bars leave here as tz-aware UTC at ns, always.
        df.index = df.index.as_unit("ns")
    if hasattr(df.index, "freq") and df.index.freq is not None:
        return df
    freq = pd.infer_freq(df.index)
    if freq and freq.upper().startswith("1H"):
        return df
    vol_col = "volume" if "volume" in df.columns else "tick_volume"
    agg = {
        "open": "first", "high": "max", "low": "min", "close": "last",
    }
    if vol_col in df.columns:
        agg[vol_col] = "sum"
    return df.resample("1h").agg(agg).dropna()


def _rsi(series: pd.Series, n: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0).rolling(n, min_periods=1).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(n, min_periods=1).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _bb(series: pd.Series, n: int = 20, k: float = 2.0):
    mid = series.rolling(n, min_periods=1).mean()
    std = series.rolling(n, min_periods=1).std()
    return mid, mid + k * std, mid - k * std


def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, min_periods=1).mean()


# ===========================================================================
# EXISTING FAMILIES (preserved exactly)
# ===========================================================================

def d1_session_filtered(frame, *, trades_weekends: bool = False):
    """Drop rows on days this market declares CLOSED -- via the ONE shared calendar rule.

    Takes an ALREADY-BUILT daily frame or Series and filters it; it never resamples (callers own
    their aggregation -- a close-only Series and an OHLC frame are both legitimate inputs, and a
    resample here threw KeyError on the first and re-encoded the weekday rule on both). The rule
    itself lives in libs.research.bar_span so the filter, the lake audit and the gap detector
    can never quietly disagree about what a trading day is (L1.61: one encoding, many readers).
    A weekend-trading instrument is passed through WHOLE, identity included.
    """
    if trades_weekends:
        return frame
    keep = [not is_out_of_calendar(int(ts.value) // 1_000_000, trades_weekends=trades_weekends)
            for ts in frame.index]
    return frame[keep]


@register_family(param_grid={
    "shock_atr": [1.5, 2.0, 2.5],
    "rr": [1.5, 1.8, 2.0],
})
def family_usd_session_shock(
    df: pd.DataFrame,
    fx: pd.DataFrame | None,
    *,
    # STAMP-HOURS, NOT UTC (measured 2026-08-29, see `_h1`): 7-16 broker EET is 04:00-13:00 UTC
    # in summer -- it opens three hours before London does and closes three hours before it
    # does. Constants unchanged; the claim is what was wrong.
    london_start: int = 7,
    london_end: int = 16,
    shock_atr: float = 2.0,
    atr_n: int = 20,
    ttl_bars: int = 12,
    rr: float = 1.8,
) -> list[Signal]:
    if fx is None or len(fx) < 300:
        return []
    h1 = _h1(df)
    fxr = fx.resample("1h").agg({"close": "last"}).dropna()
    fxr = fxr.reindex(h1.index.union(fxr.index)).ffill().reindex(h1.index)
    fx_ret = fxr["close"].pct_change().rolling(24).std().fillna(0)
    fx_move = fxr["close"].pct_change().abs()
    atr = _atr(h1, atr_n)
    fxc = fxr["close"].to_numpy()
    fr = fx_ret.to_numpy()
    fm = fx_move.to_numpy()
    a = atr.to_numpy()
    c = h1["close"].to_numpy()
    signals: list[Signal] = []
    for i in range(2, len(h1) - 2):
        ts = h1.index[i]
        if not (london_start <= ts.hour < london_end):
            continue
        if np.isnan(c[i]) or np.isnan(c[i - 1]):
            continue
        std = fr[i]
        if not (std > 0):
            continue
        if not (fm[i] > shock_atr * std):
            continue
        ai = a[i]
        if not (ai > 0):
            continue
        side = 1 if fxc[i] < fxc[i - 1] else -1
        stop_dist = 1.2 * ai
        entry = c[i]
        stop = entry - side * stop_dist
        target = entry + side * stop_dist * rr
        signals.append(Signal(time=ts, side=side, stop=stop, target=target,
                              ttl_bars=ttl_bars, tag="usd_session_shock"))
    return signals


@register_family(param_grid={
    "move_thresh": [0.5, 0.75, 1.0],
    "rr": [1.4, 1.6, 1.8],
})
def family_comex_settlement(
    df: pd.DataFrame,
    *,
    settle_hour: int = 20,
    window_before: int = 2,
    vol_floor: float = 0.5,
    move_thresh: float = 0.75,
    ttl_bars: int = 12,
    rr: float = 1.6,
    atr_n: int = 20,
) -> list[Signal]:
    h1 = _h1(df)
    atr = _atr(h1, atr_n)
    vol_med = atr.rolling(120).median()
    c = h1["close"].to_numpy()
    o = h1["open"].to_numpy()
    a = atr.to_numpy()
    vm = vol_med.to_numpy()
    signals: list[Signal] = []
    for i in range(window_before, len(h1) - 2):
        ts = h1.index[i]
        if ts.hour != settle_hour:
            continue
        if np.isnan(c[i - 1]):
            continue
        ai = a[i]
        v = vm[i]
        if not (ai > 0) or np.isnan(v):
            continue
        pre = c[i - window_before]
        now = c[i - 1]
        move = (now - pre) / ai
        vol_high = ai > vol_floor * v
        side = 0
        if vol_high and abs(move) > move_thresh:
            side = 1 if move > 0 else -1
        elif not vol_high and abs(move) > move_thresh:
            side = -1 if move > 0 else 1
        if side == 0:
            continue
        entry = o[i]
        stop_dist = 1.2 * ai
        stop = entry - side * stop_dist
        target = entry + side * stop_dist * rr
        signals.append(Signal(time=ts, side=side, stop=stop, target=target,
                              ttl_bars=ttl_bars, tag="comex_settlement"))
    return signals


@register_family(param_grid={
    "mom_thresh": [0.25, 0.35, 0.5],
    "rr": [1.5, 1.8, 2.0],
})
def family_asia_momentum(
    df: pd.DataFrame,
    *,
    asia_start: int = 0,
    asia_end: int = 7,
    atr_n: int = 20,
    mom_thresh: float = 0.35,
    ttl_bars: int = 12,
    rr: float = 1.8,
) -> list[Signal]:
    h1 = _h1(df)
    atr = _atr(h1, atr_n)
    h1 = h1.assign(date=h1.index.date, hour=h1.index.hour)
    asia = (
        h1.loc[(h1["hour"] >= asia_start) & (h1["hour"] < asia_end)]
        .groupby("date")
        .agg(o=("open", "first"), c=("close", "last"))
    )
    signals: list[Signal] = []
    a = atr.to_numpy()
    o = h1["open"].to_numpy()
    for i in range(2, len(h1) - 2):
        ts = h1.index[i]
        if ts.hour != asia_end:
            continue
        key = ts.date()
        if key not in asia.index:
            continue
        ai = a[i]
        if not (ai > 0) or np.isnan(ai):
            continue
        row = asia.loc[key]
        move = float(row["c"] - row["o"])
        if abs(move) < mom_thresh * ai:
            continue
        side = 1 if move > 0 else -1
        entry = o[i]
        stop_dist = 1.2 * ai
        stop = entry - side * stop_dist
        target = entry + side * stop_dist * rr
        signals.append(Signal(time=ts, side=side, stop=stop, target=target,
                              ttl_bars=ttl_bars, tag="asia_momentum"))
    return signals


@register_family(param_grid={
    "dow_long": [0], "dow_short": [3],
})
def family_dow_effect(
    df: pd.DataFrame,
    *,
    dow_long: int = 0,
    dow_short: int = 3,
    atr_n: int = 20,
    ttl_bars: int = 12,
    rr: float = 1.8,
) -> list[Signal]:
    h1 = _h1(df)
    atr = _atr(h1, atr_n)
    signals: list[Signal] = []
    a = atr.to_numpy()
    o = h1["open"].to_numpy()
    for i in range(2, len(h1) - 2):
        ts = h1.index[i]
        if ts.hour != 0:
            continue
        ai = a[i]
        if not (ai > 0) or np.isnan(ai):
            continue
        side = 0
        if ts.dayofweek == dow_long:
            side = 1
        elif ts.dayofweek == dow_short:
            side = -1
        if side == 0:
            continue
        entry = o[i]
        stop_dist = 1.2 * ai
        stop = entry - side * stop_dist
        target = entry + side * stop_dist * rr
        signals.append(Signal(time=ts, side=side, stop=stop, target=target,
                              ttl_bars=ttl_bars, tag="dow_effect"))
    return signals


@register_family(param_grid={
    "mom_thresh": [0.0008, 0.0012, 0.002],
    "rr": [1.5, 1.8, 2.0],
})
def family_momentum_volgate(
    df: pd.DataFrame,
    *,
    mom_n: int = 6,
    atr_n: int = 20,
    vol_gate_q: float = 0.4,
    ttl_bars: int = 12,
    rr: float = 1.8,
    mom_thresh: float = 0.0012,
) -> list[Signal]:
    h1 = _h1(df)
    atr = _atr(h1, atr_n)
    atr_med = atr.rolling(120, min_periods=40).median()
    mom = h1["close"].pct_change(mom_n)
    a = atr.to_numpy()
    vm = atr_med.to_numpy()
    m = mom.to_numpy()
    c = h1["close"].to_numpy()
    o = h1["open"].to_numpy()
    signals: list[Signal] = []
    for i in range(mom_n + 1, len(h1) - 2):
        ts = h1.index[i]
        if np.isnan(c[i]):
            continue
        ai = a[i]
        v = vm[i]
        if not (ai > 0) or np.isnan(v) or ai < vol_gate_q * v:
            continue
        mi = m[i]
        if np.isnan(mi) or abs(mi) < mom_thresh:
            continue
        if abs(mi) < 0.35 * (ai / c[i]):
            continue
        side = 1 if mi > 0 else -1
        entry = o[i + 1]
        stop_dist = 1.2 * ai
        stop = entry - side * stop_dist
        target = entry + side * stop_dist * rr
        signals.append(Signal(time=h1.index[i + 1], side=side, stop=stop,
                              target=target, ttl_bars=ttl_bars, tag="momentum_volgate"))
    return signals


@register_family(param_grid={
    "wait_bars": [8, 12, 16],
    "rr": [1.5, 2.0, 2.5],
})
def family_session_range_breakout(
    df: pd.DataFrame,
    *,
    range_start: int = 7,
    range_end: int | None = None,
    signal_at: int | None = None,
    wait_bars: int = 8,
    atr_n: int = 20,
    ttl_bars: int = 12,
    rr: float = 2,
    spread_gate: bool = False,
    trend_filter: str = "none",
    range_filter: str = "all",
    vol_filter: str = "all",
    midpoint_filter: str = "off",
) -> list[Signal]:
    """`midpoint_filter="prev_day"` is Stefano Serafini's published conditioning, reverse-
    engineered: take only the side of a session breakout that agrees with where price sits
    relative to the PREVIOUS DAY'S midpoint.

        MID_(d-1) = (H_(d-1) + L_(d-1)) / 2
        long only if price > MID_(d-1);  short only if price < MID_(d-1)

    IT IS A FILTER ON AN EXISTING TRIGGER, NOT A NEW FAMILY, and that is deliberate. The desk
    already has this breakout; adding "Serafini opening range" as its own family would spend a
    multiplicity slot on a duplicate and make the deflated-Sharpe bar harder for every other
    candidate in the sweep. The falsifiable claim is precisely the conditioning -- does the same
    trigger do better when it agrees with yesterday's structure -- so it is tested as an A/B
    against the identical unfiltered parent, which `midpoint_filter="off"` still is.

    The midpoint is computed on the desk's own daily aggregation of H1 bars rather than on
    broker settlement bars, which is the point Serafini makes about synthetic 1,440-minute bars.
    """
    h1 = _h1(df)
    atr = _atr(h1, atr_n)
    h1 = h1.assign(date=h1.index.date, hour=h1.index.hour)
    spread_med = (
        h1["spread"].rolling(96).median() if "spread" in h1.columns else None
    )
    if range_end is None:
        window = h1.loc[h1["hour"] < range_start]
        signal_hour = signal_at if signal_at is not None else range_start
    else:
        window = h1.loc[(h1["hour"] >= range_start) & (h1["hour"] < range_end)]
        signal_hour = signal_at if signal_at is not None else range_end
    range_by_day = window.groupby("date").agg(hi=("high", "max"), lo=("low", "min"))
    span_by_day = (range_by_day["hi"] - range_by_day["lo"]).rename("span")
    span_med = span_by_day.rolling(20, min_periods=10).median()
    atr_med = atr.rolling(200, min_periods=60).median()
    ema20 = h1["close"].ewm(span=20, min_periods=10).mean()
    # PREVIOUS day's midpoint per date, shifted so a day never sees its own range.
    prev_mid: dict = {}
    if midpoint_filter == "prev_day":
        day = h1.groupby("date").agg(hi=("high", "max"), lo=("low", "min"))
        prev_mid = ((day["hi"] + day["lo"]) / 2.0).shift(1).to_dict()
    signals: list[Signal] = []
    for i in range(1, len(h1) - 2):
        ts = h1.index[i]
        if ts.hour != signal_hour:
            continue
        if np.isnan(h1["open"].iloc[i]):
            continue
        a = atr.iloc[i]
        if not (a > 0):
            continue
        if spread_gate:
            sm = spread_med.iloc[i]
            if spread_med is None or np.isnan(sm) or h1["spread"].iloc[i] > sm:
                continue
        key = ts.date()
        if key not in range_by_day.index:
            continue
        hi, lo = float(range_by_day.at[key, "hi"]), float(range_by_day.at[key, "lo"])
        span = hi - lo
        if span <= 0:
            continue
        sm2 = span_med.get(key, np.nan)
        if range_filter == "small" and not (np.isnan(sm2) or span < sm2):
            continue
        if range_filter == "large" and not (np.isnan(sm2) or span > sm2):
            continue
        am = atr_med.iloc[i]
        if vol_filter == "low" and not (np.isnan(am) or a < am):
            continue
        if vol_filter == "high" and not (np.isnan(am) or a > am):
            continue
        slope = 0.0
        if trend_filter == "aligned":
            if i >= 5:
                slope = float(ema20.iloc[i] - ema20.iloc[i - 4])

        # SERAFINI'S PRIOR-DAY MIDPOINT. Strictly one-sided lookback: the midpoint comes from the
        # day BEFORE this signal's day, so a signal can never see its own session's range.
        allow_long = allow_short = True
        if midpoint_filter == "prev_day":
            mid = prev_mid.get(h1["date"].iloc[i])
            if mid is None or np.isnan(mid):
                continue                  # no prior day: UNMEASURED, so no trade (L1.28a)
            px = float(h1["close"].iloc[i])
            allow_long, allow_short = px > mid, px < mid

        dist = max(1.2 * a, span)
        if allow_long and (trend_filter != "aligned" or slope >= 0):
            signals.append(Signal(time=ts, side=1, stop=hi - dist, target=hi + dist * rr,
                                  ttl_bars=ttl_bars, tag="session_range_breakout",
                                  trigger=hi, wait_bars=wait_bars))
        if allow_short and (trend_filter != "aligned" or slope < 0):
            signals.append(Signal(time=ts, side=-1, stop=lo + dist, target=lo - dist * rr,
                                  ttl_bars=ttl_bars, tag="session_range_breakout",
                                  trigger=lo, wait_bars=wait_bars))
    return signals


@register_family(param_grid={
    "mode": ["momentum", "fade"],
    "min_gap_atr": [0.15, 0.2, 0.3],
})
def family_monday_gap(
    df: pd.DataFrame,
    *,
    atr_n: int = 20,
    ttl_bars: int = 12,
    rr: float = 1.8,
    mode: str = "momentum",
    min_gap_atr: float = 0.2,
) -> list[Signal]:
    h1 = _h1(df)
    atr = _atr(h1, atr_n)
    a = atr.to_numpy()
    o = h1["open"].to_numpy()
    c = h1["close"].to_numpy()
    signals: list[Signal] = []
    for i in range(2, len(h1) - 2):
        ts = h1.index[i]
        if ts.dayofweek != 0 or ts.hour != 0:
            continue
        j = i - 1
        while j > 0 and h1.index[j].dayofweek != 4:
            j -= 1
        if j <= 0:
            continue
        ai = a[i]
        if not (ai > 0) or np.isnan(ai):
            continue
        gap = float(o[i] - c[j])
        if abs(gap) < min_gap_atr * ai:
            continue
        side = 1 if gap > 0 else -1
        if mode == "fade":
            side = -side
        entry = o[i]
        stop_dist = 1.2 * ai
        stop = entry - side * stop_dist
        target = entry + side * stop_dist * rr
        signals.append(Signal(time=ts, side=side, stop=stop, target=target,
                              ttl_bars=ttl_bars, tag="monday_gap"))
    return signals


@register_family(param_grid={
    "mom_thresh": [0.2, 0.3, 0.4],
    "ttl_bars": [4, 8],
})
def family_london_close_momentum(
    df: pd.DataFrame,
    *,
    lookback: int = 2,
    atr_n: int = 20,
    mom_thresh: float = 0.3,
    ttl_bars: int = 4,
    rr: float = 1.5,
) -> list[Signal]:
    """NAME IS 2-3 HOURS OFF ITS WINDOW (measured 2026-08-29, see `_h1`). Stamp-hour 16 is
    13:00 UTC in summer / 14:00 in winter -- the London AFTERNOON, not the 15:00-16:00 UTC
    London close. The hour is left untouched (re-timing a tested cell needs its own evidence);
    only the claim is corrected, because gate 1 judges the mechanism by this name."""
    h1 = _h1(df)
    atr = _atr(h1, atr_n)
    a = atr.to_numpy()
    c = h1["close"].to_numpy()
    o = h1["open"].to_numpy()
    signals: list[Signal] = []
    for i in range(lookback + 1, len(h1) - 2):
        ts = h1.index[i]
        if ts.hour != 16:
            continue
        ai = a[i]
        if not (ai > 0) or np.isnan(ai):
            continue
        m = (c[i] - c[i - lookback]) / ai
        if abs(m) < mom_thresh:
            continue
        side = 1 if m > 0 else -1
        entry = o[i]
        stop_dist = 1.2 * ai
        stop = entry - side * stop_dist
        target = entry + side * stop_dist * rr
        signals.append(Signal(time=ts, side=side, stop=stop, target=target,
                              ttl_bars=ttl_bars, tag="london_close_momentum"))
    return signals


@register_family(param_grid={
    "wait_bars": [8, 12],
    "rr": [1.5, 2.0],
    "vol_filter": ["all", "high"],
})
def family_level_breakout(
    df: pd.DataFrame,
    *,
    level: str = "pdh",
    signal_hour: int = 7,
    wait_bars: int = 12,
    atr_n: int = 20,
    ttl_bars: int = 12,
    rr: float = 2.0,
    vol_filter: str = "all",
    vol_gate_q: float = 0.75,
    range_filter: str = "all",
    spread_gate: bool = False,
) -> list[Signal]:
    h1 = _h1(df)
    atr = _atr(h1, atr_n)
    atr_med = atr.rolling(200, min_periods=60).median()
    h1 = h1.assign(date=h1.index.date)
    if level == "pdh":
        d = h1.groupby("date").agg(hi=("high", "max"), lo=("low", "min"))
        d["phi"] = d["hi"].shift(1)
        d["plo"] = d["lo"].shift(1)
    else:
        iso = h1.index.isocalendar()
        h1["wkey"] = iso.year.astype(int) * 100 + iso.week.astype(int)
        d = h1.groupby("wkey").agg(hi=("high", "max"), lo=("low", "min"))
        d["phi"] = d["hi"].shift(1)
        d["plo"] = d["lo"].shift(1)
    span_by_day = (d["hi"] - d["lo"]).rename("span")
    span_med = span_by_day.rolling(20, min_periods=10).median()
    spread_med = (
        h1["spread"].rolling(96).median() if "spread" in h1.columns else None
    )
    a = atr.to_numpy()
    am = atr_med.to_numpy()
    sp = h1["spread"].to_numpy() if "spread" in h1.columns else None
    sm = spread_med.to_numpy() if spread_med is not None else None
    signals: list[Signal] = []
    for i in range(1, len(h1) - 2):
        ts = h1.index[i]
        if ts.hour != signal_hour:
            continue
        if level == "week" and ts.dayofweek != 0:
            continue
        if np.isnan(h1["open"].iloc[i]):
            continue
        ai = a[i]
        if not (ai > 0):
            continue
        if vol_filter == "high":
            v = am[i]
            if np.isnan(v) or ai < vol_gate_q * v:
                continue
        if spread_gate:
            if sm is None or np.isnan(sm[i]) or sp[i] > sm[i]:
                continue
        key = h1["date"].iloc[i] if level == "pdh" else int(h1["wkey"].iloc[i])
        if key not in d.index:
            continue
        hi, lo = float(d.at[key, "phi"]), float(d.at[key, "plo"])
        if not (hi > 0) or not (lo > 0) or hi <= lo:
            continue
        span = hi - lo
        if span <= 0:
            continue
        if range_filter == "small":
            sm2 = span_med.get(key, np.nan)
            if np.isnan(sm2) or span >= sm2:
                continue
        dist = max(1.2 * ai, span)
        signals.append(Signal(time=ts, side=1, stop=hi - dist, target=hi + dist * rr,
                              ttl_bars=ttl_bars, tag=f"level_breakout.{level}",
                              trigger=hi, wait_bars=wait_bars))
        signals.append(Signal(time=ts, side=-1, stop=lo + dist, target=lo - dist * rr,
                              ttl_bars=ttl_bars, tag=f"level_breakout.{level}",
                              trigger=lo, wait_bars=wait_bars))
    return signals


@register_family(param_grid={
    "rr": [1.4, 1.6, 1.8],
    "min_pierce_atr": [0.03, 0.05, 0.1],
})
def family_failed_breakout(
    df: pd.DataFrame,
    *,
    level: str = "pdh",
    signal_hours: tuple = (7, 13, 14, 17),
    atr_n: int = 20,
    ttl_bars: int = 12,
    rr: float = 1.6,
    min_pierce_atr: float = 0.05,
    spread_gate: bool = False,
) -> list[Signal]:
    h1 = _h1(df)
    atr = _atr(h1, atr_n)
    h1 = h1.assign(date=h1.index.date)
    d = h1.groupby("date").agg(hi=("high", "max"), lo=("low", "min"))
    d["phi"] = d["hi"].shift(1)
    d["plo"] = d["lo"].shift(1)
    spread_med = (
        h1["spread"].rolling(96).median() if "spread" in h1.columns else None
    )
    a = atr.to_numpy()
    o = h1["open"].to_numpy()
    c = h1["close"].to_numpy()
    hh = h1["high"].to_numpy()
    ll = h1["low"].to_numpy()
    sp = h1["spread"].to_numpy() if "spread" in h1.columns else None
    sm = spread_med.to_numpy() if spread_med is not None else None
    signals: list[Signal] = []
    for i in range(2, len(h1) - 2):
        ts = h1.index[i]
        if ts.hour not in signal_hours:
            continue
        key = h1["date"].iloc[i]
        if key not in d.index:
            continue
        phi, plo = float(d.at[key, "phi"]), float(d.at[key, "plo"])
        ai = a[i]
        if not (ai > 0) or np.isnan(ai):
            continue
        if spread_gate:
            if sm is None or np.isnan(sm[i]) or sp[i] > sm[i]:
                continue
        side = 0
        pierce = 0.0
        if hh[i] > phi and c[i] < phi and phi > 0:
            side = -1
            pierce = hh[i] - phi
        elif ll[i] < plo and c[i] > plo and plo > 0:
            side = 1
            pierce = plo - ll[i]
        if side == 0:
            continue
        if pierce < min_pierce_atr * ai:
            continue
        entry = o[i + 1]
        stop_dist = 1.2 * ai
        stop = entry - side * stop_dist
        target = entry + side * stop_dist * rr
        signals.append(Signal(time=h1.index[i + 1], side=side, stop=stop,
                              target=target, ttl_bars=ttl_bars,
                              tag=f"failed_breakout.{level}"))
    return signals


# --- COT families ---

def _cot_entries(
    h1: pd.DataFrame,
    cot: pd.DataFrame,
    side: pd.Series,
    tag: str,
    *,
    atr_n: int = 20,
    ttl_bars: int = 160,
    rr: float = 1.6,
) -> list[Signal]:
    atr = _atr(h1, atr_n)
    idx_ns = h1.index.to_numpy().astype("datetime64[ns]").astype("int64")
    sigs: list[Signal] = []
    for rd, s in zip(cot["report_date"], side):
        if s == 0 or pd.isna(rd):
            continue
        monday = rd + pd.Timedelta(days=6)
        loc = int(np.searchsorted(idx_ns, np.int64(pd.Timestamp(monday).value)))
        if loc + 1 >= len(h1):
            continue
        a = atr.iloc[loc]
        if not (a > 0) or np.isnan(a):
            continue
        entry = float(h1["open"].iloc[loc + 1])
        stop_dist = 1.2 * a
        stop = entry - s * stop_dist
        target = entry + s * stop_dist * rr
        sigs.append(Signal(time=h1.index[loc], side=int(s), stop=stop,
                           target=target, ttl_bars=ttl_bars, tag=tag))
    return sigs


@register_family(param_grid={"lo_q": [0.05, 0.10], "hi_q": [0.90, 0.95]})
def family_cot_net_fade(
    df: pd.DataFrame,
    cot: pd.DataFrame,
    *,
    lookback_weeks: int = 104,
    lo_q: float = 0.10,
    hi_q: float = 0.90,
) -> list[Signal]:
    cot = cot.sort_values("report_date").reset_index(drop=True)
    net = cot["noncomm_positions_long_all"] - cot["noncomm_positions_short_all"]
    pct = net.rolling(lookback_weeks, min_periods=lookback_weeks).rank(pct=True)
    side = pd.Series(0, index=cot.index)
    side[pct > hi_q] = -1
    side[pct < lo_q] = 1
    return _cot_entries(_h1(df), cot, side, "cot_net_fade")


@register_family(param_grid={"z_thresh": [1.0, 1.5, 2.0]})
def family_cot_change_fade(
    df: pd.DataFrame,
    cot: pd.DataFrame,
    *,
    lookback_weeks: int = 52,
    z_thresh: float = 1.5,
) -> list[Signal]:
    cot = cot.sort_values("report_date").reset_index(drop=True)
    net = cot["noncomm_positions_long_all"] - cot["noncomm_positions_short_all"]
    delta = net.diff()
    z = (delta - delta.rolling(lookback_weeks, min_periods=lookback_weeks).mean()
         ) / delta.rolling(lookback_weeks, min_periods=lookback_weeks).std()
    side = pd.Series(0, index=cot.index)
    side[z.abs() > z_thresh] = -np.sign(delta[z.abs() > z_thresh])
    side = side.astype(int)
    return _cot_entries(_h1(df), cot, side, "cot_change_fade")


@register_family()
def family_cot_change_momentum(
    df: pd.DataFrame,
    cot: pd.DataFrame,
) -> list[Signal]:
    cot = cot.sort_values("report_date").reset_index(drop=True)
    net = cot["noncomm_positions_long_all"] - cot["noncomm_positions_short_all"]
    delta = net.diff()
    side = pd.Series(0, index=cot.index)
    side[delta > 0] = 1
    side[delta < 0] = -1
    return _cot_entries(_h1(df), cot, side, "cot_change_momentum")


@register_family()
def family_cot_comm_follow(
    df: pd.DataFrame,
    cot: pd.DataFrame,
) -> list[Signal]:
    cot = cot.sort_values("report_date").reset_index(drop=True)
    comm_net = (
        cot["comm_positions_long_all"] - cot["comm_positions_short_all"]
    )
    delta = comm_net.diff()
    side = pd.Series(0, index=cot.index)
    side[delta > 0] = 1
    side[delta < 0] = -1
    return _cot_entries(_h1(df), cot, side, "cot_comm_follow")


# ===========================================================================
# NEW ORTHOGONAL FAMILIES — maximum diversity, zero hardcoding
# ===========================================================================

@register_family(param_grid={
    "rsi_n": [7, 14],
    "oversold": [25, 30],
    "overbought": [70, 75],
    "rr": [1.5, 2.0],
})
def family_mean_reversion_rsi(
    df: pd.DataFrame,
    *,
    rsi_n: int = 14,
    oversold: int = 30,
    overbought: int = 70,
    atr_n: int = 20,
    ttl_bars: int = 12,
    rr: float = 1.8,
) -> list[Signal]:
    """Fade RSI extremes: buy when RSI crosses above oversold, sell below overbought."""
    h1 = _h1(df)
    atr = _atr(h1, atr_n)
    rsi = _rsi(h1["close"], rsi_n)
    a = atr.to_numpy()
    r = rsi.to_numpy()
    o = h1["open"].to_numpy()
    signals: list[Signal] = []
    for i in range(max(rsi_n, atr_n) + 1, len(h1) - 2):
        ts = h1.index[i]
        ai = a[i]
        if not (ai > 0) or np.isnan(r[i]) or np.isnan(r[i - 1]):
            continue
        side = 0
        if r[i - 1] < oversold and r[i] >= oversold:
            side = 1  # crossed up from oversold
        elif r[i - 1] > overbought and r[i] <= overbought:
            side = -1  # crossed down from overbought
        if side == 0:
            continue
        entry = o[i]
        stop_dist = 1.2 * ai
        stop = entry - side * stop_dist
        target = entry + side * stop_dist * rr
        signals.append(Signal(time=ts, side=side, stop=stop, target=target,
                              ttl_bars=ttl_bars, tag="mean_reversion_rsi"))
    return signals


@register_family(param_grid={
    "bb_n": [15, 20, 25],
    "bb_k": [1.5, 2.0, 2.5],
    "rr": [1.5, 2.0],
})
def family_mean_reversion_bollinger(
    df: pd.DataFrame,
    *,
    bb_n: int = 20,
    bb_k: float = 2.0,
    atr_n: int = 20,
    ttl_bars: int = 12,
    rr: float = 1.8,
) -> list[Signal]:
    """Fade Bollinger band touches: buy at lower band, sell at upper band."""
    h1 = _h1(df)
    atr = _atr(h1, atr_n)
    mid, upper, lower = _bb(h1["close"], bb_n, bb_k)
    a = atr.to_numpy()
    c = h1["close"].to_numpy()
    o = h1["open"].to_numpy()
    lo_arr = lower.to_numpy()
    hi_arr = upper.to_numpy()
    signals: list[Signal] = []
    for i in range(max(bb_n, atr_n) + 1, len(h1) - 2):
        ts = h1.index[i]
        ai = a[i]
        if not (ai > 0) or np.isnan(lo_arr[i]) or np.isnan(hi_arr[i]):
            continue
        if np.isnan(c[i - 1]):
            continue
        side = 0
        if c[i - 1] < lo_arr[i] and c[i] >= lo_arr[i]:
            side = 1  # bounced off lower band
        elif c[i - 1] > hi_arr[i] and c[i] <= hi_arr[i]:
            side = -1  # bounced off upper band
        if side == 0:
            continue
        entry = o[i + 1]
        stop_dist = 1.2 * ai
        stop = entry - side * stop_dist
        target = entry + side * stop_dist * rr
        signals.append(Signal(time=h1.index[i + 1], side=side, stop=stop,
                              target=target, ttl_bars=ttl_bars,
                              tag="mean_reversion_bollinger"))
    return signals


@register_family(param_grid={
    "fast_ema": [8, 12, 20],
    "slow_ema": [26, 50],
    "rr": [1.5, 2.0],
})
def family_trend_ma_cross(
    df: pd.DataFrame,
    *,
    fast_ema: int = 12,
    slow_ema: int = 50,
    atr_n: int = 20,
    ttl_bars: int = 12,
    rr: float = 1.8,
) -> list[Signal]:
    """EMA crossover trend-following: fast crosses above slow = long, below = short."""
    h1 = _h1(df)
    atr = _atr(h1, atr_n)
    fast = _ema(h1["close"], fast_ema)
    slow = _ema(h1["close"], slow_ema)
    a = atr.to_numpy()
    f = fast.to_numpy()
    s = slow.to_numpy()
    o = h1["open"].to_numpy()
    signals: list[Signal] = []
    for i in range(max(slow_ema, atr_n) + 1, len(h1) - 2):
        ts = h1.index[i]
        ai = a[i]
        if not (ai > 0) or np.isnan(f[i]) or np.isnan(s[i]):
            continue
        if np.isnan(f[i - 1]) or np.isnan(s[i - 1]):
            continue
        side = 0
        if f[i - 1] < s[i - 1] and f[i] >= s[i]:
            side = 1  # golden cross
        elif f[i - 1] > s[i - 1] and f[i] <= s[i]:
            side = -1  # death cross
        if side == 0:
            continue
        entry = o[i]
        stop_dist = 1.2 * ai
        stop = entry - side * stop_dist
        target = entry + side * stop_dist * rr
        signals.append(Signal(time=ts, side=side, stop=stop, target=target,
                              ttl_bars=ttl_bars, tag="trend_ma_cross"))
    return signals


@register_family(param_grid={
    "bb_n": [20],
    "bb_k": [2.0],
    "squeeze_lookback": [10, 20],
})
def family_volatility_squeeze(
    df: pd.DataFrame,
    *,
    bb_n: int = 20,
    bb_k: float = 2.0,
    squeeze_lookback: int = 20,
    atr_n: int = 20,
    ttl_bars: int = 12,
    rr: float = 2.0,
) -> list[Signal]:
    """BB squeeze (low vol) followed by expansion breakout."""
    h1 = _h1(df)
    atr = _atr(h1, atr_n)
    mid, upper, lower = _bb(h1["close"], bb_n, bb_k)
    bw = (upper - lower) / mid
    bw_low = bw.rolling(squeeze_lookback, min_periods=5).min()
    a = atr.to_numpy()
    c = h1["close"].to_numpy()
    o = h1["open"].to_numpy()
    bw_arr = bw.to_numpy()
    bw_low_arr = bw_low.to_numpy()
    signals: list[Signal] = []
    for i in range(max(bb_n, squeeze_lookback, atr_n) + 1, len(h1) - 2):
        ts = h1.index[i]
        ai = a[i]
        if not (ai > 0) or np.isnan(bw_arr[i]) or np.isnan(bw_low_arr[i]):
            continue
        if np.isnan(c[i - 1]):
            continue
        was_squeezed = bw_low_arr[i - 1] < bw_arr[i - 1] * 0.6
        expanding = bw_arr[i] > bw_arr[i - 1] * 1.2
        if not (was_squeezed and expanding):
            continue
        side = 1 if c[i] > c[i - 1] else -1
        entry = o[i + 1]
        stop_dist = 1.5 * ai
        stop = entry - side * stop_dist
        target = entry + side * stop_dist * rr
        signals.append(Signal(time=h1.index[i + 1], side=side, stop=stop,
                              target=target, ttl_bars=ttl_bars,
                              tag="volatility_squeeze"))
    return signals


@register_family(param_grid={
    "range_n": [20, 50],
    "threshold_pct": [0.005, 0.01],
    "rr": [1.5, 2.0],
})
def family_range_reversion(
    df: pd.DataFrame,
    *,
    range_n: int = 20,
    threshold_pct: float = 0.01,
    atr_n: int = 20,
    ttl_bars: int = 12,
    rr: float = 1.8,
) -> list[Signal]:
    """Fade extreme intraday moves: if price moved > threshold in range_n bars, fade."""
    h1 = _h1(df)
    atr = _atr(h1, atr_n)
    a = atr.to_numpy()
    c = h1["close"].to_numpy()
    o = h1["open"].to_numpy()
    signals: list[Signal] = []
    for i in range(range_n + 1, len(h1) - 2):
        ts = h1.index[i]
        ai = a[i]
        if not (ai > 0) or np.isnan(c[i]) or np.isnan(c[i - range_n]):
            continue
        move = (c[i] - c[i - range_n]) / c[i - range_n]
        if abs(move) < threshold_pct:
            continue
        entry = o[i + 1]
        stop_dist = 1.2 * ai
        side = -1 if move > 0 else 1  # fade the extreme
        stop = entry - side * stop_dist
        target = entry + side * stop_dist * rr
        signals.append(Signal(time=h1.index[i + 1], side=side, stop=stop,
                              target=target, ttl_bars=ttl_bars,
                              tag="range_reversion"))
    return signals


@register_family(param_grid={
    "vol_mult": [1.5, 2.0, 3.0],
    "rr": [1.5, 2.0],
})
def family_volume_spike(
    df: pd.DataFrame,
    *,
    vol_lookback: int = 20,
    vol_mult: float = 2.0,
    atr_n: int = 20,
    ttl_bars: int = 12,
    rr: float = 1.8,
) -> list[Signal]:
    """Trade in the direction of a volume spike (institutional flow)."""
    h1 = _h1(df)
    vol_col = "volume" if "volume" in h1.columns else "tick_volume"
    if vol_col not in h1.columns:
        return []
    atr = _atr(h1, atr_n)
    vol_med = h1[vol_col].rolling(vol_lookback, min_periods=5).median()
    a = atr.to_numpy()
    c = h1["close"].to_numpy()
    o = h1["open"].to_numpy()
    v = h1[vol_col].to_numpy()
    vm = vol_med.to_numpy()
    signals: list[Signal] = []
    for i in range(vol_lookback + 1, len(h1) - 2):
        ts = h1.index[i]
        ai = a[i]
        if not (ai > 0) or np.isnan(vm[i]) or vm[i] <= 0:
            continue
        if v[i] < vol_mult * vm[i]:
            continue
        if np.isnan(c[i]) or np.isnan(c[i - 1]):
            continue
        side = 1 if c[i] > c[i - 1] else -1
        entry = o[i + 1]
        stop_dist = 1.2 * ai
        stop = entry - side * stop_dist
        target = entry + side * stop_dist * rr
        signals.append(Signal(time=h1.index[i + 1], side=side, stop=stop,
                              target=target, ttl_bars=ttl_bars,
                              tag="volume_spike"))
    return signals


@register_family(param_grid={
    "anchor_hour": [0, 7, 13],
    "hold_bars": [4, 8, 12],
    "rr": [1.5, 2.0],
})
def family_overnight_drift(
    df: pd.DataFrame,
    *,
    anchor_hour: int = 0,
    hold_bars: int = 8,
    atr_n: int = 20,
    ttl_bars: int = 12,
    rr: float = 1.8,
) -> list[Signal]:
    """Fade the overnight drift: if price drifted up from anchor, short at anchor hour."""
    h1 = _h1(df)
    atr = _atr(h1, atr_n)
    a = atr.to_numpy()
    c = h1["close"].to_numpy()
    o = h1["open"].to_numpy()
    signals: list[Signal] = []
    for i in range(hold_bars + 2, len(h1) - 2):
        ts = h1.index[i]
        if ts.hour != anchor_hour:
            continue
        ai = a[i]
        if not (ai > 0) or np.isnan(c[i]) or np.isnan(c[i - hold_bars]):
            continue
        drift = (c[i] - c[i - hold_bars]) / ai
        if abs(drift) < 0.3:
            continue
        side = -1 if drift > 0 else 1  # fade the drift
        entry = o[i]
        stop_dist = 1.2 * ai
        stop = entry - side * stop_dist
        target = entry + side * stop_dist * rr
        signals.append(Signal(time=ts, side=side, stop=stop, target=target,
                              ttl_bars=ttl_bars, tag="overnight_drift"))
    return signals


@register_family(param_grid={
    "rsi_n": [14],
    "trend_ema": [50, 100],
    "rr": [1.5, 2.0],
})
def family_pullback_entry(
    df: pd.DataFrame,
    *,
    rsi_n: int = 14,
    trend_ema: int = 50,
    rsi_pullback: int = 40,
    rsi_bounce: int = 50,
    atr_n: int = 20,
    ttl_bars: int = 12,
    rr: float = 1.8,
) -> list[Signal]:
    """Trend-following pullback: buy when price is above EMA and RSI bounces from pullback."""
    h1 = _h1(df)
    atr = _atr(h1, atr_n)
    rsi = _rsi(h1["close"], rsi_n)
    ema = _ema(h1["close"], trend_ema)
    a = atr.to_numpy()
    r = rsi.to_numpy()
    e = ema.to_numpy()
    c = h1["close"].to_numpy()
    o = h1["open"].to_numpy()
    signals: list[Signal] = []
    for i in range(max(trend_ema, rsi_n, atr_n) + 1, len(h1) - 2):
        ts = h1.index[i]
        ai = a[i]
        if not (ai > 0) or np.isnan(r[i]) or np.isnan(e[i]):
            continue
        if np.isnan(r[i - 1]) or np.isnan(c[i - 1]):
            continue
        side = 0
        # Long: above EMA, RSI was below pullback level, now bouncing
        if c[i] > e[i] and r[i - 1] < rsi_pullback and r[i] >= rsi_bounce:
            side = 1
        # Short: below EMA, RSI was above overbought, now falling
        elif c[i] < e[i] and r[i - 1] > (100 - rsi_pullback) and r[i] <= (100 - rsi_bounce):
            side = -1
        if side == 0:
            continue
        entry = o[i + 1]
        stop_dist = 1.2 * ai
        stop = entry - side * stop_dist
        target = entry + side * stop_dist * rr
        signals.append(Signal(time=h1.index[i + 1], side=side, stop=stop,
                              target=target, ttl_bars=ttl_bars,
                              tag="pullback_entry"))
    return signals


@register_family(param_grid={
    "anchor": ["open", "mid"],
    "extreme_atr": [1.5, 2.0, 3.0],
    "rr": [1.5, 2.0],
})
def family_pin_bar_reversal(
    df: pd.DataFrame,
    *,
    anchor: str = "open",
    extreme_atr: float = 2.0,
    atr_n: int = 20,
    ttl_bars: int = 12,
    rr: float = 1.8,
) -> list[Signal]:
    """Pin bar (hammer/shooting star) reversal at key levels."""
    h1 = _h1(df)
    atr = _atr(h1, atr_n)
    a = atr.to_numpy()
    o_arr = h1["open"].to_numpy()
    h_arr = h1["high"].to_numpy()
    l_arr = h1["low"].to_numpy()
    c_arr = h1["close"].to_numpy()
    signals: list[Signal] = []
    for i in range(2, len(h1) - 2):
        ts = h1.index[i]
        ai = a[i]
        if not (ai > 0):
            continue
        body = abs(c_arr[i] - o_arr[i])
        if body < 0.0001:
            continue
        if anchor == "open":
            ref = o_arr[i]
        else:
            ref = (h_arr[i] + l_arr[i]) / 2
        upper_wick = h_arr[i] - max(o_arr[i], c_arr[i])
        lower_wick = min(o_arr[i], c_arr[i]) - l_arr[i]
        side = 0
        # Bullish pin bar: long lower wick, small body at top
        if lower_wick > extreme_atr * ai and lower_wick > 3 * body:
            side = 1
        # Bearish pin bar: long upper wick, small body at bottom
        elif upper_wick > extreme_atr * ai and upper_wick > 3 * body:
            side = -1
        if side == 0:
            continue
        entry = o_arr[i + 1] if i + 1 < len(h1) else c_arr[i]
        stop_dist = 1.2 * ai
        stop = entry - side * stop_dist
        target = entry + side * stop_dist * rr
        signals.append(Signal(time=ts, side=side, stop=stop, target=target,
                              ttl_bars=ttl_bars, tag="pin_bar_reversal"))
    return signals


@register_family(param_grid={
    "n": [3, 5],
    "rr": [1.5, 2.0],
})
def family_engulfing_reversal(
    df: pd.DataFrame,
    *,
    n: int = 3,
    atr_n: int = 20,
    ttl_bars: int = 12,
    rr: float = 1.8,
) -> list[Signal]:
    """N-bar engulfing reversal: current bar fully engulfs prior n bars."""
    h1 = _h1(df)
    atr = _atr(h1, atr_n)
    a = atr.to_numpy()
    o_arr = h1["open"].to_numpy()
    h_arr = h1["high"].to_numpy()
    l_arr = h1["low"].to_numpy()
    c_arr = h1["close"].to_numpy()
    signals: list[Signal] = []
    for i in range(n + 1, len(h1) - 2):
        ts = h1.index[i]
        ai = a[i]
        if not (ai > 0):
            continue
        if np.isnan(c_arr[i]) or np.isnan(o_arr[i]):
            continue
        prev_h = max(h_arr[i - n:i])
        prev_l = min(l_arr[i - n:i])
        curr_h = h_arr[i]
        curr_l = l_arr[i]
        side = 0
        # Bullish engulfing: current bar's range fully engulfs prior n bars
        if curr_h > prev_h and curr_l < prev_l and c_arr[i] > o_arr[i]:
            side = 1
        # Bearish engulfing
        elif curr_h > prev_h and curr_l < prev_l and c_arr[i] < o_arr[i]:
            side = -1
        if side == 0:
            continue
        entry = o_arr[i + 1] if i + 1 < len(h1) else c_arr[i]
        stop_dist = 1.2 * ai
        stop = entry - side * stop_dist
        target = entry + side * stop_dist * rr
        signals.append(Signal(time=ts, side=side, stop=stop, target=target,
                              ttl_bars=ttl_bars, tag="engulfing_reversal"))
    return signals


@register_family(param_grid={
    "ema_fast": [5, 8],
    "ema_slow": [21, 34],
    "rsi_n": [14],
    "rr": [1.5, 2.0],
})
def family_ict_fvg(
    df: pd.DataFrame,
    *,
    ema_fast: int = 8,
    ema_slow: int = 34,
    rsi_n: int = 14,
    atr_n: int = 20,
    ttl_bars: int = 12,
    rr: float = 2.0,
) -> list[Signal]:
    """ICT Fair Value Gap: 3-bar pattern with gap in middle, confirmed by EMA trend."""
    h1 = _h1(df)
    atr = _atr(h1, atr_n)
    fast = _ema(h1["close"], ema_fast)
    slow = _ema(h1["close"], ema_slow)
    a = atr.to_numpy()
    f = fast.to_numpy()
    s = slow.to_numpy()
    o_arr = h1["open"].to_numpy()
    h_arr = h1["high"].to_numpy()
    l_arr = h1["low"].to_numpy()
    c_arr = h1["close"].to_numpy()
    signals: list[Signal] = []
    for i in range(max(ema_slow, atr_n) + 1, len(h1) - 2):
        ts = h1.index[i]
        ai = a[i]
        if not (ai > 0) or np.isnan(f[i]) or np.isnan(s[i]):
            continue
        if i < 2:
            continue
        side = 0
        # Bullish FVG: bar[i-2].high < bar[i].low (gap up), in uptrend
        if h_arr[i - 2] < l_arr[i] and f[i] > s[i]:
            side = 1
        # Bearish FVG: bar[i-2].low > bar[i].high (gap down), in downtrend
        elif l_arr[i - 2] > h_arr[i] and f[i] < s[i]:
            side = -1
        if side == 0:
            continue
        entry = o_arr[i + 1] if i + 1 < len(h1) else c_arr[i]
        stop_dist = 1.2 * ai
        stop = entry - side * stop_dist
        target = entry + side * stop_dist * rr
        signals.append(Signal(time=ts, side=side, stop=stop, target=target,
                              ttl_bars=ttl_bars, tag="ict_fvg"))
    return signals


@register_family(param_grid={
    "rr": [1.0, 1.5],
    "ttl_bars": [2, 4],
    "mode": ["fade", "follow"],
}, tags=["retail_flow", "fxblue", "H-20260828-005"])
def family_retail_overlap_reversal(
    df: pd.DataFrame,
    *,
    hours: tuple[int, ...] = (15, 16),
    ext_atr: float = 1.0,
    atr_n: int = 20,
    stop_atr: float = 1.5,
    ttl_bars: int = 2,
    rr: float = 1.5,
    mode: str = "fade",
) -> list[Signal]:
    """H-20260828-005 -- fade the extension into the retail-concentration hours.

    THE CLOCK IS BROKER STAMP-HOURS, AND THE CARD'S "UTC" LABEL WAS WRONG (verified
    2026-08-29). The universe parquets are stamped +00:00 but carry a fixed civil clock:
    446/452 weeks in EURUSD_H1 begin Monday 00:00 and end Friday 23:00 in BOTH summer and
    winter, which no true-UTC FX tape does (its week boundary walks with DST). They are
    broker EET. The FX Blue corpus that produced this card carries the SAME convention --
    its trade-share peak (15/16/17) is the tape's own stamp-hour tick_volume peak
    (EURUSD 7.3/7.8/8.5%, GBPUSD 7.0/7.6/8.2%, XAUUSD 6.7/8.4/8.4%), and under a UTC
    reading it would have landed on 18-20 where the tape falls away to 6.1/4.2/3.6%.

    So `hours` are stamp-hours on both sides and NO conversion is applied: the integers in
    the card are operationally right and its narrative was three hours off (stamp 15-17 is
    UTC 12-14 -- London afternoon into the NY open, not the overlap's centre). Anyone who
    had "fixed" the label by converting would have introduced the error the label implied.

    M15 IS UNMEASURED, NOT TESTED: the card prescribes M15 and this box holds H1 only
    (203 *_H1 parquets, no M15 for these symbols). This is the H1 arm of the mechanism.
    """
    h1 = _h1(df)
    if len(h1) < atr_n + 4:
        return []
    atr = _atr(h1, atr_n)
    a = atr.to_numpy()
    o = h1["open"].to_numpy()
    c = h1["close"].to_numpy()
    hset = set(int(x) for x in hours)
    signals: list[Signal] = []
    # i is the CLOSED extension bar; entry fills at the open of i+1 (engine rule), so the
    # bar that decides the signal is never the bar that fills it.
    for i in range(atr_n + 1, len(h1) - 2):
        ts = h1.index[i]
        if ts.hour not in hset:
            continue
        ai = a[i]
        if not (ai > 0) or np.isnan(ai):
            continue
        ext = (c[i] - o[i]) / ai
        if abs(ext) < ext_atr:
            continue
        # BOTH DIRECTIONS ARE IN THE GRID BECAUSE THE CARD SET direction: 0 AND SAID SO --
        # "direction is the gauntlet's question". Running only the fade would have been the
        # producer answering a question it explicitly deferred, and both arms are counted as
        # trials by the canonical census, never reported as one.
        sign = 1 if ext > 0 else -1
        side = -sign if mode == "fade" else sign
        entry = c[i]
        stop_dist = stop_atr * ai
        stop = entry - side * stop_dist
        target = entry + side * stop_dist * rr
        signals.append(Signal(time=ts, side=side, stop=stop, target=target,
                              ttl_bars=ttl_bars, tag="retail_overlap_reversal"))
    return signals


def _adx(df: pd.DataFrame, n: int = 14) -> pd.Series:
    """Wilder's ADX -- trend STRENGTH, direction-blind, which is the whole point of the gate.

    Wilder smoothing (an EMA at alpha=1/n), not a simple mean: the published rule this serves
    is stated in Wilder's terms and a rolling mean would answer a different question at every
    parameter the sweep tries.
    """
    h, low, c = df["high"], df["low"], df["close"]
    up, dn = h.diff(), -low.diff()
    plus = np.where((up > dn) & (up > 0), up, 0.0)
    minus = np.where((dn > up) & (dn > 0), dn, 0.0)
    prev = c.shift(1)
    tr = pd.concat([(h - low), (h - prev).abs(), (low - prev).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1.0 / n, min_periods=n, adjust=False).mean()
    pdi = 100.0 * pd.Series(plus, index=df.index).ewm(
        alpha=1.0 / n, min_periods=n, adjust=False).mean() / atr.replace(0.0, np.nan)
    mdi = 100.0 * pd.Series(minus, index=df.index).ewm(
        alpha=1.0 / n, min_periods=n, adjust=False).mean() / atr.replace(0.0, np.nan)
    dx = 100.0 * (pdi - mdi).abs() / (pdi + mdi).replace(0.0, np.nan)
    return dx.ewm(alpha=1.0 / n, min_periods=n, adjust=False).mean()


@register_family(
    # PREREGISTERED, NARROW, AND CENTRED ON THE PUBLISHED POINT. Davey's article settles near a
    # 34-bar channel with a 10-bar ADX lag and explicitly shows the system evaluated across a
    # parameter NEIGHBOURHOOD rather than at one magic point -- so the grid brackets that
    # neighbourhood and stops. Sweeping 8..64 would be searching for the number, which is the
    # multiplicity this desk deflates against.
    param_grid={"channel": [21, 34, 55], "adx_lag": [5, 10], "rr": [1.5, 2.0]},
    tags=["external", "davey", "trend_state", "channel"],
)
def family_adx_channel_hybrid(
    df: pd.DataFrame,
    *,
    channel: int = 34,
    adx_n: int = 11,
    adx_lag: int = 10,
    atr_n: int = 20,
    ttl_bars: int = 24,
    rr: float = 2.0,
    stop_atr: float = 1.5,
) -> list[Signal]:
    """Channel extreme x ADX state: the SAME extreme is continuation or fade by trend state.

    REVERSE-ENGINEERED FROM KEVIN DAVEY'S PUBLISHED CRUDE-OIL RULES, which are unusually exact
    for public material and are the reason this card is worth a family of its own:

        HI_t = (close == max(close[t-channel+1 : t]))
        LO_t = (close == min(close[t-channel+1 : t]))
        TREND_t = ADX_n[t] >= ADX_n[t - adx_lag]          (strengthening, not "above 25")

        new high + trend strengthening -> LONG      (continuation)
        new low  + trend strengthening -> SHORT     (continuation)
        new low  + trend weakening     -> LONG      (fade)
        new high + trend weakening     -> SHORT     (fade)

    THE HYPOTHESIS IS THE INTERACTION, not "ADX works": a price extreme means opposite things
    depending on whether trend strength is building or decaying. That is falsifiable in a way
    "trade with the trend" is not, which is why it clears the economic-prior gate as a NAMED
    mechanism rather than a statistical find.

    WHAT IS OURS AND NOT DAVEY'S, stated so no reader mistakes it for his: the published system
    is stop-and-reverse with no fixed stop, which this desk's engine cannot express -- every
    sleeve here is sized from a stop. The stop is therefore an ATR-based structural distance and
    the exit an rr target plus a TTL, matching how every other family on this desk is judged.
    The stop-and-reverse management rule is a SEPARATE challenger, not smuggled in here.
    """
    h1 = _h1(df)
    if len(h1) < max(channel, adx_n + adx_lag) + 5:
        return []
    atr = _atr(h1, atr_n)
    adx = _adx(h1, adx_n)
    close = h1["close"]
    hi = close.rolling(channel, min_periods=channel).max()
    lo = close.rolling(channel, min_periods=channel).min()
    strengthening = adx >= adx.shift(adx_lag)

    c, a = close.to_numpy(), atr.to_numpy()
    hi_a, lo_a = hi.to_numpy(), lo.to_numpy()
    st = strengthening.to_numpy()
    ok = (~np.isnan(adx.to_numpy())) & (~np.isnan(hi_a)) & (~np.isnan(a))

    signals: list[Signal] = []
    last_side = 0
    for i in range(len(h1) - 2):
        if not ok[i] or not (a[i] > 0):
            continue
        at_high = c[i] >= hi_a[i]
        at_low = c[i] <= lo_a[i]
        if not (at_high or at_low):
            continue
        if at_high and at_low:
            continue                      # a flat channel is not an extreme
        # The interaction table above, in one expression: an extreme is followed when trend
        # strength is building and faded when it is decaying.
        side = 1 if (at_high == bool(st[i])) else -1
        # STATE TRANSITIONS ONLY. Davey's published system is STOP-AND-REVERSE: it holds exactly
        # one position and flips it, so a signal exists when the implied side CHANGES -- not on
        # every bar that happens to sit at an extreme. Firing on every such bar is not a stricter
        # reading of his rule, it is a different and much heavier-trading strategy: measured, it
        # produced 8,484 signals and 3,359 trades on XAUUSD alone, and the cost of that turnover
        # is most of what it lost. Emitting on the flip is the faithful transfer.
        if side == last_side:
            continue
        last_side = side
        # ENTRY IS THE NEXT BAR'S OPEN, as published -- `trigger=None` is exactly that on this
        # engine, so no resting order and no intrabar fill assumption.
        entry = h1["open"].to_numpy()[i + 1]
        if not (entry > 0):
            continue
        stop_dist = stop_atr * a[i]
        stop = entry - side * stop_dist
        target = entry + side * stop_dist * rr
        signals.append(Signal(time=h1.index[i + 1], side=side, stop=stop, target=target,
                              ttl_bars=ttl_bars, tag="adx_channel_hybrid"))
    return signals
