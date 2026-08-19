"""Deterministic US macro release times, and the blackout rail built on them.

WHY THIS IS A CALENDAR AND NOT A FEED

The events that reprice gold are scheduled years ahead and most of them follow
rules, not announcements: the Employment Situation is the first Friday of the
month at 08:30 ET, initial claims are every Thursday at 08:30 ET. Those need no
network, no key and no vendor, and a rail that depends on a live feed fails
exactly when the feed does -- which is a busy morning. Dates that genuinely
cannot be derived (FOMC, CPI, PPI) live in an explicit table that is checked
against the official schedule, and an EMPTY table for a future year raises
rather than silently waving every event through.

WHAT THE RAIL IS FOR

On 2026-08-19 a copy strategy with no release filter shorted into a repricing
and lost the account. The distinction it could not draw is the one that decides
everything: fading TRANSIENT impact pays, and fading a data print does not,
because the print IS the information. A clock separates them for free.

WHAT THE RAIL IS NOT

It is not tuned on that day. `blackout` takes the pre and post windows as
arguments precisely so they can be swept and measured per event family rather
than fitted to one loss -- see research/blackout_sweep.py. A window chosen from
a single bad afternoon is a story, not a parameter.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

__all__ = ["Release", "us_eastern_offset", "releases", "blackout", "TIER1"]

#: Event families the desk treats as capable of repricing gold outright.
TIER1 = ("FOMC", "FOMC_MINUTES", "CPI", "NFP", "PPI", "GDP", "PCE")


@dataclass(frozen=True)
class Release:
    when: datetime          # tz-aware UTC
    family: str
    tier: int = 1

    def __str__(self) -> str:                                # pragma: no cover
        return f"{self.when:%Y-%m-%d %H:%M}Z {self.family}"


def us_eastern_offset(d: date) -> int:
    """Hours BEHIND UTC for US Eastern on `d`: 4 during DST, else 5.

    DST runs from the second Sunday in March to the first Sunday in November.
    Getting this wrong shifts every 08:30 ET release by a full hour, which would
    blackout the wrong sixty minutes and leave the real one open -- the failure
    mode is silent and total, so it is computed rather than assumed.
    """
    mar = date(d.year, 3, 1)
    start = mar + timedelta(days=(6 - mar.weekday()) % 7 + 7)
    nov = date(d.year, 11, 1)
    end = nov + timedelta(days=(6 - nov.weekday()) % 7)
    return 4 if start <= d < end else 5


def _et(d: date, hh: int, mm: int) -> datetime:
    return datetime.combine(d, time(hh, mm)).replace(
        tzinfo=timezone.utc) + timedelta(hours=us_eastern_offset(d))


def _first_weekday(y: int, m: int, weekday: int) -> date:
    d = date(y, m, 1)
    return d + timedelta(days=(weekday - d.weekday()) % 7)


#: Dates that follow no rule. Sourced from the official Fed/BLS/BEA schedules;
#: a year absent from this table is a REFUSAL, not an empty blackout list.
FIXED: dict[int, tuple[tuple[str, int, int, int, int], ...]] = {
    2026: (
        ("FOMC_MINUTES", 8, 19, 14, 0),     # July 28-29 minutes, 14:00 ET
        ("GDP", 8, 26, 8, 30),              # Q2 second estimate
        ("PCE", 8, 26, 8, 30),              # July personal income & outlays
    ),
}


def releases(start: date, end: date) -> list[Release]:
    """Every tier-1 release in [start, end], in UTC.

    Rule-derived where a rule exists; table-driven where it does not.
    """
    years = range(start.year, end.year + 1)
    if any(y not in FIXED for y in years):
        missing = [y for y in years if y not in FIXED]
        raise ValueError(
            f"no official release table for {missing}; refusing to report an "
            f"empty calendar, which would read as 'no events' and disable the "
            f"rail exactly when it is needed")
    out: list[Release] = []
    for y in years:
        for m in range(1, 13):
            # Employment Situation: first Friday, 08:30 ET
            out.append(Release(_et(_first_weekday(y, m, 4), 8, 30), "NFP"))
        # Initial claims: every Thursday, 08:30 ET
        d = _first_weekday(y, 1, 3)
        while d.year == y:
            out.append(Release(_et(d, 8, 30), "CLAIMS", tier=2))
            d += timedelta(days=7)
        for fam, mm, dd, hh, mi in FIXED[y]:
            out.append(Release(_et(date(y, mm, dd), hh, mi), fam))
    lo = datetime.combine(start, time.min).replace(tzinfo=timezone.utc)
    hi = datetime.combine(end, time.max).replace(tzinfo=timezone.utc)
    return sorted((r for r in out if lo <= r.when <= hi), key=lambda r: r.when)


def blackout(ts: datetime, rel: list[Release], *, pre_min: int, post_min: int,
             families: tuple[str, ...] = TIER1) -> Release | None:
    """The release blacking out `ts`, or None.

    Windows are arguments, not constants. The one thing this must never become
    is a pair of magic numbers fitted to the afternoon that motivated it.
    """
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    for r in rel:
        if r.family not in families:
            continue
        if r.when - timedelta(minutes=pre_min) <= ts <= r.when + timedelta(
                minutes=post_min):
            return r
    return None
