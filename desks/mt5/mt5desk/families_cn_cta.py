"""THE CHINESE FUTURES CTA CANON, WHICH THE DESK COULD NOT EXPRESS (2026-09-30).

Absorbed from github.com/thuquant/awesome-quant (MIT, Tsinghua's curated Chinese quant list) and
the strategy collections it links (myquant/strategy, botvs/strategies, vn.py's CTA strategies,
the JoinQuant / Ricequant / Uqer communities). Four intraday systems are the shared vocabulary of
Chinese futures retail and small CTAs -- taught on every platform, run in the 期货日报 live
competitions -- and none had a family here, so the cell emitter reading vn.py's
`dual_thrust_strategy.py` or `king_keltner_strategy.py` had nothing to map them onto.

    dual_thrust   Michael Chalek's Dual Thrust as adopted by the CN futures canon: the day's
                  range is max(HH-LC, HC-LL) over N days; long on a close above today's open +
                  k1*range, short below open - k2*range; flat by the day's end.
    r_breaker     R-Breaker (a top-ranked Futures Truth system, a staple of CN index-futures
                  teaching): six pivot levels off yesterday's H/L/C. `trend` follows a break of
                  the outer levels; `reversal` fades a day that pierced a setup level and closed
                  back through its entry level.
    sky_garden    空中花园: a gap of `gap_pct` at the day's open, confirmed when a later bar closes
                  beyond the FIRST bar's extreme in the gap's direction; flat by the day's end.
    king_keltner  King Keltner: typical-price MA +- ATR channel; long above, short below, only in
                  the channel's slope direction; exits on the MA (encoded as the stop).

WHY THEY ARE ORTHOGONAL HERE, and it is a participant claim rather than a code claim: these rules
are what CN retail and small CTAs actually run on SHFE / DCE / CFFEX, so their collective stops
and entries are a FLOW that shows up in the offshore analogues -- XAUUSD (SHFE gold), USDCNH,
China50 / HK50 (CFFEX IF/IH), copper and oil (SHFE, INE). They fail when that crowd is absent
(Golden Week, the CN session closed) rather than when a Western trend or carry book fails.

Signals are causal bar-close crossings (no resting OCO pair, which a single-position engine would
fill in list order rather than time order); the engine enters at the next bar's open. Every
family is flat by the day's last bar through its TTL. Price only.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from mt5desk.families import Signal, _atr, _h1, bars_per_day


def _day_frame(h: pd.DataFrame) -> tuple[np.ndarray, pd.DataFrame, np.ndarray]:
    """Per bar: its day index; per day: O/H/L/C; per bar: bars left in its day (incl. itself).

    Bars left come from the CLOCK (bars per day minus the bar's position), never from counting
    the day's later bars: on the live edge the newest bar is the last one in the frame, and a
    count would read "no bar left today" on every live decision."""
    dates = pd.Index(h.index.date)
    codes, uniq = pd.factorize(dates)
    g = h.groupby(codes)
    day = pd.DataFrame({"open": g["open"].first(), "high": g["high"].max(),
                        "low": g["low"].min(), "close": g["close"].last()})
    pos = h.groupby(codes).cumcount().to_numpy()
    left = np.maximum(bars_per_day(h) - pos, 1)
    return codes, day, left


def _emit(h: pd.DataFrame, fire: np.ndarray, side: np.ndarray, atr: np.ndarray, left: np.ndarray,
          codes: np.ndarray, *, stop_atr: float, rr: float, tag: str,
          stop_px: np.ndarray | None = None, one_per_day: bool = True) -> list[Signal]:
    close = h["close"].to_numpy(dtype=float)
    out: list[Signal] = []
    used: set[int] = set()
    for i in np.flatnonzero(fire):
        if i >= len(h) - 1 or left[i] <= 1:            # no bar left today to trade in
            continue
        s = int(side[i])
        if s == 0 or (one_per_day and int(codes[i]) in used):
            continue
        a, px = float(atr[i]), float(close[i])
        if not (np.isfinite(a) and a > 0 and px > 0):
            continue
        stop = px - s * stop_atr * a
        if stop_px is not None and np.isfinite(stop_px[i]) and (px - stop_px[i]) * s > 0:
            stop = float(stop_px[i])
        dist = abs(px - stop)
        out.append(Signal(time=h.index[i], side=s, stop=stop, target=px + s * dist * rr,
                          ttl_bars=int(left[i] - 1), tag=tag))
        used.add(int(codes[i]))
    return out


def _prev_cross(x: np.ndarray, level: np.ndarray, up: bool) -> np.ndarray:
    prev = np.concatenate(([np.nan], x[:-1]))
    lp = np.concatenate(([np.nan], level[:-1]))
    return (x > level) & (prev <= lp) if up else (x < level) & (prev >= lp)


def family_dual_thrust(df: pd.DataFrame, *, n_days: int = 4, k1: float = 0.5, k2: float = 0.5,
                       mode: str = "follow", atr_n: int = 20, stop_atr: float = 1.5,
                       rr: float = 2.0) -> list[Signal]:
    """`follow` is the canon; `fade` sells the crowd's breakout. The first local screen (2026-09-30,
    32 symbols) printed 41 cells below t=-2 against 5.7 expected, concentrated in managed or thin
    crosses (EURCHF, AUDHUF, AUDSGD, USDCHF): there the crowd's breakout is the liquidity."""
    if mode not in ("follow", "fade"):
        return []
    h = _h1(df)
    if len(h) < 24 * (n_days + 30):
        return []
    codes, day, left = _day_frame(h)
    hh = day["high"].rolling(n_days).max().shift(1)
    ll = day["low"].rolling(n_days).min().shift(1)
    hc = day["close"].rolling(n_days).max().shift(1)
    lc = day["close"].rolling(n_days).min().shift(1)
    rng = np.maximum(hh - lc, hc - ll).to_numpy()
    op = day["open"].to_numpy()
    up_lvl = (op + k1 * rng)[codes]
    dn_lvl = (op - k2 * rng)[codes]
    c = h["close"].to_numpy(dtype=float)
    long_ = _prev_cross(c, up_lvl, True)
    short = _prev_cross(c, dn_lvl, False)
    side = np.where(long_, 1, np.where(short, -1, 0)) * (1 if mode == "follow" else -1)
    return _emit(h, side != 0, side, _atr(h, atr_n).to_numpy(), left, codes, stop_atr=stop_atr,
                 rr=rr, tag=f"dual_thrust:{mode}:{n_days}:{k1:g}/{k2:g}")


