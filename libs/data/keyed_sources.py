"""PARSERS AND REQUEST BUILDERS FOR THE KEYED FREE SOURCES -- pure functions, no I/O.

Each source the principal can unlock with a free key (EIA, Nasdaq Data Link, e-Stat, KOSIS, Bank of
Korea ECOS, BLS, Reddit OAuth, Telegram MTProto) gets:

  * a REQUEST BUILDER: roster row + key -> the requests one pass makes. The key goes into the
    request and nowhere else; `redact()` is applied to anything that could be logged.
  * a PARSER: response bytes -> `Obs(series, period, value)`. Nothing is inferred at parse time
    except the period the value describes; the release instant is the roster row's rule, applied
    by the leg (`research/keyed_sources.py`), which is late by construction.

WHAT IS NOT HERE ON PURPOSE. e-Stat is parsed by `research.alt_proxies.parse_estat_cpi` (the
Asia thread's getStatsData parser, #131): one e-Stat reader on the desk, never two. Until #131
merges that import fails and the e-Stat rows report BLOCKED_DEPENDENCY by name.

ROUTES MARKED `confirm_on_box` in the roster are the publisher's table ids as best known when this
was written from a container that cannot reach the hosts; each is overridable by the env var the
row names, and a wrong id comes back as the publisher's own error, recorded, never as a zero.
"""
from __future__ import annotations

import base64
import json
import math
import re
import urllib.parse
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any

UNMEASURED = "UNMEASURED"


@dataclass(frozen=True)
class Obs:
    series: str
    period: date
    value: float


@dataclass
class Request:
    url: str
    method: str = "GET"
    headers: dict[str, str] = field(default_factory=dict)
    data: bytes | None = None
    part: str = ""


def _num(s: Any) -> float | None:
    try:
        v = float(str(s).replace(",", "").strip())
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _month_end(y: int, m: int) -> date:
    nxt = date(y + (m == 12), 1 if m == 12 else m + 1, 1)
    return nxt - timedelta(days=1)


def _json(body: bytes) -> Any:
    try:
        return json.loads(body.decode("utf-8", errors="replace"))
    except ValueError:
        return None


def redact(text: str, secrets: Iterable[str]) -> str:
    """Every secret substring replaced by a marker. Applied to anything that could be logged."""
    out = str(text)
    for s in secrets:
        if s:
            out = out.replace(s, "<redacted>")
    return out


def _period(text: str) -> date | None:
    """'2024-08-30' | '2024-08' | '202408' | '2024M08' | '20240830' -> the period's end date."""
    t = str(text or "").strip()
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", t) or re.fullmatch(r"(\d{4})(\d{2})(\d{2})", t)
    if m:
        try:
            return date(int(m[1]), int(m[2]), int(m[3]))
        except ValueError:
            return None
    m = re.fullmatch(r"(\d{4})-?M?(\d{2})", t)
    if m and 1 <= int(m[2]) <= 12:
        return _month_end(int(m[1]), int(m[2]))
    return None


# ================================================================================ EIA v2 ====
EIA_BASE = "https://api.eia.gov/v2/"


def eia_requests(row: Mapping[str, Any], key: str, start: str | None) -> list[Request]:
    q: list[tuple[str, str]] = [("api_key", key), ("frequency", str(row.get("frequency") or
                                                                     "weekly")),
                                ("data[0]", "value"), ("sort[0][column]", "period"),
                                ("sort[0][direction]", "desc"), ("length", "5000")]
    for sid in (row.get("series") or {}):
        code = (row["series"][sid] or {}).get("code")
        if code:
            q.append(("facets[series][]", str(code)))
    if start:
        q.append(("start", start))
    url = EIA_BASE + str(row["route"]).strip("/") + "/data/?" + urllib.parse.urlencode(q)
    return [Request(url)]


def parse_eia(body: bytes, row: Mapping[str, Any], part: str = "") -> list[Obs]:
    """`response.data[]` rows `{period, series, value}` -> one Obs per (series code, period)."""
    doc = _json(body)
    data = ((doc or {}).get("response") or {}).get("data") if isinstance(doc, dict) else None
    code_to = {str((v or {}).get("code")): k for k, v in (row.get("series") or {}).items()}
    out: list[Obs] = []
    for r in data or []:
        if not isinstance(r, dict):
            continue
        name = code_to.get(str(r.get("series") or r.get("series-id") or ""))
        p, v = _period(str(r.get("period") or "")), _num(r.get("value"))
        if name and p and v is not None:
            out.append(Obs(name, p, v))
    return out


# ==================================================================== Nasdaq Data Link =====
NDL_BASE = "https://data.nasdaq.com/api/v3/"


def ndl_requests(row: Mapping[str, Any], key: str, start: str | None) -> list[Request]:
    """One request per dataset code. `datasets/<CODE>.json` (legacy Quandl) or `datatables/`."""
    out: list[Request] = []
    for sid, spec in (row.get("series") or {}).items():
        code = str((spec or {}).get("code") or "")
        if not code:
            continue
        q = {"api_key": key}
        if start:
            q["start_date"] = start
        kind = "datatables" if (spec or {}).get("table") else "datasets"
        out.append(Request(f"{NDL_BASE}{kind}/{code}.json?{urllib.parse.urlencode(q)}", part=sid))
    return out


