"""F1 -- THE IDIOSYNCRATIC TICK-VOLUME SPIKE, faded over the next one to four hours.

THE MECHANISM (GAP_MAP row 42, "large-trade footprint detection": flow-pressure inference from
public volume, never targeting a named participant and never front-running). Tick volume on a
retail CFD feed is a count of quote updates, and most of an instrument's hour-to-hour variation in
it is COMMON: the London open, a US data print and a risk-off afternoon raise every symbol's count
together. What is left after the common part and the hour-of-week rhythm is removed is activity
peculiar to ONE instrument -- a large order working through it, a stop cascade, a fixing hedge.
That burst moves price by inventory pressure, not information, and the liquidity provider who
absorbed it (`axis_registry`: inventory_shock, payer `inventory_laden_dealer`) lays the inventory
off over the following hours: the move retraces. The family fades the spike bar's direction.

THE MEASUREMENT, ALL OF IT TRAILING (nothing here sees a future bar):

  1. y_t = log(1 + tick_volume) of the instrument, demeaned by its own trailing mean;
     F_t = the cross-sectional mean of the same quantity over the peer set (`volume_peers`,
     loaded on the cell's own chart through `family_inputs.bars_named`, the gauntlet's reader).
  2. e_t = y_t - beta_{t-1} * F_t, with beta a trailing rolling regression of y on F
     (`beta_window` bars), lagged one bar so the bar being scored never fits its own beta.
  3. z_t = (e_t - mu) / sd, where mu and sd are the residual's mean and spread over the PRIOR
     occurrences of the same hour of the week (Mon 00:00 ... Sun 23:00). The London open is
     compared with past London opens, never with the Asian lull.
  4. A bar with z_t > `z_threshold` is a spike. The signal fades its bar's direction (close vs
     open), enters at the next bar's open, and holds `hold_bars` bars (1-4h on H1).

THE COST OF THE HOUR IT FILLS IN. A spike at the daily rollover fills into the widest spread of
the day (USDZAR: ~2,000 points at broker hour 01 against a 310-point pooled median, measured by
`research/cost_surface.py`). The sealed gauntlet charges a cell the spread of its MODAL fill hour;
a family that fills at many hours would hide its rollover fills behind a cheap modal hour. So the
family reads the same per-symbol / per-hour surface (`data/cost_surface.json`, p50 at the fill
hour) and refuses an entry whose fill-hour spread exceeds `max_spread_atr` of the bar's ATR: the
rollover spike that could never pay is not taken, rather than taken and averaged away. A symbol or
hour the surface does not measure refuses nothing (`symbol` unset reads no surface at all).

WHICH SPREAD, AND WHEN (audit SHOULD-FIX, 2026-10-14). The point-in-time source is the fill bar's
OWN recorded spread: MT5 bars carry a `spread` column (points) written when the bar closed, so a
2019 fill is judged by a 2019 spread. It is used whenever it is recorded (> 0). The surface is
TODAY's per-hour p50 and is used only where the bar recorded none (0 or absent) -- a fallback that
applies today's costs to history, disclosed in the F1 preregistration. Caveat on the PIT source
too: MT5's bar spread is commonly the bar's MINIMUM, so it can understate the fill's spread.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from mt5desk.families import Signal, _atr, _h1

#: The cross-sectional factor's members: the most liquid FX, metals and index CFDs, the set whose
#: common activity rhythm a single instrument's burst is measured against. A peer with no bars on
#: the cell's chart is skipped; fewer than `MIN_PEERS` loaded and the family refuses.
DEFAULT_PEERS: tuple[str, ...] = ("EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF",
                                  "NZDUSD", "EURJPY", "XAUUSD", "XAGUSD", "US500", "NAS100",
                                  "GER40")
MIN_PEERS = 4
#: The F1 targets: majors, the two rand crosses (thin books, where an idiosyncratic burst is
#: largest relative to normal flow) and gold.
F1_SYMBOLS: tuple[str, ...] = ("EURUSD", "GBPUSD", "AUDUSD", "USDJPY", "EURZAR", "USDZAR",
                               "XAUUSD")
F1_HOLDS: tuple[int, ...] = (1, 2, 4)
#: Prior same-hour-of-week observations needed before an hour's z-score exists.
MIN_HOW_OBS = 8

COST_SURFACE = Path(__file__).resolve().parents[1] / "data" / "cost_surface.json"


def _log_volume(df: pd.DataFrame) -> pd.Series | None:
    col = "tick_volume" if "tick_volume" in df.columns else (
        "volume" if "volume" in df.columns else None)
    if col is None:
        return None
    v = pd.to_numeric(df[col], errors="coerce").astype(float)
    return np.log1p(v.clip(lower=0.0))


def idio_volume_z(target: pd.DataFrame, peers: list[pd.DataFrame], *, beta_window: int = 500,
                  demean_window: int = 500) -> pd.Series | None:
    """The hour-of-week-normalised residual of the target's log tick volume on the peer factor,
    on the target's own index; None when the target has no volume or too few peers align."""
    y_raw = _log_volume(target)
    if y_raw is None:
        return None
    idx = target.index
    cols: list[pd.Series] = []
    for p in peers:
        lv = _log_volume(p)
        if lv is None:
            continue
        lv = lv[~lv.index.duplicated(keep="last")].reindex(idx)
        if lv.notna().sum() < beta_window:
            continue
        cols.append(lv - lv.rolling(demean_window, min_periods=50).mean().shift(1))
    if len(cols) < MIN_PEERS:
        return None
    factor = pd.concat(cols, axis=1).mean(axis=1, skipna=True)
    y = y_raw - y_raw.rolling(demean_window, min_periods=50).mean().shift(1)
    cov = y.rolling(beta_window, min_periods=100).cov(factor)
    var = factor.rolling(beta_window, min_periods=100).var()
    beta = (cov / var.replace(0.0, np.nan)).shift(1)
    resid = y - beta * factor
    di = pd.DatetimeIndex(idx)
    how = pd.Series(di.dayofweek * 24 + di.hour, index=idx)
    grouped = resid.groupby(how)
    mu = grouped.transform(lambda s: s.shift(1).expanding(MIN_HOW_OBS).mean())
    sd = grouped.transform(lambda s: s.shift(1).expanding(MIN_HOW_OBS).std(ddof=0))
    z = (resid - mu) / sd.replace(0.0, np.nan)
    return z.replace([np.inf, -np.inf], np.nan)


