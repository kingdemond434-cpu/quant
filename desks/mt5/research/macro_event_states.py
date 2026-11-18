"""MACRO EVENT STATES -- five scheduled public releases turned into point-in-time surprise states.

WHAT IT READS (one organ, five sources, every one from its primary publisher, no paid feed):

  N5  snb_sight_deposits   SNB weekly sight deposits (data.snb.ch cube `snbgwdchfsgw`). The weekly
                           change is the footprint of SNB FX intervention -> EURCHF, USDCHF, XAUUSD.
                           BLOCKED_ON_TERMS: snb.ch limits reuse to "non-commercial purposes" and
                           its liability page says no SNB data is "intended for direct or indirect
                           use in connection with financial transactions". Parser and release rule
                           are kept (and tested) so the source turns on the day the terms allow.
  N7  usda_export_sales    USDA FAS weekly export sales highlights (Thursday 08:30 ET): net sales
                           of corn, wheat and soybeans for the current marketing year against
                           their own 4-release mean -> CORN, WHEAT, SOYBEAN.
  N8  eia_gas_storage      EIA weekly working gas in underground storage, Lower 48 (Thursday
                           10:30 ET): the week's change against the 5-year same-week average of
                           changes -> XNGUSD. Keyless public history page first; the keyed EIA
                           API (key read BY NAME through the repo's reader, never printed or
                           stored) only when the keyless page answers in a shape it cannot read.
  N6  tic_foreign_flows    US Treasury TIC SLT Table 1 (monthly): net U.S. sales of U.S. long-term
                           securities to foreigners, grand total (code 99996) -- i.e. net foreign
                           purchases -- against their own 12-month median -> USDJPY, EURUSD,
                           US500, US30, NAS100, US2000.
  N4  boj_rinban           BoJ JGB outright purchases against the published plan -> USDJPY,
                           EURJPY, JPN225. BLOCKED_ON_TERMS: boj.or.jp lists "copying or
                           reproduction of the content for commercial purposes" as an exception
                           that needs the Bank's prior contact. No request is made.

WHAT IT WRITES
  * `data/macro_event_states/<source>.jsonl` -- the point-in-time store (gitignored, box-local).
    Append-only: the FIRST record of a (series, period) is its point-in-time value; a later
    different value is appended as a revision stamped when it was seen. Re-merging the same
    answer appends nothing.
  * `data/lake/series/mes_<series>.csv` -- the lake series (`event_time`, `available_time`,
    `value`), read by `mt5desk/family_exogenous_conditioner.py`.
  * `exogenous_conditioner` cells on the surprise series, only on symbols the registry holds AND
    `universe_policy.may_hypothesise` admits (fails closed), donated through
    `proposer_common.donate` the way keyed_sources does, a ring slice per pass.
  * `reports/MACRO_EVENT_STATES_CLOCK.json` -- one event row per surprise (`at` = the release's
    available_time, `kind`, `instruments`, `actual`, `consensus` = the baseline), read by
    `event_response_atlas.load_events` as the ground `macro_event_states`.
  * `reports/MACRO_EVENT_STATES.json` -- the record: per-source status, terms evidence, store
    size, latest state and its z, cells, missed-growth lines.

POINT-IN-TIME RULE. `available_time` is never earlier than the moment the publisher released the
number:
  * FIRST PULL (backfill): the publisher's release rule, as a LATE bound (or the moment of the
    read, when that is earlier: the number was public then) -- EIA Thursday 10:30 ET
    after the Friday week end (Friday 10:30 when a federal holiday falls Monday..Thursday of the
    release week); TIC 16:00 ET on the LAST day of the second month after the data month (TIC
    releases mid-month; the bound is deliberately late); USDA the page's own release date at
    08:30 ET; SNB the first Zurich business day after the Friday, 10:00.
  * LATER PULLS: the rule time only when the evidence brackets it -- the previous successful
    read did NOT hold the period and the rule time lies between that read and this one;
    otherwise (a delayed release) the moment it was first seen.
  * A REVISION is stamped when seen. Surprise maths reads first-seen values only.

ACCESS, IN THIS ORDER, EACH FAILING CLOSED BY NAME: the source's terms row must read
`machine_use_allowed: True`; `libs.data.refused_hosts` must not list the host; the host's
robots.txt must allow the path for our agent (only 404/410 means "no rules"; an unreadable or
HTML answer refuses). 401/403/429/451 is a HARD STOP for that source: no further request this
pass and none for `HARD_STOP_H` hours (451 stays stopped until a person clears it). Honest UA,
one request every `MIN_INTERVAL_S` seconds at most, `MAX_REQUESTS` per pass, and a wall-clock
budget no request may outrun. A source is fetched only when due (slow cadence, hourly inside its
release window).

    python desks/mt5/research/macro_event_states.py --once [--budget-s 240] [--no-fetch] [--dry-run]
"""
from __future__ import annotations

import argparse
import contextlib
import html
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
from datetime import UTC, date, datetime, timedelta
from itertools import pairwise, product
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SOURCE_ID = "macro_event_states"
SEAT = "macro_event_states"
UNMEASURED = "UNMEASURED"
NY = ZoneInfo("America/New_York")
ZRH = ZoneInfo("Europe/Zurich")

# -------------------------------------------------------------------------- pacing and stops
MIN_INTERVAL_S = 2.0
MAX_REQUESTS = 16
HARD_STOP_CODES = frozenset({401, 403, 429, 451})
HARD_STOP_H = 24
TIMEOUT = 30.0
MAX_BYTES = 8 * 1024 * 1024
ROBOTS_AGENT = "quant-desk-research"
UA = f"{ROBOTS_AGENT}/1.0 (macro_event_states; research; honours robots.txt)"
#: The family's bar clock is broker time (up to UTC+3); four hours absorbs it and an hour more.
LAG_HOURS = 4
#: Points a surprise series needs before cells are minted: the family itself emits nothing
#: below `family_exogenous_conditioner.MIN_OBSERVATIONS` (30) after its own z warm-up (5).
MIN_POINTS = 35
CELL_GRID = {"transform": ("level_z",), "threshold": (1.0, 1.5), "side_when_high": (1, -1)}

_CHK = "2026-11-18"

