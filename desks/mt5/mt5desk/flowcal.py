"""Calendar-driven institutional flow: who is compelled to trade, and when.

WHY A CALENDAR IS A MECHANISM AND A PRICE PATTERN IS NOT

Every surviving edge on this desk is `asia`-session, on JPY crosses and gold. The only mechanism
ever proposed for that -- prior-NY displacement state -- was measured on 2026-08-17 and does not
discriminate: corrected for its lookahead, the four states pay +0.191 / +0.256 / +0.210 / +0.158 R
against an unconditional base of +0.212R. A flat line. So the desk currently trades a statistical
regularity whose cause it cannot name, and an unnamed cause cannot be reasoned about when it stops
working.

This module supplies the candidate causes that are FREE, because they are calendars rather than
data: dates on which somebody is obliged to transact regardless of price.

    TOKYO FIX (09:55 JST). Japanese corporates settle FX at a published benchmark. The
    counterparty is a bank that must hedge into the print. That is a compelled flow with a
    timestamp, and it sits inside the asia window this desk trades.

    GOTOBI. Japanese settlement concentrates on dates ending in 5 or 0 (go=5, to=10), so fixing
    demand is systematically LARGER on those days. A pure calendar rule with no data dependency.

    MONTH / QUARTER END. Passive mandates and index funds rebalance currency hedges into the
    close. Among the most documented flow effects in FX, and this desk has no code for it.

THE POINT IS FALSIFICATION, NOT FEATURES. `japan_holiday` exists so the Tokyo-fix hypothesis can
be KILLED: on a Japanese public holiday the fix does not happen, so if the asia edge is
fixing-driven it must weaken measurably on those days, and if it is identical then the fix is not
the mechanism and the story is something else. A conditioning variable that can only confirm is
worthless; this one is chosen because it can refute.

NO NETWORK, NO LICENCE, NO DATA FILE. Holidays are legislated years in advance and settlement
conventions do not move, so everything here is deterministic and reproducible on any box.
"""

from __future__ import annotations

import datetime as _dt
from functools import lru_cache

#: Japanese public holidays, 2018-2026. Sourced from the Cabinet Office's published calendar,
#: including the Happy-Monday moved holidays, the 2019 Reiwa accession dates and the 2020/2021
#: Olympic reschedules -- those are exactly the years a naive rule-based generator gets wrong,
#: and a wrong holiday here would silently move days between the test and control groups.
#: Substitute holidays (furikae kyujitsu, when a holiday falls on Sunday) are included.
_JP_HOLIDAYS: frozenset[_dt.date] = frozenset(_dt.date(*d) for d in [
    # 2018
    (2018,1,1),(2018,1,8),(2018,2,12),(2018,3,21),(2018,4,30),(2018,5,3),(2018,5,4),(2018,5,5),
    (2018,7,16),(2018,8,11),(2018,9,17),(2018,9,24),(2018,10,8),(2018,11,3),(2018,11,23),
    (2018,12,24),
    # 2019 -- Reiwa accession: 27 Apr - 6 May was a 10-day national holiday
    (2019,1,1),(2019,1,14),(2019,2,11),(2019,3,21),(2019,4,29),(2019,4,30),(2019,5,1),(2019,5,2),
    (2019,5,3),(2019,5,4),(2019,5,6),(2019,7,15),(2019,8,12),(2019,9,16),(2019,9,23),(2019,10,14),
    (2019,10,22),(2019,11,4),(2019,11,23),
    # 2020 -- Olympic-year moves (Marine Day, Mountain Day, Sports Day shifted)
    (2020,1,1),(2020,1,13),(2020,2,11),(2020,2,24),(2020,3,20),(2020,4,29),(2020,5,4),(2020,5,5),
    (2020,5,6),(2020,7,23),(2020,7,24),(2020,8,10),(2020,9,21),(2020,9,22),(2020,11,3),
    (2020,11,23),
    # 2021 -- Olympics again moved Marine/Mountain/Sports Day
    (2021,1,1),(2021,1,11),(2021,2,11),(2021,2,23),(2021,3,20),(2021,4,29),(2021,5,3),(2021,5,4),
    (2021,5,5),(2021,7,22),(2021,7,23),(2021,8,9),(2021,9,20),(2021,9,23),(2021,11,3),
    (2021,11,23),
    # 2022
    (2022,1,1),(2022,1,10),(2022,2,11),(2022,2,23),(2022,3,21),(2022,4,29),(2022,5,3),(2022,5,4),
    (2022,5,5),(2022,7,18),(2022,8,11),(2022,9,19),(2022,9,23),(2022,10,10),(2022,11,3),
    (2022,11,23),
    # 2023
    (2023,1,1),(2023,1,2),(2023,1,9),(2023,2,11),(2023,2,23),(2023,3,21),(2023,4,29),(2023,5,3),
    (2023,5,4),(2023,5,5),(2023,7,17),(2023,8,11),(2023,9,18),(2023,9,23),(2023,10,9),
    (2023,11,3),(2023,11,23),
    # 2024
    (2024,1,1),(2024,1,8),(2024,2,11),(2024,2,12),(2024,2,23),(2024,3,20),(2024,4,29),(2024,5,3),
    (2024,5,4),(2024,5,5),(2024,5,6),(2024,7,15),(2024,8,11),(2024,8,12),(2024,9,16),(2024,9,22),
    (2024,9,23),(2024,10,14),(2024,11,3),(2024,11,4),(2024,11,23),
    # 2025
    (2025,1,1),(2025,1,13),(2025,2,11),(2025,2,23),(2025,2,24),(2025,3,20),(2025,4,29),(2025,5,3),
    (2025,5,4),(2025,5,5),(2025,5,6),(2025,7,21),(2025,8,11),(2025,9,15),(2025,9,23),
    (2025,10,13),(2025,11,3),(2025,11,23),(2025,11,24),
    # 2026
    (2026,1,1),(2026,1,12),(2026,2,11),(2026,2,23),(2026,3,20),(2026,4,29),(2026,5,3),(2026,5,4),
    (2026,5,5),(2026,5,6),(2026,7,20),(2026,8,11),(2026,9,21),(2026,9,22),(2026,9,23),
    (2026,10,12),(2026,11,3),(2026,11,23),
])


