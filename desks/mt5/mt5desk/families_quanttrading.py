"""SIX MECHANISMS FROM je-suis-tm/quant-trading (Apache-2.0) THE DESK COULD NOT EXPRESS.

Source: github.com/je-suis-tm/quant-trading. Copyright its contributors, Apache License 2.0. The
rules below are re-derived from the repository's backtests. Where the originals loop forward over
bars inside a pattern scan, the versions here are written so that bar i reads bars <= i only.

    heikin_ashi_reversal      Heikin-Ashi exhaustion: a body wider than the one before, with no
                              wick on the side the trend came from, marks the flush. `mode`
                              follows the flush or fades it.
    awesome_saucer            Bill Williams' Awesome Oscillator (SMA5 - SMA34 of the median
                              price): the zero-line cross, or the "saucer" (two falling bars then
                              a rising one on the positive side, and the mirror on the negative).
    parabolic_sar_flip        Wilder's stop-and-reverse. Enter on the bar the SAR flips sides.
    bollinger_w               The Bollinger W bottom (and the M top that mirrors it): a first low
                              outside the lower band, a second low inside it, then a close above
                              the mid band. A retest that fails to make a new band extreme is the
                              exhaustion.
    rsi_head_shoulders        Head-and-shoulders read on RSI rather than price: three RSI peaks
                              with the middle one highest and the shoulders within `tol`, then
                              RSI falling through the neckline. The inverse pattern goes long.
    commodity_fx_residual     "Oil Money": a commodity currency regressed on the commodity it
                              exports (NOK/CAD/MXN/RUB on Brent, ZAR on gold, AUD/CLP/BRL on
                              copper). Only when the rolling fit is VALID (R^2 >= min_r2) does a
                              residual beyond +-entry_sd mean anything. The author found that a
                              BREAK of a valid fit is followed by momentum rather than reversion,
                              so `mode="follow"` is the default and `fade` is the contrasting claim.

The first five are retail-chart mechanisms, so their crowding prior is high and the claim under
test is the crowd's error. The sixth is a terms-of-trade mechanism in exactly the currencies
(RUB, MXN, BRL, CLP) where the desk has no producer.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from mt5desk.families import Signal, _atr, _h1

BASE = Path(__file__).resolve().parent.parent
#: Where commodity_fx_residual reads its commodity leg from. Module-level so a test can repoint it.
UNIVERSE_DIR = BASE / "data" / "universe"


def _sig(d: pd.DataFrame, i: int, side: int, atr: np.ndarray, *, stop_atr: float, rr: float,
         ttl_bars: int, tag: str) -> Signal | None:
    a = float(atr[i])
    px = float(d["close"].iloc[i])
    if not (np.isfinite(a) and a > 0 and np.isfinite(px) and px > 0):
        return None
    return Signal(time=d.index[i], side=int(side), stop=px - side * stop_atr * a,
                  target=px + side * stop_atr * a * rr, ttl_bars=int(ttl_bars), tag=tag)


def _emit(d: pd.DataFrame, sides: np.ndarray, *, atr_n: int, stop_atr: float, rr: float,
          ttl_bars: int, tag: str) -> list[Signal]:
    atr = _atr(d, atr_n).to_numpy()
    out: list[Signal] = []
    for i in np.flatnonzero(sides[:-1] != 0):
        s = _sig(d, int(i), int(sides[i]), atr, stop_atr=stop_atr, rr=rr, ttl_bars=ttl_bars,
                 tag=tag)
        if s is not None:
            out.append(s)
    return out


# ------------------------------------------------------------------ 1. Heikin-Ashi reversal ---
def heikin_ashi(o: np.ndarray, h: np.ndarray, lo: np.ndarray, c: np.ndarray
                ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """HA candles. The HA open is recursive on the previous HA candle, so it is causal."""
    hc = (o + h + lo + c) / 4.0
    ho = np.empty_like(hc)
    ho[0] = (o[0] + c[0]) / 2.0
    for i in range(1, len(hc)):
        ho[i] = (ho[i - 1] + hc[i - 1]) / 2.0
    hh = np.maximum.reduce([h, ho, hc])
    hl = np.minimum.reduce([lo, ho, hc])
    return ho, hh, hl, hc


def family_heikin_ashi_reversal(df: pd.DataFrame, *, run: int = 3, mode: str = "fade",
                                atr_n: int = 20, stop_atr: float = 1.5, rr: float = 1.5,
                                ttl_bars: int = 12) -> list[Signal]:
    """After `run` same-colour HA candles, a widening body with no wick against it is the flush.
    `fade` bets that it exhausts, `follow` that it runs on."""
    if mode not in ("fade", "follow") or run < 1:
        return []
    d = _h1(df)
    if len(d) < 100:
        return []
    ho, hh, hl, hc = heikin_ashi(*(d[k].astype(float).to_numpy()
                                   for k in ("open", "high", "low", "close")))
    body = hc - ho
    eps = 1e-12 * np.abs(hc)
    bear = (body < 0) & (np.abs(ho - hh) <= eps)       # red, no upper wick
    bull = (body > 0) & (np.abs(ho - hl) <= eps)       # green, no lower wick
    wider = np.abs(body) > np.abs(np.concatenate(([np.nan], body[:-1])))
    streak_dn = pd.Series(body < 0).rolling(run).sum().to_numpy() == run
    streak_up = pd.Series(body > 0).rolling(run).sum().to_numpy() == run
    flush = np.where(bear & wider & streak_dn, -1, np.where(bull & wider & streak_up, 1, 0))
    sides = flush * (-1 if mode == "fade" else 1)
    return _emit(d, sides, atr_n=atr_n, stop_atr=stop_atr, rr=rr, ttl_bars=ttl_bars,
                 tag=f"heikin_ashi:{mode}")


# ------------------------------------------------------------------- 2. Awesome oscillator ----
def family_awesome_saucer(df: pd.DataFrame, *, fast: int = 5, slow: int = 34,
                          trigger: str = "saucer", atr_n: int = 20, stop_atr: float = 1.5,
                          rr: float = 2.0, ttl_bars: int = 24) -> list[Signal]:
    """Bill Williams' AO = SMA(fast) - SMA(slow) of the median price. `zero`: trade the sign
    cross. `saucer`: on the positive side, two falling AO bars then a rising one go long (and the
    mirror goes short). Either way the claim is that the oscillator's turn leads the price."""
    if trigger not in ("saucer", "zero") or not 1 <= fast < slow:
        return []
    d = _h1(df)
    if len(d) < slow + 10:
        return []
    med = (d["high"].astype(float) + d["low"].astype(float)) / 2.0
    ao = (med.rolling(fast).mean() - med.rolling(slow).mean()).to_numpy()
    prev = np.concatenate(([np.nan], ao[:-1]))
    if trigger == "zero":
        sides = np.where((ao > 0) & (prev <= 0), 1, np.where((ao < 0) & (prev >= 0), -1, 0))
    else:
        d1 = np.diff(ao, prepend=np.nan)
        d1p, d1pp = np.concatenate(([np.nan], d1[:-1])), np.concatenate(([np.nan, np.nan],
                                                                            d1[:-2]))
        long_ = (ao > 0) & (d1pp < 0) & (d1p < 0) & (d1 > 0)
        short = (ao < 0) & (d1pp > 0) & (d1p > 0) & (d1 < 0)
        sides = np.where(long_, 1, np.where(short, -1, 0))
    return _emit(d, sides, atr_n=atr_n, stop_atr=stop_atr, rr=rr, ttl_bars=ttl_bars,
                 tag=f"awesome:{trigger}")