def family_r_breaker(df: pd.DataFrame, *, mode: str = "trend", break_k: float = 0.25,
                     atr_n: int = 20, stop_atr: float = 1.5, rr: float = 1.5) -> list[Signal]:
    if mode not in ("trend", "reversal"):
        return []
    h = _h1(df)
    if len(h) < 24 * 30:
        return []
    codes, day, left = _day_frame(h)
    ph, pl, pc = (day[k].shift(1).to_numpy() for k in ("high", "low", "close"))
    p = (ph + pl + pc) / 3.0
    s_setup = p + (ph - pl)
    b_setup = p - (ph - pl)
    s_enter = 2 * p - pl
    b_enter = 2 * p - ph
    b_break = s_setup + break_k * (s_setup - b_setup)
    s_break = b_setup - break_k * (s_setup - b_setup)
    c = h["close"].to_numpy(dtype=float)
    atr = _atr(h, atr_n).to_numpy()
    if mode == "trend":
        long_ = _prev_cross(c, b_break[codes], True)
        short = _prev_cross(c, s_break[codes], False)
    else:
        # The day's running extreme up to and including this bar (causal within the day).
        run_hi = h["high"].groupby(codes).cummax().to_numpy()
        run_lo = h["low"].groupby(codes).cummin().to_numpy()
        short = (run_hi > s_setup[codes]) & _prev_cross(c, s_enter[codes], False)
        long_ = (run_lo < b_setup[codes]) & _prev_cross(c, b_enter[codes], True)
    side = np.where(long_, 1, np.where(short, -1, 0))
    return _emit(h, side != 0, side, atr, left, codes, stop_atr=stop_atr, rr=rr,
                 tag=f"r_breaker:{mode}")


