#!/usr/bin/env python3
"""TICK FEATURES: the recorded tape turned into point-in-time CONDITIONERS the generators can name.

THE ASK (principal, 2026-11-25): use the tick tape the way a tier-1 desk does -- not only as a
cost model and not only as raw input to the two tape families, but as STATE that every hypothesis
generator can condition on. The tape families (`liquidity_regime`, `spread_state`,
`orderflow_imbalance`) read it, and the cost/fill models read it. Nothing published it as a named
exogenous series, so `exogenous_conditioner` and the lake readers (`causal_lab`, `pack_cells`)
could not reach it at all. This organ publishes three features per non-exotic symbol:

  1. SPREAD REGIME     the hour's mean quoted spread (bps, positive-spread ticks only) ranked
                       against the symbol's OWN trailing distribution of hourly spreads
                       (REGIME_DAYS, strictly earlier hours): `spread_pctile`, and
                       `spread_state` -1 tight / 0 normal / +1 wide at TIGHT_PCT / WIDE_PCT.
  2. LIQUIDITY BY HOUR the tick-arrival rate (ticks per minute) and the mean spread by hour of day,
                       profiled over the trailing PROFILE_DAYS (strictly earlier days, same hour):
                       `tick_rate_profile`, `spread_hour_profile`, and the hour's deviation from
                       them as log ratios `tick_rate_dev`, `spread_hour_dev`. The report carries
                       the latest profile and today's deviations.
  3. POST-NEWS         for every scheduled release in the desk's calendars (the FF vintage store
                       `data/intelligence/ff_calendar_vintage`, High and Medium impact, plus the
                       FOMC, Fed and BoC calendars `orthogonal_sweep` already reads), on every
                       symbol carrying the released currency: the spread over 5/15/60 minutes
                       after release against the same hour's trailing profile (`spread_widen_*`),
                       and the realised move against the hour's trailing typical move of the same
                       length (`move_ratio_*`).

KNOWN AS OF ITS TIMESTAMP, AND THE RULE IS STATED ONCE (KNOWLEDGE_RULE). An hourly row summarises
ticks stamped inside [event_time, available_time) and nothing else -- even the 5- and 15-minute
move statistics only pair minutes that both lie inside the hour -- and every trailing distribution
it is ranked against holds strictly earlier hours. A news row is stamped at release + 60 minutes,
the end of its longest window, and its baselines are the profile of strictly earlier days. A row is
published only once a tick at or after its `available_time` is on disk, so an hour still being
recorded is never published half-built. A later tick therefore never changes an earlier row; a
re-converted day file can REVISE one, which is a revision, not a look-ahead.

`available_time` is genuinely UTC (the tape is stamped on the venue's epoch clock, as
`moat_series` and the tape families read it). The bar index is broker time under a UTC tzinfo, so
`exogenous_conditioner` must hold these series back by at least the broker offset plus one hour
(`MIN_CONDITIONER_LAG_HOURS`); its own default, a full publication day, already does.

PUBLISHED IN THE SHAPE THE EXOGENOUS PATH ALREADY READS. One CSV per symbol per kind under
`data/lake/series/` -- `tick_features_<SYM>.csv` (hourly) and `tick_news_<SYM>.csv` (per release)
-- in the lake's PIT envelope, through `alt_proxies.write_series_csv`, THE lake-series write. So a
cell `{"family": "exogenous_conditioner", "params": {"source": "tick_features_EURUSD",
"signal": "spread_pctile", "transform": "level_z"}}` runs with no further code, `causal_lab`
tests and donates every numeric column of every lake frame, and `source_conversion` counts each
file as a `lake_series` source the moment it lands.

READS, NEVER RE-PARSES. Tape days come from `moat_series.tape_index` and are read with
`moat_series._read_day` (the desk's one decision about what an unusable quote is); calendar
vintages with `bar_clock_release._rows`. One instrument-day is resident at a time, folded to at
most 24 hourly rows and kept in a small per-hour store under `data/lake/tick_features/`, so a pass
re-reads only day files whose size or mtime changed, and stops on a wall clock.

UNMEASURED IS NEVER ZERO. A non-exotic universe instrument with no tape is listed UNMEASURED with
the reason; a feature with too little history is UNMEASURED for that symbol. Exotics
(`universe_policy.is_exotic_symbol`) are set aside and named. This organ mints, judges, sizes and
vetoes nothing.

    python desks/mt5/research/tick_features.py --budget-s 240
    python desks/mt5/research/tick_features.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import moat_series as mos  # noqa: E402

SCHEMA = "tick-features/1"
SOURCE_ID = "tick_features"
UNMEASURED = "UNMEASURED"
MEASURED = "MEASURED"
REPORT = DESK / "reports" / "TICK_FEATURES.json"
SERIES_DIR = DESK / "data" / "lake" / "series"
STORE = DESK / "data" / "lake" / "tick_features"
VINTAGES = DESK / "data" / "intelligence" / "ff_calendar_vintage"

HOURLY_PREFIX, NEWS_PREFIX = "tick_features_", "tick_news_"
HOUR_MS, MIN_MS, DAY_MS = 3_600_000, 60_000, 86_400_000

#: Trailing window the spread regime ranks an hour against, and the observations it needs first.
REGIME_DAYS, REGIME_MIN_OBS = 30, 48
TIGHT_PCT, WIDE_PCT = 0.2, 0.8
#: Trailing days the hour-of-day profile is taken over, and the same-hour observations it needs.
PROFILE_DAYS, PROFILE_MIN_OBS = 20, 5
#: Windows after a release, in minutes. The row is known at the end of the longest.
NEWS_WINDOWS: tuple[int, ...] = (5, 15, 60)
#: A pre-release quote older than this is not "the price at release" -- the window is UNMEASURED.
NEWS_MAX_PRE_GAP_MS = 15 * MIN_MS
NEWS_IMPACTS: dict[str, int] = {"high": 3, "medium": 2}
#: Tape days read per symbol: the regime window plus the profile window plus slack.
MAX_DAYS = 45
#: Broker offset (+2/+3) plus one closed bar: the least `lag_hours` an exogenous_conditioner cell
#: on these series may run with, because the bar index is broker time under a UTC tzinfo.
MIN_CONDITIONER_LAG_HOURS = 4

KNOWLEDGE_RULE = (
    "available_time is the UTC instant a row became knowable: an hourly row = its hour's end, "
    "built only from ticks stamped inside [event_time, available_time) and ranked against "
    "strictly earlier hours (regime) or strictly earlier days at the same hour (profile); a "
    "news row = release + 60 min, the end of its longest window, against the profile of "
    "strictly earlier days. A row is published only once a tick at or after its available_time "
    "is on disk. Trailing windows only; a later tick never changes an earlier row.")

HOURLY_COLUMNS: tuple[str, ...] = (
    "spread_bps", "spread_pctile", "spread_state", "tick_rate", "tick_rate_profile",
    "tick_rate_dev", "spread_hour_profile", "spread_hour_dev", "zero_spread_frac")
NEWS_COLUMNS: tuple[str, ...] = tuple(
    [f"spread_widen_{w}m" for w in NEWS_WINDOWS] + [f"move_bps_{w}m" for w in NEWS_WINDOWS]
    + [f"move_ratio_{w}m" for w in NEWS_WINDOWS] + ["move_signed_bps_15m", "impact_level"])
FEATURES: dict[str, dict[str, Any]] = {
    "spread_regime": {"file": HOURLY_PREFIX + "<SYM>.csv",
                      "columns": ("spread_bps", "spread_pctile", "spread_state"),
                      "window": f"trailing {REGIME_DAYS} days of hourly spreads, min "
                                f"{REGIME_MIN_OBS} hours; tight <= {TIGHT_PCT}, wide >= "
                                f"{WIDE_PCT}"},
    "liquidity_by_hour": {"file": HOURLY_PREFIX + "<SYM>.csv",
                          "columns": ("tick_rate", "tick_rate_profile", "tick_rate_dev",
                                      "spread_hour_profile", "spread_hour_dev"),
                          "window": f"trailing {PROFILE_DAYS} days, same UTC hour, min "
                                    f"{PROFILE_MIN_OBS} days"},
    "post_news": {"file": NEWS_PREFIX + "<SYM>.csv", "columns": NEWS_COLUMNS,
                  "window": f"{list(NEWS_WINDOWS)} minutes after release, against the "
                            f"trailing {PROFILE_DAYS}-day profile of the release's UTC hour"},
}
BASE_COLUMNS: tuple[str, ...] = ("day", "hour_ms", "n", "n_pos", "sp_sum", "first_ms", "last_ms",
                                 "mid_first", "mid_last", "minutes", "mv5", "mv15")
RAW_NEWS_COLUMNS: tuple[str, ...] = ("event_id", "t_ms", "day", "currency", "title", "impact",
                                     "pre_mid", "mid5", "mid15", "mid60", "sp5", "sp15", "sp60")


def now_utc() -> datetime:
    return datetime.now(tz=UTC)


def _iso(ms: float) -> str:
    return datetime.fromtimestamp(float(ms) / 1000.0, tz=UTC).isoformat(timespec="seconds")


def _read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write_json(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f".tmp{os.getpid()}")
    tmp.write_text(json.dumps(doc, indent=1, default=str) + "\n", encoding="utf-8")
    mos._replace(tmp, path)


def _f(x: Any) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


# ------------------------------------------------------------------------------ the universe --

def _policy() -> Any:
    from research import universe_policy as up
    return up


def eligible(symbols: Iterable[str]) -> tuple[list[str], list[str]]:
    """(non-exotic symbols, exotic symbols set aside). The ONE exotic definition decides."""
    up = _policy()
    ok, exotic = [], []
    for s in sorted(set(symbols)):
        (exotic if up.is_exotic_symbol(s) else ok).append(s)
    return ok, exotic


def _currencies(symbol: str) -> set[str]:
    """The currencies a release can move this instrument through: an FX/metal/crypto pair's two
    legs, else the registry's profit currency (an index, an energy contract, a share CFD)."""
    up = _policy()
    out: set[str] = set()
    legs = up._pair_legs(symbol)
    if legs is not None:
        out.update(legs)
    row = up._registry().get(str(symbol).upper()) or {}
    cur = str(row.get("currency_profit") or "").upper()
    if cur:
        out.add(cur)
    return out


