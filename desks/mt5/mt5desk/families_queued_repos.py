"""NINE MECHANISMS FROM THE QUEUED REPOSITORIES THE DESK COULD NOT EXPRESS (2026-10-06).

Read from the cards in `/mnt/project-files/mining/queued_repos/cards_{A,B}.json` (the repositories
the principal queued for the EliteQuant thread). Every rule is written fresh, causally, for MT5
bars; nothing is copied from the upstream code:

    waditu/czsc (Apache-2.0, CN Chan-theory signal library)
      td_setup_exhaustion   QR-A-CZSC-007: nine closes in a row beyond the close four bars back
                            is a setup that exhausts; fade it, stop past the setup's extreme.
      volume_climax_fade    QR-A-CZSC-003: the three heaviest tick-volume bars of the last ten all
                            in the top fifth of the prior 300 bars is a climax; fade the move.
      range_trap_reclaim    QR-A-CZSC-002: a full-overlap box, a break below it that closes back
                            inside, then a new 20-bar high: the trapped breakers fuel the reclaim.
      overlap_box_breakout  QR-A-CZSC-004: five bars sharing one common price band, then a close
                            outside every one of them.
      quiet_grind           QR-A-CZSC-009: a D1 trend made of small bars that keep setting new
                            lows (highs) without one violent bar is followed, not faded.
      ribbon_release        QR-A-CZSC-008: an SMA 5/13/21/34/55 ribbon compressed for 16 of 20
                            bars, whose dispersion then leaves the compressed band, is
                            followed in the direction it opens.
    shinnytech/tqsdk-python (Apache-2.0, CN futures SDK demos)
      escalator             QR-A-TQ-002: above SMA8 and SMA40, a bar that closed in its bottom
                            quarter followed by one that closed in its top quarter.
    LLMQuant/quant-wiki (no licence, CN wiki; the idea only)
      payday_dom            QR-A-QW-001: index long from the close of the 15th (the Friday before
                            when the 15th is a weekend) to the next close.
    quant-science/sunday-quant-scientist (no licence; the idea only)
      rare_losing_streak    B-SQS-02: the first three-day losing streak in an index after 42
                            trading days without one is bought for five days.

All are price-only (`volume_climax_fade` reads the bars' own tick_volume). Signals fire at a bar's
close and the engine fills at the next open; the daily rules decide on the day's last bar.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from mt5desk.engine import Signal
from mt5desk.families import _atr, _h1, bars_per_day


def _sig(h: pd.DataFrame, i: int, side: int, stop: float, rr: float, ttl: int,
         tag: str) -> Signal | None:
    px = float(h["close"].iloc[i])
    risk = (px - stop) * side
    if not (math.isfinite(px) and math.isfinite(stop) and risk > 0):
        return None
    return Signal(time=h.index[i], side=int(side), stop=float(stop),
                  target=px + side * rr * risk, ttl_bars=int(ttl), tag=tag)


def _ok(x: float) -> bool:
    return math.isfinite(x) and x > 0


# --------------------------------------------------------------------- czsc: TD setup ---------
def family_td_setup_exhaustion(df: pd.DataFrame, *, count: int = 9, lag: int = 4,
                               atr_n: int = 20, pad_atr: float = 0.25, rr: float = 1.5,
                               ttl_bars: int = 4) -> list[Signal]:
    """Fade a completed `count`-bar run of closes beyond the close `lag` bars earlier."""
    h = _h1(df)
    if len(h) < count + lag + atr_n + 2:
        return []
    c = h["close"].to_numpy(dtype=float)
    hi, lo = h["high"].to_numpy(dtype=float), h["low"].to_numpy(dtype=float)
    atr = _atr(h, atr_n).to_numpy()
    s = np.zeros(len(c), dtype=int)
    s[lag:] = np.sign(c[lag:] - c[:-lag]).astype(int)
    out: list[Signal] = []
    run, busy = 0, -1
    for i in range(lag, len(c) - 1):
        run = run + 1 if s[i] != 0 and s[i] == s[i - 1] else (1 if s[i] != 0 else 0)
        if run != count or i <= busy or i < atr_n or not _ok(float(atr[i])):
            continue
        side = -int(s[i])
        ext = hi[i - count + 1:i + 1].max() if side < 0 else lo[i - count + 1:i + 1].min()
        sig = _sig(h, i, side, ext - side * pad_atr * float(atr[i]), rr, ttl_bars,
                   f"td_setup_exhaustion:{count}")
        if sig:
            out.append(sig)
            busy = i + ttl_bars
    return out


# --------------------------------------------------------------- czsc: volume climax ---------
def family_volume_climax_fade(df: pd.DataFrame, *, lookback: int = 10, base: int = 300,
                              q: float = 0.80, top: int = 3, atr_n: int = 20,
                              stop_atr: float = 1.5, rr: float = 1.5,
                              ttl_bars: int = 12) -> list[Signal]:
    """Fade the last `lookback` bars' move when their `top` heaviest bars are all climax volume."""
    h = _h1(df)
    if "tick_volume" not in h.columns or len(h) < base + lookback + 2:
        return []
    v = h["tick_volume"].to_numpy(dtype=float)
    if not np.isfinite(v).all() or v.max() <= 0:
        return []
    c = h["close"].to_numpy(dtype=float)
    atr = _atr(h, atr_n).to_numpy()
    # the prior `base` bars' quantile, ending before the climax window starts
    thr = pd.Series(v).rolling(base).quantile(q).shift(lookback).to_numpy()
    win = np.lib.stride_tricks.sliding_window_view(v, lookback)
    kth = np.full(len(v), np.nan)
    kth[lookback - 1:] = np.partition(win, lookback - top, axis=1)[:, lookback - top]
    hot = kth > thr
    out: list[Signal] = []
    busy = -1
    for i in np.flatnonzero(hot):
        if i <= busy or i < lookback or i >= len(c) - 1 or not _ok(float(atr[i])):
            continue
        side = -int(np.sign(c[i] - c[i - lookback]))
        if side == 0:
            continue
        sig = _sig(h, int(i), side, c[i] - side * stop_atr * float(atr[i]), rr, ttl_bars,
                   f"volume_climax_fade:{q:g}")
        if sig:
            out.append(sig)
            busy = int(i) + ttl_bars
    return out


