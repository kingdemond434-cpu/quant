"""CROSS-SECTIONAL CLASS BOOKS, one symbol per cell, so the SEALED gauntlet can judge them.

WHY THIS FILE EXISTS WHEN `family_cross_sectional` ALREADY DOES. That family takes its peer set as
an argument (`peers: dict[str, DataFrame]`), and the sealed gauntlet's `build_cell` has an input
branch for carry, peers, factors, tape, macro, COT and events -- and none for `peers`. So every
`cross_sectional` cell the gauntlet ever built was called with `peers=None`, returned [] by its own
guard, produced no daily series and came back UNKNOWN. The `cross_sectional_fx` cluster sat at zero
cells and zero certificates while two registered families "classified into it". The gauntlet is
immutable (IMMUTABLE_MANIFEST) and is not edited; instead, every family here LOADS ITS OWN CLASS
PANEL from the desk's bar store, keyed by nothing but the `symbol` parameter the cell carries. The
same call builds the same signals in the gauntlet, the forward clock and the live executor, with
no input branch anywhere.

THE SHAPE OF A CELL. A tier-1 cross-sectional book is long the top of a class and short the bottom,
market-neutral within the class. The gauntlet builds one symbol per cell, so the book is expressed
as its LEGS: a cell is "SYMBOL, long while it ranks in the top `quantile` of its class, short while
it ranks in the bottom". Every member of a class carries the same rule, so the union of the class's
certified legs IS the neutral book, and each leg is judged on its own evidence. R-multiples are
measured against a stop set in units of the leg's own daily volatility, so the legs are
risk-normalised -- which is what makes a rank book (and betting-against-beta in particular) a
neutral one rather than a bet on whichever member moves most.

THE FAMILIES AND THEIR ECONOMIC PRIORS (written down before any data was looked at):

  cross_sectional_class_momentum   Slow-moving capital and under-reaction: information diffuses
      across a class over weeks, so relative winners keep winning. Moskowitz & Grinblatt;
      Menkhoff et al. (2012, currencies); Asness, Moskowitz & Pedersen (2013, "Value and Momentum
      Everywhere", indices/commodities/FX). Payer: the slow reallocator. Optional LAGGED
      dispersion conditioner: momentum pays when the class is dispersed (there is a spread to
      earn), and a lagged conditioner selects a regime, never a realisation.
  cross_sectional_class_reversal   Liquidity provision in the cross-section: a member pushed to
      the extreme of its class over one to five days by an impatient flow reverts as that flow's
      inventory is laid off (Lehmann 1990; Nagel 2012 -- reversal returns are the price of
      immediacy and rise with dispersion). Payer: the liquidity demander.
  cross_sectional_class_value      Mean reversion to a long-run level, ranked: the member furthest
      below its own one-to-two-year level (in its own volatility units) is cheap RELATIVE to its
      class. AMP (2013) value; PPP reversion for currencies. Payer: the extrapolator.
  cross_sectional_class_low_vol    Betting against beta within a class: leverage-constrained
      investors reach for the high-beta members and overpay for them (Frazzini & Pedersen 2014).
      Long the lowest-vol/beta members, short the highest, each leg risk-normalised.
  crisis_only_class_defensive      Forced deleveraging: in a stress regime (the class's own
      trailing volatility in the upper part of its history, read with a lag) margin calls and
      risk limits sell the high-beta members hardest (Brunnermeier & Pedersen 2009). Long the
      class's lowest-beta third, short its highest-beta third, ONLY in stress. Fires specifically
      in the book's worst periods, which is the crisis_drawdown cluster's bar.
  lead_lag_class_catchup           Slow updaters: a member's return today is partly its class's
      return yesterday, because its participants watch a different screen. The causal lagged
      beta on the class ex-self predicts which members have not yet caught up; long the members
      predicted to rise most, short those predicted to fall most. Payer: the slow updater.

NO LOOKAHEAD, BY CONSTRUCTION. The decision bar for a day is the symbol's own last bar at or
before `decision_hour` (broker stamp hour). Every peer is read AS OF THAT BAR'S STAMP -- a peer bar
stamped later is invisible -- and a peer whose last bar is older than `max_stale_h` hours is
ABSENT from that day's cross-section, never carried forward: a stale price silently re-ranks
every other member. Every window is trailing; every conditioner is lagged a row. The signal
enters at the next bar's open, like every orthogonal family (`trigger=None`).

HONEST LIMITS. A family returns [] (never a price-only fallback) when: `symbol` is empty or not in
a peer class, fewer than MIN_CLASS_MEMBERS members are present on a day (that day is skipped), or
the bars are too short for the trailing windows. The panel is read from `data/universe/*_H1.parquet`
-- on the trading box that store is refreshed hourly; if a peer's file is stale the peer is absent
from the recent cross-section rather than wrong in it.
"""
from __future__ import annotations

