"""CHINA OFFICIAL TABLES: the shape adapter `asia_parser` dispatches to for SAFE, CFETS/ChinaMoney,
PBOC open-market operations, NBS easyquery and China Customs. NOT A LEG AND NOT A FETCHER.

WHY THIS EXISTS (audit 2026-10-06, rows 1-5 and 7). The generic parser reads the largest HTML
table of a page. For the China official sources that is the wrong object every time:

  * SAFE's registry rows point at INDEX pages. The values live one hop away (the monthly release
    article, with an inline table and/or an .xls/.xlsx attachment), and they are WIDE -- the
    months run across the header and the items (结汇 / 售汇 / 差额, 收入 / 支出, 外汇储备 / 黄金)
    run down the first column, nested under section numbers that a flat read throws away.
  * CFETS `ccpr.json` is ONE DAY of central parities with the date in `data.lastDate`, not in any
    row, so a frame read of it has no period column and nothing ever becomes a history.
  * NBS easyquery answers a cube (`datanodes` keyed `zb.<code>_sj.<yyyymm>` plus the code->name
    dictionary in `wdnodes`); flattened, the indicator names and the months are lost.
  * PBOC OMO announcements are prose: "以利率招标方式开展了1500亿元7天期逆回购操作".
  * Customs commodity tables carry quantity AND value per commodity with the period and the
    direction only in the title.

So each shape gets the one reader it needs, and every reader returns LONG observations carrying
the universal sensor contract's field names (source_id, dataset_id, entity, geography, metric,
value, unit, event_time, scheduled_time, publication_time, ...). `asia_parser` appends them to the
source's append-only vintage ledger, fills the receipt / knowability / revision / provenance
fields, and nothing here writes to disk.

NOTHING HERE FETCHES. An index page yields the article ADDRESSES it links (handed back to the
collector exactly as the generic parser hands back .csv links) and an article yields its data
attachments; the collector fetches them as derived sources under the same root id.

FORMATS ARE THE DOCUMENTED PUBLIC ONES, AND THE LIVE YIELD IS UNMEASURED. This container's proxy
refuses safe.gov.cn, chinamoney.com.cn, pbc.gov.cn, stats.gov.cn and customs.gov.cn, so every
reader is built against fixtures that reproduce the published layout (see
desks/mt5/tests/fixtures/cn_official/README.md for what each is based on). The first box pass is
the measurement; a shape that changed reads PARSE_ERROR / NO_TABLE with its reason, never as an
empty series.

Dependency-free on purpose: the HTML tables are read with the standard library's HTMLParser and
an .xlsx with zipfile + ElementTree, because neither lxml nor openpyxl is in the requirements
files and a reader that silently needs one is a reader that silently reads nothing. A legacy .xls
(BIFF) needs xlrd and says so: NEEDS_PARSER with the reason, bytes kept in the vault.
"""
from __future__ import annotations

import io
import json
import re
import zipfile
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta, timezone
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlsplit

PARSER_VERSION = "cn_official_tables/1"

#: China Standard Time. No daylight saving since 1991, so a fixed offset is exact.
CST = timezone(timedelta(hours=8))

#: Fixed UTC offsets (hours) of the registry's countries whose official clocks have no DST. A
#: printed time on a page from any other country is read as DATE-ONLY (see `_date_only_bound`),
#: because guessing a DST offset is the lookahead `libs/research/bar_clock` exists to refuse.
FIXED_TZ_HOURS: dict[str, float] = {
    "cn": 8, "hk": 8, "mo": 8, "tw": 8, "sg": 8, "my": 8, "ph": 8, "jp": 9, "kr": 9,
    "in": 5.5, "id": 7, "th": 7, "vn": 7,
}

#: The universal sensor contract's field names (MANDATE 2026-10-06 §2.5) that an observation
#: record carries where they apply. A later adapter onto the one canonical contract is a pure
#: mapping: these names are used verbatim, and an inapplicable one is None, never invented.
CONTRACT_FIELDS: tuple[str, ...] = (
    "source_id", "dataset_id", "observation_id", "entity", "geography", "metric", "value", "unit",
    "event_time", "scheduled_time", "publication_time", "knowable_at", "received_at",
    "expected_value", "consensus", "seasonal_expected", "raw_surprise", "surprise_z", "delta",
    "acceleration", "revision_of", "revision_delta", "licence", "provenance_hash", "raw_pointer")

#: Registry `adapter` values this module answers. Declared per registry row, never guessed from a
#: URL, so a source is read by a bespoke shape only because someone wrote that down.
ADAPTERS: tuple[str, ...] = ("chinamoney", "nbs_easyquery", "safe", "pboc_omo", "customs")


@dataclass
class AdapterResult:
    """What one payload yielded. `observations` are long rows; `endpoints` go to the collector."""
    status: str                       # PARSED | INDEX_PAGE | NO_TABLE | PARSE_ERROR | NEEDS_PARSER
    kind: str
    observations: list[dict[str, Any]] = field(default_factory=list)
    endpoints: list[str] = field(default_factory=list)
    publication_time: str | None = None
    publication_basis: str = ""
    why: str = ""

    def summary(self) -> dict[str, Any]:
        return {"status": self.status, "kind": self.kind, "n_observations": len(self.observations),
                "endpoints_found": len(self.endpoints), "endpoints": self.endpoints[:40],
                "publication_time": self.publication_time,
                "publication_basis": self.publication_basis, "why": self.why,
                "parser_version": PARSER_VERSION}


# =============================================================================== time
def _iso(dt: datetime | None) -> str | None:
    return None if dt is None else dt.astimezone(UTC).isoformat(timespec="seconds")