# ------------------------------------------------------------------------- terms evidence
#: One row per source, in the shape `alt_proxies.TERMS_EVIDENCE` records. Read on 2026-11-18
#: through a page reader: this build container's proxy refuses every one of these hosts to curl
#: (CONNECT 403), so robots lines that could not be read here say so, and the live gate below
#: re-reads robots.txt on the box before every fetch pass and fails closed.
TERMS_EVIDENCE: dict[str, dict[str, Any]] = {
    "snb_sight_deposits": {
        "terms_url": "https://www.snb.ch/en/srv/disclaimer_copyright",
        "terms_quote": ("'Such information and data may be saved, translated (with reference to "
                        "the source), transmitted or used in other ways' 'for non-commercial "
                        "purposes, compatible with the purpose of such information or data'"),
        "liability_url": "https://www.snb.ch/en/srv/disclaimer_liability",
        "liability_quote": ("'No data calculated by the SNB and made available on its website "
                            "are intended for direct or indirect use in connection with "
                            "financial transactions (e.g. as underlying benchmark).' (read "
                            "2026-11-13, PR #1087)"),
        "judgement": ("trading is commercial use: BLOCKED_ON_TERMS until the SNB grants it; "
                      "same verdict as #1087 (futures_state_sources.json TO_CONFIRM)"),
        "robots": ("not readable from the build container (proxy CONNECT 403 on data.snb.ch "
                   "and www.snb.ch); #1087 recorded one 'User-agent: *' group with zero "
                   "Disallow (read 2026-08-28)"),
        "checked_at": _CHK,
        "machine_use_allowed": False,
    },
    "usda_export_sales": {
        "terms_url": "https://www.usda.gov/policies-and-links",
        "terms_quote": ("'Most information presented on the USDA Web site is considered public "
                        "domain information.' 'Public domain information may be freely "
                        "distributed or copied, but use of appropriate byline/photo/image "
                        "credits is requested.'"),
        "release_url": "https://www.fas.usda.gov/programs/export-sales-reporting-program",
        "release_quote": ("'FAS publishes a weekly summary of export sales activity every "
                          "Thursday at 8:30 a.m. ET, unless a change is announced.'"),
        "judgement": ("the weekly export sales report is FAS's own statistical publication, "
                      "not a third-party, trademarked or personal-use item: public domain. The "
                      "keyed OpenData API (header API_KEY) is NOT used: no key is held for it"),
        "robots": ("apps.fas.usda.gov/robots.txt not readable from the build container (proxy "
                   "CONNECT 403; page reader 'client_error'); the live gate decides on the box"),
        "attribution": "U.S. Department of Agriculture, Foreign Agricultural Service",
        "checked_at": _CHK,
        "machine_use_allowed": True,
    },
    "eia_gas_storage": {
        "terms_url": "https://www.eia.gov/about/copyrights_reuse.php",
        "terms_quote": ("'U.S. government publications are in the public domain and are not "
                        "subject to copyright protection.' 'You may use and/or distribute any "
                        "of our data, files, databases, reports, graphs, charts' -- with an "
                        "acknowledgment that 'includes the publication date'"),
        "robots": ("www.eia.gov/robots.txt (read 2026-11-18 via page reader): 'User-agent: *', "
                   "Disallow on archive, beta, CFIDE, cfapps, scripts, styles, rss, global, "
                   "oil_gas, survey, reports (Allow /reports/upcoming.php) and similar; nothing "
                   "matches /dnav/. api.eia.gov/robots.txt not readable from here"),
        "attribution": "Source: U.S. Energy Information Administration (EIA), publication date",
        "checked_at": _CHK,
        "machine_use_allowed": True,
    },
    "tic_foreign_flows": {
        "terms_url": "https://www.law.cornell.edu/uscode/text/17/105",
        "terms_quote": ("17 U.S.C. 105(a): 'Copyright protection under this title is not "
                        "available for any work of the United States Government'"),
        "judgement": ("TIC tables are Treasury's own statistics; Treasury's site-policy and "
                      "privacy pages (read 2026-11-18) publish no reuse or crawling restriction"),
        "data_url_quote": ("SLT Table 1: 'A positive number for net U.S. sales to foreigners "
                           "denotes an increase in a foreign position'; 'data begin at February "
                           "2023'; Grand Total row code 99996"),
        "robots": ("home.treasury.gov/robots.txt (read 2026-11-18): 'User-agent: * / Allow: /'. "
                   "ticdata.treasury.gov/robots.txt not readable from the build container "
                   "(proxy CONNECT 403; page reader 'client_error'); the live gate decides"),
        "attribution": "U.S. Department of the Treasury, Treasury International Capital (TIC)",
        "checked_at": _CHK,
        "machine_use_allowed": True,
    },
    "boj_rinban": {
        "terms_url": "https://www.boj.or.jp/en/about/copyright.htm",
        "terms_quote": ("'The information included in the site may be copied or reproduced with "
                        "the exceptions below.' Exceptions include 'The copying or reproduction "
                        "of the content for commercial purposes' -- 'please contact the Public "
                        "Relations Department of the Bank (post.prd8@boj.or.jp) in advance'"),
        "judgement": ("storing the purchase results for a trading desk is commercial copying: "
                      "BLOCKED_ON_TERMS until the Bank answers; unclear terms fail closed"),
        "robots": ("www.boj.or.jp/robots.txt not readable from the build container (proxy "
                   "CONNECT 403; page reader 'client_error')"),
        "checked_at": _CHK,
        "machine_use_allowed": False,
    },
}

MISSED_GROWTH: dict[str, str] = {
    "snb_sight_deposits": ("SNB sight-deposit intervention state not built: no EURCHF / USDCHF / "
                           "XAUUSD cell or event row on the SNB's weekly FX footprint until the "
                           "SNB's non-commercial clause is lifted for the desk"),
    "usda_export_sales": ("USDA export-sales surprise unbuilt this pass: no CORN / WHEAT / "
                          "SOYBEAN state on the Thursday 08:30 ET print"),
    "eia_gas_storage": ("EIA storage surprise unbuilt this pass: XNGUSD trades the Thursday "
                        "10:30 ET print with no state on it"),
    "tic_foreign_flows": ("TIC foreign-flow surprise unbuilt this pass: no USD / US-index state "
                          "on the monthly foreign-demand print"),
    "boj_rinban": ("BoJ rinban surprise not built: no USDJPY / EURJPY / JPN225 same-day state on "
                   "JGB purchase size against plan until the Bank permits commercial reuse"),
    "history": ("series {name} stands down until it holds {need} surprise points (has {have}): "
                "a z on fewer would trade the warm-up"),
}


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