def family_sky_garden(df: pd.DataFrame, *, gap_pct: float = 0.005, atr_n: int = 20,
                      stop_atr: float = 1.5, rr: float = 2.0) -> list[Signal]:
    h = _h1(df)
    if len(h) < 24 * 30 or gap_pct <= 0:
        return []
    codes, day, left = _day_frame(h)
    gap = (day["open"] / day["close"].shift(1) - 1.0).to_numpy()
    first = np.concatenate(([True], codes[1:] != codes[:-1]))
    fh = pd.Series(np.where(first, h["high"], np.nan)).ffill().to_numpy()
    fl = pd.Series(np.where(first, h["low"], np.nan)).ffill().to_numpy()
    c = h["close"].to_numpy(dtype=float)
    g = gap[codes]
    long_ = (~first) & (g >= gap_pct) & _prev_cross(c, fh, True)
    short = (~first) & (g <= -gap_pct) & _prev_cross(c, fl, False)
    side = np.where(long_, 1, np.where(short, -1, 0))
    return _emit(h, side != 0, side, _atr(h, atr_n).to_numpy(), left, codes, stop_atr=stop_atr,
                 rr=rr, tag=f"sky_garden:{gap_pct:g}")


def family_king_keltner(df: pd.DataFrame, *, n: int = 20, k: float = 1.5, atr_n: int = 20,
                        rr: float = 2.0, ttl_bars: int = 24) -> list[Signal]:
    h = _h1(df)
    if len(h) < n * 5 + 50:
        return []
    tp = (h["high"] + h["low"] + h["close"]) / 3.0
    ma = tp.rolling(n).mean()
    atr = _atr(h, atr_n)
    up_ = (ma + k * atr).to_numpy()
    dn = (ma - k * atr).to_numpy()
    slope = ma.diff().to_numpy()
    c = h["close"].to_numpy(dtype=float)
    long_ = _prev_cross(c, up_, True) & (slope > 0)
    short = _prev_cross(c, dn, False) & (slope < 0)
    side = np.where(long_, 1, np.where(short, -1, 0))
    a = atr.to_numpy()
    mav = ma.to_numpy()
    out: list[Signal] = []
    for i in np.flatnonzero(side):
        if i >= len(h) - 1 or not (np.isfinite(a[i]) and a[i] > 0 and np.isfinite(mav[i])):
            continue
        s = int(side[i])
        px = float(c[i])
        stop = float(mav[i]) if (px - mav[i]) * s > 0.25 * a[i] else px - s * a[i]
        out.append(Signal(time=h.index[i], side=s, stop=stop,
                          target=px + s * abs(px - stop) * rr, ttl_bars=ttl_bars,
                          tag=f"king_keltner:{n}:{k:g}"))
    return out


CN_CTA_FAMILIES = {
    "dual_thrust": family_dual_thrust,
    "r_breaker": family_r_breaker,
    "sky_garden": family_sky_garden,
    "king_keltner": family_king_keltner,
}

PARAM_GRID: dict[str, dict[str, list]] = {
    "dual_thrust": {"n_days": [2, 4], "k1": [0.4, 0.7], "k2": [0.4, 0.7],
                    "mode": ["follow", "fade"]},
    "r_breaker": {"mode": ["trend", "reversal"], "break_k": [0.2, 0.35]},
    "sky_garden": {"gap_pct": [0.002, 0.005, 0.01]},
    "king_keltner": {"n": [20, 40], "k": [1.0, 1.5, 2.0]},
}

#: The MT5 analogues of the CN contracts this crowd trades, seeded first.
CN_ANALOGUES: tuple[str, ...] = ("USDCNH", "XAUUSD", "XAGUSD", "China50", "CHINA50", "CHINAH",
                                 "HK50", "HSI", "XCUUSD", "COPPER", "XTIUSD", "XBRUSD", "USOIL",
                                 "UKOIL", "XPTUSD", "XPDUSD", "AUDUSD", "AUDJPY")

_CN = {"source_culture": "CN/zh", "participant_structure": "retail_heavy", "crowding_prior": "low"}
CULTURE: dict[str, dict[str, str]] = {
    "dual_thrust": {**_CN, "failure_mode_hypothesis": (
        "fails when the CN futures crowd is absent (Golden Week, CN session shut), not when a "
        "Western session breakout fails")},
    "r_breaker": {**_CN, "failure_mode_hypothesis": (
        "pivot levels are CN index-futures retail stops; fails on days driven by an offshore "
        "shock the onshore crowd did not trade")},
    "sky_garden": {**_CN, "failure_mode_hypothesis": (
        "a CN open-gap follow-through; fails when the gap is a Western overnight repricing the "
        "onshore crowd fades")},
    "king_keltner": {**_CN, "crowding_prior": "medium", "failure_mode_hypothesis": (
        "channel breakout run by CN small CTAs; fails in the same chop as any breakout but on "
        "CN-crowd days, which a US-session breakout book does not share")},
}
