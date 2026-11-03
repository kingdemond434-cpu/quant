"""CLUSTER-REACH FAMILIES: the two declared alpha clusters no registered family could reach.

WHY THIS FILE EXISTS (row 72, 2026-11-03). `libs/research/alpha_clusters` declares fifteen
clusters and `BREADTH_MANDATE.json` had carried three of them as NEVER_ATTEMPTED since the
mandate was written: `execution_entry`, `news_reaction` and `options_implied`. The forcer
(`research/empty_cluster_forcer.py`) could not mint for any of them, because no registered family
classified into them -- it named the missing artifact and stopped. `news_reaction` is reached by
classifying `jump` (a Lee-Mykland discontinuity with no calendar, whose own docstring says it
"catches the unscheduled shock the event family cannot see"), which needs no new code. The other
two needed a family, and these are those families. Both keys (`entry_alpha`, `implied_vol`) were
already declared in `alpha_clusters.FAMILY_CLUSTER`, waiting for an implementation.

  entry_alpha   EXECUTION AND ENTRY ALPHA. An OPERATOR over a market-entry base family: the base's
      own directional signal, entered on a resting LIMIT `offset_atr` x ATR better than the
      signal bar's reference price and alive `wait_bars` bars; an unfilled limit is no trade.
      Stop and target move by the same offset, so the R geometry is the base's own and the ONLY
      thing that differs from the base cell is the entry mechanics -- which is the cluster's
      definition ("the pullback that would have been filled"). The un-operated base is already in
      the docket, so the control arm (enter at market) exists and the gauntlet compares the two.
      PRICE ONLY.

  implied_vol   OPTIONS-IMPLIED STATE. Fusion quotes no options, but the cluster's payer -- the
      variance risk premium, implied against realised -- is observable for free: CBOE's VIX
      close is on FRED (`VIXCLS`), and LIVE already collects it (`data/fred_macro.json`, the
      `fred_macro` source in `data/data_registry.json`; `data/lake/fred_VIXCLS.parquet` on the box).
      The family computes the traded index's own realised volatility from its bars, the spread
      implied - realised in vol points, z-scores it against its own trailing history, and takes
      `harvest` (long when the premium is rich: the insurance seller is paid) or `stress` (short
      when realised runs above implied: dealers short gamma hedge into the move). EXOGENOUS: it
      reads a dataset that is not a bar series, declared as such so `gauntlet_buildability`
      names the series rather than calling the family price-only. GVZCLS / OVXCLS / VXNCLS are
      accepted by name when the store holds them; a series the store does not hold returns [],
      never a price-only fallback (UNMEASURED, not a verdict).

NO LOOKAHEAD. The implied print for trading date d is a CLOSE published after the US close; it
is lagged `lag_days` (default 2) whole days before it may condition a bar, because the bar index is
broker time under a UTC tzinfo (+2/+3) and a one-day lag lands ~an hour before the print exists.
Realised volatility uses only closes up to and including d, then takes the same lag.
"""
from __future__ import annotations

import inspect
import json
import math
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from mt5desk.families import Signal, _atr, _h1, bars_per_day

DESK = Path(__file__).resolve().parents[1]
REPO = DESK.parents[1]
#: Where LIVE's FRED collector keeps the dated series (`orthogonal_sweep._macro_series` reads it).
FRED_MACRO = REPO / "data" / "fred_macro.json"
#: The lake copy written by `research/fetch_fred.py`.
LAKE = DESK / "data" / "lake"

#: Whole days between an implied print dated d and the first bar it may condition (see the module
#: docstring: the bar clock is broker time, so one day lands before the print exists).
IMPLIED_PUBLICATION_LAG_D = 2

#: Implied-vol series the family accepts, and the MT5 underlyings each one prices. Only VIXCLS is
#: in LIVE's registered FRED pull today; the others are read when the store holds them.
IMPLIED_UNDERLYINGS: dict[str, tuple[str, ...]] = {
    "VIXCLS": ("US500", "US30", "NAS100"),
    "VXNCLS": ("NAS100",),
    "GVZCLS": ("XAUUSD",),
    "OVXCLS": ("XTIUSD",),
}