def _num(s: str) -> float | None:
    try:
        return float(str(s).replace(",", "").strip())
    except ValueError:
        return None


class Refused(Exception):
    """A named refusal: BLOCKED_ON_TERMS:..., ROBOTS_REFUSED:..., HARD_STOP:<code>, ..."""


# --------------------------------------------------------------------------- calendars
def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    first = date(year, month, 1)
    return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    nxt = date(year + (month == 12), month % 12 + 1, 1)
    last = nxt - timedelta(days=1)
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def us_federal_holidays(year: int) -> frozenset[date]:
    """US federal holidays (5 U.S.C. 6103), actual and observed dates."""
    fixed = [date(year, 1, 1), date(year, 6, 19), date(year, 7, 4), date(year, 11, 11),
             date(year, 12, 25)]
    out = set(fixed)
    for d in fixed:
        if d.weekday() == 5:
            out.add(d - timedelta(days=1))
        elif d.weekday() == 6:
            out.add(d + timedelta(days=1))
    out |= {_nth_weekday(year, 1, 0, 3), _nth_weekday(year, 2, 0, 3), _last_weekday(year, 5, 0),
            _nth_weekday(year, 9, 0, 1), _nth_weekday(year, 10, 0, 2),
            _nth_weekday(year, 11, 3, 4)}
    return frozenset(out)


def _ny(d: date, hh: int, mm: int) -> datetime:
    return datetime(d.year, d.month, d.day, hh, mm, tzinfo=NY).astimezone(UTC)


def eia_release_time(week_end: date) -> datetime:
    """Thursday 10:30 ET after the week ending `week_end`; Friday 10:30 when a federal holiday
    falls on Monday..Thursday of that release week (EIA moves the report then -- to Wednesday for
    Thanksgiving, later otherwise -- so Friday is a late bound either way)."""
    thursday = week_end + timedelta(days=(3 - week_end.weekday()) % 7 or 7)
    monday = thursday - timedelta(days=3)
    hol = us_federal_holidays(thursday.year) | us_federal_holidays(monday.year)
    if any(monday + timedelta(days=i) in hol for i in range(4)):
        return _ny(thursday + timedelta(days=1), 10, 30)
    return _ny(thursday, 10, 30)


def tic_release_bound(period: str) -> datetime:
    """16:00 ET on the last day of the second month after the data month: a LATE bound on the
    TIC release (published mid-month), so a backfilled month is never stamped early."""
    y, m = int(period[:4]), int(period[5:7])
    m2 = m + 2
    y2, m2 = y + (m2 - 1) // 12, (m2 - 1) % 12 + 1
    nxt = date(y2 + (m2 == 12), m2 % 12 + 1, 1)
    return _ny(nxt - timedelta(days=1), 16, 0)


def _easter(year: int) -> date:
    a, b, c = year % 19, year // 100, year % 100
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    ell = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * ell) // 451
    month, day = divmod(h + ell - 7 * m + 114, 31)
    return date(year, month, day + 1)


def zurich_holidays(year: int) -> frozenset[date]:
    easter = _easter(year)
    return frozenset({easter - timedelta(days=2), easter + timedelta(days=1),
                      easter + timedelta(days=39), easter + timedelta(days=50),
                      date(year, 1, 1), date(year, 1, 2), date(year, 8, 1),
                      date(year, 12, 25), date(year, 12, 26)})


def snb_release_time(friday: date) -> datetime:
    """The first Zurich business day strictly after the Monday-or-later following `friday`
    (#1087's rule: data as of Friday -> Monday 10:00 Zurich, rolled past holidays)."""
    d = friday + timedelta(days=(7 - friday.weekday()) % 7 or 7)
    while d.weekday() >= 5 or d in zurich_holidays(d.year):
        d += timedelta(days=1)
    return datetime(d.year, d.month, d.day, 10, 0, tzinfo=ZRH).astimezone(UTC)


# ------------------------------------------------------------------------------- parsers
@dataclass(frozen=True)
class Obs:
    series: str
    period: str              # ISO date (weekly) or YYYY-MM (monthly)
    value: float
    rule_time: datetime      # the publisher's release rule, as a late bound


_TAG = re.compile(r"<[^>]+>")
_MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August",
           "September", "October", "November", "December")
_MON3 = {m[:3]: i + 1 for i, m in enumerate(_MONTHS)}


def _text(body: bytes) -> str:
    raw = body.decode("utf-8", errors="replace")
    raw = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", raw)
    return re.sub(r"\s+", " ", html.unescape(_TAG.sub(" ", raw))).strip()


def _is_html(body: bytes) -> bool:
    return body.lstrip()[:15].lower().startswith((b"<!doctype", b"<html"))


USDA_COMMODITIES: dict[str, str] = {"corn": "Corn", "wheat": "Wheat", "soybeans": "Soybeans"}


def parse_usda_highlights(body: bytes) -> list[Obs]:
    """FAS weekly highlights -> net sales (MT, current marketing year) per commodity, keyed by
    the page's own release date, stamped 08:30 ET on it."""
    text = _text(body)
    m = re.search(r"\b(" + "|".join(_MONTHS) + r")\s+(\d{1,2}),\s+(\d{4})\b", text)
    if not m:
        raise Refused("METADATA_MISMATCH:usda highlights carry no release date")
    rel = date(int(m.group(3)), _MONTHS.index(m.group(1)) + 1, int(m.group(2)))
    out: list[Obs] = []
    for key, label in USDA_COMMODITIES.items():
        g = re.search(rf"\b{label}:\s*Net sales( reductions)? of ([\d,]+(?:\.\d+)?)\s*"
                      r"(?:metric tons|MT)\b", text)
        if not g:
            continue
        v = _num(g.group(2))
        if v is None:
            continue
        out.append(Obs(f"usda_esr_{key}_net", rel.isoformat(), -v if g.group(1) else v,
                       _ny(rel, 8, 30)))
    if not out:
        raise Refused("METADATA_MISMATCH:usda highlights name none of corn, wheat, soybeans")
    return out


