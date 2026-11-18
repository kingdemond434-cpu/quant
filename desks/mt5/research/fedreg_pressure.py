"""FEDERAL REGISTER REGULATORY PRESSURE -- how much binding US rule-making is landing, and when.

WHAT IT READS. The Federal Register's public REST API (`/api/v1/documents.json`, no key) lists
every document the Office of the Federal Register publishes. This organ reads only two document
types: final rules (`RULE`, "Rule") and proposed rules (`PRORULE`, "Proposed Rule"), and only the
fields it needs -- document number, type, publication date, effective date, comment-close date,
page length (or start/end page), agencies, the significance flag and the title.

WHAT IT PUBLISHES (ideas ledger #15):
  1. DAILY PRESSURE, BY AGENCY. Per publication day: the count and the page total of final and
     proposed rules, overall and per agency (a document signed by two agencies counts toward
     both; the overall total counts it once). `reports/FEDREG_PRESSURE.json` carries the last
     days and the busiest agencies; the per-day table is box-local.
  2. MIDNIGHT-RULE WINDOWS, FROM A CALENDAR RULE, NEVER A GUESS. The "midnight period" is the
     lame-duck stretch between a presidential election and the inauguration that follows it:
       * election day: the Tuesday next after the first Monday in November of every year
         divisible by four (3 U.S.C. 1; 2 U.S.C. 7);
       * inauguration: noon on January 20 of the following year (U.S. Const. amend. XX, s.1).
     The window is [election day, January 20] inclusive and is computed for any year, so the
     2024-11-05 .. 2025-01-20 window inside the backfill is measured, and the next one
     (2028-11-07 .. 2029-01-20) is known now. Whether the presidency changes party is NOT a
     calendar fact; the window is flagged for every presidential election and the report says so.
  3. COMMENT-DEADLINE CLUSTERS. Comment periods closing per day and per ISO week over the next
     `CLUSTER_AHEAD_DAYS`, and a point-in-time series: on each publication day D, the number of
     documents already published whose comment period closes in (D, D + 7 days].
  4. AN EVENT CLOCK FOR EFFECTIVE DATES. `reports/FEDREG_EFFECTIVE_CLOCK.json`: significant final
     rules (the API's `significant` flag, or a page length at or above the store's own 90th
     percentile of final-rule length) with their effective date, agency and size, upcoming and
     recent. It is shaped as a calendar (`events[]` with `at`, `kind`, `instruments`), and
     `event_response_atlas.load_events` reads it as one of its grounds, so effective dates that
     have passed are measured against the tape like every other dated event.
  5. CELLS. `exogenous_conditioner` cells on US500 and US2000 only (the broad index and the
     small-cap index, which carries the most domestic regulatory exposure), through
     `proposer_common.donate`, a ring slice per pass, every one charged to the trial census.
     `universe_policy.may_hypothesise` is asked for each symbol and the registry must hold it.

ONE PASS (hourly leg `fedreg_pressure`, `--once --budget-s 240`). The Register publishes once a
business day, so the leg FETCHES only when the last complete pull is older than `FETCH_EVERY_H`;
the other passes rebuild the report, the clock and the cells from the store (status NOT_DUE).
  * TERMS, REFUSED HOSTS, ROBOTS -- in that order, each failing closed by name: the terms row
    below must read `machine_use_allowed: True`; `libs.data.refused_hosts` must not list the host;
    www.federalregister.gov/robots.txt must allow `/api/v1/documents.json` for our agent (only a
    404/410 means "no rules"; an unreadable or HTML answer refuses).
  * HARD STOP on 401 / 403 / 429 / 451: no further request this pass, the code is recorded, and
    the organ makes no request for `HARD_STOP_H` hours (451, a legal block, stays stopped until a
    person clears `hard_stop` in the state file). Honest UA, one request every `MIN_INTERVAL_S`
    seconds at most, `MAX_REQUESTS` per pass, and a wall-clock budget no request may outrun.
  * THE API IS BELIEVED ONLY WHEN IT AGREES: a row missing its document number, type or
    publication date, a type other than the two requested, or a publication date outside the
    window asked for refuses the pass as `METADATA_MISMATCH:<what>`. The documented pagination cap
    (the first 2000 results) is honoured by halving any window whose `count` exceeds it.
  * STORE, POINT-IN-TIME, APPEND-ONLY: `data/fedreg/docs/<YYYY-MM>.jsonl` (gitignored, box-local;
    raw pulled data is never committed). The first record of a document is its point-in-time
    value; a later different value (an effective date moved, a page count corrected) is appended
    as a revision beside it. Re-merging the same rows appends nothing.

POINT-IN-TIME RULE. A document published on day D is treated as available at the END of D in New
York (D+1 00:00 America/New_York) -- late by construction, since the issue is public that
morning -- or when first seen, whichever is later. A document from the organ's FIRST pull
(backfill) is available `BACKFILL_LAG_H` hours later still, because what the API returns today
for an old document may carry corrections made after it printed.

    python desks/mt5/research/fedreg_pressure.py --once [--budget-s 240] [--no-fetch] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from itertools import product
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SOURCE_ID = "fedreg_pressure"
SEAT = "fedreg_pressure"
UNMEASURED = "UNMEASURED"
HOST = "https://www.federalregister.gov"
API_PATH = "/api/v1/documents.json"
API = HOST + API_PATH
NY = ZoneInfo("America/New_York")

# ------------------------------------------------------------------ terms (checked 2026-11-18)
#: The source's terms row, in the shape `alt_proxies.TERMS_EVIDENCE` records. The quotes were read
#: on 2026-11-18 through a page reader (the build container's egress refused the host), so they
#: are short and were checked against the page's own wording; `machine_use_allowed` is the only
#: switch the collector obeys.
TERMS_EVIDENCE: dict[str, Any] = {
    "terms_url": ("https://www.federalregister.gov/reader-aids/government-policy-and-ofr-"
                  "procedures/about-this-site"),
    "terms_quote": ("'Any person may reproduce or republish any material appearing in any regular "
                    "or special edition of the Federal Register' (1 CFR 2.6); 'There are no "
                    "restrictions regarding what is reproduced, who can reproduce it, or where it "
                    "can be reproduced.'"),
    "legal_status_quote": ("the site 'is not an official legal edition of the Federal Register' "
                           "and its XML 'does not provide legal notice to the public or judicial "
                           "notice to the courts' -- counts and dates here are research inputs, "
                           "never legal citations"),
    "api_terms_url": "https://www.federalregister.gov/reader-aids/developer-resources/rest-api",
    "api_terms_quote": ("'No API keys are needed; all you need is an HTTP client or browser.' "
                        "Usage Restrictions: 'Republishers of Federal Register material are not "
                        "permitted to use official NARA or OFR logos or seals.' Pagination: "
                        "'you can only paginate through the first 2000 results.' No rate limit "
                        "is published; this organ throttles itself anyway"),
    "robots": ("www.federalregister.gov/robots.txt (read 2026-11-18): 'User-agent: *' with "
               "Disallow /documents/current, /documents/email-a-friend, /articles/search, "
               "/documents/search, /public-inspection/search, /regulations/search, /my/, /auth/; "
               "no Allow lines; nothing matches /api/. The gate below re-reads it every fetch "
               "pass and fails closed"),
    "unverified_url": ("https://www.federalregister.gov/reader-aids/using-federalregister-gov/"
                       "understanding-the-federal-register-and-its-api -- not readable from the "
                       "build container (the page reader refused it); the two pages above carry "
                       "the operative lines"),
    "attribution": "Source: Office of the Federal Register (NARA), federalregister.gov API",
    "checked_at": "2026-11-18",
    "machine_use_allowed": True,
}

# --------------------------------------------------------------- request shape (partly verified)
#: `conditions[type][]`, `per_page`, `fields[]`, `count`, `total_pages`, `next_page_url`,
#: `results[].document_number/type/publication_date/agencies/page_length/comments_close_on`
#: were seen in live answers on 2026-11-18. `effective_on`, `significant`, `start_page`,
#: `end_page`, `order` and the `publication_date` gte/lte conditions follow the API's
#: documentation and are CHECKED on every answer: a row outside the asked window refuses.
TYPES: dict[str, str] = {"RULE": "Rule", "PRORULE": "Proposed Rule"}
TYPE_CODE: dict[str, str] = {v: k for k, v in TYPES.items()}
FIELDS: tuple[str, ...] = ("document_number", "type", "publication_date", "effective_on",
                           "comments_close_on", "page_length", "start_page", "end_page",
                           "agencies", "significant", "title")
PER_PAGE = 1000
MAX_RESULTS = 2000                       # the API's documented pagination cap
WINDOW_DAYS = 31                         # ~450 rules+proposed rules a month, well under the cap

# -------------------------------------------------------------------------- pacing and stops
MIN_INTERVAL_S = 2.0
MAX_REQUESTS = 40
HARD_STOP_CODES = frozenset({401, 403, 429, 451})
HARD_STOP_H = 24
TIMEOUT = 30.0
MAX_BYTES = 16 * 1024 * 1024
ROBOTS_AGENT = "quant-desk-research"
UA = f"{ROBOTS_AGENT}/1.0 (fedreg_pressure; research; honours robots.txt)"

# ------------------------------------------------------------------------------ windows
BACKFILL_DAYS = 730                      # two years: a full z window and one midnight period
REPULL_DAYS = 7                          # later pulls re-read a week for corrections
FETCH_EVERY_H = 6                        # the Register prints once a business day
BACKFILL_LAG_H = 24
#: One year of publication days: every season of the regulatory year (fiscal-year end, the
#: December push) sits in the baseline, so a calendar effect cannot pass as pressure.
Z_WINDOW = 250
MIN_POINTS = Z_WINDOW
#: The series is already stamped at the end of the publication day in New York; 4 hours more
#: absorbs the broker clock's offset from UTC (up to +3) and an hour of margin.
LAG_HOURS = 4
COMMENT_HORIZON_D = 7
CLUSTER_AHEAD_DAYS = 60
CLOCK_BACK_DAYS = 400
SIZE_QUANTILE = 0.90
MIN_SIZE_SAMPLE = 50
#: US cash open: the first moment the index CFDs trade the regime a rule's effective date sets.
EFFECTIVE_LOCAL = (9, 30)

INDEX_CFDS: tuple[str, ...] = ("US500", "US2000")
#: Prior sign of more rule-making on the indices: compliance cost and uncertainty weigh on
#: earnings. The grid judges both sides anyway (`side_when_high` +1 and -1).
PRIOR = -1
CELL_SERIES: tuple[str, ...] = ("rule__pages", "prorule__pages", "comments__close_next7d")

MISSED_GROWTH = {
    "blocked": ("source not fetched: no regulatory-pressure series reaches a US500 / US2000 "
                "exogenous_conditioner cell, and no rule effective date reaches the event clock, "
                "until it is"),
    "history": ("series {name} stands down until it holds {need} publication days (has {have}): "
                "a z without a year's baseline would flag the regulatory calendar as pressure"),
    "size": ("size threshold UNMEASURED ({have} final rules < {need}): the clock lists only rules "
             "the API flags significant, so long unflagged rules miss the event lane"),
}


@dataclass(frozen=True)
class Paths:
    desk: Path = DESK

    @property
    def store(self) -> Path:
        return self.desk / "data" / "fedreg"

    @property
    def docs(self) -> Path:
        return self.store / "docs"

    @property
    def state(self) -> Path:
        return self.store / "state.json"

    @property
    def daily(self) -> Path:
        return self.store / "daily.json"

    @property
    def series(self) -> Path:
        return self.desk / "data" / "lake" / "series"

    @property
    def universe(self) -> Path:
        return self.desk / "data" / "universe" / "universe.json"

    @property
    def report(self) -> Path:
        return self.desk / "reports" / "FEDREG_PRESSURE.json"

    @property
    def clock(self) -> Path:
        return self.desk / "reports" / "FEDREG_EFFECTIVE_CLOCK.json"


class Refused(Exception):
    """A named refusal: METADATA_MISMATCH:..., ROBOTS_REFUSED:..., HARD_STOP:<code>, ..."""


# ------------------------------------------------------------------------------- io helpers
def _now() -> datetime:
    return datetime.now(UTC)


def _read(p: Path, default: Any) -> Any:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def _atomic(p: Path, doc: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(f".tmp{os.getpid()}")
    tmp.write_text(json.dumps(doc, indent=1, sort_keys=True, default=str), "utf-8")
    os.replace(tmp, p)


def _t(s: Any) -> datetime | None:
    if not s:
        return None
    try:
        d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def _iso(d: datetime) -> str:
    return d.astimezone(UTC).isoformat(timespec="seconds")


def _day(s: Any) -> date | None:
    try:
        return date.fromisoformat(str(s or "")[:10])
    except ValueError:
        return None


def _int(v: Any) -> int | None:
    try:
        x = int(v)
    except (TypeError, ValueError):
        return None
    return x if x >= 0 else None


def end_of_day_ny(d: date) -> datetime:
    """D+1 00:00 in New York, as UTC: the end of a publication day on the Register's own clock."""
    return datetime.combine(d + timedelta(days=1), datetime.min.time(), tzinfo=NY).astimezone(UTC)


