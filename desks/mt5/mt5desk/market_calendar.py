"""US release and exchange calendars from the date alone: CFTC COT usability, NYSE/CME holidays.

WHY (Auditor MF3/SF1/SF2 on #845, 2026-11-13). The COT, expiry-gamma and strike-pin families
assumed every week is a normal week:

  COT. A report as of Tuesday D is released Friday D+3 at 15:30 ET, so it is usable from the
      Monday bar after it (D+6, 00:00 UTC). In a week holding a US federal holiday the CFTC
      releases on the next business day -- typically Monday 15:30 ET -- so the Monday 00:00 bar
      is BEFORE the data existed. Holiday weeks are therefore usable from D+8 (Wednesday 00:00
      UTC), which clears a Monday or a Tuesday release. In the three federal shutdowns the reports
      came out weeks late, on a catch-up schedule the in-tree files do not record: reports dated
      inside those windows are DROPPED (`cot_usable_at` returns None), never given a guessed date.
  Third Friday. When the third Friday is an exchange holiday (Good Friday; Juneteenth from 2022;
      Independence Day observed) the monthly equity option expires the Thursday before.
  COMEX gold options. Trading terminates on the 4th last business day of the month before the
      contract month; if that day is a Friday or the day before an exchange holiday, the prior
      business day.

Business days here skip weekends and `exchange_holidays` (the NYSE/CME full-day set), never
early closes. Everything is computed from the calendar date: no lookahead is possible.
"""
from __future__ import annotations

from datetime import date, timedelta
from functools import lru_cache

import pandas as pd

#: Normal week: Tuesday as-of + 3 days to the Friday release + 3 to the Monday bar after it.
COT_NORMAL_LAG_D = 6
#: Holiday week: the release slips to Monday (or Tuesday); Wednesday 00:00 UTC clears both.
COT_HOLIDAY_LAG_D = 8
#: Report dates (inclusive) whose release was delayed by a federal shutdown and caught up later.
COT_SHUTDOWN_WINDOWS: tuple[tuple[date, date], ...] = (
    (date(2013, 9, 24), date(2013, 11, 12)),
    (date(2018, 12, 18), date(2019, 3, 5)),
    (date(2025, 9, 30), date(2026, 1, 27)),
)


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    first = date(year, month, 1)
    return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    nxt = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    last = nxt - timedelta(days=1)
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def _observed(day: date) -> date:
    if day.weekday() == 5:
        return day - timedelta(days=1)
    if day.weekday() == 6:
        return day + timedelta(days=1)
    return day


def easter(year: int) -> date:
    """Gregorian Easter Sunday (anonymous algorithm)."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    m = (32 + 2 * e + 2 * i - h - k) % 7
    n = (a + 11 * h + 22 * m) // 451
    month = (h + m - 7 * n + 114) // 31
    day = (h + m - 7 * n + 114) % 31 + 1
    return date(year, month, day)


@lru_cache(maxsize=256)
def federal_holidays(year: int) -> frozenset[date]:
    """US federal holidays as observed (the days the CFTC is closed)."""
    days = {
        _observed(date(year, 1, 1)), _nth_weekday(year, 1, 0, 3), _nth_weekday(year, 2, 0, 3),
        _last_weekday(year, 5, 0), _observed(date(year, 7, 4)), _nth_weekday(year, 9, 0, 1),
        _nth_weekday(year, 10, 0, 2), _observed(date(year, 11, 11)),
        _nth_weekday(year, 11, 3, 4), _observed(date(year, 12, 25)),
    }
    if year >= 2021:
        days.add(_observed(date(year, 6, 19)))
    nxt_ny = _observed(date(year + 1, 1, 1))
    if nxt_ny.year == year:                       # New Year's Day observed on Dec 31
        days.add(nxt_ny)
    return frozenset(days)


@lru_cache(maxsize=256)
def exchange_holidays(year: int) -> frozenset[date]:
    """NYSE/CME full-day closures: New Year, MLK, Presidents, Good Friday, Memorial, Juneteenth
    (2022 on), Independence, Labor, Thanksgiving, Christmas -- observed."""
    days = {
        _observed(date(year, 1, 1)), _nth_weekday(year, 1, 0, 3), _nth_weekday(year, 2, 0, 3),
        easter(year) - timedelta(days=2), _last_weekday(year, 5, 0), _observed(date(year, 7, 4)),
        _nth_weekday(year, 9, 0, 1), _nth_weekday(year, 11, 3, 4), _observed(date(year, 12, 25)),
    }
    if year >= 2022:
        days.add(_observed(date(year, 6, 19)))
    days = {d for d in days if d.weekday() < 5 and d.year == year}
    return frozenset(days)


def is_business_day(day: date) -> bool:
    return day.weekday() < 5 and day not in exchange_holidays(day.year)


def add_business_days(day: date, n: int) -> date:
    step = 1 if n >= 0 else -1
    out = day
    for _ in range(abs(int(n))):
        out += timedelta(days=step)
        while not is_business_day(out):
            out += timedelta(days=step)
    return out


def monthly_option_expiry(year: int, month: int) -> date:
    """The third Friday, or the business day before it when it is an exchange holiday."""
    third = _nth_weekday(year, month, 4, 3)
    while not is_business_day(third):
        third -= timedelta(days=1)
    return third


def comex_gold_option_expiry(year: int, month: int) -> date:
    """COMEX gold (OG) options on the contract delivering in the month AFTER (year, month): the
    4th last business day of (year, month), moved back one business day if it is a Friday or
    the day before an exchange holiday."""
    nxt = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    last = nxt - timedelta(days=1)
    while not is_business_day(last):
        last -= timedelta(days=1)
    day = add_business_days(last, -3)              # the 4th last business day (last is the 1st)
    if day.weekday() == 4 or not is_business_day(day + timedelta(days=1)):
        day = add_business_days(day, -1)
    return day


def cot_usable_at(report_date: date | pd.Timestamp) -> pd.Timestamp | None:
    """The UTC instant a COT report as of `report_date` (a Tuesday) may first be read, or None
    for a report delayed by a federal shutdown (dropped, never guessed)."""
    ts = pd.Timestamp(report_date)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    ts = ts.tz_convert("UTC").normalize()
    d = ts.date()
    if any(lo <= d <= hi for lo, hi in COT_SHUTDOWN_WINDOWS):
        return None
    release = d + timedelta(days=3)
    week = {release - timedelta(days=k) for k in range(5)}       # Mon..Fri of the release week
    holiday = bool(week & (federal_holidays(release.year) | federal_holidays(d.year)))
    return ts + pd.Timedelta(days=COT_HOLIDAY_LAG_D if holiday else COT_NORMAL_LAG_D)


def cot_usable_index(report_dates: pd.Series | pd.DatetimeIndex) -> pd.DatetimeIndex:
    """`cot_usable_at` over many dates; NaT where a report is dropped or its date is missing."""
    out = []
    for v in pd.DatetimeIndex(pd.to_datetime(report_dates, utc=True, errors="coerce")):
        out.append(pd.NaT if pd.isna(v) else (cot_usable_at(v) or pd.NaT))
    return pd.DatetimeIndex(out, tz="UTC")
