"""The macro STATE the book is solved in: five variables, point-in-time, from the FRED archive.

WHAT THIS IS FOR. Every sleeve's expectancy in `robust_elog._posterior_mu` was UNCONDITIONAL on
the world outside its own price series: a dollar-bull sleeve carried one mean into a strong-dollar
year and a weak-dollar year alike. The desk had the inputs (`data/fred_macro.json`, refreshed by
`scripts/collect_fred_macro.py`) and a per-ORDER lean (`mt5desk.macro_view`), and nothing that
collapsed them into a state the ALLOCATOR could condition on. This is that collapse:

    dollar      DTWEXBGS   trade-weighted broad dollar
    risk        VIXCLS     risk appetite, inverted (high = risk-off)
    rates       DGS10      nominal 10-year
    real_rates  DFII10     10-year TIPS real yield (collected from 2026-09-16; absent before)
    curve       T10Y2Y     2s10s slope
    liquidity   WALCL      Fed balance sheet

each expressed as the trailing `RANK_WINDOW`-print percentile RANK of its level. A rank is a
regime, not a return: "the dollar is in the top decile of its year" is a slow-moving state the
book will still be in next week, which is what an allocation held for days needs. A daily change
is not.

POINT-IN-TIME BY CONSTRUCTION. The rank at a date uses only prints on or before that date, so a
day in 2024 is labelled with 2024's rank and never with the full sample's. `labeller` goes one
step further for the state-admission test and reads the state as of the day BEFORE a trade, so a
print published the evening of the trade cannot label the trade it followed.

THREE CONSUMERS, ONE STATE:
  1. `kernel_weights(dates)` -- how similar each historical day's state was to TODAY's, in
     [0, 1]. `pf_allocator` hands these to `_posterior_mu`, which forms each sleeve's OWN
     regime-weighted mean as a contrast against its unconditional one. That is the
     regime-conditional expectancy: the sleeve that earned more on days like today is tilted up,
     the one that earned less is tilted down, both shrunk and both bounded, and the heat between
     them is what moves. Nothing is refused and total heat is untouched.
  2. `labeller(dim)` -- a bucket for a trade's own moment, so `libs.regime.state_admission` can
     JUDGE `dollar` and `risk` as conditioning dimensions on realised forward trades, walk-forward,
     and bury them if they measure worse (the same graveyard session/weekday/event/rvol face).
  3. `now()` -- the state, its buckets and a confidence, for the allocation artifact.

STALENESS WIDENS THE KERNEL RATHER THAN LYING ABOUT TODAY. Freshness decays to zero over
`STALE_DAYS`; the kernel bandwidth is divided by it, so a month-old archive yields near-uniform
weights, a regime-weighted mean equal to the unconditional one, and a tilt of zero. A stale view
tilts nothing, and says so in `now()["status"]`.

NONE IS A REAL ANSWER. No archive, a series with fewer than `RANK_WINDOW` prints, a date outside
the archive -- each yields no weight (NaN, excluded from BOTH sides of the contrast), an empty
bucket, or an UNMEASURED status. Never a guessed rank of 0.5 wearing a measurement's clothes.
"""
from __future__ import annotations

import json
import math
import os
from collections.abc import Callable, Iterable, Sequence
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
#: The rolling ~3-year archive every older consumer reads, and the full fetch the collector
#: writes beside it (2026-09-16). The regime kernel needs a state on every day of the backtest
#: matrix, so it prefers the long one; a box that has not run the collector since still works
#: off the short one and simply covers fewer days.
ARCHIVE = ROOT / "data" / "fred_macro.json"
ARCHIVE_LONG = ROOT / "data" / "fred_macro_long.json"


def resolve_archive(path: Path | None = None) -> Path:
    """The archive to read: an explicit path, else the long fetch when present, else the short."""
    if path is not None:
        return path
    return ARCHIVE_LONG if ARCHIVE_LONG.exists() else ARCHIVE