_EIA_ROW = re.compile(r"(?is)<tr[^>]*>(.*?)</tr>")
_EIA_CELL = re.compile(r"(?is)<t[dh][^>]*>(.*?)</t[dh]>")


def parse_eia_history(body: bytes) -> list[Obs]:
    """EIA dnav weekly history page -> Lower-48 working gas level (Bcf) per Friday week end.
    Rows: `YYYY-Mon | MM/DD | value | MM/DD | value | ...` (five week pairs, blanks allowed)."""
    out: list[Obs] = []
    for row in _EIA_ROW.findall(body.decode("utf-8", errors="replace")):
        cells = [re.sub(r"\s+", " ", html.unescape(_TAG.sub("", c))).strip()
                 for c in _EIA_CELL.findall(row)]
        if not cells:
            continue
        ym = re.fullmatch(r"(\d{4})-([A-Z][a-z]{2})", cells[0])
        if not ym or ym.group(2) not in _MON3:
            continue
        year, month = int(ym.group(1)), _MON3[ym.group(2)]
        for i in range(1, len(cells) - 1, 2):
            md = re.fullmatch(r"(\d{2})/(\d{2})", cells[i])
            v = _num(cells[i + 1]) if md else None
            if not md or v is None:
                continue
            mm, dd = int(md.group(1)), int(md.group(2))
            y = year - 1 if (mm == 12 and month == 1) else year
            try:
                wk = date(y, mm, dd)
            except ValueError:
                continue
            out.append(Obs("eia_ngs_level", wk.isoformat(), v, eia_release_time(wk)))
    if not out:
        raise Refused("METADATA_MISMATCH:eia history page holds no Year-Mon week rows")
    return out


EIA_API_SERIES = "NW2_EPG0_SWO_R48_BCF"


def parse_eia_api(body: bytes) -> list[Obs]:
    """EIA API v2 `response.data[]` rows (`period`, `value`) -> the same level series."""
    try:
        doc = json.loads(body.decode("utf-8", errors="replace"))
    except ValueError:
        raise Refused("UNPARSEABLE:eia api did not answer JSON") from None
    rows = ((doc or {}).get("response") or {}).get("data") if isinstance(doc, dict) else None
    if not isinstance(rows, list):
        raise Refused("METADATA_MISMATCH:eia api answer has no response.data list")
    out: list[Obs] = []
    for r in rows:
        wk = _day(r.get("period")) if isinstance(r, dict) else None
        v = _num(str(r.get("value"))) if isinstance(r, dict) else None
        if wk is not None and v is not None:
            out.append(Obs("eia_ngs_level", wk.isoformat(), v, eia_release_time(wk)))
    if not out:
        raise Refused("METADATA_MISMATCH:eia api rows carry no period/value")
    return out


TIC_GRAND_TOTAL = "99996"


def parse_tic_table1(body: bytes) -> list[Obs]:
    """SLT Table 1 (tab-separated) -> the grand total's net U.S. sales of U.S. long-term
    securities to foreigners (USD mn) per month. The column is found by the machine header
    (`country_code`, `date`, first `*_net`), never by position alone."""
    lines = body.decode("utf-8", errors="replace").splitlines()
    hdr_i = next((i for i, ln in enumerate(lines)
                  if "country_code" in [c.strip().lower() for c in ln.split("\t")]), None)
    if hdr_i is None:
        raise Refused("METADATA_MISMATCH:tic table 1 has no machine header with country_code")
    hdr = [c.strip().lower() for c in lines[hdr_i].split("\t")]
    try:
        ci, di = hdr.index("country_code"), hdr.index("date")
    except ValueError:
        raise Refused("METADATA_MISMATCH:tic table 1 header lacks date") from None
    ni = next((i for i, h in enumerate(hdr) if h.endswith("_net")), None)
    if ni is None:
        raise Refused("METADATA_MISMATCH:tic table 1 header has no *_net column")
    out: list[Obs] = []
    for ln in lines[hdr_i + 1:]:
        cells = [c.strip() for c in ln.split("\t")]
        if len(cells) <= max(ci, di, ni) or cells[ci] != TIC_GRAND_TOTAL:
            continue
        if not re.fullmatch(r"\d{4}-\d{2}", cells[di]):
            continue
        v = _num(cells[ni])
        if v is None:
            continue
        out.append(Obs("tic_net_lt", cells[di], v, tic_release_bound(cells[di])))
    if not out:
        raise Refused(f"METADATA_MISMATCH:tic table 1 has no grand-total ({TIC_GRAND_TOTAL}) row")
    return out


def parse_snb_cube(body: bytes) -> list[Obs]:
    """SNB cube CSV (`"Date";"D0";"Value"` after a preamble) -> total sight deposits (TG, CHF
    mn) per Friday. Empty scaffold rows are no observation."""
    out: list[Obs] = []
    header = False
    for raw in body.decode("utf-8", errors="replace").splitlines():
        parts = [x.strip().strip('"').strip() for x in raw.split(";")]
        if not header:
            header = len(parts) >= 3 and parts[0].lower() == "date"
            continue
        if len(parts) < 3 or not parts[2] or parts[1].upper() != "TG":
            continue
        d, v = _day(parts[0]), _num(parts[2])
        if d is None or v is None:
            continue
        out.append(Obs("snb_sd_total", d.isoformat(), v, snb_release_time(d)))
    if not out:
        raise Refused("METADATA_MISMATCH:snb cube has no TG rows")
    return out


# ------------------------------------------------------------------------------ sources
def _thursday_window(hh: int) -> Callable[[datetime], bool]:
    def fast(now: datetime) -> bool:
        loc = now.astimezone(NY)
        return loc.weekday() in (2, 3, 4) and hh <= loc.hour <= 20
    return fast


def _tic_window(now: datetime) -> bool:
    loc = now.astimezone(NY)
    return 13 <= loc.day <= 25 and 15 <= loc.hour <= 22


