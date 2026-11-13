"""THE SCHEDULED-EVENT CALENDAR, BUILT FROM THE PUBLISHERS' OWN PAGES.

`libs/execution/event_guard.py` refuses new entries inside a high-impact window and BLOCKS when
its calendar is absent, stale or empty. Until 2026-11-13 the calendar held hand-entered FOMC
dates only (scripts/build_event_calendar.py): bls.gov had answered 403 to the build host, so
CPI and payrolls were missing, and nothing refreshed it.

This module parses each official schedule page the box fetched (robots-gated, honest UA) and
writes the guard's schema. Release times are stated in the publisher's own zone and converted
to UTC with the IANA database, so no daylight-saving offset is ever typed by hand.

    publisher   page                                                     stamp (publisher zone)
    Fed         federalreserve.gov/monetarypolicy/fomccalendars.htm      14:00 America/New_York
    BLS         bls.gov/schedule/news_release/{cpi,empsit}.htm           the page's own time, ET
    BEA         bea.gov/news/schedule                                    the page's own time, ET
    ECB         ecb.europa.eu/press/calendars/mgcgc/html/index.en.html   14:15 Europe/Berlin
    BoE         bankofengland.co.uk/monetary-policy/upcoming-mpc-dates   12:00 Europe/London
    BoJ         boj.or.jp/en/mopo/mpmsche_minu/index.htm                 11:30-13:00 Asia/Tokyo *
    SNB         snb.ch/en/services-events/digital-services/event-schedule  the page's own time
    BoC         bankofcanada.ca/press/upcoming-events/                   the page's own time, ET

  * The BoJ publishes no fixed statement time: the decision is released when the meeting ends,
    usually late morning to early afternoon Tokyo time. It is therefore written as four stamps
    30 minutes apart, which with the guard's -30/+15 window covers 11:00-13:15 JST. A
    narrower window would be a guess.

WHAT A PARSER MAY NOT DO: invent a date. A page that no longer matches its parser yields no
events and a named `why`, and the publisher's coverage reads UNMEASURED. `valid_through` is the
earliest horizon among the CORE publishers (Fed, CPI, payrolls), so the calendar goes STALE,
and the guard blocks, before any of the three runs out.
"""
from __future__ import annotations

import html as _html
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

UTC = ZoneInfo("UTC")
ET = ZoneInfo("America/New_York")

#: The publisher pages, in the order a refresh fetches them.
PAGES: dict[str, str] = {
    "fed_fomc": "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm",
    "bls_cpi": "https://www.bls.gov/schedule/news_release/cpi.htm",
    "bls_empsit": "https://www.bls.gov/schedule/news_release/empsit.htm",
    "bea_schedule": "https://www.bea.gov/news/schedule",
    "ecb_mp_meetings": "https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html",
    "boe_mpc_dates": "https://www.bankofengland.co.uk/monetary-policy/upcoming-mpc-dates",
    "boj_mpm": "https://www.boj.or.jp/en/mopo/mpmsche_minu/index.htm",
    "snb_events": "https://www.snb.ch/en/services-events/digital-services/event-schedule",
    "boc_schedule": "https://www.bankofcanada.ca/press/upcoming-events/",
    "rba_schedule": "https://www.rba.gov.au/schedules-events/calendar/",
}
#: The publishers whose horizon bounds `valid_through`.
CORE = ("fed_fomc", "bls_cpi", "bls_empsit")

_MONTHS = {m: i for i, m in enumerate(
    ("january", "february", "march", "april", "may", "june", "july", "august", "september",
     "october", "november", "december"), start=1)}


def _month(word: str) -> int | None:
    w = word.strip().lower().rstrip(".")
    for name, i in _MONTHS.items():
        if w and name.startswith(w[:3]) and (len(w) <= 4 or name.startswith(w)):
            return i
    return None


