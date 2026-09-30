"""A publisher's own wall clock, read off broker-stamped bars, DST-correct on every date.

WHY THIS EXISTS (2026-09-30). A fixing, a closing auction or a policy announcement happens at a
LOCAL time -- 16:00 London, 09:15 Beijing, 09:45 Toronto -- and the bars carry the venue's stamp
(New York + 7 h, `libs/regime/session_clock.py`). A family that takes ONE broker hour is right
only on the dates when the publisher's and New York's daylight-time calendars agree: for London
that is ~92% of the year, for Hong Kong, Beijing or Seoul (no DST) about 65% at one hour and 35%
at the next. A recipe then had to mint two cells per window, each wrong a third of the year, and
the gauntlet judged a rule nobody proposed on the other dates.

This module lets a family take the window AS THE PUBLISHER STATES IT (`tz`, `at` = "HH:MM",
`align`) and finds, per bar, whether that bar is the window on that bar's own date. One cell, the
right bar on every date, no variants.

    align = "contains"   the bar whose span [open, open + bar length) contains `at`
                         (the bar in which the fix is struck / the auction runs)
    align = "start"      the first bar that opens at or after `at` (the first full bar of a
                         session that begins at `at`)

A half-hour zone (India, +05:30) works unchanged: the bar's local open is xx:30 and the span test
is done in minutes, never in hours.

CALENDARS. A dated event (a central bank's eight announcements a year) is a `calendar`: a JSON file
under `desks/mt5/data/calendars/<name>.json` holding `{"tz": ..., "dates": {"YYYY-MM-DD": "HH:MM"}}`
-- the publisher's own dates and local times. A family given a calendar fires ONLY on those dates,
at that date's own time. A date absent from the file is not an event; a file that cannot be read is
no events at all (the cell makes no trades), never "every day".
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ALIGNS = ("contains", "start")
CALENDARS = Path(__file__).resolve().parents[1] / "data" / "calendars"


def _server_to_utc(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    try:
        from libs.regime.session_clock import server_to_utc
    except ImportError:  # pragma: no cover - the desk root on the path is the only layout used
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
        from libs.regime.session_clock import server_to_utc
    return server_to_utc(index)


def minutes_of(at: str) -> int | None:
    """"HH:MM" -> minutes after local midnight; None for anything else."""
    try:
        h, m = str(at).strip().split(":")
        hh, mm = int(h), int(m)
    except (ValueError, AttributeError):
        return None
    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        return None
    return hh * 60 + mm


def bar_minutes(index: pd.DatetimeIndex) -> int:
    """The chart's bar length in minutes (median spacing; 60 when it cannot be read)."""
    if len(index) < 2:
        return 60
    d = np.diff(index.asi8) // 60_000_000_000
    d = d[d > 0]
    return int(np.median(d)) if len(d) else 60


def local_frame(index: Any, tz: str) -> tuple[np.ndarray, np.ndarray]:
    """(local open minute-of-day, local date as int YYYYMMDD) of every broker-stamped bar."""
    idx = pd.DatetimeIndex(index)
    local = _server_to_utc(idx).tz_convert(tz)
    minute = np.asarray(local.hour * 60 + local.minute, dtype=np.int32)
    ymd = np.asarray(local.year * 10000 + local.month * 100 + local.day, dtype=np.int64)
    return minute, ymd


def window_mask(index: Any, tz: str, at: str, align: str = "contains") -> np.ndarray | None:
    """Per bar, whether it is the window on its own date. None when the window is malformed
    (unknown zone, bad "HH:MM", unknown align) -- a caller then makes no trades, never guesses."""
    t = minutes_of(at)
    if t is None or align not in ALIGNS or not tz:
        return None
    idx = pd.DatetimeIndex(index)
    try:
        minute, _ymd = local_frame(idx, tz)
    except Exception:
        return None
    span = bar_minutes(idx)
    if align == "contains":
        # [open, open + span) contains t, modulo the day (a bar opening 23:30 contains 00:10)
        return np.asarray(((t - minute) % 1440) < span)
    return np.asarray(((minute - t) % 1440) < span)


@lru_cache(maxsize=32)
def _calendar(name: str, mtime_ns: int) -> tuple[str, dict[int, str]] | None:
    try:
        doc = json.loads((CALENDARS / f"{name}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    tz = str(doc.get("tz") or "")
    dates = doc.get("dates") if isinstance(doc.get("dates"), dict) else {}
    out: dict[int, str] = {}
    for k, v in dates.items():
        try:
            out[int(str(k).replace("-", ""))] = str(v)
        except ValueError:
            continue
    return (tz, out) if tz and out else None


def calendar(name: str) -> tuple[str, dict[int, str]] | None:
    """(tz, {YYYYMMDD: "HH:MM"}) of a named event calendar, or None when it cannot be read."""
    if not name or "/" in name or "\\" in name or name.startswith("."):
        return None
    try:
        m = (CALENDARS / f"{name}.json").stat().st_mtime_ns
    except OSError:
        return None
    return _calendar(name, m)


def calendar_mask(index: Any, name: str, align: str = "contains") -> np.ndarray | None:
    """Per bar, whether it is the window of a calendar event on its own date and at that date's
    own local time. None when the calendar is unreadable or the align unknown."""
    cal = calendar(name)
    if cal is None or align not in ALIGNS:
        return None
    tz, dates = cal
    idx = pd.DatetimeIndex(index)
    try:
        minute, ymd = local_frame(idx, tz)
    except Exception:
        return None
    span = bar_minutes(idx)
    out = np.zeros(len(idx), dtype=bool)
    for day, at in dates.items():
        t = minutes_of(at)
        if t is None:
            continue
        on = ymd == day
        if not on.any():
            continue
        hit = (((t - minute) % 1440) < span) if align == "contains" else (
            ((minute - t) % 1440) < span)
        # the window must lie on that local date: a "contains" bar opening the day before
        # (23:30 for a 00:10 event) is the only cross-midnight case and is kept by `on` below
        out |= on & hit
    return out