# -------------------------------------------------------------------- 3. Parabolic SAR --------
def parabolic_sar(h: np.ndarray, lo: np.ndarray, *, step: float = 0.02,
                  max_af: float = 0.2) -> tuple[np.ndarray, np.ndarray]:
    """Wilder's SAR and the trend it implies (+1/-1). Bar i's SAR uses bars < i, and the flip is
    decided by bar i's own extreme, so a flip is known at bar i's close."""
    n = len(h)
    sar = np.full(n, np.nan)
    trend = np.zeros(n, dtype=int)
    if n < 3:
        return sar, trend
    up = True
    ep, af, s = h[0], step, lo[0]
    for i in range(1, n):
        s = s + af * (ep - s)
        if up:
            s = min(s, lo[i - 1], lo[i - 2] if i >= 2 else lo[i - 1])
            if lo[i] < s:
                up, s, ep, af = False, ep, lo[i], step
            elif h[i] > ep:
                ep, af = h[i], min(af + step, max_af)
        else:
            s = max(s, h[i - 1], h[i - 2] if i >= 2 else h[i - 1])
            if h[i] > s:
                up, s, ep, af = True, ep, h[i], step
            elif lo[i] < ep:
                ep, af = lo[i], min(af + step, max_af)
        sar[i] = s
        trend[i] = 1 if up else -1
    return sar, trend


