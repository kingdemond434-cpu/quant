"""THE GAIN TEST FOR A RELEASED SERIES: does its surprise lead the instrument AFTER release, more
than the same surprises stamped on the wrong dates do?

WHY A PLACEBO AND NOT ONLY A t-STAT. An alternative-data series that trends with the business
cycle correlates with any instrument that trends with the business cycle, whatever day the print
lands. The claim worth paying for is narrower: the market moves in the direction of the surprise
in the window AFTER the desk could first read it. So the same surprise values are re-stamped on
shifted release dates -- same values, same distribution, same regime -- and the true IC must beat
the |IC| of those placebos. A series whose "edge" survives the shift is a slow trend co-moving
with the tape, not information arriving on a date.

POINT IN TIME. An event is `(available_time, surprise)`. The entry is the first bar whose label is
at or after `available_time + clock_pad_h` (bars carry BROKER time under a UTC tzinfo, +2 winter
and +3 summer, so a flat +3h pad can only ever be late, never early); the return runs from that
bar's close to the close `horizon_bars` later. Events are thinned so no two windows overlap --
overlapping windows are one observation counted several times.

    ic, n, placebo -> GainResult.verdict in {PASS, FAIL, UNMEASURED}

UNMEASURED is a verdict (L1.28a): fewer than `min_events` independent windows is not a zero.
Pure numpy/pandas; no desk paths, so it is testable on synthetic data with a planted effect.
"""
from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np
import pandas as pd

#: Bars carry broker time (UTC+2 winter, UTC+3 summer) under a UTC tzinfo. Adding 3h to a UTC
#: release instant can only place the entry at or after the true first tradable bar.
CLOCK_PAD_H = 3
#: Placebo shifts in calendar days, both directions, none a multiple of 7 below 30 so a weekly
#: seasonal cannot line the placebo up with the true calendar. 38 shifts: the smallest reachable
#: placebo p is 1/39 ~= 0.026.
PLACEBO_SHIFTS_D: tuple[int, ...] = tuple(
    s * d for d in (3, 5, 9, 11, 13, 16, 19, 23, 26, 31, 37, 41, 45, 50, 55, 61, 67, 73, 79)
    for s in (1, -1))
MIN_EVENTS = 24
ALPHA_PLACEBO = 0.05
ALPHA_FAMILY = 0.05


@dataclass
class GainResult:
    verdict: str
    ic: float | None
    n: int
    t: float | None
    p_t: float | None
    p_placebo: float | None
    placebo_abs_ic_median: float | None
    placebo_abs_ic_p95: float | None
    n_placebos: int
    horizon_bars: int
    why: str
    events_dropped: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _spearman(a: np.ndarray, b: np.ndarray) -> float | None:
    if a.size < 3 or b.size != a.size:
        return None
    ra = pd.Series(a).rank().to_numpy(dtype=float)
    rb = pd.Series(b).rank().to_numpy(dtype=float)
    if float(np.std(ra)) == 0.0 or float(np.std(rb)) == 0.0:
        return None
    return float(np.corrcoef(ra, rb)[0, 1])


def _norm_sf(x: float) -> float:
    return 0.5 * math.erfc(x / math.sqrt(2.0))


