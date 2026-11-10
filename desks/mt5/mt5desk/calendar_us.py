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

__all__ = ["Release", "us_eastern_offset", "releases", "blackout", "TIER1",
           "FIXED_SOURCES", "UNDATED"]

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


#: Employment Situation dates BLS moved off the first Friday. 2026-07-03 is the observed
#: Independence Day holiday, so June's report came on Thursday 07-02. OTHER rule exceptions
#: (a first Friday on the 1st-2nd that BLS pushes a week, a shutdown delay) are NOT derived:
#: until this table is checked against the BLS schedule for every armed year it is a
#: PRE-ARM BLOCKER of the news fence (patch e8_news_fence/v2 README).
NFP_MOVED: dict[tuple[int, int], tuple[int, int]] = {
    (2026, 7): (7, 2),
}

#: Dates that follow no rule. Sourced from the official Fed/BLS/BEA schedules;
#: a year absent from this table is a REFUSAL, not an empty blackout list.
FIXED: dict[int, tuple[tuple[str, int, int, int, int], ...]] = {
    2026: (
        ("FOMC_MINUTES", 8, 19, 14, 0),     # July 28-29 minutes, 14:00 ET
        ("GDP", 8, 26, 8, 30),              # Q2 second estimate
        ("PCE", 8, 26, 8, 30),              # July personal income & outlays
        # 2026 REMAINDER, read from the official pages on 2026-11-10 (the box fetched them;
        # page hashes in FIXED_SOURCES). Dates are the pages'. Times: BEA prints 8:30 AM on
        # its schedule; FRED's release calendar gives BLS dates with no time, so CPI and PPI
        # carry BLS's standing 08:30 ET; the Fed page gives no statement time, so FOMC
        # carries the standing 14:00 ET. September and October are NOT back-filled: nothing
        # official for them was read, and a past month stays a published gap.
        ("CPI", 11, 10, 8, 30),             # FRED release 10
        ("PPI", 11, 13, 8, 30),             # FRED release 46
        ("GDP", 11, 25, 8, 30),             # BEA: Q3 second estimate
        ("PCE", 11, 25, 8, 30),             # BEA: October personal income & outlays
        ("FOMC", 12, 9, 14, 0),             # Fed: December 8-9 meeting, statement day two
        ("CPI", 12, 10, 8, 30),             # FRED release 10
        ("PPI", 12, 15, 8, 30),             # FRED release 46
        ("GDP", 12, 23, 8, 30),             # BEA: Q3 third estimate
        ("PCE", 12, 23, 8, 30),             # BEA: November personal income & outlays
    ),
    # NO 2027 ROW ON PURPOSE. The Fed has published tentative 2027 meeting dates, but no
    # CPI, PPI, PCE, GDP or minutes date for 2027 exists on any official page yet. A 2027
    # entry holding FOMC alone would stop `releases` refusing the year while the fence saw
    # one family in seven. The year stays a refusal until the monthly families are dated.
}

#: Tier-1 releases known to be coming whose date no official page gives yet: (family, year,
#: month, why). The fence publishes each as a named gap for that month (never a quiet month)
#: until a FIXED row for that family lands in that month, which clears it by itself.
UNDATED: tuple[tuple[str, int, int, str], ...] = (
    ("FOMC_MINUTES", 2026, 11,
     "minutes of the October 27-28 meeting: the Fed page had no release link on 2026-11-10 "
     "(usually three weeks after the meeting)"),
)

#: Where each batch of FIXED rows was read, so the table can be re-checked against the page.
FIXED_SOURCES: dict[str, dict[str, str]] = {
    "2026-11..12": {
        "read_utc": "2026-11-10T16:01Z",
        "fed": "federalreserve.gov/monetarypolicy/fomccalendars.htm sha256 "
               "7d268c691661ac7bc1ae2c89f72e207a689f09d31852b95f8ab499bc2604257a",
        "bea": "bea.gov/news/schedule sha256 "
               "df1e8ef61e53e7e3ecca101b9895a63b0a71c57e1a824c8ffb95acc0124100cd",
        "bls": "FRED release/dates ids 10 (CPI), 46 (PPI), 50 (Employment Situation); the "
               "BLS schedule pages refused the fetch and were not retried",
    },
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
            # Employment Situation: first Friday, 08:30 ET -- unless BLS moved it (a federal
            # holiday on that Friday), which the rule cannot know: NFP_MOVED wins.
            mv = NFP_MOVED.get((y, m))
            d_nfp = date(y, mv[0], mv[1]) if mv else _first_weekday(y, m, 4)
            out.append(Release(_et(d_nfp, 8, 30), "NFP"))
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
