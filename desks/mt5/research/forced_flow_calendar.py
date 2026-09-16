#!/usr/bin/env python3
"""FORCED-FLOW CALENDAR -- a DATED list of known forced participants, computed from RULES.

WHY A FORCED-FLOW FAMILY NEEDS A CALENDAR AND NOT A FEED (blueprint item 10)

A forced-flow claim has three parts and all three must be nameable in advance:

    1. a KNOWN FORCED PARTICIPANT  -- somebody who must transact regardless of price
    2. a KNOWN TIME WINDOW         -- fixed by a rule, a mandate or a contract, not by the tape
    3. an OBSERVABLE CONSTRAINT    -- why they cannot simply wait for a better price

If the desk cannot name all three before the window opens, what it has is a pattern, not a
mechanism. The whole point of this module is that every row below is derivable from a RULE
years ahead: the last business day of a month, the third Friday of a quarter, the Wednesday
of an inventory week. No network, no key, no vendor. A rail that depends on a live feed fails
exactly when the feed does, and `mt5desk/calendar_us.py` already made this argument for the
macro-release blackout -- this is the same doctrine applied to flow rather than to news.

WHAT IS RULE-DERIVED AND WHAT IS A TABLE, because the difference is the honesty

Everything here is computed except the central-bank meeting dates, which follow no rule at all
and therefore live in ONE table at the top (`CENTRAL_BANK_MEETINGS`), each labelled
`VERIFY_BANK`. A year absent from that table produces NO central_bank events and is reported in
the artifact's `unmeasured` block -- an empty list is a measurement, never a silent "no events"
(L1.28a). The US Treasury auction dates are a PATTERN rather than a rule and are labelled as
such in every row's `source_rule` (`VERIFY_SCHEDULE`).

TIME ZONES: LOCAL WALL CLOCK IN, UTC OUT, zoneinfo in between

Every window below is anchored to the LOCAL wall clock of the institution that sets it -- the
WMR fix is 16:00 in London, the FOMC statement is 14:00 in New York, the BoJ is noon in Tokyo --
and converted to UTC with `zoneinfo`. It is stored as UTC and nothing downstream has to guess.

THIS MATTERS BECAUSE THE UTC ANSWER MOVES TWICE A YEAR AND THE LOCAL ONE DOES NOT. The
month-end fix window is 15:00-16:30 London every day of the year; in UTC that is 14:00-15:30
from the last Sunday in March to the last Sunday in October and 15:00-16:30 for the rest of it.
The FOMC statement is 18:00 UTC in EDT and 19:00 UTC in EST.

The blueprint that commissioned this module quoted a single UTC figure per rule. Each one is
reproduced EXACTLY here in the season it belongs to: the fix window's "15:00-16:30 UTC" is the
GMT identity (London local == UTC in winter); the FOMC's 18:00 UTC, the ECB's 12:15 UTC, EIA's
14:30 UTC and WASDE's 16:00 UTC are the summer anchors; the BoE's 12:00 UTC is the winter one.
The BoJ's 03:00 UTC is right all year, because Japan keeps no summer time. Every row's
`source_rule` carries the quoted figure beside the local rule, so the two can never drift apart
unnoticed.

A hard-coded UTC constant would have been an hour wrong for half of every year, always in the
direction that puts the window on the wrong bars -- which for a forced-flow family is not a
rounding error, it is trading a different mechanism.

UNIVERSE MANDATE (2026-08-18 / 2026-09-06)

`instruments` names MT5/Fusion registry symbols only, read from
`desks/mt5/data/universe/universe.json`, and every one is filtered through
`research/universe_policy.may_hypothesise` -- so single-name equities can never appear here.
They are traded on news and earnings in the EVENT lane; this is a hypothesis-discovery source
and spending trial count on them raises the bar for every FX and metals cell. No
crypto-exchange-native venue is referenced anywhere in this file.

NO HAND-KEPT SYMBOL LISTS THAT THE REGISTRY CANNOT CONFIRM. Bundles are resolved by asset class
and by currency substring wherever a rule exists; the handful of venue->index mappings that no
rule can derive (S&P is US500/US30/NAS100/US2000) live in ONE table and are INTERSECTED with the
registry, so a symbol that is not on the broker's books is dropped rather than published.

WHAT THIS MODULE DOES NOT DO. It does not judge whether a window is tradeable, does not filter
on any expected effect, and does not rank. Which forced flows are worth trading is the
gauntlet's verdict, and a calendar that pre-filtered its own rows would be choosing the evidence
after seeing it.

CLI
    python forced_flow_calendar.py            # write the artifact, print counts by kind
    python forced_flow_calendar.py --dry-run  # print counts by kind, write nothing
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from collections import Counter
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

BASE = Path(__file__).resolve().parent.parent
UNIVERSE = BASE / "data" / "universe" / "universe.json"
CALENDAR = BASE / "data" / "forced_flow_calendar.json"

#: Bumped whenever a RULE changes, so an artifact on disk can be told apart from one written by
#: a different set of rules. A consumer comparing two calendars compares this first.
RULES_VERSION = "2026-09-16.1"

#: The two labels the blueprint requires on anything not derivable from a rule.
VERIFY_BANK = "verify against the bank's published calendar"
VERIFY_SCHEDULE = "pattern, verify against the published schedule"

MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY = 0, 1, 2, 3, 4

#: Every kind this module can emit. A consumer that filters on a kind not in here gets nothing,
#: and that is a typo, not an empty market -- `events()` refuses an unknown kind rather than
#: returning [] (L1.28a: absence must never read as a clean verdict).
KINDS = (
    "month_end", "quarter_end", "index_rebalance", "futures_roll", "option_expiry",
    "bond_auction", "central_bank", "fixing", "inventory", "usda", "holiday_liquidity",
)


# =============================================================================================
# THE ONE TABLE. Everything else in this file is computed; these dates follow no rule.
# =============================================================================================

#: Central-bank decision dates. Multi-day meetings are stored as (month, first_day, last_day)
#: and the EVENT is placed on the last day, which is when the decision is published; the span is
#: kept so the row can say which meeting it belongs to.
#:
#: `at` is the LOCAL wall clock of the bank's own announcement and `tz` the zone it is set in --
#: see the module docstring for why a UTC constant would be an hour wrong for half of each year.
#: `quoted_utc` records the figure the commissioning blueprint gave, and the season in which this
#: table reproduces it exactly, so the two can be reconciled without re-deriving anything.
#:
#: A YEAR ABSENT FROM `days` PRODUCES NO EVENTS FOR THAT BANK and is reported in the artifact's
#: `unmeasured` block. It is never quietly treated as a year with no meetings.
CENTRAL_BANK_MEETINGS: dict[str, dict[str, Any]] = {
    "FOMC": {
        "tz": "America/New_York",
        "at": (14, 0),
        "quoted_utc": "18:00 UTC (= 14:00 America/New_York in EDT; 19:00 UTC in EST)",
        "actor": "primary dealers and rates desks re-hedging the front end into the statement",
        "verify": VERIFY_BANK,
        "days": {2026: ((1, 27, 28), (3, 17, 18), (4, 28, 29), (6, 16, 17),
                        (7, 28, 29), (9, 15, 16), (10, 27, 28), (12, 8, 9))},
    },
    "ECB": {
        "tz": "Europe/Berlin",
        "at": (14, 15),
        "quoted_utc": "12:15 UTC (= 14:15 Europe/Berlin in CEST; 13:15 UTC in CET)",
        "actor": "euro-area bank treasuries and EUR rates market makers",
        "verify": VERIFY_BANK,
        "days": {2026: ((2, 5, 5), (3, 19, 19), (4, 30, 30), (6, 11, 11),
                        (7, 23, 23), (9, 10, 10), (10, 29, 29), (12, 17, 17))},
    },
    "BOE": {
        "tz": "Europe/London",
        "at": (12, 0),
        "quoted_utc": "12:00 UTC (= 12:00 Europe/London in GMT; 11:00 UTC in BST)",
        "actor": "gilt market makers and GBP rates desks",
        "verify": VERIFY_BANK,
        "days": {2026: ((2, 5, 5), (3, 19, 19), (4, 30, 30), (6, 18, 18),
                        (7, 30, 30), (9, 17, 17), (11, 5, 5), (12, 17, 17))},
    },
    "BOJ": {
        "tz": "Asia/Tokyo",
        "at": (12, 0),
        "quoted_utc": "03:00 UTC all year (Japan keeps no summer time)",
        "actor": "JGB dealers and JPY funding desks",
        "verify": VERIFY_BANK,
        "days": {2026: ((1, 22, 23), (3, 18, 19), (4, 27, 28), (6, 15, 16),
                        (7, 30, 31), (9, 17, 18), (10, 29, 30), (12, 17, 18))},
    },
}

#: Venue -> index symbols. No rule derives "the S&P 500 trades on this desk as US500", so this is
#: a declared mapping -- but it is INTERSECTED with the broker registry at resolution time, so a
#: symbol Fusion does not list is dropped rather than published as a tradeable instrument.
INDEX_VENUES: dict[str, tuple[str, ...]] = {
    "sp": ("US500", "US30", "NAS100", "US2000"),
    "ftse": ("UK100",),
    "stoxx": ("GER40", "FRA40", "EUSTX50", "E35", "NETH25"),
    "nikkei": ("JPN225",),
    "rates": ("UST05Y", "UST10Y", "USDX"),
    "gilt": ("UKGILT",),
}

#: The seven FX majors, as the WMR fix and the CME FX complex understand the term. Intersected
#: with the registry like everything else.
FX_MAJORS = ("EURUSD", "GBPUSD", "USDJPY", "USDCHF", "USDCAD", "AUDUSD", "NZDUSD")


# =============================================================================================
# The registry: which symbols exist, and which of them this lane may name
# =============================================================================================

@lru_cache(maxsize=1)
def _registry() -> dict[str, dict]:
    try:
        data = json.loads(UNIVERSE.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return {str(k).upper(): v for k, v in data.items() if isinstance(v, dict)}


@lru_cache(maxsize=1)
def _may_hypothesise() -> Any:
    """`universe_policy.may_hypothesise`, or a permissive stand-in when it cannot be imported.

    THE STAND-IN IS NOT A LOOPHOLE. The bundles below are built from asset classes and currency
    substrings that contain no single-name equity in the first place, so the policy call is a
    SECOND fence rather than the only one. If it is unreachable (this module is run from a
    directory where neither import spelling resolves) the calendar still refuses anything absent
    from the registry, which is where a share CFD would have to come from.
    """
    try:
        from research.universe_policy import may_hypothesise
    except ImportError:                              # pragma: no cover - import-context dependent
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            from universe_policy import may_hypothesise  # type: ignore[no-redef]
        except ImportError:
            return lambda _symbol: True
    return may_hypothesise


def _keep(symbols: Any) -> tuple[str, ...]:
    """Registry symbols, hypothesis lane only, de-duplicated and ordered."""
    allowed = _registry()
    policy = _may_hypothesise()
    out = [s for s in dict.fromkeys(str(x).upper() for x in symbols)
           if s in allowed and policy(s)]
    return tuple(out)


def _by_class(*classes: str) -> tuple[str, ...]:
    wanted = {c.strip().lower() for c in classes}
    return _keep(sorted(k for k, v in _registry().items()
                        if str(v.get("asset_class", "")).strip().lower() in wanted))


def _fx_with(currency: str) -> tuple[str, ...]:
    """Every FX pair (majors, crosses and exotics) carrying `currency` as a leg."""
    cur = currency.upper()
    return _keep(sorted(k for k, v in _registry().items()
                        if str(v.get("asset_class", "")).strip().lower().startswith("forex")
                        and cur in k))


def _venue(*names: str) -> tuple[str, ...]:
    out: list[str] = []
    for name in names:
        out.extend(INDEX_VENUES.get(name, ()))
    return _keep(out)


def _gold() -> tuple[str, ...]:
    return _keep(sorted(k for k in _registry() if k.startswith(("XAU", "XAG"))))


def _energy() -> tuple[str, ...]:
    return _by_class("Energy")


def _softs() -> tuple[str, ...]:
    return _by_class("Soft Commodity")


def _fx_all() -> tuple[str, ...]:
    return _by_class("Forex")


def _fx_majors() -> tuple[str, ...]:
    return _keep(FX_MAJORS)


# =============================================================================================
# Calendar arithmetic -- every rule in this file bottoms out in these
# =============================================================================================

def is_business_day(day: date) -> bool:
    """Monday-Friday. HOLIDAYS ARE DELIBERATELY NOT SUBTRACTED HERE.

    `libs/research/bar_span.is_out_of_calendar` -- the desk's ONE encoding of what a trading day
    is -- is weekend-only, and a second, richer definition living here would let the lake audit
    and this calendar disagree about which bar belongs to which day (L1.61: one encoding, many
    readers). Holidays are not ignored: they are emitted as their own `holiday_liquidity` rows,
    so a consumer that needs them can intersect the two rather than trust a hidden rule.
    """
    return day.weekday() < 5


def add_business_days(day: date, n: int) -> date:
    """`n` business days after `day` (negative walks backwards). n=0 returns `day` unchanged."""
    step = 1 if n >= 0 else -1
    out = day
    for _ in range(abs(int(n))):
        out += timedelta(days=step)
        while not is_business_day(out):
            out += timedelta(days=step)
    return out


def last_business_day(year: int, month: int) -> date:
    """The last Monday-Friday of the month -- the WMR fix's month-end, and a futures FND."""
    first_next = date(year + (month == 12), (month % 12) + 1, 1)
    day = first_next - timedelta(days=1)
    while not is_business_day(day):
        day -= timedelta(days=1)
    return day


def nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """The `n`th `weekday` of the month (n starts at 1). Third Friday is nth_weekday(y,m,4,3)."""
    first = date(year, month, 1)
    return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))


def last_weekday(year: int, month: int, weekday: int) -> date:
    """The last `weekday` of the month -- Russell's reconstitution Friday, a UK bank holiday."""
    first_next = date(year + (month == 12), (month % 12) + 1, 1)
    day = first_next - timedelta(days=1)
    return day - timedelta(days=(day.weekday() - weekday) % 7)


def easter(year: int) -> date:
    """Gregorian Easter Sunday (anonymous Gregorian computus).

    Good Friday is the only US and UK market holiday with no fixed date and no weekday rule, so
    it has to be computed; hard-coding it is the one thing that would make this table rot.
    """
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    ell = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * ell) // 451
    month, day = divmod(h + ell - 7 * m + 114, 31)
    return date(year, month, day + 1)


def _us_observed(day: date) -> date:
    """US federal/market observance: Saturday moves to Friday, Sunday moves to Monday."""
    if day.weekday() == 5:
        return day - timedelta(days=1)
    if day.weekday() == 6:
        return day + timedelta(days=1)
    return day


def us_market_holidays(year: int) -> dict[date, str]:
    """The ten NYSE full closures, every one computed from its rule."""
    good_friday = easter(year) - timedelta(days=2)
    return {
        _us_observed(date(year, 1, 1)): "New Year's Day",
        nth_weekday(year, 1, MONDAY, 3): "Martin Luther King Jr. Day",
        nth_weekday(year, 2, MONDAY, 3): "Presidents' Day",
        good_friday: "Good Friday",
        last_weekday(year, 5, MONDAY): "Memorial Day",
        _us_observed(date(year, 6, 19)): "Juneteenth",
        _us_observed(date(year, 7, 4)): "Independence Day",
        nth_weekday(year, 9, MONDAY, 1): "Labor Day",
        nth_weekday(year, 11, THURSDAY, 4): "Thanksgiving",
        _us_observed(date(year, 12, 25)): "Christmas Day",
    }