def lines(page: str) -> list[str]:
    s = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", page)
    s = re.sub(r"<[^>]+>", "\n", s)
    s = _html.unescape(s).replace("\xa0", " ").replace("﻿", "")
    return [ln.strip() for ln in s.splitlines() if ln.strip()]


@dataclass(frozen=True)
class Event:
    utc: datetime
    name: str
    publisher: str
    impact: str
    local: str          # the stamp as the publisher states it, with its zone

    def row(self, source: str, fetched_at: str) -> dict[str, Any]:
        return {"utc": self.utc.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "name": self.name, "publisher": self.publisher, "impact": self.impact,
                "local": self.local, "source": source, "fetched_at": fetched_at}


def _at(d: date, hh: int, mm: int, zone: str) -> datetime:
    return datetime.combine(d, time(hh, mm), tzinfo=ZoneInfo(zone)).astimezone(UTC)


def _hhmm(s: str) -> tuple[int, int] | None:
    m = re.search(r"(\d{1,2}):(\d{2})\s*([AaPp]\.?[Mm]\.?)?", s)
    if not m:
        return None
    hh, mm = int(m.group(1)), int(m.group(2))
    ap = (m.group(3) or "").lower().replace(".", "")
    if ap == "pm" and hh < 12:
        hh += 12
    if ap == "am" and hh == 12:
        hh = 0
    return hh, mm


# --------------------------------------------------------------------------- Fed
def parse_fed(page: str, fetched: date) -> list[Event]:
    """Decision day = the LAST day of each scheduled meeting; statement at 14:00 ET. A notation
    vote or an unscheduled meeting is not on the scheduled calendar and is skipped."""
    out: list[Event] = []
    heads = list(re.finditer(r"(\d{4}) FOMC Meetings", page))
    for i, h in enumerate(heads):
        year = int(h.group(1))
        seg = page[h.end(): heads[i + 1].start() if i + 1 < len(heads) else len(page)]
        months = re.findall(r"fomc-meeting__month[^>]*>\s*(?:<strong>)?\s*([^<]+?)\s*<", seg)
        days = re.findall(r"fomc-meeting__date[^>]*>\s*([^<]+?)\s*<", seg)
        for mon, dd in zip(months, days, strict=False):
            if not re.fullmatch(r"\d{1,2}(-\d{1,2})?\*?", dd.strip()):
                continue                                   # notation vote, unscheduled
            sep = dd.strip().endswith("*")
            last_day = int(dd.strip().rstrip("*").split("-")[-1])
            m = _month(mon.split("/")[-1])                 # "Apr/May" ends in May
            if m is None:
                continue
            try:
                d = date(year, m, last_day)
            except ValueError:
                continue
            name = "FOMC decision" + (" + SEP" if sep else "")
            out.append(Event(_at(d, 14, 0, "America/New_York"), name, "Fed", "high",
                             f"{d} 14:00 America/New_York"))
    return out


# --------------------------------------------------------------------------- BLS
def parse_bls(page: str, fetched: date, *, name: str) -> list[Event]:
    """The schedule table: Reference Month | Release Date ('Nov. 10, 2026') | Release Time."""
    L = lines(page)
    out: list[Event] = []
    for i, ln in enumerate(L):
        m = re.fullmatch(r"([A-Z][a-z]{2,8})\.?\s+(\d{1,2}),\s+(\d{4})", ln)
        if not m or i + 1 >= len(L):
            continue
        mo = _month(m.group(1))
        t = _hhmm(L[i + 1])
        if mo is None or t is None:
            continue
        d = date(int(m.group(3)), mo, int(m.group(2)))
        out.append(Event(_at(d, *t, "America/New_York"), name, "BLS", "high",
                         f"{d} {t[0]:02d}:{t[1]:02d} America/New_York"))
    return out


# --------------------------------------------------------------------------- BEA
#: BEA releases the guard treats as high impact; everything else on the schedule is low.
BEA_HIGH = ("GDP (Advance", "GDP (Second", "GDP (Third", "Personal Income and Outlays")