def parse_ndl(body: bytes, row: Mapping[str, Any], part: str = "") -> list[Obs]:
    """Both NDL shapes: `dataset{column_names,data}` and `datatable{columns,data}`. The column
    read is the row's `column` for that series (by name), else the first numeric one."""
    doc = _json(body)
    if not isinstance(doc, dict):
        return []
    spec = (row.get("series") or {}).get(part) or {}
    if "dataset" in doc:
        names = [str(c) for c in (doc["dataset"] or {}).get("column_names") or []]
        data = (doc["dataset"] or {}).get("data") or []
    elif "datatable" in doc:
        names = [str((c or {}).get("name")) for c in (doc["datatable"] or {}).get("columns") or []]
        data = (doc["datatable"] or {}).get("data") or []
    else:
        return []
    if not names:
        return []
    want = str(spec.get("column") or "")
    col = names.index(want) if want in names else 1 if len(names) > 1 else -1
    dcol = next((i for i, n in enumerate(names) if n.lower() in ("date", "report_date")), 0)
    out: list[Obs] = []
    for r in data:
        if not isinstance(r, list) or len(r) <= max(col, dcol) or col < 0:
            continue
        p, v = _period(str(r[dcol])), _num(r[col])
        if p and v is not None:
            out.append(Obs(part or str(row.get("id")), p, v))
    return out


# =================================================================================== KOSIS ===
KOSIS_BASE = "https://kosis.kr/openapi/Param/statisticsParameterData.do"


def kosis_requests(row: Mapping[str, Any], key: str, start: str | None) -> list[Request]:
    out: list[Request] = []
    for sid, spec in (row.get("series") or {}).items():
        s = spec or {}
        q = {"method": "getList", "apiKey": key, "format": "json", "jsonVD": "Y",
             "prdSe": s.get("prdSe", "M"), "orgId": s.get("orgId", ""), "tblId": s.get("tblId", ""),
             "itmId": s.get("itmId", "T+"), "objL1": s.get("objL1", "ALL"),
             "newEstPrdCnt": s.get("periods", 120)}
        out.append(Request(f"{KOSIS_BASE}?{urllib.parse.urlencode(q)}", part=sid))
    return out


def parse_kosis(body: bytes, row: Mapping[str, Any], part: str = "") -> list[Obs]:
    """A JSON list of `{PRD_DE, DT, C1, ITM_ID, ...}`. An `{err, errMsg}` object is an error,
    not data. With a `pick` filter (`{"C1": "0"}`) only matching rows are read, so a table with
    many categories yields one value per period."""
    doc = _json(body)
    if not isinstance(doc, list):
        return []
    pick = ((row.get("series") or {}).get(part) or {}).get("pick") or {}
    seen: set[date] = set()
    out: list[Obs] = []
    for r in doc:
        if not isinstance(r, dict) or any(str(r.get(k)) != str(v) for k, v in pick.items()):
            continue
        p, v = _period(str(r.get("PRD_DE") or "")), _num(r.get("DT"))
        if p and v is not None and p not in seen:
            seen.add(p)
            out.append(Obs(part, p, v))
    return out


# ============================================================================== BoK ECOS ===
ECOS_BASE = "https://ecos.bok.or.kr/api/StatisticSearch"


def ecos_requests(row: Mapping[str, Any], key: str, start: str | None) -> list[Request]:
    out: list[Request] = []
    now = datetime.now(UTC)
    for sid, spec in (row.get("series") or {}).items():
        s = spec or {}
        cyc = str(s.get("cycle", "M"))
        if cyc == "D":
            a, b = f"{now.year - 5}0101", now.strftime("%Y%m%d")
        else:
            a, b = f"{now.year - 15}01", now.strftime("%Y%m")
        parts = [ECOS_BASE, key, "json", "kr", "1", "10000", str(s.get("stat", "")), cyc, a, b,
                 str(s.get("item", ""))]
        out.append(Request("/".join(urllib.parse.quote(p, safe=":/") for p in parts), part=sid))
    return out


def parse_ecos(body: bytes, row: Mapping[str, Any], part: str = "") -> list[Obs]:
    doc = _json(body)
    rows = ((doc or {}).get("StatisticSearch") or {}).get("row") if isinstance(doc, dict) else None
    out: list[Obs] = []
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        p, v = _period(str(r.get("TIME") or "")), _num(r.get("DATA_VALUE"))
        if p and v is not None:
            out.append(Obs(part, p, v))
    return out


# =================================================================================== BLS ====
BLS_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"


def bls_requests(row: Mapping[str, Any], key: str, start: str | None) -> list[Request]:
    now = datetime.now(UTC)
    ids = [str((v or {}).get("code")) for v in (row.get("series") or {}).values()
           if (v or {}).get("code")]
    body = json.dumps({"seriesid": ids, "registrationkey": key, "startyear": str(now.year - 19),
                       "endyear": str(now.year)}).encode("utf-8")
    return [Request(BLS_URL, "POST", {"Content-Type": "application/json"}, body)]