# ---------------------------------------------------------- czsc: overlap boxes ---------------
def _boxes(h: pd.DataFrame, m: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """For each bar e: the m bars ending at e share a common band (max low <= min high), and
    that band's floor DD and ceiling GG."""
    dd = h["low"].rolling(m).max().to_numpy()
    gg = h["high"].rolling(m).min().to_numpy()
    return dd <= gg, dd, gg


def family_range_trap_reclaim(df: pd.DataFrame, *, n: int = 20, m: int = 5, atr_n: int = 20,
                              pad_atr: float = 0.25, rr: float = 1.5,
                              ttl_bars: int = 24) -> list[Signal]:
    """After a false break out of an overlap box, follow the bar that makes a new n-bar extreme
    the other way."""
    h = _h1(df)
    if len(h) < n + m + atr_n + 2:
        return []
    o, c = h["open"].to_numpy(dtype=float), h["close"].to_numpy(dtype=float)
    hi, lo = h["high"].to_numpy(dtype=float), h["low"].to_numpy(dtype=float)
    atr = _atr(h, atr_n).to_numpy()
    box, dd, gg = _boxes(h, m)
    prior_hi = pd.Series(hi).rolling(n).max().shift(1).to_numpy()
    prior_lo = pd.Series(lo).rolling(n).min().shift(1).to_numpy()
    last_box = pd.Series(np.where(box, np.arange(len(c)), np.nan)).ffill().shift(1).to_numpy()
    out: list[Signal] = []
    busy = -1
    for i in range(n + m, len(c) - 1):
        up = c[i] > o[i] and hi[i] > prior_hi[i]
        dn = c[i] < o[i] and lo[i] < prior_lo[i]
        if not (up or dn) or i <= busy or not np.isfinite(last_box[i]):
            continue
        e = int(last_box[i])
        if e < i - n or e >= i - 1 or not _ok(float(atr[i])):
            continue
        after = slice(e + 1, i)
        side = 1 if up else -1
        if side > 0:
            broke = lo[after].min() < dd[e] and c[after][-1] > dd[e]
            stop = lo[after].min() - pad_atr * float(atr[i])
        else:
            broke = hi[after].max() > gg[e] and c[after][-1] < gg[e]
            stop = hi[after].max() + pad_atr * float(atr[i])
        if not broke:
            continue
        sig = _sig(h, i, side, stop, rr, ttl_bars, f"range_trap_reclaim:{n}")
        if sig:
            out.append(sig)
            busy = i + ttl_bars
    return out


def family_overlap_box_breakout(df: pd.DataFrame, *, m: int = 5, atr_n: int = 20,
                                rr: float = 2.0, ttl_bars: int = 24) -> list[Signal]:
    """Follow the first close outside every bar of an m-bar full-overlap box."""
    h = _h1(df)
    if len(h) < m + atr_n + 2:
        return []
    c = h["close"].to_numpy(dtype=float)
    box, _, _ = _boxes(h, m)
    top = h["high"].rolling(m).max().to_numpy()
    bot = h["low"].rolling(m).min().to_numpy()
    out: list[Signal] = []
    busy = -1
    for i in range(m + atr_n, len(c) - 1):
        j = i - 1                                             # the box ends on the prior bar
        if not box[j] or i <= busy:
            continue
        side = 1 if c[i] > top[j] else (-1 if c[i] < bot[j] else 0)
        if side == 0:
            continue
        stop = bot[j] if side > 0 else top[j]
        sig = _sig(h, i, side, stop, rr, ttl_bars, f"overlap_box_breakout:{m}")
        if sig:
            out.append(sig)
            busy = i + ttl_bars
    return out


# ------------------------------------------------------------------ daily helpers -------------
def _daily_ohlc(h: pd.DataFrame) -> tuple[pd.DataFrame, np.ndarray]:
    """Daily OHLC by the bars' own date, and each day's LAST bar index in `h`."""
    dates = pd.Index(h.index.date)
    last = np.flatnonzero(np.r_[dates[1:] != dates[:-1], True])
    g = h.groupby(dates)
    d = pd.DataFrame({"open": g["open"].first(), "high": g["high"].max(),
                      "low": g["low"].min(), "close": g["close"].last()})
    return d, last


def _daily_atr(d: pd.DataFrame, n: int) -> np.ndarray:
    prev = d["close"].shift(1)
    tr = pd.concat([d["high"] - d["low"], (d["high"] - prev).abs(), (d["low"] - prev).abs()],
                   axis=1).max(axis=1)
    return tr.rolling(n, min_periods=n).mean().to_numpy()


def _daily_signal(h: pd.DataFrame, last: np.ndarray, k: int, side: int, datr: np.ndarray, *,
                  stop_atr: float, rr: float, hold_days: int, tag: str) -> Signal | None:
    i = int(last[k])
    if i >= len(h) - 1 or not _ok(float(datr[k])):
        return None
    px = float(h["close"].iloc[i])
    return _sig(h, i, side, px - side * stop_atr * float(datr[k]), rr,
                hold_days * bars_per_day(h), tag)


# ------------------------------------------------------------------ czsc: quiet grind ---------
def family_quiet_grind(df: pd.DataFrame, *, n: int = 13, warm: int = 5, share: float = 0.8,
                       big_bp: float = 300.0, atr_n: int = 20, stop_atr: float = 2.0,
                       rr: float = 2.0, hold_days: int = 5) -> list[Signal]:
    """Follow a D1 trend whose last n bars keep printing new window extremes in small steps."""
    h = _h1(df)
    d, last = _daily_ohlc(h)
    if len(d) < n + warm + atr_n + 2:
        return []
    o, c = d["open"].to_numpy(dtype=float), d["close"].to_numpy(dtype=float)
    hi, lo = d["high"].to_numpy(dtype=float), d["low"].to_numpy(dtype=float)
    datr = _daily_atr(d, atr_n)
    big = np.abs(c / o - 1.0) > big_bp / 1e4
    out: list[Signal] = []
    busy = -1
    need = math.ceil(share * n)
    for k in range(n + warm, len(d)):
        if k <= busy:
            continue
        w0 = k - n - warm + 1
        if int(big[k - n + 1:k + 1].sum()) > max(0.2 * n, 3):
            continue
        cw = c[w0:k + 1]
        run_min = np.minimum.accumulate(cw)[:-1]              # min close of all prior bars
        run_max = np.maximum.accumulate(cw)[:-1]
        lows, highs = lo[w0 + 1:k + 1], hi[w0 + 1:k + 1]
        n_dn = int((lows[-n:] <= run_min[-n:]).sum())
        n_up = int((highs[-n:] >= run_max[-n:]).sum())
        side = -1 if n_dn >= need else (1 if n_up >= need else 0)
        if side == 0:
            continue
        sig = _daily_signal(h, last, k, side, datr, stop_atr=stop_atr, rr=rr,
                            hold_days=hold_days, tag=f"quiet_grind:{n}")
        if sig:
            out.append(sig)
            busy = k + hold_days
    return out


# ---------------------------------------------------------------- czsc: ribbon release --------
def family_ribbon_release(df: pd.DataFrame, *, spans: tuple[int, ...] = (5, 13, 21, 34, 55),
                          lookback: int = 100, ref: int = 80, recent: int = 20,
                          need: int = 16, release: float = 0.5, atr_n: int = 20,
                          stop_atr: float = 2.0, rr: float = 2.0,
                          ttl_bars: int = 24) -> list[Signal]:
    """Follow a compressed SMA ribbon the bar it starts expanding, in the direction it opens."""
    h = _h1(df)
    if len(h) < max(spans) + lookback + atr_n + 2:
        return []
    c = h["close"]
    mas = pd.concat([c.rolling(s).mean() for s in spans], axis=1)
    hi_ma, lo_ma = mas.max(axis=1), mas.min(axis=1)
    ret = (hi_ma / lo_ma - 1.0).to_numpy()
    # the dispersion's scale over the first `ref` of the last `lookback` bars
    sd = pd.Series(ret).shift(lookback - ref).rolling(ref).std().to_numpy()
    tight = pd.Series(ret < 0.5 * sd).rolling(recent).sum().to_numpy()
    cv = c.to_numpy(dtype=float)
    mid = mas.mean(axis=1).to_numpy()
    atr = _atr(h, atr_n).to_numpy()
    out: list[Signal] = []
    busy = -1
    for i in range(max(spans) + lookback, len(cv) - 1):
        if i <= busy or not (tight[i - 1] >= need and ret[i] >= release * sd[i]):
            continue
        side = 1 if cv[i] > hi_ma.iloc[i] else (-1 if cv[i] < lo_ma.iloc[i] else 0)
        if side == 0 or (cv[i] - mid[i]) * side <= 0 or not _ok(float(atr[i])):
            continue
        sig = _sig(h, i, side, cv[i] - side * stop_atr * float(atr[i]), rr, ttl_bars,
                   "ribbon_release")
        if sig:
            out.append(sig)
            busy = i + ttl_bars
    return out


# ------------------------------------------------------------------ tqsdk: escalator ----------
def family_escalator(df: pd.DataFrame, *, fast: int = 8, slow: int = 40, q: float = 0.25,
                     atr_n: int = 20, pad_atr: float = 0.1, rr: float = 2.0,
                     ttl_bars: int = 12) -> list[Signal]:
    """In a trend above (below) SMA fast and slow, buy a top-quarter close after a bottom-quarter
    one (mirror), stopped beyond the two bars' extreme."""
    h = _h1(df)
    if len(h) < slow + atr_n + 2:
        return []
    c = h["close"].to_numpy(dtype=float)
    hi, lo = h["high"].to_numpy(dtype=float), h["low"].to_numpy(dtype=float)
    rng = hi - lo
    clv = np.where(rng > 0, (c - lo) / np.where(rng > 0, rng, 1.0), np.nan)
    f = h["close"].rolling(fast).mean().to_numpy()
    s = h["close"].rolling(slow).mean().to_numpy()
    atr = _atr(h, atr_n).to_numpy()
    out: list[Signal] = []
    busy = -1
    for i in range(slow + 1, len(c) - 1):
        if i <= busy or not _ok(float(atr[i])):
            continue
        if c[i] > f[i] and c[i] > s[i] and clv[i - 1] <= q and clv[i] >= 1 - q:
            side, stop = 1, min(lo[i], lo[i - 1]) - pad_atr * float(atr[i])
        elif c[i] < f[i] and c[i] < s[i] and clv[i - 1] >= 1 - q and clv[i] <= q:
            side, stop = -1, max(hi[i], hi[i - 1]) + pad_atr * float(atr[i])
        else:
            continue
        sig = _sig(h, i, side, stop, rr, ttl_bars, f"escalator:{fast}:{slow}")
        if sig:
            out.append(sig)
            busy = i + ttl_bars
    return out


# ----------------------------------------------------------------- quant-wiki: payday ---------
def family_payday_dom(df: pd.DataFrame, *, dom: int = 15, atr_n: int = 20,
                      stop_atr: float = 3.0) -> list[Signal]:
    """Long from the close of the `dom`th (the Friday before when it is a weekend) to the next
    day's close. The date is a calendar fact, known at the decision bar."""
    h = _h1(df)
    d, last = _daily_ohlc(h)
    if len(d) < atr_n + 2:
        return []
    datr = _daily_atr(d, atr_n)
    out: list[Signal] = []
    for k, day in enumerate(d.index):
        wd = day.weekday()
        if not (day.day == dom or (wd == 4 and dom - 2 <= day.day < dom)):
            continue
        sig = _daily_signal(h, last, k, 1, datr, stop_atr=stop_atr, rr=10.0, hold_days=1,
                            tag=f"payday_dom:{dom}")
        if sig:
            out.append(sig)
    return out


# ------------------------------------------------- sunday-quant-scientist: rare streak --------
def family_rare_losing_streak(df: pd.DataFrame, *, streak: int = 3, gap: int = 42,
                              hold_days: int = 5, atr_n: int = 20,
                              stop_atr: float = 3.0) -> list[Signal]:
    """Buy the first `streak`-day losing streak after `gap` trading days without one."""
    h = _h1(df)
    d, last = _daily_ohlc(h)
    if len(d) < gap + streak + atr_n + 2:
        return []
    c = d["close"].to_numpy(dtype=float)
    down = np.r_[False, c[1:] < c[:-1]]
    run = np.zeros(len(c), dtype=int)
    for k in range(1, len(c)):
        run[k] = run[k - 1] + 1 if down[k] else 0
    datr = _daily_atr(d, atr_n)
    out: list[Signal] = []
    prev = None
    for k in np.flatnonzero(run == streak):
        rare = prev is not None and k - prev >= gap
        prev = int(k)
        if not rare:
            continue
        sig = _daily_signal(h, last, int(k), 1, datr, stop_atr=stop_atr, rr=10.0,
                            hold_days=hold_days, tag=f"rare_losing_streak:{gap}")
        if sig:
            out.append(sig)
    return out


QUEUED_REPO_FAMILIES = {
    "td_setup_exhaustion": family_td_setup_exhaustion,
    "volume_climax_fade": family_volume_climax_fade,
    "range_trap_reclaim": family_range_trap_reclaim,
    "overlap_box_breakout": family_overlap_box_breakout,
    "quiet_grind": family_quiet_grind,
    "ribbon_release": family_ribbon_release,
    "escalator": family_escalator,
    "payday_dom": family_payday_dom,
    "rare_losing_streak": family_rare_losing_streak,
}

#: Where each came from (the elitequant_breadth donor row; `github:<owner>/<repo>` is its seed).
ORIGIN = {**dict.fromkeys(("td_setup_exhaustion", "volume_climax_fade", "range_trap_reclaim",
                           "overlap_box_breakout", "quiet_grind", "ribbon_release"),
                          "github.com/waditu/czsc (Apache-2.0; rewritten)"),
          "escalator": "github.com/shinnytech/tqsdk-python (Apache-2.0; rewritten)",
          "payday_dom": "github.com/LLMQuant/quant-wiki (no licence; rewritten)",
          "rare_losing_streak": "github.com/quant-science/sunday-quant-scientist (no licence; "
                                "rewritten)"}

#: The calendar anomalies are claims about equity indices only; anywhere else they are trials
#: spent on a mechanism nobody proposed. Keyed to `universe_policy.peer_class`.
CLASS_ONLY: dict[str, frozenset[str]] = {"payday_dom": frozenset({"index"}),
                                         "rare_losing_streak": frozenset({"index"})}

PARAM_GRID: dict[str, dict[str, list]] = {
    "td_setup_exhaustion": {"count": [9, 13]},
    "volume_climax_fade": {"q": [0.80, 0.90]},
    "range_trap_reclaim": {"n": [20, 40]},
    "overlap_box_breakout": {"m": [5, 8]},
    "quiet_grind": {"n": [13]},
    "ribbon_release": {"need": [12, 16]},
    "escalator": {"q": [0.25]},
    "payday_dom": {"dom": [15]},
    "rare_losing_streak": {"gap": [21, 42]},
}

_CN = {"source_culture": "CN/zh", "participant_structure": "retail_futures_chan_theory",
       "crowding_prior": "low"}
_US = {"source_culture": "US/en", "participant_structure": "retail_education",
       "crowding_prior": "medium"}
CULTURE: dict[str, dict[str, str]] = {
    "td_setup_exhaustion": {**_CN, "crowding_prior": "medium", "failure_mode_hypothesis": (
        "fails in a genuine trend, where the ninth bar is the middle of the move rather than "
        "its end")},
    "volume_climax_fade": {**_CN, "failure_mode_hypothesis": (
        "fails when the volume is a scheduled release starting a repricing, not a crowd "
        "exhausting itself")},
    "range_trap_reclaim": {**_CN, "failure_mode_hypothesis": (
        "fails when the first break was real and the reclaim is a retest before continuation")},
    "overlap_box_breakout": {**_CN, "failure_mode_hypothesis": (
        "fails in a dead session where a box is just the absence of trading and the break "
        "is noise")},
    "quiet_grind": {**_CN, "failure_mode_hypothesis": (
        "fails at the turn of a carry or policy regime, where the grind is the last of it")},
    "ribbon_release": {**_CN, "failure_mode_hypothesis": (
        "fails when the expansion is a one-bar spike that the ribbon's slow legs never follow")},
    "escalator": {**_CN, "participant_structure": "cn_futures_sdk_demo",
                  "failure_mode_hypothesis": (
                      "fails on mean-reverting crosses where a top-quarter close is the "
                      "range's ceiling")},
    "payday_dom": {**_CN, "crowding_prior": "medium", "failure_mode_hypothesis": (
        "fails once payroll contributions stop landing as one dated flow into index funds")},
    "rare_losing_streak": {**_US, "failure_mode_hypothesis": (
        "fails at the start of a bear market, where the first streak in months is the first "
        "of many")},
}