def parse_bea(page: str, fetched: date) -> list[Event]:
    """Rows of 'November 25' | '8:30 AM' | type split across tags ('N', 'ews') | title. The
    year is not printed beside the date: it is the fetch year, or the next one for a month
    already behind the fetch month."""
    L = lines(page)
    out: list[Event] = []
    for i in range(1, len(L) - 1):
        m = re.fullmatch(r"([A-Z][a-z]+)\s+(\d{1,2})", L[i])
        t = _hhmm(L[i + 1]) if m else None
        mo = _month(m.group(1)) if m else None
        if not m or t is None or mo is None:
            continue
        title = next((x for x in L[i + 2:i + 6] if len(x) > 6), "")
        if not title:
            continue
        year = fetched.year + (1 if mo < fetched.month - 1 else 0)
        try:
            d = date(year, mo, int(m.group(2)))
        except ValueError:
            continue
        impact = "high" if title.startswith(BEA_HIGH) else "low"
        out.append(Event(_at(d, *t, "America/New_York"), title[:120], "BEA", impact,
                         f"{d} {t[0]:02d}:{t[1]:02d} America/New_York"))
    return out


# --------------------------------------------------------------------------- ECB
def parse_ecb(page: str, fetched: date) -> list[Event]:
    """dt 'dd/mm/yyyy' / dd text. The decision is the monetary-policy meeting day that is
    'followed by press conference'; the statement is published at 14:15 Frankfurt time."""
    out: list[Event] = []
    for d_s, text in re.findall(r"<dt>\s*(\d{2}/\d{2}/\d{4})\s*</dt>\s*<dd>(.*?)</dd>", page,
                                flags=re.S):
        t = " ".join(lines(text)).lower()
        if "monetary policy meeting" not in t or "press conference" not in t \
                or "non-monetary" in t:
            continue
        dd, mm, yy = (int(x) for x in d_s.split("/"))
        d = date(yy, mm, dd)
        out.append(Event(_at(d, 14, 15, "Europe/Berlin"), "ECB monetary policy decision", "ECB",
                         "high", f"{d} 14:15 Europe/Berlin"))
    return out


# --------------------------------------------------------------------------- BoE
def parse_boe(page: str, fetched: date) -> list[Event]:
    """'2026 confirmed dates' then 'Thursday 5 February' rows; announcement at 12:00 London."""
    out: list[Event] = []
    year: int | None = None
    for ln in lines(page):
        y = re.fullmatch(r"(\d{4}) (?:confirmed|provisional) dates", ln, flags=re.I)
        if y:
            year = int(y.group(1))
            continue
        m = re.fullmatch(r"(?:Monday|Tuesday|Wednesday|Thursday|Friday)\s+(\d{1,2})\s+"
                         r"([A-Z][a-z]+)", ln)
        if m and year is not None and (mo := _month(m.group(2))) is not None:
            d = date(year, mo, int(m.group(1)))
            out.append(Event(_at(d, 12, 0, "Europe/London"), "BoE Bank Rate decision", "BoE",
                             "high", f"{d} 12:00 Europe/London"))
    return out


# --------------------------------------------------------------------------- BoJ
BOJ_STAMPS = ((11, 30), (12, 0), (12, 30), (13, 0))