def parse_bls(body: bytes, row: Mapping[str, Any], part: str = "") -> list[Obs]:
    doc = _json(body)
    if not isinstance(doc, dict) or str(doc.get("status")) != "REQUEST_SUCCEEDED":
        return []
    code_to = {str((v or {}).get("code")): k for k, v in (row.get("series") or {}).items()}
    out: list[Obs] = []
    for s in ((doc.get("Results") or {}).get("series") or []):
        name = code_to.get(str((s or {}).get("seriesID")))
        for d in (s or {}).get("data") or []:
            per = str((d or {}).get("period") or "")
            if not name or not re.fullmatch(r"M(0[1-9]|1[0-2])", per):
                continue
            v = _num(d.get("value"))
            try:
                p = _month_end(int(d.get("year")), int(per[1:]))
            except (TypeError, ValueError):
                continue
            if v is not None:
                out.append(Obs(name, p, v))
    return out


# ============================================================ text sources: mention counts ===
def keyword_patterns(row: Mapping[str, Any]) -> dict[str, re.Pattern[str]]:
    """Per mapped instrument, one case-insensitive alternation of its keywords."""
    out: dict[str, re.Pattern[str]] = {}
    for sym, words in (row.get("keywords") or {}).items():
        ws = [re.escape(str(w)) for w in words or [] if str(w).strip()]
        if ws:
            out[str(sym)] = re.compile(r"(?i)(?<![A-Za-z])(?:" + "|".join(ws) + r")(?![A-Za-z])")
    return out


def count_mentions(items: Iterable[tuple[datetime, str]], row: Mapping[str, Any],
                   before: date) -> list[Obs]:
    """Daily mention counts per instrument, COMPLETED DAYS ONLY (strictly before `before`), so a
    day's count is never first seen partial and then revised upward."""
    pats = keyword_patterns(row)
    counts: dict[tuple[str, date], int] = {}
    days: set[date] = set()
    for ts, text in items:
        d = ts.astimezone(UTC).date()
        if d >= before:
            continue
        days.add(d)
        for sym, pat in pats.items():
            if pat.search(text or ""):
                counts[(sym, d)] = counts.get((sym, d), 0) + 1
    # A covered day with no mention of an instrument is a MEASURED zero for that instrument.
    return [Obs(f"mentions_{sym}", d, float(counts.get((sym, d), 0)))
            for sym in pats for d in sorted(days)]


REDDIT_TOKEN_URL = "https://www.reddit.com/api/v1/access_token"  # noqa: S105 -- a URL
REDDIT_API = "https://oauth.reddit.com"
REDDIT_UA = "windows:quant-desk-keyed-sources:1.0 (research; contact via app owner)"


def reddit_token_request(client_id: str, secret: str) -> Request:
    auth = base64.b64encode(f"{client_id}:{secret}".encode()).decode("ascii")
    return Request(REDDIT_TOKEN_URL, "POST",
                   {"Authorization": f"Basic {auth}", "User-Agent": REDDIT_UA,
                    "Content-Type": "application/x-www-form-urlencoded"},
                   b"grant_type=client_credentials")


def parse_reddit_token(body: bytes) -> str | None:
    doc = _json(body)
    tok = (doc or {}).get("access_token") if isinstance(doc, dict) else None
    return str(tok) if tok else None


def reddit_listing_requests(row: Mapping[str, Any], token: str) -> list[Request]:
    h = {"Authorization": f"bearer {token}", "User-Agent": REDDIT_UA}
    return [Request(f"{REDDIT_API}/r/{sub}/new?limit=100&raw_json=1", headers=dict(h), part=sub)
            for sub in row.get("subreddits") or []]


def parse_reddit_listing(body: bytes) -> list[tuple[datetime, str]]:
    doc = _json(body)
    kids = ((doc or {}).get("data") or {}).get("children") if isinstance(doc, dict) else None
    out: list[tuple[datetime, str]] = []
    for k in kids or []:
        d = (k or {}).get("data") or {}
        try:
            ts = datetime.fromtimestamp(float(d.get("created_utc")), tz=UTC)
        except (TypeError, ValueError, OSError):
            continue
        out.append((ts, f"{d.get('title') or ''} {d.get('selftext') or ''}"))
    return out


# ============================================================================ registry ======
Builder = Callable[[Mapping[str, Any], str, "str | None"], list[Request]]
Parser = Callable[..., list[Obs]]

BUILDERS: dict[str, Builder] = {"eia_v2": eia_requests, "ndl": ndl_requests,
                                "kosis": kosis_requests, "ecos": ecos_requests,
                                "bls": bls_requests}
PARSERS: dict[str, Parser] = {"eia_v2": parse_eia, "ndl": parse_ndl, "kosis": parse_kosis,
                              "ecos": parse_ecos, "bls": parse_bls}
