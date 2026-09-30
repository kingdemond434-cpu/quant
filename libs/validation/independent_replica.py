"""A SECOND IMPLEMENTATION, FROM THE FROZEN SPEC: signals, fills and P&L rebuilt without the first.

Item 15 of the principal's 2026-09-29 list: *"independent implementation verifier: second engine
reconstructs signals and P&L from the frozen spec without calling the original implementation;
compare trades/costs/returns within tolerance, for every promoted strategy."*

WHAT EXISTED. `libs/validation/replay2.py` (IMMUTABLE -- listed in
scripts/check_immutable_evaluator.py) is a second ENGINE written from `run_backtest`'s contract;
it replays signals the FIRST implementation generated, models no stop-entry trigger, and so a
breakout certificate replayed there disagrees for reasons that are about the replay.
`research/blind_reviewer.py` reproduces a certificate from its spec -- through the very same
`mt5desk.family_call` + `mt5desk.engine` path that minted it. Neither can catch a defect in the
family code, which is where a certificate's number is actually born.

THIS MODULE IMPORTS NOTHING FROM `mt5desk`, `research` OR `scripts` -- a test parses its AST and
fails on any such import. It is written from the families' DOCSTRINGS and the engine's CONTRACT
(both restated below), not from their bodies' control flow, and it deliberately shares no helper
with them: its own bar loader, its own ATR, its own session windows, its own fill model, its own
cost arithmetic. Two implementations that agree are evidence the number is the strategy's; two
that disagree are a defect report, and the disagreement names the trade.

FAMILIES COVERED (the certified population's price-only families; anything else is UNSUPPORTED,
which is a verdict and never a pass):

    overnight_gap_decay     on the first bar of each calendar day, when |open - previous close|
                            >= gap_atr x ATR(atr_n), fade the gap: stop stop_atr x ATR beyond the
                            open, target rr x |gap| back toward the prior close; entry at the next
                            open, ttl_bars to live.
    session_range_breakout  the day's range over hours [range_start, range_end) -- or every hour
                            before range_start when range_end is unset -- and at the signal hour a
                            resting BUY STOP at the range high and SELL STOP at the range low,
                            stop distance max(1.2 x ATR, range), target rr x that distance beyond
                            the trigger, alive wait_bars bars. Only the default filters
                            (trend/range/vol/midpoint off, no spread gate) are implemented; a
                            spec that turns one on is UNSUPPORTED.
    discovered              a price-native primitive (dd_n, ru_n, hour) inside its quantile band
                            -> enter at the next open, 2 ATR stop, 1.5R target, hold `horizon`.
                            External-residual features (ext_*) are UNSUPPORTED: they need the
                            cross-asset universe the searcher builds, which is not re-derivable
                            from the spec alone.

THE ENGINE CONTRACT (restated from `mt5desk.engine.run_backtest`'s docstring and Signal fields):
    * a signal at bar t is acted on from bar t+1: market entries fill at bar t+1's OPEN
    * a trigger (stop/limit entry) rests from bar t+1 for `wait_bars` bars and fills AT the trigger
      on the first bar whose [low, high] contains it; it is a LIMIT when it sits on the favourable
      side of bar t+1's open, and a limit fill bar may not also pay the target
    * stop and target are checked intrabar from the fill bar; if both are touched the STOP wins
    * after `ttl_bars` bars from the fill the position closes at the OPEN of bar fill+ttl
    * one position at a time: a signal whose entry bar is at or before the last exit is skipped;
      a trigger that never fills does not occupy the book
    * R = side x (exit - entry) / |entry - stop|, minus the round trip and the financing over the
      same unit. Round trip (price units) = max(spread_pts x tick_size x contract, 0.05)/contract
      + 2 x commission x tick_size / tick_value; financing per rollover = max(|swap_long|,
      |swap_short|) x tick_size, rollovers counted at 21:00 UTC, Wednesday's counting three.
"""
from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