def parse_boj(page: str, fetched: date) -> list[Event]:
    """'Table : 2026' then MPM date cells 'Jan. 22 (Thurs.), 23 (Fri.)'; the decision falls on
    the meeting's last day at an unannounced time (see the module note)."""
    out: list[Event] = []
    year: int | None = None
    for ln in lines(page):
        y = re.fullmatch(r"Table\s*:\s*(\d{4})", ln)
        if y:
            year = int(y.group(1))
            continue
        m = re.match(r"([A-Z][a-z]{2,5})\.?\s+(\d{1,2})\s*\([A-Za-z.]+\),\s*(\d{1,2})\s*"
                     r"\([A-Za-z.]+\)", ln)
        if not m or year is None or (mo := _month(m.group(1))) is None:
            continue
        first, last = int(m.group(2)), int(m.group(3))
        mo_last = mo + 1 if last < first else mo
        d = date(year + (1 if mo_last == 13 else 0), (mo_last - 1) % 12 + 1, last)
        for hh, mm in BOJ_STAMPS:
            out.append(Event(_at(d, hh, mm, "Asia/Tokyo"), "BoJ policy decision (time not fixed)",
                             "BoJ", "high", f"{d} {hh:02d}:{mm:02d} Asia/Tokyo"))
    return out


# --------------------------------------------------------------------------- SNB
def parse_snb(page: str, fetched: date) -> list[Event]:
    """Rows 'dd.mm.yyyy' | 'HH:MM' | title; the monetary policy assessment press release is the
    decision. Times are Zurich time."""
    L = lines(page)
    out: list[Event] = []
    for i in range(len(L) - 2):
        m = re.fullmatch(r"(\d{2})\.(\d{2})\.(\d{4})", L[i])
        t = _hhmm(L[i + 1]) if m else None
        if not m or t is None:
            continue
        title = L[i + 2]
        low = title.lower()
        if "monetary policy assessment" not in low or "press release" not in low:
            continue
        d = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        out.append(Event(_at(d, *t, "Europe/Zurich"), "SNB monetary policy assessment", "SNB",
                         "high", f"{d} {t[0]:02d}:{t[1]:02d} Europe/Zurich"))
    return out


# --------------------------------------------------------------------------- BoC
def parse_boc(page: str, fetched: date) -> list[Event]:
    """Upcoming-events cards: 'December 9, 2026' | 'Interest Rate Announcement' | '09:45 (ET)'."""
    L = lines(page)
    out: list[Event] = []
    for i in range(len(L) - 2):
        m = re.fullmatch(r"([A-Z][a-z]+)\s+(\d{1,2}),\s+(\d{4})", L[i])
        if not m or L[i + 1].lower() != "interest rate announcement":
            continue
        t = _hhmm(L[i + 2])
        mo = _month(m.group(1))
        if t is None or mo is None:
            continue
        d = date(int(m.group(3)), mo, int(m.group(2)))
        out.append(Event(_at(d, *t, "America/Toronto"), "BoC rate announcement", "BoC", "high",
                         f"{d} {t[0]:02d}:{t[1]:02d} America/Toronto"))
    return out


PARSERS: dict[str, Callable[[str, date], list[Event]]] = {
    "fed_fomc": parse_fed,
    "bls_cpi": lambda p, f: parse_bls(p, f, name="US CPI"),
    "bls_empsit": lambda p, f: parse_bls(p, f, name="US Employment Situation (NFP)"),
    "bea_schedule": parse_bea,
    "ecb_mp_meetings": parse_ecb,
    "boe_mpc_dates": parse_boe,
    "boj_mpm": parse_boj,
    "snb_events": parse_snb,
    "boc_schedule": parse_boc,
}