import math
import sys
from collections import OrderedDict
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pandas as pd
from mt5desk.families import Signal, _h1, bars_per_day

BASE = Path(__file__).resolve().parent.parent
#: Where the class panel is read from. Module-level so a test can point it at synthetic bars.
UNIVERSE_DIR = BASE / "data" / "universe"

#: Members that must be present on a day before that day has a cross-section at all.
MIN_MEMBERS = 5

#: Trailing rows of daily returns the leg's own volatility is measured on, for the stop.
VOL_ROWS = 20

#: Symbols whose close series is held in memory at once. One entry is ~12 bytes per H1 bar (an
#: int64 stamp and a float32 close): 54,000 bars is ~650 KB, so the whole hypothesis universe
#: (~140 symbols) is under 100 MB. Bounded so a larger store cannot grow it without limit.
SERIES_CACHE_MAX = 200

#: The families this module registers, and the params each one is swept on. The grid is the
#: trial count this module charges the family-wise error budget, so it is written out here and
#: nowhere else; the seeding organ reads it rather than restating it.
PARAM_GRID: dict[str, dict[str, list]] = {
    "cross_sectional_class_momentum": {"lookback_d": [20, 60, 120, 250], "hold_d": [5, 20],
                                       "dispersion": ["any", "high"]},
    "cross_sectional_class_reversal": {"lookback_d": [1, 3, 5], "hold_d": [1, 3],
                                       "dispersion": ["any", "high"]},
    "cross_sectional_class_value": {"anchor_d": [250, 500], "hold_d": [10, 20]},
    "cross_sectional_class_low_vol": {"measure": ["vol", "beta"], "window_d": [60, 120],
                                      "hold_d": [5, 20]},
    "crisis_only_class_defensive": {"stress_q": [0.67, 0.8], "hold_d": [3, 5]},
    "lead_lag_class_catchup": {"window_d": [120, 250], "hold_d": [1, 2]},
}

_SERIES_CACHE: OrderedDict[str, tuple[int, np.ndarray, np.ndarray]] = OrderedDict()


# ----------------------------------------------------------------------------------- class ---
def _policy():
    """`research.universe_policy`, importable from the gauntlet, the clock and the gateway."""
    try:
        from research import universe_policy as up
    except ImportError:                                            # pragma: no cover - path
        if str(BASE) not in sys.path:
            sys.path.insert(0, str(BASE))
        from research import universe_policy as up
    return up


def class_of(symbol: str) -> str | None:
    """The peer class `symbol` is ranked within (research.universe_policy.peer_class)."""
    try:
        return _policy().peer_class(symbol)
    except Exception:
        return None


def class_symbols(klass: str) -> list[str]:
    """Every registry member of `klass`. Module-level so a test can substitute a synthetic one."""
    try:
        return list(_policy().class_members(klass))
    except Exception:
        return []


