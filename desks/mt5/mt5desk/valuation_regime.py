"""VALUATION AND QUALITY REGIMES FROM POINT-IN-TIME FUNDAMENTALS: one state, three consumers.

The fundamentals dataset (`mt5desk/fundamentals_pit.py`) feeds the desk three ways, and all three
read the SAME regime computation here so a cell, a report and an allocation read agree:

  DIRECT      `families_quantamental` ranks single names on value, quality and earnings yield.
  INDIRECT    `family_valuation_regime_conditioned` (below) keeps an EXISTING class-book cell's
              signals only while a lagged valuation or quality regime holds -- the equity class
              books and quantamental books on the single names, the index class books on the
              indices, and the semis sector book on its members.
  ALLOCATION  `research/sec_fundamentals.py` publishes `reports/SECTOR_VALUATION_STATE.json`:
              each class's current level, its percentile in its own history, and the state these
              regimes read, for the allocator's regime inputs to consume.

THE REGIMES, AND THEIR PRIORS (written before any data was looked at):

  market_value     The equity class's median earnings yield (price at the bar store's close, EPS
      as accepted) against its own trailing median. A cheap market carries a higher forward
      equity premium (Campbell & Shiller 1988; Cochrane 2008), so risk-on legs should pay more
      when it is `cheap` and less when `rich`.
  value_spread     The cross-sectional spread of earnings yield (75th minus 25th percentile)
      against its own history. A wide spread predicts value's return (Asness, Friedman, Krail &
      Liew 2000; Cohen, Polk & Vuolteenaho 2003): `wide` or `narrow`.
  market_quality   The class's median gross margin against its history: `high` or `low`. A
      low-margin regime is the late-cycle squeeze in which defensive and quality legs pay.
  semis_value      The semis book's median earnings yield against its own history: `cheap` or
      `rich`, for the sector book's members.

NO LOOKAHEAD. The level on a decision day uses only fundamentals accepted by that day's stamp and
prices at that stamp; the STATE on day t compares level[t-1] with the trailing median of levels
through t-1 (`families_cross_sectional._lagged_high`), and a base signal reads the state of the
last decision stamp at or before it.
"""
from __future__ import annotations

from collections import OrderedDict
from typing import Any

import numpy as np
import pandas as pd
from mt5desk import families_cross_sectional as xs
from mt5desk import fundamentals_pit as fp
from mt5desk.families import Signal, _h1

#: regime -> (the class whose members it is measured over, the two states: high, low)
REGIMES: dict[str, tuple[str, tuple[str, str]]] = {
    "market_value": ("equity", ("cheap", "rich")),
    "value_spread": ("equity", ("wide", "narrow")),
    "market_quality": ("equity", ("high", "low")),
    "semis_value": ("semis", ("cheap", "rich")),
}

#: The classes whose members may carry a conditioned cell, and the regimes each may read.
REGIMES_FOR_CLASS: dict[str, tuple[str, ...]] = {
    "equity": ("market_value", "value_spread", "market_quality"),
    "index": ("market_value", "market_quality"),
    "semis": ("semis_value",),
}

#: Trailing decision days the regime's own reference median is taken over.
HISTORY_D = 500
MIN_COVERED = 5
MAX_AGE_D = 200.0

_LEVEL_CACHE: OrderedDict[tuple, np.ndarray] = OrderedDict()
_LEVEL_CACHE_MAX = 64


def _members(klass: str) -> list[str]:
    covered = set(fp.covered_symbols())
    return [m for m in xs.class_symbols(klass) if m.upper() in covered]


def class_characteristic(klass: str, stamps: np.ndarray, name: str) -> np.ndarray:
    """rows x covered members: `name` as known at each stamp (NaN where stale or absent)."""
    members = _members(klass)
    out = np.full((len(stamps), len(members)), np.nan, dtype="float64")
    for j, m in enumerate(members):
        ok = fp.fresh(m, stamps, MAX_AGE_D)
        if not ok.any():
            continue
        if name in ("gross_margin", "operating_margin", "roe", "net_margin"):
            v = fp.asof(m, stamps, name)
        else:
            series = xs._load_series(m)
            if series is None:
                continue
            t, c = series
            k = np.searchsorted(t, stamps, side="right") - 1
            price = np.where(k >= 0, c[np.maximum(k, 0)].astype("float64"), np.nan)
            v = fp.valuation(m, stamps, price)[name]
        out[:, j] = np.where(ok, v, np.nan)
    return out


def _row_quantile(m: np.ndarray, q: float) -> np.ndarray:
    n = np.isfinite(m).sum(axis=1)
    out = np.full(m.shape[0], np.nan)
    rows = np.flatnonzero(n >= MIN_COVERED)
    if rows.size:
        out[rows] = pd.DataFrame(m[rows]).quantile(q, axis=1).to_numpy()
    return out