#: state dimension -> FRED series id. Order is the order the artifact reports them in.
SERIES: dict[str, str] = {
    "dollar": "DTWEXBGS", "risk": "VIXCLS", "rates": "DGS10", "real_rates": "DFII10",
    "curve": "T10Y2Y", "liquidity": "WALCL",
}
#: The dimensions the KERNEL conditions on. Dollar and risk are the two every FX and metals sleeve
#: expresses; rates is the third axis of the macro trade. Curve and liquidity are reported, and
#: available to the admission test, but not kernelled: five dimensions at bandwidth 0.2 would
#: leave almost no historical day "like today" and the contrast would be noise wearing precision.
KERNEL_DIMS: tuple[str, ...] = ("dollar", "risk", "rates")
#: Prints in the trailing rank window. ~250 trading-day prints is one year for the daily series;
#: the weekly WALCL and monthly M2 get a year in their own print count (52 / 12) -- see `_rank`.
RANK_WINDOW = int(os.environ.get("MACRO_RANK_WINDOW", "250"))
#: Kernel bandwidth in rank units at full freshness. 0.2 means a day whose dollar rank differs
#: from today's by 0.2 (a fifth of the year's range) gets weight exp(-0.5) ~ 0.61 on that axis.
BANDWIDTH = float(os.environ.get("MACRO_KERNEL_BW", "0.2"))
#: Days after which the archive is treated as saying nothing about today.
STALE_DAYS = float(os.environ.get("MACRO_STALE_DAYS", "30"))
#: Bucket edges for the admission labeller: terciles of the rank.
LOW_EDGE, HIGH_EDGE = 1.0 / 3.0, 2.0 / 3.0

#: Per-series window in PRINTS, so a weekly or monthly series still ranks over about a year.
_WINDOW_BY_SERIES = {"WALCL": 52, "M2SL": 12}

_CACHE: dict[str, Any] = {"key": None, "states": None}


def _load_archive(path: Path | None = None,
                  ) -> tuple[dict[str, list[tuple[str, float]]], str | None]:
    """series id -> [(date, value), ...] sorted, plus the newest print date across all."""
    path = resolve_archive(path)
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}, None
    out: dict[str, list[tuple[str, float]]] = {}
    newest: str | None = None
    for sid, pts in (doc.get("series") or {}).items():
        if not isinstance(pts, list):
            continue
        rows: list[tuple[str, float]] = []
        for p in pts:
            try:
                d, v = str(p[0])[:10], float(p[1])
            except (TypeError, ValueError, IndexError):
                continue
            if math.isfinite(v) and len(d) == 10:
                rows.append((d, v))
        rows.sort()
        if rows:
            out[str(sid)] = rows
            if newest is None or rows[-1][0] > newest:
                newest = rows[-1][0]
    return out, newest


def _rank(values: np.ndarray, window: int) -> np.ndarray:
    """Trailing-window percentile rank of each value among the `window` prints ending at it.

    NaN until `window` prints exist. Rank is the share of the window strictly below the value,
    the same definition `mt5desk.macro_view._rank` uses, so the two organs agree on what "top of
    its year" means.
    """
    n = values.size
    out = np.full(n, np.nan)
    if n < window:
        return out
    for i in range(window - 1, n):
        tail = values[i - window + 1: i + 1]
        out[i] = float((tail < values[i]).sum()) / float(window - 1)
    return out


