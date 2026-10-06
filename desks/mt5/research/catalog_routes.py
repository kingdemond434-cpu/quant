"""CATALOG ROUTES: open-world dataset discovery through the machine-readable doors portals publish.

WHY THIS EXISTS (2026-10-06). The desk's discovery path finds data by READING PAGES: the world
crawler and `deep_forest_miner` follow links and regex `.csv` out of HTML, and `index_discovery`
collects addresses without resolving them. But most of the world's public statistics are not
linked from anywhere a crawler starts; they are listed, with their download URLs, in catalogue
APIs that every open-data portal, statistics office, central bank and satellite archive exposes
for exactly this purpose. One CKAN page names a hundred datasets AND their resource URLs; one SDMX
dataflow listing names every table a statistics office publishes; one STAC page names every
satellite product family. This organ reads those doors, nothing else:

    ckan          /api/3/action/package_search?rows=N&start=K   resources[].url with a data format
    dcat_pod      /data.json (Project Open Data)                distribution downloadURL/accessURL
    dcat_jsonld   DCAT-AP JSON-LD catalogues, hydra-paged       distribution downloadURL/accessURL
    opendatasoft  /api/explore/v2.1/catalog/datasets            per-dataset CSV export URL
    sdmx          /dataflow listings                            concrete data URLs (csv where the
                                                                API supports it)
    stac          /collections and /search, `next`-paged        observation classes; tabular asset
                                                                hrefs only as endpoints
    cdx           Common Crawl CDX over producer domains         data files search engines miss
    keyed         a portal that needs a credential               recorded NEEDS_KEY, never dropped
    probe         an API whose shape no route parses yet         recorded UNMEASURED, never zero

ONE DISCOVERY PATH, NOT A SECOND ONE. Rows go to `data/intelligence/world/discoveries_catalog_
<YYYYMMDD>.json` in the shape `acquire_datasets._endpoints` already reads (`host`, `endpoints`),
so fetching, parsing, PIT certification and registration stay where they are. This module never
fetches a dataset; it fetches CATALOGUE PAGES, and resolves each dataset to the URLs a parser can
read. It is scheduled as an `hourly_discovery` organ, not by a scheduler of its own.

PAGE 1 IS NEVER THE CATALOGUE. Every route keeps a resumable cursor in `data/catalog_routes/
state.json` (atomic writes), advanced after every page, so a portal with 300,000 datasets is
enumerated across as many hours as it takes, and the UNPROCESSED REMAINDER is published per
portal as a number (or UNMEASURED when the API does not say how many it holds). A completed pass
waits `relist_days` and then re-lists with conditional requests.

NEVER REFETCH AN UNCHANGED PAGE. ETag/Last-Modified are stored per page with what that page
yielded (its next link and item count), and sent back as If-None-Match / If-Modified-Since; a 304
advances the cursor without re-reading anything. Bounded timeouts, an HONEST UA that names the
desk (never a browser string), a per-host minimum gap, a per-run request cap and a wall-clock
budget.

ROBOTS, TERMS, MANDATE. robots.txt is read once a week per host and obeyed. Platforms
under the shared terms fence (libs/data/terms_fence.py: Reddit, StockTwits, ...) and every
crypto-exchange host are refused at the request and at the endpoint (the 2026-08-18 MT5 mandate). No credential is ever sent: a keyed portal or resource
is recorded with access NEEDS_KEY, so the desk can see what a key would buy.

DEDUP WITHOUT DOUBLE COUNTING. A URL already discovered is never a new endpoint; a dataset whose
(producer, title) was already discovered through another portal -- the EU hub harvesting a national
portal, a city republishing a state file -- is kept with `mirror_of` naming the first row and its
URLs moved to `mirror_endpoints`, so it is visible and never counted or acquired twice.

    python desks/mt5/research/catalog_routes.py --budget-s 600
    python desks/mt5/research/catalog_routes.py --only ckan,sdmx --budget-s 120
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
import xml.etree.ElementTree as ET
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

ROUTES_DIR = DESK / "data" / "catalog_routes"
ROSTER = ROUTES_DIR / "roster.json"
STATE = ROUTES_DIR / "state.json"
#: Parsed listings and the dedup index: reconstructible (the index from the discoveries files,
#: the listings by one request), so gitignored like every other cache on this desk.
CACHE = ROUTES_DIR / "cache"
WORLD = DESK / "data" / "intelligence" / "world"
REPORT = DESK / "reports" / "CATALOG_ROUTES.json"
FILE_PREFIX = "discoveries_catalog_"

UNMEASURED = "UNMEASURED"
DEFAULT_BUDGET_S = 600.0
MAX_REQUESTS_PER_RUN = 400
MAX_PAGE_BYTES = 64 * 1024 * 1024
ROBOTS_REFRESH_D = 7
HTTP_META_KEEP_D = 45

# The acquirer's credential pattern, so a URL this organ calls keyed is exactly a URL the acquirer
# would skip. Imported rather than copied; the fallback only exists so a transient import failure
# in that module (it is edited by other sessions) cannot stop discovery.
try:
    from acquire_datasets import _KEYED as _ACQ_KEYED
except Exception:  # noqa: BLE001  # pragma: no cover - only when the acquirer cannot import
    _ACQ_KEYED = re.compile(r"(api[_-]?key|apikey|token=|access_key|client_id|subscription)",
                            re.IGNORECASE)
#: AN HONEST USER-AGENT. The desk names itself; it never presents as a browser to a catalogue.
UA: str = "quant-desk-catalog-routes/1.0 (public open-data catalogue discovery; research use)"
KEYED: re.Pattern[str] = _ACQ_KEYED


def _terms_platform(host: str) -> str | None:
    """The shared platform terms fence (libs/data/terms_fence.py) when it is importable. Its
    absence falls back to the roster's own social entries, which stay refused: fail closed."""
    try:
        from libs.data import terms_fence as _tf
    except Exception:  # noqa: BLE001
        return None
    return _tf.platform_of_url(f"https://{host}/")

# ----------------------------------------------------------------------------- formats ----
#: Formats the acquirer can parse (delimited text, workbooks, JSON, archives of CSV, parquet).
DATA_FORMATS = frozenset({"csv", "tsv", "xls", "xlsx", "json", "parquet", "zip", "txt",
                          "sdmx-csv", "ods", "csvdata"})
#: STAC assets count as endpoints only when tabular/numeric; rasters are observation classes.
STAC_DATA_FORMATS = frozenset({"csv", "tsv", "parquet", "json"})
#: A resource in one of these is a page ABOUT data, never an endpoint.
LANDING_FORMATS = frozenset({"html", "htm", "web page", "webpage", "landing page", "website",
                             "url", "link", "pdf", "doc", "docx", "api", "esri rest", "wms",
                             "wfs", "arcgis geoservices rest api"})
_MEDIA = {
    "text/csv": "csv", "application/csv": "csv", "text/comma-separated-values": "csv",
    "text/tab-separated-values": "tsv", "application/vnd.ms-excel": "xls",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "application/json": "json", "application/x-parquet": "parquet",
    "application/vnd.apache.parquet": "parquet", "application/parquet": "parquet",
    "application/zip": "zip", "application/x-zip-compressed": "zip", "text/plain": "txt",
    "text/html": "html", "application/xhtml+xml": "html", "application/pdf": "pdf",
    "application/geo+json": "geojson", "application/vnd.sdmx.data+csv": "sdmx-csv",
    "application/vnd.oasis.opendocument.spreadsheet": "ods",
}
_DATA_EXT = re.compile(r"\.(csv|tsv|xlsx?|json|parquet|zip|txt|ods)(\.gz)?$", re.IGNORECASE)
_FORMAT_PARAM = re.compile(
    r"[?&](format|_format|f|outputformat|downloadformat)=(csv|json|xlsx?|tsv|sdmx-csv|csvdata"
    r"|csvfilewithlabels|csvfile)(&|$)", re.IGNORECASE)
_PAGE_EXT = re.compile(r"\.(html?|php|aspx?|jsp)$", re.IGNORECASE)
#: STAC asset roles that are never a numeric product, whatever their media type.
_NON_DATA_ROLES = frozenset({"thumbnail", "overview", "tiles", "visual", "metadata"})


def norm_format(fmt: Any, media: Any = "") -> str:
    """A resource's declared format as one lower-case token ('' when nothing is declared)."""
    for raw in (media, fmt):
        s = str(raw or "").strip().lower()
        if not s:
            continue
        s = s.split(";")[0].strip()
        if s in _MEDIA:
            return _MEDIA[s]
        if "/" in s:                       # EU file-type IRIs, media types we do not map
            tail = s.rstrip("/").rsplit("/", 1)[-1]
            return _MEDIA.get(s, tail.lower())
        return s.lstrip(".")
    return ""


def _http_url(url: Any) -> bool:
    return isinstance(url, str) and url.startswith(("http://", "https://"))