def _isoz(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat(timespec="seconds")


def _date_only_bound(y: int, m: int, d: int, tz: timezone) -> datetime:
    """A page that prints only a DATE was knowable no later than the end of that local day.

    The end, not the start: the start would make a 16:00 release visible at midnight, which is
    lookahead inside the day. Later-than-true is the conservative direction, and `asia_parser`
    bounds it again by the receipt instant (the desk demonstrably held it then)."""
    return datetime(y, m, d, 23, 59, 59, tzinfo=tz)


_DT_RE = re.compile(
    r"(\d{4})\s*[-/.年]\s*(\d{1,2})\s*[-/.月]\s*(\d{1,2})日?"
    r"(?:[\sT]+(\d{1,2})[:：](\d{2})(?:[:：](\d{2}))?)?")  # noqa: RUF001


def parse_local_datetime(text: str, tz_hours: float | None = 8.0
                         ) -> tuple[datetime | None, str]:
    """(UTC instant, basis) for the first date[-time] in `text`, read in the page's own clock.

    With no time printed, or no fixed offset known for the country, the result is the END of the
    printed local day (UTC-12 when the offset is unknown: the latest that date can end anywhere).
    """
    m = _DT_RE.search(str(text or ""))
    if m is None:
        return None, "no date printed"
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        datetime(y, mo, d, tzinfo=UTC)
    except ValueError:
        return None, f"unparseable date {m.group(0)!r}"
    tz = timezone(timedelta(hours=tz_hours)) if tz_hours is not None else timezone(
        timedelta(hours=-12))
    if m.group(4) is not None and tz_hours is not None:
        hh, mm, ss = int(m.group(4)), int(m.group(5)), int(m.group(6) or 0)
        if hh < 24 and mm < 60 and ss < 60:
            return datetime(y, mo, d, hh, mm, ss, tzinfo=tz), "printed date and time"
    return (_date_only_bound(y, mo, d, tz),
            "printed date only: end of that local day" if tz_hours is not None
            else "printed date only, country clock unknown: end of that day at UTC-12")


#: Where a page prints its own publication instant, most specific first.
_PUB_PATTERNS: tuple[str, ...] = (
    r'<meta[^>]+name=["\'](?:PubDate|publishdate|ArticlePubDate|pubdate|firstpublishedtime)'
    r'["\'][^>]+content=["\']([^"\']+)["\']',
    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\'](?:PubDate|publishdate|'
    r'ArticlePubDate|pubdate)["\']',
    r'<meta[^>]+property=["\']article:published_time["\'][^>]+content=["\']([^"\']+)["\']',
    r"(?:发布时间|发布日期|发表时间|公布日期)\s*[:：]?\s*([0-9]{4}[^<]{0,24})",  # noqa: RUF001
    r"(?:Release Date|Released on|Date of Release)\s*[:：]?\s*([0-9]{4}[^<]{0,24})",  # noqa: RUF001
)


def page_publication_time(text: str, country: str | None = "cn"
                          ) -> tuple[str | None, str]:
    """The page's OWN publication stamp as a UTC ISO string, or (None, why).

    Never the fetch time and never the registry's lag: those are what `asia_parser` falls back
    to, and it says which one it used."""
    tz_h = FIXED_TZ_HOURS.get(str(country or "").lower())
    for pat in _PUB_PATTERNS:
        m = re.search(pat, text or "", re.I)
        if m is None:
            continue
        raw = m.group(1)
        if re.search(r"[+-]\d{2}:?\d{2}$|Z$", raw.strip()):        # carries its own offset
            try:
                return (_iso(datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))),
                        "printed with its own UTC offset")
            except ValueError:
                pass
        dt, basis = parse_local_datetime(raw, tz_h)
        if dt is not None:
            return _iso(dt), basis
    return None, "the page prints no publication stamp"


def month_end(y: int, m: int) -> datetime:
    """The last instant of a reference month, as the event time a monthly statistic describes."""
    nxt = datetime(y + (m == 12), m % 12 + 1, 1, tzinfo=CST)
    return nxt - timedelta(seconds=1)


_MONTH_RE = re.compile(r"^\s*(\d{4})\s*(?:[.\-/年]\s*(\d{1,2})\s*月?|(\d{2}))\s*$")


def parse_month(text: Any) -> tuple[int, int] | None:
    """`2025.01` / `2025-1` / `2025年1月` / `202501` -> (2025, 1). Anything else -> None."""
    s = str(text or "").strip().replace("　", "")
    m = _MONTH_RE.match(s)
    if m is None:
        return None
    y = int(m.group(1))
    mo = int(m.group(2) or m.group(3))
    if not (1990 <= y <= 2100 and 1 <= mo <= 12):
        return None
    return y, mo


