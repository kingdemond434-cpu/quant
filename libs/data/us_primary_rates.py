"""US RATES FROM THEIR PRIMARY PUBLISHERS -- the replacement for FRED's copies of them.

FRED is terms-refused (governance ruling 2026-11-13, `libs.data.terms_refused`). The Treasury
and the Federal Reserve Bank of New York publish the same numbers themselves, on terms that allow
the desk's use:

  US Treasury     daily par nominal and real yield curves, one CSV per year
                  (home.treasury.gov/resource-center/data-chart-center/interest-rates/). A US
                  government work, public domain (17 U.S.C. 105); robots.txt "Allow: /".
  NY Fed          EFFR and SOFR via the Markets API (markets.newyorkfed.org/api/rates/...). The
                  terms of use (newyorkfed.org/privacy/termsofuse, 2023-06-09) license use "for
                  your personal or business purposes" and allow access "manually or through an
                  automated process or device"; attribution is required (`NYFED_NOTICE`). SOFR is
                  computed from data DTCC licenses to the NY Fed, which the same terms cover.

FRED ids served, so a caller keyed on the old ids changes nothing but its source:

  DGS1MO DGS3MO DGS6MO DGS1 DGS2 DGS3 DGS5 DGS7 DGS10 DGS20 DGS30   Treasury nominal curve
  DFII5 DFII7 DFII10 DFII20 DFII30                                  Treasury real curve
  T10Y2Y = DGS10 - DGS2, T10YIE = DGS10 - DFII10, T5YIE = DGS5 - DFII5  (FRED's own definitions)
  DFF (EFFR), SOFR                                                  NY Fed

FAIL CLOSED: robots.txt is read for the agent sent before each host's first request (a 404
allows; any other failure, an HTML body or a Disallow refuses), and a refusal returns nothing.
Values are dated by their observation day; each is known after that day's publication (Treasury
curves ~15:30-18:00 ET, EFFR/SOFR the next business morning), so a caller keeps its own
one-day publication lag.
"""
from __future__ import annotations

import csv
import io
import json
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime

AGENT = "quant-desk-research/1.0 (primary publishers; robots-respecting)"
TREASURY = ("https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
            "daily-treasury-rates.csv/{year}/all?type={kind}&field_tdr_date_value={year}"
            "&page&_format=csv")
NOMINAL, REAL = "daily_treasury_yield_curve", "daily_treasury_real_yield_curve"
NYFED = "https://markets.newyorkfed.org/api/rates/{path}/search.json?{query}"
NYFED_PATHS = {"DFF": "unsecured/effr", "SOFR": "secured/sofr"}
NYFED_NOTICE = ("Content from the New York Fed subject to the Terms of Use at newyorkfed.org "
                "(reference rate data: EFFR, SOFR)")

#: FRED id -> Treasury column, per curve. Columns are matched case-insensitively.
NOMINAL_COLS = {"DGS1MO": "1 mo", "DGS3MO": "3 mo", "DGS6MO": "6 mo", "DGS1": "1 yr",
                "DGS2": "2 yr", "DGS3": "3 yr", "DGS5": "5 yr", "DGS7": "7 yr",
                "DGS10": "10 yr", "DGS20": "20 yr", "DGS30": "30 yr"}
REAL_COLS = {"DFII5": "5 yr", "DFII7": "7 yr", "DFII10": "10 yr", "DFII20": "20 yr",
             "DFII30": "30 yr"}
SPREADS = {"T10Y2Y": ("DGS10", "DGS2"), "T10YIE": ("DGS10", "DFII10"),
           "T5YIE": ("DGS5", "DFII5")}
SERVED = frozenset({*NOMINAL_COLS, *REAL_COLS, *SPREADS, *NYFED_PATHS})

Get = Callable[[str], tuple[int | None, bytes]]
Refusal = Callable[[str], str | None]


class CrossHostRedirect(urllib.error.URLError):
    """A redirect off the host whose robots and terms were read: refused, never followed."""