# ----------------------------------------------------------------------------- the calendar --

def _parse_ms(raw: Any) -> int | None:
    """A release instant with a CLOCK, to epoch ms; None for a day-precision or bad stamp."""
    s = str(raw or "").strip()
    if "T" not in s and ":" not in s:
        return None
    try:
        t = pd.Timestamp(s)
    except (ValueError, TypeError):
        return None
    if pd.isna(t):
        return None
    t = t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")
    return int(t.value // 1_000_000)


def load_events(vintage_dir: Path | None = None, *, extra: bool = True
                ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Every scheduled release with a clock, de-duplicated, and the accounting of what was not.

    The calendar is published ahead of its events (data_os `event_calendar`): the schedule is
    known before the release, and nothing here reads a value the release itself printed.
    """
    from libs.research.bar_clock_release import _rows
    root = vintage_dir or VINTAGES
    seen: dict[tuple[int, str, str], dict[str, Any]] = {}
    acc: dict[str, Any] = {"vintage_files": 0, "rows": 0, "kept": 0, "low_or_holiday": 0,
                           "day_precision_or_unparsed": 0, "no_currency": 0}
    files = sorted(root.glob("*.json*")) if root.is_dir() else []
    acc["vintage_files"] = len(files)
    for path in files:
        for row in _rows(path):
            acc["rows"] += 1
            impact = str(row.get("impact") or "").strip().lower()
            if impact not in NEWS_IMPACTS:
                acc["low_or_holiday"] += 1
                continue
            t = _parse_ms(row.get("event_date") or row.get("datetime"))
            if t is None:
                acc["day_precision_or_unparsed"] += 1
                continue
            curs = [str(c).upper() for c in (row.get("symbols") or []) if str(c).strip()]
            if not curs:
                acc["no_currency"] += 1
                continue
            title = str(row.get("title") or "")[:80]
            for cur in curs:
                seen.setdefault((t, cur, title), {"t_ms": t, "currency": cur, "title": title,
                                                  "impact": impact, "source": "ff_vintage"})
    if extra:
        try:
            from research.orthogonal_sweep import _extra_calendar_values
            vals = _extra_calendar_values()
        except Exception as exc:  # a calendar module that will not import is a named gap
            vals = {}
            acc["extra_calendars"] = f"{UNMEASURED}: {type(exc).__name__}"
        cur_of = {"fomc_decisions": "USD", "fed_calendar": "USD", "boc_policy_rate": "CAD"}
        for name, stamps in vals.items():
            cur = cur_of.get(name)
            if cur is None:
                continue
            for raw in stamps:
                t = _parse_ms(raw)
                if t is not None:
                    seen.setdefault((t, cur, name), {"t_ms": t, "currency": cur, "title": name,
                                                     "impact": "high", "source": name})
            acc[f"extra_{name}"] = len(stamps)
    events = sorted(seen.values(), key=lambda e: (e["t_ms"], e["currency"], e["title"]))
    for e in events:
        e["event_id"] = f"{e['t_ms']}|{e['currency']}|{e['title']}"
    acc["kept"] = len(events)
    return events, acc


# ------------------------------------------------------------------------ one tape day -> rows --

def _minute_mids(ms: np.ndarray, mid: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(every minute from the first to the last quoted one, the last mid at or before its end)."""
    minute = ms // MIN_MS
    last = np.r_[np.where(np.diff(minute) != 0)[0], minute.size - 1]
    mins, mm = minute[last], mid[last]
    grid = np.arange(int(mins[0]), int(mins[-1]) + 1, dtype="int64")
    pos = np.searchsorted(mins, grid, side="right") - 1
    return grid, mm[pos]


def hour_rows(day: str, d: Mapping[str, np.ndarray]) -> list[dict[str, Any]]:
    """One row per hour the day's ticks touch. Everything in a row comes from ticks INSIDE that
    hour: the 5/15-minute moves pair only minutes whose later end is still in the hour."""
    ms, mid, sp = d["ms"], d["mid"], d["spread_bps"]
    hours, start, count = np.unique(ms // HOUR_MS, return_index=True, return_counts=True)
    grid, gmid = _minute_mids(ms, mid)
    moves: dict[int, tuple[np.ndarray, np.ndarray]] = {}
    for w in (5, 15):
        if grid.size > w:
            m0 = grid[:-w]
            ok = (m0 % 60) + w <= 59
            mv = np.abs(np.log(gmid[w:] / gmid[:-w])) * 1e4
            moves[w] = (m0[ok] // 60, mv[ok])
    rows: list[dict[str, Any]] = []
    for h, a, n in zip(hours.tolist(), start.tolist(), count.tolist(), strict=True):
        b = a + n
        s = sp[a:b]
        pos = s > 0
        row: dict[str, Any] = {
            "day": day, "hour_ms": int(h) * HOUR_MS, "n": int(n), "n_pos": int(pos.sum()),
            "sp_sum": float(s[pos].sum()), "first_ms": int(ms[a]), "last_ms": int(ms[b - 1]),
            "mid_first": float(mid[a]), "mid_last": float(mid[b - 1]),
            "minutes": int(np.unique(ms[a:b] // MIN_MS).size)}
        for w in (5, 15):
            hh, mv = moves.get(w, (np.empty(0, "int64"), np.empty(0)))
            sel = mv[hh == h]
            row[f"mv{w}"] = float(np.median(sel)) if sel.size else float("nan")
        rows.append(row)
    return rows


def news_rows(day: str, d: Mapping[str, np.ndarray], events: list[dict[str, Any]]
              ) -> tuple[list[dict[str, Any]], int]:
    """Raw post-release measurements for the events inside this day's ticks. Only events whose
    longest window closed inside the file are kept; the count of the rest is returned."""
    ms, mid, sp = d["ms"], d["mid"], d["spread_bps"]
    out: list[dict[str, Any]] = []
    incomplete = 0
    longest = max(NEWS_WINDOWS) * MIN_MS
    for e in events:
        t = int(e["t_ms"])
        if not (ms[0] < t <= ms[-1]):
            continue
        if ms[-1] < t + longest:
            incomplete += 1
            continue
        i_pre = int(np.searchsorted(ms, t, side="left")) - 1
        if i_pre < 0 or t - ms[i_pre] > NEWS_MAX_PRE_GAP_MS:
            continue
        row: dict[str, Any] = {"event_id": e["event_id"], "t_ms": t, "day": day,
                               "currency": e["currency"], "title": e["title"],
                               "impact": e["impact"], "pre_mid": float(mid[i_pre])}
        a = int(np.searchsorted(ms, t, side="left"))
        for w in NEWS_WINDOWS:
            end = t + w * MIN_MS
            j = int(np.searchsorted(ms, end, side="left")) - 1   # last tick strictly before end
            row[f"mid{w}"] = float(mid[j])
            win = sp[a:j + 1]
            win = win[win > 0]
            row[f"sp{w}"] = float(win.mean()) if win.size else float("nan")
        out.append(row)
    return out, incomplete


# ------------------------------------------------------------------------------- the store --

def _base_path(sym: str, store: Path) -> Path:
    return store / "hourly" / f"{sym}.csv"


def _raw_news_path(sym: str, store: Path) -> Path:
    return store / "news" / f"{sym}.csv"


def _load_csv(path: Path, cols: tuple[str, ...]) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=list(cols))
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame(columns=list(cols))


def _save_csv(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f".tmp{os.getpid()}")
    frame.to_csv(tmp, index=False)
    mos._replace(tmp, path)


def _replace_days(frame: pd.DataFrame, days: set[str], rows: list[dict[str, Any]],
                  cols: tuple[str, ...]) -> pd.DataFrame:
    keep = frame[~frame["day"].astype(str).isin(days)] if not frame.empty else frame
    new = pd.DataFrame(rows, columns=list(cols))
    parts = [p for p in (keep, new) if not p.empty]
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=list(cols))


def _signature(path: Path) -> str:
    try:
        st = path.stat()
    except OSError:
        return ""
    return f"{st.st_size}:{st.st_mtime_ns}"


def refresh_symbol(sym: str, days: Mapping[str, Path], state: dict[str, str],
                   events: list[dict[str, Any]], *, store: Path, deadline: float
                   ) -> dict[str, Any]:
    """Re-read only the day files whose size or mtime changed, OLDEST FIRST, so the built set is
    always a contiguous run of days and a trailing window is never back-filled under a row that
    was already published. Returns what was read."""
    pending = [d for d in sorted(days) if state.get(d) != _signature(days[d])]
    done: dict[str, list[dict[str, Any]]] = {}
    news: dict[str, list[dict[str, Any]]] = {}
    incomplete, stopped, unreadable = 0, False, 0
    for day in pending:
        if time.monotonic() >= deadline:
            stopped = True
            break
        d = mos._read_day(days[day])
        state[day] = _signature(days[day])
        if d is None:
            unreadable += 1
            done[day] = []
            continue
        done[day] = hour_rows(day, d)
        news[day], inc = news_rows(day, d, events)
        incomplete += inc
        del d
    if done:
        path = _base_path(sym, store)
        _save_csv(path, _replace_days(_load_csv(path, BASE_COLUMNS), set(done),
                                      [r for v in done.values() for r in v], BASE_COLUMNS))
        npath = _raw_news_path(sym, store)
        _save_csv(npath, _replace_days(_load_csv(npath, RAW_NEWS_COLUMNS), set(done),
                                       [r for v in news.values() for r in v], RAW_NEWS_COLUMNS))
    return {"days_read": len(done), "days_pending": len(pending) - len(done),
            "unreadable_days": unreadable, "news_windows_incomplete": incomplete,
            "budget_stopped": stopped}


# ------------------------------------------------------------------------- the features --

def hourly_base(frame: pd.DataFrame) -> pd.DataFrame:
    """The per-hour store folded to one row per hour (an hour split across two day files is
    summed; its move medians come from the larger part), sorted, with derived columns."""
    if frame.empty:
        return pd.DataFrame(columns=["hour_ms"])
    f = frame.copy()
    for c in BASE_COLUMNS[1:]:
        f[c] = pd.to_numeric(f[c], errors="coerce")
    f = f.sort_values(["hour_ms", "n"]).reset_index(drop=True)
    g = f.groupby("hour_ms", sort=True)
    h = pd.DataFrame({
        "n": g["n"].sum(), "n_pos": g["n_pos"].sum(), "sp_sum": g["sp_sum"].sum(),
        "first_ms": g["first_ms"].min(), "last_ms": g["last_ms"].max(),
        "minutes": g["minutes"].sum(), "mv5": g["mv5"].last(), "mv15": g["mv15"].last()})
    firsts = f.loc[g["first_ms"].idxmin(), ["hour_ms", "mid_first"]].set_index("hour_ms")
    lasts = f.loc[g["last_ms"].idxmax(), ["hour_ms", "mid_last"]].set_index("hour_ms")
    h = h.join(firsts).join(lasts).reset_index()
    h["spread_bps"] = (h["sp_sum"] / h["n_pos"]).where(h["n_pos"] > 0)
    h["zero_spread_frac"] = 1.0 - h["n_pos"] / h["n"]
    h["tick_rate"] = h["n"] / 60.0
    h["mv60"] = (np.log(h["mid_last"] / h["mid_first"]).abs() * 1e4)
    h["hod"] = (h["hour_ms"] // HOUR_MS) % 24
    return h


def _pctile(prior: np.ndarray, x: float) -> float:
    prior = prior[np.isfinite(prior)]
    if prior.size < REGIME_MIN_OBS or not math.isfinite(x):
        return float("nan")
    return float(((prior < x).sum() + 0.5 * (prior == x).sum()) / prior.size)


def spread_regime(h: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """(percentile, state) per hour against STRICTLY EARLIER hours in the trailing window."""
    t = h["hour_ms"].to_numpy(dtype="int64")
    x = h["spread_bps"].to_numpy(dtype=float)
    lo = np.searchsorted(t, t - REGIME_DAYS * DAY_MS, side="left")
    hi = np.searchsorted(t, t, side="left")
    pct = np.array([_pctile(x[a:b], float(v)) for a, b, v in zip(lo, hi, x, strict=True)])
    state = np.where(np.isnan(pct), np.nan,
                     np.where(pct <= TIGHT_PCT, -1.0, np.where(pct >= WIDE_PCT, 1.0, 0.0)))
    return pct, state


def hour_profile(h: pd.DataFrame, cols: tuple[str, ...] = ("tick_rate", "spread_bps", "mv5",
                                                           "mv15", "mv60")
                 ) -> dict[str, np.ndarray]:
    """Per hour: the median of each column over STRICTLY EARLIER days at the same hour of day,
    within PROFILE_DAYS. NaN until PROFILE_MIN_OBS such days exist."""
    out = {c: np.full(len(h), np.nan) for c in cols}
    t_all = h["hour_ms"].to_numpy(dtype="int64")
    for _hod, idx in h.groupby("hod").indices.items():
        t = t_all[idx]
        lo = np.searchsorted(t, t - PROFILE_DAYS * DAY_MS, side="left")
        hi = np.arange(len(t))                    # rows before this one: strictly earlier days
        for c in cols:
            v = h[c].to_numpy(dtype=float)[idx]
            for k, (a, b) in enumerate(zip(lo, hi, strict=True)):
                s = v[a:b]
                s = s[np.isfinite(s)]
                if s.size >= PROFILE_MIN_OBS:
                    out[c][idx[k]] = float(np.median(s))
    return out


def _log_ratio(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    with np.errstate(divide="ignore", invalid="ignore"):
        r = np.log(a / b)
    return np.where(np.isfinite(r), r, np.nan)


def _stamps(event_ms: np.ndarray, avail_ms: np.ndarray, n: int) -> dict[str, Any]:
    return {"event_time": [_iso(v) for v in event_ms],
            "available_time": [_iso(v) for v in avail_ms], "source_id": [SOURCE_ID] * n}


def hourly_series(h: pd.DataFrame, latest_tick_ms: float
                  ) -> tuple[pd.DataFrame, dict[str, np.ndarray]]:
    """(the published hourly frame, its hour profile): closed hours only -- a tick at or after
    the hour's end exists on disk."""
    if h.empty:
        return pd.DataFrame(columns=["event_time", "available_time", "source_id",
                                     *HOURLY_COLUMNS]), {}
    pct, state = spread_regime(h)
    prof = hour_profile(h)
    tr, sp = h["tick_rate"].to_numpy(dtype=float), h["spread_bps"].to_numpy(dtype=float)
    end = h["hour_ms"].to_numpy(dtype="int64") + HOUR_MS
    frame = pd.DataFrame({
        **_stamps(h["hour_ms"].to_numpy(), end, len(h)),
        "spread_bps": sp, "spread_pctile": pct, "spread_state": state, "tick_rate": tr,
        "tick_rate_profile": prof["tick_rate"], "tick_rate_dev": _log_ratio(tr, prof["tick_rate"]),
        "spread_hour_profile": prof["spread_bps"],
        "spread_hour_dev": _log_ratio(sp, prof["spread_bps"]),
        "zero_spread_frac": h["zero_spread_frac"].to_numpy(dtype=float)})
    closed = end <= latest_tick_ms
    return frame[closed].reset_index(drop=True), {c: v[closed] for c, v in prof.items()}


def news_series(raw: pd.DataFrame, h: pd.DataFrame) -> pd.DataFrame:
    """One row per measured release, against the profile of the release's own hour -- which is
    built from strictly earlier days, so it was known before the release."""
    cols = ["event_time", "available_time", "source_id", "event", "currency", *NEWS_COLUMNS]
    if raw.empty or h.empty:
        return pd.DataFrame(columns=cols)
    prof = hour_profile(h)
    hidx = {int(v): i for i, v in enumerate(h["hour_ms"].to_numpy(dtype="int64"))}
    rows: list[dict[str, Any]] = []
    longest = max(NEWS_WINDOWS) * MIN_MS
    for r in raw.sort_values("t_ms").to_dict("records"):
        t = int(r["t_ms"])
        i = hidx.get((t // HOUR_MS) * HOUR_MS)
        base_sp = prof["spread_bps"][i] if i is not None else float("nan")
        pre = _f(r.get("pre_mid"))
        row: dict[str, Any] = {"event_time": _iso(t), "available_time": _iso(t + longest),
                               "source_id": SOURCE_ID, "event": r.get("title"),
                               "currency": r.get("currency"),
                               "impact_level": NEWS_IMPACTS.get(str(r.get("impact")), np.nan)}
        for w in NEWS_WINDOWS:
            m = _f(r.get(f"mid{w}"))
            mv = abs(math.log(m / pre)) * 1e4 if pre and m else float("nan")
            base_mv = prof[f"mv{w}"][i] if i is not None else float("nan")
            s = _f(r.get(f"sp{w}"))
            row[f"spread_widen_{w}m"] = (s / base_sp if s is not None and base_sp and
                                         math.isfinite(base_sp) else float("nan"))
            row[f"move_bps_{w}m"] = mv
            row[f"move_ratio_{w}m"] = (mv / base_mv if base_mv and math.isfinite(base_mv)
                                       and math.isfinite(mv) else float("nan"))
            if w == 15:
                row["move_signed_bps_15m"] = (math.log(m / pre) * 1e4 if pre and m
                                              else float("nan"))
        rows.append(row)
    return pd.DataFrame(rows, columns=cols)


# ------------------------------------------------------------------------------ the report --

def _status(n_measured: int, n_rows: int) -> str:
    if n_rows == 0:
        return UNMEASURED
    return MEASURED if n_measured else UNMEASURED


def _broker_offset(now: datetime) -> tuple[int | None, str]:
    try:
        from libs.research.bar_clock import to_bar_time
        moved, status, _why = to_bar_time(now, fallback=True)
    except Exception as exc:
        return None, f"{UNMEASURED}: {type(exc).__name__}"
    if moved is None:
        return None, f"{UNMEASURED}: {status}"
    return round((moved - now).total_seconds() / 3600.0), status


def symbol_doc(sym: str, hs: pd.DataFrame, prof: Mapping[str, np.ndarray], ns: pd.DataFrame,
               raw_news: int, offset: int | None, now: datetime) -> dict[str, Any]:
    def cov(frame: pd.DataFrame, cols: Iterable[str]) -> dict[str, Any]:
        n = len(frame)
        measured = int(frame[list(cols)].notna().any(axis=1).sum()) if n else 0
        doc: dict[str, Any] = {"status": _status(measured, n), "rows": n,
                               "measured_rows": measured}
        if n:
            doc["last_available_time"] = str(frame["available_time"].iloc[-1])
        if not measured:
            doc["why"] = ("no tape rows" if not n else "too little trailing history to rank "
                          "against (see the window)")
        return doc

    out: dict[str, Any] = {"status": MEASURED if len(hs) else UNMEASURED,
                           "hours_published": len(hs), "events_published": len(ns),
                           "files": {"hourly": f"data/lake/series/{HOURLY_PREFIX}{sym}.csv",
                                     "news": f"data/lake/series/{NEWS_PREFIX}{sym}.csv"}}
    reg = cov(hs, ("spread_pctile",))
    if len(hs):
        last = hs.iloc[-1]
        reg["latest"] = {"available_time": str(last["available_time"]),
                         "spread_bps": _f(last["spread_bps"]),
                         "spread_pctile": _f(last["spread_pctile"]),
                         "spread_state": _f(last["spread_state"])}
    liq = cov(hs, ("tick_rate_profile", "spread_hour_profile"))
    if len(hs):
        hod = pd.to_datetime(hs["event_time"], utc=True).dt.hour.to_numpy()
        profile: dict[str, Any] = {}
        for k in range(24):
            sel = np.where(hod == k)[0]
            if sel.size:
                j = int(sel[-1])
                profile[str(k)] = {
                    "tick_rate": _f(prof.get("tick_rate", np.full(len(hs), np.nan))[j]),
                    "spread_bps": _f(prof.get("spread_bps", np.full(len(hs), np.nan))[j]),
                    "broker_hour": (k + offset) % 24 if offset is not None else UNMEASURED}
        liq["profile_by_utc_hour"] = profile
        today = now.date().isoformat()
        tod = hs[hs["event_time"].astype(str).str.startswith(today)]
        liq["today_deviation"] = {
            str(pd.Timestamp(r["event_time"]).hour): {"tick_rate_dev": _f(r["tick_rate_dev"]),
                                                      "spread_hour_dev": _f(r["spread_hour_dev"])}
            for r in tod.to_dict("records")}
    news = cov(ns, ("spread_widen_15m", "move_ratio_15m"))
    news["raw_windows_held"] = raw_news
    if not raw_news:
        news["why"] = "no scheduled release with a complete window on this symbol's tape"
    out["features"] = {"spread_regime": reg, "liquidity_by_hour": liq, "post_news": news}
    return out


def _consumption() -> dict[str, Any]:
    return {
        "shape": ("CSV under data/lake/series/ in the lake's PIT envelope (event_time, "
                  "available_time, source_id) plus numeric signal columns -- exactly what "
                  "mt5desk.family_exogenous_conditioner.conditioner() reads"),
        "example_cell": {"family": "exogenous_conditioner",
                         "params": {"source": f"{HOURLY_PREFIX}EURUSD", "signal": "spread_pctile",
                                    "transform": "level_z",
                                    "lag_hours": MIN_CONDITIONER_LAG_HOURS}},
        "lag_rule": (f"lag_hours >= {MIN_CONDITIONER_LAG_HOURS}: available_time is UTC and the "
                     "bar index is broker time (+2/+3) under a UTC tzinfo; the family's default "
                     "of 24 is safe"),
        "readers": ["mt5desk/family_exogenous_conditioner.py (source/signal/transform)",
                    "research/causal_lab.py (every lake frame: tests each numeric column and "
                    "donates exogenous_conditioner cells)",
                    "research/source_conversion.py (each file is a lake_series source)"],
        "cross_asset": ("any symbol's cell may name another symbol's file as `source`: the "
                        "conditioner is the named series, the traded bars are the cell's own")}


# --------------------------------------------------------------------------------- the run --

def build(*, budget_s: float = 240.0, max_days: int = MAX_DAYS, dry_run: bool = False,
          symbols: list[str] | None = None, now: datetime | None = None,
          series_dir: Path | None = None, store: Path | None = None,
          vintage_dir: Path | None = None, extra_calendars: bool = True) -> dict[str, Any]:
    t0 = time.monotonic()
    deadline = t0 + max(1.0, float(budget_s))
    now = now or now_utc()
    series_dir = series_dir or SERIES_DIR
    store = store or STORE
    up = _policy()
    index = mos.tape_index()
    universe = list(up._registry())
    names = sorted(set(universe) | set(index))
    if symbols:
        names = [s for s in names if s in set(symbols)]
    ok, exotic = eligible(names)
    events, cal = load_events(vintage_dir, extra=extra_calendars)
    now_ms = now.timestamp() * 1000.0
    events = [e for e in events if e["t_ms"] + max(NEWS_WINDOWS) * MIN_MS <= now_ms]
    state_path = store / "state.json"
    state = _read_json(state_path, {}) or {}
    offset, offset_status = _broker_offset(now)

    built: dict[str, dict[str, Any]] = {}
    with_tape = [s for s in ok if s in index]
    with_tape.sort(key=lambda s: (len(state.get(s) or {}), s))   # thinnest store first
    stopped = False
    for sym in with_tape:
        if stopped or time.monotonic() >= deadline:
            stopped = True
            break
        days = dict(sorted(index[sym].items())[-max_days:]) if max_days > 0 else index[sym]
        curs = _currencies(sym)
        sym_events = [e for e in events if e["currency"] in curs]
        if dry_run:
            built[sym] = {"days_pending": sum(1 for d in days if (state.get(sym) or {}).get(d)
                                              != _signature(days[d]))}
            continue
        st = state.setdefault(sym, {})
        built[sym] = refresh_symbol(sym, days, st, sym_events, store=store, deadline=deadline)
        stopped = bool(built[sym]["budget_stopped"])
        _write_json(state_path, state)

    per_symbol: dict[str, Any] = {}
    published = 0
    for sym in ok:
        if sym not in index:
            per_symbol[sym] = {"status": UNMEASURED, "why": "no tape directory for this symbol",
                               "features": {k: {"status": UNMEASURED, "why": "no tape"}
                                            for k in FEATURES}}
            continue
        h = hourly_base(_load_csv(_base_path(sym, store), BASE_COLUMNS))
        if h.empty:
            per_symbol[sym] = {"status": UNMEASURED,
                               "why": "tape present but no day built yet (budget or unreadable)",
                               "features": {k: {"status": UNMEASURED, "why": "not built yet"}
                                            for k in FEATURES}}
            continue
        hs, prof = hourly_series(h, float(h["last_ms"].max()))
        raw = _load_csv(_raw_news_path(sym, store), RAW_NEWS_COLUMNS)
        ns = news_series(raw, h)
        if not dry_run:
            from research.alt_proxies import write_series_csv
            if len(hs):
                write_series_csv(series_dir, f"{HOURLY_PREFIX}{sym}", hs)
                published += 1
            if len(ns):
                write_series_csv(series_dir, f"{NEWS_PREFIX}{sym}", ns)
                published += 1
        per_symbol[sym] = symbol_doc(sym, hs, prof, ns, len(raw), offset, now)
        per_symbol[sym]["lane"] = up.lane(sym)
        if sym in built:
            per_symbol[sym]["this_pass"] = built[sym]

    def n_status(feature: str, status: str) -> int:
        return sum(1 for v in per_symbol.values()
                   if (v.get("features") or {}).get(feature, {}).get("status") == status)

    coverage = {k: {"measured": n_status(k, MEASURED), "unmeasured": n_status(k, UNMEASURED)}
                for k in FEATURES}
    measured_syms = sum(1 for v in per_symbol.values() if v.get("status") == MEASURED)
    return {
        "schema": SCHEMA, "generated_at": now.isoformat(timespec="seconds"),
        "status": MEASURED if measured_syms else UNMEASURED,
        "knowledge_time_rule": KNOWLEDGE_RULE, "features": FEATURES,
        "symbols_eligible": len(ok), "symbols_measured": measured_syms,
        "symbols_unmeasured": len(ok) - measured_syms, "series_published": published,
        "coverage": coverage,
        "exotics_set_aside": exotic,
        "hour_key": ("UTC hour of the tape stamp; broker_hour = (utc_hour + offset) % 24 where "
                     "libs.research.bar_clock converts now"),
        "broker_offset_hours": offset if offset is not None else UNMEASURED,
        "broker_offset_status": offset_status,
        "calendar": {**cal, "events_window_closed": len(events)},
        "consumption": _consumption(),
        "pass": {"elapsed_s": round(time.monotonic() - t0, 2), "budget_s": budget_s,
                 "budget_stopped": stopped, "max_days": max_days, "dry_run": dry_run,
                 "symbols_touched": len(built)},
        "symbols": per_symbol,
        "rule": ("report and conditioner only: it mints, judges, sizes and vetoes nothing. "
                 "UNMEASURED is never zero."),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--budget-s", type=float, default=240.0)
    ap.add_argument("--max-days", type=int, default=MAX_DAYS)
    ap.add_argument("--symbols", nargs="*", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out", default=str(REPORT))
    args = ap.parse_args(argv)
    doc = build(budget_s=args.budget_s, max_days=args.max_days, dry_run=args.dry_run,
                symbols=args.symbols)
    if not args.dry_run:
        _write_json(Path(args.out), doc)
    p = doc["pass"]
    print(f"tick_features: {doc['status']} measured={doc['symbols_measured']}/"
          f"{doc['symbols_eligible']} series={doc['series_published']} "
          f"exotics_set_aside={len(doc['exotics_set_aside'])} "
          f"elapsed={p['elapsed_s']}s stopped={p['budget_stopped']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