def orientation(symbol: str, klass: str | None) -> int:
    """-1 when the pair must be inverted to read as a currency's dollar value (USDXXX in fx_usd,
    or a USDXXX proxy leg of a sector book such as USDKRW in `semis`)."""
    try:
        oriented = _policy().ORIENTED_CLASSES
    except Exception:
        oriented = frozenset({"fx_usd"})
    if klass not in oriented:
        return 1
    try:
        return int(_policy().usd_orientation(symbol))
    except Exception:
        return 1


# ---------------------------------------------------------------------------------- panel ---
def _load_series(symbol: str) -> tuple[np.ndarray, np.ndarray] | None:
    """(stamps as int64 ns, closes) for `symbol`'s H1 bars from the store, cached per file mtime."""
    path = UNIVERSE_DIR / f"{symbol}_H1.parquet"
    try:
        mtime = path.stat().st_mtime_ns
    except OSError:
        return None
    hit = _SERIES_CACHE.get(symbol)
    if hit is not None and hit[0] == mtime:
        _SERIES_CACHE.move_to_end(symbol)
        return hit[1], hit[2]
    try:
        frame = pd.read_parquet(path)
    except Exception:
        return None
    out = _stamps_closes(frame)
    if out is None:
        return None
    _SERIES_CACHE[symbol] = (mtime, out[0], out[1])
    while len(_SERIES_CACHE) > SERIES_CACHE_MAX:
        _SERIES_CACHE.popitem(last=False)
    return out


def _stamps_closes(frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray] | None:
    if frame is None or len(frame) == 0 or "close" not in frame.columns:
        return None
    idx = frame.index
    if not isinstance(idx, pd.DatetimeIndex):
        col = next((c for c in ("time", "timestamp", "datetime") if c in frame.columns), None)
        if col is None:
            return None
        idx = pd.DatetimeIndex(pd.to_datetime(frame[col], utc=True, errors="coerce"))
    idx = idx.tz_localize("UTC") if idx.tz is None else idx.tz_convert("UTC")
    close = pd.Series(pd.to_numeric(frame["close"], errors="coerce").to_numpy(dtype="float64"),
                      index=idx.as_unit("ns"))
    close = close[~close.index.isna()]
    close = close[np.isfinite(close.to_numpy()) & (close.to_numpy() > 0)]
    close = close[~close.index.duplicated(keep="last")].sort_index()
    if close.empty:
        return None
    return close.index.asi8.astype("int64"), close.to_numpy(dtype="float32")


def _decision_rows(d: pd.DataFrame, decision_hour: int,
                   max_stale_h: float) -> tuple[np.ndarray, np.ndarray]:
    """(bar positions, stamps ns) of the symbol's decision bar on each weekday.

    The decision bar is the LAST bar stamped at or before `decision_hour` on that broker date,
    and no older than `max_stale_h` hours before it. A day without one has no decision.
    """
    idx = d.index
    hours = idx.hour.to_numpy()
    days = idx.normalize()
    dow = days.dayofweek.to_numpy()
    ok = (hours <= int(decision_hour)) & (dow < 5)
    if not ok.any():
        return np.empty(0, dtype="int64"), np.empty(0, dtype="int64")
    pos = np.flatnonzero(ok)
    day_ns = days.asi8[pos]
    # last eligible bar per date: where the next eligible bar is on a different date
    last = np.r_[day_ns[1:] != day_ns[:-1], True]
    pos, day_ns = pos[last], day_ns[last]
    stamps = idx.asi8[pos]
    target = day_ns + int(decision_hour) * 3_600_000_000_000
    fresh = (target - stamps) <= float(max_stale_h) * 3_600_000_000_000
    return pos[fresh], stamps[fresh]


