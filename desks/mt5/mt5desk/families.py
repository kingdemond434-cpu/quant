"""Candidate signal generators for the MT5 research desk.

Seven families, priced not argued. Each generator is a pure function
(closed bars in, signals out) so backtest == production path.

Family map (from the research brief):
  1. real-yield/USD shock conditioned by London/COMEX sessions
  2. CFTC gold positioning change / crowding unwind   (needs COT data: deferred)
  3. ETF-flow acceleration / flow-price disagreement  (needs WGC data: deferred)
  4. COMEX settlement/open effects conditioned on vol/liquidity
  5. CPI/NFP/FOMC event continuation vs reversal      (needs timestamped surprises: deferred)
  6. GC futures-spot divergence / futures-curve state (needs GC feed: deferred)
  7. broker spread/swap-state avoidance
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from mt5desk.engine import Signal


def _atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    h, l, c = df["high"], df["low"], df["close"]
    tr = pd.concat(
        [h - l, (h - c.shift(1)).abs(), (l - c.shift(1)).abs()], axis=1
    ).max(axis=1)
    return tr.ewm(alpha=1 / n, min_periods=n).mean()


def _h1(df: pd.DataFrame) -> pd.DataFrame:
    """Resample to H1 and drop gap rows so rolling stats see only real bars."""
    h1 = df.resample("1h").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}
    )
    if "spread" in df.columns:
        h1["spread"] = df["spread"].resample("1h").mean()
    return h1.dropna(subset=["close"])


def family1_usd_session_shock(
    df: pd.DataFrame,
    fx: pd.DataFrame | None,
    *,
    london_start: int = 7,
    london_end: int = 16,
    shock_atr: float = 2.0,
    atr_n: int = 20,
    ttl_bars: int = 12,
    rr: float = 1.8,
) -> list[Signal]:
    """USD impulse (EURUSD drop = USD up = gold down) taken only inside London/NY.

    Condition on the 1H EURUSD bar: a 1H move beyond `shock_atr` std is a
    genuine impulse; gold reacts anti-correlated. Only fires in active sessions.
    """
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
        std = fr[i] * np.sqrt(1)
        if not (std > 0):
            continue
        impulse = fm[i] > shock_atr * std
        if not impulse:
            continue
        ai = a[i]
        if not (ai > 0):
            continue
        # gold anti-correlates with USD: USD up (EUR down) -> gold down
        side = 1 if fxc[i] < fxc[i - 1] else -1
        stop_dist = 1.2 * ai
        entry = c[i]
        stop = entry - side * stop_dist
        target = entry + side * stop_dist * rr
        signals.append(Signal(time=ts, side=side, stop=stop, target=target,
                              ttl_bars=ttl_bars, tag="usd_session_shock"))
    return signals


def family4_comex_settlement_effect(
    df: pd.DataFrame,
    *,
    settle_hour: int = 20,  # Vantage halts 21:00-22:00 UTC; 20:00 = pre-pause, 22:00 = post
    window_before: int = 2,
    vol_floor: float = 0.5,
    move_thresh: float = 0.75,
    ttl_bars: int = 12,
    rr: float = 1.6,
    atr_n: int = 20,
) -> list[Signal]:
    """Settlement/pause-window effects conditioned on volatility.

    Around the daily roll pause (21:00-22:00 UTC), measure whether the pre-
    window move continues when vol is elevated; fade it when vol is suppressed.
    """
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
            side = 1 if move > 0 else -1  # continuation under high vol
        elif not vol_high and abs(move) > move_thresh:
            side = -1 if move > 0 else 1  # fade under low vol
        if side == 0:
            continue
        entry = o[i]
        stop_dist = 1.2 * ai
        stop = entry - side * stop_dist
        target = entry + side * stop_dist * rr
        signals.append(Signal(time=ts, side=side, stop=stop, target=target,
                              ttl_bars=ttl_bars, tag="comex_settlement_effect"))
    return signals


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
    """Trade Asia-session direction into London: net Asia move, entered at 08:00."""
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


def family_dow_effect(
    df: pd.DataFrame,
    *,
    dow_long: int = 0,  # Monday
    dow_short: int = 3,  # Thursday
    atr_n: int = 20,
    ttl_bars: int = 12,
    rr: float = 1.8,
) -> list[Signal]:
    """Pre-registered day-of-week seasonality test (control family)."""
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


def family7_spread_state_avoidance(
    df: pd.DataFrame,
    *,
    spread_col: str = "spread",
    high_spread_frac: float = 0.5,
    ttl_bars: int = 10,
    rr: float = 1.8,
    atr_n: int = 20,
    mom_n: int = 4,
) -> list[Signal]:
    """Trade only when the venue's own spread is low (predictably bad periods removed).

    Uses the measured live spread column from the Vantage feed. The signal is a
    simple momentum push, but gated: when spread is in its top half, skip.
    """
    if spread_col not in df.columns:
        return []
    h1 = _h1(df)
    atr = _atr(h1, atr_n)
    spread_med = h1[spread_col].rolling(96).median()
    mom = h1["close"].pct_change(mom_n)
    sp = h1[spread_col].to_numpy()
    sm = spread_med.to_numpy()
    a = atr.to_numpy()
    m = mom.to_numpy()
    o = h1["open"].to_numpy()
    signals: list[Signal] = []
    for i in range(4, len(h1) - 2):
        ts = h1.index[i]
        if np.isnan(h1["close"].iloc[i]):
            continue
        ai = a[i]
        smi = sm[i]
        if not (ai > 0) or np.isnan(smi):
            continue
        if sp[i] > smi * (1 + high_spread_frac):
            continue
        mi = m[i]
        if abs(mi) < 0.0005:
            continue
        side = 1 if mi > 0 else -1
        entry = o[i + 1]
        stop_dist = 1.2 * ai
        stop = entry - side * stop_dist
        target = entry + side * stop_dist * rr
        signals.append(Signal(time=h1.index[i + 1], side=side, stop=stop,
                              target=target, ttl_bars=ttl_bars,
                              tag="spread_state_avoidance"))
    return signals


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
    """Baseline: momentum gated by a volatility floor (control, not a family)."""
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
        # vol-scaled: the move must exceed 0.35x ATR% so noise can't pass
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
) -> list[Signal]:
    """Session-range breakout as a resting bracket.

    Range window: hours [0, range_start) if range_end is None, else
    [range_start, range_end). At hour == signal_at (default: range_start /
    range_end) a bracket is placed: long stop above the range high, short stop
    below the range low. Whichever level price trades through first (within
    `wait_bars` bars) fills, mirroring a real stop order.

    spread_gate: skip days whose current spread is above its own 96-bar median
    (tighter-cost subset of the same pattern).

    trend_filter="aligned": keep only the leg aligned with the EMA20 slope at
    signal time (buy leg if slope >= 0, sell leg otherwise) - one-sided.

    range_filter="small"/"large": trade only days whose range span is below /
    above the rolling 20-day median span.

    vol_filter="low"/"high": trade only days whose ATR is below / above the
    rolling 200-bar ATR median.
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
        dist = max(1.2 * a, span)
        if trend_filter != "aligned" or slope >= 0:
            signals.append(Signal(time=ts, side=1, stop=hi - dist, target=hi + dist * rr,
                                  ttl_bars=ttl_bars, tag="session_range_breakout",
                                  trigger=hi, wait_bars=wait_bars))
        if trend_filter != "aligned" or slope < 0:
            signals.append(Signal(time=ts, side=-1, stop=lo + dist, target=lo - dist * rr,
                                  ttl_bars=ttl_bars, tag="session_range_breakout",
                                  trigger=lo, wait_bars=wait_bars))
    return signals


