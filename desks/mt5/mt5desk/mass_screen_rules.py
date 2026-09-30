"""THE EXECUTABLE HALF OF THE MASS SCREEN: one rule grammar, one feature set, one thinning law.

`desks/mt5/research/mass_screen.py` generates and screens rule cells in bulk; this module is what
the sealed gauntlet, the forward clock and the live executor call to REBUILD any cell it forwards.
Both sides import the same `features()`, the same `condition_mask()` and the same `thin()`, so the
screen's cheap statistics and the gauntlet's full replay are computed from byte-identical signals.
A cell the screen measured is the cell the judge receives -- there is no second implementation to
drift.

THE RULE, in one sentence: at the close of bar i, when `feat op thr` holds (and the optional
conditioner `cond_lo <= cond_feat < cond_hi`, the optional clock `hour`/`weekday`), enter
`direction` at the next bar's open with a stop `stop_atr` ATRs from bar i's close and a far target
(`TARGET_R` stops away, effectively a time exit), held for `hold` bars. Signals closer than `hold`
bars to the previous kept signal are dropped (`thin`), which is exactly the single-position
discipline `engine.run_backtest` applies -- so every emitted signal fills and the screen's trade
list equals the engine's.

GRAMMARS (the family name is the grammar; the params are the whole identity):

    mass_screen_thresh   one bar-derived feature beyond a quantile threshold
    mass_screen_cond     the same, conditioned on a second feature's tercile or a session bucket
    mass_screen_clock    a fixed broker hour (and optionally weekday) -- intraday seasonality
    mass_screen_lead     a LEADER instrument's normalised return beyond a threshold (lead-lag)
    mass_screen_carry    the positive-carry side, entered at a fixed hour, regime-conditioned

MECHANISM CLASSES, named, because gate 1 asks for one: time-series momentum and short-horizon
reversal (returns over lookbacks), mean reversion to a moving anchor (z-scores, range position),
volatility-regime conditioning (vol ratio, range/ATR), intraday seasonality (clock), cross-asset
information transmission (lead), and carry (swap). Every cell names its class in `mechanism`.

Pure numpy/pandas; no network; bars from `data/universe/<SYM>_H1.parquet`.
"""
from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from mt5desk.families import Signal, _atr, _h1

BASE = Path(__file__).resolve().parent.parent
UNIVERSE = BASE / "data" / "universe"

#: Grammar version, carried in every cell's params so a later grammar change is a new identity.
GRAMMAR_VERSION = 1
#: The target sits this many stops away: far enough that the exit is the stop or the clock, which
#: is what the screen prices. A finite price, so any executor can place it.
TARGET_R = 50.0
#: Lookbacks (bars) of the normalised return features.
RET_LOOKBACKS = (1, 2, 4, 8, 12, 24, 48, 120)
#: Windows (bars) of the z-score-to-moving-mean features.
Z_WINDOWS = (24, 72, 240)
#: Windows (bars) of the position-in-range features.
RPOS_WINDOWS = (24, 120)
#: Lookbacks (bars) of a leader's normalised return.
LEAD_LOOKBACKS = (1, 4, 24)
#: The volatility normaliser: rolling std of one-bar log returns over this many bars.
VOL_WINDOW = 240
VOL_MIN_PERIODS = 120
#: Sentinel for an open conditioner bound (JSON has no infinity).
OPEN_BOUND = 1e300

MECHANISM_OF_FEATURE = {
    "ret": "time-series momentum / short-horizon reversal over the lookback",
    "z": "mean reversion to (or departure from) a moving anchor",
    "rpos": "position in the recent range: breakout continuation or range reversion",
    "volratio": "volatility-regime transition (short vs long realised vol)",
    "rngatr": "bar expansion relative to ATR: exhaustion or continuation after a shock",
    "lead_ret": "cross-asset information transmission from a leader instrument",
    "clock": "intraday / weekday seasonality of flows at a fixed broker hour",
    "carry": "carry: holding the positive-swap side, regime-conditioned",
}


def base_feature_names() -> tuple[str, ...]:
    return (tuple(f"ret_{n}" for n in RET_LOOKBACKS) + tuple(f"z_{n}" for n in Z_WINDOWS)
            + ("volratio",) + tuple(f"rpos_{n}" for n in RPOS_WINDOWS) + ("rngatr",))


def _clean(a: np.ndarray) -> np.ndarray:
    a = np.array(a, dtype="float64", copy=True)
    a[~np.isfinite(a)] = np.nan
    return a