def class_panel(d: pd.DataFrame, symbol: str, *, decision_hour: int = 22,
                max_stale_h: float = 12.0, klass: str | None = None) -> dict | None:
    """The class cross-section on `symbol`'s own decision bars, or None when there is none.

    Returns {"klass", "members", "own", "pos", "logv" (rows x members, oriented log values),
    "orient"}. `own` is the column holding `symbol`, read from `d` itself (the bars the caller
    handed in), never from the store, so the gauntlet's override and the live frame are honoured.

    `klass` names a SECTOR book (e.g. `semis`) to rank within instead of the symbol's primary
    peer class; `symbol` must then be a member of that book, or there is no panel.
    """
    if klass is None:
        klass = class_of(symbol)
        if not klass:
            return None
        roster = class_symbols(klass)
    else:
        roster = class_symbols(klass)
        if symbol.upper() not in {s.upper() for s in roster}:
            return None
    members = [s for s in roster if s.upper() != symbol.upper()]
    pos, stamps = _decision_rows(d, decision_hour, max_stale_h)
    if pos.size == 0:
        return None
    stale_ns = float(max_stale_h) * 3_600_000_000_000
    cols: list[np.ndarray] = []
    names: list[str] = []
    for peer in members:
        series = _load_series(peer)
        if series is None:
            continue
        t, c = series
        j = np.searchsorted(t, stamps, side="right") - 1
        v = np.full(stamps.size, np.nan, dtype="float64")
        has = j >= 0
        jj = np.where(has, j, 0)
        fresh = has & ((stamps - t[jj]) <= stale_ns)
        v[fresh] = np.log(c[jj[fresh]].astype("float64")) * orientation(peer, klass)
        if np.isfinite(v).sum() == 0:
            continue
        cols.append(v)
        names.append(peer)
    if len(names) + 1 < MIN_MEMBERS:
        return None
    own_close = d["close"].to_numpy(dtype="float64")[pos]
    with np.errstate(divide="ignore", invalid="ignore"):
        own = np.where(own_close > 0, np.log(own_close), np.nan) * orientation(symbol, klass)
    logv = np.column_stack([own, *cols])
    return {"klass": klass, "members": [symbol, *names], "own": 0, "pos": pos,
            "logv": logv, "orient": orientation(symbol, klass), "close": own_close,
            "stamps": stamps}


# ------------------------------------------------------------------------------ primitives ---
def _shift(m: np.ndarray, k: int) -> np.ndarray:
    out = np.full_like(m, np.nan)
    if k <= 0:
        return m.copy()
    if k < m.shape[0]:
        out[k:] = m[:-k]
    return out


def _rolling(m: np.ndarray, window: int, how: str, min_frac: float = 0.8) -> np.ndarray:
    frame = pd.DataFrame(m)
    r = frame.rolling(int(window), min_periods=max(2, int(window * min_frac)))
    return getattr(r, how)().to_numpy()


def _returns(logv: np.ndarray) -> np.ndarray:
    return logv - _shift(logv, 1)