#: Contract terms restated, so the two implementations share a DOCUMENT and not a variable.
COMMISSION_PER_LOT_SIDE = 2.00
MIN_SPREAD_PER_LOT = 0.05
ROLLOVER_HOUR_UTC = 21
TRIPLE_WEEKDAY = 2   # Wednesday

SUPPORTED_FAMILIES: tuple[str, ...] = ("overnight_gap_decay", "session_range_breakout",
                                       "discovered")
_SRB_DEFAULT_OFF = {"trend_filter": "none", "range_filter": "all", "vol_filter": "all",
                    "midpoint_filter": "off", "spread_gate": False}


@dataclass(frozen=True)
class Sig:
    time: pd.Timestamp
    side: int
    stop: float
    target: float
    ttl: int
    trigger: float | None = None
    wait: int = 1


@dataclass(frozen=True)
class Fill:
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    side: int
    entry: float
    exit: float
    stop: float
    gross_r: float
    cost_r: float
    r: float
    reason: str


# ------------------------------------------------------------------------------- bars
def load_bars(path: Path) -> pd.DataFrame | None:
    """OHLC on a tz-aware UTC, nanosecond, sorted, de-duplicated (last wins) index."""
    if not path.exists():
        return None
    df = pd.read_parquet(path)
    if "time" in df.columns and not isinstance(df.index, pd.DatetimeIndex):
        df = df.set_index("time")
    idx = pd.DatetimeIndex(df.index)
    idx = idx.tz_localize("UTC") if idx.tz is None else idx.tz_convert("UTC")
    df = df.copy()
    df.index = idx.as_unit("ns")
    df = df.sort_index()
    df = df[~df.index.duplicated(keep="last")]
    need = ["open", "high", "low", "close"]
    if any(c not in df.columns for c in need):
        return None
    return df[need].astype(float)


def true_range_mean(df: pd.DataFrame, n: int) -> np.ndarray:
    """Mean of the true range over the last n bars (fewer at the start); bar 0's TR is H-L."""
    h = df["high"].to_numpy(float)
    lo = df["low"].to_numpy(float)
    c = df["close"].to_numpy(float)
    prev = np.concatenate([[np.nan], c[:-1]])
    tr = np.fmax(h - lo, np.fmax(np.abs(h - prev), np.abs(lo - prev)))
    out = np.empty_like(tr)
    csum = np.nancumsum(np.where(np.isfinite(tr), tr, 0.0))
    cnt = np.cumsum(np.isfinite(tr).astype(float))
    for i in range(len(tr)):
        j = i - n
        s = csum[i] - (csum[j] if j >= 0 else 0.0)
        k = cnt[i] - (cnt[j] if j >= 0 else 0.0)
        out[i] = s / k if k > 0 else np.nan
    return np.asarray(out, dtype=float)


# ------------------------------------------------------------------------------- families
def overnight_gap_decay(df: pd.DataFrame, *, gap_atr: float = 0.75, atr_n: int = 20,
                        stop_atr: float = 1.5, rr: float = 1.0, ttl_bars: int = 8) -> list[Sig]:
    a = true_range_mean(df, atr_n)
    o = df["open"].to_numpy(float)
    c = df["close"].to_numpy(float)
    dates = df.index.date
    out: list[Sig] = []
    for i in range(atr_n, len(df) - 1):
        if dates[i] == dates[i - 1]:
            continue
        atr = a[i]
        if not (math.isfinite(atr) and atr > 0):
            continue
        gap = o[i] - c[i - 1]
        if abs(gap) < gap_atr * atr:
            continue
        side = 1 if gap < 0 else -1
        out.append(Sig(df.index[i], side, o[i] - side * stop_atr * atr,
                       o[i] + side * abs(gap) * rr, int(ttl_bars)))
    return out