def build(pages: dict[str, str | None], fetched_at: datetime,
          refused: dict[str, str] | None = None) -> dict[str, Any]:
    """The guard's calendar from whatever pages were read. `pages[id]` None = not fetched."""
    refused = refused or {}
    fetched_d = fetched_at.date()
    stamp = fetched_at.astimezone(UTC).isoformat(timespec="seconds")
    events: list[dict[str, Any]] = []
    coverage: dict[str, Any] = {}
    for pid, url in PAGES.items():
        parser = PARSERS.get(pid)
        page = pages.get(pid)
        if parser is None:
            coverage[pid] = {"status": "UNMEASURED", "url": url,
                             "why": "no parser yet: the page has not been read on the box"}
            continue
        if not page:
            coverage[pid] = {"status": "UNMEASURED", "url": url,
                             "why": refused.get(pid) or "page not fetched this refresh"}
            continue
        try:
            evs = parser(page, fetched_d)
        except Exception as exc:                       # a broken page never breaks the rest
            evs = []
            coverage[pid] = {"status": "UNMEASURED", "url": url,
                             "why": f"parser raised {type(exc).__name__}"}
            continue
        if not evs:
            coverage[pid] = {"status": "UNMEASURED", "url": url,
                             "why": "the page no longer matches its parser: 0 events"}
            continue
        events.extend(e.row(url, stamp) for e in evs)
        coverage[pid] = {"status": "OK", "url": url, "events": len(evs),
                         "through": max(e.utc for e in evs).date().isoformat()}
    horizons = [coverage[p].get("through") for p in CORE]
    valid = min(horizons) if all(horizons) else None   # type: ignore[type-var]
    events.sort(key=lambda r: (r["utc"], r["name"]))
    return {"valid_through": valid or "", "generated_at": stamp,
            "source": "official publisher schedules (libs/data/event_calendar.py)",
            "core_publishers": list(CORE), "coverage": coverage, "events": events,
            "rule": ("valid_through is the earliest horizon among the core publishers; an "
                     "absent core page leaves it empty, which the guard reads as STALE and "
                     "blocks on. No date is ever entered by hand.")}


# --------------------------------------------------------------------------- refresh
#: Refresh cadence. The publishers move dates rarely and announce it; a week is the order the
#: Hourly pass gave (2026-11-13), and the refresh also runs early when a core page was missing.
REFRESH_D = 7
#: A core publisher whose page could not be read this refresh keeps the events of the last
#: refresh that DID read it, for this long. Past it the publisher reads UNMEASURED and
#: valid_through empties: the guard blocks rather than trusting a schedule nobody re-read.
CARRY_MAX_D = 21
#: The leg reports STALE (and exits non-zero) when the written calendar is older than this.
STALE_D = 14
ROBOTS_AGENT = "quant-desk-calendar"
HONEST_UA = f"{ROBOTS_AGENT}/1.0 (research; reads official release schedules; robots-respecting)"
#: What a refused or unread page costs: the guard blocks every entry once valid_through passes,
#: and a non-core publisher's window goes unguarded until it is read again.
MISSED_GROWTH = ("an unread core page empties valid_through within CARRY_MAX_D days, after which "
                 "event_guard blocks every new entry; an unread non-core page leaves that "
                 "publisher's windows unguarded")


def _parse_ts(s: str) -> datetime | None:
    try:
        d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def fetch_pages(get: Callable[..., Any] | None = None,
                refusal: Callable[[str], str | None] | None = None,
                ) -> tuple[dict[str, str | None], dict[str, str]]:
    """Every publisher page through the robots gate (fail closed) under an honest UA."""
    if get is None:
        from libs.data import polite_fetch as pf
        get = pf.get
    if refusal is None:
        from libs.data.datahub_feeds import robots_refusal as refusal
    pages: dict[str, str | None] = {}
    refused: dict[str, str] = {}
    for pid, url in PAGES.items():
        why = refusal(url)
        if why:
            pages[pid], refused[pid] = None, f"ROBOTS_REFUSED: {why}"
            continue
        r = get(url, headers={"User-Agent": HONEST_UA}, leg="event_calendar")
        if getattr(r, "ok", False) and getattr(r, "text", ""):
            pages[pid] = r.text
        else:
            code = getattr(r, "status", None)
            pages[pid] = None
            refused[pid] = (f"HTTP {code}" if code else
                            f"unreachable ({getattr(r, 'error', '') or 'no body'})")
    return pages, refused