# =============================================================================== numbers
def to_number(v: Any) -> float | None:
    """A printed statistic as a float: thousands separators, %, full-width minus and blanks."""
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v) if v == v else None
    s = (str(v).strip().replace(",", "").replace("，", "").replace("%", "")  # noqa: RUF001
         .replace("−", "-").replace("－", "-").replace("　", "").replace(" ", ""))  # noqa: RUF001
    if s in ("", "-", "--", "—", "…", "...", "NA", "N/A", "null", "None"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


# =============================================================================== html tables
class _TableParser(HTMLParser):
    """Every <table> as a list of rows of cell text, colspan expanded. Standard library only."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self._stack: list[list[list[str]]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None
        self._span = 1

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        t = tag.lower()
        if t == "table":
            self._stack.append([])
        elif t == "tr" and self._stack:
            self._row = []
        elif t in ("td", "th") and self._row is not None:
            self._cell = []
            span = dict(attrs).get("colspan") or "1"
            try:
                self._span = max(1, min(50, int(str(span).strip() or "1")))
            except ValueError:
                self._span = 1
        elif t == "br" and self._cell is not None:
            self._cell.append(" ")

    def handle_endtag(self, tag: str) -> None:
        t = tag.lower()
        if t in ("td", "th") and self._cell is not None and self._row is not None:
            txt = re.sub(r"\s+", " ", "".join(self._cell)).strip()
            self._row.extend([txt] * self._span)
            self._cell = None
        elif t == "tr" and self._row is not None and self._stack:
            if self._row:
                self._stack[-1].append(self._row)
            self._row = None
        elif t == "table" and self._stack:
            self.tables.append(self._stack.pop())

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)


def html_tables(text: str) -> list[list[list[str]]]:
    p = _TableParser()
    try:
        p.feed(text)
        p.close()
    except Exception:
        pass
    return [t for t in p.tables if len(t) >= 2]


def _strip_tags(text: str) -> str:
    t = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", text or "", flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _anchors(text: str, base: str) -> list[tuple[str, str]]:
    """(absolute href, anchor text) for every link on a page."""
    out: list[tuple[str, str]] = []
    for m in re.finditer(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', text or "",
                         re.S | re.I):
        href = m.group(1).strip()
        if href.startswith(("javascript:", "#", "mailto:")):
            continue
        out.append((urljoin(base, href), _strip_tags(m.group(2))))
    return out


_DATA_EXT = (".xls", ".xlsx", ".csv", ".json", ".xml", ".zip")


def data_links(text: str, base: str) -> list[str]:
    out: list[str] = []
    for href, _txt in _anchors(text, base):
        if href.lower().split("?")[0].endswith(_DATA_EXT) and href not in out:
            out.append(href)
    return out


# =============================================================================== xlsx (stdlib)
def xlsx_sheets(body: bytes) -> list[list[list[str]]]:
    """Every worksheet of an .xlsx as rows of cell text, with no third-party reader.

    An .xlsx is a zip of XML: shared strings in xl/sharedStrings.xml, cells in
    xl/worksheets/sheetN.xml with `r="B7"` references. Merged cells read as blank, which the wide
    melt below tolerates (a section label is carried down from the row that printed it)."""
    import xml.etree.ElementTree as ET
    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    try:
        zf = zipfile.ZipFile(io.BytesIO(body))
    except zipfile.BadZipFile:
        return []
    shared: list[str] = []
    if "xl/sharedStrings.xml" in zf.namelist():
        root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
        for si in root.iter(f"{ns}si"):
            shared.append("".join(t.text or "" for t in si.iter(f"{ns}t")))
    sheets: list[list[list[str]]] = []
    names = sorted((n for n in zf.namelist() if re.match(r"xl/worksheets/sheet\d+\.xml$", n)),
                   key=lambda n: int(re.findall(r"\d+", n)[-1]))
    for name in names[:12]:
        root = ET.fromstring(zf.read(name))
        grid: dict[int, dict[int, str]] = {}
        for c in root.iter(f"{ns}c"):
            ref = c.get("r") or ""
            m = re.match(r"([A-Z]+)(\d+)$", ref)
            if m is None:
                continue
            col = 0
            for ch in m.group(1):
                col = col * 26 + (ord(ch) - 64)
            row = int(m.group(2))
            v = c.find(f"{ns}v")
            text = ""
            if c.get("t") == "s" and v is not None and v.text is not None:
                try:
                    text = shared[int(v.text)]
                except (ValueError, IndexError):
                    text = ""
            elif c.get("t") == "inlineStr":
                text = "".join(t.text or "" for t in c.iter(f"{ns}t"))
            elif v is not None and v.text is not None:
                text = v.text
            grid.setdefault(row, {})[col] = text.strip()
        if not grid:
            continue
        width = max(max(r) for r in grid.values())
        sheets.append([[grid[r].get(k, "") for k in range(1, width + 1)]
                       for r in sorted(grid)])
    return sheets


# =============================================================================== wide melt
_SECTION_RE = re.compile(r"^\s*([一二三四五六七八九十]+)\s*[、.．]\s*(.*)$")  # noqa: RUF001
_SUB_RE = re.compile(r"^\s*[（(]\s*([一二三四五六七八九十\d]+)\s*[)）]\s*(.*)$")  # noqa: RUF001
_UNIT_RE = re.compile(r"单位\s*[:：]\s*([^\s，,;；)）]+)")  # noqa: RUF001


def _excel_serial_month(v: str) -> tuple[int, int] | None:
    x = to_number(v)
    if x is None or not 20_000 < x < 60_000:
        return None
    d = datetime(1899, 12, 30, tzinfo=UTC) + timedelta(days=x)
    return d.year, d.month


def _month_cell(v: str) -> tuple[int, int] | None:
    return parse_month(v) or _excel_serial_month(v)


def melt_wide_months(rows: list[list[str]], *, unit_hint: str | None = None
                     ) -> list[tuple[str, tuple[int, int], float, str | None]]:
    """(label path, (year, month), value, unit) from a months-across OR months-down table.

    Months across: the header row holding >= 3 month cells; labels down the first text column,
    each nested under the last SECTION it sat under (`一、结汇` > `(二)代客结汇` reads as
    `结汇/代客结汇`), because SAFE repeats `代客` under both settlement and sales and a flat label
    would merge them. Months down: the column holding >= 3 month cells; the header row names
    the items. A block of two numeric columns per month (亿美元 / 亿SDR) keeps the first."""
    text_all = " ".join(" ".join(r) for r in rows[:8])
    um = _UNIT_RE.search(text_all)
    unit = um.group(1) if um else unit_hint
    width = max((len(r) for r in rows), default=0)
    grid = [r + [""] * (width - len(r)) for r in rows]
    out: list[tuple[str, tuple[int, int], float, str | None]] = []
    # ---- months across
    hdr_i = -1
    hdr_cols: dict[int, tuple[int, int]] = {}
    for i, r in enumerate(grid[:15]):
        cols = {j: mo for j, c in enumerate(r) if (mo := _month_cell(c)) is not None}
        if len(cols) >= 3 and len(cols) > len(hdr_cols):
            hdr_i, hdr_cols = i, cols
    if hdr_cols:
        first_month_col = min(hdr_cols)
        seen_month: set[tuple[int, int]] = set()
        keep: dict[int, tuple[int, int]] = {}
        for j in sorted(hdr_cols):
            if hdr_cols[j] not in seen_month:
                keep[j] = hdr_cols[j]
                seen_month.add(hdr_cols[j])
        section = ""
        for r in grid[hdr_i + 1:]:
            label = next((c for c in r[:first_month_col] if c and to_number(c) is None), "")
            if not label:
                continue
            sm = _SECTION_RE.match(label)
            sub = _SUB_RE.match(label)
            if sm is not None:
                section = sm.group(2).strip()
                path = section
            elif sub is not None:
                path = f"{section}/{sub.group(2).strip()}" if section else sub.group(2).strip()
            else:
                path = f"{section}/{label.strip()}" if section and not label.startswith(
                    section) else label.strip()
            for j, mo in keep.items():
                v = to_number(r[j]) if j < len(r) else None
                if v is not None:
                    out.append((path, mo, v, unit))
        if out:
            return out
    # ---- months down
    best_j, best_n = -1, 0
    for j in range(width):
        n = sum(1 for r in grid if _month_cell(r[j]) is not None)
        if n > best_n:
            best_j, best_n = j, n
    if best_n < 3:
        return []
    first_row = next(i for i, r in enumerate(grid) if _month_cell(r[best_j]) is not None)
    header = grid[first_row - 1] if first_row > 0 else [f"col{k}" for k in range(width)]
    for r in grid[first_row:]:
        mo = _month_cell(r[best_j])
        if mo is None:
            continue
        for j, c in enumerate(r):
            if j == best_j:
                continue
            v = to_number(c)
            name = header[j].strip() if j < len(header) else ""
            if v is not None and name:
                out.append((name, mo, v, unit))
    return out


# =============================================================================== observations
def observation(*, source_id: str, dataset_id: str, entity: str, metric: str,
                value: float, unit: str | None, event_time: datetime | str,
                geography: str = "CN", publication_time: str | None = None,
                scheduled_time: str | None = None, period: str | None = None,
                basis: str = "") -> dict[str, Any]:
    """One long observation with the contract's field names. Receipt, knowability, revision and
    provenance fields are filled by `asia_parser` (it knows the vintage), never here."""
    ev = event_time if isinstance(event_time, str) else _iso(event_time)
    row: dict[str, Any] = dict.fromkeys(CONTRACT_FIELDS)
    row.update({"source_id": source_id, "dataset_id": dataset_id, "entity": entity,
                "geography": geography, "metric": metric, "value": float(value), "unit": unit,
                "event_time": ev, "scheduled_time": scheduled_time,
                "publication_time": publication_time, "period": period,
                "time_basis": basis, "parser_version": PARSER_VERSION})
    return row


def _json(body: bytes) -> Any:
    try:
        return json.loads(body.decode("utf-8-sig", errors="replace"))
    except ValueError:
        return None


# ----------------------------------------------------------------------------- chinamoney
#: Record keys that name the row (pair / tenor), and keys that carry its level, in preference
#: order, as ChinaMoney's own front-end JSON names them.
_CM_LABEL_KEYS = ("vrtEName", "vrtCode", "ccyPair", "termCode", "term", "vrtName", "name")
_CM_VALUE_KEYS = ("price", "shibor", "value", "rate", "middlePrice", "frValue", "closePrice")
_CM_DATE_KEYS = ("lastDate", "showDateCN", "showDateEN", "date", "searchDate", "tradeDate")

#: The documented publication instant of each ChinaMoney series (Beijing time), used as the
#: event and publication time when the payload prints only a date: CFETS announces the central
#: parity at 09:15, SHIBOR at 11:00, the repo fixings (FR/FDR) at 11:00.
_CM_RELEASE: dict[str, tuple[int, int]] = {
    "central_parity": (9, 15), "shibor": (11, 0), "repo_fixing": (11, 0)}


def _cm_metric(url: str, rec: dict[str, Any]) -> str:
    low = url.lower()
    if "shibor" in low or "shibor" in rec:
        return "shibor"
    if "ccpr" in low or "vrtEName" in rec or "vrtCode" in rec:
        return "central_parity"
    if re.search(r"/(frr|fdr|fr|repo|prr)", low):
        return "repo_fixing"
    return "value"


def _cm_stamp(text: Any, metric: str) -> tuple[datetime | None, str]:
    dt, basis = parse_local_datetime(str(text or ""), 8)
    if dt is None:
        return None, basis
    if basis.startswith("printed date only") and metric in _CM_RELEASE:
        hh, mm = _CM_RELEASE[metric]
        local = dt.astimezone(CST)
        return (datetime(local.year, local.month, local.day, hh, mm, tzinfo=CST),
                f"printed date; the documented {hh:02d}:{mm:02d} Beijing release of {metric}")
    return dt, basis


def parse_chinamoney(body: bytes, source_id: str, url: str) -> AdapterResult:
    """ccpr.json (today's parities), CcprHisNew (parity history), shibor / repo-fixing JSON."""
    doc = _json(body)
    if not isinstance(doc, dict):
        return AdapterResult("PARSE_ERROR", "chinamoney", why="not a JSON object")
    data: dict[str, Any] = doc["data"] if isinstance(doc.get("data"), dict) else {}
    recs = [r for r in (doc.get("records") or []) if isinstance(r, dict)]
    obs: list[dict[str, Any]] = []
    head = data.get("head") or data.get("searchlist") or doc.get("head")
    # ---- history: data.head names the pairs, each record is {date, values[]}
    if recs and isinstance(head, list) and isinstance(recs[0].get("values"), list):
        names = [str(h) for h in head]
        for r in recs:
            ev, basis = _cm_stamp(r.get("date"), "central_parity")
            if ev is None:
                continue
            for name, raw in zip(names, r.get("values") or [], strict=False):
                v = to_number(raw)
                if v is None:
                    continue
                obs.append(observation(source_id=source_id, dataset_id=f"{source_id}:history",
                                       entity=name, metric="central_parity", value=v,
                                       unit=f"CNY per {name.split('/')[0]}" if "/" in name
                                       else None, event_time=ev,
                                       publication_time=_iso(ev), period=_isoz(ev)[:10],
                                       basis=basis))
        if obs:
            return AdapterResult("PARSED", "chinamoney_history", obs,
                                 publication_time=None,
                                 publication_basis="per-row: the 09:15 Beijing announcement")
        return AdapterResult("NO_TABLE", "chinamoney_history", why="history carried no values")
    if not recs:
        return AdapterResult("NO_TABLE", "chinamoney",
                             why="no `records` list in the document (route changed?)")
    metric = _cm_metric(url, recs[0])
    stamp_raw = next((data.get(k) for k in _CM_DATE_KEYS if data.get(k)), None)
    if stamp_raw is None:
        stamp_raw = next((recs[0].get(k) for k in _CM_DATE_KEYS if recs[0].get(k)), None)
    ev, basis = _cm_stamp(stamp_raw, metric)
    if ev is None:
        # NO DATE, NO ROW. A parity with no date cannot be placed in time, and stamping it at the
        # fetch would put yesterday's fix into today's history on a stale payload.
        return AdapterResult("PARSE_ERROR", "chinamoney",
                             why=f"the payload prints no date in data.{'/'.join(_CM_DATE_KEYS)}")
    for r in recs:
        label = next((str(r[k]) for k in _CM_LABEL_KEYS if r.get(k)), "")
        val = next((to_number(r[k]) for k in _CM_VALUE_KEYS if to_number(r.get(k)) is not None),
                   None)
        if not label or val is None:
            continue
        unit = ("percent" if metric in ("shibor", "repo_fixing")
                else f"CNY per {label.split('/')[0]}" if "/" in label else None)
        obs.append(observation(source_id=source_id, dataset_id=f"{source_id}:{metric}",
                               entity=label, metric=metric, value=val, unit=unit, event_time=ev,
                               publication_time=_iso(ev), period=_isoz(ev)[:10], basis=basis))
    if not obs:
        return AdapterResult("NO_TABLE", "chinamoney", why="records carried no label/value pair")
    return AdapterResult("PARSED", f"chinamoney_{metric}", obs, publication_time=_iso(ev),
                         publication_basis=basis)


# ----------------------------------------------------------------------------- NBS easyquery
#: Sub-index names (Chinese and the English site's) -> canonical metric. ORDER MATTERS: the
#: longer, more specific phrase is tested first ("new export orders" before "new orders").
NBS_PMI_NAMES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("新出口订单", "new export order"), "new_export_orders"),
    (("新订单", "new order"), "new_orders"),
    (("在手订单", "backlog"), "backlog_orders"),
    (("产成品库存", "finished goods"), "finished_goods_inventory"),
    (("原材料库存", "stocks of major raw", "raw materials inventor"), "raw_material_inventory"),
    (("购进价格", "input price", "purchase price"), "input_prices"),
    (("出厂价格", "ex-factory", "output price"), "output_prices"),
    (("销售价格", "sales price", "charge price"), "output_prices"),
    (("从业人员", "employ"), "employment"),
    (("供应商配送", "delivery"), "supplier_delivery"),
    (("业务活动预期", "生产经营活动预期", "expectation"), "expectations"),
    (("采购量", "quantity of purchase"), "purchase_quantity"),
    (("进口", "import"), "imports"),
    (("商务活动", "business activit"), "business_activity"),
    (("生产指数", "production index", "output index"), "production"),
    (("综合pmi产出", "composite"), "composite_output"),
    (("采购经理", "purchasing manager", "pmi"), "pmi"),
)