def resource_kind(url: str, fmt: Any = "", media: Any = "", *, stac: bool = False,
                  roles: Iterable[str] = ()) -> str:
    """'data', 'landing', 'keyed' or 'other' for one catalogued resource. Pure.

    A landing page is never an endpoint: a resource declared HTML/PDF/web page, or one with no
    declared format whose URL is a page, is 'landing'. A credentialed URL is 'keyed' and is
    recorded, never fetched.
    """
    if not _http_url(url):
        return "other"
    if KEYED.search(url):
        return "keyed"
    allowed = STAC_DATA_FORMATS if stac else DATA_FORMATS
    if stac and set(roles) & _NON_DATA_ROLES:
        return "other"
    f = norm_format(fmt, media)
    path = urllib.parse.urlsplit(url).path
    if f in LANDING_FORMATS:
        return "landing"
    if f:
        if f in allowed:
            return "landing" if _PAGE_EXT.search(path) else "data"
        return "other"
    ext_m, fmt_m = _DATA_EXT.search(path), _FORMAT_PARAM.search(url)
    if ext_m or fmt_m:
        ext = norm_format(ext_m.group(1) if ext_m else fmt_m.group(2) if fmt_m else "")
        ext = "csv" if ext.startswith("csv") else ext
        return "data" if ext in allowed else "other"
    if _PAGE_EXT.search(path) or path in ("", "/") or not stac:
        return "landing"
    return "other"


# ------------------------------------------------------------------------------- hosts ----
def host_of(url: str) -> str:
    return (urllib.parse.urlsplit(url).hostname or "").lower()


def is_blocked(host: str, blocked: Iterable[str]) -> bool:
    """Terms-fenced platforms (the shared fence) and crypto-exchange hosts (the 2026-08-18 MT5
    mandate, from the roster). A dotted entry is a domain (and its subdomains); a bare name
    matches any host label containing it, so `data.binance.vision` is refused too."""
    h = host.lower().split(":")[0].rstrip(".")
    if h and _terms_platform(h):
        return True
    labels = h.split(".")
    for b in blocked:
        b = str(b).lower().strip()
        if not b:
            continue
        if "." in b:
            if h == b or h.endswith("." + b):
                return True
        elif any(b in label for label in labels):
            return True
    return False


def norm_url(url: str) -> str:
    """Scheme/host lower-cased, default port, fragment and trailing slash dropped; query kept."""
    try:
        p = urllib.parse.urlsplit(url.strip())
    except ValueError:
        return url.strip()
    host = (p.hostname or "").lower()
    if p.port and not ((p.scheme == "http" and p.port == 80)
                       or (p.scheme == "https" and p.port == 443)):
        host = f"{host}:{p.port}"
    path = p.path.rstrip("/") or ""
    return urllib.parse.urlunsplit((p.scheme.lower(), host, path, p.query, ""))


def title_key(producer: Any, title: Any) -> str | None:
    """(producer, title) identity for mirror detection; None when either is missing, because a
    bare title ('Budget 2020') is shared by unrelated producers."""
    p = re.sub(r"[\W_]+", " ", str(producer or "").lower()).strip()
    t = re.sub(r"[\W_]+", " ", str(title or "").lower()).strip()
    return f"{p}|{t}" if p and t else None


# ---------------------------------------------------------------------------- transport ----
@dataclass
class Response:
    status: int                     #: HTTP status; 0 = transport failure; -1 = refused locally
    body: bytes = b""
    headers: dict[str, str] = field(default_factory=dict)
    error: str = ""


Fetch = Callable[[str, Mapping[str, str], float], Response]


def urllib_fetch(url: str, headers: Mapping[str, str], timeout: float) -> Response:
    """The live transport. Never retries; a 304 and every HTTP error come back as a status."""
    req = urllib.request.Request(url, headers=dict(headers))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read(MAX_PAGE_BYTES + 1)
            hdrs = {k.lower(): v for k, v in r.headers.items()}
            return Response(int(getattr(r, "status", 200) or 200), body, hdrs)
    except urllib.error.HTTPError as e:
        hdrs = {k.lower(): v for k, v in (e.headers.items() if e.headers else [])}
        return Response(int(e.code), b"", hdrs, f"HTTP {e.code}")
    except Exception as e:  # noqa: BLE001 - every transport failure is a named status
        return Response(0, b"", {}, f"{type(e).__name__}: {str(e)[:120]}")


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat(timespec="seconds")


def _parse_iso(value: Any) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


class Session:
    """Budgeted, polite, conditional HTTP for one run. Every request in the module goes here."""

    def __init__(self, state: dict[str, Any], fetch: Fetch, *, now: datetime,
                 budget_s: float, max_requests: int, blocked: Iterable[str],
                 clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep) -> None:
        self.state = state
        self.fetch = fetch
        self.now = now
        self.clock = clock
        self.sleep = sleep
        self.started = clock()
        self.budget_s = float(budget_s)
        self.max_requests = int(max_requests)
        self.blocked = tuple(blocked)
        self.requests = 0
        self.not_modified = 0
        self.refusals: Counter[str] = Counter()
        self.labels: Counter[str] = Counter()
        self.robots_disallow: set[str] = set()
        self._last: dict[str, float] = {}
        self.http: dict[str, Any] = state.setdefault("http", {})
        self.robots: dict[str, Any] = state.setdefault("robots", {})

    def left_s(self) -> float:
        return self.budget_s - (self.clock() - self.started)

    def exhausted(self) -> bool:
        return self.requests >= self.max_requests or self.left_s() <= 0

    def _wait_turn(self, host: str, gap_s: float) -> bool:
        last = self._last.get(host)
        if last is not None:
            wait = last + gap_s - self.clock()
            if wait > 0:
                if wait >= self.left_s():
                    return False
                self.sleep(wait)
        self._last[host] = self.clock()
        return True

    def _raw(self, url: str, headers: dict[str, str], gap_s: float,
             timeout: float) -> Response | None:
        if self.exhausted():
            return None
        if not self._wait_turn(host_of(url), gap_s):
            return None
        self.requests += 1
        return self.fetch(url, headers, timeout)

    def allowed_by_robots(self, url: str, gap_s: float, timeout: float) -> tuple[bool | None, str]:
        """(allowed, why) per robots.txt, read weekly per host. allowed is None when robots.txt
        could not be read: why is BUDGET (this run is spent), UNREACHABLE or ROBOTS_HTTP_<n>."""
        p = urllib.parse.urlsplit(url)
        host = (p.hostname or "").lower()
        ent = self.robots.get(host) or {}
        at = _parse_iso(ent.get("at"))
        if at is None or self.now - at > timedelta(days=ROBOTS_REFRESH_D):
            resp = self._raw(f"{p.scheme}://{p.netloc}/robots.txt",
                             {"User-Agent": UA, "Accept": "text/plain"}, gap_s, timeout)
            if resp is None:
                return None, "BUDGET"
            if resp.status == 200:
                lines = [ln.strip() for ln in resp.body.decode("utf-8", "replace").splitlines()
                         if ln.strip().lower().startswith(("user-agent", "allow", "disallow"))]
                ent = {"at": _iso(self.now), "status": "OK", "lines": lines[:600]}
            elif 400 <= resp.status < 500:
                ent = {"at": _iso(self.now), "status": f"ABSENT_{resp.status}", "lines": []}
            elif resp.status <= 0:
                return None, "UNREACHABLE"
            else:
                return None, f"ROBOTS_HTTP_{resp.status}"
            self.robots[host] = ent
        rp = urllib.robotparser.RobotFileParser()
        rp.parse(list(ent.get("lines") or []))
        return bool(rp.can_fetch(UA, url)), "OK"

    def get(self, url: str, *, gap_s: float = 1.0, timeout: float = 25.0,
            conditional: bool = True, accept: str = "") -> Response | None:
        """One polite request. None = this run's budget is spent (not a failure of the URL)."""
        host = host_of(url)
        if is_blocked(host, self.blocked):
            self.refusals["BLOCKED_HOST"] += 1
            return Response(-1, error="BLOCKED_HOST")
        # ROBOTS IS OBEYED. A Disallow, or a robots.txt that cannot be read, refuses the request
        # and is counted; the host is also recorded so the report shows what robots cost.
        robots, why = self.allowed_by_robots(url, gap_s, timeout)
        if robots is None:
            if why == "BUDGET":
                return None
            self.refusals[why] += 1
            return Response(0 if why == "UNREACHABLE" else -1, error=why)
        if not robots:
            self.robots_disallow.add(host)
            self.refusals["ROBOTS_DISALLOWED"] += 1
            return Response(-1, error="ROBOTS_DISALLOWED")
        headers = {"User-Agent": UA,
                   "Accept": accept or "application/json, application/ld+json;q=0.9, "
                                       "application/xml;q=0.8, */*;q=0.5"}
        meta = self.http.get(url) or {}
        # A validator older than HTTP_META_KEEP_D is not sent (the page is fetched whole), but it
        # is never deleted: `remember` overwrites it with the fresh one, nothing is removed.
        seen = _parse_iso(meta.get("at"))
        fresh = seen is not None and seen >= self.now - timedelta(days=HTTP_META_KEEP_D)
        if conditional and "next" in meta and fresh:
            if meta.get("etag"):
                headers["If-None-Match"] = str(meta["etag"])
            if meta.get("last_modified"):
                headers["If-Modified-Since"] = str(meta["last_modified"])
        resp = self._raw(url, headers, gap_s, timeout)
        if resp is not None and resp.status == 304:
            self.not_modified += 1
        return resp

    def page_meta(self, url: str) -> dict[str, Any]:
        return dict(self.http.get(url) or {})

    def remember(self, url: str, resp: Response, nxt: str | None, n: int) -> None:
        """Validators plus what the page yielded, so a later 304 can advance without a body."""
        etag = resp.headers.get("etag")
        lm = resp.headers.get("last-modified")
        self.http[url] = {"etag": etag, "last_modified": lm, "next": nxt, "n": int(n),
                          "at": _iso(self.now)}