def _uk_substitute(day: date, taken: set[date]) -> date:
    """UK substitute day: a weekend holiday moves to the next free weekday."""
    out = day
    while out.weekday() >= 5 or out in taken:
        out += timedelta(days=1)
    return out


def uk_bank_holidays(year: int) -> dict[date, str]:
    """England and Wales bank holidays, by rule (the LSE's closure list)."""
    east = easter(year)
    out: dict[date, str] = {}
    taken: set[date] = set()
    for day, name in (
        (date(year, 1, 1), "New Year's Day"),
        (east - timedelta(days=2), "Good Friday"),
        (east + timedelta(days=1), "Easter Monday"),
        (nth_weekday(year, 5, MONDAY, 1), "Early May bank holiday"),
        (last_weekday(year, 5, MONDAY), "Spring bank holiday"),
        (last_weekday(year, 8, MONDAY), "Summer bank holiday"),
        (date(year, 12, 25), "Christmas Day"),
        (date(year, 12, 26), "Boxing Day"),
    ):
        moved = _uk_substitute(day, taken)
        taken.add(moved)
        out[moved] = name if moved == day else f"{name} (substitute day)"
    return out


def japan_golden_week(year: int) -> dict[date, str]:
    """Showa Day plus the three early-May holidays, with Japan's Sunday-substitute rule.

    The substitute (furikae kyujitsu) is the next day that is neither a Sunday nor already a
    holiday, which is why 2026's Sunday 3 May lands on Wednesday 6 May rather than on Monday.
    """
    fixed = [(date(year, 4, 29), "Showa Day"),
             (date(year, 5, 3), "Constitution Memorial Day"),
             (date(year, 5, 4), "Greenery Day"),
             (date(year, 5, 5), "Children's Day")]
    out: dict[date, str] = dict(fixed)
    base = {day for day, _ in fixed}
    for day, name in fixed:
        if day.weekday() != 6:
            continue
        sub = day + timedelta(days=1)
        while sub in base or sub.weekday() == 6:
            sub += timedelta(days=1)
        out[sub] = f"{name} (substitute holiday)"
    return out