#: easyquery indicator parents -> dataset. A0B01 manufacturing PMI, A0B02 non-manufacturing,
#: A0B03 composite (the NBS monthly database `hgyd`).
NBS_DATASETS: dict[str, str] = {"A0B01": "pmi_mfg", "A0B02": "pmi_nonmfg", "A0B03": "pmi_composite"}


def nbs_metric(name: str, code: str) -> str:
    low = name.lower()
    for keys, metric in NBS_PMI_NAMES:
        if any(k in low for k in keys):
            return metric
    return re.sub(r"[^a-z0-9]+", "_", code.lower()).strip("_") or "value"


def parse_nbs_easyquery(body: bytes, source_id: str, url: str) -> AdapterResult:
    """The easyquery cube: `returndata.datanodes` values, `returndata.wdnodes` code->name/unit."""
    doc = _json(body)
    rd = doc.get("returndata") if isinstance(doc, dict) else None
    if not isinstance(rd, dict):
        why = (f"returncode {doc.get('returncode')}" if isinstance(doc, dict)
               else "not JSON (the portal answers HTML to an unparameterised query)")
        return AdapterResult("PARSE_ERROR", "nbs_easyquery", why=why)
    names: dict[str, tuple[str, str | None]] = {}
    for wd in rd.get("wdnodes") or []:
        if not isinstance(wd, dict) or wd.get("wdcode") != "zb":
            continue
        for node in wd.get("nodes") or []:
            if isinstance(node, dict) and node.get("code"):
                names[str(node["code"])] = (str(node.get("cname") or node.get("name") or ""),
                                            node.get("unit") or None)
    obs: list[dict[str, Any]] = []
    for dn in rd.get("datanodes") or []:
        if not isinstance(dn, dict):
            continue
        dat = dn.get("data") or {}
        if not dat.get("hasdata", True):
            continue
        v = to_number(dat.get("data") if dat.get("data") is not None else dat.get("strdata"))
        codes = {str(w.get("wdcode")): str(w.get("valuecode"))
                 for w in dn.get("wds") or [] if isinstance(w, dict)}
        zb, sj = codes.get("zb"), codes.get("sj")
        mo = parse_month(sj) if sj else None
        if v is None or zb is None or mo is None:
            continue
        cname, unit = names.get(zb, ("", None))
        parent = next((p for p in NBS_DATASETS if zb.startswith(p)), "")
        dataset = NBS_DATASETS.get(parent, "nbs")
        metric = nbs_metric(cname, zb)
        sched = None
        if dataset.startswith("pmi"):
            # NBS publishes the official PMIs on the LAST DAY of the reference month at 09:30
            # Beijing (NBS release calendar). A scheduled instant, not a measured one: the
            # knowable instant is bounded again by the receipt in `asia_parser`.
            y, m = mo
            last = month_end(y, m)
            sched = _iso(datetime(last.year, last.month, last.day, 9, 30, tzinfo=CST))
        obs.append(observation(source_id=source_id, dataset_id=f"{source_id}:{dataset}",
                               entity=dataset, metric=metric, value=v, unit=unit,
                               event_time=month_end(*mo), scheduled_time=sched,
                               period=f"{mo[0]:04d}-{mo[1]:02d}",
                               basis=f"NBS {zb} {cname}"[:120]))
    if not obs:
        return AdapterResult("NO_TABLE", "nbs_easyquery", why="the cube carried no data nodes")
    return AdapterResult("PARSED", "nbs_easyquery", obs,
                         publication_basis="scheduled (PMI) or the registry lag (others)")


