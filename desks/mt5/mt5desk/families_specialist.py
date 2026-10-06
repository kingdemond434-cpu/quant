"""SPECIALIST FAMILIES: domain mechanisms a generic sweep cannot express, and the entry filter
that lets the residual search name a certified cell plus the condition it earns in.

WHY A NEW MODULE. Most of what an asset-class specialist knows is already a registered family
the sealed gauntlet can build -- the WMR fix (`fx_fixing_reversal`, `forced_flow` kind
`fixing`), central-bank and EIA windows (`forced_flow` kinds `central_bank`, `inventory`), the
overnight gap (`overnight_gap_decay`, `monday_gap`), the open drive (`opening_range`), the
gold/silver ratio (`relative_value` with `peer_symbol`), gold against bonds and the dollar
(`cross_asset_residual` with `factor_symbols`). `research/specialist_cell.py` mints those as
cells and adds nothing here for them. Four mechanisms had no family at all:

  carry_risk_off        FX. Carry is harvested in calm and unwound in risk-off: a levered carry
      book is margin-called when equities fall, and the high-yielder is sold into the funding
      currency on somebody else's schedule (Brunnermeier, Nagel & Pedersen 2008, "Carry Trades
      and Currency Crashes"). `harvest` holds the positive-swap side while the RISK PROXY is calm;
      `unwind` takes the anti-carry side on the day the proxy's trailing return breaks down.
      Payer: the levered carry holder who must deleverage. NOT PRICE-ONLY: EXOGENOUS (swap
      terms) and CONDITIONED on the risk proxy -- see `INFORMATION_CLASS`.
  month_end_rebalance   Indices. A balanced fund with fixed equity/bond weights must sell the
      asset that outperformed over the month and buy the one that lagged, and does so in the
      last days of the month (the pension-rebalancing flow). The side is AGAINST the month-to-
      date equity-minus-bond return, read as of the decision bar. Payer: the fixed-weight
      allocator. `turn_of_month` bets on the calendar; this bets on the flow's direction.
      NOT PRICE-ONLY: CONDITIONED on the bond proxy's bars.
  seasonal_window       Softs. A weather or crop-cycle risk premium is priced into a fixed
      stretch of the calendar and bled out as the risk resolves -- the US corn/soy pollination
      premium that decays through July-August, the Brazilian coffee frost season, the West
      African cocoa mid-crop. A day-of-year window, not a month: `calendar_month` cannot say
      "June 15 to August 31". Payer: the hedger who buys weather insurance at any price.
  entry_conditioned     Any family. An OPERATOR, like `exit_operated`: a base cell's own signals
      kept only at the broker hours, weekdays, volatility regime or cross-asset state it was
      measured to earn in. `research/residual_search.py` names these cells from the book's
      residual; the un-filtered base is already in the docket, so the control arm exists.

EVERY INPUT IS LOADED HERE, FROM THE BAR STORE, GIVEN ONLY WHAT THE CELL CARRIES -- the same
contract `families_cross_sectional` keeps. The sealed gauntlet's `build_cell` has no branch that
would hand these families a risk proxy, a bond series or a conditioning symbol, and it is never
edited; so the cell names them (`risk_symbol`, `bond_symbol`, `cond_symbol`) and the family reads
them itself. The gauntlet, the forward clock and the live executor therefore build identical
signals with no input branch anywhere.

NO LOOKAHEAD, BY CONSTRUCTION. Every foreign series is read AS OF the decision bar's stamp -- a
bar stamped later is invisible -- and one older than `max_stale_h` hours is ABSENT, never carried
forward. Calendar windows come from the date alone, never from whether the market turned out to
be open (the defect `family_turn_of_month` was repaired for). Entries are at the next open.

HONEST LIMITS. A family returns [] -- never a price-only fallback -- when a named input symbol has
no bars in the store, when the swap terms are unrecorded (carry), or when a window or filter is
malformed. Month-end uses weekdays, not an exchange holiday table: a holiday on the last weekday
moves the flow a day and this family does not see it, which is written here rather than hidden.
"""
from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from mt5desk.families import Signal, _atr, _h1, bars_per_day

BASE = Path(__file__).resolve().parent.parent
_NS_PER_H = 3_600_000_000_000
_NS_PER_D = 24 * _NS_PER_H