def daily_states(path: Path | None = None) -> dict[str, Any]:
    """{dim: {date -> rank}} on a CALENDAR-DAY grid, forward-filled from each print to the next.

    Forward-filling is the point-in-time rule, not a convenience: on a Saturday the state is
    Friday's print, and on a day whose print has not arrived yet the state is yesterday's. A print
    is never carried BACKWARD.
    """
    path = resolve_archive(path)
    key: tuple[str, float | None]
    try:
        key = (str(path), path.stat().st_mtime)
    except OSError:
        key = (str(path), None)
    if _CACHE["key"] == key and _CACHE["states"] is not None:
        return dict(_CACHE["states"])
    series, newest = _load_archive(path)
    states: dict[str, dict[str, float]] = {}
    for dim, sid in SERIES.items():
        rows = series.get(sid)
        if not rows:
            continue
        window = _WINDOW_BY_SERIES.get(sid, RANK_WINDOW)
        dates = [d for d, _ in rows]
        ranks = _rank(np.array([v for _, v in rows], dtype=float), window)
        by_day: dict[str, float] = {}
        last: float | None = None
        first = date.fromisoformat(dates[0])
        stop = date.fromisoformat(newest or dates[-1])
        j = 0
        day = first
        while day <= stop:
            ds = day.isoformat()
            while j < len(dates) and dates[j] <= ds:
                last = None if not math.isfinite(ranks[j]) else float(ranks[j])
                j += 1
            if last is not None:
                by_day[ds] = last
            day += timedelta(days=1)
        if by_day:
            states[dim] = by_day
    doc = {"states": states, "newest": newest}
    _CACHE["key"], _CACHE["states"] = key, doc
    return dict(doc)


def bucket(rank: float | None) -> str:
    """"low" / "mid" / "high" tercile of a rank, "" when unknown."""
    if rank is None or not math.isfinite(rank):
        return ""
    if rank < LOW_EDGE:
        return "low"
    if rank > HIGH_EDGE:
        return "high"
    return "mid"


def _freshness(newest: str | None, now: datetime | None = None) -> tuple[float, float | None]:
    if not newest:
        return 0.0, None
    try:
        age = ((now or datetime.now(tz=UTC)).date()
               - date.fromisoformat(newest)).days
    except ValueError:
        return 0.0, None
    return max(0.0, 1.0 - float(age) / STALE_DAYS), float(age)


def now(path: Path | None = None, at: datetime | None = None) -> dict[str, Any]:
    """Today's state: rank and bucket per dimension, freshness, confidence, and why."""
    path = resolve_archive(path)
    doc = daily_states(path)
    states, newest = doc["states"], doc["newest"]
    if not states or not newest:
        return {"status": "UNMEASURED", "why": f"no macro state: {path.name} holds no series "
                f"with {RANK_WINDOW}+ prints", "state": {}, "labels": {}, "confidence": 0.0,
                "freshness": 0.0, "age_days": None, "newest_print": newest}
    state = {dim: float(by_day[newest]) for dim, by_day in states.items() if newest in by_day}
    # A dimension whose series ended before the newest print of the others reads its own last
    # calendar day, never the others'.
    for dim, by_day in states.items():
        if dim not in state and by_day:
            state[dim] = float(by_day[max(by_day)])
    fresh, age = _freshness(newest, at)
    drivers = [abs(2.0 * state[d] - 1.0) for d in KERNEL_DIMS if d in state]
    strength = float(sum(drivers) / len(drivers)) if drivers else 0.0
    conf = round(strength * fresh, 4)
    labels = {dim: bucket(v) for dim, v in state.items()}
    why = ", ".join(f"{d} {state[d]:.2f} ({labels[d]})" for d in SERIES if d in state)
    return {"status": "MEASURED" if fresh > 0 else "STALE",
            "why": f"{why}; newest print {newest} ({age:.0f}d old -> freshness {fresh:.2f})",
            "state": {k: round(v, 4) for k, v in state.items()}, "labels": labels,
            "confidence": conf, "freshness": round(fresh, 4), "strength": round(strength, 4),
            "age_days": age, "newest_print": newest, "kernel_dims": list(KERNEL_DIMS),
            "bandwidth": BANDWIDTH}


def _as_day(d: Any) -> str:
    if isinstance(d, datetime):
        return d.date().isoformat()
    if isinstance(d, date):
        return d.isoformat()
    return str(d)[:10]