def access_status(resp: Response) -> str:
    """A non-200 answer as a named portal status. 401 is a key; 403 is ambiguous (a WAF or a
    key), so it is FORBIDDEN rather than guessed at."""
    if resp.status == -1:
        return resp.error or "REFUSED"
    if resp.status == 0:
        return "UNREACHABLE"
    if resp.status == 401:
        return "NEEDS_KEY"
    if resp.status == 403:
        return "FORBIDDEN"
    if resp.status == 429:
        return "RATE_LIMITED"
    return f"HTTP_{resp.status}"


# ----------------------------------------------------------------------------- parsing ----
def _json(body: bytes) -> Any:
    try:
        return json.loads(body.decode("utf-8", "replace"))
    except ValueError:
        return None


def _first(v: Any) -> Any:
    if isinstance(v, list):
        return v[0] if v else None
    return v


def _lp(obj: Mapping[str, Any], name: str) -> Any:
    """A JSON(-LD) property by LOCAL name: `title`, `dct:title` and the full IRI all match."""
    if name in obj:
        return obj[name]
    for k, v in obj.items():
        local = re.split(r"[#:/]", str(k))[-1]
        if local == name:
            return v
    return None


def _text(v: Any) -> str:
    """A literal from plain JSON or JSON-LD (`@value`, language maps, lists): English first."""
    v = _first(v) if isinstance(v, list) and v and not isinstance(v[0], dict) else v
    if isinstance(v, list):
        en = [x for x in v if isinstance(x, dict) and str(x.get("@language", "")).startswith("en")]
        v = (en or v)[0] if v else ""
    if isinstance(v, dict):
        if "@value" in v:
            return str(v["@value"])
        for k in ("en", "name", "title", "label", "@id"):
            if k in v and isinstance(v[k], str | int | float):
                return str(v[k])
        vals = [x for x in v.values() if isinstance(x, str)]
        return vals[0] if vals else ""
    return "" if v is None else str(v)


def _iri(v: Any) -> str:
    v = _first(v)
    if isinstance(v, dict):
        return str(v.get("@id") or v.get("@value") or "")
    return "" if v is None else str(v)


def _entry(*, id: Any, title: Any, producer: Any = "", license: Any = "", cadence: Any = "",
           landing: Any = "", dists: list[dict[str, Any]] | None = None,
           **extra: Any) -> dict[str, Any]:
    e = {"id": str(id or ""), "title": str(title or id or "").strip()[:300],
         "producer": str(producer or "").strip()[:200], "license": str(license or "")[:200],
         "cadence": str(cadence or "")[:80], "landing": str(landing or ""),
         "dists": dists or []}
    e.update({k: v for k, v in extra.items() if v not in (None, "", [], {})})
    return e


_CKAN_CADENCE_KEYS = ("frequency", "accrualPeriodicity", "accrual_periodicity",
                      "update_frequency", "frequency-of-update", "update-frequency")


def ckan_entry(pkg: Mapping[str, Any], base: str) -> dict[str, Any]:
    extras = {str(x.get("key")): x.get("value") for x in (pkg.get("extras") or [])
              if isinstance(x, dict)}
    cadence = next((pkg.get(k) or extras.get(k) for k in _CKAN_CADENCE_KEYS
                    if pkg.get(k) or extras.get(k)), "")
    org = pkg.get("organization") if isinstance(pkg.get("organization"), dict) else {}
    name = pkg.get("name") or pkg.get("id")
    return _entry(
        id=name, title=_text(pkg.get("title")) or name,
        producer=(org or {}).get("title") or pkg.get("author") or pkg.get("maintainer") or "",
        license=pkg.get("license_title") or pkg.get("license_id") or "", cadence=_text(cadence),
        landing=f"{base.rstrip('/')}/dataset/{name}" if name else "",
        dists=[{"url": r.get("url"), "format": r.get("format"),
                "media": r.get("mimetype") or r.get("mimetype_inner") or ""}
               for r in (pkg.get("resources") or []) if isinstance(r, dict)])


def parse_ckan_page(body: bytes, url: str, base: str
                    ) -> tuple[list[dict[str, Any]], str | None, int] | None:
    """(entries, next url, total) or None when the answer is not package_search's shape."""
    obj = _json(body)
    res = obj.get("result") if isinstance(obj, dict) else None
    if not (isinstance(res, dict) and isinstance(res.get("count"), int)
            and isinstance(res.get("results"), list)):
        return None
    results = [p for p in res["results"] if isinstance(p, dict)]
    q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))
    start = int(q.get("start") or 0)
    count = int(res["count"])
    nxt_start = start + len(results)
    nxt = _with_query(url, start=str(nxt_start)) if results and nxt_start < count else None
    return [ckan_entry(p, base) for p in results], nxt, count


def _with_query(url: str, **params: str) -> str:
    p = urllib.parse.urlsplit(url)
    q = dict(urllib.parse.parse_qsl(p.query, keep_blank_values=True))
    q.update(params)
    return urllib.parse.urlunsplit((p.scheme, p.netloc, p.path,
                                    urllib.parse.urlencode(q, safe=",:+"), ""))


def _dcat_dist(d: Mapping[str, Any]) -> list[dict[str, Any]]:
    fmt = _text(_lp(d, "format"))
    media = _text(_lp(d, "mediaType")) or _iri(_lp(d, "mediaType"))
    out: list[dict[str, Any]] = []
    for key in ("downloadURL", "accessURL"):
        u = _lp(d, key)
        for one in (u if isinstance(u, list) else [u]):
            href = _iri(one) if isinstance(one, dict) else (str(one) if one else "")
            if href:
                out.append({"url": href, "format": fmt or _iri(_lp(d, "format")),
                            "media": media, "via": key})
    return out


def parse_pod(body: bytes) -> list[dict[str, Any]] | None:
    """Project Open Data `data.json`: {"dataset": [...]} with distribution lists."""
    obj = _json(body)
    if not (isinstance(obj, dict) and isinstance(obj.get("dataset"), list)):
        return None
    out = []
    for ds in obj["dataset"]:
        if not isinstance(ds, dict):
            continue
        pub = ds.get("publisher")
        dists: list[dict[str, Any]] = []
        for d in ds.get("distribution") or []:
            if isinstance(d, dict):
                dists.extend(_dcat_dist(d))
        out.append(_entry(id=ds.get("identifier") or ds.get("title"), title=ds.get("title"),
                          producer=_text(pub.get("name") if isinstance(pub, dict) else pub),
                          license=_text(ds.get("license")),
                          cadence=_text(ds.get("accrualPeriodicity")),
                          landing=_text(ds.get("landingPage")), dists=dists,
                          spatial=_text(ds.get("spatial"))[:120]))
    return out


def _types(node: Mapping[str, Any]) -> set[str]:
    t = node.get("@type")
    ts = t if isinstance(t, list) else [t]
    return {re.split(r"[#:/]", str(x))[-1] for x in ts if x}


