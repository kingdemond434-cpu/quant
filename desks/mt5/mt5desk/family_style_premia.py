"""AQR's style premia as one family with six styles, each an economic claim on MT5 instruments.

    trend       multi-horizon vol-scaled time-series momentum (the manifold, not one rule)
    carry       the instrument's own rollover: Fusion's swap differential, signed
    value       long-horizon deviation of log price from its own slow mean (reverts)
    defensive   low beta to the risk driver pays: long when the instrument's beta to the
                equity/risk factor is in its own low percentile, short when high (BAB)
    volatility  realised-vol mean reversion: fade a vol spike, follow a vol expansion from
                a compression
    momentum    12-1 style: past 252-bar return excluding the last 21 bars, vol-scaled

and their public COMBINATIONS as a second axis: carry x momentum, carry conditioned on calm
vol, trend x defensive. Everything is scaled by the instrument's own history so the desk never
compares gold to a JPY cross in points. The desk's expected result is that most styles fail the
MT5 cost gauntlet on most instruments -- AQR's premia are harvested at institutional cost -- and
the ones that survive are diversifiers the breakout book does not have.

INPUTS. `swap_diff` (points, long minus short) for carry; `risk` driver bars for defensive.
Both are resolved by `family_inputs`; without them those styles refuse rather than guess.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from mt5desk.families import Signal, _atr, _h1

STYLES = ("trend", "carry", "value", "defensive", "volatility", "momentum")
COMBOS = ("carry_x_momentum", "carry_calm_vol", "trend_x_defensive")


def _z(s: pd.Series, w: int) -> pd.Series:
    r = s.rolling(w, min_periods=w)
    return (s - r.mean()) / r.std()


def _score(d: pd.DataFrame, style: str, *, swap_diff: float | None, risk: pd.DataFrame | None,
           speeds: tuple[int, ...]) -> pd.Series | None:
    c = d["close"].astype(float)
    lr = np.log(c)
    ret = lr.diff()
    vol = ret.rolling(48, min_periods=24).std()
    if style == "trend":
        parts = [((lr - lr.shift(h)) / (vol * np.sqrt(h))).clip(-3, 3) for h in speeds]
        return sum(parts) / len(parts)
    if style == "momentum":
        return ((lr.shift(21) - lr.shift(252)) / (vol * np.sqrt(231))).clip(-3, 3)
    if style == "value":
        slow = lr.rolling(1000, min_periods=500).mean()
        return -_z(lr - slow, 500)                             # cheap vs its own history: long
    if style == "volatility":
        vz = _z(vol, 240)
        return -vz.where(vz > 0, 0.0) * np.sign(ret.rolling(6).sum())   # fade the move on spike
    if style == "carry":
        if swap_diff is None:
            return None
        sign = float(np.sign(swap_diff))
        return pd.Series(sign * min(abs(float(swap_diff)) / 10.0, 3.0), index=d.index)
    if style == "defensive":
        if risk is None or "close" not in risk.columns:
            return None
        rc = risk["close"].astype(float)
        rc.index = pd.DatetimeIndex(pd.to_datetime(rc.index, utc=True, errors="coerce"))
        rr = np.log(rc[~rc.index.duplicated(keep="last")].sort_index()).diff()
        rr = rr.reindex(d.index).fillna(0.0)
        cov = ret.rolling(120, min_periods=60).cov(rr)
        var = rr.rolling(120, min_periods=60).var()
        beta = cov / var.where(var > 1e-18)
        b_rank = beta.rolling(500, min_periods=250).rank(pct=True)
        return (0.5 - b_rank) * 4.0                            # low beta: long; high beta: short
    return None


def family_style_premia(
    df: pd.DataFrame,
    *,
    style: str = "trend",
    combo: str | None = None,
    swap_diff: float | None = None,
    risk: pd.DataFrame | None = None,
    speeds: tuple[int, ...] = (24, 120, 480),
    entry: float = 1.0,
    hold_bars: int = 24,
    atr_n: int = 20,
    stop_atr: float = 2.5,
    rr: float = 1.5,
) -> list[Signal]:
    if style not in STYLES or (combo is not None and combo not in COMBOS):
        return []
    d = _h1(df)
    if len(d) < 1500:
        return []
    s = _score(d, style, swap_diff=swap_diff, risk=risk, speeds=speeds)
    if s is None:
        return []
    if combo == "carry_x_momentum":
        m = _score(d, "momentum", swap_diff=None, risk=None, speeds=speeds)
        cs = _score(d, "carry", swap_diff=swap_diff, risk=None, speeds=speeds)
        if m is None or cs is None:
            return []
        s = 0.5 * (cs + m)
    elif combo == "carry_calm_vol":
        cs = _score(d, "carry", swap_diff=swap_diff, risk=None, speeds=speeds)
        if cs is None:
            return []
        vz = _z(np.log(d["close"].astype(float)).diff().rolling(48, min_periods=24).std(), 240)
        s = cs.where(vz < 0.5, 0.0)
    elif combo == "trend_x_defensive":
        t = _score(d, "trend", swap_diff=None, risk=None, speeds=speeds)
        de = _score(d, "defensive", swap_diff=None, risk=risk, speeds=speeds)
        if t is None or de is None:
            return []
        s = 0.5 * (t + de)
    sv = s.to_numpy(dtype=float)
    atr = _atr(d, atr_n).to_numpy(dtype=float)
    close = d["close"].to_numpy(dtype=float)
    idx = d.index
    # Daily decision: one look per day, at the last completed bar of the day, entering next open.
    day = pd.Series(idx.normalize(), index=idx)
    last_of_day = (day != day.shift(-1)).to_numpy()
    out: list[Signal] = []
    last = -10 ** 9
    for i in range(500, len(idx) - 1):
        if not last_of_day[i] or i - last < int(hold_bars):
            continue
        v, a = sv[i], atr[i]
        if not np.isfinite(v) or abs(v) < float(entry) or not np.isfinite(a) or a <= 0:
            continue
        side = int(np.sign(v))
        px = close[i]
        out.append(Signal(time=idx[i], side=side, stop=px - side * stop_atr * a,
                          target=px + side * stop_atr * a * rr, ttl_bars=int(hold_bars),
                          tag=f"style:{combo or style}", trigger=None, wait_bars=1))
        last = i
    return out