# =============================================================================================
# Windows: local wall clock in, UTC out
# =============================================================================================

def local_utc(day: date, hh: int, mm: int, tz: str) -> datetime:
    """`hh:mm` local in `tz` on `day`, as a tz-aware UTC instant. The only clock conversion here.

    Every window in this file goes through this function, so there is exactly one place where a
    DST mistake could live -- and `test_forced_flow` pins it against a March and an October date
    in both London and New York.
    """
    return datetime.combine(day, time(hh, mm), tzinfo=ZoneInfo(tz)).astimezone(UTC)


def _around(day: date, hh: int, mm: int, tz: str, before: int, after: int
            ) -> tuple[datetime, datetime]:
    anchor = local_utc(day, hh, mm, tz)
    return anchor - timedelta(minutes=before), anchor + timedelta(minutes=after)


def _span(day_from: date, from_hm: tuple[int, int], day_to: date, to_hm: tuple[int, int],
          tz: str) -> tuple[datetime, datetime]:
    return (local_utc(day_from, from_hm[0], from_hm[1], tz),
            local_utc(day_to, to_hm[0], to_hm[1], tz))


# =============================================================================================
# The event
# =============================================================================================

@dataclass(frozen=True)
class Event:
    """One dated forced-flow window.

    `forced_actor` and `mechanism` are not decoration -- they are parts 1 and 3 of the claim the
    module docstring names, and a row that cannot fill them in is not a forced-flow event. A
    reader judging whether the family's mechanism gate can pass reads these two fields.
    """
    date: date
    kind: str
    name: str
    window_start_utc: datetime
    window_end_utc: datetime
    instruments: tuple[str, ...]
    forced_actor: str
    mechanism: str
    source_rule: str

    def to_json(self) -> dict[str, Any]:
        return {
            "date": self.date.isoformat(),
            "kind": self.kind,
            "name": self.name,
            "window_start_utc": self.window_start_utc.isoformat(),
            "window_end_utc": self.window_end_utc.isoformat(),
            "instruments": list(self.instruments),
            "forced_actor": self.forced_actor,
            "mechanism": self.mechanism,
            "source_rule": self.source_rule,
        }


def _event(day: date, kind: str, name: str, window: tuple[datetime, datetime],
           instruments: tuple[str, ...], actor: str, mechanism: str, rule: str) -> Event:
    return Event(date=day, kind=kind, name=name, window_start_utc=window[0],
                 window_end_utc=window[1], instruments=instruments, forced_actor=actor,
                 mechanism=mechanism, source_rule=rule)


# --------------------------------------------------------------------------- month / quarter end

#: The WMR/Refinitiv 4pm London fix. The window opens an hour before the fix and closes half an
#: hour after it -- 15:00-16:30 LONDON, which is the 15:00-16:30 UTC the blueprint quotes read in
#: GMT. The published month-end fix calculation window is itself an hour (15:00-16:00 London)
#: rather than the five minutes a normal day gets, so the -60 side is the fix, not padding.
WMR = ("Europe/London", 16, 0, 60, 30)

_WMR_ACTOR = ("index and pension funds whose mandate values their book at the WMR 4pm London "
              "fix, plus the banks that guaranteed them that price")
_WMR_MECH = ("A fund benchmarked to the fix must transact AT the fix or carry tracking error it "
             "is not permitted to carry, and the bank that sold the guaranteed rate must hedge "
             "into the same minutes. Neither can wait for a better price: the constraint is the "
             "benchmark, not the level.")


def _fix_window(day: date, before: int = WMR[3], after: int = WMR[4]
                ) -> tuple[datetime, datetime]:
    return _around(day, WMR[1], WMR[2], WMR[0], before, after)