def event_returns(events: Sequence[tuple[Any, float]], close: pd.Series, horizon_bars: int, *,
                  clock_pad_h: int = CLOCK_PAD_H,
                  dropped: dict[str, int] | None = None) -> tuple[np.ndarray, np.ndarray]:
    """(surprises, forward log returns) for non-overlapping post-release windows."""
    drop = dropped if dropped is not None else {}
    idx = pd.DatetimeIndex(close.index)
    if idx.tz is None:
        idx = idx.tz_localize("UTC")
    px = close.to_numpy(dtype=float)
    rows: list[tuple[pd.Timestamp, float]] = []
    for when, s in events:
        try:
            ts = pd.Timestamp(when)
        except (TypeError, ValueError):
            drop["bad_time"] = drop.get("bad_time", 0) + 1
            continue
        if pd.isna(ts) or s is None or not math.isfinite(float(s)):
            drop["bad_value"] = drop.get("bad_value", 0) + 1
            continue
        ts = ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")
        rows.append((ts + pd.Timedelta(hours=int(clock_pad_h)), float(s)))
    rows.sort(key=lambda r: r[0])
    xs: list[float] = []
    ys: list[float] = []
    free_from = -1
    for ts, s in rows:
        pos = int(idx.searchsorted(ts, side="left"))
        end = pos + int(horizon_bars)
        if pos >= len(idx) or end >= len(idx):
            drop["no_forward_bars"] = drop.get("no_forward_bars", 0) + 1
            continue
        if pos < free_from:
            drop["overlapping_window"] = drop.get("overlapping_window", 0) + 1
            continue
        a, b = px[pos], px[end]
        if not (np.isfinite(a) and np.isfinite(b)) or a <= 0 or b <= 0:
            drop["bad_price"] = drop.get("bad_price", 0) + 1
            continue
        xs.append(s)
        ys.append(math.log(b / a))
        free_from = end
    return np.asarray(xs, dtype=float), np.asarray(ys, dtype=float)


def release_gain(events: Sequence[tuple[Any, float]], close: pd.Series, *,
                 horizon_bars: int = 120, n_cells: int = 1,
                 shifts_d: Sequence[int] = PLACEBO_SHIFTS_D, min_events: int = MIN_EVENTS,
                 clock_pad_h: int = CLOCK_PAD_H) -> GainResult:
    """IC of surprise on the post-release return, against shifted-date placebos.

    PASS needs all three: enough independent windows, a Bonferroni-charged t across `n_cells`
    (every cell the caller tested is charged, not only this one), and the true |IC| beating the
    placebo distribution at ALPHA_PLACEBO.
    """
    dropped: dict[str, int] = {}
    x, y = event_returns(events, close, horizon_bars, clock_pad_h=clock_pad_h, dropped=dropped)
    n = int(x.size)
    if n < min_events:
        return GainResult("UNMEASURED", None, n, None, None, None, None, None, 0, horizon_bars,
                          f"{n} independent post-release windows < {min_events}",
                          dropped)
    ic = _spearman(x, y)
    if ic is None:
        return GainResult("UNMEASURED", None, n, None, None, None, None, None, 0, horizon_bars,
                          "surprise or return is constant: no rank correlation exists", dropped)
    t = ic * math.sqrt(max(n - 2, 1) / max(1e-12, 1.0 - ic * ic))
    p_t = 2.0 * _norm_sf(abs(t))
    placebo: list[float] = []
    for d in shifts_d:
        shifted = [(pd.Timestamp(w) + pd.Timedelta(days=int(d)), s) for w, s in events]
        px_, py_ = event_returns(shifted, close, horizon_bars, clock_pad_h=clock_pad_h)
        pic = _spearman(px_, py_) if px_.size >= max(8, min_events // 2) else None
        if pic is not None:
            placebo.append(abs(pic))
    if len(placebo) < 10:
        return GainResult("UNMEASURED", round(ic, 4), n, round(t, 3), p_t, None, None, None,
                          len(placebo), horizon_bars,
                          f"only {len(placebo)} placebo windows could be formed", dropped)
    arr = np.asarray(placebo)
    p_pl = float((1 + int((arr >= abs(ic)).sum())) / (1 + arr.size))
    charged = min(1.0, p_t * max(1, int(n_cells)))
    ok = charged <= ALPHA_FAMILY and p_pl <= ALPHA_PLACEBO
    why = (f"IC {ic:+.3f} over {n} windows; t {t:+.2f} (Bonferroni over {n_cells} cells -> "
           f"p {charged:.3g}); placebo p {p_pl:.3f} against {arr.size} shifted calendars")
    return GainResult("PASS" if ok else "FAIL", round(ic, 4), n, round(t, 3), p_t, round(p_pl, 4),
                      round(float(np.median(arr)), 4), round(float(np.quantile(arr, 0.95)), 4),
                      int(arr.size), horizon_bars, why, dropped)