def family_monday_gap(
    df: pd.DataFrame,
    *,
    atr_n: int = 20,
    ttl_bars: int = 12,
    rr: float = 1.8,
    mode: str = "momentum",
    min_gap_atr: float = 0.2,
) -> list[Signal]:
    """Weekend gap (Sunday 22:00 open vs Friday close): momentum or fade."""
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


def family_london_close_momentum(
    df: pd.DataFrame,
    *,
    lookback: int = 2,
    atr_n: int = 20,
    mom_thresh: float = 0.3,
    ttl_bars: int = 4,
    rr: float = 1.5,
) -> list[Signal]:
    """14:00-16:00 momentum entered at 17:00, exited by 20:00 (pre-pause)."""
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


def family_level_breakout(
    df: pd.DataFrame,
    *,
    level: str = "pdh",          # "pdh" = prior-day high/low, "week" = prior week
    signal_hour: int = 7,
    wait_bars: int = 12,
    atr_n: int = 20,
    ttl_bars: int = 12,
    rr: float = 2.0,
    vol_filter: str = "all",     # "high": trade only vol-expansion days
    vol_gate_q: float = 0.75,    # ATR > q * rolling 200-bar median
    range_filter: str = "all",   # "small": trade only compressed prior ranges
    spread_gate: bool = False,
) -> list[Signal]:
    """Structural level breakout: prior-day (or prior-week) high/low as a
    resting bracket at `signal_hour`. Reverse-engineered from the public
    Gold breakout-EA family (Goldtrade/Reaper): important level -> range
    state -> expansion -> confirmed break -> runner. Same execution geometry
    as the armed session-range family (dist = max(1.2*ATR, span)).
    """
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
            continue  # week bracket armed once, Monday
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
    """Failed-breakout fade: price pierces the prior-day extreme on a closed
    bar but closes back inside (no displacement/follow-through) -> fade back
    into the range at the next bar open. The Gold Reaper "fake breakout
    filter" turned into a falsifiable rule. Entry next open (no intrabar).
    """
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
            side = -1  # broke above, closed back inside -> fade short
            pierce = hh[i] - phi
        elif ll[i] < plo and c[i] > plo and plo > 0:
            side = 1  # broke below, closed back inside -> fade long
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
    """Turn a per-report side series (-1/0/1) into Monday-open signals.

    COT is published Friday ~19:30 UTC; positions are as of the Tuesday
    report date. Entries go in at the open of the first H1 bar after the
    following Monday 00:00 UTC. Weekly cadence -> no overlapping reports.
    """
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