def _month_end_events(year: int, month: int) -> list[Event]:
    day = last_business_day(year, month)
    fx = _keep(_fx_majors() + _fx_all() + _gold() + _venue("sp", "ftse", "stoxx", "nikkei"))
    rows = [_event(
        day, "month_end", f"month_end_fix_{year:04d}{month:02d}", _fix_window(day), fx,
        _WMR_ACTOR, _WMR_MECH,
        "last Monday-Friday of the month; WMR 16:00 Europe/London fix, window -60/+30 min "
        "= 15:00-16:30 London (= 14:00-15:30 UTC in BST, 15:00-16:30 UTC in GMT)")]
    if month in (3, 6, 9, 12):
        rows.append(_event(
            day, "quarter_end", f"quarter_end_fix_{year:04d}Q{(month - 1) // 3 + 1}",
            _fix_window(day, before=90, after=30), fx,
            _WMR_ACTOR + "; plus quarterly-mandate rebalancers and bank balance-sheet window "
            "dressing",
            _WMR_MECH + " At a quarter end the same constraint binds a strictly larger set of "
            "mandates, and bank balance sheets are reported on the date itself.",
            "last Monday-Friday of Mar/Jun/Sep/Dec; same WMR fix, window widened to -90/+30 min"))
    return rows


# ------------------------------------------------------------------------------ index rebalance

def _index_rebalance_events(year: int, month: int) -> list[Event]:
    rows: list[Event] = []
    actor = ("index-tracking funds, which must hold the new constituent weights from the "
             "effective open and are measured on tracking error against the close that sets them")
    mech = ("A tracker cannot trade a rebalance early without taking on the tracking error it "
            "exists to avoid, so it transacts in the closing auction of the effective date. The "
            "size is published in advance and the timing is not a choice.")
    if month in (3, 6, 9, 12):
        friday = nth_weekday(year, month, FRIDAY, 3)
        rows.append(_event(
            friday, "index_rebalance", f"sp_quarterly_{year:04d}{month:02d}",
            _around(friday, 16, 0, "America/New_York", 30, 15), _venue("sp"), actor, mech,
            "S&P quarterly share-count and index review: effective at the close of the third "
            "Friday of Mar/Jun/Sep/Dec; NYSE 16:00 America/New_York closing auction -30/+15 min"))
        rows.append(_event(
            friday, "index_rebalance", f"ftse_quarterly_{year:04d}{month:02d}",
            _around(friday, 16, 30, "Europe/London", 20, 10), _venue("ftse"), actor, mech,
            "FTSE quarterly review: effective at the close of the third Friday of "
            "Mar/Jun/Sep/Dec; LSE 16:30 Europe/London closing auction -20/+10 min"))
        rows.append(_event(
            friday, "index_rebalance", f"stoxx_quarterly_{year:04d}{month:02d}",
            _around(friday, 17, 30, "Europe/Berlin", 20, 10), _venue("stoxx"), actor, mech,
            "STOXX quarterly review: effective at the close of the third Friday of "
            "Mar/Jun/Sep/Dec; 17:30 Europe/Berlin closing auction -20/+10 min"))
    if month == 6:
        friday = last_weekday(year, 6, FRIDAY)
        rows.append(_event(
            friday, "index_rebalance", f"russell_reconstitution_{year:04d}",
            _around(friday, 16, 0, "America/New_York", 45, 15),
            _keep(_venue("sp") + _venue("rates")), actor,
            mech + " Reconstitution is the largest single forced print of the US year because "
            "the whole Russell family reconstitutes on one close.",
            "Russell annual reconstitution: effective at the close of the last Friday of June; "
            "NYSE 16:00 America/New_York closing auction -45/+15 min"))
    return rows


# --------------------------------------------------------------------------------- futures roll

def _futures_roll_events(year: int, month: int) -> list[Event]:
    rows: list[Event] = []
    if month in (3, 6, 9, 12):
        roll = nth_weekday(year, month, FRIDAY, 3) - timedelta(days=1)
        rows.append(_event(
            roll, "futures_roll", f"cme_equity_index_roll_{year:04d}{month:02d}",
            _span(roll, (8, 30), roll, (16, 0), "America/Chicago"), _venue("sp"),
            "anyone carrying a long-dated equity index futures position -- index replication "
            "funds, structured-product hedges, CTAs -- who must be out of the expiring contract",
            "The expiring contract cash-settles; a holder who wants the exposure to survive has "
            "to be in the next contract before it does. The date is set by the exchange, the "
            "direction of the roll is known, and the calendar spread is where it prints.",
            "CME equity index quarterly roll: the Thursday before the third Friday of "
            "Mar/Jun/Sep/Dec; 08:30-16:00 America/Chicago"))
        rows.append(_event(
            roll, "futures_roll", f"cme_fx_roll_{year:04d}{month:02d}",
            _span(roll, (7, 20), roll, (16, 0), "America/Chicago"), _fx_majors(),
            "holders of CME FX futures and of the OTC forwards banks hedge with them",
            "Same constraint as the equity index roll, transmitted into spot through the "
            "forward points the dealer has to re-strike.",
            "CME FX futures quarterly roll: the Thursday before the third Friday of "
            "Mar/Jun/Sep/Dec; 07:20-16:00 America/Chicago"))
    if month in (2, 4, 6, 8, 10, 12):
        # First notice day for a COMEX delivery month is the last business day of the month
        # BEFORE it; nobody who cannot take delivery may still be in the contract on FND.
        prior_year, prior_month = (year - 1, 12) if month == 1 else (year, month - 1)
        fnd = last_business_day(prior_year, prior_month)
        roll_end = add_business_days(fnd, -1)
        roll_start = add_business_days(fnd, -5)
        rows.append(_event(
            roll_end, "futures_roll", f"comex_gold_roll_{year:04d}{month:02d}",
            _span(roll_start, (8, 20), roll_end, (13, 30), "America/New_York"), _gold(),
            "every financial holder of the active COMEX gold contract -- ETFs, banks and funds "
            "that cannot take physical delivery of 100oz bars",
            "A holder who cannot take delivery MUST be out before first notice day or be "
            "assigned metal. The deadline is contractual and the exit is one-directional, so "
            "the active month drains into the next on a schedule known a year ahead.",
            f"COMEX gold active-month roll for the {year:04d}-{month:02d} delivery month: the "
            f"five business days ending the business day before first notice ({fnd.isoformat()}, "
            "the last business day of the prior month); 08:20-13:30 America/New_York"))
    target = date(year, month, 25)
    while not is_business_day(target):
        target -= timedelta(days=1)
    wti = add_business_days(target, -3)
    rows.append(_event(
        wti, "futures_roll", f"wti_expiry_{year:04d}{month:02d}",
        _around(wti, 14, 30, "America/New_York", 90, 30), _keep(_energy() + _fx_with("CAD")),
        "holders of the expiring NYMEX WTI contract who cannot take delivery at Cushing, and "
        "the index funds whose published roll schedule lands in the same days",
        "Physical delivery at a landlocked hub is not an option for a financial holder, so the "
        "exit is compulsory and its date is contractual. Commodity index funds publish their "
        "roll window in advance, which tells the rest of the market exactly when they must be "
        "there.",
        "NYMEX WTI: trading terminates three business days before the 25th calendar day of the "
        "month preceding delivery (or before the last business day preceding the 25th when that "
        "day is not a business day); 14:30 America/New_York -90/+30 min"))
    return rows