# --------------------------------------------------------------------------- foreign series ---
def _series(symbol: str) -> tuple[np.ndarray, np.ndarray] | None:
    """(stamps ns, closes) of `symbol`'s H1 bars, through the class books' own cached loader so a
    test that points `families_cross_sectional.UNIVERSE_DIR` at synthetic bars points both."""
    from mt5desk import families_cross_sectional as xs
    if not symbol:
        return None
    return xs._load_series(str(symbol))


def asof_close(stamps: np.ndarray, symbol: str, *, max_stale_h: float = 12.0) -> np.ndarray:
    """`symbol`'s close as of each stamp (ns), NaN where absent or older than `max_stale_h`."""
    out = np.full(stamps.size, np.nan, dtype="float64")
    series = _series(symbol)
    if series is None or stamps.size == 0:
        return out
    t, c = series
    j = np.searchsorted(t, stamps, side="right") - 1
    has = j >= 0
    jj = np.where(has, j, 0)
    fresh = has & ((stamps - t[jj]) <= float(max_stale_h) * _NS_PER_H)
    out[fresh] = c[jj[fresh]].astype("float64")
    return out


def trailing_log_return(stamps: np.ndarray, symbol: str, lookback_d: int, *,
                        max_stale_h: float = 12.0) -> np.ndarray:
    """log(close_t / close_{t - lookback_d days}) of `symbol`, both read as of their own stamps.

    THE ONE DEFINITION of a cross-asset state: `entry_conditioned` filters on it and
    `research/residual_search.py` labels the book's trades with it, so a condition the search
    measured is exactly the condition the cell trades."""
    now = asof_close(stamps, symbol, max_stale_h=max_stale_h)
    then = asof_close(stamps - int(lookback_d) * _NS_PER_D, symbol,
                      max_stale_h=max_stale_h + 72.0)       # a weekend may sit under `then`
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where((now > 0) & (then > 0), np.log(now / then), np.nan)


def vol_regime_mask(d: pd.DataFrame, regime: str) -> np.ndarray | None:
    """The desk's own volatility regimes (`family_generic._CONTEXTS`, the definition
    `cell_modifiers` applies for `regime=high_vol`), plus their complements."""
    from mt5desk.family_generic import _CONTEXTS
    key = str(regime or "").strip().lower()
    neg = key.startswith("not_")
    base = key[4:] if neg else key
    if base not in ("high_vol", "low_vol"):
        return None
    m = pd.Series(_CONTEXTS[base](d), index=d.index).fillna(False).astype(bool).to_numpy()
    return ~m if neg else m


def _daily_decisions(d: pd.DataFrame, decision_hour: int) -> np.ndarray:
    """Position of the LAST bar stamped at or before `decision_hour` on each weekday date."""
    idx = d.index
    ok = (idx.hour <= int(decision_hour)) & (idx.dayofweek < 5)
    pos = np.flatnonzero(ok)
    if pos.size == 0:
        return pos
    day = idx.normalize().asi8[pos]
    last = np.r_[day[1:] != day[:-1], True]
    return pos[last]


def _signal(d: pd.DataFrame, p: int, side: int, atr: np.ndarray, *, stop_atr: float, rr: float,
            ttl_bars: int, tag: str) -> Signal | None:
    a = float(atr[p])
    px = float(d["close"].iat[p])
    if not (math.isfinite(a) and a > 0 and math.isfinite(px) and px > 0) or side == 0:
        return None
    dist = float(stop_atr) * a
    return Signal(time=d.index[p], side=int(side), stop=px - side * dist,
                  target=px + side * dist * float(rr), ttl_bars=int(ttl_bars), tag=tag,
                  trigger=None, wait_bars=1)


# ------------------------------------------------------------------------ carry and risk-off ---
def carry_side(symbol: str) -> int:
    """+1 / -1 for the positive-swap side, 0 when the terms are unrecorded or unresolvable --
    `family_carry`'s own resolution, so the two families agree on which side carry is."""
    from mt5desk import families_orthogonal as fo
    terms = fo._swap_terms(str(symbol))
    if not terms:
        return 0
    money = fo.swap_money_per_lot(terms)
    if money is None or money[0] == money[1]:
        return 0
    return 1 if money[0] > money[1] else -1