def session_range_breakout(df: pd.DataFrame, *, range_start: int = 7,
                           range_end: int | None = None, signal_at: int | None = None,
                           wait_bars: int = 8, atr_n: int = 20, ttl_bars: int = 12,
                           rr: float = 2.0) -> list[Sig]:
    a = true_range_mean(df, atr_n)
    hours = df.index.hour
    dates = df.index.date
    h = df["high"].to_numpy(float)
    lo = df["low"].to_numpy(float)
    o = df["open"].to_numpy(float)
    in_range = (hours < range_start) if range_end is None else \
        ((hours >= range_start) & (hours < range_end))
    sig_hour = signal_at if signal_at is not None else \
        (range_start if range_end is None else range_end)
    day_hi: dict[Any, float] = {}
    day_lo: dict[Any, float] = {}
    for ii in np.flatnonzero(in_range):
        i = int(ii)
        d = dates[i]
        day_hi[d] = max(day_hi.get(d, -math.inf), h[i])
        day_lo[d] = min(day_lo.get(d, math.inf), lo[i])
    out: list[Sig] = []
    for i in range(1, len(df) - 2):
        if hours[i] != sig_hour or not math.isfinite(o[i]):
            continue
        atr = a[i]
        if not (atr > 0):
            continue
        d = dates[i]
        if d not in day_hi:
            continue
        hi, low = day_hi[d], day_lo[d]
        span = hi - low
        if span <= 0:
            continue
        dist = max(1.2 * atr, span)
        out.append(Sig(df.index[i], 1, hi - dist, hi + dist * rr, int(ttl_bars), hi,
                       int(wait_bars)))
        out.append(Sig(df.index[i], -1, low + dist, low - dist * rr, int(ttl_bars), low,
                       int(wait_bars)))
    return out


_PRICE_FEATURE = re.compile(r"^(dd|ru)_(\d+)$")


def price_feature(df: pd.DataFrame, name: str) -> np.ndarray | None:
    """The searcher's price-native primitives, restated from their definitions:
    dd_n = close / max(close over the last n bars) - 1; ru_n = close / min(...) - 1 (NaN until n
    bars exist); hour = the bar's stamp hour. Anything else (ext_*, residuals) is not replicated."""
    c = df["close"].to_numpy(float)
    if name == "hour":
        return np.asarray(df.index.hour, dtype=float)
    m = _PRICE_FEATURE.match(name)
    if not m:
        return None
    n = int(m.group(2))
    out = np.full(len(c), np.nan)
    for i in range(n - 1, len(c)):
        w = c[i - n + 1:i + 1]
        if not np.all(np.isfinite(w)):
            continue
        ref = w.max() if m.group(1) == "dd" else w.min()
        out[i] = c[i] / ref - 1.0
    return out


def discovered(df: pd.DataFrame, *, feature: str, band: Sequence[float], horizon: int = 12,
               side: int = 1, atr_n: int = 20, stop_atr: float = 2.0, rr: float = 1.5
               ) -> list[Sig] | None:
    """Enter at the next open whenever the feature sits inside its quantile band (edges over the
    series' finite values, linear interpolation, >= 200 needed); ATR bracket; hold `horizon`."""
    v = price_feature(df, feature)
    if v is None:
        return None
    fin = np.isfinite(v)
    if fin.sum() < 200:
        return []
    lo_e, hi_e = np.quantile(v[fin], float(band[0])), np.quantile(v[fin], float(band[1]))
    if not (np.isfinite(lo_e) and np.isfinite(hi_e)) or hi_e <= lo_e:
        return []
    a = true_range_mean(df, atr_n)
    c = df["close"].to_numpy(float)
    sd = 1 if int(side) >= 0 else -1
    out: list[Sig] = []
    for i in range(atr_n, len(df) - 1):
        if not (fin[i] and lo_e <= v[i] <= hi_e):
            continue
        atr = a[i]
        if not (math.isfinite(atr) and atr > 0):
            continue
        out.append(Sig(df.index[i], sd, c[i] - sd * stop_atr * atr,
                       c[i] + sd * stop_atr * atr * rr, max(1, int(horizon))))
    return out