# ----------------------------------------------------------------------------- SAFE
#: SAFE row labels -> canonical metric, tested on the full label PATH (section/label). The
#: path carries the section, so `结汇/代客结汇` and `售汇/代客售汇` stay apart.
SAFE_LABELS: tuple[tuple[str, str], ...] = (
    ("远期结汇", "forward_settlement"), ("远期售汇", "forward_sales"),
    ("期权", "options"),
    ("银行自身结汇", "bank_own_settlement"), ("银行自身售汇", "bank_own_sales"),
    ("代客结汇", "customer_settlement"), ("代客售汇", "customer_sales"),
    ("涉外收入", "receipts"), ("涉外收款", "receipts"), ("收入", "receipts"), ("收款", "receipts"),
    ("涉外支出", "payments"), ("涉外付款", "payments"), ("支出", "payments"), ("付款", "payments"),
    ("外汇储备", "fx_reserves"), ("黄金", "gold_reserves"),
    ("特别提款权", "sdr_holdings"), ("基金组织储备头寸", "imf_reserve_position"),
    ("官方储备资产", "official_reserve_assets"),
    ("差额", "net"), ("结汇", "settlement"), ("售汇", "sales"),
)


def safe_metric(path: str) -> str:
    """The canonical metric of a SAFE label path; the section prefixes a sub-item's metric."""
    leaf = path.split("/")[-1]
    section = path.split("/")[0] if "/" in path else ""
    for key, metric in SAFE_LABELS:
        if key in leaf:
            if metric in ("net", "customer_settlement", "customer_sales", "bank_own_settlement",
                          "bank_own_sales") and section:
                sec = safe_metric(section)
                if metric == "net" and sec not in ("net", "value"):
                    return f"{sec}_net"
            return metric
    return re.sub(r"\s+", "_", leaf)[:60] or "value"