# ------------------------------------------------------------------------ midnight calendar
def election_day(year: int) -> date | None:
    """The Tuesday next after the first Monday in November (3 U.S.C. 1), presidential years only
    (years divisible by four). None for any other year."""
    if year % 4:
        return None
    first = date(year, 11, 1)
    first_monday = first + timedelta(days=(0 - first.weekday()) % 7)
    return first_monday + timedelta(days=1)


def inauguration_day(election_year: int) -> date:
    """January 20 of the year after the election (U.S. Const. amend. XX, s.1)."""
    return date(election_year + 1, 1, 20)


def midnight_window(election_year: int) -> tuple[date, date] | None:
    e = election_day(election_year)
    return None if e is None else (e, inauguration_day(election_year))


def midnight_state(d: date) -> dict[str, Any]:
    """Is `d` inside a midnight window; which one; and the next window from `d`."""
    for y in (d.year - 1, d.year):
        w = midnight_window(y)
        if w and w[0] <= d <= w[1]:
            return {"in_window": True, "election_year": y, "start": w[0].isoformat(),
                    "end": w[1].isoformat(), "days_to_inauguration": (w[1] - d).days}
    y = d.year + (-d.year) % 4
    w = midnight_window(y)
    if w is None or w[0] <= d:          # already past this cycle's election: the next one
        y += 4
        w = midnight_window(y)
    assert w is not None
    return {"in_window": False, "next_election_year": y, "next_start": w[0].isoformat(),
            "next_end": w[1].isoformat(), "days_to_next": (w[0] - d).days}


