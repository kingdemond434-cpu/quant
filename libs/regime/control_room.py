"""THE LIVE CONTROL ROOM -- each instrument's regime on three transparent axes, as a sizing input.

WHAT IT REVERSE-ENGINEERS. The winner of a 19,000-entrant Korean quant competition described his
core as three axes: regime detection (volatility and liquidity diagnose trend vs range, and the
diagnosis re-weights the strategies), factor selection, and Kelly-based geometric allocation. The
operators who run seven strategies rather than seven hundred say the same thing in fewer words:
"the most important thing is to pay attention to the market regime". Both describe a regime
reading that DRIVES ALLOCATION IN PRODUCTION, not a research output.

WHAT THE DESK ALREADY HAD, AND THE GAP. `pf_allocator.regime_state` fits ONE hidden Markov
model on gold's daily closes and lets that condition every sleeve's worlds (its own docstring
calls the per-asset version "the next piece of work"). `libs.portfolio.macro_state` tilts each
sleeve's posterior by how much each past day's dollar/risk/rates state resembled today's. Neither
asks the question the Korean axes ask of the instrument a sleeve actually trades: is EURUSD
trending or ranging right now, is its volatility high or low, is it liquid? `asset_state` fits an
HMM per instrument but is cached, windowed and published, never fed to a size.

THIS MODULE IS THAT READING, KEPT DELIBERATELY SMALL AND CAUSAL:

    vol     realised 20-day volatility, ranked against the instrument's own trailing year:
            low / mid / high at the terciles
    trend   Kaufman efficiency ratio over 20 days (net move / path length), ranked the same
            way: trend at or above the median of its own year, range below it
    liq     the day's mean quoted spread against its trailing 60-day median, and tick activity
            against its own year: thin when the spread is 1.25x normal or activity is in its
            bottom fifth, normal otherwise

Every label on day t uses bars up to and including t. A sleeve's return on day t is conditioned on
the label of day t-1, the last reading a desk could have acted on before that day's trading.

HOW IT DRIVES ALLOCATION. `sleeve_weights` returns, per day of a sleeve's history, how much that
day's state on the sleeve's OWN instrument resembled the state now: the product over the three
axes of 1.0 on a match and `EPS` on a mismatch. That is exactly the shape of the `macro_w`
channel `robust_elog._posterior_mu` already reads -- a regime-weighted mean formed as a CONTRAST
against the plain mean, shrunk at k=60 effective days, bounded by the posterior's own magnitude
-- so the allocator can consume it with no new arithmetic: a trend sleeve on an instrument that
has stopped trending is tilted down, a range sleeve on the same instrument tilted up, and the
total heat is untouched. SOFT, NEVER BINARY (the principal: "don't make the regime classifier
binary"): a mismatched day still carries weight EPS, so no state is ever certain.

WHETHER IT IS ALLOWED TO. Admission rule: a subsystem ships only with a measured contract showing
gain. `desks/mt5/research/regime_allocation_contract.py` is that contract -- walk-forward, on
the desk's own bars, the live solver with and without this kernel -- and the allocator patch that
consumes it reads the contract's verdict and does nothing unless it says GAIN.

FAILS CLOSED. No bars, fewer than MIN_DAYS days, or a symbol this desk has no file for returns an
EMPTY weight vector, which the posterior reads as "no claim" -- never uniform weights pretending
to be a reading.
"""
from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
#: Where the desk's H1 bars live, most complete first. The box's `data/universe` carries every
#: symbol it records; the checked-in `universe` folder is the research snapshot.
BAR_DIRS: tuple[Path, ...] = (ROOT / "desks" / "mt5" / "data" / "universe",
                              ROOT / "desks" / "mt5" / "universe")

AXES: tuple[str, ...] = ("vol", "trend", "liq")
VOL_WIN = 20
ER_WIN = 20
RANK_WIN = 252
LIQ_WIN = 60
THIN_SPREAD_MULT = 1.25
QUIET_PCT = 0.20
#: Weight of a day whose state MISMATCHES today's on one axis. 0.35 means a day that differs on
#: every axis still carries 4% of a perfect match's weight: nothing is ever excluded outright.
EPS = 0.35
#: Days of labelled history before the reading says anything. One trailing rank year plus the
#: longest feature window, rounded up.
MIN_DAYS = RANK_WIN + 30

_CACHE: dict[str, tuple[float, pd.DataFrame]] = {}


def bar_path(symbol: str, dirs: Sequence[Path] = BAR_DIRS) -> Path | None:
    for d in dirs:
        p = d / f"{symbol}_H1.parquet"
        if p.exists():
            return p
    return None