@lru_cache(maxsize=1)
def _surface_doc(path: str) -> dict[str, Any]:
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def fill_hour_spread(symbol: str, hour: int, surface: dict[str, Any] | None = None
                     ) -> float | None:
    """The surface's p50 spread at `hour` in PRICE units, or None when it is not measured."""
    doc = surface if surface is not None else _surface_doc(str(COST_SURFACE))
    sym = ((doc or {}).get("symbols") or {}).get(symbol) or {}
    cell = (sym.get("hours") or {}).get(str(int(hour))) or {}
    if cell.get("status") != "MEASURED" or cell.get("p50") is None:
        return None
    tick = float(sym.get("tick_size") or 0.0)
    if tick <= 0:
        return None
    return float(cell["p50"]) * tick


def _tick_size(symbol: str, surface: dict[str, Any] | None) -> float | None:
    doc = surface if surface is not None else _surface_doc(str(COST_SURFACE))
    tick = float((((doc or {}).get("symbols") or {}).get(symbol) or {}).get("tick_size") or 0.0)
    return tick if tick > 0 else None


def fill_spread(symbol: str, hour: int, bar_spread_pts: float | None,
                surface: dict[str, Any] | None = None) -> tuple[float | None, str]:
    """The fill's spread in price units and its source: the bar's own recorded spread (PIT)
    when it is recorded, else today's surface p50 at that hour, else (None, 'unmeasured')."""
    if bar_spread_pts is not None and np.isfinite(bar_spread_pts) and bar_spread_pts > 0:
        tick = _tick_size(symbol, surface)
        if tick is not None:
            return float(bar_spread_pts) * tick, "bar_pit"
    spr = fill_hour_spread(symbol, hour, surface)
    return (spr, "surface_today") if spr is not None else (None, "unmeasured")


def _peers_for(df: pd.DataFrame, names: list[str] | tuple[str, ...], symbol: str
               ) -> list[pd.DataFrame]:
    from mt5desk.family_inputs import bars_named
    out: list[pd.DataFrame] = []
    for name in names:
        if name == symbol:
            continue
        b = bars_named(str(name), df)
        if b is not None and len(b):
            out.append(b)
    return out