# ------------------------------------------------------------------------------- the fetcher
#: (url) -> (HTTP status, body). Injected in tests; `http_get` on the box.
Getter = Callable[[str], tuple[int, bytes]]


def http_get(url: str) -> tuple[int, bytes]:
    """One GET with the honest UA; every redirect hop is checked against the refused hosts.
    Returns the status instead of raising on 4xx/5xx."""
    from libs.data import refused_hosts
    handlers: list[Any] = [refused_hosts.RefusingRedirectHandler()]
    ctx = _tls()
    if ctx is not None:
        handlers.append(urllib.request.HTTPSHandler(context=ctx))
    opener = urllib.request.build_opener(*handlers)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with opener.open(req, timeout=TIMEOUT) as resp:
            return int(getattr(resp, "status", 200) or 200), bytes(resp.read(MAX_BYTES))
    except urllib.error.HTTPError as e:
        return int(e.code), b""


def _tls() -> Any:
    try:
        from research import asia_collector
        make: Any = asia_collector._tls_context
        return make()
    except Exception:
        return None


class Client:
    """Every request of a pass: throttled, counted, hard-stopped, bounded by the wall clock."""

    def __init__(self, get: Getter, *, sleep: Callable[[float], None] = time.sleep,
                 max_requests: int = MAX_REQUESTS, min_interval_s: float = MIN_INTERVAL_S,
                 deadline: float = math.inf) -> None:
        self.get, self.sleep = get, sleep
        self.max_requests, self.min_interval_s = max_requests, min_interval_s
        self.deadline = deadline
        self.requests = 0
        self._last = -math.inf

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

    def json(self, url: str) -> dict[str, Any]:
        self._pace()
        try:
            status, body = self.get(url)
        except Exception as exc:
            raise Refused(f"FETCH_ERROR:{type(exc).__name__}: {str(exc)[:160]}") from None
        if status in HARD_STOP_CODES:
            raise Refused(f"HARD_STOP:{status}")
        if status != 200:
            raise Refused(f"HTTP_{status}:{urllib.parse.urlsplit(url).path}")
        try:
            doc = json.loads(body.decode("utf-8", errors="replace"))
        except ValueError:
            raise Refused("UNPARSEABLE:documents.json did not answer JSON") from None
        if not isinstance(doc, dict) or not isinstance(doc.get("results", []), list):
            raise Refused("METADATA_MISMATCH:answer is not an object with a results list")
        return doc