def daily_frame(h1: pd.DataFrame) -> pd.DataFrame:
    """H1 bars -> one weekday row per UTC day: close, spread (mean), activity (tick sum)."""
    df = h1.copy()
    if not isinstance(df.index, pd.DatetimeIndex):
        tcol = next((c for c in ("time", "Time", "datetime") if c in df.columns), None)
        if tcol is None:
            raise KeyError("bars carry no time index or column")
        df.index = pd.to_datetime(df[tcol], utc=True)
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    # A ZERO SPREAD IS AN UNRECORDED ONE, NOT A FREE MARKET: the box's feed writes 0 on hours it
    # did not stamp (measured on EURUSD 2026-09-15/16, every hour but one), and a median of zeros
    # would call every later day "thin" at an infinite multiple.
    if "spread" in df.columns:
        df["spread"] = df["spread"].where(df["spread"] > 0)
    agg: dict[str, Any] = {"close": "last", "n_bars": "count"}
    df["n_bars"] = 1
    if "spread" in df.columns:
        agg["spread"] = "mean"
    if "tick_volume" in df.columns:
        # Activity PER BAR, so a day the feed stamped fewer hours is not read as a quiet one.
        agg["tick_volume"] = "mean"
    out = df.resample("1D").agg(agg).dropna(subset=["close"])
    out = out[out.index.dayofweek < 5]
    # THE LAST DAY IS USUALLY STILL OPEN. A half-day's close is not that day's close and half a
    # day's range is not its volatility, so an incomplete final day is dropped; complete days are
    # the ones with at least 20 of their hours stamped.
    if len(out) and int(out["n_bars"].iloc[-1]) < 20:
        out = out.iloc[:-1]
    out = out.drop(columns=["n_bars"])
    out.index = out.index.strftime("%Y-%m-%d")
    return out