def family_parabolic_sar_flip(df: pd.DataFrame, *, step: float = 0.02, max_af: float = 0.2,
                              mode: str = "follow", atr_n: int = 20, stop_atr: float = 2.0,
                              rr: float = 2.0, ttl_bars: int = 48) -> list[Signal]:
    """Enter on the bar the SAR flips. `follow` is Wilder's system; `fade` is the claim that a
    flip on hourly bars is mostly noise that stops out the crowd before reverting."""
    if mode not in ("follow", "fade") or not 0 < step <= max_af:
        return []
    d = _h1(df)
    if len(d) < 100:
        return []
    _, trend = parabolic_sar(d["high"].astype(float).to_numpy(),
                             d["low"].astype(float).to_numpy(), step=step, max_af=max_af)
    prev = np.concatenate(([0], trend[:-1]))
    flip = np.where((trend != prev) & (prev != 0), trend, 0)
    sides = flip * (1 if mode == "follow" else -1)
    return _emit(d, sides, atr_n=atr_n, stop_atr=stop_atr, rr=rr, ttl_bars=ttl_bars,
                 tag=f"psar:{mode}")


# -------------------------------------------------------------------- 4. Bollinger W / M -----
def family_bollinger_w(df: pd.DataFrame, *, n: int = 20, k: float = 2.0, lookback: int = 60,
                       atr_n: int = 20, stop_atr: float = 1.5, rr: float = 2.0,
                       ttl_bars: int = 24) -> list[Signal]:
    """W bottom: within the last `lookback` bars a close fell BELOW the lower band, a later low
    stayed INSIDE it while not above the first low by more than one band width, and the close
    now crosses up through the mid band. The M top is the mirror image. Every read is at or
    before bar i."""
    d = _h1(df)
    if len(d) < n + lookback + 10:
        return []
    c = d["close"].astype(float)
    mid = c.rolling(n).mean()
    sd = c.rolling(n).std(ddof=0)
    lower, upper = (mid - k * sd).to_numpy(), (mid + k * sd).to_numpy()
    cv, mv, sv = c.to_numpy(), mid.to_numpy(), sd.to_numpy()
    below, above = cv < lower, cv > upper
    cross_up = (cv > mv) & (np.concatenate(([np.nan], cv[:-1])) <= np.concatenate(([np.nan],
                                                                                    mv[:-1])))
    cross_dn = (cv < mv) & (np.concatenate(([np.nan], cv[:-1])) >= np.concatenate(([np.nan],
                                                                                    mv[:-1])))
    sides = np.zeros(len(cv), dtype=int)
    for i in np.flatnonzero(cross_up | cross_dn):
        lo_i = max(0, i - lookback)
        win = slice(lo_i, i)
        if cross_up[i]:
            first = np.flatnonzero(below[win])
            if not len(first):
                continue
            f = lo_i + int(first[0])
            after = slice(f + 1, i)
            if f + 1 >= i:
                continue
            j = f + 1 + int(np.argmin(cv[after]))
            if (not below[j]) and cv[j] <= cv[f] + 2 * k * sv[j] and j > f + 2:
                sides[i] = 1
        else:
            first = np.flatnonzero(above[win])
            if not len(first):
                continue
            f = lo_i + int(first[0])
            if f + 1 >= i:
                continue
            j = f + 1 + int(np.argmax(cv[f + 1:i]))
            if (not above[j]) and cv[j] >= cv[f] - 2 * k * sv[j] and j > f + 2:
                sides[i] = -1
    return _emit(d, sides, atr_n=atr_n, stop_atr=stop_atr, rr=rr, ttl_bars=ttl_bars,
                 tag="bollinger_w")


# --------------------------------------------------------- 5. head-and-shoulders on the RSI --
def _rsi(c: pd.Series, n: int) -> np.ndarray:
    delta = c.diff()
    up = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-delta.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return (100 - 100 / (1 + up / dn.replace(0, np.nan))).to_numpy()