def features(df: pd.DataFrame, *, atr_n: int = 20) -> dict[str, np.ndarray]:
    """Every base feature, causal (bar i uses bars <= i only), as float64 arrays aligned to df.

    Deterministic pandas rolling on the frame handed in, so the screen and the gauntlet -- given
    the same bars -- compute the same numbers.
    """
    c = df["close"].astype("float64")
    h = df["high"].astype("float64")
    lo = df["low"].astype("float64")
    lc = np.log(c.where(c > 0))
    r1 = lc.diff()
    sig = r1.rolling(VOL_WINDOW, min_periods=VOL_MIN_PERIODS).std()
    out: dict[str, np.ndarray] = {}
    for n in RET_LOOKBACKS:
        out[f"ret_{n}"] = _clean(((lc - lc.shift(n)) / (sig * math.sqrt(n))).to_numpy())
    for n in Z_WINDOWS:
        m = c.rolling(n, min_periods=n).mean()
        s = c.rolling(n, min_periods=n).std()
        out[f"z_{n}"] = _clean(((c - m) / s).to_numpy())
    out["volratio"] = _clean(np.log((r1.rolling(24, min_periods=24).std() / sig).to_numpy()))
    for n in RPOS_WINDOWS:
        mn = lo.rolling(n, min_periods=n).min()
        mx = h.rolling(n, min_periods=n).max()
        out[f"rpos_{n}"] = _clean(((c - mn) / (mx - mn)).to_numpy())
    atr = _atr(df, atr_n).to_numpy(dtype="float64")
    out["rngatr"] = _clean((h - lo).to_numpy() / atr)
    return out


def lead_features(df: pd.DataFrame, leader: pd.DataFrame | None) -> dict[str, np.ndarray]:
    """A leader's normalised returns, reindexed CAUSALLY onto df's clock (last leader bar whose
    stamp is <= this bar's stamp: both bars close together, so it is known at decision time)."""
    if leader is None or len(leader) == 0:
        return {}
    lc = np.log(leader["close"].astype("float64").where(leader["close"] > 0))
    r1 = lc.diff()
    sig = r1.rolling(VOL_WINDOW, min_periods=VOL_MIN_PERIODS).std()
    out: dict[str, np.ndarray] = {}
    for n in LEAD_LOOKBACKS:
        z = (lc - lc.shift(n)) / (sig * math.sqrt(n))
        z = z[~z.index.duplicated(keep="last")].sort_index()
        out[f"lead_ret_{n}"] = _clean(z.reindex(df.index, method="ffill").to_numpy())
    return out