def parse_dcat_page(body: bytes) -> tuple[list[dict[str, Any]], str | None, int | None] | None:
    """A DCAT JSON-LD page (@graph, hydra-paged) or a linked-data-API page (result.items).

    Returns (entries, next url, total) or None when no dataset-bearing shape is recognised.
    """
    obj = _json(body)
    if obj is None:
        return None
    datasets: list[Mapping[str, Any]] = []
    nodes: dict[str, Mapping[str, Any]] = {}
    nxt: str | None = None
    total: int | None = None
    recognised = False
    if isinstance(obj, dict) and isinstance(obj.get("result"), dict) \
            and isinstance(obj["result"].get("items"), list):
        datasets = [x for x in obj["result"]["items"] if isinstance(x, dict)]
        nxt = _iri(obj["result"].get("next")) or None
        tot = obj["result"].get("totalResults") or obj["result"].get("total")
        total = int(tot) if isinstance(tot, int | str) and str(tot).isdigit() else None
    else:
        graph = obj.get("@graph") if isinstance(obj, dict) else obj
        if isinstance(obj, dict) and graph is None:
            graph = [obj]
        if not isinstance(graph, list):
            return None
        for n in graph:
            if not isinstance(n, dict):
                continue
            if n.get("@id"):
                nodes[str(n["@id"])] = n
            types = _types(n)
            if "Dataset" in types:
                datasets.append(n)
            if types & {"PagedCollection", "PartialCollectionView", "Collection"} or \
                    _lp(n, "nextPage") or _lp(n, "next"):
                nxt = _iri(_lp(n, "nextPage") or _lp(n, "next")) or nxt
                tot = _lp(n, "totalItems")
                tv = _text(tot)
                total = int(tv) if tv.isdigit() else total
            if types & {"PagedCollection", "PartialCollectionView", "Collection", "Catalog"}:
                recognised = True
            # a catalog node may embed its datasets
            embedded = _lp(n, "dataset") if "Catalog" in types else None
            for d in embedded if isinstance(embedded, list) else [embedded]:
                if isinstance(d, dict) and _types(d) & {"Dataset"}:
                    datasets.append(d)
        if not datasets and not recognised:
            return None
    out = []
    for ds in datasets:
        dists: list[dict[str, Any]] = []
        raw_d = _lp(ds, "distribution") or []
        for d in raw_d if isinstance(raw_d, list) else [raw_d]:
            if isinstance(d, dict) and set(d) == {"@id"}:
                d = nodes.get(str(d["@id"]), d)
            elif isinstance(d, str):
                d = nodes.get(d, {"accessURL": d})
            if isinstance(d, dict):
                dists.extend(_dcat_dist(d))
        pub = _lp(ds, "publisher")
        if isinstance(pub, dict) and set(pub) == {"@id"}:
            pub = nodes.get(str(pub["@id"]), pub)
        producer = _text(_lp(pub, "name")) if isinstance(pub, dict) else _text(pub)
        ident = _text(_lp(ds, "identifier")) or _iri(ds.get("@id")) or _text(_lp(ds, "_about"))
        out.append(_entry(id=ident, title=_text(_lp(ds, "title")), producer=producer,
                          license=_iri(_lp(ds, "license")) or _text(_lp(ds, "license")),
                          cadence=_iri(_lp(ds, "accrualPeriodicity")),
                          landing=_iri(_lp(ds, "landingPage")), dists=dists,
                          spatial=_iri(_lp(ds, "spatial"))[:120]))
    return out, nxt, total


def parse_ods_page(body: bytes, url: str, base: str
                   ) -> tuple[list[dict[str, Any]], str | None, int] | None:
    """Opendatasoft explore v2.1 catalogue page: per-dataset CSV export URLs."""
    obj = _json(body)
    if not (isinstance(obj, dict) and isinstance(obj.get("results"), list)
            and isinstance(obj.get("total_count"), int)):
        return None
    out = []
    for r in obj["results"]:
        if not isinstance(r, dict) or not r.get("dataset_id"):
            continue
        meta = ((r.get("metas") or {}).get("default") or {}) if isinstance(r.get("metas"),
                                                                             dict) else {}
        did = str(r["dataset_id"])
        has = r.get("has_records")
        dists = [] if has is False else [{
            "url": f"{base.rstrip('/')}/api/explore/v2.1/catalog/datasets/{did}/exports/csv",
            "format": "csv"}]
        out.append(_entry(id=did, title=meta.get("title") or did,
                          producer=meta.get("publisher") or "", license=meta.get("license"),
                          cadence=meta.get("update_frequency") or "",
                          landing=f"{base.rstrip('/')}/explore/dataset/{did}/", dists=dists))
    q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))
    off = int(q.get("offset") or 0) + len(obj["results"])
    nxt = _with_query(url, offset=str(off)) if obj["results"] and off < obj["total_count"] \
        else None
    return out, nxt, int(obj["total_count"])


def parse_sdmx_listing(body: bytes) -> list[dict[str, str]] | None:
    """Every dataflow in an SDMX-ML or SDMX-JSON structure message; None if neither."""
    head = body.lstrip()[:1]
    flows: list[dict[str, str]] = []
    if head in (b"{", b"["):
        obj = _json(body)
        if not isinstance(obj, dict):
            return None
        data = obj.get("data") if isinstance(obj.get("data"), dict) else obj
        raw = data.get("dataflows") if isinstance(data, dict) else None
        if not isinstance(raw, list):
            return None
        for f in raw:
            if isinstance(f, dict) and f.get("id"):
                names = f.get("names") if isinstance(f.get("names"), dict) else {}
                flows.append({"id": str(f["id"]), "agency": str(f.get("agencyID") or ""),
                              "version": str(f.get("version") or "latest"),
                              "name": str((names or {}).get("en") or f.get("name") or f["id"])})
        return flows
    if head != b"<":
        return None
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        return None
    if not (root.tag.endswith("Structure") or root.tag.endswith("RegistryInterface")):
        return None
    lang_attr = "{http://www.w3.org/XML/1998/namespace}lang"
    for el in root.iter():
        if not (el.tag == "Dataflow" or el.tag.endswith("}Dataflow")):
            continue
        fid = el.get("id")
        if not fid:
            continue
        names = {(n.get(lang_attr) or ""): (n.text or "").strip() for n in el
                 if n.tag.endswith("}Name") or n.tag == "Name"}
        name = names.get("en") or next(iter(names.values()), "") or fid
        flows.append({"id": fid, "agency": el.get("agencyID") or "",
                      "version": el.get("version") or "latest", "name": name})
    return flows