def family_carry_risk_off(
    df: pd.DataFrame,
    *,
    symbol: str = "",
    mode: str = "harvest",
    risk_symbol: str = "US500",
    lookback_d: int = 5,
    z_thr: float = 1.0,
    vol_window_d: int = 60,
    hold_d: int = 1,
    decision_hour: int = 22,
    atr_n: int = 20,
    stop_atr: float = 2.0,
    rr: float = 1.5,
) -> list[Signal]:
    """`harvest`: the carry side on a day the risk proxy's trailing return is ABOVE -z_thr of its
    own trailing volatility. `unwind`: the anti-carry side on a day it is BELOW. Daily decision
    at `decision_hour`, held `hold_d` days."""
    if mode not in ("harvest", "unwind") or int(lookback_d) < 1 or int(hold_d) < 1:
        return []
    if float(z_thr) <= 0 or int(vol_window_d) < 20 or not symbol or not risk_symbol:
        return []
    side0 = carry_side(symbol)
    if side0 == 0 or df is None or len(df) == 0:
        return []
    d = _h1(df)
    pos = _daily_decisions(d, decision_hour)
    if pos.size < int(vol_window_d) + 2:
        return []
    stamps = d.index.asi8[pos]
    ret = trailing_log_return(stamps, risk_symbol, int(lookback_d))
    daily = trailing_log_return(stamps, risk_symbol, 1)
    sd = pd.Series(daily).rolling(int(vol_window_d), min_periods=int(vol_window_d) // 2).std()
    # the volatility the day's move is judged against is YESTERDAY's, so today's move cannot
    # inflate its own yardstick
    sd_l = sd.shift(1).to_numpy() * math.sqrt(int(lookback_d))
    with np.errstate(divide="ignore", invalid="ignore"):
        z = np.where(sd_l > 0, ret / sd_l, np.nan)
    atr = _atr(d, int(atr_n)).to_numpy()
    ttl = int(hold_d) * bars_per_day(d)
    out: list[Signal] = []
    for k, p in enumerate(pos):
        zk = z[k]
        if not np.isfinite(zk) or p >= len(d) - 1:
            continue
        if mode == "harvest" and zk > -float(z_thr):
            side = side0
        elif mode == "unwind" and zk < -float(z_thr):
            side = -side0
        else:
            continue
        s = _signal(d, int(p), side, atr, stop_atr=stop_atr, rr=rr, ttl_bars=ttl,
                    tag=f"carry_risk_off:{mode}:{risk_symbol}")
        if s is not None:
            out.append(s)
    return out


# ------------------------------------------------------------------ month-end rebalancing ---
def last_weekdays(year: int, month: int, n: int) -> list[date]:
    """The last `n` weekdays of a month, from the calendar alone."""
    nxt = date(year + (month == 12), month % 12 + 1, 1)
    out: list[date] = []
    day = nxt - timedelta(days=1)
    while len(out) < n:
        if day.weekday() < 5:
            out.append(day)
        day -= timedelta(days=1)
    return out


def family_month_end_rebalance(
    df: pd.DataFrame,
    *,
    bond_symbol: str = "UST10Y",
    days_before: int = 3,
    min_gap_sd: float = 1.0,
    vol_window_d: int = 60,
    decision_hour: int = 16,
    hold_d: int = 2,
    atr_n: int = 20,
    stop_atr: float = 2.0,
    rr: float = 1.5,
) -> list[Signal]:
    """In the last `days_before` weekdays of each month: when the index has out-run the bond proxy
    month-to-date by more than `min_gap_sd` of its own monthly spread volatility, sell it; when it
    has lagged by as much, buy it. The flow is the fixed-weight allocator's, so it is against the
    gap."""
    if int(days_before) < 1 or float(min_gap_sd) < 0 or int(hold_d) < 1 or not bond_symbol:
        return []
    if df is None or len(df) == 0:
        return []
    d = _h1(df)
    pos = _daily_decisions(d, decision_hour)
    if pos.size < int(vol_window_d) + 25:
        return []
    idx = d.index
    stamps = idx.asi8[pos]
    close = d["close"].to_numpy(dtype="float64")[pos]
    bond = asof_close(stamps, bond_symbol)
    if not np.isfinite(bond).any():
        return []
    days = idx[pos].normalize()
    month_key = days.year * 12 + days.month
    # the last decision of the PREVIOUS month is the month-to-date base; both legs read as of it
    first = np.r_[True, month_key[1:] != month_key[:-1]]
    base_row = np.maximum.accumulate(np.where(first, np.arange(pos.size), 0)) - 1
    ok = base_row >= 0
    br = np.where(ok, base_row, 0)
    with np.errstate(divide="ignore", invalid="ignore"):
        eq = np.where(ok, np.log(close / close[br]), np.nan)
        bd = np.where(ok, np.log(bond / bond[br]), np.nan)
    gap = eq - bd
    # the spread's volatility over a month, from DAILY spread returns strictly before today
    with np.errstate(divide="ignore", invalid="ignore"):
        dr = np.r_[np.nan, np.diff(np.log(close))] - np.r_[np.nan, np.diff(np.log(bond))]
    sd = (pd.Series(dr).rolling(int(vol_window_d), min_periods=int(vol_window_d) // 2).std()
          .shift(1).to_numpy() * math.sqrt(21.0))
    windows: set[date] = set()
    for y in range(int(days.year.min()), int(days.year.max()) + 1):
        for m in range(1, 13):
            windows.update(last_weekdays(y, m, int(days_before)))
    atr = _atr(d, int(atr_n)).to_numpy()
    ttl = int(hold_d) * bars_per_day(d)
    out: list[Signal] = []
    for k, p in enumerate(pos):
        if days[k].date() not in windows or p >= len(d) - 1:
            continue
        g, s_ = gap[k], sd[k]
        if not (np.isfinite(g) and np.isfinite(s_) and s_ > 0):
            continue
        if abs(g) <= float(min_gap_sd) * s_:
            continue
        sig = _signal(d, int(p), -1 if g > 0 else 1, atr, stop_atr=stop_atr, rr=rr,
                      ttl_bars=ttl, tag=f"month_end_rebalance:{bond_symbol}")
        if sig is not None:
            out.append(sig)
    return out


# ------------------------------------------------------------------------- seasonal window ---
def in_window(day: date, start_md: int, end_md: int) -> bool:
    """Is `day` inside [start_md, end_md] (MMDD ints), wrapping the year end when start > end."""
    md = day.month * 100 + day.day
    if start_md <= end_md:
        return start_md <= md <= end_md
    return md >= start_md or md <= end_md


def _valid_md(md: int) -> bool:
    m, dd = divmod(int(md), 100)
    return 1 <= m <= 12 and 1 <= dd <= 31


def family_seasonal_window(
    df: pd.DataFrame,
    *,
    start_md: int,
    end_md: int,
    side_bias: int,
    decision_hour: int = 16,
    hold_d: int = 1,
    atr_n: int = 20,
    stop_atr: float = 2.0,
    rr: float = 1.5,
) -> list[Signal]:
    """One `side_bias` position a day, decided at `decision_hour`, on every weekday inside the
    window. The window and side are the mechanism's own, stated before the data (the specialist
    organ's catalogue); they are REQUIRED so the family is never called blind."""
    if not (_valid_md(start_md) and _valid_md(end_md)) or int(side_bias) not in (1, -1):
        return []
    if int(hold_d) < 1 or df is None or len(df) == 0:
        return []
    d = _h1(df)
    pos = _daily_decisions(d, decision_hour)
    if pos.size == 0:
        return []
    atr = _atr(d, int(atr_n)).to_numpy()
    ttl = int(hold_d) * bars_per_day(d)
    days = d.index[pos]
    out: list[Signal] = []
    for k, p in enumerate(pos):
        if p < int(atr_n) or p >= len(d) - 1:
            continue
        if not in_window(days[k].date(), int(start_md), int(end_md)):
            continue
        s = _signal(d, int(p), int(side_bias), atr, stop_atr=stop_atr, rr=rr, ttl_bars=ttl,
                    tag=f"seasonal_window:{int(start_md):04d}-{int(end_md):04d}")
        if s is not None:
            out.append(s)
    return out


# ----------------------------------------------------------------------- entry conditioned ---
#: Families whose signals need a data input the gauntlet injects for THEM and not for a wrapper.
#: `families_cross_sectional` and this module's own families load their inputs from what their
#: params carry, so they wrap.
def unwrappable() -> frozenset[str]:
    from mt5desk.family_exit_operated import _UNWRAPPABLE
    return frozenset(_UNWRAPPABLE | {"entry_conditioned", "exit_operated"}) - {"carry"}


def wrappable(name: str) -> bool:
    from mt5desk.families import get_family_func
    return bool(name) and name not in unwrappable() and get_family_func(name) is not None


def _ints(v: Any) -> list[int] | None:
    if v is None:
        return None
    if isinstance(v, (int, np.integer)):
        return [int(v)]
    if isinstance(v, str):
        v = [x for x in v.replace(",", " ").split() if x]
    try:
        return sorted({int(x) for x in v})
    except (TypeError, ValueError):
        return None


def family_entry_conditioned(
    df: pd.DataFrame,
    *,
    base_family: str = "",
    base_params: dict[str, Any] | None = None,
    symbol: str = "",
    hours: Sequence[int] | None = None,
    dows: Sequence[int] | None = None,
    vol_regime: str = "",
    cond_symbol: str = "",
    cond_lookback_d: int = 5,
    cond_sign: int = 0,
) -> list[Signal]:
    """`base_family`'s signals kept only where every named condition holds at the signal bar:
    its broker hour in `hours`, its weekday in `dows`, the volatility regime `vol_regime`
    (`high_vol`, `low_vol`, `not_high_vol`, `not_low_vol`), and the sign of `cond_symbol`'s
    trailing `cond_lookback_d`-day log return equal to `cond_sign`. A cell naming no condition is
    the base cell again under a second multiplicity charge, so it returns []."""
    if not base_family or not wrappable(base_family):
        return []
    hs, ds = _ints(hours), _ints(dows)
    if hours is not None and (hs is None or not hs or any(h < 0 or h > 23 for h in hs)):
        return []
    if dows is not None and (ds is None or not ds or any(x < 0 or x > 6 for x in ds)):
        return []
    use_cond = bool(cond_symbol) and int(cond_sign) in (1, -1)
    if not (hs or ds or vol_regime or use_cond):
        return []
    if int(cond_lookback_d) < 1:
        return []
    from mt5desk.families import get_family_func
    fn = get_family_func(base_family)
    if fn is None or df is None or len(df) == 0:
        return []
    params = dict(base_params or {})
    for k in ("timeframe", "session"):
        params.pop(k, None)
    try:
        import inspect
        takes_symbol = "symbol" in inspect.signature(fn).parameters
    except (TypeError, ValueError):
        takes_symbol = False
    if takes_symbol and symbol and not params.get("symbol"):
        params["symbol"] = symbol
    d = _h1(df)
    try:
        raw = fn(d, side=1, **params)
    except TypeError:
        try:
            raw = fn(d, **params)
        except Exception:
            return []
    except Exception:
        return []
    sigs = [s for s in (raw or []) if isinstance(s, Signal)]
    if not sigs:
        return []
    keep = np.ones(len(sigs), dtype=bool)
    times = pd.DatetimeIndex([pd.Timestamp(s.time) for s in sigs])
    if times.tz is None:
        times = times.tz_localize("UTC")
    if hs:
        keep &= np.isin(times.hour, hs)
    if ds:
        keep &= np.isin(times.dayofweek, ds)
    if vol_regime:
        mask = vol_regime_mask(d, vol_regime)
        if mask is None:
            return []
        at = d.index.get_indexer(times)
        keep &= (at >= 0) & mask[np.where(at >= 0, at, 0)]
    if use_cond:
        r = trailing_log_return(times.as_unit("ns").asi8, cond_symbol, int(cond_lookback_d))
        keep &= np.isfinite(r) & (np.sign(r) == int(cond_sign))
    return [s for s, k in zip(sigs, keep, strict=True) if k]


SPECIALIST_FAMILIES: dict[str, Callable[..., list[Signal]]] = {
    "carry_risk_off": family_carry_risk_off,
    "month_end_rebalance": family_month_end_rebalance,
    "seasonal_window": family_seasonal_window,
    "entry_conditioned": family_entry_conditioned,
}

#: WHAT KIND OF INFORMATION EACH FAMILY BETS ON -- and it is NOT price for two of them.
#:
#: `carry_risk_off` and `month_end_rebalance` were first registered beside `seasonal_window` as
#: if all three were bar-only: `gauntlet_buildability` read their foreign series as ordinary
#: parameters and said the gauntlet "supplies every data input it reads", which is the verdict a
#: price-only family gets. They are not price-only. `carry_risk_off` reads a DATASET the bars do
#: not carry (the venue's recorded swap terms, `data/tape/contract_terms`) and conditions on a
#: second instrument's path (the risk proxy); `month_end_rebalance` conditions on the bond
#: proxy's month-to-date return. So:
#:
#:   exogenous    the family reads a dataset that is not a price series (swap terms)
#:   conditioned  the family conditions the traded instrument on ANOTHER instrument's bars
#:   price_only   the traded instrument's own bars and the calendar, nothing else
#:
#: `FOREIGN_SERIES` names, per family, the PARAMETER that names each foreign series and the
#: dataset it is read from, so a reader (buildability, the report, the forward clock's needs
#: text) sees the input by name rather than inferring it from prose. `entry_conditioned` is
#: conditioned only when its cell names a `cond_symbol`; otherwise it is its base's information.
INFORMATION_CLASS: dict[str, str] = {
    "carry_risk_off": "exogenous",
    "month_end_rebalance": "conditioned",
    "seasonal_window": "price_only",
    "entry_conditioned": "conditioned",
}
FOREIGN_SERIES: dict[str, tuple[tuple[str | None, str], ...]] = {
    "carry_risk_off": ((None, "data/tape/contract_terms (swap terms, as `family_carry` reads "
                              "them through families_orthogonal._swap_terms)"),
                       ("risk_symbol", "data/universe/<risk_symbol>_H1.parquet")),
    "month_end_rebalance": (("bond_symbol", "data/universe/<bond_symbol>_H1.parquet"),),
    "seasonal_window": (),
    "entry_conditioned": (("cond_symbol", "data/universe/<cond_symbol>_H1.parquet"),),
}


def information_class(family: str, params: dict[str, Any] | None = None) -> str | None:
    """`exogenous` / `conditioned` / `price_only` for a specialist family, None for any other.
    `entry_conditioned` with no `cond_symbol` filters on its own bars' hour, weekday or regime,
    so that cell alone is `price_only`."""
    fam = str(family or "")
    if fam == "entry_conditioned" and params is not None and not params.get("cond_symbol"):
        return "price_only"
    return INFORMATION_CLASS.get(fam)


#: What each family reads, for `families_orthogonal.FAMILY_INPUTS`.
INPUTS: dict[str, tuple[str, str]] = {
    "carry_risk_off": ("EXOGENOUS: the venue's recorded swap terms (data/tape/contract_terms, as "
                       "`carry`) and CONDITIONED on the RISK PROXY named by `risk_symbol`, read "
                       "as of each decision bar from the bar store -- not price-only",
                       "data/universe/<risk_symbol>_H1.parquet"),
    "month_end_rebalance": ("CONDITIONED on the bond proxy named by `bond_symbol`, read as of "
                            "each decision bar from the bar store -- not price-only",
                            "data/universe/<bond_symbol>_H1.parquet"),
    "seasonal_window": ("price only + the window and side the cell declares",
                        "data/universe/*_H1.parquet"),
    "entry_conditioned": ("the base cell's own inputs, plus `cond_symbol` from the bar store when "
                          "a cross-asset condition is named",
                          "data/universe/<cond_symbol>_H1.parquet"),
}

#: Charts each daily-decision family can express, for `families_orthogonal.FAMILY_TIMEFRAMES`.
TIMEFRAMES: dict[str, tuple[tuple[str, ...], str]] = {
    **dict.fromkeys(("carry_risk_off", "month_end_rebalance"),
                    (("H1",), "decides once a day at a broker decision HOUR and reads its "
                              "foreign series from the H1 store; on a four-hour or daily chart "
                              "the decision hour does not exist, and below the hour the foreign "
                              "series would be joined to a finer clock than it carries")),
    "seasonal_window": (("H1",), "decides once a day at a broker decision HOUR; on a four-hour or "
                                 "daily chart the decision hour does not exist"),
}