def kernel_weights(dates: Iterable[Any], path: Path | None = None, at: datetime | None = None,
                   dims: Sequence[str] = KERNEL_DIMS, bandwidth: float = BANDWIDTH,
                   ) -> tuple[np.ndarray, dict[str, Any]]:
    """Weight in [0, 1] per date: how much that day's macro state resembles today's.

    Product over `dims` of a Gaussian kernel in rank distance. A day with no state on some
    kernel dimension gets 0.0 -- it contributes to neither side of the contrast -- and a day
    AFTER the newest print (forward days the archive has not caught up with) takes the newest
    state, which is the point-in-time reading a desk would have had on that day.

    Returns (weights, meta). A day with no state on some kernel dimension is NaN -- it leaves
    both sides of the contrast -- and a day unlike today is a small positive number, never NaN.
    `meta["status"]` is UNMEASURED when nothing could be weighted, in which case every weight is
    NaN and the posterior behaves as if this level did not exist.
    """
    days = [_as_day(d) for d in dates]
    # NaN IS "NO STATE FOR THIS DAY" AND 0.0 IS "A DAY UNLIKE TODAY". They are different
    # answers and the posterior must not confuse them: a day with no state leaves BOTH sides of
    # the contrast, a day unlike today stays on the unconditional side and weighs nothing on
    # the regime side. Encoding the first as 0.0 made the contrast compare the regime days with
    # themselves, which is identically zero (measured in the first test of this level).
    w = np.full(len(days), np.nan, dtype=float)
    doc = daily_states(path)
    states, newest = doc["states"], doc["newest"]
    use = [d for d in dims if d in states]
    if not use or not newest:
        return w, {"status": "UNMEASURED", "why": "no kernel dimension has a rankable series",
                   "dims": [], "n_weighted": 0}
    fresh, age = _freshness(newest, at)
    if fresh <= 0.0:
        # Uniform weights: the contrast is then identically zero, which is the honest tilt from
        # an archive that says nothing about today. Not zeros -- zeros would read as "no days
        # resemble today", and a stale file does not know that either.
        w[:] = 1.0
        return w, {"status": "STALE", "why": f"newest print {newest} is {age:.0f}d old; "
                   f"uniform weights, no tilt", "dims": use, "n_weighted": len(days),
                   "freshness": 0.0}
    bw = float(bandwidth) / max(fresh, 1e-3)
    today = {d: states[d].get(newest, states[d][max(states[d])]) for d in use}
    for i, ds in enumerate(days):
        acc = 1.0
        ok = True
        for d in use:
            by_day = states[d]
            r = by_day.get(ds)
            if r is None:
                if ds > newest:
                    r = today[d]
                else:
                    ok = False
                    break
            z = (float(r) - float(today[d])) / bw
            acc *= math.exp(-0.5 * z * z)
        if ok:
            w[i] = acc
    known = w[np.isfinite(w)]
    n_w = int(known.size)
    sw = float(known.sum()) if n_w else 0.0
    return w, {"status": "MEASURED", "dims": use, "n_weighted": n_w, "n_dates": len(days),
               "freshness": round(fresh, 4), "bandwidth_effective": round(bw, 4),
               "today": {d: round(float(v), 4) for d, v in today.items()},
               "sum_weights": round(sw, 3),
               "n_eff": (round(sw ** 2 / float((known * known).sum()), 2)
                         if n_w and sw > 0 else 0.0)}


def labeller(dim: str, path: Path | None = None) -> Callable[[str], str] | None:
    """A function from a timestamp to this dimension's bucket AS OF THE DAY BEFORE, or None.

    The day before, strictly: a trade entered on the 14th is labelled with the state as of the
    13th's prints, so a print released on the 14th after the trade cannot label it.
    """
    if dim not in SERIES:
        return None
    states = daily_states(path)["states"].get(dim)
    if not states:
        return None
    first = min(states)

    def _label(when: str) -> str:
        try:
            d = datetime.fromisoformat(str(when).replace("Z", "+00:00")).date()
        except (TypeError, ValueError):
            try:
                d = date.fromisoformat(str(when)[:10])
            except ValueError:
                return ""
        ds = (d - timedelta(days=1)).isoformat()
        if ds < first:
            return ""
        r = states.get(ds)
        return bucket(r)
    return _label