def trailing_pct(x: np.ndarray, win: int) -> np.ndarray:
    """Rank of x[t] within x[t-win+1 .. t], in [0, 1]. Causal; NaN until `win // 2` values."""
    out = np.full(x.shape, np.nan)
    for t in range(x.size):
        if not math.isfinite(x[t]):
            continue
        seg = x[max(0, t - win + 1): t + 1]
        seg = seg[np.isfinite(seg)]
        if seg.size < max(20, win // 2):
            continue
        out[t] = float((seg < x[t]).sum() + 0.5 * ((seg == x[t]).sum() - 1)) / max(seg.size - 1, 1)
    return out


def label_days(daily: pd.DataFrame) -> pd.DataFrame:
    """Per-day labels on the three axes plus the raw readings behind them. Causal row by row."""
    close = daily["close"].to_numpy(float)
    lr = np.r_[np.nan, np.diff(np.log(close))]
    rv = pd.Series(lr).rolling(VOL_WIN).std().to_numpy()
    net = np.abs(pd.Series(np.log(close)).diff(ER_WIN).to_numpy())
    path = pd.Series(np.abs(lr)).rolling(ER_WIN).sum().to_numpy()
    er = np.where(path > 0, net / np.where(path > 0, path, 1.0), np.nan)
    vol_pct = trailing_pct(rv, RANK_WIN)
    er_pct = trailing_pct(er, RANK_WIN)
    vol = np.where(np.isnan(vol_pct), "",
                   np.where(vol_pct < 1 / 3, "low", np.where(vol_pct > 2 / 3, "high", "mid")))
    trend = np.where(np.isnan(er_pct), "", np.where(er_pct >= 0.5, "trend", "range"))
    liq = np.full(close.size, "normal", dtype=object)
    spread_mult = np.full(close.size, np.nan)
    act_pct = np.full(close.size, np.nan)
    if "spread" in daily.columns:
        sp = daily["spread"].to_numpy(float)
        med = pd.Series(sp).rolling(LIQ_WIN, min_periods=LIQ_WIN // 2).median().to_numpy()
        spread_mult = np.where(med > 0, sp / np.where(med > 0, med, 1.0), np.nan)
    if "tick_volume" in daily.columns:
        act_pct = trailing_pct(daily["tick_volume"].to_numpy(float), RANK_WIN)
    thin = (np.nan_to_num(spread_mult, nan=0.0) >= THIN_SPREAD_MULT) | (
        np.nan_to_num(act_pct, nan=1.0) < QUIET_PCT)
    liq[thin] = "thin"
    liq[np.isnan(vol_pct)] = ""
    return pd.DataFrame({"vol": vol, "trend": trend, "liq": liq.astype(str),
                         "rv20": rv, "er20": er, "vol_pct": vol_pct, "er_pct": er_pct,
                         "spread_mult": spread_mult, "activity_pct": act_pct},
                        index=daily.index)


def labels_for(symbol: str, dirs: Sequence[Path] = BAR_DIRS) -> pd.DataFrame | None:
    """Labels for one symbol from its H1 file, cached by the file's mtime. None when absent."""
    p = bar_path(symbol, dirs)
    if p is None:
        return None
    key = str(p)
    mt = p.stat().st_mtime
    hit = _CACHE.get(key)
    if hit is not None and hit[0] == mt:
        return hit[1]
    h1 = pd.read_parquet(p)
    lab = label_days(daily_frame(h1))
    _CACHE[key] = (mt, lab)
    return lab


def state_key(row: pd.Series | dict[str, Any]) -> str:
    vals = [str(row[a]) for a in AXES]
    return "|".join(vals) if all(vals) else ""


def kernel(hist: pd.DataFrame, now: pd.Series | dict[str, Any], eps: float = EPS) -> np.ndarray:
    """Weight per row of `hist`: product over axes of 1 on a match and `eps` on a mismatch.

    NaN where the row carries no label -- that day leaves both sides of the contrast.
    """
    w = np.ones(len(hist), dtype=float)
    missing = np.zeros(len(hist), dtype=bool)
    for a in AXES:
        col = hist[a].to_numpy(dtype=object)
        missing |= (col == "") | pd.isna(col)
        w *= np.where(col == now[a], 1.0, eps)
    w[missing] = np.nan
    return w


def sleeve_weights(symbol: str, dates: Iterable[Any], *, eps: float = EPS,
                   asof: str | None = None, labels: pd.DataFrame | None = None,
                   ) -> tuple[np.ndarray, dict[str, Any]]:
    """The `macro_w`-shaped weight vector for a sleeve trading `symbol`, on the sleeve's dates.

    A return on day d is weighted by the state of the last labelled day STRICTLY BEFORE d; `now`
    is the last labelled day at or before `asof` (default: the newest bar). Returns an EMPTY
    array, never uniform weights, when the reading cannot be made.
    """
    days = [str(d)[:10] for d in dates]
    lab = labels if labels is not None else labels_for(symbol)
    if lab is None:
        return np.array([], dtype=float), {"status": "UNMEASURED", "why": f"no bars for {symbol}"}
    lab = lab[lab["vol"] != ""]
    if asof is not None:
        lab = lab[lab.index <= asof]
    if len(lab) < MIN_DAYS - RANK_WIN // 2:
        return np.array([], dtype=float), {"status": "UNMEASURED",
                                           "why": f"{len(lab)} labelled days for {symbol}"}
    now = lab.iloc[-1]
    idx = lab.index.to_numpy(dtype=str)
    pos = np.searchsorted(idx, np.asarray(days, dtype=str), side="left") - 1
    prior = pd.DataFrame({a: np.where(pos >= 0, lab[a].to_numpy(dtype=object)[np.maximum(pos, 0)],
                                      "") for a in AXES})
    w = kernel(prior, now, eps)
    known = w[np.isfinite(w)]
    sw = float(known.sum()) if known.size else 0.0
    return w, {"status": "MEASURED", "symbol": symbol, "asof": str(lab.index[-1]),
               "now": {a: str(now[a]) for a in AXES}, "state": state_key(now),
               "n_weighted": int(known.size),
               "n_eff": round(sw * sw / float((known * known).sum()), 2) if sw > 0 else 0.0}


@dataclass(frozen=True)
class AssetReading:
    symbol: str
    state: str
    asof: str
    vol: str
    trend: str
    liq: str
    vol_pct: float | None
    er_pct: float | None
    spread_mult: float | None

    def to_dict(self) -> dict[str, Any]:
        def r(x: float | None) -> float | None:
            return None if x is None or not math.isfinite(x) else round(float(x), 4)
        return {"symbol": self.symbol, "state": self.state, "asof": self.asof, "vol": self.vol,
                "trend": self.trend, "liq": self.liq, "vol_pct": r(self.vol_pct),
                "er_pct": r(self.er_pct), "spread_mult": r(self.spread_mult)}


def reading(symbol: str, labels: pd.DataFrame | None = None) -> AssetReading | None:
    lab = labels if labels is not None else labels_for(symbol)
    if lab is None:
        return None
    lab = lab[lab["vol"] != ""]
    if lab.empty:
        return None
    row = lab.iloc[-1]
    return AssetReading(symbol, state_key(row), str(lab.index[-1]), str(row["vol"]),
                        str(row["trend"]), str(row["liq"]), float(row["vol_pct"]),
                        float(row["er_pct"]), float(row["spread_mult"]))


def snapshot(symbols: Sequence[str]) -> dict[str, Any]:
    """The book-level reading: every instrument's state now and how the tape splits."""
    rows = {s: reading(s) for s in symbols}
    ok = {s: r for s, r in rows.items() if r is not None}
    n = len(ok) or 1
    return {
        "assets": {s: r.to_dict() for s, r in sorted(ok.items())},
        "unmeasured": sorted(s for s, r in rows.items() if r is None),
        "share_trending": round(sum(r.trend == "trend" for r in ok.values()) / n, 4),
        "share_high_vol": round(sum(r.vol == "high" for r in ok.values()) / n, 4),
        "share_thin": round(sum(r.liq == "thin" for r in ok.values()) / n, 4),
    }