# --------------------------------------------------------------------------------- option expiry

def _option_expiry_events(year: int, month: int) -> list[Event]:
    friday = nth_weekday(year, month, FRIDAY, 3)
    quarterly = month in (3, 6, 9, 12)
    name = "quad_witching" if quarterly else "monthly_opex"
    window = (_span(friday, (9, 20), friday, (16, 15), "America/New_York") if quarterly
              else _around(friday, 16, 0, "America/New_York", 60, 15))
    instruments = _keep(_venue("sp") + (_fx_majors() + _gold() if quarterly else ()))
    return [_event(
        friday, "option_expiry", f"{name}_{year:04d}{month:02d}", window, instruments,
        "option market makers, who are short gamma into the expiry and must hedge the delta "
        "their book mechanically acquires as spot moves through the strikes",
        "A dealer's hedge is not a view. As expiry approaches, gamma concentrates at the large "
        "open-interest strikes and the hedge becomes larger and more price-insensitive the "
        "closer spot sits to them. The expiry date and the strike ladder are both published.",
        ("quarterly triple/quad witching: index futures, index options, single-stock options "
         "and single-stock futures all expire on the third Friday of Mar/Jun/Sep/Dec; "
         "09:20-16:15 America/New_York spans the AM and PM settlements")
        if quarterly else
        ("monthly equity option expiry: the third Friday of every month; PM settlement at the "
         "16:00 America/New_York close, window -60/+15 min"))]


# --------------------------------------------------------------------------------- bond auctions

def _bond_auction_events(year: int, month: int) -> list[Event]:
    if month not in (2, 5, 8, 11):
        return []
    rows: list[Event] = []
    second_week = [date(year, month, d) for d in range(8, 15)]
    actor = ("primary dealers, who are obliged to bid in every auction and then have to "
             "distribute or carry whatever they are left with")
    mech = ("A dealer's bid is a contractual obligation of its primary dealership, not a view, "
            "and the size is announced days ahead. The concession into the auction and the "
            "unwind after it are the price of a position nobody chose to hold.")
    for tenor, weekday, weekday_name in (("10y", WEDNESDAY, "Wednesday"),
                                         ("30y", THURSDAY, "Thursday")):
        day = next((d for d in second_week if d.weekday() == weekday), None)
        if day is None:                                          # pragma: no cover - 7-day week
            continue
        rows.append(_event(
            day, "bond_auction", f"ust_{tenor}_auction_{year:04d}{month:02d}",
            _around(day, 13, 0, "America/New_York", 30, 30),
            _keep(_venue("rates") + _gold() + _fx_majors()), actor, mech,
            f"US Treasury {tenor} refunding auction, 13:00 America/New_York: {VERIFY_SCHEDULE}. "
            f"The pattern encoded here is the {weekday_name} of the second week (calendar days "
            "8-14) of Feb/May/Aug/Nov"))
    return rows


# --------------------------------------------------------------------------------- central banks

def _central_bank_events(year: int) -> list[Event]:
    rows: list[Event] = []
    for bank, spec in CENTRAL_BANK_MEETINGS.items():
        table = spec["days"].get(year)
        if not table:
            continue                     # reported as `unmeasured`, never as "no meetings"
        hh, mm = spec["at"]
        tz = str(spec["tz"])
        for month, first_day, last_day in table:
            day = date(year, month, last_day)
            span = (f"{year:04d}-{month:02d}-{first_day:02d}" if first_day == last_day
                    else f"{year:04d}-{month:02d}-{first_day:02d}..{last_day:02d}")
            rows.append(_event(
                day, "central_bank", f"{bank.lower()}_{year:04d}{month:02d}{last_day:02d}",
                _around(day, hh, mm, tz, 30, 90),
                _instruments_for_bank(bank), str(spec["actor"]),
                "A policy decision repositions the whole front end of one curve at a published "
                "minute. The forced participants are the balance sheets that must re-hedge "
                "rate risk they are mandated to carry within limits, not the speculators who "
                "may choose to.",
                f"{bank} meeting {span}, decision published {hh:02d}:{mm:02d} {tz} "
                f"[{spec['quoted_utc']}]. Hard-coded date list -- {spec['verify']}"))
    return rows