def signals_for(family: str, df: pd.DataFrame, params: Mapping[str, Any]
                ) -> tuple[list[Sig] | None, str]:
    """(signals, 'ok') or (None, why UNSUPPORTED). Never guesses a parameterisation."""
    p = {k: v for k, v in dict(params or {}).items()
         if k not in ("timeframe", "session", "input_symbol", "input_source", "peer_symbol",
                      "factor_symbols")}
    if family == "overnight_gap_decay":
        allowed = {"gap_atr", "atr_n", "stop_atr", "rr", "ttl_bars"}
        extra = sorted(set(p) - allowed)
        if extra:
            return None, f"overnight_gap_decay params outside the replica: {extra}"
        return overnight_gap_decay(df, **p), "ok"
    if family == "session_range_breakout":
        for k, off in _SRB_DEFAULT_OFF.items():
            if k in p and p[k] != off:
                return None, f"session_range_breakout filter {k}={p[k]!r} is not replicated"
            p.pop(k, None)
        allowed = {"range_start", "range_end", "signal_at", "wait_bars", "atr_n", "ttl_bars",
                   "rr"}
        extra = sorted(set(p) - allowed)
        if extra:
            return None, f"session_range_breakout params outside the replica: {extra}"
        return session_range_breakout(df, **p), "ok"
    if family == "discovered":
        allowed = {"feature", "band", "horizon", "side", "atr_n", "stop_atr", "rr"}
        extra = sorted(set(p) - allowed)
        if extra:
            return None, f"discovered params outside the replica: {extra}"
        if not p.get("feature") or not isinstance(p.get("band"), (list, tuple)):
            return None, "discovered spec names no feature or band"
        sigs = discovered(df, **p)
        if sigs is None:
            return None, (f"discovered feature {p['feature']!r} is not price-native; the replica "
                          "implements dd_n, ru_n and hour only")
        return sigs, "ok"
    return None, f"family {family!r} has no independent implementation yet"


# ------------------------------------------------------------------------------- costs
def round_trip_price(meta: Mapping[str, Any]) -> float:
    cs = float(meta.get("contract_size", 1e5) or 1e5)
    ts = float(meta.get("tick_size", 0.0) or 0.0)
    tv = float(meta.get("tick_value", 0.0) or 0.0)
    pts = float(meta.get("median_spread_pts", 0.0) or 0.0)
    spread = max(pts * ts * cs, MIN_SPREAD_PER_LOT) / cs
    comm = 2.0 * COMMISSION_PER_LOT_SIDE * (ts / tv if (tv > 0 and ts > 0) else 1.0 / cs)
    return spread + comm


def swap_price_per_night(meta: Mapping[str, Any]) -> float:
    ts = float(meta.get("tick_size", 0.0) or 0.0)
    return max(abs(float(meta.get("swap_long", 0.0) or 0.0)),
               abs(float(meta.get("swap_short", 0.0) or 0.0))) * ts


def rollovers(t0: pd.Timestamp, t1: pd.Timestamp) -> float:
    a = pd.Timestamp(t0).tz_convert("UTC") if pd.Timestamp(t0).tzinfo else pd.Timestamp(t0)
    b = pd.Timestamp(t1).tz_convert("UTC") if pd.Timestamp(t1).tzinfo else pd.Timestamp(t1)
    a, b = a.tz_localize(None), b.tz_localize(None)
    if not b > a:
        return 0.0
    first = a.normalize() + pd.Timedelta(hours=ROLLOVER_HOUR_UTC)
    if first <= a:
        first += pd.Timedelta(days=1)
    n = 0.0
    cur = first
    while cur <= b:
        n += 3.0 if cur.weekday() == TRIPLE_WEEKDAY else 1.0
        cur += pd.Timedelta(days=1)
    return n


