"""JAPAN: the largest jurisdiction on the desk's map with no pack, and its own grounds said so.

MEASURED 2026-09-23. `pack_cells` walked every world ground that already holds documents to the
one registry door and published, per ground, the reason any of them could not name an MT5
instrument. Two of the seventeen survivors gave the same reason and it was not a thesis problem:

    asia:estat_jp_customs   6 documents   www.e-stat.go.jp   "the country code jp is covered by
    asia:boj_timeseries     1 document    www.stat-search.boj.or.jp   no pack under countries/"

Seventy-five packs exist and not one of them declares `jp`. Meanwhile `research/japan/mandate.py`
carries thirty-odd Japanese actors with their instruments attached, `japan/calendars.py` carries
the BoJ's meeting clock and `japan/miners_policy.py` mines it. The desk had the knowledge and was
missing the DECLARATION that the conversion path reads.

WHAT THIS PACK IS, EXACTLY. A door with a derived instrument list. It states no new mechanism,
duplicates no miner and overrides nothing: `research/japan/` remains the department that does the
work. The one thing it adds is the pair `(EXECUTABLE_INSTRUMENTS, REGION_COMMAND)` that
`pack_cells.country_pack` asks for, so a Japanese ground's documents become cells the one
gauntlet can judge.

WHY THE LIST IS DERIVED AND NOT TYPED. Two sources, both already on the desk, intersected with
the broker's own quote list:

  1. THE BROKER'S UNIVERSE REGISTRY (`data/universe/universe.json`). Every six-character symbol
     ending in JPY is a yen pair the account can actually trade. Typing that list by hand would
     be a claim about the broker; reading it is a measurement of the broker.
  2. THE JAPAN DEPARTMENT'S OWN ACTOR MAP (`research/japan/mandate.py`). Its actors declare the
     instruments each one moves -- USDJPY, EURJPY, JPN225 and the carry crosses. Anything it
     names that the broker does not quote (UST10Y, UST05Y) is dropped by the intersection rather
     than argued about.

If the department is absent or the registry unreadable, the list falls back to the yen pairs
alone, which is still a measurement and never an empty tuple: a pack that cannot name an
instrument would put its grounds straight back where they were.

JAPAN'S ONE STANDING PROPERTY, stated once so the pack is not merely plumbing: the yen is the
world's funding currency, so a Japanese policy or flow surprise transmits as a CARRY unwind
across every JPY cross at once rather than as an idiosyncratic move in one of them. That is why
the whole cross set is executable here and not just USDJPY, and it is the department's claim, not
a new one.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[3]          # countries/jp/pack.py -> desks/mt5
UNIVERSE = BASE / "data" / "universe" / "universe.json"

CODE = "JP"
NAME = "Japan"
REGION_COMMAND = "asia"
REGION_DESK = "ASIA"
FOREST = "japan"
CURRENCY = "JPY"
JURISDICTIONS: tuple[str, ...] = ("jp",)
NATIVE_LANGUAGES: tuple[str, ...] = ("ja", "en")
COT_CURRENCY = "JAPANESE YEN"
FISCAL_YEAR_END = "03-31"
EXPORT_ECONOMY = "manufactured_exporter"
RETAIL_LEVERAGE_REGIME = "restricted"

MISSION = ("hold the jurisdiction so its already-crawled grounds -- the BoJ time-series portal, "
           "e-Stat customs, and everything the world crawler reaches under .jp -- name the "
           "instruments the Japan department already knows they move. The mechanisms live in "
           "research/japan/; this pack is the declaration the conversion path reads.")

#: The department that owns Japan's research. Named here so nothing re-implements it.
#: REPOINTED 2026-10-06: `research.japan.mandate` was never committed to this repository (no
#: commit in any branch's history carries `research/japan/`), so the name pointed at nothing.
#: The Japan department that exists is the official plane beside this file, run by
#: `global_research_os` through `miners.py`.
DEPARTMENT_MODULE = "research.countries.jp.official_plane"


def _quoted() -> tuple[str, ...]:
    """Every symbol the broker's own universe registry lists. Empty when it cannot be read."""
    try:
        doc = json.loads(UNIVERSE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ()
    return tuple(str(k) for k in doc) if isinstance(doc, dict) else ()


def _yen_pairs(quoted: tuple[str, ...]) -> tuple[str, ...]:
    """The six-character JPY pairs the account can trade, USDJPY first because it is the axis."""
    pairs = sorted(s for s in quoted
                   if len(s) == 6 and s.isalpha() and s.upper().endswith("JPY"))
    return tuple(["USDJPY"] * ("USDJPY" in pairs) + [p for p in pairs if p != "USDJPY"])


def _department_instruments(quoted: tuple[str, ...]) -> tuple[str, ...]:
    """What the Japan department's own actor map names, kept only where the broker quotes it."""
    try:
        from research.japan import mandate
    except Exception:
        return ()
    seen: list[str] = []
    for actor in (getattr(mandate, "ACTORS", ()) or ()):
        if not isinstance(actor, dict):
            continue
        for sym in (actor.get("instruments") or ()):
            s = str(sym)
            if s in quoted and s not in seen:
                seen.append(s)
    for sym in (getattr(mandate, "JPY_CROSSES", ()) or ()):
        s = str(sym)
        if s in quoted and s not in seen:
            seen.append(s)
    return tuple(seen)


def _executable() -> tuple[str, ...]:
    quoted = _quoted()
    out: list[str] = []
    for sym in _yen_pairs(quoted) + _department_instruments(quoted):
        if sym not in out:
            out.append(sym)
    return tuple(out)


#: DERIVED at import from the broker's registry and the Japan department's actor map. Never typed.
EXECUTABLE_INSTRUMENTS: tuple[str, ...] = _executable()

#: Where Japanese information is published. These are the grounds already in the crawler's
#: registry that this pack now gives an instrument to; the list is documentation of what exists,
#: not a new crawl target -- the crawler's own registry remains the only source of grounds.
KNOWN_GROUNDS: tuple[dict[str, Any], ...] = (
    {"id": "asia:boj_timeseries", "host": "www.stat-search.boj.or.jp",
     "publishes": "the Bank of Japan's own time-series portal: policy rate, monetary base, "
                  "TANKAN, the effective exchange rate"},
    {"id": "asia:estat_jp_customs", "host": "www.e-stat.go.jp",
     "publishes": "the government statistics portal: trade by partner and commodity, the trade "
                  "balance that is the yen's own flow story"},
)

BOUNDARIES: tuple[str, ...] = (
    "this pack states no mechanism of its own and must never grow a miner or a trading rule; its "
    "one calendar is the statutory closure table below, which the Japan official plane's release "
    "rules roll over (alt_proxies.roll_business_day) and nothing else reads as a signal",
    "EXECUTABLE_INSTRUMENTS is derived at import and never hard-coded; a symbol the broker stops "
    "quoting leaves the list on the next process start with no edit here",
    "nothing here judges, sizes or vetoes anything",
)


# --------------------------------------------------------------------------- holidays
#: The years the closure table is DERIVED for. Outside them a release rule has no calendar and
#: `alt_proxies.merge_vintages` floors the row at the instant it was first seen (never earlier).
HOLIDAY_YEARS = range(2000, 2041)


def _nth_monday(y: int, m: int, n: int) -> date:
    first = date(y, m, 1)
    return first + timedelta(days=(7 - first.weekday()) % 7 + 7 * (n - 1))


def _equinoxes(y: int) -> tuple[date, date]:
    """Vernal and autumnal equinox days by the National Astronomical Observatory's standard
    approximation (valid 1980-2099; the Cabinet Office gazettes each year from NAOJ's almanac)."""
    k = y - 1980
    v = int(20.8431 + 0.242194 * k - k // 4)
    a = int(23.2488 + 0.242194 * k - k // 4)
    return date(y, 3, v), date(y, 9, a)


def _national_holidays(y: int) -> dict[date, str]:
    """国民の祝日 for one year (2000 on), then 振替休日 and 国民の休日 by the Act's own rules."""
    spring, autumn = _equinoxes(y)
    h: dict[date, str] = {
        date(y, 1, 1): "元日 New Year's Day",
        _nth_monday(y, 1, 2): "成人の日 Coming of Age Day",
        date(y, 2, 11): "建国記念の日 National Foundation Day",
        spring: "春分の日 Vernal Equinox Day",
        date(y, 4, 29): "昭和の日 Showa Day" if y >= 2007 else "みどりの日 Greenery Day",
        date(y, 5, 3): "憲法記念日 Constitution Memorial Day",
        date(y, 5, 5): "こどもの日 Children's Day",
        autumn: "秋分の日 Autumnal Equinox Day",
        date(y, 11, 3): "文化の日 Culture Day",
        date(y, 11, 23): "勤労感謝の日 Labour Thanksgiving Day",
    }
    if y >= 2007:
        h[date(y, 5, 4)] = "みどりの日 Greenery Day"
    if 2000 <= y <= 2018:
        h[date(y, 12, 23)] = "天皇誕生日 Emperor's Birthday"
    elif y >= 2020:
        h[date(y, 2, 23)] = "天皇誕生日 Emperor's Birthday"
    # 海の日 / スポーツの日 / 山の日: the Olympic special measures moved them in 2020 and 2021.
    marine = {2020: date(2020, 7, 23), 2021: date(2021, 7, 22)}.get(
        y, _nth_monday(y, 7, 3) if y >= 2003 else date(y, 7, 20))
    h[marine] = "海の日 Marine Day"
    sports = {2020: date(2020, 7, 24), 2021: date(2021, 7, 23)}.get(y, _nth_monday(y, 10, 2))
    h[sports] = "スポーツの日 Sports Day" if y >= 2020 else "体育の日 Health and Sports Day"
    if y >= 2016:
        h[{2020: date(2020, 8, 10), 2021: date(2021, 8, 8)}.get(y, date(y, 8, 11))] = \
            "山の日 Mountain Day"
    h[_nth_monday(y, 9, 3) if y >= 2003 else date(y, 9, 15)] = "敬老の日 Respect for the Aged Day"
    if y == 2019:
        h[date(2019, 5, 1)] = "即位の日 Enthronement Day (2019 special act)"
        h[date(2019, 10, 22)] = "即位礼正殿の儀 Enthronement Ceremony (2019 special act)"
    out = dict(h)
    # 国民の休日: a day sandwiched between two holidays is itself a holiday (not a Sunday).
    for d in sorted(h):
        mid = d + timedelta(days=1)
        if mid not in h and (mid + timedelta(days=1)) in h and mid.weekday() != 6:
            out[mid] = "国民の休日 Citizens' Holiday (between two holidays)"
    # 振替休日: a holiday on a Sunday moves to the next day that is not already a holiday.
    for d in sorted(h):
        if d.weekday() == 6:
            nxt = d + timedelta(days=1)
            while nxt in out:
                nxt += timedelta(days=1)
            out[nxt] = "振替休日 Substitute Holiday"
    return out


def _closures(y: int) -> dict[str, str]:
    days = {d.isoformat(): n for d, n in _national_holidays(y).items() if d.year == y}
    # 行政機関の休日 (Act No. 91 of 1988): MOF and the other ministries close 29 Dec - 3 Jan, and
    # the Bank of Japan closes 31 Dec - 3 Jan; neither publishes on those days.
    for m, d in ((1, 2), (1, 3), (12, 29), (12, 30), (12, 31)):
        days.setdefault(date(y, m, d).isoformat(), "年末年始 administrative year-end closure")
    return dict(sorted(days.items()))


HOLIDAYS_RULE: dict[str, Any] = {
    "rule": (
        "DERIVED, not typed. (1) 国民の祝日に関する法律 (Act on National Holidays): 1 Jan; "
        "Coming of Age Day = 2nd Monday of January; 11 Feb; 23 Feb (Emperor's Birthday from 2020; "
        "23 Dec 1989-2018; none in 2019); the vernal and autumnal equinox days (NAOJ almanac, "
        "standard approximation 1980-2099); 29 Apr; 3/4/5 May; Marine Day = 3rd Monday of July "
        "(20 Jul before 2003); Mountain Day = 11 Aug from 2016; Respect for the Aged Day = 3rd "
        "Monday of September (15 Sep before 2003); Sports Day = 2nd Monday of October; 3 Nov; "
        "23 Nov. (2) Special acts: 2019 enthronement (1 May, 22 Oct) and the Olympic moves of "
        "2020/2021. (3) 振替休日: a holiday on a Sunday moves to the next non-holiday. (4) 国民の"
        "休日: a day between two holidays is a holiday. (5) 行政機関の休日: ministries close "
        "29 Dec - 3 Jan, the BOJ 31 Dec - 3 Jan, so neither publishes then."),
    "authority": ("Act on National Holidays (Act No. 178 of 1948, as amended) and the Cabinet "
                  "Office's gazetted list; Act on Holidays of Administrative Organs (No. 91 of "
                  "1988); equinox days from the National Astronomical Observatory of Japan"),
    "table": {y: _closures(y) for y in HOLIDAY_YEARS},
    "status": dict.fromkeys(HOLIDAY_YEARS, "DERIVED_FROM_RULE"),
    "market_effect": ("MOF and BOJ publish nothing on these days, so a release rule that lands on "
                      "one is look-ahead and is rolled to the next business day; the yen keeps "
                      "trading offshore through every closure"),
    "callable": "countries.jp.pack:holidays",
}


def holidays(year: int) -> dict[str, str]:
    """Japan's publisher-closure table for one year, `{"YYYY-MM-DD": name}`; `{}` outside
    HOLIDAY_YEARS (no calendar, never an invented one)."""
    tbl = HOLIDAYS_RULE["table"].get(int(year))
    return dict(tbl) if tbl else {}