# ------------------------------------------------------------------------------- the gates
def robots_refusal(get: Getter, url: str = API) -> str | None:
    """None when robots.txt allows `url` for our agent, else why not. Only 404 or 410 means "no
    rules"; anything unreadable, an HTML page or a stop code refuses."""
    parts = urllib.parse.urlsplit(url)
    try:
        status, body = get(f"{parts.scheme}://{parts.netloc}/robots.txt")
    except Exception as exc:
        return f"ROBOTS_REFUSED:robots.txt unreadable ({type(exc).__name__})"
    if status in (404, 410):
        return None
    if status != 200:
        return f"ROBOTS_REFUSED:robots.txt answered HTTP {status}"
    text = body.decode("utf-8", errors="replace")
    if text.lstrip()[:15].lower().startswith(("<!doctype", "<html")):
        return "ROBOTS_REFUSED:robots.txt answered HTML"
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(text.splitlines())
    if not rp.can_fetch(ROBOTS_AGENT, url):
        return f"ROBOTS_REFUSED:robots.txt disallows {parts.path}"
    return None


def access_refusal(get: Getter) -> str | None:
    """Terms, then the refused-hosts list, then robots -- before any API request."""
    if TERMS_EVIDENCE.get("machine_use_allowed") is not True:
        return "BLOCKED_ON_TERMS:machine_use_allowed is not true"
    from libs.data import refused_hosts
    why = refused_hosts.refusal(API)
    if why:
        return f"BLOCKED_ON_TERMS:{why}"
    return robots_refusal(get, API)


# ------------------------------------------------------------------------------- data pull
def query_url(start: date, end: date) -> str:
    q: list[tuple[str, str]] = [("per_page", str(PER_PAGE)), ("order", "oldest"),
                                ("conditions[publication_date][gte]", start.isoformat()),
                                ("conditions[publication_date][lte]", end.isoformat())]
    q += [("conditions[type][]", t) for t in TYPES]
    q += [("fields[]", f) for f in FIELDS]
    return API + "?" + urllib.parse.urlencode(q)


def _next_url(doc: Mapping[str, Any]) -> str | None:
    """The API's own next page, only on our host and our path; anything else ends the walk."""
    nxt = doc.get("next_page_url")
    if not nxt:
        return None
    parts = urllib.parse.urlsplit(str(nxt))
    if f"{parts.scheme}://{parts.netloc}" != HOST or not parts.path.startswith("/api/v1/"):
        raise Refused(f"METADATA_MISMATCH:next_page_url leaves {HOST}{API_PATH}")
    return str(nxt)


def parse_rows(results: Any, start: date, end: date) -> list[dict[str, Any]]:
    """`results[]` -> normalised rows. A row without its number, type or date, a type not asked
    for, or a date outside the window is a METADATA_MISMATCH. Absent optional fields are None
    (UNMEASURED), never zero."""
    out: list[dict[str, Any]] = []
    for r in results if isinstance(results, list) else []:
        if not isinstance(r, dict):
            raise Refused("METADATA_MISMATCH:result row is not an object")
        miss = [k for k in ("document_number", "type", "publication_date") if not r.get(k)]
        if miss:
            raise Refused(f"METADATA_MISMATCH:result row lacks {miss}")
        code = TYPE_CODE.get(str(r["type"]))
        if code is None:
            raise Refused(f"METADATA_MISMATCH:type {str(r['type'])[:30]!r} was not asked for")
        pub = _day(r["publication_date"])
        if pub is None or not start <= pub <= end:
            raise Refused(f"METADATA_MISMATCH:publication_date {str(r['publication_date'])[:12]!r}"
                          f" outside {start}..{end}")
        pages = _int(r.get("page_length"))
        sp, ep = _int(r.get("start_page")), _int(r.get("end_page"))
        if pages is None and sp is not None and ep is not None and ep >= sp:
            pages = ep - sp + 1
        agencies = sorted({str(a.get("slug") or a.get("name") or a.get("raw_name") or "")
                           for a in (r.get("agencies") or []) if isinstance(a, dict)} - {""})
        eff, cc = _day(r.get("effective_on")), _day(r.get("comments_close_on"))
        sig = r.get("significant")
        out.append({"document_number": str(r["document_number"]), "type": code,
                    "publication_date": pub.isoformat(),
                    "effective_on": eff.isoformat() if eff else None,
                    "comments_close_on": cc.isoformat() if cc else None,
                    "page_length": pages, "agencies": agencies or ["unknown"],
                    "significant": sig if isinstance(sig, bool) else None,
                    "title": str(r.get("title") or "")[:200]})
    return out