@dataclass(frozen=True)
class Source:
    sid: str
    idea: str
    url: str
    parse: Callable[[bytes], list[Obs]]
    symbols: tuple[str, ...]
    slow_h: float
    fast_h: float
    fast_window: Callable[[datetime], bool]
    #: (series it derives from, surprise name, baseline kind)
    states: tuple[tuple[str, str, str], ...] = field(default_factory=tuple)
    #: symbols per surprise series when they differ by series (USDA commodity -> its CFD)
    series_symbols: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    z_window: int = 52


SOURCES: dict[str, Source] = {
    "snb_sight_deposits": Source(
        "snb_sight_deposits", "N5", "https://data.snb.ch/api/cube/snbgwdchfsgw/data/csv/en",
        parse_snb_cube, ("EURCHF", "USDCHF", "XAUUSD"), 20.0, 20.0, lambda _n: False,
        (("snb_sd_total", "snb_sd_change_w", "change"),)),
    "usda_export_sales": Source(
        "usda_export_sales", "N7", "https://apps.fas.usda.gov/export-sales/highlite.htm",
        parse_usda_highlights, ("CORN", "WHEAT", "SOYBEAN"), 24.0, 1.0, _thursday_window(8),
        tuple((f"usda_esr_{c}_net", f"usda_esr_{c}_surprise_4w", "mean4")
              for c in USDA_COMMODITIES),
        {"usda_esr_corn_surprise_4w": ("CORN",), "usda_esr_wheat_surprise_4w": ("WHEAT",),
         "usda_esr_soybeans_surprise_4w": ("SOYBEAN",)}),
    "eia_gas_storage": Source(
        "eia_gas_storage", "N8", "https://www.eia.gov/dnav/ng/hist/nw2_epg0_swo_r48_bcfw.htm",
        parse_eia_history, ("XNGUSD",), 24.0, 1.0, _thursday_window(10),
        (("eia_ngs_level", "eia_ngs_surprise_5y", "five_year"),)),
    "tic_foreign_flows": Source(
        "tic_foreign_flows", "N6",
        "https://ticdata.treasury.gov/resource-center/data-chart-center/tic/Documents/"
        "slt_table1.txt",
        parse_tic_table1, ("USDJPY", "EURUSD", "US500", "US30", "NAS100", "US2000"),
        24.0, 1.0, _tic_window, (("tic_net_lt", "tic_net_lt_surprise_12m", "median12"),),
        z_window=24),
    "boj_rinban": Source(
        "boj_rinban", "N4", "https://www.boj.or.jp/en/mopo/mkt/index.htm",
        lambda _b: [], ("USDJPY", "EURJPY", "JPN225"), 24.0, 24.0, lambda _n: False, ()),
}

EIA_API = "https://api.eia.gov/v2/natural-gas/stor/wkly/data/"
EIA_KEY_NAME = "EIA_API_KEY"


def eia_api_url(key: str) -> str:
    q = [("frequency", "weekly"), ("data[0]", "value"), ("facets[series][]", EIA_API_SERIES),
         ("sort[0][column]", "period"), ("sort[0][direction]", "desc"), ("length", "500"),
         ("api_key", key)]
    return EIA_API + "?" + urllib.parse.urlencode(q)


def eia_key() -> str:
    """The EIA key, read BY NAME through the repo's reader (never printed, logged or stored)."""
    try:
        from libs.data import credentials as cred
        from libs.ops.env_keys import read_key
    except Exception:
        return ""
    for name in cred.accepted_names(EIA_KEY_NAME):
        with contextlib.suppress(Exception):
            v = read_key(name)
            if v:
                return v
    return ""


# ------------------------------------------------------------------------------- the fetcher
#: (url) -> (HTTP status, body). Injected in tests; `http_get` on the box.
Getter = Callable[[str], tuple[int, bytes]]


def _tls() -> Any:
    with contextlib.suppress(Exception):
        from research import asia_collector
        make: Any = asia_collector._tls_context
        return make()
    return None


def http_get(url: str) -> tuple[int, bytes]:
    """One GET with the honest UA; every redirect hop is checked against the refused hosts."""
    from libs.data import refused_hosts
    handlers: list[Any] = [refused_hosts.RefusingRedirectHandler()]
    ctx = _tls()
    if ctx is not None:
        handlers.append(urllib.request.HTTPSHandler(context=ctx))
    opener = urllib.request.build_opener(*handlers)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
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
        self.max_requests, self.min_interval_s = max_requests, min_interval_s
        self.deadline = deadline
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

    def fetch(self, url: str, *, secret: bool = False) -> bytes:
        """200 body, or a named Refused. With `secret` the URL (it carries a key) and the
        exception text never reach a message."""
        self._pace()
        try:
            status, body = self.get(url)
        except Exception as exc:
            msg = "" if secret else f": {str(exc)[:160]}"
            raise Refused(f"FETCH_ERROR:{type(exc).__name__}{msg}") from None
        if status in HARD_STOP_CODES:
            raise Refused(f"HARD_STOP:{status}")
        if status != 200:
            where = urllib.parse.urlsplit(url).netloc if secret else \
                urllib.parse.urlsplit(url).path
            raise Refused(f"HTTP_{status}:{where}")
        return body

    def robots(self, url: str) -> str | None:
        """None when robots.txt allows `url` for our agent, else why not (cached per host per
        pass). Only 404/410 means "no rules"; anything unreadable, HTML or a stop code refuses."""
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
            status, body = self.get(f"{host}/robots.txt")
        except Exception as exc:
            return f"ROBOTS_REFUSED:robots.txt unreadable ({type(exc).__name__})"
        if status in (404, 410):
            return None
        if status in HARD_STOP_CODES:
            return f"HARD_STOP:{status}"
        if status != 200:
            return f"ROBOTS_REFUSED:robots.txt answered HTTP {status}"
        if _is_html(body):
            return "ROBOTS_REFUSED:robots.txt answered HTML"
        return "RULES:" + body.decode("utf-8", errors="replace")


def access_refusal(sid: str, url: str, client: Client) -> str | None:
    """Terms, then the refused-hosts list, then robots -- before any data request."""
    if (TERMS_EVIDENCE.get(sid) or {}).get("machine_use_allowed") is not True:
        return "BLOCKED_ON_TERMS:machine_use_allowed is not true"
    from libs.data import refused_hosts
    why = refused_hosts.refusal(url)
    if why:
        return f"BLOCKED_ON_TERMS:{why}"
    return client.robots(url)