def _instruments_for_bank(bank: str) -> tuple[str, ...]:
    if bank == "FOMC":
        return _keep(_fx_majors() + _fx_with("USD") + _gold() + _venue("sp", "rates"))
    if bank == "ECB":
        return _keep(_fx_with("EUR") + _venue("stoxx"))
    if bank == "BOE":
        return _keep(_fx_with("GBP") + _venue("ftse", "gilt"))
    return _keep(_fx_with("JPY") + _venue("nikkei"))


# --------------------------------------------------------------------------------------- fixings

def _fixing_events(day: date) -> list[Event]:
    if not is_business_day(day):
        return []
    return [
        _event(day, "fixing", f"wmr_1600_london_{day.isoformat()}", _fix_window(day, 15, 15),
               _keep(_fx_majors() + _fx_all() + _gold()), _WMR_ACTOR, _WMR_MECH,
               "daily WMR/Refinitiv fix, 16:00 Europe/London, window -15/+15 min "
               "(= 14:45-15:15 UTC in BST, 15:45-16:15 UTC in GMT)"),
        _event(day, "fixing", f"tokyo_0955_{day.isoformat()}",
               _around(day, 9, 55, "Asia/Tokyo", 10, 5),
               _keep(_fx_with("JPY") + _venue("nikkei")),
               "Japanese bank customers settling import and export invoices at the TTM rate "
               "their bank publishes that morning",
               "The TTM is struck once, at 09:55 Tokyo, and every corporate flow booked against "
               "it must be covered by then. Month-end and the 5th/10th ('gotobi') days "
               "concentrate the invoices; the hour does not move.",
               "Tokyo 09:55 Asia/Tokyo fix, window -10/+5 min (= 00:45-01:00 UTC all year; "
               "Japan keeps no summer time)"),
    ]


# ------------------------------------------------------------------------------------- inventory

def _inventory_events(day: date) -> list[Event]:
    energy = _keep(_energy() + _fx_with("CAD") + _fx_with("NOK"))
    if day.weekday() == WEDNESDAY:
        return [_event(
            day, "inventory", f"eia_crude_{day.isoformat()}",
            _around(day, 10, 30, "America/New_York", 15, 45), energy,
            "refiners, physical traders and index funds whose hedge ratio is set by a stock "
            "number they do not control",
            "The inventory print changes the physical balance a hedger's book is sized against, "
            "so the hedge has to be resized on the print. The release minute is statutory and "
            "the same every week.",
            "EIA Weekly Petroleum Status Report, Wednesday 10:30 America/New_York, window "
            "-15/+45 min (= 14:30 UTC in EDT, 15:30 UTC in EST)")]
    if day.weekday() == TUESDAY:
        return [_event(
            day, "inventory", f"api_crude_{day.isoformat()}",
            _around(day, 16, 30, "America/New_York", 15, 45), energy,
            "the same hedgers, positioning for the EIA print the next morning",
            "The API number is the only read on the same week's balance before the statutory "
            "one, so a book that must be flat into EIA is repositioned against it.",
            "API Weekly Statistical Bulletin, Tuesday 16:30 America/New_York, window -15/+45 "
            "min (= 20:30 UTC in EDT, 21:30 UTC in EST)")]
    return []


# ------------------------------------------------------------------------------------------ USDA

def _usda_events(year: int, month: int) -> list[Event]:
    day = date(year, month, 12)
    while not is_business_day(day):
        day += timedelta(days=1)
    return [_event(
        day, "usda", f"wasde_{year:04d}{month:02d}",
        _around(day, 12, 0, "America/New_York", 15, 45), _softs(),
        "grain merchandisers and elevators, whose basis book is marked against a balance sheet "
        "the USDA publishes and they cannot forecast away",
        "WASDE resets the supply and demand balance every hedge in the complex is sized "
        "against, at a minute announced a year ahead. A merchandiser carrying physical grain "
        "must re-hedge on the number, not on a view about it.",
        f"USDA WASDE, around the 12th of each month at 12:00 America/New_York (rolled forward "
        f"to the next business day when the 12th is a weekend): {VERIFY_SCHEDULE}. Window "
        "-15/+45 min (= 16:00 UTC in EDT, 17:00 UTC in EST)")]


# ------------------------------------------------------------------------------ holiday liquidity