def family2_cot_net_fade(
    df: pd.DataFrame,
    cot: pd.DataFrame,
    *,
    lookback_weeks: int = 104,
    lo_q: float = 0.10,
    hi_q: float = 0.90,
) -> list[Signal]:
    """Fade extreme fund (noncomm) net positioning: crowding mean-reversion."""
    cot = cot.sort_values("report_date").reset_index(drop=True)
    net = cot["noncomm_positions_long_all"] - cot["noncomm_positions_short_all"]
    pct = net.rolling(lookback_weeks, min_periods=lookback_weeks).rank(pct=True)
    side = pd.Series(0, index=cot.index)
    side[pct > hi_q] = -1
    side[pct < lo_q] = 1
    return _cot_entries(_h1(df), cot, side, "cot_net_fade")


def family2_cot_change_fade(
    df: pd.DataFrame,
    cot: pd.DataFrame,
    *,
    lookback_weeks: int = 52,
    z_thresh: float = 1.5,
) -> list[Signal]:
    """Fade large weekly fund net-position CHANGES (crowding unwind)."""
    cot = cot.sort_values("report_date").reset_index(drop=True)
    net = cot["noncomm_positions_long_all"] - cot["noncomm_positions_short_all"]
    delta = net.diff()
    z = (delta - delta.rolling(lookback_weeks, min_periods=lookback_weeks).mean()
         ) / delta.rolling(lookback_weeks, min_periods=lookback_weeks).std()
    side = pd.Series(0, index=cot.index)
    side[z.abs() > z_thresh] = -np.sign(delta[z.abs() > z_thresh])
    side = side.astype(int)
    return _cot_entries(_h1(df), cot, side, "cot_change_fade")


def family2_cot_change_momentum(
    df: pd.DataFrame,
    cot: pd.DataFrame,
) -> list[Signal]:
    """Control: trade WITH weekly fund net-position changes."""
    cot = cot.sort_values("report_date").reset_index(drop=True)
    net = cot["noncomm_positions_long_all"] - cot["noncomm_positions_short_all"]
    delta = net.diff()
    side = pd.Series(0, index=cot.index)
    side[delta > 0] = 1
    side[delta < 0] = -1
    return _cot_entries(_h1(df), cot, side, "cot_change_momentum")


def family2_cot_comm_follow(
    df: pd.DataFrame,
    cot: pd.DataFrame,
) -> list[Signal]:
    """Follow commercial net-position changes (the informed counterparty)."""
    cot = cot.sort_values("report_date").reset_index(drop=True)
    comm_net = (
        cot["comm_positions_long_all"] - cot["comm_positions_short_all"]
    )
    delta = comm_net.diff()
    side = pd.Series(0, index=cot.index)
    side[delta > 0] = 1
    side[delta < 0] = -1
    return _cot_entries(_h1(df), cot, side, "cot_comm_follow")