def sdmx_entries(flows: list[dict[str, str]], portal: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Each dataflow as a concrete data URL. Where the provider's csv support is UNMEASURED the
    SDMX-ML URL is kept under `unparsed` (the acquirer has no SDMX-ML parser), not as an endpoint."""
    base = str(portal["base"]).rstrip("/")
    tmpl = portal.get("data_template")
    xml_tmpl = portal.get("data_template_xml")
    out = []
    for f in flows:
        fill = {"base": base, "id": f["id"], "agency": f.get("agency") or "",
                "version": f.get("version") or "latest"}
        dists: list[dict[str, Any]] = []
        unparsed: list[str] = []
        if tmpl:
            dists.append({"url": str(tmpl).format(**fill), "format": "sdmx-csv"})
        elif xml_tmpl:
            unparsed.append(str(xml_tmpl).format(**fill))
        out.append(_entry(id=f["id"], title=f.get("name") or f["id"],
                          producer=portal.get("producer", ""), dists=dists,
                          landing="", unparsed=unparsed,
                          data_url=None if (tmpl or xml_tmpl) else UNMEASURED,
                          sdmx_agency=f.get("agency"), sdmx_version=f.get("version")))
    return out


def _link(obj: Mapping[str, Any], rel: str) -> str | None:
    for ln in obj.get("links") or []:
        if (isinstance(ln, dict) and ln.get("rel") == rel and ln.get("href")
                and str(ln.get("method") or "GET").upper() == "GET"):
            return str(ln["href"])
    return None


def _stac_dists(assets: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [{"url": a.get("href"), "format": "", "media": a.get("type") or "",
             "roles": list(a.get("roles") or []), "stac": True, "key": k}
            for k, a in assets.items() if isinstance(a, dict)]


def _tabular_media(media: Any) -> bool:
    return norm_format("", media) in STAC_DATA_FORMATS


def stac_collection_entry(col: Mapping[str, Any], base: str) -> dict[str, Any]:
    providers = [p for p in col.get("providers") or [] if isinstance(p, dict)]
    prod = next((p.get("name") for p in providers
                 if set(p.get("roles") or []) & {"producer", "licensor"}), None)
    item_assets = col.get("item_assets") if isinstance(col.get("item_assets"), dict) else {}
    tabular = sorted(k for k, a in (item_assets or {}).items()
                     if isinstance(a, dict) and _tabular_media(a.get("type"))
                     and not set(a.get("roles") or []) & _NON_DATA_ROLES)
    media = sorted({str(a.get("type")) for a in (item_assets or {}).values()
                    if isinstance(a, dict) and a.get("type")})
    cid = str(col.get("id") or "")
    return _entry(id=cid, title=col.get("title") or cid,
                  producer=prod or (providers[0].get("name") if providers else ""),
                  license=col.get("license") or "",
                  landing=_link(col, "self") or f"{base.rstrip('/')}/collections/{cid}",
                  dists=_stac_dists(col.get("assets") or {}),
                  observation_class=True, item_media=media, tabular_item_assets=tabular,
                  observable=(str(col.get("description") or "")[:240] or None),
                  keywords=[str(k) for k in (col.get("keywords") or [])][:12])


def parse_stac_collections(body: bytes, base: str
                           ) -> tuple[list[dict[str, Any]], str | None, int | None] | None:
    obj = _json(body)
    if not (isinstance(obj, dict) and isinstance(obj.get("collections"), list)):
        return None
    total = obj.get("numberMatched") or (obj.get("context") or {}).get("matched")
    return ([stac_collection_entry(c, base) for c in obj["collections"] if isinstance(c, dict)],
            _link(obj, "next"), int(total) if isinstance(total, int) else None)


def parse_stac_search(body: bytes, collection_title: str
                      ) -> tuple[list[dict[str, Any]], str | None, int | None] | None:
    obj = _json(body)
    if not (isinstance(obj, dict) and isinstance(obj.get("features"), list)):
        return None
    out = []
    for it in obj["features"]:
        if not isinstance(it, dict):
            continue
        iid = str(it.get("id") or "")
        props = it.get("properties") if isinstance(it.get("properties"), dict) else {}
        out.append(_entry(id=f"{it.get('collection') or ''}/{iid}",
                          title=f"{collection_title} {iid}".strip(),
                          license=(props or {}).get("license") or "",
                          landing=_link(it, "self") or "",
                          dists=_stac_dists(it.get("assets") or {}), observation_class=True,
                          observed_at=(props or {}).get("datetime")))
    total = obj.get("numberMatched") or (obj.get("context") or {}).get("matched")
    return out, _link(obj, "next"), int(total) if isinstance(total, int) else None


def parse_cdx_lines(body: bytes) -> list[dict[str, Any]]:
    out = []
    for ln in body.decode("utf-8", "replace").splitlines():
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        if not isinstance(r, dict) or str(r.get("status") or "200") != "200" or not r.get("url"):
            continue
        u = str(r["url"])
        name = urllib.parse.unquote(urllib.parse.urlsplit(u).path.rsplit("/", 1)[-1]) or u
        out.append(_entry(id=u, title=name, dists=[{"url": u, "format": "",
                                                    "media": r.get("mime") or ""}],
                          crawled_at=r.get("timestamp")))
    return out


def detect_shape(body: bytes) -> str:
    """Which route a probed answer looks like. Detection is reported, never acted on: a portal
    is moved to a route by editing the roster after a human has seen the shape."""
    head = body.lstrip()[:1]
    if head == b"<":
        return "sdmx" if parse_sdmx_listing(body) is not None else UNMEASURED
    obj = _json(body)
    if not isinstance(obj, dict):
        return UNMEASURED
    if isinstance(obj.get("result"), dict) and "count" in obj["result"]:
        return "ckan"
    if isinstance(obj.get("dataset"), list):
        return "dcat_pod"
    if "collections" in obj or "stac_version" in obj:
        return "stac"
    if "total_count" in obj and "results" in obj:
        return "opendatasoft"
    if "value" in obj and any("odata" in str(k).lower() for k in obj):
        return "odata"
    return UNMEASURED


# --------------------------------------------------------------------------------- rows ----
def row_key(route: str, portal_id: str, dataset_id: str) -> str:
    return hashlib.sha1(f"{route}|{portal_id}|{dataset_id}".encode()).hexdigest()[:16]


def build_row(portal: Mapping[str, Any], route: str, entry: Mapping[str, Any], now_iso: str,
              blocked: Iterable[str]) -> dict[str, Any]:
    """One discovery row in the shape the acquirer reads, plus the catalogue metadata. Pure."""
    blocked = tuple(blocked)
    endpoints: list[str] = []
    keyed: list[str] = []
    unparsed = [str(u) for u in entry.get("unparsed") or []]
    landing_like: list[str] = []
    formats: set[str] = set()
    n_blocked = 0
    for d in entry.get("dists") or []:
        url = str(d.get("url") or "").strip()
        if not url:
            continue
        f = norm_format(d.get("format"), d.get("media"))
        if f:
            formats.add(f)
        if _http_url(url) and is_blocked(host_of(url), blocked):
            n_blocked += 1
            continue
        kind = resource_kind(url, d.get("format"), d.get("media"), stac=bool(d.get("stac")),
                             roles=d.get("roles") or ())
        if kind == "data" and url not in endpoints:
            endpoints.append(url)
        elif kind == "keyed":
            keyed.append(url)
        elif kind == "landing":
            landing_like.append(url)
    formats.update(norm_format("", m) for m in entry.get("item_media") or [])
    formats.discard("")
    if portal.get("asset_auth") and endpoints:
        keyed.extend(endpoints)
        endpoints = []
    if endpoints:
        access = "OPEN"
    elif keyed:
        access = "NEEDS_KEY"
    elif entry.get("observation_class"):
        access = "CATALOGUED_NOT_ACQUIRABLE"
    elif unparsed:
        access = "UNPARSED_FORMAT"
    else:
        access = "NO_DATA_ENDPOINT"
    base = str(portal.get("base") or "")
    did = str(entry.get("id") or entry.get("title") or "")
    landing = str(entry.get("landing") or "") or (landing_like[0] if landing_like else "")
    url = landing or (endpoints[0] if endpoints else "") or (unparsed[0] if unparsed else base)
    row: dict[str, Any] = {
        "source": "catalog_routes", "kind": "dataset", "route": route,
        "row_id": row_key(route, str(portal["id"]), did),
        "portal": portal["id"], "portal_url": base,
        "producer": entry.get("producer") or portal.get("producer") or "",
        "producer_type": portal.get("producer_type") or UNMEASURED,
        "country": portal.get("country") or UNMEASURED,
        "subnational": portal.get("subnational") or entry.get("spatial") or None,
        "region": portal.get("region") or UNMEASURED,
        "lang": portal.get("language") or UNMEASURED,
        "title": entry.get("title") or did,
        "observable": entry.get("observable") or entry.get("title") or did,
        "dataset_id": did, "url": url, "landing_page": landing or None,
        "formats": sorted(formats), "license": entry.get("license") or None,
        "cadence": entry.get("cadence") or None,
        "first_discovered_at": now_iso, "published": now_iso,
        "host": host_of(endpoints[0]) if endpoints else host_of(base),
        "endpoints": endpoints, "n_endpoints": len(endpoints),
        "keyed_endpoints": keyed, "unparsed_endpoints": unparsed,
        "n_landing_resources": len(landing_like), "n_blocked_resources": n_blocked,
        "access": access, "mirror_of": None,
    }
    for k in ("tabular_item_assets", "keywords", "observed_at", "crawled_at", "data_url",
              "sdmx_agency", "sdmx_version"):
        if entry.get(k) not in (None, "", []):
            row[k] = entry[k]
    if entry.get("observation_class"):
        row["observation_class"] = True
    return row


def portal_row(portal: Mapping[str, Any], access: str, now_iso: str,
               note: str = "") -> dict[str, Any]:
    """A portal recorded as a whole: a keyed catalogue is kept, with what a key would open."""
    base = str(portal.get("base") or "")
    return {"source": "catalog_routes", "kind": "catalog", "route": portal.get("route"),
            "row_id": row_key(str(portal.get("route")), str(portal["id"]), "__portal__"),
            "portal": portal["id"], "portal_url": base,
            "producer": portal.get("producer") or "",
            "producer_type": portal.get("producer_type") or UNMEASURED,
            "country": portal.get("country") or UNMEASURED,
            "subnational": portal.get("subnational"), "region": portal.get("region"),
            "lang": portal.get("language"), "title": portal.get("producer") or portal["id"],
            "observable": UNMEASURED, "dataset_id": "__portal__", "url": base,
            "formats": [], "license": None, "cadence": None,
            "first_discovered_at": now_iso, "published": now_iso, "host": host_of(base),
            "endpoints": [], "n_endpoints": 0, "keyed_endpoints": [base], "access": access,
            "note": note or portal.get("note") or "", "mirror_of": None}


def empty_index() -> dict[str, Any]:
    return {"rows": {}, "urls": {}, "titles": {}}


def dedup(rows: Iterable[dict[str, Any]], index: dict[str, Any]
          ) -> tuple[list[dict[str, Any]], Counter[str]]:
    """New rows only; URL- or (producer, title)-repeats kept as `mirror_of`. Mutates `index`.

    A dataset row already in the index is a revisit and is dropped. Endpoints already owned by
    another row are removed from the new row; if that leaves a row whose every URL belonged to
    someone else, or whose (producer, title) another row already holds, it is a MIRROR: kept,
    flagged, its URLs under `mirror_endpoints`, never counted as a discovery or acquired twice.
    """
    seen_rows: dict[str, Any] = index.setdefault("rows", {})
    seen_urls: dict[str, str] = index.setdefault("urls", {})
    seen_titles: dict[str, str] = index.setdefault("titles", {})
    stats: Counter[str] = Counter()
    kept: list[dict[str, Any]] = []
    for r in rows:
        rid = str(r["row_id"])
        if rid in seen_rows:
            stats["revisited"] += 1
            continue
        all_urls = [*r.get("endpoints", []), *r.get("keyed_endpoints", []),
                    *r.get("unparsed_endpoints", [])]
        owners = {seen_urls[norm_url(u)] for u in all_urls if norm_url(u) in seen_urls}
        fresh = [u for u in r.get("endpoints", []) if norm_url(u) not in seen_urls]
        tk = title_key(r.get("producer"), r.get("title"))
        mirror_of: str | None = None
        if all_urls and owners and all(norm_url(u) in seen_urls for u in all_urls):
            mirror_of = min(owners)
        elif tk and tk in seen_titles and seen_titles[tk] != rid:
            mirror_of = seen_titles[tk]
        if mirror_of:
            r["mirror_of"] = mirror_of
            r["mirror_endpoints"] = list(r.get("endpoints", []))
            r["endpoints"], r["n_endpoints"] = [], 0
            stats["mirrors"] += 1
        else:
            if len(fresh) < len(r.get("endpoints", [])):
                stats["endpoints_already_known"] += len(r["endpoints"]) - len(fresh)
            r["endpoints"], r["n_endpoints"] = fresh, len(fresh)
            stats["new_rows"] += 1
            stats["new_endpoints"] += len(fresh)
            if tk:
                seen_titles.setdefault(tk, rid)
        for u in all_urls:
            seen_urls.setdefault(norm_url(u), rid)
        seen_rows[rid] = r.get("first_discovered_at")
        kept.append(r)
    return kept, stats


# ----------------------------------------------------------------------------- storage ----
def atomic_write(path: Path, text: str) -> None:
    """tmp + os.replace. Windows refuses a replace onto a file another process holds open, so a
    short retry, never a non-atomic fallback that could leave half a JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(text, encoding="utf-8")
    for attempt in range(5):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if attempt == 4:
                tmp.unlink(missing_ok=True)
                raise
            time.sleep(0.2 * (attempt + 1))


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def _cache_path(url: str) -> Path:
    return CACHE / "listings" / f"{hashlib.sha1(url.encode()).hexdigest()[:20]}.json.gz"


def cache_put(url: str, entries: list[dict[str, Any]]) -> None:
    p = _cache_path(url)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_bytes(gzip.compress(json.dumps(entries).encode()))
    os.replace(tmp, p)


def cache_get(url: str) -> list[dict[str, Any]] | None:
    try:
        v = json.loads(gzip.decompress(_cache_path(url).read_bytes()))
    except (OSError, ValueError, EOFError):
        return None
    return v if isinstance(v, list) else None


def load_index(world: Path | None = None) -> dict[str, Any]:
    """The dedup index; rebuilt from the catalog discoveries files when the cache is gone."""
    idx = _read_json(CACHE / "index.json", None)
    if isinstance(idx, dict) and {"rows", "urls", "titles"} <= set(idx):
        return idx
    idx = empty_index()
    for f in sorted((world or WORLD).glob(f"{FILE_PREFIX}*.json")):
        rows = _read_json(f, [])
        for r in rows if isinstance(rows, list) else []:
            if not isinstance(r, dict) or not r.get("row_id"):
                continue
            rid = str(r["row_id"])
            idx["rows"][rid] = r.get("first_discovered_at")
            for u in [*r.get("endpoints", []), *r.get("keyed_endpoints", []),
                      *r.get("unparsed_endpoints", []), *r.get("mirror_endpoints", [])]:
                idx["urls"].setdefault(norm_url(str(u)), rid)
            tk = title_key(r.get("producer"), r.get("title"))
            if tk and not r.get("mirror_of"):
                idx["titles"].setdefault(tk, rid)
    return idx


def append_discoveries(rows: list[dict[str, Any]], now: datetime,
                       world: Path | None = None) -> Path | None:
    if not rows:
        return None
    path = (world or WORLD) / f"{FILE_PREFIX}{now:%Y%m%d}.json"
    existing = _read_json(path, [])
    existing = existing if isinstance(existing, list) else []
    atomic_write(path, json.dumps(existing + rows, indent=1, ensure_ascii=False, default=str))
    return path


# ------------------------------------------------------------------------------ routes ----
@dataclass
class Visit:
    status: str = "OK"
    rows: list[dict[str, Any]] = field(default_factory=list)
    remainder: int | str = UNMEASURED
    unit: str = "datasets"
    total: int | str = UNMEASURED
    pages: int = 0
    detail: dict[str, Any] = field(default_factory=dict)


def _idle(cur: Mapping[str, Any], now: datetime) -> bool:
    nxt = _parse_iso(cur.get("next_pass_after"))
    return nxt is not None and now < nxt


def _complete(cur: dict[str, Any], now: datetime, relist_days: float) -> None:
    cur["passes"] = int(cur.get("passes") or 0) + 1
    cur["pass_completed_at"] = _iso(now)
    cur["next_pass_after"] = _iso(now + timedelta(days=relist_days))
    cur["next"] = None
    cur["offset"] = 0
    cur["done_items"] = 0


PageParser = Callable[[bytes, str], tuple[list[dict[str, Any]], str | None, int | None] | None]


def visit_paged(sess: Session, portal: Mapping[str, Any], cur: dict[str, Any], first_url: str,
                parse: PageParser, cfg: Mapping[str, Any], *, route: str,
                unit: str = "datasets") -> Visit:
    """Follow a catalogue's own pagination from the cursor, a few pages per visit.

    The cursor is advanced after EVERY page, so a run cut short resumes on the next page, and
    the pass is complete only when the API says there is no next page.
    """
    v = Visit(unit=unit)
    if _idle(cur, sess.now):
        v.status, v.remainder, v.total = "IDLE_UNTIL_RELIST", 0, cur.get("total", UNMEASURED)
        return v
    url = cur.get("next") or first_url
    if not cur.get("next"):
        cur["pass_started_at"] = _iso(sess.now)
        cur["done_items"] = 0
    gap, timeout = float(cfg["min_gap_s"]), float(cfg["timeout_s"])
    now_iso = _iso(sess.now)
    complete = False
    for _ in range(int(cfg["pages_per_visit"])):
        resp = sess.get(url, gap_s=gap, timeout=timeout)
        if resp is None:
            v.status = "BUDGET_EXHAUSTED"
            break
        if resp.status == 304:
            meta = sess.page_meta(url)
            nxt, n = meta.get("next"), int(meta.get("n") or 0)
            v.detail["not_modified"] = int(v.detail.get("not_modified", 0)) + 1
        elif resp.status == 200:
            parsed = parse(resp.body, url)
            if parsed is None:
                v.status = "UNMEASURED_SHAPE"
                break
            entries, nxt, total = parsed
            n = len(entries)
            v.rows.extend(build_row(portal, route, e, now_iso, sess.blocked) for e in entries)
            sess.remember(url, resp, nxt, n)
            if total is not None:
                cur["total"] = int(total)
        else:
            v.status = access_status(resp)
            break
        v.pages += 1
        cur["done_items"] = int(cur.get("done_items") or 0) + n
        cur["pages_read"] = int(cur.get("pages_read") or 0) + 1
        if not nxt or nxt == url:
            complete = True
            break
        cur["next"] = url = str(nxt)
    v.total = cur.get("total", UNMEASURED)
    if complete:
        _complete(cur, sess.now, float(cfg["relist_days"]))
        v.remainder = 0
    elif isinstance(cur.get("total"), int):
        v.remainder = max(0, int(cur["total"]) - int(cur.get("done_items") or 0))
    return v


def visit_listing(sess: Session, portal: Mapping[str, Any], cur: dict[str, Any], url: str,
                  parse: Callable[[bytes], list[dict[str, Any]] | None],
                  cfg: Mapping[str, Any], *, route: str, accept: str = "") -> Visit:
    """A catalogue served as ONE document (data.json, an SDMX dataflow listing).

    The parsed listing is cached so a 304 still lets the cursor walk the rest of it: rows are
    emitted `max_entries_per_visit` at a time from `offset`, and the remainder is the rest of
    the listing. A changed listing restarts at offset 0 (the dedup index drops what is known).
    """
    v = Visit()
    if _idle(cur, sess.now):
        v.status, v.remainder, v.total = "IDLE_UNTIL_RELIST", 0, cur.get("total", UNMEASURED)
        return v
    cached = cache_get(url)
    resp = sess.get(url, gap_s=float(cfg["min_gap_s"]), timeout=float(cfg["timeout_s"]),
                    conditional=cached is not None, accept=accept)
    if resp is None:
        v.status = "BUDGET_EXHAUSTED"
        return v
    entries: list[dict[str, Any]] | None
    if resp.status == 304 and cached is not None:
        entries = cached
        v.detail["not_modified"] = 1
    elif resp.status == 200:
        if len(resp.body) > MAX_PAGE_BYTES:
            v.status = "TRUNCATED_OVER_CAP"
            return v
        entries = parse(resp.body)
        if entries is None:
            v.status = "UNMEASURED_SHAPE"
            return v
        sha = hashlib.sha1(json.dumps(entries, sort_keys=True).encode()).hexdigest()[:16]
        if sha != cur.get("listing_sha"):
            cur["listing_sha"], cur["offset"] = sha, 0
        cache_put(url, entries)
        sess.remember(url, resp, None, len(entries))
    else:
        v.status = access_status(resp)
        return v
    v.pages = 1
    off = int(cur.get("offset") or 0)
    step = int(cfg["max_entries_per_visit"])
    chunk = entries[off:off + step]
    now_iso = _iso(sess.now)
    for e in chunk:
        v.rows.append(build_row(portal, route, e, now_iso, sess.blocked))
    cur["offset"] = off + len(chunk)
    cur["total"] = v.total = len(entries)
    if cur["offset"] >= len(entries):
        _complete(cur, sess.now, float(cfg["relist_days"]))
        v.remainder = 0
    else:
        v.remainder = len(entries) - int(cur["offset"])
    return v


def _route_ckan(sess: Session, portal: Mapping[str, Any], st: dict[str, Any],
                cfg: Mapping[str, Any]) -> Visit:
    base = str(portal["base"]).rstrip("/")
    api = base + str(portal.get("api") or "/api/3/action/package_search")
    first = (f"{api}?rows={int(cfg['rows'])}&start=0"
             f"&sort={urllib.parse.quote('metadata_created asc')}")
    cur = st.setdefault("cursor", {})
    return visit_paged(sess, portal, cur, first,
                       lambda body, url: parse_ckan_page(body, url, base), cfg, route="ckan")


def _route_dcat_pod(sess: Session, portal: Mapping[str, Any], st: dict[str, Any],
                    cfg: Mapping[str, Any]) -> Visit:
    url = str(portal.get("url") or str(portal["base"]).rstrip("/") + "/data.json")
    return visit_listing(sess, portal, st.setdefault("cursor", {}), url, parse_pod, cfg,
                         route="dcat_pod")


def _route_dcat_jsonld(sess: Session, portal: Mapping[str, Any], st: dict[str, Any],
                       cfg: Mapping[str, Any]) -> Visit:
    url = str(portal.get("url") or str(portal["base"]).rstrip("/") + "/catalog.jsonld?page=1")
    return visit_paged(sess, portal, st.setdefault("cursor", {}), url,
                       lambda body, _u: parse_dcat_page(body), cfg, route="dcat_jsonld")


def _route_ods(sess: Session, portal: Mapping[str, Any], st: dict[str, Any],
               cfg: Mapping[str, Any]) -> Visit:
    base = str(portal["base"]).rstrip("/")
    first = f"{base}/api/explore/v2.1/catalog/datasets?limit={min(int(cfg['rows']), 100)}&offset=0"
    return visit_paged(sess, portal, st.setdefault("cursor", {}), first,
                       lambda body, url: parse_ods_page(body, url, base), cfg,
                       route="opendatasoft")


def _route_sdmx(sess: Session, portal: Mapping[str, Any], st: dict[str, Any],
                cfg: Mapping[str, Any]) -> Visit:
    url = str(portal["base"]).rstrip("/") + str(portal.get("listing") or "/dataflow/all")

    def parse(body: bytes) -> list[dict[str, Any]] | None:
        flows = parse_sdmx_listing(body)
        return None if flows is None else sdmx_entries(flows, portal)

    v = visit_listing(sess, portal, st.setdefault("cursor", {}), url, parse, cfg, route="sdmx",
                      accept="application/vnd.sdmx.structure+xml;version=2.1, "
                             "application/xml;q=0.9, */*;q=0.5")
    v.unit = "dataflows"
    return v


def _route_stac(sess: Session, portal: Mapping[str, Any], st: dict[str, Any],
                cfg: Mapping[str, Any]) -> Visit:
    """Collections (observation classes) first; then, for collections whose items carry tabular
    assets (or that the roster names), item search pages, each item's tabular hrefs endpoints."""
    base = str(portal["base"]).rstrip("/")
    v = visit_paged(sess, portal, st.setdefault("cursor", {}), f"{base}/collections",
                    lambda body, _u: parse_stac_collections(body, base), cfg, route="stac",
                    unit="collections")
    searches: dict[str, Any] = st.setdefault("search", {})
    for r in v.rows:
        if r.get("tabular_item_assets"):
            searches.setdefault(str(r["dataset_id"]), {"title": r.get("title")})
    for cid in portal.get("search_collections") or []:
        searches.setdefault(str(cid), {"title": str(cid)})
    search_remainder: dict[str, int | str] = {}
    for cid, sc in searches.items():
        if sess.exhausted():
            search_remainder[cid] = sc.get("remainder", UNMEASURED)
            continue
        title = str(sc.get("title") or cid)
        q = urllib.parse.urlencode({"collections": cid, "limit": min(int(cfg["rows"]), 100)})

        def parse_items(body: bytes, _url: str, t: str = title
                        ) -> tuple[list[dict[str, Any]], str | None, int | None] | None:
            return parse_stac_search(body, t)

        sv = visit_paged(sess, portal, sc.setdefault("cursor", {}), f"{base}/search?{q}",
                         parse_items, cfg, route="stac_search", unit="items")
        v.rows.extend(sv.rows)
        sc["remainder"] = search_remainder[cid] = sv.remainder
        sc["status"] = sv.status
    if search_remainder:
        v.detail["search_remainder_items"] = search_remainder
    return v


def cdx_index_id(cfg: Mapping[str, Any]) -> str:
    if cfg.get("cdx_index"):
        return str(cfg["cdx_index"])
    try:
        from index_discovery import CC_INDEX
        return str(CC_INDEX)
    except Exception:  # noqa: BLE001  # pragma: no cover - index_discovery is in this tree
        return "CC-MAIN-2026-30"


def _route_cdx(sess: Session, portal: Mapping[str, Any], st: dict[str, Any],
               cfg: Mapping[str, Any]) -> Visit:
    """Common Crawl CDX per (domain, mimetype), paged by the server's own page count."""
    idx = cdx_index_id(cfg)
    fld = str(cfg.get("cdx_filter_field") or "mimetype")
    v = Visit(unit="pages")
    remainder = 0
    unknown = False
    now_iso = _iso(sess.now)
    cursors: dict[str, Any] = st.setdefault("cdx", {})
    statuses: Counter[str] = Counter()
    for domain in portal.get("domains") or []:
        if is_blocked(str(domain), sess.blocked):
            statuses["BLOCKED_HOST"] += 1
            continue
        for mime in portal.get("mimetypes") or ["text/csv"]:
            key = f"{idx}|{domain}|{mime}"
            cur = cursors.setdefault(key, {})
            if _idle(cur, sess.now):
                statuses["IDLE_UNTIL_RELIST"] += 1
                continue
            q = urllib.parse.urlencode({"url": f"{domain}/*", "output": "json",
                                        "filter": f"{fld}:{mime}"}, safe="/*:")
            api = f"https://index.commoncrawl.org/{idx}-index?{q}"
            if "pages" not in cur:
                if sess.exhausted():
                    unknown = True
                    continue
                resp = sess.get(api + "&showNumPages=true", gap_s=float(cfg["min_gap_s"]),
                                timeout=float(cfg["timeout_s"]), conditional=False)
                if resp is None:
                    unknown = True
                    continue
                if resp.status != 200:
                    statuses[access_status(resp)] += 1
                    unknown = True
                    continue
                obj = _json(resp.body)
                if not (isinstance(obj, dict) and isinstance(obj.get("pages"), int)):
                    statuses["UNMEASURED_SHAPE"] += 1
                    unknown = True
                    continue
                cur["pages"], cur["page"] = int(obj["pages"]), 0
            for _ in range(int(cfg["pages_per_visit"])):
                if int(cur["page"]) >= int(cur["pages"]):
                    break
                resp = sess.get(f"{api}&page={int(cur['page'])}", gap_s=float(cfg["min_gap_s"]),
                                timeout=float(cfg["timeout_s"]))
                if resp is None:
                    break
                if resp.status == 304:
                    pass
                elif resp.status == 200:
                    for e in parse_cdx_lines(resp.body):
                        e["producer"] = portal.get("producer", "")
                        v.rows.append(build_row(portal, "cdx", e, now_iso, sess.blocked))
                    sess.remember(f"{api}&page={int(cur['page'])}", resp, "", 0)
                elif resp.status == 404:
                    # pywb answers 404 for a page with no captures matching the filter
                    pass
                else:
                    statuses[access_status(resp)] += 1
                    break
                cur["page"] = int(cur["page"]) + 1
                v.pages += 1
            if int(cur["page"]) >= int(cur["pages"]):
                _complete(cur, sess.now, float(cfg["relist_days"]))
                cur.pop("pages", None)
                cur.pop("page", None)
            else:
                remainder += int(cur["pages"]) - int(cur["page"])
    v.remainder = UNMEASURED if unknown else remainder
    v.detail["cdx_index"] = idx
    if statuses:
        v.detail["statuses"] = dict(statuses)
        if not v.rows and v.pages == 0 and not statuses.get("IDLE_UNTIL_RELIST"):
            v.status = statuses.most_common(1)[0][0]
    return v


def _route_keyed(sess: Session, portal: Mapping[str, Any], st: dict[str, Any],
                 cfg: Mapping[str, Any]) -> Visit:
    """No request, no credential: the portal itself is recorded NEEDS_KEY, once."""
    v = Visit(status="NEEDS_KEY", remainder=UNMEASURED)
    v.rows.append(portal_row(portal, "NEEDS_KEY", _iso(sess.now)))
    return v


def _route_probe(sess: Session, portal: Mapping[str, Any], st: dict[str, Any],
                 cfg: Mapping[str, Any]) -> Visit:
    """An API no route parses yet: fetch once a relist period and REPORT its shape. Datasets
    behind it read UNMEASURED; nothing is emitted, so its silence is never read as zero."""
    v = Visit(status="UNMEASURED_SHAPE", remainder=UNMEASURED)
    cur = st.setdefault("cursor", {})
    if _idle(cur, sess.now):
        v.status = "IDLE_UNTIL_RELIST"
        v.detail["detected_shape"] = cur.get("detected_shape", UNMEASURED)
        return v
    url = str(portal.get("url") or portal["base"])
    resp = sess.get(url, gap_s=float(cfg["min_gap_s"]), timeout=float(cfg["timeout_s"]),
                    conditional=False)
    if resp is None:
        v.status = "BUDGET_EXHAUSTED"
        return v
    if resp.status != 200:
        v.status = access_status(resp)
        return v
    shape = detect_shape(resp.body)
    cur["detected_shape"] = v.detail["detected_shape"] = shape
    _complete(cur, sess.now, float(cfg["relist_days"]))
    return v


ROUTES: dict[str, Callable[[Session, Mapping[str, Any], dict[str, Any], Mapping[str, Any]],
                           Visit]] = {
    "ckan": _route_ckan, "dcat_pod": _route_dcat_pod, "dcat_jsonld": _route_dcat_jsonld,
    "opendatasoft": _route_ods, "sdmx": _route_sdmx, "stac": _route_stac, "cdx": _route_cdx,
    "keyed": _route_keyed, "probe": _route_probe,
}


# --------------------------------------------------------------------------------- run ----
def load_roster(path: Path | None = None) -> dict[str, Any]:
    r = _read_json(path or ROSTER, {})
    return r if isinstance(r, dict) else {}


def _cfg(roster: Mapping[str, Any], portal: Mapping[str, Any]) -> dict[str, Any]:
    cfg: dict[str, Any] = {"rows": 100, "pages_per_visit": 3, "max_entries_per_visit": 400,
                           "min_gap_s": 1.0, "relist_days": 7, "timeout_s": 25,
                           "cdx_index": None, "cdx_filter_field": "mimetype"}
    cfg.update({k: v for k, v in (roster.get("defaults") or {}).items() if v is not None})
    cfg.update({k: portal[k] for k in cfg if k in portal and portal[k] is not None})
    return cfg


def _register_portals(table: dict[str, Any], portals: list[dict[str, Any]]) -> int:
    """Every portal that answered becomes a source in the source frontier with
    `discovered_via="catalog_route:<route>"`, so discovery yield can be compared by METHOD
    (catalogue route vs crawl vs seed). Never stops the pass."""
    try:
        import source_frontier as SF
    except Exception:  # noqa: BLE001
        return 0
    by_id = {str(p.get("id")): p for p in portals}
    n = 0
    for pid, row in table.items():
        if int(row.get("rows") or 0) <= 0:
            continue
        p = by_id.get(pid) or {}
        try:
            n += int(SF.register_source(f"catalog:{pid}", url=str(p.get("base") or ""),
                                        kind=f"catalog_{row.get('route')}",
                                        country=str(p.get("country") or ""),
                                        discovered_via=f"catalog_route:{row.get('route')}"))
        except Exception:  # noqa: BLE001
            return n
    return n


def run(budget_s: float = DEFAULT_BUDGET_S, *, fetch: Fetch | None = None,
        now: datetime | None = None, roster_path: Path | None = None,
        only_routes: set[str] | None = None, max_requests: int = MAX_REQUESTS_PER_RUN,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep, write: bool = True) -> dict[str, Any]:
    """One budgeted pass over the roster, stalest portal first. Returns the report."""
    now = now or _now()
    roster = load_roster(roster_path)
    state = _read_json(STATE, {})
    state = state if isinstance(state, dict) else {}
    pstate: dict[str, Any] = state.setdefault("portals", {})
    index = load_index()
    blocked = [str(b) for b in roster.get("blocked_hosts") or []]
    sess = Session(state, fetch or urllib_fetch, now=now, budget_s=budget_s,
                   max_requests=max_requests, blocked=blocked, clock=clock, sleep=sleep)
    portals = [p for p in roster.get("portals") or []
               if isinstance(p, dict) and p.get("id") and p.get("route")
               and (not only_routes or p["route"] in only_routes)]

    def stale(p: Mapping[str, Any]) -> str:
        return str((pstate.get(str(p["id"])) or {}).get("last_visit_at") or "")

    rows_all: list[dict[str, Any]] = []
    table: dict[str, Any] = {}
    for p in sorted(portals, key=stale):
        pid, route = str(p["id"]), str(p["route"])
        st = pstate.setdefault(pid, {})
        if sess.exhausted() and route != "keyed":           # keyed costs no request
            table[pid] = {"route": route, "status": "NOT_VISITED_BUDGET",
                          "remainder": st.get("remainder", UNMEASURED),
                          "unit": st.get("unit", "datasets")}
            continue
        if is_blocked(host_of(str(p.get("base") or "")), blocked):
            v = Visit(status="BLOCKED_HOST", remainder=0)
        elif route not in ROUTES:
            v = Visit(status=f"UNKNOWN_ROUTE_{route}", remainder=UNMEASURED)
        else:
            try:
                v = ROUTES[route](sess, p, st, _cfg(roster, p))
            except Exception as exc:  # noqa: BLE001 - one portal never stops the pass
                v = Visit(status=f"ERROR {type(exc).__name__}: {str(exc)[:160]}")
        rows_all.extend(v.rows)
        st.update({"last_visit_at": _iso(now), "status": v.status, "remainder": v.remainder,
                   "unit": v.unit, "total": v.total,
                   "rows_emitted_total": int(st.get("rows_emitted_total") or 0) + len(v.rows)})
        table[pid] = {"route": route, "country": p.get("country"), "region": p.get("region"),
                      "status": v.status, "pages": v.pages, "rows": len(v.rows),
                      "total": v.total, "remainder": v.remainder, "unit": v.unit,
                      "passes": int((st.get("cursor") or {}).get("passes") or 0), **v.detail}
    if fetch is None:                     # live passes only; a test's fake transport registers nothing
        _register_portals(table, portals)
    for r in rows_all:
        hosts = {host_of(u) for u in [*r.get("endpoints", []), str(r.get("url") or "")] if u}
        if hosts & sess.robots_disallow:
            r["terms_note"] = "robots Disallow on this host (those paths were not fetched)"
    kept, stats = dedup(rows_all, index)
    by_route: dict[str, dict[str, Any]] = {}
    for pid, row in table.items():
        br = by_route.setdefault(row["route"], {"portals": 0, "rows": 0, "remainder": 0,
                                                "remainder_unmeasured_portals": 0,
                                                "statuses": Counter()})
        br["portals"] += 1
        br["rows"] += int(row.get("rows") or 0)
        rem = row.get("remainder")
        if isinstance(rem, int):
            br["remainder"] += rem
        else:
            br["remainder_unmeasured_portals"] += 1
        br["statuses"][str(row.get("status"))] += 1
    for br in by_route.values():
        br["statuses"] = dict(br["statuses"])
    new_rows = [r for r in kept if not r.get("mirror_of")]
    access = Counter(str(r.get("access")) for r in kept)
    report = {
        "generated_at": _iso(now),
        "rule": ("catalogue pages only: every route walks its portal's own pagination from a "
                 "persisted cursor and publishes the unprocessed remainder; a shape no route "
                 "parses reads UNMEASURED, never zero; rows land in discoveries_catalog_* for "
                 "acquire_datasets, which alone fetches data"),
        "discovered": len(new_rows),
        "endpoints": int(stats.get("new_endpoints", 0)),
        "mirrors": int(stats.get("mirrors", 0)),
        "revisited": int(stats.get("revisited", 0)),
        "endpoints_already_known": int(stats.get("endpoints_already_known", 0)),
        "access": dict(access),
        "requests": sess.requests, "not_modified": sess.not_modified,
        "refusals": dict(sess.refusals),
        "labels": dict(sess.labels), "robots_disallow_hosts": sorted(sess.robots_disallow),
        "budget_s": budget_s, "spent_s": round(sess.clock() - sess.started, 1),
        "remainder_total": sum(int(r["remainder"]) for r in table.values()
                               if isinstance(r.get("remainder"), int)),
        "remainder_unmeasured_portals": sorted(pid for pid, r in table.items()
                                               if not isinstance(r.get("remainder"), int)),
        "by_route": by_route,
        "portals": table,
    }
    if write:
        out = append_discoveries(kept, now)
        report["discoveries_file"] = str(out) if out else None
        state["updated_at"] = _iso(now)
        atomic_write(STATE, json.dumps(state, indent=1, default=str))
        atomic_write(CACHE / "index.json", json.dumps(index))
        atomic_write(REPORT, json.dumps(report, indent=1, default=str))
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--budget-s", type=float, default=DEFAULT_BUDGET_S)
    ap.add_argument("--only", default="", help="comma-separated routes")
    ap.add_argument("--max-requests", type=int, default=MAX_REQUESTS_PER_RUN)
    a = ap.parse_args(argv)
    only = {s.strip() for s in a.only.split(",") if s.strip()} or None
    r = run(a.budget_s, only_routes=only, max_requests=a.max_requests)
    print(f"catalog routes: {r['discovered']} new dataset row(s), {r['endpoints']} new "
          f"endpoint(s), {r['mirrors']} mirror(s), {r['requests']} request(s) "
          f"({r['not_modified']} not modified); remainder {r['remainder_total']} + "
          f"{len(r['remainder_unmeasured_portals'])} portal(s) UNMEASURED -> {REPORT}")
    for route, br in sorted(r["by_route"].items()):
        print(f"  {route:13} portals={br['portals']:3} rows={br['rows']:6} "
              f"remainder={br['remainder']} statuses={br['statuses']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