#: Base families the entry operator is minted over: market-entry, price-only, buildable on
#: defaults. A base whose signal already rests a stop trigger (a breakout) is still accepted --
#: the limit then sits `offset_atr` behind the trigger, i.e. the retest.
ENTRY_BASES: tuple[str, ...] = ("trend_ma_cross", "mean_reversion_rsi", "volatility_squeeze",
                                "pullback_entry", "overnight_drift")


# ------------------------------------------------------------------------------ entry alpha ---
def _base_signals(d: pd.DataFrame, base_family: str, base_params: dict[str, Any] | None,
                  symbol: str) -> list[Signal]:
    """The base family's own signals, called the way `entry_conditioned` calls it."""
    from mt5desk.families import get_family_func
    from mt5desk.families_specialist import wrappable
    if not base_family or base_family in ("entry_alpha", "implied_vol") \
            or not wrappable(base_family):
        return []
    fn = get_family_func(base_family)
    if fn is None:
        return []
    params = dict(base_params or {})
    for k in ("timeframe", "session"):
        params.pop(k, None)
    try:
        takes_symbol = "symbol" in inspect.signature(fn).parameters
    except (TypeError, ValueError):
        takes_symbol = False
    if takes_symbol and symbol and not params.get("symbol"):
        params["symbol"] = symbol
    try:
        raw = fn(d, **params) if "side" in params else fn(d, side=1, **params)
    except TypeError:
        try:
            raw = fn(d, **params)
        except Exception:
            return []
    except Exception:
        return []
    return [s for s in (raw or []) if isinstance(s, Signal)]


def family_entry_alpha(
    df: pd.DataFrame,
    *,
    base_family: str = "trend_ma_cross",
    base_params: dict[str, Any] | None = None,
    symbol: str = "",
    offset_atr: float = 0.5,
    wait_bars: int = 4,
    atr_n: int = 20,
) -> list[Signal]:
    """`base_family`'s signals re-entered on a resting LIMIT `offset_atr` ATR better than the
    signal bar's reference (its trigger if it rests one, else its close), alive `wait_bars`
    bars. Stop and target shift by the same distance, so only the ENTRY differs from the base."""
    try:
        off = float(offset_atr)
        wait = int(wait_bars)
    except (TypeError, ValueError):
        return []
    if not (math.isfinite(off) and off > 0) or wait < 1 or df is None or len(df) == 0:
        return []
    d = _h1(df)
    sigs = _base_signals(d, str(base_family or ""), base_params, symbol)
    if not sigs:
        return []
    atr = _atr(d, int(atr_n)).to_numpy(dtype="float64", na_value=np.nan)
    close = d["close"].to_numpy(dtype="float64", na_value=np.nan)
    times = pd.DatetimeIndex([pd.Timestamp(s.time) for s in sigs])
    if times.tz is None and d.index.tz is not None:
        times = times.tz_localize(d.index.tz)
    at = d.index.get_indexer(times)
    out: list[Signal] = []
    for s, p in zip(sigs, at, strict=True):
        if p < 0 or s.side not in (-1, 1):
            continue
        a = float(atr[p])
        ref = float(s.trigger) if s.trigger is not None else float(close[p])
        if not (math.isfinite(a) and a > 0 and math.isfinite(ref) and ref > 0):
            continue
        shift = off * a
        limit = ref - s.side * shift
        if not limit > 0:
            continue
        out.append(Signal(time=s.time, side=s.side, stop=float(s.stop) - s.side * shift,
                          target=float(s.target) - s.side * shift, ttl_bars=int(s.ttl_bars),
                          tag=f"entry_alpha:{base_family}:limit{off:g}atr/{wait}",
                          trigger=float(limit), wait_bars=wait))
    return out


