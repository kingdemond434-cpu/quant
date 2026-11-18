"""RELEASE CALENDAR STATES -- official headline prints as point-in-time surprise events.

WHY (hourly pass idea 26, 2026-11-18). The cloud deep-forest pass found ZERO trader claims in 25
regions (research/deep_forest_cloud/ZERO_REGION_REASONS.md): search engines refuse, forums refuse,
and the official pages it did reach "yield datasets, not trader claims". A dataset is exactly what
this organ wants. An official statistics office publishes its headline print on a calendar; the
print against a point-in-time naive expectation is a SURPRISE, and the surprise, dated at the
moment the public could first read it, is an event the region's currency can be tested against.

THE GROUNDS ARE DATA, NOT CODE. `desks/mt5/data/release_calendar_grounds.json` holds one row per
region: the calendar and terms URLs, the quoted clause, a verdict (CONFIRMED / BLOCKED_ON_TERMS /
HARD_STOP / NO_CALENDAR) and `built`. This organ fetches a route ONLY when every region it serves
is CONFIRMED and built in that file; a row that is missing, unread or refused fails closed by name.
Built on 2026-11-18: ea, it, cz, hu, no (Eurostat dissemination API), gb (ONS time series), ca
(Statistics Canada Web Data Service). Everything else carries its verdict and a missed-growth line.

THE POINT-IN-TIME RULE (the design of PR #1318 `macro_event_states`, reused, not imported: that
branch is unmerged). available_time is never earlier than the publication:
  * every route gives the PUBLISHER'S OWN publication stamp for the print -- Eurostat's
    DISSEMINATION_TIMESTAMP_DATA annotation (its calendar's PLANNED stamp sits beside it, and a
    print later than planned is recorded as delayed), ONS `updateDate` (the release day; the
    calendar's 07:00 London rule gives the instant), StatCan `releaseTime` (Ottawa local time).
  * FIRST PULL (backfill) is the publisher's CURRENT vintage of old periods. It is labelled
    `backfill`, is NEVER judged (no lake row, no cell, no clock event) and feeds expectation
    history only, known from the moment it was read.
  * a LIVE first print takes the publisher's stamp only when the reads bracket it (the previous
    successful read did not hold the period, the stamp lies after that read and at or before
    this one, within RULE_SLACK); otherwise the moment it was first seen. So a stamp that is a
    date-only or a late re-load can only make the time LATER, never earlier.
  * a revision is appended and stamped when seen; surprise maths reads first-seen values only.

THE EXPECTATION (no paid consensus is read). For each print, every method uses only prints with
an earlier period that were known strictly before the release: `last` (random walk, PRIMARY),
`trailing_mean3`, `ar1` (OLS over <= 36 points). surprise = actual - expectation. surprise_z
divides by the std of the method's strictly earlier surprises (>= SCALE_MIN), and that history
MAY include backfilled prints: it is part of the expectation, never a judged row, and the count
of backfilled vs live surprises behind each scale is published on the row (`scale_basis`).

WHAT IT WRITES
  * `data/release_calendar_states/<route>.jsonl` -- the append-only PIT store (gitignored).
  * `data/lake/series/rcs_<series>.csv` -- LIVE prints only: event_time (reference period),
    available_time, value (= surprise_z), surprise_z, surprise, actual, expectation, pit_quality.
  * `alt_release_drift` cells (a registered family) on the mapped currency pairs with the
    declared prior sign, once a series holds MIN_LIVE_RELEASES scaled live prints.
  * `reports/RELEASE_CALENDAR_CLOCK.json` -- one event per live surprise, a ground of
    `event_response_atlas.load_events`.
  * `reports/RELEASE_CALENDAR_STATES.json` -- per-route status, the region verdicts, store size,
    latest state per series, cells, missed-growth lines.

ACCESS, EACH FAILING CLOSED BY NAME: the grounds file must hold CONFIRMED+built for every region
the route serves; `libs.data.refused_hosts` must not list the host; the host's robots.txt must
allow the path for our agent (only 404/410 means "no rules"; unreadable or HTML refuses).
401/403/429/451 -- and a challenge page or wall where data was expected -- is a HARD STOP for the
route: no further request this pass. 401, 403, 451 and a wall stay stopped until a person
releases them, as `source_fixer` holds them site-wide; only a 429 lapses after HARD_STOP_H
hours. Honest UA, MIN_INTERVAL_S between requests, MAX_REQUESTS per pass, and a wall-clock
budget no request may outrun. A route is fetched only when due.

    python desks/mt5/research/release_calendar_states.py --once [--budget-s 240] [--no-fetch]
"""
from __future__ import annotations

import argparse
import contextlib
import json
import math
import os
import re
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from itertools import product
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SOURCE_ID = "release_calendar_states"
SEAT = "release_calendar_states"
FAMILY = "alt_release_drift"
UNMEASURED = "UNMEASURED"
LON = ZoneInfo("Europe/London")
OTT = ZoneInfo("America/Toronto")

MIN_INTERVAL_S = 2.0
MAX_REQUESTS = 12
HARD_STOP_CODES = frozenset({401, 403, 429, 451})
HARD_STOP_H = 24
#: Refusals held until a person releases them (the fetch law, as source_fixer reads it).
HELD_UNTIL_RELEASED = frozenset({"401", "403", "451", "WALL"})
TIMEOUT = 30.0
MAX_BYTES = 8 * 1024 * 1024
ROBOTS_AGENT = "quant-desk-research"
UA = f"{ROBOTS_AGENT}/1.0 (release_calendar_states; research; honours robots.txt)"
RULE_SLACK = timedelta(hours=2)
SCALE_MIN = 8
SCALE_WINDOW = 60
AR1_MIN = 12
AR1_WINDOW = 36
#: Scaled LIVE releases a series needs before cells are minted: every cell is a trial charged to
#: the desk's one family-wise error budget, so no cell is minted on a handful of events.
MIN_LIVE_RELEASES = 12
CELL_GRID: dict[str, tuple[Any, ...]] = {"threshold": (1.0, 1.5), "side": (1, -1),
                                         "hold_days": (3,)}