def japan_holiday(d: _dt.date) -> bool:
    """Is `d` a Japanese public holiday? Tokyo banks shut, so THE FIX DOES NOT HAPPEN.

    The falsification lever. If the asia-session edge is driven by Tokyo fixing flow it must be
    measurably weaker on these days; if it is unchanged, the fix is not the mechanism.
    """
    return _to_date(d) in _JP_HOLIDAYS


def japan_business_day(d: _dt.date) -> bool:
    """Tokyo settlement day: a weekday that is not a public holiday."""
    dd = _to_date(d)
    return dd.weekday() < 5 and dd not in _JP_HOLIDAYS


def gotobi(d: _dt.date) -> bool:
    """A Japanese settlement-concentration day: date ends in 5 or 0.

    `go` (5) and `to` (10). Corporate payment terms cluster on these dates, so demand at the
    09:55 JST fix is systematically larger. Month-end is included by convention because the last
    business day carries settlement regardless of its number.
    """
    dd = _to_date(d)
    return dd.day % 5 == 0 or is_month_end(dd)


def effective_gotobi(d: _dt.date) -> bool:
    """Gotobi flow ACTUALLY lands on the nearest prior Tokyo business day.

    A settlement dated to a Sunday does not create a fix that Sunday -- the flow is brought
    forward to the last business day before it. Testing the raw calendar date instead would put
    roughly a third of gotobi flow in the wrong bucket and blur the very effect being measured.
    """
    dd = _to_date(d)
    if not japan_business_day(dd):
        return False
    probe, seen = dd, 0
    while seen < 5:
        if gotobi(probe):
            return True
        probe -= _dt.timedelta(days=1)
        seen += 1
        if japan_business_day(probe):      # an earlier business day owns any flow before it
            break
    return False


def is_month_end(d: _dt.date) -> bool:
    """Last calendar day of the month."""
    dd = _to_date(d)
    nxt = dd + _dt.timedelta(days=1)
    return nxt.month != dd.month


def is_quarter_end(d: _dt.date) -> bool:
    dd = _to_date(d)
    return is_month_end(dd) and dd.month in (3, 6, 9, 12)


def month_end_window(d: _dt.date, days: int = 2) -> bool:
    """Within `days` business days of month end -- when hedge rebalancing actually trades.

    Rebalancing is executed INTO the month-end print, not on it, so a same-day-only test would
    miss most of the flow it is looking for.
    """
    dd = _to_date(d)
    probe, n = dd, 0
    while n <= days:
        if is_month_end(probe):
            return True
        probe += _dt.timedelta(days=1)
        if probe.weekday() < 5:
            n += 1
    return False


def flow_state(d: _dt.date) -> str:
    """One label per day, for conditioning a sweep the way `day_states` is used.

    Ordered by how specific the claim is, because a day can be several of these at once and a
    cell must belong to exactly one bucket or the groups overlap and the statistics are wrong.
    """
    dd = _to_date(d)
    if japan_holiday(dd):
        return "JP_HOLIDAY"
    if is_quarter_end(dd) or (is_month_end(dd) and japan_business_day(dd)):
        return "PERIOD_END"
    if month_end_window(dd):
        return "MONTH_END_WINDOW"
    if effective_gotobi(dd):
        return "GOTOBI"
    if japan_business_day(dd):
        return "TOKYO_NORMAL"
    return "TOKYO_CLOSED"


FLOW_STATES = ("JP_HOLIDAY", "PERIOD_END", "MONTH_END_WINDOW", "GOTOBI",
               "TOKYO_NORMAL", "TOKYO_CLOSED")


@lru_cache(maxsize=8192)
def _to_date(d) -> _dt.date:
    if isinstance(d, _dt.datetime):
        return d.date()
    if isinstance(d, _dt.date):
        return d
    return _dt.date.fromisoformat(str(d)[:10])