# ------------------------------------------------------------------------------ implied vol ---
def _from_fred_macro(name: str, path: Path) -> pd.Series | None:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    rows = ((doc or {}).get("series") or {}).get(name) if isinstance(doc, dict) else None
    if not isinstance(rows, list) or not rows:
        return None
    try:
        stamps = pd.to_datetime([r[0] for r in rows], utc=True, errors="coerce")
        values = pd.to_numeric(pd.Series([r[1] for r in rows]), errors="coerce").to_numpy()
    except (TypeError, IndexError, KeyError, ValueError):
        return None
    return pd.Series(values, index=stamps)


def _from_lake(name: str, lake: Path) -> pd.Series | None:
    p = lake / f"fred_{name}.parquet"
    if not p.exists():
        return None
    try:
        df = pd.read_parquet(p)
    except Exception:
        return None
    if df.empty:
        return None
    col = name if name in df.columns else ("value" if "value" in df.columns else None)
    if col is None:
        num = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
        if not num:
            return None
        col = num[0]
    idx: Any = df.index
    for c in ("date", "DATE", "observation_date", "event_time"):
        if c in df.columns:
            idx = df[c]
            break
    stamps = pd.to_datetime(idx, utc=True, errors="coerce")
    return pd.Series(pd.to_numeric(df[col], errors="coerce").to_numpy(), index=stamps)


def implied_series(name: str, *, fred_macro: Path | None = None,
                   lake: Path | None = None) -> pd.Series | None:
    """The named implied-vol index as a dated daily series, or None when the store lacks it."""
    nm = str(name or "").upper()
    if nm not in IMPLIED_UNDERLYINGS:
        return None
    for s in (_from_fred_macro(nm, fred_macro or FRED_MACRO), _from_lake(nm, lake or LAKE)):
        if s is None:
            continue
        s = s[s.index.notna()].dropna()
        s = s[s > 0]
        if len(s) >= 30:
            s = s.sort_index()
            return s[~s.index.duplicated(keep="last")]
    return None


def source_state(name: str = "VIXCLS") -> tuple[bool, str]:
    """(readable, why) for an implied series on THIS host -- what the forcer reports."""
    s = implied_series(name)
    if s is None:
        return False, (f"{name} is not readable on this host: neither {FRED_MACRO} (series "
                       f"'{name}') nor {LAKE / f'fred_{name}.parquet'} holds 30 positive prints")
    return True, f"{name}: {len(s)} prints to {s.index.max().date()}"