def _row_mean_std(m: np.ndarray, min_n: int = 2) -> tuple[np.ndarray, np.ndarray]:
    """Per-row mean and sample std over finite entries; NaN where fewer than `min_n` exist.
    Written out rather than `np.nanmean`, which WARNS on an all-NaN row (a test failure here)."""
    valid = np.isfinite(m)
    n = valid.sum(axis=1)
    x = np.where(valid, m, 0.0)
    s1, s2 = x.sum(axis=1), (x * x).sum(axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        mean = np.where(n >= 1, s1 / np.maximum(n, 1), np.nan)
        var = np.where(n >= 2, (s2 - n * mean * mean) / np.maximum(n - 1, 1), np.nan)
    ok = n >= int(min_n)
    return np.where(ok, mean, np.nan), np.where(ok, np.sqrt(np.clip(var, 0.0, None)), np.nan)


def _ew_ex_self(r: np.ndarray) -> np.ndarray:
    """Each member's class return excluding itself: (row sum - own) / (row count - 1)."""
    valid = np.isfinite(r)
    s = np.where(valid, r, 0.0).sum(axis=1, keepdims=True)
    n = valid.sum(axis=1, keepdims=True)
    with np.errstate(divide="ignore", invalid="ignore"):
        ex = (s - np.where(valid, r, 0.0)) / (n - 1)
    ex[~valid | (n - 1 < 1)] = np.nan
    return ex


def _beta(r: np.ndarray, x: np.ndarray, window: int) -> np.ndarray:
    """Trailing beta of each column of r on the matching column of x, over `window` rows."""
    both = np.isfinite(r) & np.isfinite(x)
    rr, xx = np.where(both, r, np.nan), np.where(both, x, np.nan)
    mr, mx = _rolling(rr, window, "mean"), _rolling(xx, window, "mean")
    mrx = _rolling(rr * xx, window, "mean")
    mxx = _rolling(xx * xx, window, "mean")
    var = mxx - mx * mx
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(var > 0, (mrx - mr * mx) / var, np.nan)


def _lagged_high(series: np.ndarray, window: int, q: float | None) -> np.ndarray:
    """Row t is True when series[t-1] is above its own trailing quantile (median when q None),
    both read strictly before t. A LAGGED conditioner, which selects a regime and not a
    realisation (libs/research/effective_breadth: the collider this avoids)."""
    s = pd.Series(series).shift(1)
    roll = s.rolling(int(window), min_periods=max(2, int(window * 0.5)))
    ref = roll.median() if q is None else roll.quantile(float(q))
    return (s > ref).to_numpy() & np.isfinite(ref.to_numpy())


def _rank_sides(score: np.ndarray, own: int, quantile: float,
                gate: np.ndarray | None = None) -> np.ndarray:
    """+1 / -1 / 0 per row: own member in the top / bottom `quantile` of the valid cross-section."""
    valid = np.isfinite(score)
    n = valid.sum(axis=1)
    k = np.maximum(1, np.floor(n * float(quantile))).astype("int64")
    own_s = score[:, own]
    ok = valid[:, own] & (n >= MIN_MEMBERS)
    if gate is not None:
        ok &= gate
    with np.errstate(invalid="ignore"):
        below = (valid & (score < own_s[:, None])).sum(axis=1)
        above = (valid & (score > own_s[:, None])).sum(axis=1)
    side = np.zeros(score.shape[0], dtype="int64")
    side[ok & (above < k)] = 1
    side[ok & (below < k)] = -1
    # a class of ties (flat day) ranks nobody
    side[ok & (above < k) & (below < k)] = 0
    return side


def _signals(d: pd.DataFrame, panel: dict, side: np.ndarray, *, hold_d: int, stop_sd: float,
             rr: float, tag: str) -> list[Signal]:
    """Turn per-decision-row sides into next-open Signals on the symbol's own bars."""
    pos, close = panel["pos"], panel["close"]
    own_r = _returns(panel["logv"][:, [panel["own"]]])[:, 0]
    sd = pd.Series(own_r).rolling(VOL_ROWS, min_periods=VOL_ROWS).std(ddof=1).to_numpy()
    ttl = max(1, int(hold_d) * bars_per_day(d))
    horizon = math.sqrt(max(1, int(hold_d)))
    orient = int(panel["orient"])
    out: list[Signal] = []
    n_bars = len(d)
    idx = d.index
    for r in np.flatnonzero(side != 0):
        p = int(pos[r])
        if p >= n_bars - 1:
            continue
        s, px = float(sd[r]), float(close[r])
        if not (math.isfinite(s) and s > 0 and math.isfinite(px) and px > 0):
            continue
        trade_side = int(side[r]) * orient
        dist = float(stop_sd) * s * horizon * px
        out.append(Signal(time=idx[p], side=trade_side, stop=px - trade_side * dist,
                          target=px + trade_side * dist * float(rr), ttl_bars=ttl, tag=tag,
                          trigger=None, wait_bars=1))
    return out


def _prepare(df: pd.DataFrame, symbol: str, decision_hour: int,
             max_stale_h: float, klass: str | None = None) -> tuple[pd.DataFrame, dict] | None:
    if not symbol or df is None or len(df) == 0:
        return None
    d = _h1(df)
    if "close" not in d.columns:
        return None
    panel = class_panel(d, symbol, decision_hour=decision_hour, max_stale_h=max_stale_h,
                        klass=klass)
    if panel is None:
        return None
    return d, panel


def _valid_common(quantile: float, hold_d: int, stop_sd: float, rr: float) -> bool:
    return (0.0 < float(quantile) <= 0.5 and int(hold_d) >= 1 and float(stop_sd) > 0
            and float(rr) > 0)


def _dispersion_gate(r_l: np.ndarray, dispersion: str) -> np.ndarray | None:
    if dispersion == "any":
        return None
    disp = _row_mean_std(r_l, MIN_MEMBERS)[1]
    high = _lagged_high(disp, 250, None)
    return high if dispersion == "high" else (~high & np.isfinite(disp))


# -------------------------------------------------------------------------------- families ---
def family_cross_sectional_class_momentum(
    df: pd.DataFrame, *, symbol: str = "", lookback_d: int = 60, skip_d: int = 0,
    hold_d: int = 20, quantile: float = 1 / 3, dispersion: str = "any",
    decision_hour: int = 22, max_stale_h: float = 12.0, stop_sd: float = 3.0, rr: float = 2.0,
) -> list[Signal]:
    """Long while `symbol`'s `lookback_d`-day return (skipping the last `skip_d`) ranks in the
    top `quantile` of its class, short while it ranks in the bottom."""
    if (not _valid_common(quantile, hold_d, stop_sd, rr) or int(lookback_d) < 1
            or int(skip_d) < 0 or dispersion not in ("any", "high", "low")):
        return []
    got = _prepare(df, symbol, decision_hour, max_stale_h)
    if got is None:
        return []
    d, panel = got
    lv = panel["logv"]
    score = _shift(lv, int(skip_d)) - _shift(lv, int(skip_d) + int(lookback_d))
    gate = _dispersion_gate(lv - _shift(lv, 20), dispersion)
    side = _rank_sides(score, panel["own"], quantile, gate)
    return _signals(d, panel, side, hold_d=hold_d, stop_sd=stop_sd, rr=rr,
                    tag=f"xs_momentum:{panel['klass']}:{lookback_d}")


def family_cross_sectional_class_reversal(
    df: pd.DataFrame, *, symbol: str = "", lookback_d: int = 3, hold_d: int = 3,
    quantile: float = 1 / 3, dispersion: str = "any", decision_hour: int = 22,
    max_stale_h: float = 12.0, stop_sd: float = 3.0, rr: float = 2.0,
) -> list[Signal]:
    """Long while `symbol`'s `lookback_d`-day return ranks in the BOTTOM `quantile` of its class,
    short while it ranks in the top: the class's short-horizon losers are bought from the flow
    that pushed them there."""
    if (not _valid_common(quantile, hold_d, stop_sd, rr) or int(lookback_d) < 1
            or dispersion not in ("any", "high", "low")):
        return []
    got = _prepare(df, symbol, decision_hour, max_stale_h)
    if got is None:
        return []
    d, panel = got
    lv = panel["logv"]
    ret = lv - _shift(lv, int(lookback_d))
    gate = _dispersion_gate(ret, dispersion)
    side = _rank_sides(-ret, panel["own"], quantile, gate)
    return _signals(d, panel, side, hold_d=hold_d, stop_sd=stop_sd, rr=rr,
                    tag=f"xs_reversal:{panel['klass']}:{lookback_d}")


def family_cross_sectional_class_value(
    df: pd.DataFrame, *, symbol: str = "", anchor_d: int = 250, hold_d: int = 20,
    quantile: float = 1 / 3, decision_hour: int = 22, max_stale_h: float = 12.0,
    stop_sd: float = 3.0, rr: float = 2.0,
) -> list[Signal]:
    """Long while `symbol` is among the class members furthest BELOW their own `anchor_d`-day
    level (in units of that level's own dispersion), short while it is among the furthest above."""
    if not _valid_common(quantile, hold_d, stop_sd, rr) or int(anchor_d) < 20:
        return []
    got = _prepare(df, symbol, decision_hour, max_stale_h)
    if got is None:
        return []
    d, panel = got
    lv = panel["logv"]
    prior = _shift(lv, 1)
    mu = _rolling(prior, int(anchor_d), "mean")
    sd = _rolling(prior, int(anchor_d), "std")
    with np.errstate(divide="ignore", invalid="ignore"):
        z = np.where(sd > 0, (lv - mu) / sd, np.nan)
    side = _rank_sides(-z, panel["own"], quantile)
    return _signals(d, panel, side, hold_d=hold_d, stop_sd=stop_sd, rr=rr,
                    tag=f"xs_value:{panel['klass']}:{anchor_d}")


def family_cross_sectional_class_low_vol(
    df: pd.DataFrame, *, symbol: str = "", measure: str = "vol", window_d: int = 60,
    hold_d: int = 20, quantile: float = 1 / 3, decision_hour: int = 22,
    max_stale_h: float = 12.0, stop_sd: float = 3.0, rr: float = 2.0,
) -> list[Signal]:
    """Betting against beta within a class: long while `symbol` is among the class's lowest
    trailing volatility (or beta to the class ex-self), short while it is among the highest."""
    if (not _valid_common(quantile, hold_d, stop_sd, rr) or measure not in ("vol", "beta")
            or int(window_d) < 10):
        return []
    got = _prepare(df, symbol, decision_hour, max_stale_h)
    if got is None:
        return []
    d, panel = got
    r = _returns(panel["logv"])
    risk = (_rolling(r, int(window_d), "std") if measure == "vol"
            else _beta(r, _ew_ex_self(r), int(window_d)))
    side = _rank_sides(-risk, panel["own"], quantile)
    return _signals(d, panel, side, hold_d=hold_d, stop_sd=stop_sd, rr=rr,
                    tag=f"xs_low_{measure}:{panel['klass']}:{window_d}")


def family_crisis_only_class_defensive(
    df: pd.DataFrame, *, symbol: str = "", stress_q: float = 0.67, vol_d: int = 20,
    history_d: int = 500, beta_d: int = 120, hold_d: int = 5, quantile: float = 1 / 3,
    decision_hour: int = 22, max_stale_h: float = 12.0, stop_sd: float = 3.0, rr: float = 2.0,
) -> list[Signal]:
    """ONLY in a lagged stress regime of the class (its equal-weight `vol_d`-day volatility,
    read yesterday, above its own `stress_q` quantile over `history_d` days): long while `symbol`
    is among the class's lowest-beta members, short while among the highest. Idle otherwise."""
    if (not _valid_common(quantile, hold_d, stop_sd, rr) or not 0.0 < float(stress_q) < 1.0
            or int(vol_d) < 5 or int(history_d) < 60 or int(beta_d) < 20):
        return []
    got = _prepare(df, symbol, decision_hour, max_stale_h)
    if got is None:
        return []
    d, panel = got
    r = _returns(panel["logv"])
    ew = _row_mean_std(r, MIN_MEMBERS)[0]
    vol = pd.Series(ew).rolling(int(vol_d), min_periods=int(vol_d)).std(ddof=1).to_numpy()
    stress = _lagged_high(vol, int(history_d), float(stress_q))
    beta = _beta(r, _ew_ex_self(r), int(beta_d))
    side = _rank_sides(-beta, panel["own"], quantile, stress)
    return _signals(d, panel, side, hold_d=hold_d, stop_sd=stop_sd, rr=rr,
                    tag=f"crisis_defensive:{panel['klass']}:{stress_q}")


def family_lead_lag_class_catchup(
    df: pd.DataFrame, *, symbol: str = "", window_d: int = 250, hold_d: int = 1,
    quantile: float = 1 / 3, decision_hour: int = 22, max_stale_h: float = 12.0,
    stop_sd: float = 3.0, rr: float = 2.0,
) -> list[Signal]:
    """Each member's next-day return predicted from its class's return today, through a causal
    lagged beta fitted on the last `window_d` days; long while `symbol`'s prediction is positive
    and in the class's top `quantile`, short while negative and in the bottom."""
    if not _valid_common(quantile, hold_d, stop_sd, rr) or int(window_d) < 40:
        return []
    got = _prepare(df, symbol, decision_hour, max_stale_h)
    if got is None:
        return []
    d, panel = got
    r = _returns(panel["logv"])
    x = _ew_ex_self(r)
    x_lag = _shift(x, 1)
    both = np.isfinite(r) & np.isfinite(x_lag)
    num = _rolling(np.where(both, r * x_lag, np.nan), int(window_d), "sum", 0.5)
    den = _rolling(np.where(both, x_lag * x_lag, np.nan), int(window_d), "sum", 0.5)
    with np.errstate(divide="ignore", invalid="ignore"):
        b = np.where(den > 0, num / den, np.nan)
    pred = b * x
    side = _rank_sides(pred, panel["own"], quantile)
    own_pred = pred[:, panel["own"]]
    side[(side > 0) & ~(own_pred > 0)] = 0
    side[(side < 0) & ~(own_pred < 0)] = 0
    return _signals(d, panel, side, hold_d=hold_d, stop_sd=stop_sd, rr=rr,
                    tag=f"lead_lag_catchup:{panel['klass']}:{window_d}")


CROSS_SECTIONAL_FAMILIES: dict[str, Callable[..., list[Signal]]] = {
    "cross_sectional_class_momentum": family_cross_sectional_class_momentum,
    "cross_sectional_class_reversal": family_cross_sectional_class_reversal,
    "cross_sectional_class_value": family_cross_sectional_class_value,
    "cross_sectional_class_low_vol": family_cross_sectional_class_low_vol,
    "crisis_only_class_defensive": family_crisis_only_class_defensive,
    "lead_lag_class_catchup": family_lead_lag_class_catchup,
}

#: The alpha cluster (libs/research/alpha_clusters) each family is BUILT to occupy, with the
#: economic prior in one line. The seeding organ publishes this beside the live occupancy.
TARGETS: dict[str, dict[str, str]] = {
    "cross_sectional_class_momentum": {
        "cluster": "cross_sectional_fx",
        "prior": "slow-moving capital / under-reaction across a class (Menkhoff et al. 2012; "
                 "Asness, Moskowitz & Pedersen 2013)"},
    "cross_sectional_class_reversal": {
        "cluster": "cross_sectional_fx",
        "prior": "cross-sectional liquidity provision: the price of immediacy (Lehmann 1990; "
                 "Nagel 2012)"},
    "cross_sectional_class_value": {
        "cluster": "cross_sectional_fx",
        "prior": "reversion to a long-run level, ranked within class (AMP 2013 value; PPP)"},
    "cross_sectional_class_low_vol": {
        "cluster": "cross_sectional_fx",
        "prior": "leverage-constrained investors overpay for high beta (Frazzini & Pedersen "
                 "2014), risk-normalised legs"},
    "crisis_only_class_defensive": {
        "cluster": "crisis_drawdown",
        "prior": "forced deleveraging sells a class's high-beta members hardest in stress "
                 "(Brunnermeier & Pedersen 2009)"},
    "lead_lag_class_catchup": {
        "cluster": "cross_asset_lead_lag",
        "prior": "slow updaters: members price the class's move with a lag (Lo & MacKinlay "
                 "1990 lead-lag; Hou 2007)"},
}