def _safe_unit(text: str) -> str | None:
    for u in ("亿元人民币", "亿美元", "万盎司", "亿SDR", "亿元"):
        if u in text:
            return u
    return None


def _is_index_page(url: str) -> bool:
    return url.rstrip("/").lower().endswith(("index.html", "index.htm")) or url.endswith("/")


def parse_safe(body: bytes, ctype: str, source_id: str, url: str,
               country: str = "cn") -> AdapterResult:
    """SAFE index -> article addresses; article -> inline tables + attachments; xlsx -> values."""
    low = url.lower().split("?")[0]
    if body[:4] == b"PK\x03\x04" or low.endswith(".xlsx"):
        sheets = xlsx_sheets(body)
        if not sheets:
            return AdapterResult("PARSE_ERROR", "safe_xlsx", why="not a readable .xlsx")
        return _safe_from_tables(sheets, source_id, url, None, "", "safe_xlsx")
    if low.endswith(".xls") or body[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        return AdapterResult("NEEDS_PARSER", "safe_xls",
                             why=("a legacy BIFF .xls needs xlrd, which is not in the "
                                  "requirements files; the bytes are vaulted and the article's "
                                  "inline table is the parsed copy where SAFE prints one"))
    text = body.decode("utf-8", errors="replace")
    pub, basis = page_publication_time(text, country)
    tables = html_tables(text)
    attach = data_links(text, url)
    res = _safe_from_tables(tables, source_id, url, pub, basis, "safe_article",
                            page_unit=_safe_unit(_strip_tags(text)[:4000]))
    if res.status == "PARSED":
        res.endpoints = attach
        return res
    if attach:
        return AdapterResult("INDEX_PAGE", "safe_article", endpoints=attach,
                             publication_time=pub, publication_basis=basis,
                             why="article with data attachments and no month table inline")
    # AN INDEX: the release articles it lists are the payload. Same-host article links only,
    # newest first as the page orders them; the collector fetches them as derived sources.
    host = urlsplit(url).netloc
    arts = [h for h, _t in _anchors(text, url)
            if urlsplit(h).netloc == host and re.search(r"/\d{4}/\d{4}/\d+\.html?$", h)]
    arts = list(dict.fromkeys(arts))[:24]
    if arts:
        return AdapterResult("INDEX_PAGE", "safe_index", endpoints=arts,
                             why="SAFE index page: its release articles are handed to the "
                                 "collector; values are read from the articles")
    return AdapterResult("NO_TABLE", "safe", publication_time=pub, publication_basis=basis,
                         why="no month table, no attachment and no release-article link")


def _safe_from_tables(tables: list[list[list[str]]], source_id: str, url: str,
                      pub: str | None, basis: str, kind: str,
                      page_unit: str | None = None) -> AdapterResult:
    obs: list[dict[str, Any]] = []
    for ti, rows in enumerate(tables[:12]):
        unit_hint = _safe_unit(" ".join(" ".join(r) for r in rows[:4])) or page_unit
        for path, (y, m), v, unit in melt_wide_months(rows, unit_hint=unit_hint):
            metric = safe_metric(path)
            obs.append(observation(source_id=source_id, dataset_id=f"{source_id}:t{ti}",
                                   entity=path[:80], metric=metric, value=v, unit=unit,
                                   event_time=month_end(y, m), publication_time=pub,
                                   period=f"{y:04d}-{m:02d}", basis=f"SAFE table {ti}"))
    if not obs:
        return AdapterResult("NO_TABLE", kind, publication_time=pub, publication_basis=basis,
                             why="no table with three or more month columns or rows")
    return AdapterResult("PARSED", kind, obs, publication_time=pub, publication_basis=basis)


# ----------------------------------------------------------------------------- PBOC OMO
_OMO_OP = re.compile(r"开展了?\s*(\d+(?:\.\d+)?)\s*亿元\s*(\d+)\s*天期?\s*(逆回购|正回购)")
_OMO_OP_ALT = re.compile(r"开展了?\s*(\d+(?:\.\d+)?)\s*亿元\s*(逆回购|正回购)操作"
                         r"[^。]*?期限为?\s*(\d+)\s*天")
_OMO_MATURE = re.compile(r"(\d+(?:\.\d+)?)\s*亿元\s*逆回购到期")
_OMO_NONE_MATURE = re.compile(r"(?:无|没有)逆回购到期")
_OMO_RATE = re.compile(r"(?:中标利率|操作利率)\s*为?\s*(\d+(?:\.\d+)?)\s*%")


def parse_pboc_omo(body: bytes, source_id: str, url: str, country: str = "cn") -> AdapterResult:
    """OMO announcement -> amount by tenor, maturing amount, net injection; index -> articles."""
    text = body.decode("utf-8", errors="replace")
    plain = _strip_tags(text)
    pub, basis = page_publication_time(text, country)
    if pub is None:
        dt, b2 = parse_local_datetime(plain[:4000], 8)
        pub, basis = _iso(dt), f"{b2} (first date in the announcement text)"
    ops = [(float(a), int(t), kind) for a, t, kind in _OMO_OP.findall(plain)]
    ops += [(float(a), int(t), kind) for a, kind, t in _OMO_OP_ALT.findall(plain)]
    if not ops:
        host = urlsplit(url).netloc
        arts = [h for h, t in _anchors(text, url)
                if urlsplit(h).netloc == host and "公开市场业务交易公告" in t]
        arts = list(dict.fromkeys(arts))[:24]
        if arts:
            return AdapterResult("INDEX_PAGE", "pboc_omo_index", endpoints=arts,
                                 why="OMO announcement index: articles handed to the collector")
        return AdapterResult("NO_TABLE", "pboc_omo", why="no operation sentence and no "
                                                         "announcement links")
    if pub is None:
        return AdapterResult("PARSE_ERROR", "pboc_omo", why="operations found and no date")
    ev = pub
    obs: list[dict[str, Any]] = []
    injected = 0.0
    for amount, tenor, kind in ops:
        signed = amount if kind == "逆回购" else -amount
        injected += signed
        obs.append(observation(source_id=source_id, dataset_id=f"{source_id}:omo",
                               entity=f"{tenor}d_{'reverse_repo' if signed > 0 else 'repo'}",
                               metric="omo_operation", value=amount, unit="亿元",
                               event_time=ev, publication_time=pub, period=ev[:10],
                               basis=basis))
    for r in _OMO_RATE.findall(plain)[:3]:
        obs.append(observation(source_id=source_id, dataset_id=f"{source_id}:omo",
                               entity="operation_rate", metric="omo_rate", value=float(r),
                               unit="percent", event_time=ev, publication_time=pub,
                               period=ev[:10], basis=basis))
        break
    mature = _OMO_MATURE.search(plain)
    maturing = (float(mature.group(1)) if mature
                else 0.0 if _OMO_NONE_MATURE.search(plain) else None)
    if maturing is not None:
        obs.append(observation(source_id=source_id, dataset_id=f"{source_id}:omo",
                               entity="reverse_repo", metric="omo_maturing", value=maturing,
                               unit="亿元", event_time=ev, publication_time=pub,
                               period=ev[:10], basis=basis))
        obs.append(observation(source_id=source_id, dataset_id=f"{source_id}:omo",
                               entity="net", metric="omo_net_injection",
                               value=injected - maturing, unit="亿元", event_time=ev,
                               publication_time=pub, period=ev[:10], basis=basis))
    # else: the net is UNMEASURED -- the announcement did not say what matured, and a zero
    # here would read as "no drain" on a day that may have had one.
    return AdapterResult("PARSED", "pboc_omo", obs, publication_time=pub,
                         publication_basis=basis)


# ----------------------------------------------------------------------------- customs
_CUSTOMS_TITLE = re.compile(r"(\d{4})\s*年\s*(\d{1,2})\s*月[^<]{0,40}?(进口|出口|进出口)")


def _first(*idx: int | None) -> int | None:
    """The first index that is not None -- `a or b` would discard a legitimate column 0."""
    return next((i for i in idx if i is not None), None)


def _hdr_find(hdr: list[str], must: tuple[str, ...], avoid: tuple[str, ...] = ()) -> int | None:
    for j, h in enumerate(hdr):
        if all(m in h for m in must) and not any(a in h for a in avoid):
            return j
    return None


def parse_customs(body: bytes, source_id: str, url: str, country: str = "cn") -> AdapterResult:
    """Commodity (x country x port where the table prints them) quantity, value, unit value."""
    text = body.decode("utf-8", errors="replace")
    pub, basis = page_publication_time(text, country)
    plain = _strip_tags(text)
    tm = _CUSTOMS_TITLE.search(plain)
    tables = html_tables(text)
    obs: list[dict[str, Any]] = []
    if tm is not None:
        y, mo, direction = int(tm.group(1)), int(tm.group(2)), tm.group(3)
        dir_key = {"进口": "import", "出口": "export"}.get(direction, "trade")
        cur = ("万元" if "万元" in plain[:3000] else "千美元" if "千美元" in plain[:3000]
               else "亿元" if "亿元" in plain[:3000] else None)
        for ti, rows in enumerate(tables[:6]):
            # headers can span two rows (当月 / 累计 over 数量 / 金额): join them per column
            width = max(len(r) for r in rows)
            grid = [r + [""] * (width - len(r)) for r in rows]
            hdr_n = 2 if any("数量" in c or "金额" in c for c in grid[1]) else 1
            hdr = [" ".join(grid[i][j] for i in range(hdr_n)).strip() for j in range(width)]
            name_j = _first(_hdr_find(hdr, ("名称",)), _hdr_find(hdr, ("国别",)),
                            _hdr_find(hdr, ("国家",)))
            qty_j = _hdr_find(hdr, ("数量",), ("累计", "同比", "计量"))
            val_j = _hdr_find(hdr, ("金额",), ("累计", "同比"))
            unit_j = _first(_hdr_find(hdr, ("计量单位",)), _hdr_find(hdr, ("单位",), ("金额",)))
            code_j = _first(_hdr_find(hdr, ("编码",)), _hdr_find(hdr, ("税号",)))
            partner_j = _first(_hdr_find(hdr, ("贸易伙伴",)), _hdr_find(hdr, ("国别",), ("名称",)))
            port_j = _first(_hdr_find(hdr, ("关区",)), _hdr_find(hdr, ("口岸",)),
                            _hdr_find(hdr, ("注册地",)))
            if name_j is None or (qty_j is None and val_j is None):
                continue
            for r in grid[hdr_n:]:
                name = r[name_j].strip()
                if not name or to_number(name) is not None:
                    continue
                parts = [name]
                if code_j is not None and r[code_j]:
                    parts.append(f"hs={r[code_j]}")
                if partner_j is not None and partner_j != name_j and r[partner_j]:
                    parts.append(f"country={r[partner_j]}")
                if port_j is not None and r[port_j]:
                    parts.append(f"port={r[port_j]}")
                entity = "|".join(parts)[:120]
                qty = to_number(r[qty_j]) if qty_j is not None else None
                val = to_number(r[val_j]) if val_j is not None else None
                qunit = r[unit_j] if unit_j is not None else None
                common: dict[str, Any] = {
                          "source_id": source_id, "dataset_id": f"{source_id}:t{ti}",
                          "entity": entity, "event_time": month_end(y, mo),
                          "publication_time": pub, "period": f"{y:04d}-{mo:02d}",
                          "basis": f"customs {direction} table {ti}"}
                if qty is not None:
                    obs.append(observation(metric=f"{dir_key}_quantity", value=qty,
                                           unit=qunit, **common))
                if val is not None:
                    obs.append(observation(metric=f"{dir_key}_value", value=val, unit=cur,
                                           **common))
                if qty and val is not None and qty != 0:
                    obs.append(observation(metric=f"{dir_key}_unit_value", value=val / qty,
                                           unit=f"{cur or '?'}/{qunit or '?'}", **common))
    if obs:
        return AdapterResult("PARSED", "customs_table", obs, publication_time=pub,
                             publication_basis=basis)
    host = urlsplit(url).netloc
    arts = [h for h, t in _anchors(text, url)
            if urlsplit(h).netloc == host and ("量值表" in t or "国别" in t or "主要商品" in t)]
    arts = list(dict.fromkeys(arts))[:24] + data_links(text, url)
    if arts:
        return AdapterResult("INDEX_PAGE", "customs_index", endpoints=arts,
                             why="customs table index: the commodity/country tables it lists "
                                 "are handed to the collector")
    return AdapterResult("NO_TABLE", "customs",
                         why=("no dated commodity/country table and no table links"
                              if tm is None else "titled table with no quantity/value columns"))


# =============================================================================== dispatch
def parse(adapter: str, body: bytes, ctype: str, url: str, source_id: str,
          country: str = "cn") -> AdapterResult | None:
    """The declared adapter's reading of one payload, or None when the adapter is unknown.

    Never raises: a reader that throws is a PARSE_ERROR with the exception named, so one bad
    payload costs that payload and not the parser pass."""
    try:
        if adapter == "chinamoney":
            return parse_chinamoney(body, source_id, url)
        if adapter == "nbs_easyquery":
            return parse_nbs_easyquery(body, source_id, url)
        if adapter == "safe":
            return parse_safe(body, ctype, source_id, url, country)
        if adapter == "pboc_omo":
            return parse_pboc_omo(body, source_id, url, country)
        if adapter == "customs":
            return parse_customs(body, source_id, url, country)
    except Exception as exc:
        return AdapterResult("PARSE_ERROR", adapter,
                             why=f"{type(exc).__name__}: {str(exc)[:120]}")
    return None