def family_implied_vol(
    df: pd.DataFrame,
    *,
    vol_series: str = "VIXCLS",
    mode: str = "harvest",
    rv_days: int = 21,
    z_window: int = 252,
    z_entry: float = 1.0,
    hold_d: int = 5,
    lag_days: int = IMPLIED_PUBLICATION_LAG_D,
    side_bias: int = 1,
    atr_n: int = 20,
    stop_atr: float = 2.0,
    rr: float = 1.5,
) -> list[Signal]:
    """Trade the variance risk premium (implied - realised, vol points) of the underlying.

    `harvest`: z >= z_entry -> `side_bias` (long an index: the insurance seller is paid).
    `stress`:  z <= -z_entry -> -`side_bias` (realised above implied: hedging accelerates).
    One decision a day at the first bar the lagged print may condition; no new signal while the
    previous one's hold is running. Returns [] whenever the implied series is unreadable."""
    if mode not in ("harvest", "stress") or int(side_bias) not in (-1, 1):
        return []
    if int(rv_days) < 5 or int(z_window) < 20 or int(hold_d) < 1 or int(lag_days) < 1:
        return []
    implied = implied_series(vol_series)
    if implied is None or df is None or len(df) == 0:
        return []
    d = _h1(df)
    close = d["close"].astype(float)
    day = close.groupby(d.index.normalize()).last()
    rets = np.log(day).diff()
    realised = (rets.rolling(int(rv_days), min_periods=int(rv_days)).std(ddof=0)
                * math.sqrt(252) * 100)
    imp = implied.copy()
    imp.index = imp.index.normalize()
    if realised.index.tz is None:
        realised.index = realised.index.tz_localize("UTC")
    if imp.index.tz is None:
        imp.index = imp.index.tz_localize("UTC")
    joined = pd.concat({"iv": imp, "rv": realised}, axis=1).dropna()
    if len(joined) < int(z_window) // 2:
        return []
    vrp = joined["iv"] - joined["rv"]
    mu = vrp.rolling(int(z_window), min_periods=int(z_window) // 2).mean()
    sd = vrp.rolling(int(z_window), min_periods=int(z_window) // 2).std(ddof=0)
    z = ((vrp - mu) / sd.replace(0.0, np.nan)).dropna()
    if z.empty:
        return []
    # THE LAG: a print dated d may condition bars from d + lag_days on the broker clock.
    z.index = z.index + pd.Timedelta(days=int(lag_days))
    idx = d.index if d.index.tz is not None else d.index.tz_localize("UTC")
    on_bar = z.reindex(z.index.union(idx)).ffill().reindex(idx)
    z_day = pd.Series(on_bar.to_numpy(), index=idx).groupby(idx.normalize()).first()
    first_bar = pd.Series(np.arange(len(idx)), index=idx).groupby(idx.normalize()).first()
    atr = _atr(d, int(atr_n)).to_numpy(dtype="float64", na_value=np.nan)
    ttl = int(hold_d) * bars_per_day(d)
    thr = float(z_entry)
    out: list[Signal] = []
    next_ok = -1
    for dt, p in first_bar.items():
        zv = z_day.get(dt)
        if zv is None or not np.isfinite(zv) or int(p) < int(atr_n) or int(p) >= len(d) - 1:
            continue
        if int(p) < next_ok:
            continue
        side = 0
        if mode == "harvest" and zv >= thr:
            side = int(side_bias)
        elif mode == "stress" and zv <= -thr:
            side = -int(side_bias)
        if side == 0:
            continue
        a = float(atr[int(p)])
        px = float(close.iat[int(p)])
        if not (math.isfinite(a) and a > 0 and math.isfinite(px) and px > 0):
            continue
        dist = float(stop_atr) * a
        out.append(Signal(time=d.index[int(p)], side=side, stop=px - side * dist,
                          target=px + side * dist * float(rr), ttl_bars=ttl,
                          tag=f"implied_vol:{vol_series}:{mode}:z{thr:g}", trigger=None,
                          wait_bars=1))
        next_ok = int(p) + ttl
    return out


CLUSTER_REACH_FAMILIES: dict[str, Callable[..., list[Signal]]] = {
    "entry_alpha": family_entry_alpha,
    "implied_vol": family_implied_vol,
}
INFORMATION_CLASS: dict[str, str] = {"entry_alpha": "price_only", "implied_vol": "exogenous"}
FOREIGN_SERIES: dict[str, tuple[tuple[str | None, str], ...]] = {
    "entry_alpha": (),
    "implied_vol": (("vol_series", "data/fred_macro.json series <vol_series> (FRED, e.g. "
                                   "VIXCLS) or desks/mt5/data/lake/fred_<vol_series>.parquet"),),
}
INPUTS: dict[str, tuple[str, str]] = {
    "entry_alpha": ("the base cell's own bars: price only, the base family's signal re-entered "
                    "on a resting limit", "data/universe/*_H1.parquet"),
    "implied_vol": ("EXOGENOUS: a free CBOE implied-vol index close from FRED (VIXCLS by "
                    "default), against the instrument's own realised volatility",
                    "data/fred_macro.json"),
}
TIMEFRAMES: dict[str, tuple[tuple[str, ...], str]] = {
    "implied_vol": (("H1",), "decides once a day on a daily implied print; on a four-hour or "
                             "daily chart the first-bar-of-day decision moves, and below the "
                             "hour the daily print is joined to a finer clock than it carries"),
}