def family_rsi_head_shoulders(df: pd.DataFrame, *, rsi_n: int = 14, pivot: int = 5,
                              tol: float = 5.0, atr_n: int = 20, stop_atr: float = 1.5,
                              rr: float = 2.0, ttl_bars: int = 24) -> list[Signal]:
    """Pivots on the RSI are confirmed `pivot` bars after the peak, so the pattern is known only
    then. Head and shoulders: the last three confirmed RSI peaks have the middle one highest and
    the outer two within `tol` points; short when the RSI then closes below the lower of the two
    troughs between them (the neckline). The inverse pattern on troughs goes long."""
    d = _h1(df)
    if len(d) < 200 or pivot < 1:
        return []
    r = _rsi(d["close"].astype(float), rsi_n)
    w = 2 * pivot + 1
    rs = pd.Series(r)
    is_hi = (rs == rs.rolling(w, center=True).max()).to_numpy()
    is_lo = (rs == rs.rolling(w, center=True).min()).to_numpy()
    sides = np.zeros(len(r), dtype=int)
    peaks: list[int] = []
    troughs: list[int] = []
    armed_short: float | None = None
    armed_long: float | None = None
    for i in range(w, len(r)):
        k = i - pivot                                      # a pivot at k is confirmed at i
        if is_hi[k] and np.isfinite(r[k]):
            peaks.append(k)
            if len(peaks) >= 3:
                a, b, c3 = peaks[-3:]
                if r[b] > r[a] and r[b] > r[c3] and abs(r[a] - r[c3]) <= tol:
                    necks = [t for t in troughs if a < t < c3]
                    armed_short = min(r[t] for t in necks) if necks else None
        if is_lo[k] and np.isfinite(r[k]):
            troughs.append(k)
            if len(troughs) >= 3:
                a, b, c3 = troughs[-3:]
                if r[b] < r[a] and r[b] < r[c3] and abs(r[a] - r[c3]) <= tol:
                    necks = [p for p in peaks if a < p < c3]
                    armed_long = max(r[p] for p in necks) if necks else None
        if armed_short is not None and r[i] < armed_short:
            sides[i], armed_short = -1, None
        elif armed_long is not None and r[i] > armed_long:
            sides[i], armed_long = 1, None
    return _emit(d, sides, atr_n=atr_n, stop_atr=stop_atr, rr=rr, ttl_bars=ttl_bars,
                 tag="rsi_head_shoulders")


# ------------------------------------------------------------ 6. Oil Money: commodity FX ------
def commodity_of(symbol: str) -> str | None:
    """The instrument a commodity currency is regressed on, from `economic_drivers`' own roles."""
    from mt5desk import economic_drivers as ed
    s = str(symbol).upper()
    if len(s) != 6:
        return None
    for ccy in (s[3:], s[:3]):
        role = (ed.COMMODITY_CURRENCIES.get(ccy) or (None,))[0]
        if role:
            legs = ed.ROLES.get(role) or (("XAUUSD",) if role == "GOLD" else ())
            for leg in legs:
                if (UNIVERSE_DIR / f"{leg}_H1.parquet").exists():
                    return str(leg)
    return None


def _daily_close(d: pd.DataFrame) -> pd.Series:
    c = d["close"].astype(float)
    return c.groupby(c.index.normalize()).last()


