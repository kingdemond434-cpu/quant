"""THE RULE BUILDER: a strategy assembled from entry blocks, filters and an exit, as one cell.

WHY THIS EXISTS (zuck, 2026-11-20). The desk's genetic search (`research/alpha_evolution.py`,
nine populations over `libs/research/alpha_grammar`) evolves FORMULAS: one expression, one
threshold recipe. What it never evolves is the shape a StrategyQuant / Adaptrade / retail
builder evolves: a conjunction of familiar entry conditions, gated by a regime or session filter,
with its own stop, target and hold. That is a different search space -- discrete,
compositional, exit-aware -- and it finds a different kind of edge, so it is a different
generator rather than a parameter of the old one.

WHAT A CELL OF THIS FAMILY IS. `entry` is a list of 1-3 BLOCKS; each block is a dict naming a
building block from `BLOCKS` and its parameters, and reads -1 / 0 / +1 on every closed bar.
The entry fires on the bar where every block agrees on one non-zero side and did not agree on
that side the bar before (edge-triggered, so a persistent state is one trade, not a hundred).
`filters` is a list of 0-2 gates from `FILTERS`, each a permission (never a trigger). `invert`
flips the side (the same conditions read as a fade). The exit is stop `stop_atr` x ATR, target
`rr` x stop, time stop `max_hold_bars`, and the desk's own
volatility-expansion exit operator (`expansion_mult`, 0 = off).

STRICTLY TRAILING. Every block and filter reads bars that have CLOSED; the signal is stamped on
the closing bar and fills on the next open (`wait_bars=1`), the desk's standard convention.
`test_rule_builder_has_no_lookahead` pins it: truncating the frame after bar t never changes a
signal stamped at or before t.

NO PRIVILEGE. Registered, compiled, judged, charged and allocated like every other family. The
generator that proposes these cells (`research/strategy_builder.py`) charges every genome it
evaluated as a trial; the gauntlet decides.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from mt5desk.engine import Signal
from mt5desk.exit_operators import apply_exit_operators
from mt5desk.families import _atr, _h1, register_family


# --------------------------------------------------------------------------- building blocks
def _sma(x: pd.Series, n: int) -> pd.Series:
    return x.rolling(n, min_periods=n).mean()


def _ema(x: pd.Series, n: int) -> pd.Series:
    return x.ewm(span=n, min_periods=n).mean()


def _rsi(c: pd.Series, n: int) -> pd.Series:
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1.0 / n, min_periods=n).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1.0 / n, min_periods=n).mean()
    return 100.0 - 100.0 / (1.0 + up / dn.replace(0.0, np.nan))


def _sgn(cond_long: pd.Series, cond_short: pd.Series) -> np.ndarray:
    lo = cond_long.fillna(False).to_numpy(dtype=bool)
    sh = cond_short.fillna(False).to_numpy(dtype=bool)
    return lo.astype(np.int8) - sh.astype(np.int8)


def b_ma_state(d, n=50, **_):
    c = d["close"]
    m = _sma(c, int(n))
    return _sgn(c > m, c < m)


def b_ema_cross(d, fast=12, slow=36, **_):
    c = d["close"]
    f = _ema(c, int(fast))
    s = _ema(c, int(max(slow, fast + 1)))
    return _sgn(f > s, f < s)


def b_breakout(d, n=20, **_):
    hh = d["high"].rolling(int(n), min_periods=int(n)).max().shift(1)
    ll = d["low"].rolling(int(n), min_periods=int(n)).min().shift(1)
    return _sgn(d["close"] > hh, d["close"] < ll)


def b_rsi(d, n=14, lo=30, **_):
    r = _rsi(d["close"], int(n))
    return _sgn(r < float(lo), r > 100.0 - float(lo))


def b_zscore(d, n=20, k=2.0, **_):
    c = d["close"]
    z = (c - _sma(c, int(n))) / c.rolling(int(n), min_periods=int(n)).std()
    return _sgn(z < -float(k), z > float(k))  # stretched down -> long (reversion reading)


def b_roc(d, n=10, k=1.0, **_):
    r = np.log(d["close"]).diff(int(n))
    sd = np.log(d["close"]).diff().rolling(200, min_periods=50).std() * np.sqrt(int(n))
    return _sgn(r > float(k) * sd, r < -float(k) * sd)


def b_bollinger(d, n=20, k=2.0, **_):
    c = d["close"]
    m = _sma(c, int(n))
    s = c.rolling(int(n), min_periods=int(n)).std()
    return _sgn(c < m - float(k) * s, c > m + float(k) * s)


def b_channel_pos(d, n=50, edge=0.2, **_):
    hh = d["high"].rolling(int(n), min_periods=int(n)).max()
    ll = d["low"].rolling(int(n), min_periods=int(n)).min()
    p = (d["close"] - ll) / (hh - ll).replace(0.0, np.nan)
    return _sgn(p > 1.0 - float(edge), p < float(edge))


def b_streak(d, n=3, **_):
    up = (d["close"].diff() > 0).astype(int)
    dn = (d["close"].diff() < 0).astype(int)
    return _sgn(up.rolling(int(n)).sum() == int(n), dn.rolling(int(n)).sum() == int(n))


def b_stoch(d, n=14, lo=20, **_):
    hh = d["high"].rolling(int(n), min_periods=int(n)).max()
    ll = d["low"].rolling(int(n), min_periods=int(n)).min()
    k = 100.0 * (d["close"] - ll) / (hh - ll).replace(0.0, np.nan)
    return _sgn(k < float(lo), k > 100.0 - float(lo))


def b_vol_thrust(d, n=20, k=2.0, **_):
    v = d["tick_volume"] if "tick_volume" in d.columns else d.get("volume")
    if v is None:
        return np.zeros(len(d), dtype=np.int8)
    spike = v > float(k) * v.rolling(int(n), min_periods=int(n)).mean()
    r = d["close"] - d["open"]
    return _sgn(spike & (r > 0), spike & (r < 0))


def b_inside_break(d, **_):
    h, low_ = d["high"], d["low"]
    inside = (h.shift(1) <= h.shift(2)) & (low_.shift(1) >= low_.shift(2))
    return _sgn(inside & (d["close"] > h.shift(1)), inside & (d["close"] < low_.shift(1)))


def b_range_expansion(d, n=20, k=1.5, **_):
    rng = d["high"] - d["low"]
    big = rng > float(k) * rng.rolling(int(n), min_periods=int(n)).mean().shift(1)
    return _sgn(big & (d["close"] > d["open"]), big & (d["close"] < d["open"]))


BLOCKS: dict[str, tuple[Any, dict[str, list]]] = {
    "ma_state": (b_ma_state, {"n": [20, 50, 100, 200]}),
    "ema_cross": (b_ema_cross, {"fast": [5, 8, 12, 20], "slow": [21, 36, 50, 100]}),
    "breakout": (b_breakout, {"n": [10, 20, 40, 80]}),
    "rsi": (b_rsi, {"n": [2, 5, 14], "lo": [10, 20, 30]}),
    "zscore": (b_zscore, {"n": [10, 20, 50], "k": [1.5, 2.0, 2.5]}),
    "roc": (b_roc, {"n": [5, 10, 24, 48], "k": [0.5, 1.0, 1.5]}),
    "bollinger": (b_bollinger, {"n": [20, 50], "k": [1.5, 2.0, 2.5]}),
    "channel_pos": (b_channel_pos, {"n": [20, 50, 100], "edge": [0.1, 0.2, 0.3]}),
    "streak": (b_streak, {"n": [2, 3, 4, 5]}),
    "stoch": (b_stoch, {"n": [5, 14], "lo": [10, 20, 30]}),
    "vol_thrust": (b_vol_thrust, {"n": [20, 50], "k": [1.5, 2.0, 3.0]}),
    "inside_break": (b_inside_break, {}),
    "range_expansion": (b_range_expansion, {"n": [10, 20, 50], "k": [1.5, 2.0, 2.5]}),
}


#: The mechanism each block expresses. The generator keeps an archive niche per class and seeds
#: immigrants into the least-covered one, so the search spreads across mechanisms instead of
#: converging on whichever style the first lucky genome had (zuck 2026-11-20: maximum breadth).
MECH_CLASS: dict[str, str] = {
    "ma_state": "trend", "ema_cross": "trend", "breakout": "trend", "channel_pos": "trend",
    "roc": "momentum", "streak": "momentum",
    "rsi": "reversion", "zscore": "reversion", "bollinger": "reversion", "stoch": "reversion",
    "range_expansion": "volatility", "inside_break": "volatility",
    "vol_thrust": "flow",
}


# --------------------------------------------------------------------------- filters (gates)
def f_session(d, start=7, end=16, **_):
    h = d.index.hour
    s, e = int(start) % 24, int(end) % 24
    ok = (h >= s) & (h < e) if s < e else (h >= s) | (h < e)
    return np.asarray(ok, dtype=bool), None


def f_vol_regime(d, n=100, lo=0.0, hi=0.5, atr_n=14, **_):
    a = _atr(d, int(atr_n))
    pct = a.rolling(int(n), min_periods=int(n) // 2).rank(pct=True)
    ok = (pct >= float(lo)) & (pct <= float(hi))
    return ok.fillna(False).to_numpy(dtype=bool), None


def f_trend(d, n=200, mode="with", **_):
    c = d["close"]
    m = _sma(c, int(n))
    side = _sgn(c > m, c < m)
    return None, (side, str(mode))


def f_weekday(d, days=(0, 1, 2, 3, 4), **_):
    return np.isin(d.index.dayofweek, list(days)), None


FILTERS: dict[str, tuple[Any, dict[str, list]]] = {
    "session": (f_session, {"start": [0, 2, 7, 8, 12, 13], "end": [6, 10, 12, 16, 20, 22]}),
    "vol_regime": (f_vol_regime, {"n": [100, 250], "lo": [0.0, 0.25, 0.5], "hi": [0.5, 0.75, 1.0]}),
    "trend": (f_trend, {"n": [50, 100, 200], "mode": ["with", "against"]}),
    "weekday": (f_weekday, {"days": [[0, 1, 2, 3], [1, 2, 3], [1, 2, 3, 4], [0, 4]]}),
}


def entry_sides(d: pd.DataFrame, entry: list[dict], filters: list[dict],
                invert: bool) -> np.ndarray:
    """Per-bar entry side (-1/0/+1), edge-triggered, filtered; read on CLOSED bars only."""
    n = len(d)
    agree = None
    for blk in entry or []:
        fn = BLOCKS.get(str(blk.get("b")), (None,))[0]
        if fn is None:
            return np.zeros(n, dtype=np.int8)
        s = np.asarray(fn(d, **{k: v for k, v in blk.items() if k != "b"}), dtype=np.int8)
        agree = s if agree is None else np.where(agree == s, s, 0).astype(np.int8)
    if agree is None:
        return np.zeros(n, dtype=np.int8)
    prev = np.concatenate([[0], agree[:-1]])
    side = np.where((agree != 0) & (agree != prev), agree, 0).astype(np.int8)
    if invert:
        side = -side
    for flt in filters or []:
        fn = FILTERS.get(str(flt.get("f")), (None,))[0]
        if fn is None:
            return np.zeros(n, dtype=np.int8)
        mask, directional = fn(d, **{k: v for k, v in flt.items() if k != "f"})
        if mask is not None:
            side = np.where(mask, side, 0).astype(np.int8)
        if directional is not None:
            tside, mode = directional
            want = tside if mode == "with" else -tside
            side = np.where(side == want, side, 0).astype(np.int8)
    return side


@register_family(
    # The grid is the GENERATOR's space, sampled by `research/strategy_builder.py`, never swept
    # as a cartesian product (it is combinatorially huge on purpose). The defaults are one cell.
    param_grid={"stop_atr": [1.0, 1.5, 2.0, 3.0], "rr": [1.0, 1.5, 2.0, 3.0],
                "max_hold_bars": [6, 12, 24, 48, 120],
                "expansion_mult": [0.0, 2.0, 4.0]},
    tags=["rule_builder", "composable", "generated", "conditional_exit"],
)
def family_rule_builder(
    df: pd.DataFrame,
    *,
    entry: list[dict] | None = None,
    filters: list[dict] | None = None,
    invert: bool = False,
    atr_n: int = 14,
    stop_atr: float = 2.0,
    rr: float = 2.0,
    max_hold_bars: int = 24,
    expansion_mult: float = 0.0,
) -> list[Signal]:
    entry = list(entry or [{"b": "breakout", "n": 20}])
    if stop_atr <= 0 or rr <= 0 or int(max_hold_bars) < 1 or not (1 <= len(entry) <= 3):
        return []
    d = _h1(df)
    if len(d) < 300:
        return []
    side = entry_sides(d, entry, list(filters or []), bool(invert))
    atr = _atr(d, max(2, int(atr_n))).to_numpy(dtype=float)
    px = d["close"].to_numpy(dtype=float)
    idx = d.index
    hold = int(max_hold_bars)
    sigs: list[Signal] = []
    last_exit = -1
    for i in np.flatnonzero(side[:-1]):
        if i <= last_exit:
            continue
        a = atr[i]
        if not np.isfinite(a) or a <= 0:
            continue
        s = int(side[i])
        e = px[i]
        sigs.append(Signal(time=idx[i], side=s, stop=e - s * stop_atr * a,
                           target=e + s * stop_atr * a * rr, ttl_bars=hold,
                           tag="rule_builder", trigger=None, wait_bars=1))
        last_exit = i + hold
    return apply_exit_operators(d, sigs, expansion_mult=float(expansion_mult),
                                exit_on_anchor_flip=False, anchor=None, atr_n=int(atr_n))