# ------------------------------------------------------------------------------- engine
def simulate(df: pd.DataFrame, sigs: Sequence[Sig], meta: Mapping[str, Any]) -> list[Fill]:
    """The contract above, one position at a time, signals in emission order."""
    o = df["open"].to_numpy(float)
    h = df["high"].to_numpy(float)
    lo = df["low"].to_numpy(float)
    ix = df.index
    pos = {t: i for i, t in enumerate(ix)}
    rt = round_trip_price(meta)
    swap = swap_price_per_night(meta)
    busy = -1
    out: list[Fill] = []
    order = sorted(range(len(sigs)), key=lambda k: (pd.Timestamp(sigs[k].time), k))
    for k in order:
        s = sigs[k]
        i0 = pos.get(pd.Timestamp(s.time))
        if i0 is None:
            continue
        i = i0 + 1
        if i >= len(ix) - 1 or i <= busy:
            continue
        ref = o[i]
        if not (ref > 0):
            continue
        fill_i, entry, limit = i, ref, False
        if s.trigger is not None:
            limit = (s.side > 0 and s.trigger < ref) or (s.side < 0 and s.trigger > ref)
            hit = next((j for j in range(i, min(i + s.wait, len(ix)))
                        if lo[j] <= s.trigger <= h[j]), None)
            if hit is None:
                continue
            fill_i, entry = hit, float(s.trigger)
        unit = abs(entry - s.stop)
        exit_px: float | None = None
        exit_i = -1
        why = "ttl"
        for j in range(fill_i, min(len(ix), fill_i + s.ttl)):
            stopped = lo[j] <= s.stop if s.side > 0 else h[j] >= s.stop
            if stopped:
                exit_px, exit_i, why = s.stop, j, "stop"
                break
            reached = h[j] >= s.target if s.side > 0 else lo[j] <= s.target
            if reached and not (limit and j == fill_i):
                exit_px, exit_i, why = s.target, j, "target"
                break
        if exit_px is None:
            exit_i = min(fill_i + s.ttl, len(ix) - 1)
            exit_px = float(o[exit_i])
        busy = exit_i
        if not unit > 0:
            continue
        gross = s.side * (exit_px - entry) / unit
        nights = rollovers(ix[fill_i], ix[exit_i]) if swap else 0.0
        cost = (rt + swap * nights) / unit
        out.append(Fill(ix[fill_i], ix[exit_i], s.side, entry, float(exit_px), s.stop,
                        float(gross), float(cost), float(gross - cost), why))
    return out


def compare(a: Sequence[Mapping[str, Any]], b: Sequence[Mapping[str, Any]], *,
            tol_r: float = 1e-6) -> dict[str, Any]:
    """Trade-by-trade agreement keyed on (entry_time, side). Each row: entry_time, side,
    gross_r, cost_r, r. Returns counts on both sides, the unmatched on each side, and the
    worst gross / cost / net disagreement over the matched trades."""
    ka = {(pd.Timestamp(x["entry_time"]), int(x["side"])): x for x in a}
    kb = {(pd.Timestamp(x["entry_time"]), int(x["side"])): x for x in b}
    both = sorted(set(ka) & set(kb))
    only_a = sorted(set(ka) - set(kb))
    only_b = sorted(set(kb) - set(ka))

    def worst(field: str) -> float:
        d = [abs(float(ka[k][field]) - float(kb[k][field])) for k in both]
        return max(d) if d else 0.0

    wg, wc, wr = worst("gross_r"), worst("cost_r"), worst("r")
    n_bad = sum(1 for k in both if abs(float(ka[k]["r"]) - float(kb[k]["r"])) > tol_r)
    agree = not only_a and not only_b and n_bad == 0 and bool(both)
    ra = [float(x["r"]) for x in a]
    rb = [float(x["r"]) for x in b]
    return {"agree": agree, "n_original": len(ka), "n_replica": len(kb), "matched": len(both),
            "only_original": [str(k[0]) for k in only_a[:5]], "n_only_original": len(only_a),
            "only_replica": [str(k[0]) for k in only_b[:5]], "n_only_replica": len(only_b),
            "n_r_disagree": n_bad, "max_abs_gross_r": round(wg, 9),
            "max_abs_cost_r": round(wc, 9), "max_abs_r": round(wr, 9), "tol_r": tol_r,
            "sum_r_original": round(sum(ra), 6), "sum_r_replica": round(sum(rb), 6)}