def family_commodity_fx_residual(df: pd.DataFrame, *, symbol: str = "", commodity: str = "",
                                 window_d: int = 50, min_r2: float = 0.7, entry_sd: float = 2.0,
                                 hold_d: int = 10, mode: str = "follow", atr_n: int = 20,
                                 stop_atr: float = 2.5, rr: float = 2.0) -> list[Signal]:
    """log(FX) on log(commodity), fitted on the `window_d` days BEFORE day t. When that fit's R^2
    is at least `min_r2`, day t's residual beyond +-`entry_sd` residual sd is a break: `follow`
    trades in the direction of the break (the source's finding), `fade` against it. Decided on
    day t's last bar; entered at the next bar's open."""
    if mode not in ("follow", "fade") or window_d < 10 or not 0 <= min_r2 < 1:
        return []
    leg = commodity or commodity_of(symbol)
    if not leg:
        return []
    try:
        cd = pd.read_parquet(UNIVERSE_DIR / f"{leg}_H1.parquet")
    except Exception:
        return []
    d = _h1(df)
    if "time" in cd.columns:
        cd = cd.set_index("time")
    cd.index = pd.to_datetime(cd.index, utc=True) if cd.index.tz is None else cd.index
    y = _daily_close(d)
    # The commodity is read AS OF this symbol's own last bar of each day: a commodity bar stamped
    # after the decision bar (a later session close) would be a price the decision never saw.
    close = d["close"].astype(float)
    stamp = close.groupby(close.index.normalize()).apply(lambda s: s.index[-1])
    cc = cd["close"].astype(float).sort_index()
    x = pd.Series(cc.asof(pd.DatetimeIndex(stamp.to_numpy())).to_numpy(), index=y.index)
    ok = y.notna() & x.notna() & (y > 0) & (x > 0)
    ly, lx = np.log(y[ok].to_numpy()), np.log(x[ok].to_numpy())
    days = y.index[ok]
    if len(ly) < window_d + 20:
        return []
    sides_by_day: dict[pd.Timestamp, int] = {}
    for t in range(window_d, len(ly)):
        xs, ys = lx[t - window_d:t], ly[t - window_d:t]
        vx = float(np.var(xs))
        if vx <= 0:
            continue
        b = float(np.cov(xs, ys, ddof=0)[0, 1]) / vx
        a = float(ys.mean() - b * xs.mean())
        res = ys - (a + b * xs)
        vy = float(np.var(ys))
        r2 = 1 - float(np.var(res)) / vy if vy > 0 else 0.0
        sd = float(np.std(res))
        if r2 < min_r2 or sd <= 0:
            continue
        z = (ly[t] - (a + b * lx[t])) / sd
        if abs(z) >= entry_sd:
            s = 1 if z > 0 else -1
            sides_by_day[days[t]] = s if mode == "follow" else -s
    if not sides_by_day:
        return []
    atr = _atr(d, atr_n).to_numpy()
    day_of = d.index.normalize()
    last_bar = np.flatnonzero(np.r_[day_of[1:] != day_of[:-1], True])
    bpd = max(1, round(len(d) / max(1, len(last_bar))))
    out: list[Signal] = []
    for i in last_bar[:-1]:
        s = sides_by_day.get(day_of[i])
        if s:
            sig = _sig(d, int(i), s, atr, stop_atr=stop_atr, rr=rr, ttl_bars=hold_d * bpd,
                       tag=f"commodity_fx:{leg}:{mode}")
            if sig is not None:
                out.append(sig)
    return out


QUANTTRADING_FAMILIES = {
    "heikin_ashi_reversal": family_heikin_ashi_reversal,
    "awesome_saucer": family_awesome_saucer,
    "parabolic_sar_flip": family_parabolic_sar_flip,
    "bollinger_w": family_bollinger_w,
    "rsi_head_shoulders": family_rsi_head_shoulders,
    "commodity_fx_residual": family_commodity_fx_residual,
}

#: What the seeder sweeps. commodity_fx_residual also takes the cell's own `symbol`, which the
#: seeder passes to any family whose signature asks for it.
PARAM_GRID: dict[str, dict[str, list]] = {
    "heikin_ashi_reversal": {"run": [3, 5], "mode": ["fade", "follow"]},
    "awesome_saucer": {"trigger": ["saucer", "zero"]},
    "parabolic_sar_flip": {"step": [0.02, 0.04], "mode": ["follow", "fade"]},
    "bollinger_w": {"n": [20], "lookback": [60, 120]},
    "rsi_head_shoulders": {"pivot": [5, 10], "tol": [5.0]},
    "commodity_fx_residual": {"min_r2": [0.5, 0.7], "mode": ["follow", "fade"]},
}

_RETAIL_FAIL = "fails when the chart pattern is so widely traded that its stops are the liquidity"
CULTURE: dict[str, dict[str, str]] = {
    "heikin_ashi_reversal": {"source_culture": "GLOBAL/en", "participant_structure": "retail_heavy",
                             "crowding_prior": "high", "failure_mode_hypothesis": _RETAIL_FAIL},
    "awesome_saucer": {"source_culture": "US/en", "participant_structure": "retail_heavy",
                       "crowding_prior": "high", "failure_mode_hypothesis": _RETAIL_FAIL},
    "parabolic_sar_flip": {"source_culture": "US/en", "participant_structure": "retail_heavy",
                           "crowding_prior": "high",
                           "failure_mode_hypothesis": "fails in ranges, where every flip is "
                                                      "whipsawed"},
    "bollinger_w": {"source_culture": "US/en", "participant_structure": "retail_heavy",
                    "crowding_prior": "high", "failure_mode_hypothesis": _RETAIL_FAIL},
    "rsi_head_shoulders": {"source_culture": "GLOBAL/en", "participant_structure": "retail_heavy",
                           "crowding_prior": "medium", "failure_mode_hypothesis": _RETAIL_FAIL},
    "commodity_fx_residual": {"source_culture": "NO/RU/MX/CO", "participant_structure":
                              "institutional", "crowding_prior": "low",
                              "failure_mode_hypothesis": "fails when a peg, sanctions or a "
                              "capital control cuts the currency off from the commodity it "
                              "exports (RUB 2022)"},
}