def family_idio_volume_reversal(
    df: pd.DataFrame,
    *,
    symbol: str = "",
    volume_peers: list[str] | tuple[str, ...] = DEFAULT_PEERS,
    z_threshold: float = 3.0,
    hold_bars: int = 2,
    beta_window: int = 500,
    atr_n: int = 20,
    stop_atr: float = 1.5,
    rr: float = 1.0,
    max_spread_atr: float = 0.25,
    peers: list[pd.DataFrame] | None = None,
    surface: dict[str, Any] | None = None,
) -> list[Signal]:
    """Fade the bar on which the instrument's own tick volume spiked above `z_threshold`
    standard deviations of its hour-of-week residual, for `hold_bars` bars."""
    d = _h1(df)
    if d is None or d.empty or len(d) < beta_window + atr_n + 2:
        return []
    frames = peers if peers is not None else _peers_for(d, list(volume_peers), symbol)
    z = idio_volume_z(d, frames, beta_window=beta_window)
    if z is None:
        return []
    atr = _atr(d, atr_n).to_numpy()
    o = d["open"].astype(float).to_numpy()
    c = d["close"].astype(float).to_numpy()
    zv = z.to_numpy()
    bar_spread = (pd.to_numeric(d["spread"], errors="coerce").to_numpy(dtype=float)
                  if "spread" in d.columns else None)
    idx = pd.DatetimeIndex(d.index)
    thr = float(z_threshold)
    out: list[Signal] = []
    last = -10 ** 9
    for i in range(max(atr_n, 1), len(d) - 1):
        zi = zv[i]
        if not np.isfinite(zi) or zi <= thr or i - last < int(hold_bars):
            continue
        move = c[i] - o[i]
        a = float(atr[i])
        if move == 0 or not np.isfinite(a) or a <= 0:
            continue
        if symbol and max_spread_atr > 0:
            spr, _src = fill_spread(symbol, int(idx[i + 1].hour),
                                    None if bar_spread is None else float(bar_spread[i + 1]),
                                    surface)
            if spr is not None and spr > float(max_spread_atr) * a:
                continue                   # the fill hour's own spread eats the retrace
        side = -1 if move > 0 else 1
        px = float(c[i])
        out.append(Signal(time=idx[i], side=side, stop=px - side * stop_atr * a,
                          target=px + side * stop_atr * a * rr, ttl_bars=int(hold_bars),
                          tag="idio_volume_reversal", trigger=None, wait_bars=1))
        last = i
    return out


#: Carried on every F1 cell (see the preregistration).
F1_CAVEATS = (
    "COST: the spread cap reads the fill bar's own recorded MT5 spread (point-in-time) where "
    "the bar recorded one; where it did not, it falls back to TODAY's per-hour p50 from "
    "data/cost_surface.json, i.e. today's costs applied to history",
    "DIRECTION: fade is fixed by the mechanism; a measurement on the same history (EURUSD, h=2, "
    "p=0.0125) showed CONTINUATION before the preregistration was written; a continuation "
    "variant is a new, separately charged trial and is not minted here",
)


def f1_cells() -> list[dict[str, Any]]:
    """The F1 cells: every target x hold, at the declared threshold. One trial each."""
    cells: list[dict[str, Any]] = []
    for sym in F1_SYMBOLS:
        for hold in F1_HOLDS:
            params = {"symbol": sym, "z_threshold": 3.0, "hold_bars": hold, "timeframe": "H1"}
            cells.append({
                "symbol": sym, "symbols": [sym], "kind": "hypothesis",
                "family": "idio_volume_reversal", "params": params,
                "title": f"F1 idiosyncratic tick-volume spike on {sym}: fade {hold}h"[:120],
                "mechanism": ("a tick-volume burst peculiar to one instrument (after the "
                              "cross-sectional activity factor and the hour-of-week rhythm are "
                              "removed) is inventory pressure, not information; the dealer who "
                              "absorbed it lays it off and the move retraces"),
                "falsifier": (f"{sym} returns over the {hold} H1 bar(s) after a z>3 idiosyncratic "
                              "volume spike, signed against the spike bar, are no better than "
                              "zero net of the fill-hour spread"),
                "preregistration": "docs/research/F1_IDIO_VOLUME_PREREGISTRATION.md",
                "caveats": list(F1_CAVEATS),
                "lane": "F1"})
    return cells
