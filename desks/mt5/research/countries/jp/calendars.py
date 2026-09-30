"""JAPAN'S CLOCKS: the TSE session and holidays, the TDnet windows, BoJ meetings, the Tankan.

REBUILT IN GIT beside `countries/jp/pack.py` for the reason `mandate.py` states: the department's
own `research/japan/calendars.py` was never committed, and a rebuild at that path would overwrite
the box's untracked copy on its next adoption. `market_constitution._holiday_sets` asks for the
box's module first and this one second.

WHAT IS COMPUTED AND WHAT IS NOT, because a wrong date is worse than a missing one
(`libs/research/event_calendar`'s rule). TSE holidays are STRUCTURAL: the Act on National Holidays
fixes every one by date or by weekday rule, the equinoxes follow the standard astronomical
approximation the Cabinet Office's own announcements match for 1980-2099, and the exchange adds
31 December and 1-3 January. Those are computed. The BoJ's meeting DAYS and the December Tankan
day are chosen by the Bank each year and published in advance; nothing here derives them. They
load from `data/calendars/boj_mpm.json` (`{"<year>": ["YYYY-MM-DD", ...]}`) when the operator has
written the Bank's published schedule there, and are UNMEASURED otherwise -- with the months,
which ARE fixed by practice, still available.
"""
from __future__ import annotations

import json
from datetime import date, time, timedelta
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[3]
BOJ_SCHEDULE = BASE / "data" / "calendars" / "boj_mpm.json"
UNMEASURED = "UNMEASURED"

#: TSE cash-equity sessions, JST. The afternoon close moved from 15:00 to 15:30 on 2024-11-05.
TSE_SESSIONS: tuple[tuple[time, time], ...] = ((time(9, 0), time(11, 30)),
                                               (time(12, 30), time(15, 30)))
TSE_CLOSE_BEFORE_2024_11_05 = time(15, 0)
#: When TDnet timely disclosures actually land, JST. Most issuers release AFTER the close; the
#: lunch break carries the intraday ones. A window, not a rule: TDnet accepts filings all day.
TDNET_WINDOWS: tuple[dict[str, Any], ...] = (
    {"window": "lunch", "start": "11:30", "end": "12:30",
     "note": "intraday releases timed for the lunch break"},
    {"window": "after_close", "start": "15:00", "end": "18:00",
     "note": "the bulk of earnings (決算短信) and guidance revisions (業績予想の修正)"},
    {"window": "evening", "start": "18:00", "end": "21:00",
     "note": "late filings; priced at the next morning's open and in USDJPY overnight"},
)
#: The BoJ holds eight Monetary Policy Meetings a year in these months (practice since 2016).
BOJ_MEETING_MONTHS: tuple[int, ...] = (1, 3, 4, 6, 7, 9, 10, 12)
#: The Tankan is released at 08:50 JST early in April, July and October and in mid-December.
TANKAN_MONTHS: tuple[int, ...] = (4, 7, 10, 12)


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    d = date(year, month, 1)
    d += timedelta(days=(weekday - d.weekday()) % 7)
    return d + timedelta(weeks=n - 1)


def _equinoxes(year: int) -> tuple[date, date]:
    k = year - 1980
    spring = int(20.8431 + 0.242194 * k - int(k / 4))
    autumn = int(23.2488 + 0.242194 * k - int(k / 4))
    return date(year, 3, spring), date(year, 9, autumn)


def national_holidays(year: int) -> list[date]:
    """Japan's national holidays for `year` (valid 2020-2099), with substitute and citizens' days."""
    spring, autumn = _equinoxes(year)
    base = {
        date(year, 1, 1), _nth_weekday(year, 1, 0, 2), date(year, 2, 11), date(year, 2, 23),
        spring, date(year, 4, 29), date(year, 5, 3), date(year, 5, 4), date(year, 5, 5),
        _nth_weekday(year, 7, 0, 3), date(year, 8, 11), _nth_weekday(year, 9, 0, 3), autumn,
        _nth_weekday(year, 10, 0, 2), date(year, 11, 3), date(year, 11, 23),
    }
    days = set(base)
    # 国民の休日: a weekday sandwiched between two holidays is itself a holiday.
    for d in sorted(base):
        mid = d + timedelta(days=1)
        if (mid + timedelta(days=1)) in base and mid not in base and mid.weekday() != 6:
            days.add(mid)
    # 振替休日: a holiday on Sunday moves to the next day that is not already a holiday.
    for d in sorted(base):
        if d.weekday() == 6:
            nxt = d + timedelta(days=1)
            while nxt in days:
                nxt += timedelta(days=1)
            days.add(nxt)
    return sorted(days)


def exchange_holidays(year: int) -> list[date]:
    """TSE non-trading weekdays: national holidays plus 31 Dec and 1-3 Jan. Weekends excluded."""
    days = set(national_holidays(year))
    days |= {date(year, 1, 1), date(year, 1, 2), date(year, 1, 3), date(year, 12, 31)}
    return sorted(d for d in days if d.weekday() < 5)


def is_trading_day(d: date) -> bool:
    return d.weekday() < 5 and d not in set(exchange_holidays(d.year))


def trading_days(start: date, end: date) -> list[date]:
    hol = {h for y in range(start.year, end.year + 1) for h in exchange_holidays(y)}
    out, d = [], start
    while d <= end:
        if d.weekday() < 5 and d not in hol:
            out.append(d)
        d += timedelta(days=1)
    return out


def gotobi_days(year: int, month: int) -> list[date]:
    """五十日: the 5th, 10th, 15th, 20th, 25th and month-end settlement days, rolled BACK to the
    previous TSE trading day when they fall on a holiday or weekend (the Tokyo fix convention)."""
    import calendar
    last = calendar.monthrange(year, month)[1]
    out: list[date] = []
    for dd in (5, 10, 15, 20, 25, last):
        d = date(year, month, dd)
        while not is_trading_day(d):
            d -= timedelta(days=1)
        if d not in out:
            out.append(d)
    return out


def boj_meetings(year: int) -> dict[str, Any]:
    """The BoJ's published meeting dates for `year`, or UNMEASURED with the months it will use."""
    try:
        doc = json.loads(BOJ_SCHEDULE.read_text(encoding="utf-8"))
        days = [date.fromisoformat(str(x)) for x in (doc.get(str(year)) or [])]
    except (OSError, ValueError, AttributeError):
        days = []
    if days:
        return {"status": "MEASURED", "dates": sorted(days), "source": str(BOJ_SCHEDULE.name)}
    return {"status": UNMEASURED, "dates": [], "months": list(BOJ_MEETING_MONTHS),
            "why": (f"the Bank publishes its meeting days in advance; write them to "
                    f"{BOJ_SCHEDULE.relative_to(BASE)} -- they are never derived here")}


def tankan_releases(year: int) -> list[dict[str, Any]]:
    """April/July/October: the first TSE trading day of the month (the observed practice),
    flagged as an ESTIMATE; December is mid-month and UNMEASURED without the Bank's schedule."""
    out: list[dict[str, Any]] = []
    for m in TANKAN_MONTHS:
        if m == 12:
            out.append({"month": m, "date": None, "status": UNMEASURED,
                        "why": "mid-December, day chosen by the Bank"})
            continue
        d = date(year, m, 1)
        while not is_trading_day(d):
            d += timedelta(days=1)
        out.append({"month": m, "date": d, "status": "ESTIMATE", "time_jst": "08:50"})
    return out