def _holiday_events(year: int) -> list[Event]:
    rows: list[Event] = []
    regions = (
        ("us", us_market_holidays(year), _keep(_venue("sp", "rates") + _fx_with("USD") + _gold()),
         "the market makers who are absent, and the books that must still be hedged without them",
         "A closed venue does not remove the obligation to hedge -- it removes the other side. "
         "Depth is measurably thinner, the same order moves price further, and every desk knows "
         "the date a year ahead.",
         "US market holidays computed by rule (fixed dates observed Fri/Mon when they fall at a "
         "weekend; MLK/Presidents/Labor/Thanksgiving by weekday rule; Good Friday by computus)"),
        ("uk", uk_bank_holidays(year), _keep(_venue("ftse", "gilt") + _fx_with("GBP")),
         "London market makers, absent; GBP books still marked",
         "Same constraint as a US closure, on the venue that sets the WMR fix.",
         "England and Wales bank holidays by rule, with the substitute-day rule for weekends"),
        ("jp", japan_golden_week(year), _keep(_venue("nikkei") + _fx_with("JPY")),
         "Tokyo market makers, absent for a run of consecutive days",
         "Golden Week removes the Tokyo session for several days in a row, so JPY flow that "
         "would normally clear at the 09:55 fix has to clear somewhere else.",
         "Japan Golden Week by rule: Showa Day 29 Apr, Constitution Memorial Day 3 May, "
         "Greenery Day 4 May, Children's Day 5 May, plus the Sunday-substitute rule"),
    )
    for tag, table, instruments, actor, mech, rule in regions:
        for day, label in sorted(table.items()):
            rows.append(_event(
                day, "holiday_liquidity", f"{tag}_holiday_{day.isoformat()}",
                (datetime.combine(day, time(0, 0), tzinfo=UTC),
                 datetime.combine(day, time(23, 59, 59), tzinfo=UTC)),
                instruments, actor, mech, f"{label}: {rule}"))
    return rows


# =============================================================================================
# The public surface
# =============================================================================================

def events(start: date, end: date) -> list[Event]:
    """Every forced-flow window whose DATE falls in [start, end], sorted by window start.

    Pure: no network, no clock read, no file written. The same (start, end) always produces the
    same list on any machine, which is what lets a backtest and the live gateway agree about
    what a window was.
    """
    if end < start:
        return []
    out: list[Event] = []
    for year in range(start.year, end.year + 1):
        for month in range(1, 13):
            out.extend(_month_end_events(year, month))
            out.extend(_index_rebalance_events(year, month))
            out.extend(_futures_roll_events(year, month))
            out.extend(_option_expiry_events(year, month))
            out.extend(_bond_auction_events(year, month))
            out.extend(_usda_events(year, month))
        out.extend(_central_bank_events(year))
        out.extend(_holiday_events(year))
    day = start
    while day <= end:
        out.extend(_fixing_events(day))
        out.extend(_inventory_events(day))
        day += timedelta(days=1)
    inside = [e for e in out if start <= e.date <= end]
    return sorted(inside, key=lambda e: (e.window_start_utc, e.kind, e.name))


def by_kind(rows: list[Event]) -> dict[str, int]:
    """Counts per kind, with every declared kind present -- a zero is a measurement."""
    counted = Counter(e.kind for e in rows)
    return {k: int(counted.get(k, 0)) for k in KINDS}


def unmeasured_years(start: date, end: date) -> dict[str, list[int]]:
    """Which banks have no published table for which years in range.

    THIS IS THE POINT OF THE BLOCK, not bookkeeping. Without it a 2027 calendar would carry zero
    central-bank rows and read exactly like a year in which no central bank met.
    """
    out: dict[str, list[int]] = {}
    for bank, spec in CENTRAL_BANK_MEETINGS.items():
        missing = [y for y in range(start.year, end.year + 1) if y not in spec["days"]]
        if missing:
            out[bank] = missing
    return out


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, default=str)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        with suppress(FileNotFoundError):
            os.unlink(name)


def build(days_ahead: int = 120, days_back: int = 400,
          today: date | None = None) -> dict[str, Any]:
    """The artifact payload, without touching disk -- so a test can assert on it directly."""
    anchor = today or datetime.now(UTC).date()
    start, end = anchor - timedelta(days=days_back), anchor + timedelta(days=days_ahead)
    rows = events(start, end)
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "rules_version": RULES_VERSION,
        "range": {"start": start.isoformat(), "end": end.isoformat(),
                  "days_back": int(days_back), "days_ahead": int(days_ahead)},
        "n_events": len(rows),
        "by_kind": by_kind(rows),
        "unmeasured": {
            "central_bank_years": unmeasured_years(start, end),
            "note": ("a bank with no published table for a year contributes NO rows for it. "
                     "That is an absence of measurement, not a year without meetings"),
        },
        "events": [e.to_json() for e in rows],
    }


def write(path: Path | str = CALENDAR, days_ahead: int = 120, days_back: int = 400,
          today: date | None = None) -> dict[str, Any]:
    """Write the calendar artifact atomically and return the payload that was written."""
    payload = build(days_ahead=days_ahead, days_back=days_back, today=today)
    _atomic_json(Path(path), payload)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__ and __doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true",
                        help="compute and print counts by kind; write nothing")
    parser.add_argument("--path", default=str(CALENDAR), help="artifact path")
    parser.add_argument("--days-ahead", type=int, default=120)
    parser.add_argument("--days-back", type=int, default=400)
    args = parser.parse_args(argv)

    payload = (build(days_ahead=args.days_ahead, days_back=args.days_back) if args.dry_run
               else write(args.path, days_ahead=args.days_ahead, days_back=args.days_back))
    rng = payload["range"]
    print(f"forced_flow_calendar rules_version={payload['rules_version']} "
          f"range={rng['start']}..{rng['end']} n_events={payload['n_events']}")
    for kind, n in payload["by_kind"].items():
        print(f"  {kind:<20} {n:>6}")
    missing = payload["unmeasured"]["central_bank_years"]
    if missing:
        print(f"  UNMEASURED central-bank years: {missing}")
    print("  (dry run: nothing written)" if args.dry_run else f"  wrote {args.path}")
    return 0


if __name__ == "__main__":                                       # pragma: no cover - CLI
    raise SystemExit(main())