def regime_level(regime: str, stamps: np.ndarray) -> np.ndarray:
    """The regime's level on each stamp (NaN where fewer than MIN_COVERED members are known)."""
    stamps = np.asarray(stamps, dtype="int64")
    key = (regime, fp._CACHE.get("key"), int(stamps[0]) if len(stamps) else 0,
           int(stamps[-1]) if len(stamps) else 0, len(stamps))
    hit = _LEVEL_CACHE.get(key)
    if hit is not None:
        return hit
    klass = REGIMES[regime][0]
    if regime == "market_quality":
        level = _row_quantile(class_characteristic(klass, stamps, "gross_margin"), 0.5)
    elif regime == "value_spread":
        ey = class_characteristic(klass, stamps, "earnings_yield")
        level = _row_quantile(ey, 0.75) - _row_quantile(ey, 0.25)
    else:
        level = _row_quantile(class_characteristic(klass, stamps, "earnings_yield"), 0.5)
    _LEVEL_CACHE[key] = level
    while len(_LEVEL_CACHE) > _LEVEL_CACHE_MAX:
        _LEVEL_CACHE.popitem(last=False)
    return level


def regime_state(regime: str, stamps: np.ndarray) -> np.ndarray:
    """+1 (the first-named state), -1 (the second), 0 (unmeasured) per stamp, LAGGED one row."""
    level = regime_level(regime, stamps)
    high = xs._lagged_high(level, HISTORY_D, None)
    known = np.isfinite(pd.Series(level).shift(1).to_numpy())
    ref_ok = pd.Series(level).shift(1).rolling(HISTORY_D, min_periods=HISTORY_D // 2) \
        .median().notna().to_numpy()
    out = np.zeros(len(level), dtype="int64")
    out[known & ref_ok & high] = 1
    out[known & ref_ok & ~high] = -1
    return out


def family_valuation_regime_conditioned(
    df: pd.DataFrame, *, symbol: str = "", base_family: str = "",
    base_params: dict[str, Any] | None = None, regime: str = "market_value",
    state: str = "cheap", decision_hour: int = 22, max_stale_h: float = 12.0,
) -> list[Signal]:
    """`base_family`'s own signals on `symbol`, kept only while the lagged `regime` is in
    `state`. The base must be a class-book family (the cross-sectional lane); anything else, an
    unknown regime or state, or a regime the symbol's class may not read returns []."""
    from mt5desk import class_books
    if (not symbol or regime not in REGIMES or state not in REGIMES[regime][1]
            or base_family not in class_books.FAMILIES
            or base_family == "valuation_regime_conditioned"):
        return []
    klasses = {xs.class_of(symbol)}
    try:
        klasses |= set(xs._policy().sector_books_of(symbol))
    except Exception:
        klasses |= set()
    if not any(regime in REGIMES_FOR_CLASS.get(str(k), ()) for k in klasses):
        return []
    params = {k: v for k, v in dict(base_params or {}).items()
              if k not in ("timeframe", "session")}
    params["symbol"] = symbol
    if df is None or len(df) == 0:
        return []
    d = _h1(df)
    try:
        base = list(class_books.FAMILIES[base_family](d, **params) or [])
    except Exception:
        return []
    if not base:
        return []
    pos, stamps = xs._decision_rows(d, decision_hour, max_stale_h)
    if pos.size == 0:
        return []
    st = regime_state(regime, stamps)
    want = 1 if state == REGIMES[regime][1][0] else -1
    out = []
    for s in base:
        k = int(np.searchsorted(stamps, pd.Timestamp(s.time).value, side="right")) - 1
        if k >= 0 and st[k] == want:
            out.append(s)
    return out


# ------------------------------------------------------------------ the allocation artifact ---
def state_now(stamps: np.ndarray) -> dict[str, Any]:
    """Each regime's level, percentile in its own history and current state, over `stamps`."""
    out: dict[str, Any] = {}
    for regime, (klass, names) in REGIMES.items():
        level = regime_level(regime, stamps)
        finite = np.flatnonzero(np.isfinite(level))
        if finite.size == 0:
            out[regime] = {"class": klass, "status": "UNMEASURED",
                           "why": f"fewer than {MIN_COVERED} {klass} members carry fundamentals"}
            continue
        last = int(finite[-1])
        hist = level[finite[max(0, finite.size - HISTORY_D):]]
        st = regime_state(regime, stamps)[last]
        # the state a cell would read TOMORROW is today's level against the history through today
        ref = float(np.median(hist))
        out[regime] = {"class": klass, "level": round(float(level[last]), 6),
                       "reference_median": round(ref, 6),
                       "percentile_in_history": round(float((hist <= level[last]).mean()), 4),
                       "history_days": int(hist.size),
                       "state_next": names[0] if level[last] > ref else names[1],
                       "state_today": {1: names[0], -1: names[1]}.get(int(st), "UNMEASURED"),
                       "as_of": pd.Timestamp(int(stamps[last]), tz="UTC").isoformat()}
    return out


def daily_stamps(days: int = 900, hour: int = 22) -> np.ndarray:
    """Weekday stamps at `hour` UTC over the last `days` calendar days, for the state report."""
    end = pd.Timestamp.now(tz="UTC").normalize()
    dates = pd.bdate_range(end - pd.Timedelta(days=days), end, tz="UTC")
    return (dates + pd.Timedelta(hours=hour)).as_unit("ns").asi8.astype("int64")