EXPECTATION_METHODS: tuple[str, ...] = ("last", "trailing_mean3", "ar1")
PRIMARY = "last"
BACKFILL = "backfill"
GROUNDS = DESK / "data" / "release_calendar_grounds.json"
_WALL = re.compile(rb"(?i)incapsula|captcha|cf-chl|challenge-platform|access denied|"
                   rb"are you a robot|_Incapsula_Resource")


def _now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _read(p: Path, default: Any) -> Any:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def _atomic(p: Path, doc: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(f".tmp{os.getpid()}")
    tmp.write_text(json.dumps(doc, indent=1, sort_keys=True, default=str) + "\n", "utf-8")
    os.replace(tmp, p)


def _t(s: Any) -> datetime | None:
    if isinstance(s, datetime):
        return s if s.tzinfo else s.replace(tzinfo=UTC)
    if not s:
        return None
    txt = str(s).strip().replace("Z", "+00:00")
    m = re.match(r"^(.*[T ]\d\d:\d\d(?::\d\d(?:\.\d+)?)?)([+-]\d\d)(\d\d)$", txt)
    if m:                                    # Eurostat writes +0200 without the colon
        txt = f"{m.group(1)}{m.group(2)}:{m.group(3)}"
    try:
        d = datetime.fromisoformat(txt)
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def _iso(d: datetime) -> str:
    return d.astimezone(UTC).isoformat(timespec="seconds")


class Refused(Exception):
    """A named refusal: '<STATUS>:<why>'."""


# --------------------------------------------------------------------------- the grounds file
def load_grounds(path: Path = GROUNDS) -> dict[str, dict[str, Any]]:
    doc = _read(path, {}) or {}
    rows = doc.get("regions") if isinstance(doc, dict) else None
    return {str(r["region"]): r for r in rows or [] if isinstance(r, dict) and r.get("region")}


def region_refusal(regions: Iterable[str], grounds: Mapping[str, Mapping[str, Any]]) -> str | None:
    """Why a route serving `regions` may not fetch, or None. Every region must be CONFIRMED and
    built in the grounds file: a missing row is unread terms, and unread terms are a refusal."""
    for r in regions:
        g = grounds.get(r)
        if g is None:
            return f"BLOCKED_ON_TERMS:region {r} has no row in the grounds file (terms unread)"
        if g.get("verdict") != "CONFIRMED":
            return f"{g.get('verdict') or 'BLOCKED_ON_TERMS'}:region {r} verdict"
        if g.get("built") is not True:
            return f"BLOCKED_ON_TERMS:region {r} is not marked built"
    return None


# ------------------------------------------------------------------------------- observations
@dataclass(frozen=True)
class Obs:
    series: str
    period: str                      # YYYY-MM
    value: float
    published: datetime | None       # the publisher's own publication stamp (UTC), if any
    planned: datetime | None = None  # the calendar's scheduled stamp, if the route carries one


_MON = {m: i for i, m in enumerate(("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG",
                                    "SEP", "OCT", "NOV", "DEC"), start=1)}


def _json(body: bytes) -> Any:
    try:
        return json.loads(body.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError):
        raise Refused("UNPARSEABLE:body is not JSON") from None


def _annotation(doc: Mapping[str, Any], kind: str) -> datetime | None:
    ext = doc.get("extension") or {}
    for a in (ext.get("annotation") or []) if isinstance(ext, dict) else []:
        if isinstance(a, dict) and a.get("type") == kind:
            return _t(a.get("date") or a.get("title"))
    return None


#: Eurostat geo code -> region. The euro area's code moves with each enlargement.
EUROSTAT_GEO: dict[str, str] = {"EA": "ea", "EA20": "ea", "EA21": "ea", "IT": "it", "CZ": "cz",
                                "HU": "hu", "NO": "no"}


def parse_eurostat(body: bytes, indicator: str) -> list[Obs]:
    """JSON-stat 2.0 from the dissemination API -> one Obs per (geo, month). The dataset-level
    DISSEMINATION_TIMESTAMP_DATA (else `updated`) is the publication stamp of the newest period;
    older periods carry none (they are history the first time, revisions after)."""
    doc = _json(body)
    if not isinstance(doc, dict) or "value" not in doc or "id" not in doc:
        raise Refused("UNPARSEABLE:not a JSON-stat dataset")
    ids: list[str] = list(doc["id"])
    size: list[int] = [int(s) for s in doc["size"]]
    dims = doc.get("dimension") or {}
    cats: list[list[str]] = []
    for d in ids:
        idx = ((dims.get(d) or {}).get("category") or {}).get("index") or {}
        if isinstance(idx, list):
            cats.append([str(c) for c in idx])
        else:
            cats.append([k for k, _ in sorted(idx.items(), key=lambda kv: int(kv[1]))])
    for d, n, c in zip(ids, size, cats, strict=True):
        if d not in ("geo", "time") and n != 1:
            raise Refused(f"METADATA_MISMATCH:dimension {d} has {n} categories, expected 1")
        if len(c) != n:
            raise Refused(f"METADATA_MISMATCH:dimension {d} index does not match its size")
    published = _annotation(doc, "DISSEMINATION_TIMESTAMP_DATA") or _t(doc.get("updated"))
    planned = _annotation(doc, "DISSEMINATION_TIMESTAMP_PLANNED")
    vals = doc["value"]
    items = (vals.items() if isinstance(vals, dict)
             else ((str(i), v) for i, v in enumerate(vals) if v is not None))
    strides = [math.prod(size[i + 1:]) for i in range(len(size))]
    out: list[Obs] = []
    latest: dict[str, str] = {}
    raw: list[tuple[str, str, float]] = []
    for k, v in items:
        if not isinstance(v, int | float):
            continue
        flat, coord = int(k), {}
        for d, st, c in zip(ids, strides, cats, strict=True):
            coord[d] = c[(flat // st) % len(c)]
        region = EUROSTAT_GEO.get(coord.get("geo", ""))
        period = coord.get("time", "")
        if region is None or not re.match(r"^\d{4}-\d\d$", period):
            continue
        raw.append((region, period, float(v)))
        latest[region] = max(latest.get(region, ""), period)
    for region, period, v in raw:
        stamp = published if period == latest[region] else None
        out.append(Obs(f"{region}_{indicator}", period, v, stamp,
                       planned if stamp is not None else None))
    return out


def parse_ons(body: bytes, series: str) -> list[Obs]:
    """ONS time-series JSON: `months[]` rows of {date: 'YYYY MON', value, updateDate}. ONS
    stamps updateDate at London midnight of the release day; the release calendar publishes at
    07:00 London, so that instant is the publication stamp."""
    doc = _json(body)
    months = doc.get("months") if isinstance(doc, dict) else None
    if not isinstance(months, list):
        raise Refused("UNPARSEABLE:no months array")
    out: list[Obs] = []
    for m in months:
        if not isinstance(m, dict):
            continue
        mm = re.match(r"^(\d{4}) ([A-Z]{3})", str(m.get("date") or "").upper())
        try:
            v = float(str(m.get("value")).replace(",", ""))
        except ValueError:
            continue
        if not mm or mm.group(2) not in _MON:
            continue
        up = _t(m.get("updateDate"))
        pub = None
        if up is not None:
            # midnight London stamped in UTC (23:00Z the evening before in summer): round to
            # the London date it names, then the 07:00 rule
            loc = (up + timedelta(hours=1)).astimezone(LON).date()
            pub = datetime(loc.year, loc.month, loc.day, 7, 0, tzinfo=LON).astimezone(UTC)
        out.append(Obs(series, f"{mm.group(1)}-{_MON[mm.group(2)]:02d}", v, pub))
    if not out:
        raise Refused("UNPARSEABLE:months array held no readable rows")
    return out


STATCAN_VECTORS: dict[int, str] = {41690973: "ca_cpi_index", 2062815: "ca_unemployment"}


def parse_statcan(body: bytes) -> list[Obs]:
    """WDS getDataFromVectorsAndLatestNPeriods: per vector, `vectorDataPoint[]` with refPer
    (YYYY-MM-01), value and releaseTime (Ottawa local, no offset)."""
    doc = _json(body)
    if not isinstance(doc, list):
        raise Refused("UNPARSEABLE:WDS answer is not a list")
    out: list[Obs] = []
    for item in doc:
        obj = item.get("object") if isinstance(item, dict) else None
        if not isinstance(obj, dict) or item.get("status") != "SUCCESS":
            continue
        series = STATCAN_VECTORS.get(int(obj.get("vectorId") or 0))
        if series is None:
            continue
        for p in obj.get("vectorDataPoint") or []:
            ref = str(p.get("refPer") or "")
            if not re.match(r"^\d{4}-\d\d", ref) or not isinstance(p.get("value"), int | float):
                continue
            rt = None
            with contextlib.suppress(ValueError, TypeError):
                rt = datetime.fromisoformat(str(p.get("releaseTime"))).replace(
                    tzinfo=OTT).astimezone(UTC)
            out.append(Obs(series, ref[:7], float(p["value"]), rt))
    if not out:
        raise Refused("UNPARSEABLE:no vector data points")
    return out


# ------------------------------------------------------------------------------------- routes
def _since(now: datetime, years: int = 10) -> str:
    return f"{now.year - years:04d}-01"


@dataclass(frozen=True)
class Route:
    rid: str
    regions: tuple[str, ...]
    url: Callable[[datetime], str]
    parse: Callable[[bytes], list[Obs]]
    #: UTC hours (weekdays) when the route's prints land: hourly there, every SLOW_H otherwise
    window_utc: tuple[int, int]
    post: Callable[[], bytes] | None = None
    slow_h: int = 6


EUROSTAT = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
_EGEO = "".join(f"&geo={g}" for g in ("EA", "IT", "CZ", "HU", "NO"))
_UGEO = "".join(f"&geo={g}" for g in ("EA20", "IT", "CZ", "HU", "NO"))
ONS = "https://www.ons.gov.uk"
STATCAN_WDS = ("https://www150.statcan.gc.ca/t1/wds/rest/getDataFromVectorsAndLatestNPeriods")

ROUTES: dict[str, Route] = {r.rid: r for r in (
    Route("eurostat_hicp", ("ea", "it", "cz", "hu", "no"),
          lambda now: (f"{EUROSTAT}prc_hicp_minr?format=JSON&lang=EN&coicop18=TOTAL&unit=RCH_A"
                       f"{_EGEO}&sinceTimePeriod={_since(now)}"),
          lambda b: parse_eurostat(b, "cpi_yoy"), (8, 12)),
    Route("eurostat_unemployment", ("ea", "it", "cz", "hu", "no"),
          lambda now: (f"{EUROSTAT}une_rt_m?format=JSON&lang=EN&s_adj=SA&age=TOTAL&sex=T"
                       f"&unit=PC_ACT{_UGEO}&sinceTimePeriod={_since(now)}"),
          lambda b: parse_eurostat(b, "unemployment"), (8, 12)),
    Route("ons_cpi", ("gb",),
          lambda now: f"{ONS}/economy/inflationandpriceindices/timeseries/d7g7/mm23/data",
          lambda b: parse_ons(b, "gb_cpi_yoy"), (5, 9)),
    Route("ons_unemployment", ("gb",),
          lambda now: (f"{ONS}/employmentandlabourmarket/peoplenotinwork/unemployment/"
                       "timeseries/mgsx/lms/data"),
          lambda b: parse_ons(b, "gb_unemployment"), (5, 9)),
    Route("statcan_wds", ("ca",), lambda now: STATCAN_WDS, parse_statcan, (12, 15),
          post=lambda: json.dumps([{"vectorId": v, "latestN": 140}
                                   for v in STATCAN_VECTORS]).encode()),
)}


# ------------------------------------------------------------- states and the symbol mapping
@dataclass(frozen=True)
class State:
    """One judged series: `base` in the store, `kind` 'level' or 'yoy' (12-month % change of an
    index), and the mapped symbols with the DECLARED prior sign of a positive surprise on the
    symbol's price (a hot CPI strengthens the currency; a high unemployment print weakens it)."""
    name: str
    route: str
    region: str
    base: str
    kind: str
    priors: dict[str, int] = field(default_factory=dict)


def _fx(ccy: str, sign: int, pairs: Iterable[str]) -> dict[str, int]:
    """Prior on each pair: + when the region's currency is the base, - when it is the quote."""
    return {p: (sign if p.startswith(ccy) else -sign) for p in pairs}


STATES: tuple[State, ...] = (
    *(State(f"{r}_cpi_yoy", "eurostat_hicp", r, f"{r}_cpi_yoy", "level", _fx(c, 1, ps))
      for r, c, ps in (("ea", "EUR", ("EURUSD",)), ("it", "EUR", ("EURUSD",)),
                       ("cz", "CZK", ("EURCZK", "USDCZK")), ("hu", "HUF", ("EURHUF", "USDHUF")),
                       ("no", "NOK", ("EURNOK", "USDNOK")))),
    *(State(f"{r}_unemployment", "eurostat_unemployment", r, f"{r}_unemployment", "level",
            _fx(c, -1, ps))
      for r, c, ps in (("ea", "EUR", ("EURUSD",)), ("it", "EUR", ("EURUSD",)),
                       ("cz", "CZK", ("EURCZK", "USDCZK")), ("hu", "HUF", ("EURHUF", "USDHUF")),
                       ("no", "NOK", ("EURNOK", "USDNOK")))),
    State("gb_cpi_yoy", "ons_cpi", "gb", "gb_cpi_yoy", "level",
          _fx("GBP", 1, ("GBPUSD", "EURGBP"))),
    State("gb_unemployment", "ons_unemployment", "gb", "gb_unemployment", "level",
          _fx("GBP", -1, ("GBPUSD", "EURGBP"))),
    State("ca_cpi_yoy", "statcan_wds", "ca", "ca_cpi_index", "yoy", _fx("CAD", 1, ("USDCAD",))),
    State("ca_unemployment", "statcan_wds", "ca", "ca_unemployment", "level",
          _fx("CAD", -1, ("USDCAD",))),
)


# ------------------------------------------------------------------------------- the fetcher
Getter = Callable[[str, bytes | None], tuple[int, bytes]]


def http_get(url: str, data: bytes | None = None) -> tuple[int, bytes]:
    """One request with the honest UA; every redirect hop is checked against refused hosts."""
    from libs.data import refused_hosts
    opener = refused_hosts.opener()
    headers = {"User-Agent": UA, "Accept": "application/json, text/plain;q=0.5"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers,
                                 method="POST" if data is not None else "GET")
    try:
        with opener.open(req, timeout=TIMEOUT) as resp:
            return int(getattr(resp, "status", 200) or 200), bytes(resp.read(MAX_BYTES))
    except urllib.error.HTTPError as e:
        return int(e.code), b""


class Client:
    """Every request of a pass: throttled, counted, hard-stopped, bounded by the wall clock."""

    def __init__(self, get: Getter, *, sleep: Callable[[float], None] = time.sleep,
                 max_requests: int = MAX_REQUESTS, min_interval_s: float = MIN_INTERVAL_S,
                 deadline: float = math.inf) -> None:
        self.get, self.sleep = get, sleep
        self.max_requests, self.min_interval_s, self.deadline = (max_requests, min_interval_s,
                                                                 deadline)
        self.requests = 0
        self._last = -math.inf
        self._robots: dict[str, str | None] = {}

    def _pace(self) -> None:
        if self.requests >= self.max_requests:
            raise Refused(f"BUDGET:request budget of {self.max_requests} per pass spent")
        if time.monotonic() + self.min_interval_s + TIMEOUT > self.deadline:
            raise Refused("BUDGET:wall-clock budget of this pass spent")
        wait = self.min_interval_s - (time.monotonic() - self._last)
        if wait > 0 and self.requests:
            self.sleep(wait)
        self._last = time.monotonic()
        self.requests += 1

    def fetch(self, url: str, data: bytes | None = None) -> bytes:
        self._pace()
        try:
            status, body = self.get(url, data)
        except Exception as exc:
            raise Refused(f"FETCH_ERROR:{type(exc).__name__}: {str(exc)[:160]}") from None
        if status in HARD_STOP_CODES:
            raise Refused(f"HARD_STOP:{status}")
        if status != 200:
            raise Refused(f"HTTP_{status}:{urllib.parse.urlsplit(url).path}")
        head = body[:4096]
        if head.lstrip()[:1] in (b"<",) and _WALL.search(head):
            raise Refused("HARD_STOP:WALL a challenge page answered where data was expected")
        return body

    def robots(self, url: str) -> str | None:
        parts = urllib.parse.urlsplit(url)
        host = f"{parts.scheme}://{parts.netloc}"
        if host not in self._robots:
            self._robots[host] = self._robots_read(host)
        why = self._robots[host]
        if why is not None and why.startswith("RULES:"):
            rp = urllib.robotparser.RobotFileParser()
            rp.parse(why[6:].splitlines())
            if not rp.can_fetch(ROBOTS_AGENT, url):
                return f"ROBOTS_REFUSED:robots.txt disallows {parts.path}"
            return None
        return why

    def _robots_read(self, host: str) -> str | None:
        self._pace()
        try:
            status, body = self.get(f"{host}/robots.txt", None)
        except Exception as exc:
            return f"ROBOTS_REFUSED:robots.txt unreadable ({type(exc).__name__})"
        if status in (404, 410):
            return None
        if status in HARD_STOP_CODES:
            return f"HARD_STOP:{status}"
        if status != 200:
            return f"ROBOTS_REFUSED:robots.txt answered HTTP {status}"
        if body.lstrip()[:1] == b"<":
            return "ROBOTS_REFUSED:robots.txt answered HTML"
        return "RULES:" + body.decode("utf-8", errors="replace")


def access_refusal(route: Route, url: str, client: Client,
                   grounds: Mapping[str, Mapping[str, Any]]) -> str | None:
    """Grounds (terms), then the refused-hosts list, then robots -- before any data request."""
    why = region_refusal(route.regions, grounds)
    if why:
        return why
    from libs.data import refused_hosts
    host_why = refused_hosts.refusal(url)
    if host_why:
        return f"BLOCKED_ON_TERMS:{host_why}"
    return client.robots(url)


# --------------------------------------------------------------------- point-in-time store
@dataclass(frozen=True)
class Paths:
    desk: Path = DESK

    @property
    def store(self) -> Path:
        return self.desk / "data" / "release_calendar_states"

    @property
    def state(self) -> Path:
        return self.store / "state.json"

    @property
    def series(self) -> Path:
        return self.desk / "data" / "lake" / "series"

    @property
    def universe(self) -> Path:
        return self.desk / "data" / "universe" / "universe.json"

    @property
    def grounds(self) -> Path:
        return self.desk / "data" / "release_calendar_grounds.json"

    @property
    def report(self) -> Path:
        return self.desk / "reports" / "RELEASE_CALENDAR_STATES.json"

    @property
    def clock(self) -> Path:
        return self.desk / "reports" / "RELEASE_CALENDAR_CLOCK.json"


Store = dict[tuple[str, str], dict[str, Any]]


def load_store(paths: Paths, rid: str) -> Store:
    out: Store = {}
    p = paths.store / f"{rid}.jsonl"
    try:
        lines = p.read_text("utf-8").splitlines() if p.exists() else []
    except OSError:
        lines = []
    for line in lines:
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if not isinstance(r, dict) or not r.get("series") or not r.get("period"):
            continue
        k = (str(r["series"]), str(r["period"]))
        if k not in out:
            out[k] = {**r, "last_value": r.get("value"), "n_revisions": 0}
        else:
            out[k]["last_value"] = r.get("value")
            out[k]["n_revisions"] = int(out[k].get("n_revisions") or 0) + 1
    return out


def stamp(published: datetime | None, seen: datetime,
          prev_ok: datetime | None) -> tuple[datetime, str]:
    """The available_time of a period first seen at `seen` (module docstring). Never earlier
    than the publication: the publisher's stamp is taken only when the reads bracket it."""
    if prev_ok is None:
        return seen, BACKFILL
    if published is not None and prev_ok < published <= seen <= published + RULE_SLACK:
        return published, "live_publisher_stamp"
    return seen, "live_seen"


def merge(paths: Paths, rid: str, store: Store, obs: Iterable[Obs], seen: datetime,
          prev_ok: datetime | None) -> dict[str, int]:
    recs: list[dict[str, Any]] = []
    added = revised = delayed = 0
    for o in obs:
        k = (o.series, o.period)
        cur = store.get(k)
        if cur is None:
            avail, quality = stamp(o.published, seen, prev_ok)
            rec: dict[str, Any] = {
                "series": o.series, "period": o.period, "value": o.value,
                "published": _iso(o.published) if o.published else None,
                "planned": _iso(o.planned) if o.planned else None,
                "first_seen_at": _iso(seen), "available_time": _iso(avail),
                "pit_quality": quality, "revision": False}
            if o.planned and o.published and o.published > o.planned + timedelta(minutes=5):
                rec["delayed_vs_calendar"] = True
                delayed += 1
            store[k] = {**rec, "last_value": o.value, "n_revisions": 0}
            added += 1
        elif cur.get("last_value") != o.value:
            rec = {"series": o.series, "period": o.period, "value": o.value,
                   "first_seen_at": _iso(seen), "available_time": _iso(seen), "revision": True}
            cur["last_value"] = o.value
            cur["n_revisions"] = int(cur.get("n_revisions") or 0) + 1
            revised += 1
        else:
            continue
        recs.append(rec)
    if recs:
        p = paths.store / f"{rid}.jsonl"
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            for rec in recs:
                fh.write(json.dumps(rec, sort_keys=True) + "\n")
    return {"added": added, "revised": revised, "delayed_vs_calendar": delayed}


# ------------------------------------------------------------------------------ surprises
def _later(a: str, b: str) -> str:
    ta, tb = _t(a), _t(b)
    return a if ta is not None and (tb is None or ta >= tb) else b


def points(store: Mapping[tuple[str, str], Mapping[str, Any]], series: str) -> list[dict[str, Any]]:
    """First-seen (point-in-time) points of one series, in period order. `known_at` is when the
    desk could use the point as HISTORY: a backfilled row from the moment it was read."""
    pts = [{"period": k[1], "value": float(r["value"]), "available_time": r["available_time"],
            "pit_quality": r.get("pit_quality"),
            "known_at": r.get("first_seen_at") or r["available_time"]}
           for k, r in store.items() if k[0] == series and isinstance(r.get("value"), int | float)]
    return sorted(pts, key=lambda p: p["period"])


def _shift_month(period: str, k: int) -> str:
    y, m = int(period[:4]), int(period[5:7])
    n = y * 12 + (m - 1) - k
    return f"{n // 12:04d}-{n % 12 + 1:02d}"


def yoy(pts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Index level -> 12-month % change; knowable when BOTH levels are; backfill if either is."""
    by = {p["period"]: p for p in pts}
    out: list[dict[str, Any]] = []
    for p in pts:
        a = by.get(_shift_month(p["period"], 12))
        if a is None or not a["value"]:
            continue
        q = BACKFILL if BACKFILL in (a["pit_quality"], p["pit_quality"]) else p["pit_quality"]
        out.append({"period": p["period"], "value": round(100.0 * (p["value"] / a["value"] - 1), 6),
                    "available_time": _later(a["available_time"], p["available_time"]),
                    "known_at": _later(a["known_at"], p["known_at"]), "pit_quality": q})
    return out


def _ar1(values: list[float]) -> float | None:
    if len(values) < AR1_MIN:
        return None
    x, y = values[:-1], values[1:]
    mx, my = sum(x) / len(x), sum(y) / len(y)
    vx = sum((v - mx) ** 2 for v in x)
    if vx <= 0:
        return my
    b = sum((a - mx) * (c - my) for a, c in zip(x, y, strict=True)) / vx
    return (my - b * mx) + b * values[-1]


def expectation(series: list[dict[str, Any]], release: datetime | None, method: str,
                period: str) -> float | None:
    """The desk's own expectation of `period`, from points with an earlier period that were
    KNOWN strictly before `release`. None when the method lacks history (never padded).
    `release` None is used ONLY to build the scale history over backfilled prints, which are
    never judged: there the read order is meaningless and the period order is the history."""
    prior = [p for p in series if p["period"] < period
             and (release is None
                  or ((t := _t(p["known_at"])) is not None and t < release))]
    if not prior:
        return None
    if method == "last":
        # the immediately preceding month must be the last known point, else no expectation
        return float(prior[-1]["value"]) if prior[-1]["period"] == _shift_month(period, 1) \
            else None
    if method == "trailing_mean3":
        prev = prior[-3:]
        if len(prev) < 3 or prev[0]["period"] < _shift_month(period, 4):
            return None
        return sum(float(p["value"]) for p in prev) / 3.0
    if method == "ar1":
        return _ar1([float(p["value"]) for p in prior[-AR1_WINDOW:]])
    raise ValueError(f"unknown expectation method {method!r}")


def surprises(pts: list[dict[str, Any]], kind: str) -> list[dict[str, Any]]:
    """Each LIVE print against every method; backfill feeds expectations and scales only."""
    target = yoy(pts) if kind == "yoy" else pts
    hist: dict[str, list[tuple[float, bool]]] = {m: [] for m in EXPECTATION_METHODS}
    out: list[dict[str, Any]] = []
    for p in target:
        live = p["pit_quality"] != BACKFILL
        rt = _t(p["available_time"]) if live else None
        if live and rt is None:
            continue
        exps: dict[str, dict[str, Any]] = {}
        basis: dict[str, int] = {}
        for m in EXPECTATION_METHODS:
            e = expectation(target, rt, m, p["period"])
            if e is None:
                exps[m] = {"expectation": None, "surprise": None, "surprise_z": None}
                continue
            s = float(p["value"]) - e
            prior = hist[m][-SCALE_WINDOW:]
            z = None
            if len(prior) >= SCALE_MIN:
                sd = statistics.pstdev([v for v, _ in prior])
                z = s / sd if sd > 0 else None
            if m == PRIMARY:
                basis = {"backfill": sum(1 for _, b in prior if b),
                         "live": sum(1 for _, b in prior if not b)}
            hist[m].append((s, not live))
            exps[m] = {"expectation": round(e, 6), "surprise": round(s, 6),
                       "surprise_z": None if z is None else round(z, 6)}
        prim = exps[PRIMARY]
        if not live or prim["expectation"] is None:
            continue
        out.append({"period": p["period"], "available_time": p["available_time"],
                    "pit_quality": p["pit_quality"], "actual": float(p["value"]),
                    "method": PRIMARY, "expectation": prim["expectation"],
                    "surprise": prim["surprise"], "surprise_z": prim["surprise_z"],
                    "expectations": exps, "scale_basis": basis})
    return out


# --------------------------------------------------------------------------------- outputs
def lake_name(name: str) -> str:
    return f"rcs_{name}"


def write_lake(paths: Paths, name: str, rows: list[dict[str, Any]]) -> str | None:
    """LIVE rows only (the caller passes `surprises`, which never emits a backfilled print)."""
    import pandas as pd
    if not rows:
        return None
    paths.series.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame([{"event_time": f"{r['period']}-01T00:00:00+00:00",
                        "available_time": r["available_time"], "value": r["surprise_z"],
                        "surprise_z": r["surprise_z"], "surprise": r["surprise"],
                        "actual": r["actual"], "expectation": r["expectation"],
                        "method": r["method"], "pit_quality": r["pit_quality"],
                        "source_id": SOURCE_ID,
                        "vintage_id": f"{SOURCE_ID}:{r['available_time']}"} for r in rows])
    target = paths.series / f"{lake_name(name)}.csv"
    tmp = target.with_suffix(f".tmp{os.getpid()}")
    df.to_csv(tmp, index=False)
    os.replace(tmp, target)
    return target.name


def allowed(paths: Paths, symbols: Iterable[str]) -> tuple[list[str], dict[str, str]]:
    """Symbols the registry holds AND the two-lane policy admits for the family. Fails closed."""
    try:
        from research.universe_policy import may_hypothesise
    except Exception as exc:
        return [], {"universe_policy": f"BLOCKED_DEPENDENCY:research.universe_policy "
                                       f"({type(exc).__name__})"}
    uni = _read(paths.universe, {}) or {}
    ok: list[str] = []
    skipped: dict[str, str] = {}
    for sym in symbols:
        try:
            admit = sym in uni and bool(may_hypothesise(sym, FAMILY))
        except Exception:
            admit = False
        if admit:
            ok.append(sym)
        else:
            skipped[sym] = "not in the universe registry or not admitted for the family"
    return ok, skipped


def build_cells(st: State, symbols: list[str], n_live: int, now: datetime,
                grounds: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    from proposer_common import candidate
    src = lake_name(st.name)
    g = grounds.get(st.region) or {}
    cells: list[dict[str, Any]] = []
    for sym in symbols:
        prior = st.priors[sym]
        for thr, side, hold in product(*CELL_GRID.values()):
            c = candidate(SEAT, sym, FAMILY,
                          {"source": src, "prior_sign": prior, "column": "surprise_z",
                           "threshold": thr, "side": side, "hold_days": hold},
                          (f"{g.get('institution') or st.region} publishes {st.name} on its "
                           f"release calendar; the print against the desk's point-in-time naive "
                           f"expectation is a surprise, and {sym} moves with surprise x the "
                           f"declared prior ({'+' if prior > 0 else '-'}) after the desk could "
                           "first read it"),
                          f"{FAMILY} {sym} <- {st.name} ({thr} sd, side {side})",
                          {"source_row": st.route, "series": src, "n_live_releases": n_live})
            c.update({"symbols": [sym], "prior_sign": prior,
                      "available_time": _iso(now), "event_time": _iso(now),
                      "source_culture": "official/statistics", "participant_structure": "policy",
                      "failure_mode_hypothesis": (
                          "fails when the print is anticipated by a consensus the naive "
                          "expectation does not see, or when the reaction is complete inside "
                          "the release bar"),
                      "crowding_prior": "high",
                      "required_data": [f"desks/mt5/data/lake/series/{src}.csv"],
                      "falsifier": (f"the drift of {sym} after {src} surprises beyond {thr} sd "
                                    "is no larger than after placebo-shifted release dates, or "
                                    "its sign contradicts the declared prior")})
            cells.append(c)
    return cells


def _donate(seat: str, cands: list[dict[str, Any]], tests_run: int) -> dict[str, Any]:
    if not cands:
        return {"donated": 0, "path": None}
    from proposer_common import donate, donation_counts
    path = donate(seat, cands, tests_run)
    return {**donation_counts(), "path": str(path) if path else None}


MISSED_GROWTH = {
    "route": ("{rid}: {why}. Every release this route would have stamped is an event the "
              "desk cannot test until the route reads again"),
    "region": ("{region}: verdict {verdict} -- {why}. Its prints stay unstamped and its "
               "currency untested by this lane"),
    "history": ("{name}: {have} scaled live releases of {need} needed before a cell is minted; "
                "monthly prints add one a month"),
}


# -------------------------------------------------------------------------------- the pass
def _due(route: Route, st: Mapping[str, Any], now: datetime) -> bool:
    last = _t(st.get("last_attempt"))
    if last is None:
        return True
    lo, hi = route.window_utc
    hot = now.weekday() < 5 and lo <= now.hour <= hi
    return now - last >= timedelta(hours=1 if hot else route.slow_h) - timedelta(minutes=5)


def run(paths: Paths = Paths(), *, fetch: bool = True, dry_run: bool = False,
        get: Getter | None = None, now: datetime | None = None,
        sleep: Callable[[float], None] = time.sleep,
        donate: Callable[[str, list[dict[str, Any]], int], dict[str, Any]] | None = None,
        budget_s: float | None = None) -> dict[str, Any]:
    now = now or _now()
    t0 = time.monotonic()
    deadline = math.inf if budget_s is None else t0 + max(0.0, budget_s - 30.0)
    grounds = load_grounds(paths.grounds)
    state = _read(paths.state, {}) or {}
    per: dict[str, Any] = state.setdefault("routes", {})
    client = Client(get or http_get, sleep=sleep, deadline=deadline)
    routes: dict[str, Any] = {}
    stores: dict[str, Store] = {}
    missed: dict[str, str] = {}
    for rid, route in ROUTES.items():
        st = per.setdefault(rid, {})
        stores[rid] = store = load_store(paths, rid)
        rec: dict[str, Any] = {"regions": list(route.regions)}
        stop = st.get("hard_stop") or {}
        until = _t(stop.get("until"))
        why = region_refusal(route.regions, grounds)
        if why:
            status = why.split(":", 1)[0]
            rec["why"] = why
        elif not fetch:
            status = "NO_FETCH"
        elif stop and (stop.get("until") is None or (until and until > now)):
            status = "HARD_STOP"
            rec["why"] = f"HARD_STOP:{stop.get('code')} (held since {stop.get('at')})"
        elif not _due(route, st, now):
            status = "NOT_DUE"
        else:
            st["last_attempt"] = _iso(now)
            try:
                url = route.url(now)
                refusal = access_refusal(route, url, client, grounds)
                if refusal:
                    raise Refused(refusal)
                obs = route.parse(client.fetch(url, route.post() if route.post else None))
                rec["fetch"] = {"parsed": len(obs),
                                **merge(paths, rid, store, obs, now, _t(st.get("last_ok")))}
                st["last_ok"] = _iso(now)
                status = "OK"
            except Refused as r:
                status = str(r).split(":", 1)[0]
                rec["why"] = str(r)
                if status == "BUDGET":
                    st.pop("last_attempt", None)
                if status == "HARD_STOP":
                    code = str(r).split(":", 1)[1].split()[0]
                    permanent = code in HELD_UNTIL_RELEASED
                    st["hard_stop"] = {"code": code, "at": _iso(now),
                                       "until": None if permanent
                                       else _iso(now + timedelta(hours=HARD_STOP_H))}
        if status not in ("OK", "NOT_DUE", "NO_FETCH"):
            missed[rid] = MISSED_GROWTH["route"].format(rid=rid, why=rec.get("why", status))
        rec["status"] = status
        rec["store_rows"] = len(store)
        routes[rid] = rec
    states: dict[str, Any] = {}
    grid: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    lake: list[str] = []
    for s in STATES:
        rows = surprises(points(stores[s.route], s.base), s.kind)
        scaled = [x for x in rows if x["surprise_z"] is not None]
        syms, skipped = allowed(paths, s.priors)
        latest = rows[-1] if rows else None
        states[s.name] = ({"status": UNMEASURED, "live_releases": 0} if latest is None else
                          {**{k: latest[k] for k in ("period", "actual", "expectation",
                                                     "surprise", "surprise_z", "available_time",
                                                     "pit_quality", "scale_basis")},
                           "live_releases": len(rows), "scaled": len(scaled)})
        states[s.name].update({"symbols": syms, "priors": s.priors, "region": s.region})
        if skipped:
            states[s.name]["symbols_skipped"] = skipped
        if not dry_run and (w := write_lake(paths, s.name, scaled)):
            lake.append(w)
        if len(scaled) < MIN_LIVE_RELEASES:
            states[s.name]["missed_growth"] = MISSED_GROWTH["history"].format(
                name=s.name, have=len(scaled), need=MIN_LIVE_RELEASES)
        else:
            grid += build_cells(s, syms, len(scaled), now, grounds)
        for ev in rows:
            if syms:
                events.append({"at": ev["available_time"], "kind": "release_calendar",
                               "name": s.name, "instruments": syms, "actual": ev["actual"],
                               "consensus": ev["expectation"], "consensus_method": ev["method"],
                               "surprise": ev["surprise"], "surprise_z": ev["surprise_z"],
                               "period": ev["period"], "pit_quality": ev["pit_quality"],
                               "region": s.region, "source": s.route})
    for region, g in sorted(grounds.items()):
        if g.get("verdict") != "CONFIRMED" or not g.get("built"):
            missed[f"region:{region}"] = MISSED_GROWTH["region"].format(
                region=region, verdict=g.get("verdict"), why=g.get("why"))
    events.sort(key=lambda e: (e["at"], e["name"]))
    don: dict[str, Any] = {"donated": 0}
    if not dry_run:
        don = (donate or _donate)(SEAT, grid, len(grid))
        _atomic(paths.state, state)
        _atomic(paths.clock, {
            "generated_at": _iso(now), "writer": "research/release_calendar_states.py",
            "rule": ("one row per LIVE headline print: `at` is its point-in-time available_time; "
                     "`consensus` is the desk's own naive expectation (`consensus_method`) from "
                     "prints known before the release, not a paid consensus"),
            "n_events": len(events), "events": events})
    verdicts: dict[str, list[str]] = {}
    for region, g in sorted(grounds.items()):
        verdicts.setdefault(str(g.get("verdict")), []).append(region)
    doc = {"generated_at": _iso(now), "writer": "research/release_calendar_states.py",
           "status": "OK" if any(r["store_rows"] for r in routes.values()) else "EMPTY",
           "grounds": {"path": "desks/mt5/data/release_calendar_grounds.json",
                       "verdicts": verdicts,
                       "built": sorted(r for r, g in grounds.items() if g.get("built"))},
           "routes": routes, "requests": client.requests, "states": states,
           "store_rows": sum(r["store_rows"] for r in routes.values()),
           "clock": {"path": "reports/RELEASE_CALENDAR_CLOCK.json", "n_events": len(events)},
           "lake": sorted(lake),
           "cells": {"grid": len(grid), "minted": int(don.get("donated") or 0),
                     "family": FAMILY, "donation": don},
           "expectation": {"methods": list(EXPECTATION_METHODS), "primary": PRIMARY},
           "missed_growth": missed, "mode": "DRY_RUN" if dry_run else "RAN",
           "seconds": round(time.monotonic() - t0, 1)}
    if not dry_run:
        _atomic(paths.report, doc)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=240.0)
    ap.add_argument("--no-fetch", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    doc = run(fetch=not a.no_fetch, dry_run=a.dry_run, budget_s=a.budget_s)
    print(json.dumps({"status": doc["status"], "store_rows": doc["store_rows"],
                      "routes": {r: v["status"] for r, v in doc["routes"].items()},
                      "cells": doc["cells"]["grid"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