def carry_forward(doc: dict[str, Any], prev: dict[str, Any] | None,
                  now: datetime) -> dict[str, Any]:
    """Keep the last good events of a publisher this refresh could not read, within
    CARRY_MAX_D of when they were fetched, and recompute valid_through."""
    prev_cov = (prev or {}).get("coverage") or {}
    prev_events = (prev or {}).get("events") or []
    for pid, cov in doc["coverage"].items():
        old = prev_cov.get(pid) or {}
        if cov.get("status") == "OK" or old.get("status") not in ("OK", "CARRIED"):
            continue
        url = PAGES[pid]
        rows = [e for e in prev_events if isinstance(e, dict) and e.get("source") == url]
        got = [_parse_ts(e.get("fetched_at", "")) for e in rows]
        if not rows or any(g is None for g in got):
            continue
        age = (now - min(g for g in got if g is not None)).total_seconds() / 86400
        if age > CARRY_MAX_D:
            continue
        doc["events"].extend(rows)
        doc["coverage"][pid] = {"status": "CARRIED", "url": url, "events": len(rows),
                                "through": old.get("through", ""),
                                "carried_days": round(age, 2),
                                "why": cov.get("why", "")}
    doc["events"].sort(key=lambda r: (r["utc"], r["name"]))
    horizons = [doc["coverage"][p].get("through") for p in CORE
                if doc["coverage"][p].get("status") in ("OK", "CARRIED")]
    doc["valid_through"] = min(horizons) if len(horizons) == len(CORE) else ""
    return doc


def refusal(doc: dict[str, Any]) -> str | None:
    """Why this calendar must not REPLACE the one on disk, or None. A stamp that is not UTC,
    an out-of-order list or a duplicated (time, name, publisher) would clear a window the guard
    exists to block while reporting healthy; leaving the last good file is safer."""
    events = doc.get("events") or []
    if not events:
        return "REFUSED: no events parsed from any publisher"
    keys = [(e.get("utc"), e.get("name"), e.get("publisher")) for e in events]
    if any(not isinstance(k[0], str) or not k[0].endswith("Z") or _parse_ts(k[0]) is None
           for k in keys):
        return "REFUSED: a stamp is unparseable or not UTC"
    if [k[0] for k in keys] != sorted(k[0] for k in keys):
        return "REFUSED: events are not in ascending UTC order"
    if len(set(keys)) != len(keys):
        return "REFUSED: duplicate (utc, name, publisher) rows"
    return None


def due(prev: dict[str, Any] | None, now: datetime) -> str | None:
    """Why a refresh is due now, or None while the written calendar is fresh and complete."""
    if not prev or "coverage" not in prev:
        return "no calendar written by this module yet"
    gen = _parse_ts(prev.get("generated_at", ""))
    if gen is None or (now - gen).days >= REFRESH_D:
        return f"older than {REFRESH_D} days"
    bad = [p for p in CORE if (prev["coverage"].get(p) or {}).get("status") != "OK"]
    if bad:
        return "core publisher not read last refresh: " + ", ".join(bad)
    if not prev.get("valid_through"):
        return "valid_through empty"
    return None


def health(doc: dict[str, Any] | None, now: datetime) -> dict[str, Any]:
    """What the guard will make of this calendar, stated before it has to: FRESH, or STALE with
    the reason. STALE means event_guard blocks every new entry."""
    if not doc:
        return {"state": "STALE", "why": "no calendar on disk"}
    vt = str(doc.get("valid_through") or "")
    gen = _parse_ts(doc.get("generated_at") or doc.get("generated") or "")
    age = None if gen is None else round((now - gen).total_seconds() / 86400, 2)
    if not vt:
        return {"state": "STALE", "why": "valid_through empty (a core publisher is unread)",
                "age_days": age}
    if vt < now.date().isoformat():
        return {"state": "STALE", "why": f"valid_through {vt} has passed", "age_days": age}
    if age is None or age > STALE_D:
        return {"state": "STALE", "why": f"not refreshed for {age} days (limit {STALE_D})",
                "age_days": age}
    return {"state": "FRESH", "valid_through": vt, "age_days": age,
            "events": len(doc.get("events") or [])}