def clock_arrays(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    idx = pd.DatetimeIndex(df.index)
    return np.asarray(idx.hour, dtype="int64"), np.asarray(idx.weekday, dtype="int64")


def compare(a: np.ndarray, op: str, thr: float) -> np.ndarray:
    """`a op thr` with NaN never firing."""
    if op == "gt":
        return np.greater(a, thr, where=~np.isnan(a), out=np.zeros(a.shape, dtype=bool))
    if op == "lt":
        return np.less(a, thr, where=~np.isnan(a), out=np.zeros(a.shape, dtype=bool))
    raise ValueError(f"unknown op {op!r}")


def in_band(a: np.ndarray, lo: float, hi: float) -> np.ndarray:
    ok = ~np.isnan(a)
    return ok & (np.where(ok, a, 0.0) >= lo) & (np.where(ok, a, 0.0) < hi)


def condition_mask(feats: dict[str, np.ndarray], hour_arr: np.ndarray, wd_arr: np.ndarray, *,
                   feat: str = "", op: str = "gt", thr: float = 0.0, cond_feat: str = "",
                   cond_lo: float = -OPEN_BOUND, cond_hi: float = OPEN_BOUND,
                   hour: int = -1, weekday: int = -1) -> np.ndarray:
    """The bars at whose close the rule fires, BEFORE thinning."""
    n = len(hour_arr)
    m = np.ones(n, dtype=bool)
    if feat:
        if feat not in feats:
            return np.zeros(n, dtype=bool)
        m &= compare(feats[feat], op, float(thr))
    if cond_feat:
        g = hour_arr.astype("float64") if cond_feat == "hour" else feats.get(cond_feat)
        if g is None:
            return np.zeros(n, dtype=bool)
        m &= in_band(g, float(cond_lo), float(cond_hi))
    if int(hour) >= 0:
        m &= hour_arr == int(hour)
    if int(weekday) >= 0:
        m &= wd_arr == int(weekday)
    return m


try:                                                   # numba is optional; the law is identical
    from numba import njit as _njit
    _HAVE_NUMBA = True
except Exception:                                      # pragma: no cover - depends on the box
    _HAVE_NUMBA = False


def _thin_py(pos: np.ndarray, hold: int) -> np.ndarray:
    """Greedy single-position thinning: keep a fire only when it is more than `hold` bars after
    the previous kept fire. Iterates KEPT fires only (bisect jumps over the blocked ones)."""
    from bisect import bisect_left
    p = pos.tolist()
    out: list[int] = []
    j, n = 0, len(p)
    while j < n:
        v = p[j]
        out.append(v)
        j = bisect_left(p, v + hold + 1, j + 1)
    return np.asarray(out, dtype=np.int64)


if _HAVE_NUMBA:
    @_njit(cache=False)
    def _thin_nb(pos, hold):                           # pragma: no cover - compiled
        out = np.empty(pos.shape[0], dtype=np.int64)
        k = 0
        last = -(1 << 60)
        for i in range(pos.shape[0]):
            v = pos[i]
            if v > last + hold:
                out[k] = v
                k += 1
                last = v
        return out[:k]


def thin(pos: np.ndarray, hold: int) -> np.ndarray:
    pos = np.ascontiguousarray(pos, dtype=np.int64)
    if pos.size == 0:
        return pos
    if _HAVE_NUMBA:
        return _thin_nb(pos, int(hold))
    return _thin_py(pos, int(hold))


@lru_cache(maxsize=16)
def load_bars(symbol: str, timeframe: str = "H1") -> pd.DataFrame | None:
    """A symbol's bars as the gauntlet normalises them, or None when absent."""
    p = UNIVERSE / f"{symbol}_{timeframe}.parquet"
    if not p.exists():
        return None
    try:
        return _h1(pd.read_parquet(p))
    except Exception:
        return None


#: Replaceable in tests: symbol -> bars frame (or None).
LEADER_LOADER = load_bars


def rule_signals(df: pd.DataFrame, *, feat: str, op: str, thr: float, direction: int,
                 hold: int, stop_atr: float, cond_feat: str = "",
                 cond_lo: float = -OPEN_BOUND, cond_hi: float = OPEN_BOUND, hour: int = -1,
                 weekday: int = -1, leader: str = "", atr_n: int = 20,
                 tag: str = "mass_screen") -> list[Signal]:
    h1 = _h1(df)
    if len(h1) < VOL_MIN_PERIODS + 2:
        return []
    feats = features(h1, atr_n=atr_n)
    if leader:
        feats.update(lead_features(h1, LEADER_LOADER(str(leader))))
    hr, wd = clock_arrays(h1)
    m = condition_mask(feats, hr, wd, feat=feat, op=op, thr=thr, cond_feat=cond_feat,
                       cond_lo=cond_lo, cond_hi=cond_hi, hour=hour, weekday=weekday)
    atr = _atr(h1, atr_n).to_numpy(dtype="float64")
    close = h1["close"].to_numpy(dtype="float64")
    m &= np.isfinite(atr) & (atr > 0) & np.isfinite(close)
    kept = thin(np.flatnonzero(m), int(hold))
    side = 1 if int(direction) >= 0 else -1
    idx = h1.index
    sigs: list[Signal] = []
    for i in kept.tolist():
        sd = float(stop_atr) * float(atr[i])
        stop = float(close[i]) - side * sd
        target = float(close[i]) + side * sd * TARGET_R
        sigs.append(Signal(time=idx[i], side=side, stop=stop, target=target,
                           ttl_bars=int(hold), tag=tag))
    return sigs


def family_mass_screen_rule(df: pd.DataFrame, side: int = 1, *, feat: str, op: str, thr: float,
                            direction: int, hold: int, stop_atr: float, cond_feat: str = "",
                            cond_lo: float = -OPEN_BOUND, cond_hi: float = OPEN_BOUND,
                            hour: int = -1, weekday: int = -1, leader: str = "",
                            atr_n: int = 20, gv: int = GRAMMAR_VERSION) -> list[Signal]:
    """The one constructor every mass-screen grammar rebuilds through.

    `side` is accepted and IGNORED: the gauntlet always passes side=1 ("both sides tested
    externally"), so the traded side lives in `direction`, which is part of the cell's identity.
    `feat`, `op`, `thr`, `direction`, `hold` and `stop_atr` have no defaults on purpose: a
    default-parameter sweep (`breadth_sweep.default_families`) must set this family aside rather
    than mint a rule nobody screened.
    """
    del side, gv
    return rule_signals(df, feat=feat, op=op, thr=thr, direction=direction, hold=hold,
                        stop_atr=stop_atr, cond_feat=cond_feat, cond_lo=cond_lo,
                        cond_hi=cond_hi, hour=hour, weekday=weekday, leader=leader,
                        atr_n=atr_n)


GRAMMARS = ("thresh", "cond", "clock", "lead", "carry")
MASS_SCREEN_FAMILIES: dict[str, Any] = {f"mass_screen_{g}": family_mass_screen_rule
                                        for g in GRAMMARS}