def pull_window(client: Client, start: date, end: date) -> list[dict[str, Any]]:
    """Every page of one publication-date window. A window whose `count` exceeds the API's
    pagination cap is halved and each half pulled, so no result is silently cut off."""
    doc = client.json(query_url(start, end))
    count = _int(doc.get("count"))
    if count is not None and count > MAX_RESULTS:
        if start >= end:
            raise Refused(f"METADATA_MISMATCH:{count} results on one day exceed the "
                          f"{MAX_RESULTS} pagination cap")
        mid = start + timedelta(days=(end - start).days // 2)
        return pull_window(client, start, mid) + pull_window(client, mid + timedelta(days=1), end)
    rows = parse_rows(doc.get("results"), start, end)
    url = _next_url(doc)
    while url and len(rows) < MAX_RESULTS:
        doc = client.json(url)
        page = parse_rows(doc.get("results"), start, end)
        if not page:
            break
        rows += page
        url = _next_url(doc)
    return rows


def windows(start: date, end: date, days: int = WINDOW_DAYS) -> list[tuple[date, date]]:
    out: list[tuple[date, date]] = []
    a = start
    while a <= end:
        b = min(end, a + timedelta(days=days - 1))
        out.append((a, b))
        a = b + timedelta(days=1)
    return out


# --------------------------------------------------------------------- point-in-time store
TRACKED = ("type", "publication_date", "effective_on", "comments_close_on", "page_length",
           "agencies", "significant")


def load_store(paths: Paths) -> dict[str, dict[str, Any]]:
    """document_number -> {first record..., last: latest tracked values, n_revisions}."""
    store: dict[str, dict[str, Any]] = {}
    if not paths.docs.exists():
        return store
    for f in sorted(paths.docs.glob("*.jsonl")):
        try:
            lines = f.read_text("utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            k = r.get("document_number") if isinstance(r, dict) else None
            if not k:
                continue
            last = {f2: r.get(f2) for f2 in TRACKED}
            if k not in store:
                store[k] = {**r, "last": last, "n_revisions": 0}
            else:
                store[k]["last"] = last
                store[k]["n_revisions"] = int(store[k].get("n_revisions") or 0) + 1
                store[k]["revision_time"] = r.get("first_seen_at")
    return store


def merge(paths: Paths, store: dict[str, dict[str, Any]], rows: Iterable[Mapping[str, Any]],
          seen: datetime, backfill: bool) -> dict[str, int]:
    """Append what is new: a document never seen, or tracked values that differ from the last
    stored (a revision). The same rows merged twice append nothing."""
    by_month: dict[str, list[dict[str, Any]]] = {}
    added = revised = 0
    stamp = _iso(seen)
    for r in rows:
        k = str(r["document_number"])
        vals = {f: r.get(f) for f in TRACKED}
        cur = store.get(k)
        if cur is None:
            pub = _day(r["publication_date"])
            assert pub is not None
            avail = end_of_day_ny(pub)
            avail = avail + timedelta(hours=BACKFILL_LAG_H) if backfill else max(avail, seen)
            rec = {"document_number": k, **vals, "title": r.get("title") or "",
                   "first_seen_at": stamp, "available_time": _iso(avail),
                   "pit_quality": "backfill" if backfill else "live", "revision": False}
            store[k] = {**rec, "last": vals, "n_revisions": 0}
            added += 1
        elif cur.get("last") != vals:
            rec = {"document_number": k, **vals, "first_seen_at": stamp, "revision": True}
            cur["last"] = vals
            cur["n_revisions"] = int(cur.get("n_revisions") or 0) + 1
            cur["revision_time"] = stamp
            revised += 1
        else:
            continue
        by_month.setdefault(str(r["publication_date"])[:7], []).append(rec)
    if by_month:
        paths.docs.mkdir(parents=True, exist_ok=True)
    for month, recs in sorted(by_month.items()):
        with (paths.docs / f"{month}.jsonl").open("a", encoding="utf-8") as fh:
            for rec in recs:
                fh.write(json.dumps(rec, sort_keys=True) + "\n")
    return {"added": added, "revised": revised}


# ------------------------------------------------------------------------------ aggregation
def daily_aggregate(store: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    """Per publication day: count and pages per type, overall and per agency, from each
    document's FIRST-SEEN (point-in-time) values. Pages a document does not report are counted
    in `pages_unmeasured`, never as zero pages."""
    out: dict[str, dict[str, Any]] = {}
    for r in store.values():
        day, typ = str(r.get("publication_date") or ""), str(r.get("type") or "")
        if not day or typ not in TYPES:
            continue
        d = out.setdefault(day, {"available_time": str(r["available_time"]),
                                 "totals": {t: {"n": 0, "pages": 0, "pages_unmeasured": 0}
                                            for t in TYPES}, "by_agency": {}})
        d["available_time"] = max(d["available_time"], str(r["available_time"]))
        pages = r.get("page_length")
        cells = [d["totals"][typ]]
        for ag in r.get("agencies") or ["unknown"]:
            a = d["by_agency"].setdefault(ag, {t: {"n": 0, "pages": 0} for t in TYPES})
            cells.append(a[typ])
        for c in cells:
            c["n"] += 1
            if isinstance(pages, int):
                c["pages"] += pages
            elif "pages_unmeasured" in c:
                c["pages_unmeasured"] += 1
    return dict(sorted(out.items()))


def comment_close_next(store: Mapping[str, Mapping[str, Any]], days: Iterable[str],
                       horizon: int = COMMENT_HORIZON_D) -> dict[str, int]:
    """Per observation day D: documents published on or before D whose FIRST-SEEN comment period
    closes in (D, D + horizon]. Point-in-time: nothing published after D is counted."""
    rows = sorted((str(r["publication_date"]), str(r["comments_close_on"]))
                  for r in store.values() if r.get("comments_close_on"))
    out: dict[str, int] = {}
    for d in days:
        dd = _day(d)
        if dd is None:
            continue
        hi = (dd + timedelta(days=horizon)).isoformat()
        out[d] = sum(1 for pub, cc in rows if pub <= d and d < cc <= hi)
    return out


def comment_clusters(store: Mapping[str, Mapping[str, Any]], today: date,
                     ahead: int = CLUSTER_AHEAD_DAYS) -> dict[str, Any]:
    """Comment periods closing per day and per ISO week over the next `ahead` days, on the latest
    known close dates (a reopened or extended period moves its document)."""
    per_day: dict[str, int] = {}
    per_week: dict[str, int] = {}
    agencies: dict[str, int] = {}
    hi = today + timedelta(days=ahead)
    for r in store.values():
        cc = _day((r.get("last") or r).get("comments_close_on"))
        if cc is None or not today <= cc <= hi:
            continue
        per_day[cc.isoformat()] = per_day.get(cc.isoformat(), 0) + 1
        iso = cc.isocalendar()
        wk = f"{iso[0]}-W{iso[1]:02d}"
        per_week[wk] = per_week.get(wk, 0) + 1
        for ag in (r.get("last") or r).get("agencies") or ["unknown"]:
            agencies[ag] = agencies.get(ag, 0) + 1
    top = sorted(per_week.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
    return {"from": today.isoformat(), "to": hi.isoformat(), "per_day": dict(sorted(
        per_day.items())), "per_week": dict(sorted(per_week.items())),
            "busiest_weeks": [{"week": w, "closing": n} for w, n in top],
            "busiest_agencies": dict(sorted(agencies.items(), key=lambda kv: -kv[1])[:10]),
            "n_closing": sum(per_day.values())}


def build_series(store: Mapping[str, Mapping[str, Any]],
                 daily: Mapping[str, Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Lake series, one point per publication day, each with its PIT stamp."""
    days = list(daily)
    nxt = comment_close_next(store, days)
    series: dict[str, list[dict[str, Any]]] = {}
    for day, d in daily.items():
        dd = _day(day)
        assert dd is not None
        base = {"event_time": f"{day}T00:00:00+00:00", "available_time": d["available_time"]}
        vals = {"rule__count": d["totals"]["RULE"]["n"],
                "rule__pages": d["totals"]["RULE"]["pages"],
                "prorule__count": d["totals"]["PRORULE"]["n"],
                "prorule__pages": d["totals"]["PRORULE"]["pages"],
                "comments__close_next7d": nxt.get(day, 0),
                "calendar__midnight": int(midnight_state(dd)["in_window"])}
        for name, v in vals.items():
            series.setdefault(name, []).append({**base, "value": v})
    return series


def lake_name(name: str) -> str:
    return f"fedreg_{name}"


def write_lake(paths: Paths, series: Mapping[str, list[dict[str, Any]]]) -> list[str]:
    import pandas as pd
    paths.series.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for name, pts in sorted(series.items()):
        if not pts:
            continue
        df = pd.DataFrame([{**p, "source_id": SOURCE_ID,
                            "vintage_id": f"{SOURCE_ID}:{p['available_time']}"} for p in pts])
        target = paths.series / f"{lake_name(name)}.csv"
        tmp = target.with_suffix(f".tmp{os.getpid()}")
        df.to_csv(tmp, index=False)
        os.replace(tmp, target)
        written.append(target.name)
    return written


def zscore(values: list[float], window: int = Z_WINDOW, min_n: int = MIN_POINTS) -> float | None:
    """The last value against the `window` STRICTLY EARLIER values; None below `min_n`."""
    if len(values) < 2:
        return None
    prior, x = values[:-1][-window:], values[-1]
    if len(prior) < min_n:
        return None
    m = sum(prior) / len(prior)
    sd = math.sqrt(sum((v - m) ** 2 for v in prior) / len(prior))
    return (x - m) / sd if sd > 0 else None


def regime(series: Mapping[str, list[dict[str, Any]]], now: datetime) -> dict[str, Any]:
    """The latest point available at `now` per series and its z; the midnight state of today;
    and the MEASURED pages-per-day inside versus outside midnight windows."""
    out: dict[str, Any] = {"series": {}}
    for name, pts in sorted(series.items()):
        known = [p for p in pts if (_t(p["available_time"]) or now) <= now]
        if not known:
            out["series"][name] = {"status": UNMEASURED}
            continue
        z = None if name == "calendar__midnight" else zscore([float(p["value"]) for p in known])
        out["series"][name] = {"day": known[-1]["event_time"][:10], "value": known[-1]["value"],
                               "z": None if z is None else round(z, 4), "n_days": len(known)}
    out["midnight"] = midnight_state(now.astimezone(NY).date())
    inside = [p["value"] for p, m in zip(series.get("rule__pages", []),
                                         series.get("calendar__midnight", []), strict=False)
              if m["value"] == 1]
    outside = [p["value"] for p, m in zip(series.get("rule__pages", []),
                                          series.get("calendar__midnight", []), strict=False)
               if m["value"] == 0]
    out["midnight_measured"] = (
        {"rule_pages_per_day_inside": round(sum(inside) / len(inside), 2),
         "rule_pages_per_day_outside": round(sum(outside) / len(outside), 2),
         "n_inside": len(inside), "n_outside": len(outside)}
        if inside and outside else {"status": UNMEASURED,
                                    "why": "the store holds no days on both sides of a window"})
    return out


# ------------------------------------------------------------------------------ event clock
def size_threshold(store: Mapping[str, Mapping[str, Any]]) -> int | None:
    """The store's own 90th percentile of final-rule page length; None below the sample floor."""
    pages = sorted(int(r["page_length"]) for r in store.values()
                   if r.get("type") == "RULE" and isinstance(r.get("page_length"), int))
    if len(pages) < MIN_SIZE_SAMPLE:
        return None
    return pages[min(len(pages) - 1, math.ceil(SIZE_QUANTILE * len(pages)) - 1)]


def effective_at(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, *EFFECTIVE_LOCAL, tzinfo=NY).astimezone(UTC)


def build_clock(store: Mapping[str, Mapping[str, Any]], now: datetime,
                instruments: list[str], *, source_status: str) -> dict[str, Any]:
    """Significant final rules with an effective date in [now - CLOCK_BACK_DAYS, future): one
    calendar row each, on the latest known effective date (a delayed rule moves)."""
    thr = size_threshold(store)
    today = now.astimezone(NY).date()
    lo = today - timedelta(days=CLOCK_BACK_DAYS)
    events: list[dict[str, Any]] = []
    for r in store.values():
        last = r.get("last") or r
        if last.get("type") != "RULE":
            continue
        eff = _day(last.get("effective_on"))
        if eff is None or eff < lo:
            continue
        pages = last.get("page_length")
        by_flag = last.get("significant") is True
        by_size = thr is not None and isinstance(pages, int) and pages >= thr
        if not (by_flag or by_size):
            continue
        events.append({
            "at": _iso(effective_at(eff)), "effective_on": eff.isoformat(),
            "effective_on_first_seen": r.get("effective_on"),
            "kind": "fedreg_rule_effective", "name": str(r.get("title") or "")[:160],
            "document_number": r["document_number"], "agencies": last.get("agencies") or [],
            "page_length": pages, "significant": last.get("significant"),
            "why": "significant_flag" if by_flag else f"page_length>=p90 ({thr})",
            "publication_date": r.get("publication_date"),
            "available_time": r.get("available_time"), "instruments": list(instruments),
            "upcoming": eff >= today, "source": "federalregister.gov"})
    events.sort(key=lambda e: (e["at"], e["document_number"]))
    doc: dict[str, Any] = {
        "generated_at": _iso(now), "writer": "research/fedreg_pressure.py",
        "source_status": source_status, "kind": "fedreg_rule_effective",
        "rule": ("significant final rules (API flag, or page length >= the store's own p90 of "
                 "final-rule length); `at` is 09:30 New York on the effective date, the first "
                 "US cash session the rule binds"),
        "size_threshold_pages": thr, "n_events": len(events),
        "n_upcoming": sum(1 for e in events if e["upcoming"]), "events": events,
        "consumers": ["research/event_response_atlas.py (load_events ground fedreg_effective)"],
        "attribution": TERMS_EVIDENCE["attribution"]}
    if thr is None:
        n = sum(1 for r in store.values() if r.get("type") == "RULE"
                and isinstance(r.get("page_length"), int))
        doc["missed_growth_size"] = MISSED_GROWTH["size"].format(have=n, need=MIN_SIZE_SAMPLE)
    if not store:
        doc["status"] = UNMEASURED
    return doc


# ------------------------------------------------------------------------------------ cells
def allowed_symbols(paths: Paths) -> tuple[list[str], dict[str, str]]:
    """US500 / US2000 that the registry holds AND the two-lane policy admits. FAILS CLOSED."""
    from keyed_sources import universe_gate
    gate, blocker = universe_gate()
    if gate is None:
        return [], {"universe_policy": str(blocker)}
    uni = _read(paths.universe, {}) or {}
    ok, skipped = [], {}
    for sym in INDEX_CFDS:
        if sym in uni and gate(sym, "exogenous_conditioner"):
            ok.append(sym)
        else:
            skipped[sym] = "not in the universe registry or not hypothesis lane"
    return ok, skipped


def build_cells(series: Mapping[str, list[dict[str, Any]]], symbols: list[str], now: datetime
                ) -> tuple[list[dict[str, Any]], dict[str, str]]:
    from keyed_sources import EXO_GRID
    from proposer_common import candidate
    skipped: dict[str, str] = {}
    stamp = _iso(now)
    cells: list[dict[str, Any]] = []
    for name in CELL_SERIES:
        pts = series.get(name) or []
        if len(pts) < MIN_POINTS:
            skipped[name] = MISSED_GROWTH["history"].format(name=name, need=MIN_POINTS,
                                                            have=len(pts))
            continue
        src = lake_name(name)
        for sym in symbols:
            for t, thr, side in product(*EXO_GRID.values()):
                c = candidate(SEAT, sym, "exogenous_conditioner",
                              {"source": src, "signal": "value", "transform": t,
                               "threshold": thr, "side_when_high": side * PRIOR,
                               "lag_hours": LAG_HOURS, "z_window": Z_WINDOW},
                              f"Federal Register {name.replace('__', ' ')} is the regulatory "
                              f"pressure landing on US firms; at an extreme it conditions {sym}",
                              f"fedreg {name} ({t} {thr}) -> {sym}",
                              {"source_row": SOURCE_ID, "series": src, "arm": "direct"})
                c.update({"symbols": [sym], "available_time": stamp, "event_time": stamp,
                          "source_culture": "US/en", "participant_structure": "policy",
                          "failure_mode_hypothesis": (
                              "fails when the rule-making is anticipated in the agenda the "
                              "market already read, or when page counts measure paperwork "
                              "rather than binding cost"),
                          "crowding_prior": "low",
                          "required_data": [f"desks/mt5/data/lake/series/{src}.csv"],
                          "falsifier": (f"{src} {t} beyond {thr} sd carries no out-of-sample "
                                        f"information about {sym} H1 returns")})
                cells.append(c)
    return cells, skipped


# -------------------------------------------------------------------------------- the pass
def collect(paths: Paths, state: dict[str, Any], store: dict[str, dict[str, Any]], *,
            get: Getter, now: datetime, sleep: Callable[[float], None],
            deadline: float = math.inf) -> dict[str, Any]:
    """One fetch: gates, windows, merge. Returns the record; raises Refused by name."""
    stop = state.get("hard_stop") or {}
    until = _t(stop.get("until"))
    if stop.get("code") == 451 or (until and until > now):
        raise Refused(f"HARD_STOP:{stop.get('code')} (held since {stop.get('at')})")
    last = _t(state.get("last_success"))
    if last is not None and now - last < timedelta(hours=FETCH_EVERY_H):
        return {"status": "NOT_DUE", "requests": 0, "last_success": state.get("last_success")}
    refused = access_refusal(get)
    if refused:
        raise Refused(refused)
    client = Client(get, sleep=sleep, deadline=deadline)
    today = now.astimezone(NY).date()
    backfill = last is None
    # resume a backfill from where the last incomplete pass stopped
    start = _day(state.get("backfill_cursor")) if backfill else None
    start = start or (today - timedelta(days=BACKFILL_DAYS))
    if last is not None:
        start = min(today, last.astimezone(NY).date()) - timedelta(days=REPULL_DAYS)
    rec: dict[str, Any] = {"backfill": backfill, "added": 0, "revised": 0, "parsed": 0,
                           "windows": 0}
    complete = True
    try:
        for a, b in windows(start, today):
            try:
                rows = pull_window(client, a, b)
            except Refused as r:
                if str(r).startswith("BUDGET:"):
                    complete = False
                    rec["why_incomplete"] = str(r)
                    break
                raise
            m = merge(paths, store, rows, now, backfill)
            rec["added"] += m["added"]
            rec["revised"] += m["revised"]
            rec["parsed"] += len(rows)
            rec["windows"] += 1
            if backfill:
                state["backfill_cursor"] = (b + timedelta(days=1)).isoformat()
        rec["status"] = "OK" if rec["parsed"] else "EMPTY"
        rec["complete"] = complete
        if complete:
            state["last_success"] = _iso(now)
            state.pop("backfill_cursor", None)
    except Refused as r:
        if str(r).startswith("HARD_STOP:"):
            code = int(str(r).split(":", 1)[1])
            state["hard_stop"] = {"code": code, "at": _iso(now),
                                  "until": None if code == 451
                                  else _iso(now + timedelta(hours=HARD_STOP_H))}
        raise
    finally:
        rec["requests"] = client.requests
        state["last_requests"] = client.requests
    return rec


def run(paths: Paths = Paths(), *, fetch: bool = True, dry_run: bool = False,
        get: Getter | None = None, now: datetime | None = None,
        sleep: Callable[[float], None] = time.sleep,
        donate: Callable[[str, list[dict[str, Any]], int], dict[str, Any]] | None = None,
        budget_s: float | None = None) -> dict[str, Any]:
    now = now or _now()
    t0 = time.monotonic()
    deadline = math.inf if budget_s is None else t0 + max(0.0, budget_s - 30.0)
    state = _read(paths.state, {}) or {}
    store = load_store(paths)
    rec: dict[str, Any] = {}
    if not fetch:
        status = "NO_FETCH"
    else:
        state["last_attempt"] = _iso(now)
        try:
            rec = collect(paths, state, store, get=get or http_get, now=now, sleep=sleep,
                          deadline=deadline)
            status = str(rec.get("status"))
        except Refused as r:
            status = str(r).split(":", 1)[0]
            rec["why"] = str(r)
            rec["missed_growth"] = MISSED_GROWTH["blocked"]
        if not dry_run:
            _atomic(paths.state, state)
    daily = daily_aggregate(store)
    series = build_series(store, daily)
    symbols, sym_skipped = allowed_symbols(paths)
    clock = build_clock(store, now, symbols, source_status=status)
    clusters = comment_clusters(store, now.astimezone(NY).date())
    reg = regime(series, now)
    cells, skipped = build_cells(series, symbols, now)
    skipped.update(sym_skipped)
    from keyed_sources import PER_PASS, _donate, _ring
    take, nxt = _ring(cells, int(state.get("cell_cursor") or 0), PER_PASS)
    don: dict[str, Any] = {"donated": 0}
    lake: list[str] = []
    if not dry_run:
        lake = write_lake(paths, series)
        _atomic(paths.daily, daily)
        don = (donate or _donate)(SEAT, take, len(take))
        state["cell_cursor"] = nxt
        _atomic(paths.state, state)
        _atomic(paths.clock, clock)
    recent = dict(list(daily.items())[-10:])
    agencies: dict[str, int] = {}
    for d in recent.values():
        for ag, v in d["by_agency"].items():
            agencies[ag] = agencies.get(ag, 0) + v["RULE"]["pages"] + v["PRORULE"]["pages"]
    doc = {"generated_at": _iso(now), "writer": "research/fedreg_pressure.py",
           "source": SOURCE_ID, "terms": TERMS_EVIDENCE, "status": status, "fetch": rec,
           "store_rows": len(store), "days": len(daily),
           "daily_recent": {k: v["totals"] for k, v in recent.items()},
           "busiest_agencies_recent_pages": dict(sorted(agencies.items(),
                                                        key=lambda kv: -kv[1])[:10]),
           "regime": reg, "comment_clusters": clusters,
           "clock": {"path": "reports/FEDREG_EFFECTIVE_CLOCK.json",
                     "n_events": clock["n_events"], "n_upcoming": clock["n_upcoming"],
                     "size_threshold_pages": clock["size_threshold_pages"]},
           "lake": lake, "symbols": symbols,
           "cells": {"grid": len(cells), "built": len(take),
                     "minted": int(don.get("donated") or 0),
                     "trials_charged": 0 if dry_run else len(take), "skipped": skipped,
                     "donation": don},
           "mode": "DRY_RUN" if dry_run else "RAN",
           "seconds": round(time.monotonic() - t0, 1)}
    if not store:
        doc["missed_growth"] = MISSED_GROWTH["blocked"]
    if not dry_run:
        _atomic(paths.report, doc)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=240.0,
                    help="wall-clock seconds for the pass; no request starts that could outrun it")
    ap.add_argument("--no-fetch", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    doc = run(fetch=not a.no_fetch, dry_run=a.dry_run, budget_s=a.budget_s)
    print(json.dumps({"status": doc["status"], "store_rows": doc["store_rows"],
                      "clock": doc["clock"], "cells": {k: doc["cells"][k] for k in
                                                      ("grid", "built", "minted")}},
                     sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
