"""Four scheduled public releases, fetched on their own clocks, kept as FIRST PRINTS.

Ideas N4, N6, N7 and N8 of the "Closing the gap to tier 1 firms" batch (noon CRO pass,
2026-11-11 / 2026-11-13). Each is a public, free, terms-clean release whose SIZE against a
pre-stated baseline is the tradeable surprise:

  boj_rinban         N4  Bank of Japan outright JGB purchase operations (rinban): per operation
                         the amount offered to the Bank, the amount it bought and the amount it
                         had announced it would buy. Free to reuse with attribution.
  tic_flow           N6  US Treasury International Capital (TIC) monthly net foreign purchases of
                         US long-term securities (Treasuries, agencies, corporates, equities).
                         US-government public domain.
  usda_export_sales  N7  USDA FAS weekly export sales: net sales of corn, all wheat and soybeans
                         for the week ending the previous Thursday. US-government public domain.
  eia_gas_storage    N8  EIA weekly working gas in underground storage, Lower 48. US-government
                         public domain.

THE AXIS IS A LOG OF WHAT WAS KNOWABLE, NOT A COPY OF WHAT IS PUBLISHED NOW.
`data/axes/release_surprise.json` holds one row per (source, series, period). A row that is
already on disk is NEVER overwritten by a later fetch: the first value the desk saw is the value
a cell may trade on, and a later revision is recorded beside it (`revisions`) for the record
only. Every row carries `vintage`:

  first_print      captured by this organ at or after release; `knowable_at` is the later of the
                   publisher's scheduled release instant and the moment this organ first saw it.
  backfill_stable  history fetched after the fact from a publisher that does not revise the
                   figure (declared per source in `SOURCES[...]['history_vintage']` with its
                   evidence); `knowable_at` is the scheduled release instant, pushed LATER, never
                   earlier, on holiday weeks.
  backfill_latest  history fetched after the fact from a publisher that DOES revise. Kept for the
                   record; the family refuses to condition on it (a revised frame is information
                   nobody had at the time -- the #904 audit rule).

THE RELEASE CLOCKS (UTC instants; the family enters on the first bar opening after them):
  EIA storage   Thursday 10:30 America/New_York for the week ending the previous Friday. A US
                federal holiday Monday..Thursday of release week moves the instant to Friday
                12:00 ET -- LATER than any holiday schedule EIA has used (Thanksgiving week is
                released early, on Wednesday), so the clock is late, never early.
  USDA sales    Thursday 08:30 ET for the week ending the previous Thursday; the same holiday rule
                moves it to Friday 08:30 ET.
  TIC           ~16:00 ET on a mid-month business day; the date is not on a fixed rule, so a
                backfilled month M is knowable from the 20th of month M+2 at 16:00 ET (TIC
                publishes M in mid-M+2, on or before the 18th) and a first print is knowable
                from when it was first seen.
  BoJ rinban    results are posted the same Tokyo day; a backfilled operation is knowable from
                15:00 Asia/Tokyo of its operation date (results post around 12:00 JST), and a
                first print from when it was first seen.

POLITENESS AND LAW. Every request passes `robots_refusal` (a Disallow or an unreadable
robots.txt stops it -- the stricter rule, Governance 2026-11-10, #819), carries an honest
User-Agent, and each source is fetched only when it is DUE (`due()`: its release window has
opened since the last successful fetch, or 24h have passed), so an hourly leg costs each
publisher a handful of requests a week. No key, no paid API, no secret is read.

AN UNREACHABLE OR UNPARSEABLE SOURCE IS UNMEASURED, BY NAME (L1.28a). A page whose layout does
not carry the labels the parser expects writes `state: PARSE_UNVERIFIED` with the labels it
looked for and a 400-character sample of what it found, and NO rows -- a guessed column is a
confidently wrong series. The previous rows on disk always stand.

    python desks/mt5/research/release_surprise_ingest.py [--apply] [--force] \
        [--source eia_gas_storage]
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from collections.abc import Callable, Iterable, Mapping
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

AXIS = DESK / "data" / "axes" / "release_surprise.json"
REPORT = DESK / "reports" / "RELEASE_SURPRISE_INGEST.json"
UA = "quant-desk-release-surprise/1.0 (research; public statistical releases only)"
TIMEOUT_S = 40.0
MAX_BYTES = 8_000_000
NY = ZoneInfo("America/New_York")
TOKYO = ZoneInfo("Asia/Tokyo")
#: A source is re-fetched at least this often even when no release window opened.
STALE_REFETCH_H = 24.0

FIRST_PRINT = "first_print"
BACKFILL_STABLE = "backfill_stable"
BACKFILL_LATEST = "backfill_latest"
ADMITTED_VINTAGES = frozenset({FIRST_PRINT, BACKFILL_STABLE})

OK = "OK"
UNMEASURED = "UNMEASURED"
PARSE_UNVERIFIED = "PARSE_UNVERIFIED"
NOT_DUE = "NOT_DUE"
REFUSED = "REFUSED_ROBOTS"

#: USDA FAS export-sales historical pages, one per commodity (current marketing year, weekly).
USDA_PAGES: dict[str, str] = {
    "CORN": "https://apps.fas.usda.gov/export-sales/h401.htm",
    "WHEAT": "https://apps.fas.usda.gov/export-sales/h107.htm",
    "SOYBEAN": "https://apps.fas.usda.gov/export-sales/h801.htm",
}

SOURCES: dict[str, dict[str, Any]] = {
    "eia_gas_storage": {
        "idea": "N8", "publisher": "US Energy Information Administration",
        "terms": "US-government work, public domain (eia.gov/about/copyrights_reuse.php)",
        "urls": ["https://www.eia.gov/dnav/ng/hist/nw2_epg0_swo_r48_bcfw.htm"],
        "series": ("R48_WORKING_GAS_BCF",),
        "history_vintage": BACKFILL_STABLE,
        "history_vintage_evidence": (
            "the weekly Lower-48 level is revised only by occasional reclassifications that EIA "
            "publishes as a separate 'implied flow' line; the reported level of a past week is "
            "otherwise the level first printed. Live first prints are captured beside it, so a "
            "reclassification shows up as a recorded revision, never a silent rewrite"),
    },
    "usda_export_sales": {
        "idea": "N7", "publisher": "USDA Foreign Agricultural Service",
        "terms": "US-government work, public domain",
        "urls": list(USDA_PAGES.values()),
        "series": tuple(f"{k}_NET_SALES_KMT" for k in USDA_PAGES),
        "history_vintage": BACKFILL_STABLE,
        "history_vintage_evidence": (
            "FAS folds corrections into later weeks' net sales as adjustments; a published "
            "week's net-sales figure is not re-stated in the weekly history tables"),
    },
    "tic_flow": {
        "idea": "N6", "publisher": "US Department of the Treasury (TIC)",
        "terms": "US-government work, public domain",
        "urls": ["https://ticdata.treasury.gov/resource-center/data-chart-center/tic/"
                 "Documents/s1_globl.txt"],
        "series": ("NET_FOREIGN_PURCHASES_LT_USD_MN",),
        "history_vintage": BACKFILL_LATEST,
        "history_vintage_evidence": (
            "TIC revises prior months every release and re-benchmarks annually; the S-form "
            "history file is the latest vintage, so only first prints captured live are "
            "admitted to a cell"),
    },
    "boj_rinban": {
        "idea": "N4", "publisher": "Bank of Japan",
        "terms": "free reuse with attribution (boj.or.jp/en/about/copyright.htm)",
        "urls": ["https://www3.boj.or.jp/market/en/menu_o.htm"],
        "series": ("JGB_PURCHASE_<bucket>",),
        "history_vintage": BACKFILL_STABLE,
        "history_vintage_evidence": (
            "an operation's offered and purchased amounts are final once posted; the Bank does "
            "not revise the results of a completed operation"),
    },
}


# ------------------------------------------------------------------------- the HTTP door
@dataclass
class Fetched:
    url: str
    status: int | None = None
    body: str = ""
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.status is not None and 200 <= self.status < 300 and not self.error


_ROBOTS: dict[str, urllib.robotparser.RobotFileParser | str] = {}


def _tls() -> Any:
    try:
        import ssl

        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return None


def _raw_get(url: str) -> Fetched:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*",
                                               "Accept-Encoding": "identity"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S, context=_tls()) as r:
            raw = r.read(MAX_BYTES)
            ctype = str(r.headers.get("Content-Type") or "")
            m = re.search(r"charset=([\w-]+)", ctype)
            enc = m.group(1) if m else "utf-8"
            try:
                text = raw.decode(enc, "replace")
            except LookupError:
                text = raw.decode("utf-8", "replace")
            return Fetched(url, int(getattr(r, "status", 200)), text)
    except urllib.error.HTTPError as exc:
        return Fetched(url, int(getattr(exc, "code", 0) or 0), "", f"HTTP {exc.code}")
    except Exception as exc:
        return Fetched(url, None, "", f"{type(exc).__name__}: {str(exc)[:120]}")


def robots_refusal(url: str, getter: Callable[[str], Fetched] = _raw_get) -> str | None:
    """None when robots.txt allows this exact path for our agent, else why not.
    404/410 = no rules (allow); 401/403 or unreadable = refuse (never an assumed allow)."""
    parts = urllib.parse.urlsplit(url)
    key = f"{parts.scheme}://{parts.netloc}"
    rules = _ROBOTS.get(key)
    if rules is None:
        got = getter(f"{key}/robots.txt")
        rp = urllib.robotparser.RobotFileParser()
        if got.ok:
            rp.parse(got.body.splitlines())
            rules = rp
        elif got.status in (404, 410):
            rp.parse([])
            rules = rp
        elif got.status in (401, 403):
            rp.parse(["User-agent: *", "Disallow: /"])
            rules = rp
        else:
            rules = f"robots.txt unreadable ({got.error or got.status})"
        _ROBOTS[key] = rules
    if isinstance(rules, str):
        return rules
    return None if rules.can_fetch(UA, url) else "robots.txt disallows this path"


def gated_get(url: str, getter: Callable[[str], Fetched] = _raw_get) -> Fetched:
    why = robots_refusal(url, getter)
    if why:
        return Fetched(url, None, "", f"{REFUSED}: {why}")
    return getter(url)


# ------------------------------------------------------------------------- release clocks
def _holidays(year: int) -> set[date]:
    import pandas as pd
    from pandas.tseries.holiday import USFederalHolidayCalendar
    cal = USFederalHolidayCalendar()
    return {d.date() for d in cal.holidays(pd.Timestamp(year - 1, 12, 1),
                                           pd.Timestamp(year + 1, 1, 31))}


def _holiday_in(mon: date, thu: date) -> bool:
    hol = _holidays(mon.year) | _holidays(thu.year)
    d = mon
    while d <= thu:
        if d in hol:
            return True
        d += timedelta(days=1)
    return False


def _ny(d: date, hh: int, mm: int) -> datetime:
    return datetime.combine(d, time(hh, mm), tzinfo=NY).astimezone(UTC)


def eia_release_utc(week_ending: date) -> datetime:
    """Week ending Friday -> the following Thursday 10:30 ET; Friday 12:00 ET if a federal
    holiday falls Monday..Thursday of release week (late on purpose, never early)."""
    thu = week_ending + timedelta(days=(3 - week_ending.weekday()) % 7 or 7)
    mon = thu - timedelta(days=3)
    if _holiday_in(mon, thu):
        return _ny(thu + timedelta(days=1), 12, 0)
    return _ny(thu, 10, 30)


def usda_release_utc(week_ending: date) -> datetime:
    """Week ending Thursday -> the next Thursday 08:30 ET; Friday 08:30 ET on holiday weeks."""
    thu = week_ending + timedelta(days=7 - ((week_ending.weekday() - 3) % 7))
    mon = thu - timedelta(days=3)
    if _holiday_in(mon, thu):
        return _ny(thu + timedelta(days=1), 8, 30)
    return _ny(thu, 8, 30)


def tic_backfill_utc(month: date) -> datetime:
    """Data month M -> knowable from the 20th of month M+2 at 16:00 ET. TIC for month M is
    released in M+2 around the 15th-18th (September data in mid-November), so the 20th is late,
    never early. Only used for the record: TIC backfill rows are `backfill_latest`."""
    y, m = month.year, month.month + 2
    while m > 12:
        y, m = y + 1, m - 12
    return _ny(date(y, m, 20), 16, 0)


def boj_backfill_utc(op_day: date) -> datetime:
    return datetime.combine(op_day, time(15, 0), tzinfo=TOKYO).astimezone(UTC)


def _iso(ts: datetime) -> str:
    return ts.astimezone(UTC).isoformat(timespec="seconds")


def _later(a: datetime, b: datetime) -> datetime:
    return a if a >= b else b


# ------------------------------------------------------------------------- parsers
_TAG = re.compile(r"<[^>]+>")
_NUM = re.compile(r"^-?\(?[\d,]+(?:\.\d+)?\)?$")


def _cells(text: str) -> list[list[str]]:
    """HTML table rows -> lists of stripped cell texts (no external parser on the box)."""
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", text, flags=re.I | re.S):
        cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, flags=re.I | re.S)
        out = [html.unescape(_TAG.sub(" ", c)).replace("\xa0", " ").strip() for c in cells]
        out = [re.sub(r"\s+", " ", c) for c in out]
        if any(out):
            rows.append(out)
    return rows


def _num(s: str) -> float | None:
    t = s.strip().replace(" ", "")
    if not _NUM.match(t):
        return None
    neg = t.startswith("-") or (t.startswith("(") and t.endswith(")"))
    v = float(t.strip("-()").replace(",", ""))
    return -v if neg else v


_MONTHS = {m: i for i, m in enumerate(
    ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), 1)}


class ParseUnverified(ValueError):
    """The page does not carry the layout the parser was written against."""

    def __init__(self, expected: str, body: str) -> None:
        super().__init__(expected)
        self.expected = expected
        self.sample = re.sub(r"\s+", " ", _TAG.sub(" ", body))[:400]


def parse_eia_storage(body: str) -> list[tuple[date, float]]:
    """EIA dnav weekly history table: rows of `YYYY-Mon` then five (MM/DD, level) pairs.
    Returns (week ending, Lower-48 working gas in Bcf) ascending."""
    out: dict[date, float] = {}
    for row in _cells(body):
        head = row[0].strip()
        m = re.match(r"^(\d{4})-([A-Za-z]{3})$", head)
        if not m:
            continue
        year, mon = int(m.group(1)), _MONTHS.get(m.group(2).lower())
        if mon is None:
            continue
        rest = row[1:]
        for i in range(0, len(rest) - 1, 2):
            dm = re.match(r"^(\d{2})/(\d{2})$", rest[i].strip())
            v = _num(rest[i + 1])
            if not dm or v is None:
                continue
            mm, dd = int(dm.group(1)), int(dm.group(2))
            y = year - 1 if (mon == 1 and mm == 12) else (year + 1 if mon == 12 and mm == 1
                                                          else year)
            with suppress(ValueError):
                out[date(y, mm, dd)] = v
    if len(out) < 10:
        raise ParseUnverified("YYYY-Mon rows with MM/DD + level pairs (dnav weekly layout)", body)
    return sorted(out.items())


def parse_usda_history(body: str) -> list[tuple[date, float]]:
    """FAS export-sales weekly history page: a header row naming 'Net Sales' and a
    'Week Ending' date column. Returns (week ending, net sales thousand MT, current + next MY
    when both columns exist) ascending."""
    rows = _cells(body)
    hdr_i, date_c, net_cs = -1, -1, []
    for i, r in enumerate(rows):
        low = [c.lower() for c in r]
        if any("week" in c and "end" in c for c in low) and any("net sales" in c for c in low):
            hdr_i = i
            date_c = next(j for j, c in enumerate(low) if "week" in c and "end" in c)
            net_cs = [j for j, c in enumerate(low) if "net sales" in c]
            break
    if hdr_i < 0:
        raise ParseUnverified("a header with 'Week Ending' and 'Net Sales' columns", body)
    out: dict[date, float] = {}
    for r in rows[hdr_i + 1:]:
        if len(r) <= max([date_c, *net_cs]):
            continue
        d = _parse_us_date(r[date_c])
        vals = [_num(r[j]) for j in net_cs]
        if d is None or any(v is None for v in vals):
            continue
        out[d] = float(sum(v for v in vals if v is not None))
    if len(out) < 4:
        raise ParseUnverified("at least four dated weekly net-sales rows", body)
    return sorted(out.items())


def _parse_us_date(s: str) -> date | None:
    s = s.strip()
    for fmt in ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d", "%d-%b-%Y", "%d-%b-%y", "%b %d, %Y"):
        with suppress(ValueError):
            return datetime.strptime(s, fmt).replace(tzinfo=UTC).date()
    return None


#: S-form domestic long-term securities columns: (purchases keyword, sales keyword).
TIC_DOMESTIC = (("treasury", "treasury"), ("agency", "agency"),
                ("corporate bond", "corporate bond"), ("corporate stock", "corporate stock"))


def parse_tic_s1(body: str) -> list[tuple[date, float]]:
    """TIC S-form global file (tab- or comma-delimited, a multi-line header). Net foreign
    purchases of US long-term securities, USD millions, for the grand-total row of each month:
    sum over the four domestic classes of gross purchases by foreigners minus gross sales."""
    lines = [ln for ln in body.splitlines() if ln.strip()]
    sep = "\t" if sum("\t" in ln for ln in lines[:40]) > 5 else ","
    table = [[c.strip().strip('"') for c in ln.split(sep)] for ln in lines]
    hdr_i = -1
    for i, r in enumerate(table[:80]):
        low = " | ".join(c.lower() for c in r)
        if "country" in low and ("date" in low or "month" in low) and "purchase" in low:
            hdr_i = i
            break
    if hdr_i < 0:
        raise ParseUnverified("a header row naming Country, Date and gross purchases columns", body)
    hdr = [c.lower() for c in table[hdr_i]]
    date_c = next(j for j, c in enumerate(hdr) if "date" in c or "month" in c)
    name_c = next(j for j, c in enumerate(hdr) if "country" in c and "code" not in c)
    pairs: list[tuple[int, int]] = []
    for kw_p, kw_s in TIC_DOMESTIC:
        p = [j for j, c in enumerate(hdr) if kw_p in c and "purchase" in c and "foreign " not in c]
        s = [j for j, c in enumerate(hdr) if kw_s in c and "sale" in c and "foreign " not in c]
        if p and s:
            pairs.append((p[0], s[0]))
    if len(pairs) < 4:
        raise ParseUnverified("gross purchases and sales columns for Treasury, agency, corporate "
                              "bond and corporate stock", body)
    out: dict[date, float] = {}
    for r in table[hdr_i + 1:]:
        if len(r) <= max(max(pairs[-1]), date_c, name_c):
            continue
        if "grand total" not in r[name_c].lower():
            continue
        m = re.match(r"^(\d{4})-(\d{1,2})", r[date_c])
        if not m:
            continue
        vals = [(_num(r[p]), _num(r[s])) for p, s in pairs]
        if any(a is None or b is None for a, b in vals):
            continue
        out[date(int(m.group(1)), int(m.group(2)), 1)] = float(
            sum(a - b for a, b in vals if a is not None and b is not None))
    if len(out) < 12:
        raise ParseUnverified("at least twelve monthly Grand Total rows", body)
    return sorted(out.items())


#: Residual-maturity bucket labels as the Bank names them -> a stable series key.
_BOJ_BUCKET = re.compile(
    r"(?:more than|over)\s+(\d+)\s+years?\s+(?:and\s+)?up\s+to\s+(\d+)\s+years?"
    r"|(?:more than|over)\s+(\d+)\s+years?(?!\s+(?:and\s+)?up)"
    r"|up\s+to\s+(\d+)\s+years?"
    r"|(floating|inflation)", re.I)


def _bucket(label: str) -> str:
    m = _BOJ_BUCKET.search(label)
    if not m:
        return ""
    if m.group(1):
        return f"{m.group(1)}_{m.group(2)}Y"
    if m.group(3):
        return f"{m.group(3)}Y_PLUS"
    if m.group(4):
        return f"0_{m.group(4)}Y"
    return m.group(5).upper()


def _yen_100m(s: str) -> float | None:
    """'1,234.5 billion yen' / '¥123.4 bil.' / '450.0' (100 million yen) -> billion yen."""
    t = s.lower().replace(",", "")
    m = re.search(r"(-?\d+(?:\.\d+)?)", t)
    if not m:
        return None
    v = float(m.group(1))
    if "100 million" in t or "oku" in t:
        return v / 10.0
    if "trillion" in t:
        return v * 1000.0
    return v


def parse_boj_results(body: str, op_day: date) -> list[dict[str, Any]]:
    """One BoJ operation-results page -> one row per outright JGB purchase operation:
    {bucket, offered_bn, purchased_bn, planned_bn}. A page with no JGB purchase operation
    returns []; a page that names one but lacks the amount labels raises ParseUnverified."""
    text = html.unescape(_TAG.sub("\n", body)).replace("\xa0", " ")
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]
    out: list[dict[str, Any]] = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        if re.search(r"outright purchases? of (japanese government|jgb)", ln, re.I):
            block = lines[i:i + 40]
            nxt = next((k for k in range(1, len(block))
                        if re.search(r"outright purchases? of", block[k], re.I)), len(block))
            block = block[:nxt]
            joined = " ".join(block)
            bucket = _bucket(joined)
            got: dict[str, float | None] = {"offered_bn": None, "purchased_bn": None,
                                            "planned_bn": None}
            for k, b in enumerate(block):
                val_s = b.split(":", 1)[1] if ":" in b else (block[k + 1] if k + 1 < len(block)
                                                              else "")
                low = b.lower()
                # THE PLAN LINE IS READ FIRST: "Planned amount of purchase" would otherwise
                # match the purchased pattern ("amount of purchase").
                if got["planned_bn"] is None and re.search(
                        r"(planned|scheduled|intended) amount|amount (to be )?offered to purchase",
                        low):
                    got["planned_bn"] = _yen_100m(val_s)
                elif got["offered_bn"] is None and re.search(r"(amount|total) of (competitive )?"
                                                             r"(offers|bids)", low):
                    got["offered_bn"] = _yen_100m(val_s)
                elif got["purchased_bn"] is None and re.search(
                        r"amount of (successful|accepted|purchase)|amount purchased", low):
                    got["purchased_bn"] = _yen_100m(val_s)
            if bucket and got["offered_bn"] is not None and got["purchased_bn"] is not None:
                out.append({"bucket": bucket, "op_day": op_day.isoformat(), **got})
            elif bucket:
                raise ParseUnverified("an outright JGB purchase block with 'Amount of offers' and "
                                      "'Amount of successful' lines", body)
            i += max(nxt, 1)
            continue
        i += 1
    return out


def boj_result_links(index_body: str, base: str) -> list[tuple[str, date]]:
    """Operation-result page links on the Bank's market-operations index, with their day.
    The Bank names result pages by date (yymmdd or yyyymmdd); a link without a date is skipped."""
    out: dict[str, date] = {}
    for href in re.findall(r'href="([^"]+)"', index_body, flags=re.I):
        m = re.search(r"(20\d{2})(\d{2})(\d{2})|(?<!\d)(\d{2})(\d{2})(\d{2})(?!\d)", href)
        if not m or not re.search(r"(result|of|ope|stat)", href, re.I):
            continue
        try:
            if m.group(1):
                d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            else:
                d = date(2000 + int(m.group(4)), int(m.group(5)), int(m.group(6)))
        except ValueError:
            continue
        out[urllib.parse.urljoin(base, href)] = d
    return sorted(out.items(), key=lambda kv: kv[1])


# ------------------------------------------------------------------------- the axis
@dataclass
class SourceResult:
    source: str
    state: str
    rows: list[dict[str, Any]] = field(default_factory=list)
    why: str = ""
    sample: str = ""
    fetched: list[str] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        return {"state": self.state, "rows_offered": len(self.rows), "why": self.why[:300],
                "sample": self.sample, "fetched": self.fetched[:12]}


def _row(source: str, series: str, period: date, value: float, knowable: datetime,
         vintage: str, now: datetime, **extra: Any) -> dict[str, Any]:
    r = {"source": source, "series": series, "period": period.isoformat(), "value": value,
         "knowable_at": _iso(knowable), "vintage": vintage, "captured_at": _iso(now)}
    r.update({k: v for k, v in extra.items() if v is not None})
    return r


def _newest_is_first_print(rows: list[dict[str, Any]], prev_keys: set[tuple[str, str, str]],
                           seeded: bool, now: datetime) -> None:
    """A period that appears for the first time on a pass AFTER the source was seeded is a
    first print: its knowable instant is the later of the schedule and now."""
    if not seeded:
        return
    for r in rows:
        if (r["source"], r["series"], r["period"]) in prev_keys:
            continue
        r["vintage"] = FIRST_PRINT
        sched = datetime.fromisoformat(r["knowable_at"])
        r["knowable_at"] = _iso(_later(sched, now)) if sched > now - timedelta(days=10) \
            else _iso(now)


def ingest_eia(now: datetime, getter: Callable[[str], Fetched]) -> SourceResult:
    url = SOURCES["eia_gas_storage"]["urls"][0]
    got = gated_get(url, getter)
    if not got.ok:
        return SourceResult("eia_gas_storage", UNMEASURED, why=got.error or str(got.status),
                            fetched=[url])
    try:
        pts = parse_eia_storage(got.body)
    except ParseUnverified as exc:
        return SourceResult("eia_gas_storage", PARSE_UNVERIFIED, why=exc.expected,
                            sample=exc.sample, fetched=[url])
    rows = [_row("eia_gas_storage", "R48_WORKING_GAS_BCF", d, v, eia_release_utc(d),
                 BACKFILL_STABLE, now) for d, v in pts if eia_release_utc(d) <= now]
    return SourceResult("eia_gas_storage", OK, rows, fetched=[url])


def ingest_usda(now: datetime, getter: Callable[[str], Fetched]) -> SourceResult:
    rows: list[dict[str, Any]] = []
    whys, sample, fetched = [], "", []
    for crop, url in USDA_PAGES.items():
        fetched.append(url)
        got = gated_get(url, getter)
        if not got.ok:
            whys.append(f"{crop}: {got.error or got.status}")
            continue
        try:
            pts = parse_usda_history(got.body)
        except ParseUnverified as exc:
            whys.append(f"{crop}: {PARSE_UNVERIFIED} ({exc.expected})")
            sample = sample or exc.sample
            continue
        rows += [_row("usda_export_sales", f"{crop}_NET_SALES_KMT", d, v, usda_release_utc(d),
                      BACKFILL_STABLE, now, symbol=crop)
                 for d, v in pts if usda_release_utc(d) <= now]
    if not rows:
        state = PARSE_UNVERIFIED if sample else UNMEASURED
        return SourceResult("usda_export_sales", state, why="; ".join(whys), sample=sample,
                            fetched=fetched)
    return SourceResult("usda_export_sales", OK, rows, why="; ".join(whys), fetched=fetched)


def ingest_tic(now: datetime, getter: Callable[[str], Fetched]) -> SourceResult:
    url = SOURCES["tic_flow"]["urls"][0]
    got = gated_get(url, getter)
    if not got.ok:
        return SourceResult("tic_flow", UNMEASURED, why=got.error or str(got.status),
                            fetched=[url])
    try:
        pts = parse_tic_s1(got.body)
    except ParseUnverified as exc:
        return SourceResult("tic_flow", PARSE_UNVERIFIED, why=exc.expected, sample=exc.sample,
                            fetched=[url])
    rows = [_row("tic_flow", "NET_FOREIGN_PURCHASES_LT_USD_MN", d, v, tic_backfill_utc(d),
                 BACKFILL_LATEST, now) for d, v in pts]
    return SourceResult("tic_flow", OK, rows, fetched=[url])


#: Result pages read per pass at most (the index lists recent operations; history accrues).
BOJ_MAX_PAGES = 40


def ingest_boj(now: datetime, getter: Callable[[str], Fetched],
               known_days: set[str] | None = None) -> SourceResult:
    idx_url = SOURCES["boj_rinban"]["urls"][0]
    got = gated_get(idx_url, getter)
    if not got.ok:
        return SourceResult("boj_rinban", UNMEASURED, why=got.error or str(got.status),
                            fetched=[idx_url])
    links = boj_result_links(got.body, idx_url)
    if not links:
        return SourceResult("boj_rinban", PARSE_UNVERIFIED,
                            why="no dated operation-result links on the operations index",
                            sample=ParseUnverified("", got.body).sample, fetched=[idx_url])
    todo = [(u, d) for u, d in links if d.isoformat() not in (known_days or set())]
    todo = todo[-BOJ_MAX_PAGES:]
    rows: list[dict[str, Any]] = []
    whys, sample, fetched = [], "", [idx_url]
    for u, d in todo:
        fetched.append(u)
        page = gated_get(u, getter)
        if not page.ok:
            whys.append(f"{d}: {page.error or page.status}")
            continue
        try:
            ops = parse_boj_results(page.body, d)
        except ParseUnverified as exc:
            whys.append(f"{d}: {PARSE_UNVERIFIED}")
            sample = sample or exc.sample
            continue
        for op in ops:
            rows.append(_row("boj_rinban", f"JGB_PURCHASE_{op['bucket']}", d,
                             float(op["purchased_bn"]), boj_backfill_utc(d), BACKFILL_STABLE,
                             now, offered_bn=op["offered_bn"], planned_bn=op["planned_bn"],
                             bucket=op["bucket"]))
    if not rows and sample:
        return SourceResult("boj_rinban", PARSE_UNVERIFIED, why="; ".join(whys)[:300],
                            sample=sample, fetched=fetched)
    return SourceResult("boj_rinban", OK if rows or not whys else UNMEASURED, rows,
                        why="; ".join(whys)[:300], fetched=fetched)


INGESTERS: dict[str, Callable[..., SourceResult]] = {
    "eia_gas_storage": ingest_eia, "usda_export_sales": ingest_usda,
    "tic_flow": ingest_tic, "boj_rinban": ingest_boj,
}


def load_axis(path: Path = AXIS) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return {"axis": "release_surprise", "rows": [], "sources": {}}
    if not isinstance(doc, dict) or not isinstance(doc.get("rows"), list):
        return {"axis": "release_surprise", "rows": [], "sources": {}}
    doc.setdefault("sources", {})
    return doc


def merge(doc: dict[str, Any], res: SourceResult, now: datetime) -> dict[str, int]:
    """Add rows never seen; record a changed value as a revision, never as an overwrite."""
    rows: list[dict[str, Any]] = doc["rows"]
    idx = {(r["source"], r["series"], r["period"]): r for r in rows
           if isinstance(r, dict) and {"source", "series", "period"} <= set(r)}
    prev_keys = {k for k in idx if k[0] == res.source}
    seeded = bool(prev_keys)
    _newest_is_first_print(res.rows, prev_keys, seeded, now)
    added = revised = 0
    for r in res.rows:
        k = (r["source"], r["series"], r["period"])
        old = idx.get(k)
        if old is None:
            rows.append(r)
            idx[k] = r
            added += 1
            continue
        if abs(float(old["value"]) - float(r["value"])) > 1e-9:
            revs = old.setdefault("revisions", [])
            if not revs or abs(float(revs[-1]["value"]) - float(r["value"])) > 1e-9:
                revs.append({"value": r["value"], "seen_at": _iso(now)})
                revised += 1
    rows.sort(key=lambda r: (r["source"], r["series"], r["period"]))
    return {"added": added, "revised": revised}


def write_axis(doc: dict[str, Any], path: Path = AXIS) -> None:
    doc["n_rows"] = len(doc["rows"])
    doc["symbols"] = sorted({str(r.get("symbol")) for r in doc["rows"] if r.get("symbol")})
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=0, default=str), "utf-8")
    os.replace(tmp, path)


def _next_window(source: str, after: datetime) -> datetime:
    """The first scheduled release instant strictly after `after` (approximate for TIC/BoJ)."""
    d = after.astimezone(NY).date()
    if source == "eia_gas_storage":
        fri = d - timedelta(days=(d.weekday() - 4) % 7)
        for k in range(0, 3):
            t = eia_release_utc(fri + timedelta(days=7 * (k - 1)))
            if t > after:
                return t
    if source == "usda_export_sales":
        thu = d - timedelta(days=(d.weekday() - 3) % 7)
        for k in range(0, 3):
            t = usda_release_utc(thu + timedelta(days=7 * (k - 1)))
            if t > after:
                return t
    if source == "tic_flow":
        return after + timedelta(hours=STALE_REFETCH_H)
    # boj: operations run most Tokyo business days; results by ~12:00 JST
    t = datetime.combine(after.astimezone(TOKYO).date(), time(12, 30), tzinfo=TOKYO)
    t = t.astimezone(UTC)
    return t if t > after else t + timedelta(days=1)


def due(source: str, state: Mapping[str, Any], now: datetime) -> bool:
    last = state.get("last_ok_at")
    if not last:
        return True
    try:
        last_t = datetime.fromisoformat(str(last))
    except ValueError:
        return True
    if now - last_t >= timedelta(hours=STALE_REFETCH_H):
        return True
    return _next_window(source, last_t) <= now


def run(*, apply: bool, force: bool = False, only: Iterable[str] = (),
        now: datetime | None = None, getter: Callable[[str], Fetched] = _raw_get,
        axis_path: Path = AXIS, report_path: Path | None = REPORT) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    doc = load_axis(axis_path)
    states: dict[str, Any] = doc["sources"]
    report: dict[str, Any] = {"generated_at": _iso(now),
                              "organ": "desks/mt5/research/release_surprise_ingest.py",
                              "axis": str(axis_path.relative_to(DESK)) if axis_path.is_relative_to(
                                  DESK) else str(axis_path),
                              "ideas": {k: v["idea"] for k, v in SOURCES.items()},
                              "sources": {}}
    wanted = set(only) or set(INGESTERS)
    for name in sorted(wanted):
        st = states.setdefault(name, {})
        if not force and not due(name, st, now):
            report["sources"][name] = {"state": NOT_DUE, "last_ok_at": st.get("last_ok_at"),
                                       "next_window": _iso(_next_window(
                                           name, datetime.fromisoformat(st["last_ok_at"])))}
            continue
        if name == "boj_rinban":
            known = {r["period"] for r in doc["rows"] if r.get("source") == name}
            res = INGESTERS[name](now, getter, known)
        else:
            res = INGESTERS[name](now, getter)
        summ = res.summary()
        if res.state == OK:
            summ.update(merge(doc, res, now))
            st["last_ok_at"] = _iso(now)
        st.update({"last_state": res.state, "last_try_at": _iso(now),
                   "why": res.why[:300], "terms": SOURCES[name]["terms"],
                   "history_vintage": SOURCES[name]["history_vintage"],
                   "history_vintage_evidence": SOURCES[name]["history_vintage_evidence"]})
        report["sources"][name] = summ
    counts: dict[str, dict[str, int]] = {}
    for r in doc["rows"]:
        c = counts.setdefault(r["source"], {})
        c[r["vintage"]] = c.get(r["vintage"], 0) + 1
    report["rows_by_source_and_vintage"] = counts
    report["n_rows"] = len(doc["rows"])
    report["admitted_vintages"] = sorted(ADMITTED_VINTAGES)
    if apply:
        write_axis(doc, axis_path)
        if report_path is not None:
            report_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = report_path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(report, indent=1, default=str), "utf-8")
            os.replace(tmp, report_path)
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--force", action="store_true", help="fetch even when no source is due")
    ap.add_argument("--source", action="append", default=[], choices=sorted(INGESTERS))
    a = ap.parse_args(argv)
    rep = run(apply=a.apply, force=a.force, only=a.source)
    for k, v in rep["sources"].items():
        print(f"  {k:<18} {v['state']:<16} +{v.get('added', 0)} rev {v.get('revised', 0)} "
              f"{str(v.get('why') or '')[:70]}")
    print(f"release_surprise_ingest: rows={rep['n_rows']} "
          f"{json.dumps(rep['rows_by_source_and_vintage'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