class _SameHostRedirects(urllib.request.HTTPRedirectHandler):
    """Follow a 3xx only when it stays on the requested host. A redirect to another host would
    reach one whose robots and terms nobody read -- a *.stlouisfed.org target would even step
    round `terms_refused` -- so it fails the fetch instead (Auditor MF1, 2026-11-13)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        old = urllib.parse.urlsplit(req.full_url).netloc.lower()
        new = urllib.parse.urlsplit(urllib.parse.urljoin(req.full_url, newurl)).netloc.lower()
        if new != old:
            raise CrossHostRedirect(f"redirect {old} -> {new} refused")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_SameHostRedirects())


def http_get(url: str) -> tuple[int | None, bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": AGENT, "Accept": "*/*"})
    try:
        with _OPENER.open(req, timeout=30) as r:
            return int(r.status), r.read(30_000_000)
    except urllib.error.HTTPError as e:
        return e.code, b""
    except Exception:
        return None, b""


def robots_refusal(get: Get = http_get) -> Refusal:
    """A per-host robots gate for AGENT, fail closed, read once per host."""
    seen: dict[str, str | urllib.robotparser.RobotFileParser] = {}

    def refuse(url: str) -> str | None:
        p = urllib.parse.urlsplit(url)
        host = f"{p.scheme}://{p.netloc}"
        if host not in seen:
            code, body = get(host + "/robots.txt")
            text = body.decode("utf-8", "replace")
            if code == 404:                    # no robots file: everything is allowed
                empty = urllib.robotparser.RobotFileParser()
                empty.parse([])
                seen[host] = empty
            elif code != 200 or text.lstrip()[:1] == "<":
                seen[host] = f"robots.txt unreadable (HTTP {code})"
            else:
                rp = urllib.robotparser.RobotFileParser()
                rp.parse(text.splitlines())
                seen[host] = rp
        rule = seen[host]
        if isinstance(rule, str):
            return rule
        return None if rule.can_fetch(AGENT, url) else "robots.txt disallows this path"
    return refuse


def _num(v: object) -> float | None:
    try:
        return float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def parse_treasury(raw: bytes) -> dict[str, dict[str, float]]:
    """{column (lower case): {iso date: value}}; a blank cell is absent, never zero."""
    out: dict[str, dict[str, float]] = {}
    rows = list(csv.reader(io.StringIO(raw.decode("utf-8-sig", "replace"))))
    if not rows:
        return out
    head = [h.strip().lower() for h in rows[0]]
    for r in rows[1:]:
        if not r:
            continue
        try:
            m, d, y = (int(x) for x in r[0].strip().split("/"))
            day = date(y, m, d).isoformat()
        except ValueError:
            continue
        for col, cell in zip(head[1:], r[1:], strict=False):
            v = _num(cell)
            if v is not None:
                out.setdefault(col, {})[day] = v
    return out


def parse_nyfed(raw: bytes) -> dict[str, float]:
    try:
        doc = json.loads(raw.decode("utf-8", "replace"))
    except ValueError:
        return {}
    out: dict[str, float] = {}
    recs = doc.get("refRates") if isinstance(doc, dict) else None
    for rec in recs if isinstance(recs, list) else []:
        if not isinstance(rec, dict):
            continue
        v = _num(rec.get("percentRate"))
        d = str(rec.get("effectiveDate") or "")[:10]
        if v is not None and d:
            out[d] = v
    return out


#: Per-process caches for the DEFAULT transport only (Auditor SF1): `free_data` asks for one
#: series at a time, and without these each call re-read robots.txt and every yearly curve CSV.
#: An injected `get` (tests, other callers) never touches them.
_SHARED_GATE: Refusal | None = None
_YEAR_CACHE: dict[tuple[str, int], dict[str, dict[str, float]]] = {}


def treasury_curve(kind: str, years: range, get: Get, refusal: Refusal
                   ) -> tuple[dict[str, dict[str, float]], str]:
    merged: dict[str, dict[str, float]] = {}
    why = ""
    for y in years:
        url = TREASURY.format(year=y, kind=kind)
        refused = refusal(url)
        if refused:
            return {}, f"ROBOTS_REFUSED: {refused}"
        cached = _YEAR_CACHE.get((kind, y)) if get is http_get else None
        if cached is None:
            code, raw = get(url)
            if code != 200 or not raw:
                why = f"{kind} {y}: HTTP {code}"
                continue
            cached = parse_treasury(raw)
            if get is http_get:
                _YEAR_CACHE[(kind, y)] = cached
        for col, ser in cached.items():
            merged.setdefault(col, {}).update(ser)
    return merged, "" if merged else (why or "no rows")


def series(ids: list[str] | tuple[str, ...], start: date, *, get: Get = http_get,
           refusal: Refusal | None = None, today: date | None = None
           ) -> tuple[dict[str, dict[str, float]], dict[str, str]]:
    """({fred id: {iso date: value}}, {fred id: why not}) for every id in SERVED."""
    global _SHARED_GATE
    if refusal is None and get is http_get:
        if _SHARED_GATE is None:
            _SHARED_GATE = robots_refusal(get)
        gate = _SHARED_GATE
    else:
        gate = refusal or robots_refusal(get)
    today = today or datetime.now(tz=UTC).date()
    want = [i for i in ids if i in SERVED]
    out: dict[str, dict[str, float]] = {}
    why: dict[str, str] = {i: "no primary-publisher route mapped" for i in ids if i not in SERVED}
    years = range(start.year, today.year + 1)
    need_nom = {*(i for i in want if i in NOMINAL_COLS),
                *(SPREADS[i][0] for i in want if i in SPREADS),
                *(SPREADS[i][1] for i in want if i in SPREADS and SPREADS[i][1] in NOMINAL_COLS)}
    need_real = {*(i for i in want if i in REAL_COLS),
                 *(SPREADS[i][1] for i in want if i in SPREADS and SPREADS[i][1] in REAL_COLS)}
    base: dict[str, dict[str, float]] = {}
    for kind, cols, need in ((NOMINAL, NOMINAL_COLS, need_nom), (REAL, REAL_COLS, need_real)):
        if not need:
            continue
        curve, w = treasury_curve(kind, years, get, gate)
        for fid in need:
            ser = curve.get(cols[fid], {})
            if ser:
                base[fid] = ser
            else:
                why[fid] = w or f"column {cols[fid]!r} absent"
    for fid in want:
        if fid in NOMINAL_COLS or fid in REAL_COLS:
            if fid in base:
                out[fid] = base[fid]
        elif fid in SPREADS:
            a, b = (base.get(x, {}) for x in SPREADS[fid])
            days = sorted(set(a) & set(b))
            if days:
                out[fid] = {d: round(a[d] - b[d], 4) for d in days}
            else:
                why[fid] = why.get(SPREADS[fid][0]) or why.get(SPREADS[fid][1]) or "no overlap"
        elif fid in NYFED_PATHS:
            q = urllib.parse.urlencode({"startDate": start.isoformat(),
                                        "endDate": today.isoformat()})
            url = NYFED.format(path=NYFED_PATHS[fid], query=q)
            refused = gate(url)
            if refused:
                why[fid] = f"ROBOTS_REFUSED: {refused}"
                continue
            code, raw = get(url)
            ser = parse_nyfed(raw) if code == 200 else {}
            if ser and fid == "DFF":
                ser = calendar_fill(ser, today)
            if ser:
                out[fid] = ser
            else:
                why[fid] = f"HTTP {code}" if code != 200 else "no rows"
    for fid in out:
        why.pop(fid, None)
    return out, why


def calendar_fill(ser: Mapping[str, float], today: date) -> dict[str, float]:
    """FRED's DFF is a CALENDAR-day series: a weekend or holiday carries the prior business day's
    rate. The NY Fed publishes EFFR on business days only, so under the DFF id the gaps are
    filled forward -- up to `today`'s eve, never past the last published day's next morning."""
    from datetime import timedelta
    if not ser:
        return {}
    days = sorted(ser)
    out: dict[str, float] = {}
    d = date.fromisoformat(days[0])
    last = date.fromisoformat(days[-1])
    v = ser[days[0]]
    while d <= last:
        v = ser.get(d.isoformat(), v)
        out[d.isoformat()] = v
        d += timedelta(days=1)
    return out


def source_of(fid: str) -> str:
    if fid in NYFED_PATHS:
        return "NY Fed Markets API (" + NYFED_NOTICE + ")"
    return "US Treasury daily par yield curves (public domain)"


def as_rows(ser: Mapping[str, float]) -> list[tuple[str, float]]:
    return sorted(ser.items())
