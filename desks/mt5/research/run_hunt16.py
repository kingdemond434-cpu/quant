"""Hunt #16: DaviddTech external strategy corpus -> canonical mechanism families.

Source: DaviddTech public strategy corpus (119+ named systems + primitive library).
Never trust published parameters as alpha; each strategy is canonicalized to a
mechanism family with canonical (non-optimized) parameters and run through the
normal hunt battery. LONG and SHORT are separate organisms.

Families (mechanism seeds, H1 v1):
  dav_ema_trend_pullback   EMA cloud trend + pullback + momentum confirm   (Ultimate Scalper)
  dav_supertrend_trail     Supertrend ATR direction + MACD entry           (Supertrend The Works, PSAR+MACD+EMA)
  dav_breakout_fakeout     prior-day range breakout                        (Breakout/Fakeout, Golden Range)
  dav_fakeout_reverse      breakout that closes back inside -> reversal    (Fakeout family)
  dav_squeeze_expansion    BB-inside-Keltner squeeze -> expansion          (Extended Squeeze, Squeeze it)
  dav_bb_meanrev           BB %B reversal conditioned on trend             (Ultimate BB+Aroon, Nadaraya BB)
  dav_keltner_break        Keltner band breakout + ADX                     (Keltner Channel Strategy)
  dav_t3_trend             triple-smoothed MA trend + ADX, pullback        (T3 Nexus, Profit Hunter)
  dav_rsi_div_rev          RSI divergence reversal vs 200EMA               (RSI/MACD divergence families)
  dav_macd_qqe             MACD cross + smoothed-RSI agreement             (QQE hybrids, MACD+R S I)
  dav_abc_structure        swing HH/HL structure + breakout of swing high  (Ultimate ABC)
  dav_momentum_cont        big-range bar + continuation                    (HyperScalper, 1m Scalper adapted)
  dav_hull_trend           hull baseline + ADX + pullback                  (Deadzone Pro, Hull families)
  dav_range_filter_adx     ATR range channel + ADX>25                      (Range Filter + ADX v2)

Two-stage gating: cheap stage-1 (n>60, exp>0, t>1.3) then full battery (deflated
t>2 with family E[max]~1.5, PF>1.05, maxDD>-30R, 3-fold WF all>0, 2x cost stress).
Resumable via reports/hunt16_partial.json.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mt5desk import families  # noqa: E402
from mt5desk.engine import Costs, Signal, run_backtest  # noqa: E402
from research.run_hunt12 import battery, day_states, wf_oos  # noqa: E402

BASE = Path(__file__).resolve().parent.parent
UNI = BASE / "data" / "universe"
E_MAX = 1.5
WINDOWS = {
    "asia": dict(range_start=7, wait_bars=12, rr=2.0, ttl_bars=12),
    "london_am": dict(range_start=10, range_end=13, signal_at=13, wait_bars=8, rr=2.0, ttl_bars=12),
    "ny_open": dict(range_start=13, range_end=14, signal_at=14, wait_bars=12, rr=2.0, ttl_bars=12),
    "afternoon": dict(range_start=14, range_end=17, signal_at=17, wait_bars=8, rr=2.0, ttl_bars=12),
}
STATES = ["TREND_DAY", "NORMAL_DAY"]
SYMBOLS = ["AUDCAD", "AUDJPY", "AUDNZD", "NZDCAD", "EURAUD", "GBPAUD",
           "EURJPY", "GBPJPY", "CADJPY", "NZDJPY", "EURGBP", "XAUUSD"]
SIDES = ["LONG", "SHORT"]


def _atr(h1: pd.DataFrame, n: int = 14) -> pd.Series:
    h, l, c = h1["high"], h1["low"], h1["close"]
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean()


def _ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def _rsi(c: pd.Series, n: int = 14) -> pd.Series:
    d = c.diff()
    up = d.clip(lower=0).rolling(n).mean()
    dn = (-d.clip(upper=0)).rolling(n).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def _wma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n).apply(lambda x: np.dot(x, np.arange(1, n + 1)) / (n * (n + 1) / 2), raw=True)


def _hull(c: pd.Series, n: int = 20) -> pd.Series:
    h = 2 * _wma(c, n // 2) - _wma(c, n)
    return _wma(h, int(np.sqrt(n)))


def _supertrend(h1: pd.DataFrame, n: int = 10, mult: float = 3.0):
    a = _atr(h1, n)
    hl2 = (h1["high"] + h1["low"]) / 2
    ub = hl2 + mult * a
    lb = hl2 - mult * a
    f = pd.Series(np.nan, index=h1.index)
    st = pd.Series(np.nan, index=h1.index)
    for i in range(n, len(h1)):
        c = h1["close"].iloc[i]
        prev = f.iloc[i - 1] if i > 0 else 1
        if c > ub.iloc[i - 1]:
            f.iloc[i], st.iloc[i] = 1, lb.iloc[i]
        elif c < lb.iloc[i - 1]:
            f.iloc[i], st.iloc[i] = -1, ub.iloc[i]
        else:
            f.iloc[i] = prev
            st.iloc[i] = st.iloc[i - 1] if i > 0 else 0
    return f, st


def _adx(h1: pd.DataFrame, n: int = 14) -> pd.Series:
    h, l, c = h1["high"], h1["low"], h1["close"]
    up = h.diff()
    dn = -l.diff()
    plus = np.where((up > dn) & (up > 0), up, 0.0)
    minus = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = pd.concat([h - l, (h - c.shift(1)).abs(), (l - c.shift(1)).abs()], axis=1).max(axis=1)
    atr = tr.rolling(n).mean().replace(0, np.nan)
    pdi = 100 * pd.Series(plus, index=h1.index).rolling(n).mean() / atr
    mdi = 100 * pd.Series(minus, index=h1.index).rolling(n).mean() / atr
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    return dx.rolling(n).mean()


def _t3(c: pd.Series, n: int = 21) -> pd.Series:
    e1 = _ema(c, n)
    e2 = _ema(e1, n)
    e3 = _ema(e2, n)
    e4 = _ema(e3, n)
    e5 = _ema(e4, n)
    e6 = _ema(e5, n)
    b = 0.7
    c1 = -b ** 3
    c2 = 3 * b ** 2 + 3 * b ** 3
    c3 = -6 * b ** 2 - 3 * b - 3 * b ** 3
    c4 = 1 + 3 * b + b ** 3 + 3 * b ** 2
    return c1 * e6 + c2 * e5 + c3 * e4 + c4 * e3


def _sigs(df: pd.DataFrame, mask: pd.Series, side: int, stop: pd.Series,
          target: pd.Series, ttl: int, win_mask: pd.Series) -> list[Signal]:
    out = []
    for ts in df.index[mask & win_mask]:
        s, t = float(stop[ts]), float(target[ts])
        if s == s and t == t and s > 0 and t > 0:
            out.append(Signal(time=ts, side=side, stop=s, target=t, ttl_bars=ttl, tag="dav"))
    return out


def dav_ema_trend_pullback(h1: pd.DataFrame, side: int) -> list[Signal]:
    c = h1["close"]
    ema20, ema50, ema200 = _ema(c, 20), _ema(c, 50), _ema(c, 200)
    rsi = _rsi(c, 14)
    macd = _ema(c, 12) - _ema(c, 26)
    pull = c < ema20
    trend = (c > ema50) & (c > ema200) if side > 0 else (c < ema50) & (c < ema200)
    mom = (rsi > 45) & (rsi < 70) if side > 0 else (rsi < 55) & (rsi > 30)
    mdir = macd > macd.shift(1) if side > 0 else macd < macd.shift(1)
    a = _atr(h1, 14)
    stop = h1["close"] - 1.5 * a if side > 0 else h1["close"] + 1.5 * a
    target = h1["close"] + 2.0 * (1.5 * a) if side > 0 else h1["close"] - 2.0 * (1.5 * a)
    return _sigs(h1, pull & trend & mom & mdir, side, stop, target, 12,
                 h1.index.hour.between(0, 23))


def dav_supertrend_trail(h1: pd.DataFrame, side: int) -> list[Signal]:
    f, st = _supertrend(h1, 10, 3.0)
    c = h1["close"]
    macd = _ema(c, 12) - _ema(c, 26)
    cond = (f == 1) & (macd > 0) if side > 0 else (f == -1) & (macd < 0)
    a = _atr(h1, 14)
    stop = c - 1.5 * a if side > 0 else c + 1.5 * a
    target = c + 2.0 * (1.5 * a) if side > 0 else c - 2.0 * (1.5 * a)
    return _sigs(h1, cond, side, stop, target, 12, h1.index.hour.between(0, 23))


def dav_breakout_fakeout(h1: pd.DataFrame, side: int) -> list[Signal]:
    dhi = pd.Series(h1.index.date, index=h1.index).map(
        h1.assign(date=h1.index.date).groupby("date")["high"].max().shift(1))
    dlo = pd.Series(h1.index.date, index=h1.index).map(
        h1.assign(date=h1.index.date).groupby("date")["low"].min().shift(1))
    cond = (h1["close"] > dhi) if side > 0 else (h1["close"] < dlo)
    a = _atr(h1, 14)
    stop = h1["close"] - 1.5 * a if side > 0 else h1["close"] + 1.5 * a
    target = h1["close"] + 2.0 * (1.5 * a) if side > 0 else h1["close"] - 2.0 * (1.5 * a)
    return _sigs(h1, cond & dhi.notna(), side, stop, target, 12, h1.index.hour.between(0, 23))


def dav_fakeout_reverse(h1: pd.DataFrame, side: int) -> list[Signal]:
    dhi = pd.Series(h1.index.date, index=h1.index).map(
        h1.assign(date=h1.index.date).groupby("date")["high"].max().shift(1))
    dlo = pd.Series(h1.index.date, index=h1.index).map(
        h1.assign(date=h1.index.date).groupby("date")["low"].min().shift(1))
    hb = h1["high"] > dhi
    lb = h1["low"] < dlo
    bk = h1["close"] < dhi
    bl = h1["close"] > dlo
    fake = (hb & bk & (h1["high"] > dhi + 0.1 * (dhi - dlo))) if side < 0 else \
        (lb & bl & (h1["low"] < dlo - 0.1 * (dhi - dlo)))
    a = _atr(h1, 14)
    stop = h1["close"] + 1.5 * a if side < 0 else h1["close"] - 1.5 * a
    target = h1["close"] - 2.0 * (1.5 * a) if side < 0 else h1["close"] + 2.0 * (1.5 * a)
    return _sigs(h1, fake & dhi.notna(), side, stop, target, 12, h1.index.hour.between(0, 23))


def dav_squeeze_expansion(h1: pd.DataFrame, side: int) -> list[Signal]:
    c = h1["close"]
    bb_u = c.rolling(20).mean() + 2 * c.rolling(20).std()
    bb_l = c.rolling(20).mean() - 2 * c.rolling(20).std()
    kl_u = c.rolling(20).mean() + 1.5 * _atr(h1, 20)
    kl_l = c.rolling(20).mean() - 1.5 * _atr(h1, 20)
    sq = (bb_u < kl_u) & (bb_l > kl_l)
    sqk = sq.rolling(3).sum() >= 3
    ex = (h1["close"] > bb_u) if side > 0 else (h1["close"] < bb_l)
    cond = sqk.shift(1) & ex
    a = _atr(h1, 14)
    stop = h1["close"] - 1.5 * a if side > 0 else h1["close"] + 1.5 * a
    target = h1["close"] + 2.0 * (1.5 * a) if side > 0 else h1["close"] - 2.0 * (1.5 * a)
    return _sigs(h1, cond, side, stop, target, 12, h1.index.hour.between(0, 23))


def dav_bb_meanrev(h1: pd.DataFrame, side: int) -> list[Signal]:
    c = h1["close"]
    bb_u = c.rolling(20).mean() + 2 * c.rolling(20).std()
    bb_l = c.rolling(20).mean() - 2 * c.rolling(20).std()
    pctb = (c - bb_l) / (bb_u - bb_l).replace(0, np.nan)
    rsi = _rsi(c, 14)
    ema200 = _ema(c, 200)
    cond = (pctb < 0.15) & (rsi < 35) & (c > ema200) if side > 0 else \
        (pctb > 0.85) & (rsi > 65) & (c < ema200)
    a = _atr(h1, 14)
    stop = h1["close"] - 1.5 * a if side > 0 else h1["close"] + 1.5 * a
    target = h1["close"] + 1.5 * (1.5 * a) if side > 0 else h1["close"] - 1.5 * (1.5 * a)
    return _sigs(h1, cond, side, stop, target, 16, h1.index.hour.between(0, 23))


def dav_keltner_break(h1: pd.DataFrame, side: int) -> list[Signal]:
    c = h1["close"]
    kl_u = c.rolling(20).mean() + 1.5 * _atr(h1, 20)
    kl_l = c.rolling(20).mean() - 1.5 * _atr(h1, 20)
    dx = _adx(h1, 14)
    cond = (c > kl_u) & (dx > 20) if side > 0 else (c < kl_l) & (dx > 20)
    a = _atr(h1, 14)
    stop = h1["close"] - 1.5 * a if side > 0 else h1["close"] + 1.5 * a
    target = h1["close"] + 2.0 * (1.5 * a) if side > 0 else h1["close"] - 2.0 * (1.5 * a)
    return _sigs(h1, cond, side, stop, target, 12, h1.index.hour.between(0, 23))


def dav_t3_trend(h1: pd.DataFrame, side: int) -> list[Signal]:
    c = h1["close"]
    t3 = _t3(c, 21)
    dx = _adx(h1, 14)
    trend = (c > t3) & (dx > 25) if side > 0 else (c < t3) & (dx > 25)
    pull = (c < t3 * 1.002) if side > 0 else (c > t3 * 0.998)
    cond = trend & pull
    a = _atr(h1, 14)
    stop = h1["close"] - 1.5 * a if side > 0 else h1["close"] + 1.5 * a
    target = h1["close"] + 2.0 * (1.5 * a) if side > 0 else h1["close"] - 2.0 * (1.5 * a)
    return _sigs(h1, cond, side, stop, target, 12, h1.index.hour.between(0, 23))


def dav_rsi_div_rev(h1: pd.DataFrame, side: int) -> list[Signal]:
    c = h1["close"]
    rsi = _rsi(c, 14)
    ema200 = _ema(c, 200)
    lo = h1["low"].rolling(10).min()
    hi = h1["high"].rolling(10).max()
    pl = (c < ema200) if side > 0 else (c > ema200)
    div = (lo < lo.shift(1)) & (rsi > rsi.shift(1)) if side > 0 else \
        (hi > hi.shift(1)) & (rsi < rsi.shift(1))
    cond = pl & div & (rsi < 35 if side > 0 else rsi > 65)
    a = _atr(h1, 14)
    stop = h1["close"] - 1.5 * a if side > 0 else h1["close"] + 1.5 * a
    target = h1["close"] + 1.5 * (1.5 * a) if side > 0 else h1["close"] - 1.5 * (1.5 * a)
    return _sigs(h1, cond, side, stop, target, 16, h1.index.hour.between(0, 23))


def dav_macd_qqe(h1: pd.DataFrame, side: int) -> list[Signal]:
    c = h1["close"]
    macd = _ema(c, 12) - _ema(c, 26)
    sig = _ema(macd, 9)
    rsi = _rsi(c, 6)
    rsi_s = rsi.rolling(5).mean()
    cond = (macd > sig) & (rsi > rsi_s) & (rsi > 50) if side > 0 else \
        (macd < sig) & (rsi < rsi_s) & (rsi < 50)
    a = _atr(h1, 14)
    stop = h1["close"] - 1.5 * a if side > 0 else h1["close"] + 1.5 * a
    target = h1["close"] + 2.0 * (1.5 * a) if side > 0 else h1["close"] - 2.0 * (1.5 * a)
    return _sigs(h1, cond, side, stop, target, 12, h1.index.hour.between(0, 23))


def dav_abc_structure(h1: pd.DataFrame, side: int) -> list[Signal]:
    c = h1["close"]
    hi = h1["high"].rolling(5).max()
    lo = h1["low"].rolling(5).min()
    hh = hi > hi.shift(1)
    hl = lo > lo.shift(1)
    cond = (hh & hl & (c > hi.shift(1))) if side > 0 else \
        (hi < hi.shift(1)) & (lo < lo.shift(1)) & (c < lo.shift(1))
    a = _atr(h1, 14)
    stop = h1["close"] - 1.5 * a if side > 0 else h1["close"] + 1.5 * a
    target = h1["close"] + 2.0 * (1.5 * a) if side > 0 else h1["close"] - 2.0 * (1.5 * a)
    return _sigs(h1, cond, side, stop, target, 12, h1.index.hour.between(0, 23))


def dav_momentum_cont(h1: pd.DataFrame, side: int) -> list[Signal]:
    c = h1["close"]
    a = _atr(h1, 14)
    rng = (h1["high"] - h1["low"])
    bar = (c > h1["open"]) & (rng > 1.2 * a) if side > 0 else \
        (c < h1["open"]) & (rng > 1.2 * a)
    cond = bar.shift(1)
    stop = h1["close"] - 1.0 * a if side > 0 else h1["close"] + 1.0 * a
    target = h1["close"] + 1.5 * (1.0 * a) if side > 0 else h1["close"] - 1.5 * (1.0 * a)
    return _sigs(h1, cond, side, stop, target, 8, h1.index.hour.between(0, 23))


def dav_hull_trend(h1: pd.DataFrame, side: int) -> list[Signal]:
    c = h1["close"]
    hu = _hull(c, 20)
    dx = _adx(h1, 14)
    cond = (c > hu) & (dx > 20) if side > 0 else (c < hu) & (dx > 20)
    a = _atr(h1, 14)
    stop = h1["close"] - 1.5 * a if side > 0 else h1["close"] + 1.5 * a
    target = h1["close"] + 2.0 * (1.5 * a) if side > 0 else h1["close"] - 2.0 * (1.5 * a)
    return _sigs(h1, cond, side, stop, target, 12, h1.index.hour.between(0, 23))


def dav_range_filter_adx(h1: pd.DataFrame, side: int) -> list[Signal]:
    c = h1["close"]
    a = _atr(h1, 14)
    chan = a * 2.0
    dx = _adx(h1, 14)
    hi_chan = c.rolling(14).max()
    lo_chan = c.rolling(14).min()
    cond = (c < lo_chan + chan * 0.2) & (dx > 25) if side > 0 else \
        (c > hi_chan - chan * 0.2) & (dx > 25)
    stop = h1["close"] - 1.5 * a if side > 0 else h1["close"] + 1.5 * a
    target = h1["close"] + 2.0 * (1.5 * a) if side > 0 else h1["close"] - 2.0 * (1.5 * a)
    return _sigs(h1, cond, side, stop, target, 12, h1.index.hour.between(0, 23))


FAMILIES = {
    "dav_ema_trend_pullback": dav_ema_trend_pullback,
    "dav_supertrend_trail": dav_supertrend_trail,
    "dav_breakout_fakeout": dav_breakout_fakeout,
    "dav_fakeout_reverse": dav_fakeout_reverse,
    "dav_squeeze_expansion": dav_squeeze_expansion,
    "dav_bb_meanrev": dav_bb_meanrev,
    "dav_keltner_break": dav_keltner_break,
    "dav_t3_trend": dav_t3_trend,
    "dav_rsi_div_rev": dav_rsi_div_rev,
    "dav_macd_qqe": dav_macd_qqe,
    "dav_abc_structure": dav_abc_structure,
    "dav_momentum_cont": dav_momentum_cont,
    "dav_hull_trend": dav_hull_trend,
    "dav_range_filter_adx": dav_range_filter_adx,
}


def cheap_gate(h1: pd.DataFrame, sigs: list, costs: Costs) -> bool:
    r = run_backtest(h1, sigs, costs).stats()
    return r["n"] > 60 and r["expectancy_r"] > 0 and r["t_stat"] > 1.3


def main() -> None:
    meta = json.loads((UNI / "universe.json").read_text(encoding="utf-8"))
    partial = BASE / "reports" / "hunt16_partial.json"
    done, results = [], []
    if partial.exists():
        try:
            saved = json.loads(partial.read_text(encoding="utf-8"))
            done = saved.get("done", [])
            results = list(saved.get("all", []))
        except Exception:
            pass
    done_cells = {tuple(x) for x in done}
    log = open(BASE / "logs" / "hunt16_console.txt", "w", encoding="utf-8")

    def tprint(*a) -> None:
        msg = " ".join(str(x) for x in a)
        print(msg, flush=True)
        log.write(msg + "\n")
        log.flush()

    tprint(f"{'sym':>8} {'fam':<24} {'side':<5} {'win':<10} {'state':<11} {'n':>5} "
           f"{'exp':>7} {'t':>5} {'defl':>5} {'PF':>5} {'maxDD':>7} {'GATE':>5}")
    for sym in SYMBOLS:
        fp = UNI / f"{sym}_H1.parquet"
        if not fp.exists():
            tprint(f"{sym}: no parquet, skip")
            continue
        h1 = families._h1(pd.read_parquet(fp))
        m = meta.get(sym, {})
        costs = Costs(spread_per_lot=0.48 if sym == "XAUUSD" else max(
            m.get("median_spread_pts", 1) * m.get("tick_size", 1e-5) * m.get("contract_size", 1e5), 0.05),
            commission_per_lot=3.50, contract_oz=m.get("contract_size", 1e5))
        states = day_states(h1)
        for fname, ffn in FAMILIES.items():
            for side in SIDES:
                for wname, wp in WINDOWS.items():
                    sday = wp.get("signal_at") or wp["range_start"]
                    sigs = ffn(h1, 1 if side == "LONG" else -1)
                    sigs = [s for s in sigs if s.time.hour == sday]
                    sdays = [pd.Timestamp(s.time).date() for s in sigs]
                    for st_name in STATES:
                        key = (sym, fname, side, wname, st_name)
                        if key in done_cells:
                            continue
                        sub = [s for s, d in zip(sigs, sdays) if states.get(d) == st_name]
                        if len(sub) < 60:
                            done.append(list(key))
                            continue
                        if not cheap_gate(h1, sub, costs):
                            done.append(list(key))
                            continue
                        b = battery(h1, sub, costs)
                        wfs = " ".join(f"{x:+.3f}" if x == x else "  nan" for x in b["wf"])
                        tprint(f"{sym:>8} {fname:<24} {side:<5} {wname:<10} {st_name:<11} "
                               f"{b['n']:5d} {b['exp']:+7.3f} {b['t']:5.2f} {b['defl']:5.2f} "
                               f"{b['pf']:5.2f} {b['maxdd']:7.1f} "
                               f"{'PASS' if b['gate'] else 'fail':>5}  WF[{wfs}]")
                        results.append(dict(sym=sym, fam=fname, side=side, win=wname,
                                            state=st_name, **b))
                        done.append(list(key))
                        partial.write_text(json.dumps(
                            {"done": done, "all": results}, indent=2, default=str),
                            encoding="utf-8")
    (BASE / "reports" / "hunt16.json").write_text(
        json.dumps({"survivors": [r for r in results if r["gate"]], "all": results,
                    "swept_at": datetime.now(timezone.utc).isoformat()},
                   indent=2, default=str), encoding="utf-8")
    tprint(f"\n{sum(1 for r in results if r['gate'])} survivors of {len(results)} "
           f"battery tests")


if __name__ == "__main__":
    main()