# --------------------------------------------------------------------- point-in-time store
def _store_path(paths: Paths, sid: str) -> Path:
    return paths.store / f"{sid}.jsonl"


def load_store(paths: Paths, sid: str) -> dict[tuple[str, str], dict[str, Any]]:
    """(series, period) -> {first record..., last_value, n_revisions}."""
    out: dict[tuple[str, str], dict[str, Any]] = {}
    p = _store_path(paths, sid)
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


def stamp(rule: datetime, seen: datetime, prev_ok: datetime | None) -> tuple[datetime, str]:
    """The available_time of a period first seen at `seen` (see the module docstring)."""
    if prev_ok is None:
        # The rule is a late bound and `seen` is a hard one (it was public when read): the
        # earlier of the two is still never earlier than the release.
        return min(rule, seen), "backfill_rule"
    if prev_ok < rule <= seen:
        return rule, "live_rule"
    return seen, "live_seen"


def merge(paths: Paths, sid: str, store: dict[tuple[str, str], dict[str, Any]],
          obs: Iterable[Obs], seen: datetime, prev_ok: datetime | None) -> dict[str, int]:
    """Append what is new: a period never seen, or a value that differs from the last stored
    (a revision, stamped when seen). The same answer merged twice appends nothing."""
    recs: list[dict[str, Any]] = []
    added = revised = 0
    for o in obs:
        k = (o.series, o.period)
        cur = store.get(k)
        if cur is None:
            avail, quality = stamp(o.rule_time, seen, prev_ok)
            rec = {"series": o.series, "period": o.period, "value": o.value,
                   "rule_time": _iso(o.rule_time), "first_seen_at": _iso(seen),
                   "available_time": _iso(avail), "pit_quality": quality, "revision": False}
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
        p = _store_path(paths, sid)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            for rec in recs:
                fh.write(json.dumps(rec, sort_keys=True) + "\n")
    return {"added": added, "revised": revised}


# ------------------------------------------------------------------------------ surprises
def _points(store: Mapping[tuple[str, str], Mapping[str, Any]], series: str
            ) -> list[dict[str, Any]]:
    """First-seen (point-in-time) points of one series, in period order."""
    pts = [{"period": k[1], "value": float(r["value"]), "available_time": r["available_time"],
            "pit_quality": r.get("pit_quality")}
           for k, r in store.items() if k[0] == series and isinstance(r.get("value"), int | float)]
    return sorted(pts, key=lambda p: p["period"])


def _later(a: str, b: str) -> str:
    return a if (_t(a) or datetime.min.replace(tzinfo=UTC)) >= \
        (_t(b) or datetime.min.replace(tzinfo=UTC)) else b


def weekly_changes(pts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Level -> week-on-week change, only across consecutive weeks (7 days apart); the change
    is knowable when BOTH levels are."""
    out: list[dict[str, Any]] = []
    for a, b in pairwise(pts):
        da, db = _day(a["period"]), _day(b["period"])
        if da is None or db is None or (db - da).days != 7:
            continue
        out.append({"period": b["period"], "value": b["value"] - a["value"],
                    "available_time": _later(a["available_time"], b["available_time"]),
                    "pit_quality": b["pit_quality"]})
    return out


def _same_week(changes: Mapping[date, float], d: date, years_back: int) -> float | None:
    y = d.year - years_back
    try:
        target = date(y, d.month, d.day)
    except ValueError:
        target = date(y, d.month, 28)
    best = min(((abs((k - target).days), k) for k in changes
                if abs((k - target).days) <= 3), default=None)
    return None if best is None else changes[best[1]]


def surprises(pts: list[dict[str, Any]], kind: str) -> list[dict[str, Any]]:
    """Each point against its baseline from STRICTLY EARLIER points only:
      change     value = the week-on-week change, baseline 0 (SNB)
      mean4      baseline = mean of the previous 4 prints, all within 42 days (USDA)
      five_year  value = the weekly change, baseline = mean of the same-week change in each of
                 the previous 5 years (+-3 days), all five required (EIA)
      median12   baseline = median of the previous 12 months, all within 13 months (TIC)
    `surprise` = value - baseline; points without a full baseline are dropped, never padded."""
    out: list[dict[str, Any]] = []
    if kind in ("change", "five_year"):
        ch = weekly_changes(pts)
        if kind == "change":
            return [{**c, "actual": c["value"], "baseline": 0.0, "surprise": c["value"]}
                    for c in ch]
        by_day = {d: c["value"] for c in ch if (d := _day(c["period"])) is not None}
        for c in ch:
            d = _day(c["period"])
            if d is None:
                continue
            prior = [_same_week(by_day, d, k) for k in range(1, 6)]
            if any(p is None for p in prior):
                continue
            base = sum(float(p) for p in prior if p is not None) / 5.0
            out.append({**c, "actual": c["value"], "baseline": base,
                        "surprise": c["value"] - base, "value": c["value"] - base})
        return out
    for i, p in enumerate(pts):
        if kind == "mean4":
            prev = pts[max(0, i - 4):i]
            d0, d1 = _day(prev[0]["period"]) if prev else None, _day(p["period"])
            if len(prev) < 4 or d0 is None or d1 is None or (d1 - d0).days > 42:
                continue
            base = sum(q["value"] for q in prev) / 4.0
        elif kind == "median12":
            prev = pts[max(0, i - 12):i]
            if len(prev) < 12:
                continue
            y0, m0 = int(prev[0]["period"][:4]), int(prev[0]["period"][5:7])
            y1, m1 = int(p["period"][:4]), int(p["period"][5:7])
            if (y1 - y0) * 12 + (m1 - m0) > 13:
                continue
            base = float(statistics.median(q["value"] for q in prev))
        else:
            continue
        out.append({**p, "actual": p["value"], "baseline": base, "surprise": p["value"] - base,
                    "value": p["value"] - base})
    return out


def zscore(values: list[float], window: int) -> float | None:
    """The last value against the `window` strictly earlier values; None below 8 of them."""
    prior, x = values[:-1][-window:], values[-1] if values else None
    if x is None or len(prior) < 8:
        return None
    m = sum(prior) / len(prior)
    sd = math.sqrt(sum((v - m) ** 2 for v in prior) / len(prior))
    return (x - m) / sd if sd > 0 else None


def _event_time(period: str) -> str:
    return f"{period}-01T00:00:00+00:00" if len(period) == 7 else f"{period}T00:00:00+00:00"


# --------------------------------------------------------------------------------- paths
@dataclass(frozen=True)
class Paths:
    desk: Path = DESK

    @property
    def store(self) -> Path:
        return self.desk / "data" / "macro_event_states"

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
    def report(self) -> Path:
        return self.desk / "reports" / "MACRO_EVENT_STATES.json"

    @property
    def clock(self) -> Path:
        return self.desk / "reports" / "MACRO_EVENT_STATES_CLOCK.json"


def lake_name(series: str) -> str:
    return f"mes_{series}"


def write_lake(paths: Paths, name: str, pts: list[dict[str, Any]]) -> str | None:
    import pandas as pd
    if not pts:
        return None
    paths.series.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame([{"event_time": _event_time(p["period"]),
                        "available_time": p["available_time"], "value": p["value"],
                        "source_id": SOURCE_ID,
                        "vintage_id": f"{SOURCE_ID}:{p['available_time']}"} for p in pts])
    target = paths.series / f"{lake_name(name)}.csv"
    tmp = target.with_suffix(f".tmp{os.getpid()}")
    df.to_csv(tmp, index=False)
    os.replace(tmp, target)
    return target.name


# ------------------------------------------------------------------------------------ cells
def allowed(paths: Paths, symbols: Iterable[str]) -> tuple[list[str], dict[str, str]]:
    """Symbols the registry holds AND the two-lane policy admits for exogenous_conditioner.
    FAILS CLOSED: no policy, no symbols."""
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
            admit = sym in uni and bool(may_hypothesise(sym, "exogenous_conditioner"))
        except Exception:
            admit = False
        if admit:
            ok.append(sym)
        else:
            skipped[sym] = "not in the universe registry or not hypothesis lane"
    return ok, skipped


def build_cells(name: str, sid: str, symbols: list[str], n_points: int, z_window: int,
                now: datetime) -> list[dict[str, Any]]:
    from proposer_common import candidate
    src = lake_name(name)
    stamp_ = _iso(now)
    cells: list[dict[str, Any]] = []
    for sym in symbols:
        for t, thr, side in product(*CELL_GRID.values()):
            c = candidate(SEAT, sym, "exogenous_conditioner",
                          {"source": src, "signal": "value", "transform": t, "threshold": thr,
                           "side_when_high": side, "lag_hours": LAG_HOURS,
                           "z_window": z_window},
                          f"{name.replace('_', ' ')} is a scheduled public release's surprise "
                          f"against its own baseline; at an extreme it conditions {sym}",
                          f"{name} ({t} {thr}) -> {sym}",
                          {"source_row": sid, "series": src, "arm": "direct",
                           "n_points": n_points})
            c.update({"symbols": [sym], "available_time": stamp_, "event_time": stamp_,
                      "source_culture": "official/en", "participant_structure": "policy",
                      "failure_mode_hypothesis": (
                          "fails when the print is anticipated by a consensus the baseline does "
                          "not see, or when the surprise is noise the market already fades"),
                      "crowding_prior": "medium",
                      "required_data": [f"desks/mt5/data/lake/series/{src}.csv"],
                      "falsifier": (f"{src} {t} beyond {thr} sd carries no out-of-sample "
                                    f"information about {sym} H1 returns")})
            cells.append(c)
    return cells


def _ring(grid: list[dict[str, Any]], at: int, n: int) -> tuple[list[dict[str, Any]], int]:
    if not grid:
        return [], 0
    start = at % len(grid)
    take = (grid[start:] + grid[:start])[:n]
    return take, (start + len(take)) % len(grid)


def _donate(seat: str, cands: list[dict[str, Any]], tests_run: int) -> dict[str, Any]:
    if not cands:
        return {"donated": 0, "path": None}
    from proposer_common import donate, donation_counts
    path = donate(seat, cands, tests_run)
    return {**donation_counts(), "path": str(path) if path else None}


def _per_pass() -> int:
    try:
        from libs.data import credentials as cred
        return int(cred.KS_PER_PASS)
    except Exception:
        return 1200


# -------------------------------------------------------------------------------- the pass
def _due(src: Source, st: Mapping[str, Any], now: datetime) -> bool:
    last = _t(st.get("last_attempt"))
    if last is None:
        return True
    cadence = src.fast_h if src.fast_window(now) else src.slow_h
    return now - last >= timedelta(hours=cadence) - timedelta(minutes=5)


def _collect_one(paths: Paths, src: Source, st: dict[str, Any],
                 store: dict[tuple[str, str], dict[str, Any]], client: Client,
                 now: datetime, key: Callable[[], str]) -> dict[str, Any]:
    """One source's fetch: gates, request(s), parse, merge. Raises Refused by name."""
    why = access_refusal(src.sid, src.url, client)
    if why:
        raise Refused(why)
    route = "keyless"
    try:
        obs = src.parse(client.fetch(src.url))
    except Refused as r:
        # The EIA key is a FALLBACK for a keyless page that answered in a shape (or status) it
        # cannot read -- never a way round a refusal, a stop code or the budget.
        if src.sid != "eia_gas_storage" or not str(r).startswith(
                ("METADATA_MISMATCH", "UNPARSEABLE", "HTTP_")):
            raise
        k = key()
        if not k:
            raise Refused(f"{str(r)[:120]} (keyed fallback BLOCKED_AUTH:{EIA_KEY_NAME})") from None
        url = eia_api_url(k)
        robots = client.robots(EIA_API)
        if robots:
            raise Refused(robots) from None
        obs = parse_eia_api(client.fetch(url, secret=True))
        route = "keyed_api"
    m = merge(paths, src.sid, store, obs, now, _t(st.get("last_ok")))
    st["last_ok"] = _iso(now)
    return {"status": "OK", "route": route, "parsed": len(obs), **m}


def run(paths: Paths = Paths(), *, fetch: bool = True, dry_run: bool = False,
        get: Getter | None = None, now: datetime | None = None,
        sleep: Callable[[float], None] = time.sleep,
        donate: Callable[[str, list[dict[str, Any]], int], dict[str, Any]] | None = None,
        key: Callable[[], str] = eia_key, budget_s: float | None = None) -> dict[str, Any]:
    now = now or _now()
    t0 = time.monotonic()
    deadline = math.inf if budget_s is None else t0 + max(0.0, budget_s - 30.0)
    state = _read(paths.state, {}) or {}
    per_src: dict[str, Any] = state.setdefault("sources", {})
    client = Client(get or http_get, sleep=sleep, deadline=deadline,
                    max_requests=MAX_REQUESTS, min_interval_s=MIN_INTERVAL_S)
    report_src: dict[str, Any] = {}
    grid: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    lake: list[str] = []
    for sid, src in SOURCES.items():
        st = per_src.setdefault(sid, {})
        store = load_store(paths, sid)
        rec: dict[str, Any] = {"idea": src.idea, "terms": TERMS_EVIDENCE[sid]}
        stop = st.get("hard_stop") or {}
        until = _t(stop.get("until"))
        if TERMS_EVIDENCE[sid].get("machine_use_allowed") is not True:
            status = "BLOCKED_ON_TERMS"
            rec["why"] = "BLOCKED_ON_TERMS:machine_use_allowed is not true (no request made)"
        elif not fetch:
            status = "NO_FETCH"
        elif stop.get("code") == 451 or (until and until > now):
            status = "HARD_STOP"
            rec["why"] = f"HARD_STOP:{stop.get('code')} (held since {stop.get('at')})"
        elif not _due(src, st, now):
            status = "NOT_DUE"
        else:
            st["last_attempt"] = _iso(now)
            try:
                rec["fetch"] = _collect_one(paths, src, st, store, client, now, key)
                status = "OK"
            except Refused as r:
                status = str(r).split(":", 1)[0]
                rec["why"] = str(r)
                if status == "BUDGET":
                    st.pop("last_attempt", None)          # not attempted: due next pass
                if status == "HARD_STOP":
                    code = int(str(r).split(":", 1)[1].split()[0])
                    st["hard_stop"] = {"code": code, "at": _iso(now),
                                       "until": None if code == 451
                                       else _iso(now + timedelta(hours=HARD_STOP_H))}
        if status not in ("OK", "NOT_DUE", "NO_FETCH") or not store:
            rec["missed_growth"] = MISSED_GROWTH[sid]
        rec["status"] = status
        rec["store_rows"] = len(store)
        rec["revisions"] = sum(int(r.get("n_revisions") or 0) for r in store.values())
        rec["states"] = {}
        syms_all, sym_skipped = allowed(paths, src.symbols)
        if sym_skipped:
            rec["symbols_skipped"] = sym_skipped
        for base, name, kind in src.states:
            pts = surprises(_points(store, base), kind)
            want = src.series_symbols.get(name, src.symbols)
            syms = [s for s in syms_all if s in want]
            latest = pts[-1] if pts else None
            z = zscore([p["value"] for p in pts], src.z_window) if pts else None
            rec["states"][name] = (
                {"status": UNMEASURED, "points": 0} if latest is None else
                {"period": latest["period"], "actual": latest["actual"],
                 "baseline": round(latest["baseline"], 4),
                 "surprise": round(latest["surprise"], 4),
                 "z": None if z is None else round(z, 4),
                 "available_time": latest["available_time"], "points": len(pts),
                 "symbols": syms})
            if not dry_run and pts and (w := write_lake(paths, name, pts)):
                lake.append(w)
            if len(pts) < MIN_POINTS:
                rec["states"][name]["missed_growth"] = MISSED_GROWTH["history"].format(
                    name=name, need=MIN_POINTS, have=len(pts))
            else:
                grid += build_cells(name, sid, syms, len(pts), src.z_window, now)
            for p in pts:
                if syms:
                    events.append({
                        "at": p["available_time"], "kind": f"mes_{sid}", "name": name,
                        "instruments": syms, "actual": p["actual"], "consensus": p["baseline"],
                        "surprise": p["surprise"], "period": p["period"],
                        "pit_quality": p.get("pit_quality"), "source": sid})
        report_src[sid] = rec
    state["last_requests"] = client.requests
    events.sort(key=lambda e: (e["at"], e["kind"], e["name"]))
    clock = {"generated_at": _iso(now), "writer": "research/macro_event_states.py",
             "rule": ("one row per surprise: `at` is the release's point-in-time available_time; "
                      "`actual` the print (or the week's change), `consensus` the baseline from "
                      "strictly earlier prints"),
             "n_events": len(events), "events": events,
             "consumers": ["research/event_response_atlas.py (load_events ground "
                           "macro_event_states)"]}
    take, nxt = _ring(grid, int(state.get("cell_cursor") or 0), _per_pass())
    don: dict[str, Any] = {"donated": 0}
    if not dry_run:
        don = (donate or _donate)(SEAT, take, len(take))
        state["cell_cursor"] = nxt
        _atomic(paths.state, state)
        _atomic(paths.clock, clock)
    built = [s for s, r in report_src.items() if r["store_rows"]]
    doc = {"generated_at": _iso(now), "writer": "research/macro_event_states.py",
           "source": SOURCE_ID,
           "status": ("OK" if built else "EMPTY"),
           "sources": report_src, "requests": client.requests,
           "store_rows": sum(r["store_rows"] for r in report_src.values()),
           "clock": {"path": "reports/MACRO_EVENT_STATES_CLOCK.json", "n_events": len(events)},
           "lake": sorted(lake),
           "cells": {"grid": len(grid), "built": len(take),
                     "minted": int(don.get("donated") or 0),
                     "trials_charged": 0 if dry_run else len(take), "donation": don},
           "missed_growth": {s: r["missed_growth"] for s, r in report_src.items()
                             if r.get("missed_growth")},
           "mode": "DRY_RUN" if dry_run else "RAN",
           "seconds": round(time.monotonic() - t0, 1)}
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
                      "sources": {s: r["status"] for s, r in doc["sources"].items()},
                      "cells": {k: doc["cells"][k] for k in ("grid", "built", "minted")}},
                     sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
