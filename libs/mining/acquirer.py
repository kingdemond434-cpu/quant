"""Per-source fetchers with durable cursors, reading the roster in `sources.yaml`.

THE CURSOR IS WRITTEN AFTER EVERY RECORD, AND THE STORE IS IDEMPOTENT. A fetcher yields items in
cursor order; for each one the acquirer (1) stores it in the PIT store and (2) persists the
cursor advance, atomically (write-temp-then-replace). A process killed between (1) and (2)
re-fetches that one item on restart, and the store's content key makes the second put a no-op;
a kill before (1) re-fetches an item that was never stored. Either way nothing is lost and
nothing is doubled, which is `test_cursor_resume`.

EVERY SOURCE LEAVES AN OUTCOME, every run. `ok`, `empty`, `BLOCKED_AUTH` (a login or paid key the
box does not hold; the keyless path runs where one exists), `BLOCKED_FETCH` (403/WAF/DNS: the
host refused, recorded with its status), `DEFERRED_TO_OWNER` (another lane owns this fetcher and
its feed is present, so this one does not fetch twice), `NOT_DUE` or `ERROR`. A source that
silently produced nothing is not a state this module can reach.

FETCHERS ARE DATA-DRIVEN. Nine generic kinds cover the roster (html_listing, rss, reddit_json,
github_search, telegram_preview, json_api, search_route, page_snapshot, external_feed); a new
source is a YAML row, not new code. `http_get` is injected, so every fetcher runs offline in
tests against fixtures and on the box through `libs.data.polite_fetch` (per-host politeness,
bounded retries, a deadline per call).
"""
from __future__ import annotations

import glob
import hashlib
import html as _html
import json
import os
import re
import threading
import time
import urllib.parse
import urllib.robotparser
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

from libs.mining.pit_store import PitStore, PutResult, RawRecord, iso, parse_time, utcnow

ROSTER = Path(__file__).with_name("sources.yaml")
AUTH_KINDS: frozenset[str] = frozenset({"none", "optional", "key", "login"})
SEEN_CAP = 20_000


# ======================================================================== roster
@dataclass
class Source:
    id: str
    fetcher: str
    kind: str = "text"
    priority: int = 9
    name: str = ""
    cadence_minutes: int = 60
    auth: str = "none"
    auth_env: str = ""
    region: str = "global"
    language: str = ""
    licence: str = ""
    owner: str = "global_mining"
    mode: str = "primary"            # primary, or fallback: runs only while owner_feed is absent
    owner_feed: str = ""             # glob that proves the owning lane is producing
    immutable_time: bool = False
    handoff_deepening: bool = True
    feeds: list[str] = field(default_factory=list)    # consumers beyond the gauntlet
    enabled: bool = True
    config: dict[str, Any] = field(default_factory=dict)
    origin: str = "sources.yaml"
    uses: list[str] = field(default_factory=list)   # direct|indirect_cells, allocation_intel
    consumer: str = ""               # for owned rows: the organ that fetches and consumes it
    respect_robots: bool = True
    url_key: str = ""                # canonical_url of the row's own URL: the cross-roster join
    url_keys: list[str] = field(default_factory=list)  # every URL it reads (config included)
    aliases: list[str] = field(default_factory=list)  # ids other rosters gave the same source
    shares_page: list[str] = field(default_factory=list)  # distinct sources on the same page
    seats: list[str] = field(default_factory=list)  # docket `source` strings it answers for


_SLUG = re.compile(r"\W+", re.UNICODE)


def canonical_url(url: Any) -> str:
    """host + path (+ sorted query), lower-case, no scheme, `www.`, fragment or trailing slash; a
    template's `{page}`/`{q}` tail is cut. The query stays: `dataview.html?paramid=kx` and
    `?paramid=pm` are two datasets, not one page."""
    u = str(url or "").strip()
    if not u:
        return ""
    u = u.split("{", 1)[0]
    parts = urllib.parse.urlsplit(u if "//" in u else "//" + u)
    host = (parts.hostname or "").lower().removeprefix("www.")
    if not host or "." not in host:
        return ""
    q = urllib.parse.urlencode(sorted(urllib.parse.parse_qsl(parts.query)))
    return host + parts.path.rstrip("/").lower() + (f"?{q}" if q else "")


def _row_urls(row: Mapping[str, Any]) -> list[str]:
    """Every URL a row names, its own fields first, then its fetcher `config` (the pipeline's own
    rows keep theirs there: listing pages, feeds, API endpoints)."""
    out: list[str] = []

    def take(v: Any) -> None:
        if isinstance(v, str) and "://" in v:
            out.append(v)
        elif isinstance(v, Mapping):
            for k in ("page1", "url"):
                take(v.get(k))
        elif isinstance(v, (list, tuple)):
            for x in v:
                take(x)
    for src in (row, row.get("config") if isinstance(row.get("config"), Mapping) else {}):
        for k in ("url", "rss", "link", "page1", "urls", "roots", "feeds", "alt", "listing",
                  "pages"):
            take(src.get(k))
    return list(dict.fromkeys(out))


def _row_url(row: Mapping[str, Any]) -> str:
    urls = _row_urls(row)
    return urls[0] if urls else ""


def slug(name: Any) -> str:
    """The W1 registry's slug (desks/mt5/research/source_registry.py `_slug`), reproduced exactly
    so a deep-forest ground carries the SAME id in both registries."""
    raw = str(name or "").strip()
    out = _SLUG.sub("_", raw.lower()).strip("_")[:60]
    return out or ("x" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10] if raw else "unnamed")


def derive_id(row: Mapping[str, Any], style: str, taken: Mapping[str, str]) -> str:
    """A durable id for a row its roster left unnamed. `ground` is the W1 registry's
    `ground:<region>:<slug>` (with its collision suffix); anything else is `<style>:<slug>` of
    the name, else of the canonical URL. Deterministic, so the cursor survives every pass."""
    name = str(row.get("name") or row.get("title") or "")
    if style == "ground":
        sid = f"ground:{row.get('region') or 'na'}:{slug(name)}"
    else:
        sid = f"{style}:{slug(name or canonical_url(_row_url(row)))}"
    if sid in taken and taken[sid] != name:
        sid = f"{sid}_{hashlib.sha1(name.encode('utf-8')).hexdigest()[:6]}"
    return sid


USES: tuple[str, ...] = ("direct_cells", "indirect_cells", "allocation_intel")
#: What a row serves when it does not say: prose and code become cells and their regime-
#: conditioned children; broker and prop mechanics condition cells and inform allocation.
DEFAULT_USES: dict[str, list[str]] = {
    "code": ["direct_cells", "indirect_cells"],
    "text": ["direct_cells", "indirect_cells"],
    "mechanics": ["indirect_cells", "allocation_intel"],
}
#: Fetchers that crawl web PAGES obey robots.txt. Documented APIs and feeds published for
#: machine reading (json_api, github_search, reddit_json, rss) and rows read from another
#: lane's files do not consult it; search routes follow deep_forest_miner's established route.
ROBOTS_FETCHERS: frozenset[str] = frozenset({"html_listing", "page_snapshot",
                                             "telegram_preview"})


def _as_int(v: Any, default: int) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def normalise_row(row: Mapping[str, Any], *, origin: str,
                  defaults: Mapping[str, Any] | None = None) -> Source | None:
    """A roster row from this file OR from another lane's source table, as it is.

    The breadth thread keeps every source as a data row (id, cadence, auth, licence, cursor,
    region/language); those rows are read here without reshaping: `source_id` or `id`,
    cadence in minutes, seconds or hours, `license` or `licence`, `lang` or `language`."""
    defaults = dict(defaults or {})
    sid = str(row.get("id") or row.get("source_id") or "").strip()
    if not sid:
        return None
    cadence = row.get("cadence_minutes")
    if cadence is None and row.get("cadence_s") is not None:
        cadence = _as_int(row.get("cadence_s"), 3600) // 60
    if cadence is None and row.get("cadence_hours") is not None:
        cadence = _as_int(row.get("cadence_hours"), 1) * 60
    if cadence is None and isinstance(row.get("cadence"), (int, float, str)):
        c = str(row.get("cadence")).strip().lower().split(" ", 1)[0].strip("(),;")
        named = {"hourly": 60, "daily": 1440, "weekly": 10080, "continuous": 15}
        if c in named:
            cadence = named[c]
        elif c.endswith("h"):
            cadence = _as_int(c[:-1], 1) * 60
        elif c.endswith("d"):
            cadence = _as_int(c[:-1], 1) * 1440
        else:
            cadence = _as_int(c.rstrip("ms"), 60)
    auth = str(row.get("auth") or "none").lower().split(" ", 1)[0].strip("(),;")
    if auth in ("cookie", "crumb", "session"):
        auth = "none"                  # a session cookie with no login: the owner fetches it
    if auth in ("keyless", "public", "no"):
        auth = "none"
    if auth in ("api_key", "token", "paid"):
        auth = "key"
    if auth not in AUTH_KINDS:
        auth = "login"
    cfg = dict(row.get("config") or {})
    for k in ("url", "urls", "listing", "feeds", "queries", "subs", "channels", "pages",
              "paths", "item_regex"):
        if k in row and k not in cfg:
            cfg[k] = row[k]
    fetcher = str(row.get("fetcher") or defaults.get("fetcher") or (
        "rss" if row.get("feeds") or row.get("rss")
        else "external_feed" if row.get("paths") else "html_listing"))
    if fetcher == "rss" and "feeds" not in cfg and row.get("rss"):
        cfg["feeds"] = [row.get("rss")] if isinstance(row.get("rss"), str) else row.get("rss")
    kind = str(row.get("kind") or defaults.get("kind") or "text")
    if kind not in DEFAULT_USES:
        kind = str(defaults.get("kind") or "text")
    uses_raw = row.get("uses") if row.get("uses") is not None else defaults.get("uses")
    uses = [str(u) for u in (uses_raw if isinstance(uses_raw, list) else
                             [uses_raw] if uses_raw else DEFAULT_USES[kind]) if str(u) in USES]
    return Source(
        id=sid, fetcher=fetcher, kind=kind, uses=uses,
        consumer=str(row.get("consumer") or row.get("organ") or defaults.get("consumer") or ""),
        respect_robots=bool(row.get("respect_robots", fetcher in ROBOTS_FETCHERS)),
        priority=_as_int(row.get("priority"), 9), name=str(row.get("name") or sid),
        cadence_minutes=max(1, _as_int(cadence, 60)), auth=auth,
        auth_env=str(row.get("auth_env") or ""), region=str(row.get("region") or "global"),
        language=str(row.get("language") or row.get("lang") or ""),
        licence=str(row.get("licence") or row.get("license") or ""),
        owner=str(row.get("owner") or defaults.get("owner") or "global_mining"),
        mode=str(row.get("mode") or "primary"),
        owner_feed=str(row.get("owner_feed") or ""),
        immutable_time=bool(row.get("immutable_time", False)),
        handoff_deepening=bool(row.get("handoff_deepening", True)),
        feeds=[str(x) for x in (row.get("feeds_to") or [])],
        enabled=bool(row.get("enabled", True)), config=cfg, origin=origin,
        url_key=canonical_url(_row_url(row)),
        url_keys=[k for k in dict.fromkeys(canonical_url(u) for u in _row_urls(row)) if k],
        seats=_seats(row.get("seats")))


def _seats(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [str(x) for x in raw]
    return [str(raw)] if raw else []


def load_roster(path: Path = ROSTER, *, root: Path | None = None) -> list[Source]:
    """THE ONE SOURCE REGISTRY: this roster plus every lane's table its `external_rosters` name.

    Each entry is a glob read in place (`rows` picks the list inside a document; `id_style`
    names rows the lane left unnamed, see `derive_id`), or `packs: <dir>` for the country
    departments' `SourceRow`s. ONE CANONICAL ID PER SOURCE: a later row whose id was already
    seen is ignored (first definition wins, so no lane can silently redefine another's), and a
    later row from ANOTHER roster naming the same page (`canonical_url`) AND the same thing
    (`slug` of the name) in the same region becomes an alias of the first rather than a second
    source (two countries' packs naming one vendor page are two sources). Same page,
    different thing (a portal ground and one dataset on it) stays two sources, each naming the
    other in `shares_page` -- merging them would erase the dataset's own attribution."""
    doc = yaml.safe_load(Path(path).read_text("utf-8")) or {}
    out: list[Source] = []
    seen: set[str] = set()
    names: dict[str, str] = {}
    by_url: dict[str, Source] = {}

    def add(s: Source | None) -> None:
        if s is None or s.id in seen:
            return
        first = by_url.get(s.url_key) if s.url_key else None
        if first is not None and first.origin != s.origin:
            if slug(first.name) == slug(s.name) and first.region == s.region:
                first.aliases.append(s.id)
                return
            first.shares_page.append(s.id)
            s.shares_page.append(first.id)
        seen.add(s.id)
        out.append(s)
        if s.url_key:
            by_url.setdefault(s.url_key, s)

    for row in doc.get("sources") or []:
        add(normalise_row(row, origin=str(path)) if isinstance(row, Mapping) else None)
    base = root or Path(path).resolve().parents[2]
    for entry in doc.get("external_rosters") or []:
        e = entry if isinstance(entry, Mapping) else {"path": entry}
        defaults = dict(e.get("defaults") or {})
        if e.get("packs"):
            for row in pack_rows(base / str(e["packs"])):
                add(normalise_row(row, origin=str(row.get("_origin")),
                                  defaults={**defaults, **dict(row.get("_defaults") or {})}))
            continue
        for fp in sorted(glob.glob(str(base / str(e.get("path"))), recursive=True)):
            for row in _rows_of(Path(fp), str(e.get("rows") or "")):
                if not (row.get("id") or row.get("source_id")):
                    if not e.get("id_style") or not (row.get("name") or _row_url(row)):
                        continue
                    sid = derive_id(row, str(e["id_style"]), names)
                    names[sid] = str(row.get("name") or row.get("title") or "")
                    row = {**row, "id": sid}
                if e.get("seat_template"):
                    rid = row.get("id") or row.get("source_id")
                    row = {**row, "seats": [str(e["seat_template"]).format(id=rid)]}
                add(normalise_row(row, origin=fp, defaults=defaults))
    return out


def roster_files(path: Path = ROSTER, *, root: Path | None = None) -> list[dict[str, Any]]:
    """Every external roster entry and what it matched. An entry matching nothing is MISSING --
    loud, never a silent zero -- unless it declares `pending` (the lane's branch has not merged;
    the reason is the value) or `optional` (a glob a lane may or may not use)."""
    doc = yaml.safe_load(Path(path).read_text("utf-8")) or {}
    base = root or Path(path).resolve().parents[2]
    out = []
    for entry in doc.get("external_rosters") or []:
        e = entry if isinstance(entry, Mapping) else {"path": entry}
        if e.get("packs"):
            n = len(list((base / str(e["packs"])).glob("*/pack.py")))
            out.append({"path": str(e["packs"]), "files": n,
                        "state": "OK" if n else "MISSING"})
            continue
        n = len(glob.glob(str(base / str(e.get("path"))), recursive=True))
        state = "OK" if n else ("PENDING" if e.get("pending") else
                                "OPTIONAL_EMPTY" if e.get("optional") else "MISSING")
        out.append({"path": str(e.get("path")), "files": n, "state": state,
                    **({"pending": str(e["pending"])} if e.get("pending") and not n else {})})
    return out


def pack_rows(countries: Path) -> list[dict[str, Any]]:
    """Every country department's declared sources as roster rows (`pack_<cc>_<id>`), owned by
    that department. A layer the pack DECLARES absent is not a source; a pack that will not load
    contributes nothing and breaks nothing."""
    rows: list[dict[str, Any]] = []
    try:
        from libs.research import country_lab
    except Exception:
        return rows
    for pf in sorted(countries.glob("*/pack.py")):
        cc = pf.parent.name
        try:
            pack = country_lab.resolve_pack(cc)
            srows = country_lab.source_rows(pack) if pack is not None else []
        except Exception:
            continue
        for r in srows:
            if getattr(r, "absent_reason", "") or not getattr(r, "id", ""):
                continue
            roots = [str(x) for x in (r.roots or ()) if str(x)]
            rows.append({"id": f"pack_{cc}_{r.id}", "name": r.label or r.id,
                         "url": roots[0] if roots else "", "region": cc,
                         "language": (r.languages or ("",))[0], "licence": r.licence,
                         "_origin": str(pf), "_defaults": {
                             "owner": f"country_pack/{cc}",
                             "consumer": f"desks/mt5/research/countries/{cc}/pack.py"}})
    return rows


def _rows_of(fp: Path, key: str = "") -> list[Mapping[str, Any]]:
    try:
        text = fp.read_text("utf-8")
    except OSError:
        return []
    if fp.suffix in (".yaml", ".yml"):
        doc: Any = yaml.safe_load(text)
    elif fp.suffix == ".jsonl":
        doc = []
        for line in text.splitlines():
            try:
                doc.append(json.loads(line))
            except ValueError:
                continue
    else:
        try:
            doc = json.loads(text)
        except ValueError:
            return []
    if isinstance(doc, Mapping) and key:
        doc = doc.get(key)
    elif isinstance(doc, Mapping):
        doc = (doc.get("sources") or doc.get("rows") or doc.get("grounds")
               or [x for v in doc.values() if isinstance(v, list) for x in v])
    if not isinstance(doc, list):
        return []
    return [r if isinstance(r, Mapping) else {"url": r} for r in doc
            if isinstance(r, Mapping) or (isinstance(r, str) and r.startswith("http"))]


# ======================================================================== cursors
class CursorStore:
    """One JSON file per source. Atomic replace; a torn write leaves the previous cursor."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, sid: str) -> Path:
        return self.root / (re.sub(r"[^\w.-]", "_", sid) + ".json")

    def get(self, sid: str) -> dict[str, Any]:
        try:
            doc = json.loads(self._path(sid).read_text("utf-8"))
        except (OSError, ValueError):
            return {}
        return doc if isinstance(doc, dict) else {}

    def save(self, sid: str, cursor: Mapping[str, Any]) -> None:
        p = self._path(sid)
        tmp = p.with_suffix(f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps(dict(cursor), ensure_ascii=False, default=str), "utf-8")
        os.replace(tmp, p)


# ======================================================================== fetch plumbing
@dataclass
class HttpResult:
    status: int | None
    text: str
    error: str = ""
    final_url: str = ""

    @property
    def ok(self) -> bool:
        return self.status is not None and 200 <= self.status < 400 and not self.error


HttpGet = Callable[[str, Mapping[str, str]], HttpResult]


def polite_http(deadline: float, leg: str = "global_mining") -> HttpGet:
    """Production transport: `libs.data.polite_fetch.get` bounded by `deadline`."""
    from libs.data import polite_fetch

    def get(url: str, headers: Mapping[str, str]) -> HttpResult:
        r = polite_fetch.get(url, headers=dict(headers), timeout=20.0, retries=2,
                             deadline=deadline, leg=leg)
        return HttpResult(r.status, r.text, r.error, r.final_url)
    return get


@dataclass
class Item:
    uri: str
    body: str
    title: str = ""
    publication_time: str | None = None
    cursor_update: dict[str, Any] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)


ROBOTS_AGENT = "quant-global-mining"


class RobotsCache:
    """robots.txt per host, fetched once per pass through the same transport. 404/410 means
    no rules; any other failure to read it means DISALLOW (the conservative reading)."""

    def __init__(self) -> None:
        self._by_host: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        self._lock = threading.Lock()

    def allowed(self, url: str, http_get: HttpGet) -> bool:
        parts = urllib.parse.urlsplit(url)
        host = f"{parts.scheme}://{parts.netloc}"
        with self._lock:
            known = host in self._by_host
            rp = self._by_host.get(host)
        if not known:
            r = http_get(host + "/robots.txt", {})
            if r.ok:
                rp = urllib.robotparser.RobotFileParser()
                rp.parse(r.text.splitlines())
            elif r.status in (404, 410):
                rp = None
            else:
                rp = urllib.robotparser.RobotFileParser()
                rp.parse(["User-agent: *", "Disallow: /"])
            with self._lock:
                self._by_host[host] = rp
        return rp is None or rp.can_fetch(ROBOTS_AGENT, url)


@dataclass
class FetchContext:
    http_get: HttpGet
    deadline: float
    max_items: int = 200
    now: datetime = field(default_factory=utcnow)
    root: Path = field(default_factory=Path.cwd)         # relative paths in the roster resolve here
    blocked: list[str] = field(default_factory=list)     # hosts/urls that refused this run
    ok_fetches: int = 0
    respect_robots: bool = False
    robots: RobotsCache = field(default_factory=RobotsCache)

    def expired(self) -> bool:
        return time.monotonic() >= self.deadline

    def fetch(self, url: str, headers: Mapping[str, str] | None = None) -> HttpResult:
        if self.respect_robots and not self.robots.allowed(url, self.http_get):
            self.blocked.append(f"{url} -> ROBOTS_DISALLOWED")
            return HttpResult(None, "", "ROBOTS_DISALLOWED")
        r = self.http_get(url, headers or {})
        if r.ok:
            self.ok_fetches += 1
        else:
            self.blocked.append(f"{url} -> {r.status or r.error}")
        return r


Fetcher = Callable[[Source, dict[str, Any], FetchContext], Iterator[Item]]

_TAG = re.compile(r"(?is)<(script|style|noscript|svg)\b.*?</\1>")
_ANY_TAG = re.compile(r"(?s)<[^>]+>")
_TITLE = re.compile(r"(?is)<title[^>]*>(.*?)</title>")
_HREF = re.compile(r"""(?i)href\s*=\s*["']([^"'#]+)["']""")
_META_TIME = re.compile(
    r"""(?is)<meta[^>]+(?:property|name|itemprop)\s*=\s*["'](?:article:published_time|"""
    r"""datePublished|pubdate|date|og:published_time)["'][^>]*content\s*=\s*["']([^"']+)""")
_TIME_TAG = re.compile(r"""(?is)<time[^>]+datetime\s*=\s*["']([^"']+)["']""")


def html_to_text(page: str) -> str:
    t = _TAG.sub(" ", page)
    t = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>|</h\d>", "\n", t)
    t = _ANY_TAG.sub(" ", t)
    t = _html.unescape(t)
    t = re.sub(r"[ \t\r\f\v]+", " ", t)
    return re.sub(r"\n\s*\n+", "\n", t).strip()


def html_title(page: str) -> str:
    m = _TITLE.search(page)
    return _html.unescape(re.sub(r"\s+", " ", m.group(1))).strip()[:300] if m else ""


def html_time(page: str) -> str | None:
    m = _META_TIME.search(page) or _TIME_TAG.search(page)
    return m.group(1) if m else None


def _seen(cursor: dict[str, Any]) -> set[str]:
    return set(cursor.get("seen") or [])


def _seen_add(cursor: dict[str, Any], key: str) -> dict[str, Any]:
    """Mark `key` seen IN the fetcher's working cursor and return the update to persist."""
    seen = list(cursor.get("seen") or [])
    seen.append(key)
    cursor["seen"] = seen[-SEEN_CAP:]
    return {"seen": list(cursor["seen"])}


# ======================================================================== fetchers
def fetch_html_listing(src: Source, cursor: dict[str, Any], ctx: FetchContext
                       ) -> Iterator[Item]:
    """Listing pages -> item links -> item pages. Scans page 1 (newest) every run AND walks a
    deep page cursor, so the long tail of the whole index is reached over successive runs.

    `listing` rows are a URL, or {url: ".../page{page}", page1: "..."} when page 1 has its own
    address (MQL5's /en/code/mt5/experts vs /en/code/mt5/experts/page2)."""
    cfg = src.config
    raw = cfg.get("listing") or cfg.get("urls") or cfg.get("url") or []
    listings = [raw] if isinstance(raw, (str, Mapping)) else list(raw)
    item_rx = re.compile(str(cfg.get("item_regex") or r"."))
    per_run = _as_int(cfg.get("pages_per_run"), 2)
    listing_only = bool(cfg.get("listing_only", False))
    subpages = [str(s) for s in (cfg.get("item_subpages") or [""])]
    seen = _seen(cursor)
    for li, entry in enumerate(listings):
        tmpl = str(entry.get("url") if isinstance(entry, Mapping) else entry)
        first = str(entry.get("page1") or "") if isinstance(entry, Mapping) else ""
        pages_cur = dict(cursor.get("page") or {}) if isinstance(cursor.get("page"), dict) \
            else {}
        deep = max(2, _as_int(pages_cur.get(str(li)), 2))
        pages = [1, *range(deep, deep + per_run)] if "{page}" in tmpl else [1]
        for p in pages:
            if ctx.expired():
                return
            url = (first or tmpl.replace("{page}", "1")) if p == 1 \
                else tmpl.replace("{page}", str(p))
            r = ctx.fetch(url)
            if not r.ok and p == 1:
                break
            links = [urllib.parse.urljoin(url, h) for h in _HREF.findall(r.text)] \
                if r.ok else []
            links = list(dict.fromkeys(u for u in links if item_rx.search(u)))
            if p > 1 and not links:
                # Walked off the end of the index: wrap the deep cursor to the start.
                pages_cur[str(li)] = 2
                cursor["page"] = pages_cur
                yield Item(uri="", body="", cursor_update={"page": dict(pages_cur)})
                break
            for u in links[: ctx.max_items]:
                if u in seen or ctx.expired():
                    continue
                if listing_only:
                    seen.add(u)
                    yield Item(uri=u, title=u, body=_snippet_near(r.text, u),
                               cursor_update=_seen_add(cursor, u), meta={"listing": url})
                    continue
                body_parts, title, ptime = [], "", None
                for sp in subpages:
                    ir = ctx.fetch(u + sp)
                    if not ir.ok:
                        continue
                    title = title or html_title(ir.text)
                    ptime = ptime or html_time(ir.text)
                    body_parts.append(html_to_text(ir.text))
                if not body_parts:
                    continue
                seen.add(u)
                yield Item(uri=u, title=title, body="\n".join(body_parts),
                           publication_time=ptime, cursor_update=_seen_add(cursor, u),
                           meta={"listing": url})
            if p > 1:
                pages_cur[str(li)] = p + 1
                cursor["page"] = pages_cur
                yield Item(uri="", body="", cursor_update={"page": dict(pages_cur)})


def _snippet_near(page: str, url: str) -> str:
    path = urllib.parse.urlparse(url).path
    i = page.find(path) if path else -1
    if i < 0:
        return ""
    return html_to_text(page[max(0, i - 200): i + 1200])[:1500]


_RSS_ITEM = re.compile(r"(?is)<(item|entry)\b[^>]*>(.*?)</\1>")


def _feed_field(block: str, *names: str) -> str:
    for n in names:
        m = re.search(rf"(?is)<{n}\b[^>]*>(.*?)</{n}>", block)
        if m:
            v = re.sub(r"(?is)^<!\[CDATA\[(.*)\]\]>$", r"\1", m.group(1).strip())
            return _html.unescape(v).strip()
        if n == "link":
            m2 = re.search(r"""(?is)<link\b[^>]*href\s*=\s*["']([^"']+)""", block)
            if m2:
                return m2.group(1)
    return ""


def fetch_rss(src: Source, cursor: dict[str, Any], ctx: FetchContext) -> Iterator[Item]:
    feeds = src.config.get("feeds") or []
    seen = _seen(cursor)
    for f in [feeds] if isinstance(feeds, str) else feeds:
        if ctx.expired():
            return
        r = ctx.fetch(str(f))
        if not r.ok:
            continue
        for m in _RSS_ITEM.finditer(r.text):
            b = m.group(2)
            link = _feed_field(b, "link", "guid", "id")
            key = _feed_field(b, "guid", "id") or link
            if not key or key in seen:
                continue
            seen.add(key)
            yield Item(uri=link or key, title=html_to_text(_feed_field(b, "title")),
                       body=html_to_text(_feed_field(b, "description", "content", "summary",
                                                     "content:encoded")),
                       publication_time=_feed_field(b, "pubDate", "published", "updated",
                                                    "dc:date") or None,
                       cursor_update=_seen_add(cursor, key))


def fetch_reddit_json(src: Source, cursor: dict[str, Any], ctx: FetchContext
                      ) -> Iterator[Item]:
    """`/r/<sub>/new.json` (or a search URL), newest-after-cursor by created_utc."""
    subs = src.config.get("subs") or []
    searches = src.config.get("searches") or []
    urls = [(f"sub:{s}", f"https://www.reddit.com/r/{s}/new.json?limit=100&raw_json=1")
            for s in subs]
    urls += [(f"q:{q}", "https://www.reddit.com/search.json?sort=new&limit=100&raw_json=1&q="
              + urllib.parse.quote(str(q))) for q in searches]
    marks = dict(cursor.get("created") or {})
    for key, url in urls:
        if ctx.expired():
            return
        r = ctx.fetch(url, {"Accept": "application/json"})
        if not r.ok:
            continue
        try:
            children = json.loads(r.text)["data"]["children"]
        except (ValueError, KeyError, TypeError):
            ctx.blocked.append(f"{url} -> unparseable json")
            continue
        last = float(marks.get(key) or 0.0)
        posts = sorted((c.get("data") or {} for c in children if isinstance(c, dict)),
                       key=lambda d: float(d.get("created_utc") or 0.0))
        for d in posts:
            t = float(d.get("created_utc") or 0.0)
            if t <= last:
                continue
            marks[key] = t
            yield Item(uri="https://www.reddit.com" + str(d.get("permalink") or ""),
                       title=str(d.get("title") or ""),
                       body=f"{d.get('selftext') or ''}\n{d.get('url') or ''}",
                       publication_time=iso(datetime.fromtimestamp(t, tz=utcnow().tzinfo)),
                       cursor_update={"created": dict(marks)},
                       meta={"subreddit": d.get("subreddit"), "score": d.get("score"),
                             "num_comments": d.get("num_comments")})


def fetch_github_search(src: Source, cursor: dict[str, Any], ctx: FetchContext
                        ) -> Iterator[Item]:
    """GitHub search (repositories or issues), ascending by update time from the cursor, with
    each repository's README. Keyless works at 10 searches/min; GITHUB_TOKEN raises it."""
    cfg = src.config
    what = str(cfg.get("search") or "repositories")
    hdr = {"Accept": "application/vnd.github+json"}
    tok = os.environ.get(src.auth_env or "GITHUB_TOKEN", "")
    if tok:
        hdr["Authorization"] = f"Bearer {tok}"
    marks = dict(cursor.get("since") or {})
    for q in cfg.get("queries") or []:
        if ctx.expired():
            return
        since = str(marks.get(q) or cfg.get("start") or "2015-01-01")
        field_ = "pushed" if what == "repositories" else "updated"
        url = (f"https://api.github.com/search/{what}?per_page=50&sort=updated&order=asc&q="
               + urllib.parse.quote(f"{q} {field_}:>={since[:19]}"))
        r = ctx.fetch(url, hdr)
        if not r.ok:
            continue
        try:
            items = json.loads(r.text).get("items") or []
        except ValueError:
            continue
        for it in items[: ctx.max_items]:
            if ctx.expired():
                return
            upd = str(it.get("pushed_at") or it.get("updated_at") or since)
            marks[q] = upd
            body = f"{it.get('description') or ''}\n{' '.join(it.get('topics') or [])}\n" \
                   f"{it.get('body') or ''}"
            if what == "repositories" and cfg.get("readme", True):
                full = str(it.get("full_name") or "")
                rr = ctx.fetch(f"https://raw.githubusercontent.com/{full}/HEAD/README.md")
                if rr.ok:
                    body += "\n" + rr.text[:60_000]
            yield Item(uri=str(it.get("html_url") or ""),
                       title=str(it.get("full_name") or it.get("title") or ""), body=body,
                       publication_time=str(it.get("created_at") or "") or None,
                       cursor_update={"since": dict(marks)},
                       meta={"stars": it.get("stargazers_count"), "updated": upd,
                             "language": it.get("language"),
                             "licence": (it.get("license") or {}).get("spdx_id")
                             if isinstance(it.get("license"), dict) else None})


_TG_MSG = re.compile(r'(?is)data-post="([\w_]+/\d+)".*?(?:tgme_widget_message_text[^>]*>'
                     r'(.*?)</div>).*?<time[^>]+datetime="([^"]+)"')


def fetch_telegram_preview(src: Source, cursor: dict[str, Any], ctx: FetchContext
                           ) -> Iterator[Item]:
    """Public channel previews at t.me/s/<channel> (no login). Channels come from the roster
    AND from `discovered`, which search routes append to as they find new ones."""
    chans = list(src.config.get("channels") or []) + list(cursor.get("discovered") or [])
    last = dict(cursor.get("last_id") or {})
    for ch in dict.fromkeys(str(c).strip("@/ ") for c in chans):
        if ctx.expired() or not ch:
            return
        r = ctx.fetch(f"https://t.me/s/{ch}")
        if not r.ok:
            continue
        for m in _TG_MSG.finditer(r.text):
            post, text, when = m.group(1), m.group(2), m.group(3)
            try:
                mid = int(post.rsplit("/", 1)[1])
            except (IndexError, ValueError):
                continue
            if mid <= int(last.get(ch) or 0):
                continue
            last[ch] = mid
            yield Item(uri=f"https://t.me/{post}", title=f"@{ch}", body=html_to_text(text),
                       publication_time=when, cursor_update={"last_id": dict(last)})


def _dig(obj: Any, path: str) -> Any:
    for part in [p for p in path.split(".") if p]:
        if isinstance(obj, Mapping):
            obj = obj.get(part)
        elif isinstance(obj, list) and part.isdigit():
            obj = obj[int(part)] if int(part) < len(obj) else None
        else:
            return None
    return obj


def auth_headers(src: Source) -> dict[str, str]:
    """The source's secret as the header its API expects, read from `auth_env` and never logged.

    `config.auth_style`:
      cookie   the value is sent as `Cookie`. A full browser cookie string or `name=value` is
               used as pasted; a bare token becomes `<cookie_name>=<token>` (Xueqiu:
               `xq_a_token`). A leading `Cookie:` is stripped.
      kakaoak  `Authorization: KakaoAK <REST API key>` (Kakao/Daum search takes the app's REST
               key, not a user OAuth token). A pasted `KakaoAK ` prefix is stripped.
      bearer   `Authorization: Bearer <token>`.
    """
    raw = os.environ.get(src.auth_env, "").strip() if src.auth_env else ""
    style = str(src.config.get("auth_style") or "")
    if not raw or not style:
        return {}
    if style == "cookie":
        raw = re.sub(r"(?i)^cookie:\s*", "", raw)
        if "=" not in raw:
            raw = f"{src.config.get('cookie_name') or 'token'}={raw}"
        return {"Cookie": raw}
    if style == "kakaoak":
        return {"Authorization": "KakaoAK " + re.sub(r"(?i)^kakaoak\s+", "", raw)}
    if style == "bearer":
        return {"Authorization": "Bearer " + re.sub(r"(?i)^bearer\s+", "", raw)}
    return {}


def _time_text(v: Any) -> str | None:
    """API timestamps: ISO strings pass through; epoch seconds or milliseconds become ISO."""
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)) or (isinstance(v, str) and v.strip().isdigit()):
        x = float(v)
        t = parse_time(x / 1000.0 if x > 1e11 else x)
        return iso(t) if t else None
    return str(v)


def fetch_json_api(src: Source, cursor: dict[str, Any], ctx: FetchContext) -> Iterator[Item]:
    """A generic JSON listing: `url` or `urls` (with {q} and {page}), `items_path`, field paths,
    and the source's secret sent the way `config.auth_style` says (see `auth_headers`)."""
    cfg = src.config
    fields = dict(cfg.get("fields") or {})
    seen = _seen(cursor)
    headers = {"Accept": "application/json", **auth_headers(src)}
    urls = [str(u) for u in (cfg.get("urls") or [cfg.get("url") or ""]) if u]
    multi = len(urls) > 1
    for base in urls:
        for q in cfg.get("queries") or [""]:
            key = f"{base}|{q}" if multi else str(q)
            page = _as_int((cursor.get("page") or {}).get(key), 1) \
                if isinstance(cursor.get("page"), dict) else 1
            max_page = _as_int(cfg.get("max_page"), 0)
            if max_page and page > max_page:
                page = 1                                   # wrap: the index is walked again
            for p in (1, page) if page > 1 else (1,):
                if ctx.expired():
                    return
                url = base.replace("{q}", urllib.parse.quote(str(q))).replace("{page}", str(p))
                r = ctx.fetch(url, headers)
                if not r.ok:
                    break
                try:
                    items = _dig(json.loads(r.text), str(cfg.get("items_path") or ""))
                except ValueError:
                    break
                if not isinstance(items, list) or not items:
                    break
                for it in items:
                    uri = str(_dig(it, str(fields.get("uri") or "url")) or "")
                    if cfg.get("uri_template"):
                        uri = str(cfg["uri_template"]).format(
                            **{k: _dig(it, str(v)) for k, v in fields.items()})
                    if not uri or uri in seen:
                        continue
                    seen.add(uri)
                    yield Item(uri=uri,
                               title=html_to_text(str(_dig(it, str(fields.get("title")
                                                                    or "title")) or "")),
                               body=html_to_text(str(_dig(it, str(fields.get("body") or "body"))
                                                     or "")),
                               publication_time=_time_text(_dig(it, str(fields.get("time")
                                                                        or "time"))),
                               cursor_update=_seen_add(cursor, uri))
                pg = dict(cursor.get("page") or {})
                pg[key] = p + 1
                yield Item(uri="", body="", cursor_update={"page": pg})


_BING = re.compile(r'(?is)<li class="b_algo".*?<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>(.*?)</li>')
_DDG = re.compile(r'(?is)<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>(.*?)'
                  r'(?=<a[^>]+class="result__a"|$)')


def fetch_search_route(src: Source, cursor: dict[str, Any], ctx: FetchContext
                       ) -> Iterator[Item]:
    """Search-engine `site:` routes for grounds a link walk never reaches (WeChat via Sogou,
    Zhihu, Naver cafes, 5ch, X, Discord invites). Results are kept as snippet records; links that
    match `discover_regex` are handed to `discover_into` (another source's cursor)."""
    cfg = src.config
    seen = _seen(cursor)
    engine = str(cfg.get("engine") or "bing")
    for q in cfg.get("queries") or []:
        if ctx.expired():
            return
        qq = urllib.parse.quote(str(q))
        url = (f"https://html.duckduckgo.com/html/?q={qq}" if engine == "ddg"
               else f"https://www.bing.com/search?q={qq}&count=30")
        r = ctx.fetch(url)
        if not r.ok:
            continue
        rx = _DDG if engine == "ddg" else _BING
        for m in rx.finditer(r.text):
            link = _html.unescape(m.group(1))
            if "uddg=" in link:
                link = urllib.parse.unquote(link.split("uddg=", 1)[1].split("&", 1)[0])
            if link in seen:
                continue
            seen.add(link)
            yield Item(uri=link, title=html_to_text(m.group(2)),
                       body=html_to_text(m.group(3))[:2000],
                       cursor_update=_seen_add(cursor, link), meta={"query": q})


def fetch_page_snapshot(src: Source, cursor: dict[str, Any], ctx: FetchContext
                        ) -> Iterator[Item]:
    """Fixed pages fetched every cadence (broker specs, swap tables, prop-firm rules). The PIT
    store turns a changed page into a new vintage; an unchanged one is a no-op."""
    for pg in src.config.get("pages") or []:
        if ctx.expired():
            return
        url = str(pg.get("url") if isinstance(pg, Mapping) else pg)
        r = ctx.fetch(url)
        if not r.ok:
            continue
        label = str(pg.get("label") or "") if isinstance(pg, Mapping) else ""
        yield Item(uri=url, title=html_title(r.text) or label, body=html_to_text(r.text),
                   publication_time=None, meta={"label": label})


def fetch_external_feed(src: Source, cursor: dict[str, Any], ctx: FetchContext
                        ) -> Iterator[Item]:
    """Rows another lane already fetched (JSONL/JSON files), read by line offset so nothing is
    fetched from the network twice. Field paths map their shape onto an Item."""
    cfg = src.config
    root = ctx.root / str(cfg.get("root") or ".")
    fields = dict(cfg.get("fields") or {})
    offsets = dict(cursor.get("offsets") or {})
    patterns = [str(p) for p in cfg.get("paths") or []]
    if not any(glob.glob(str(root / p), recursive=True) for p in patterns):
        # LOUD, never an `empty` run: the lane's feed is not on this machine
        raise FileNotFoundError(f"no file matches {patterns} under {root}")
    for pattern in patterns:
        for fp in sorted(glob.glob(str(root / str(pattern)), recursive=True)):
            if ctx.expired():
                return
            start = _as_int(offsets.get(fp), 0)
            rows = _feed_rows(Path(fp))
            for i in range(start, len(rows)):
                row = rows[i]
                offsets[fp] = i + 1
                uri = str(_dig(row, str(fields.get("uri") or "url")) or "")
                frag = _dig(row, str(fields["fragment"])) if fields.get("fragment") else None
                if uri and frag:
                    uri = f"{uri}#{frag}"          # one page, many rows: not revisions of it
                body = str(_dig(row, str(fields.get("body") or "claim")) or "")
                if not uri or not body:
                    yield Item(uri="", body="", cursor_update={"offsets": dict(offsets)})
                    continue
                yield Item(uri=uri, title=str(_dig(row, str(fields.get("title") or "title"))
                                              or ""), body=body,
                           publication_time=str(_dig(row, str(fields.get("time") or
                                                              "published_time")) or "")
                           or None, cursor_update={"offsets": dict(offsets)},
                           meta={"feed": fp, "language":
                                 _dig(row, str(fields.get("language") or "lang"))})


def _feed_rows(fp: Path) -> list[Any]:
    if fp.suffix == ".jsonl":
        out = []
        try:
            with fp.open(encoding="utf-8") as fh:
                for line in fh:
                    try:
                        out.append(json.loads(line))
                    except ValueError:
                        out.append({})
        except OSError:
            return []
        return out
    try:
        doc = json.loads(fp.read_text("utf-8"))
    except (OSError, ValueError):
        return []
    if isinstance(doc, Mapping):
        doc = doc.get("discoveries") or doc.get("rows") or doc.get("items") or []
    return list(doc) if isinstance(doc, list) else []


def fetch_owned(src: Source, cursor: dict[str, Any], ctx: FetchContext) -> Iterator[Item]:
    """A row another organ fetches and consumes (its `consumer`). Rostered here for coverage and
    uses; never fetched twice."""
    return iter(())


FETCHERS: dict[str, Fetcher] = {
    "owned": fetch_owned,
    "html_listing": fetch_html_listing,
    "rss": fetch_rss,
    "reddit_json": fetch_reddit_json,
    "github_search": fetch_github_search,
    "telegram_preview": fetch_telegram_preview,
    "json_api": fetch_json_api,
    "search_route": fetch_search_route,
    "page_snapshot": fetch_page_snapshot,
    "external_feed": fetch_external_feed,
}


# ======================================================================== acquire
@dataclass
class AcquireReport:
    source_id: str
    outcome: str
    fetched: int = 0
    new: int = 0
    put: list[PutResult] = field(default_factory=list)
    detail: str = ""
    discovered: dict[str, list[str]] = field(default_factory=dict)


def is_due(src: Source, cursor: Mapping[str, Any], now: datetime) -> bool:
    last = parse_time(cursor.get("last_run"))
    return last is None or now - last >= timedelta(minutes=src.cadence_minutes)


def auth_missing(src: Source) -> bool:
    if src.auth not in ("key", "login"):
        return False
    return not (src.auth_env and os.environ.get(src.auth_env))


def owner_feed_present(src: Source, root: Path) -> bool:
    return bool(src.mode == "fallback" and src.owner_feed
                and glob.glob(str(root / src.owner_feed), recursive=True))


def acquire(src: Source, store: PitStore, cursors: CursorStore, ctx: FetchContext, *,
            root: Path | None = None, force: bool = False) -> AcquireReport:
    """One source, one pass. Always logs an outcome for the source."""
    cursor = cursors.get(src.id)
    rep = AcquireReport(src.id, "ok")
    ctx.blocked = []
    ctx.ok_fetches = 0
    ctx.respect_robots = src.respect_robots
    if not src.enabled:
        rep.outcome = "DISABLED"
    elif not force and not is_due(src, cursor, ctx.now):
        rep.outcome = "NOT_DUE"
        return rep                                     # not a run; nothing to log
    elif auth_missing(src):
        rep.outcome, rep.detail = "BLOCKED_AUTH", f"needs {src.auth} ({src.auth_env or '?'})"
    elif root is not None and owner_feed_present(src, root):
        rep.outcome, rep.detail = "DEFERRED_TO_OWNER", f"{src.owner} feed {src.owner_feed}"
    elif src.fetcher == "owned":
        rep.outcome, rep.detail = "OWNED", f"fetched and consumed by {src.consumer or src.owner}"
    elif src.fetcher not in FETCHERS:
        rep.outcome, rep.detail = "ERROR", f"unknown fetcher {src.fetcher!r}"
    if rep.outcome != "ok":
        store.log_run(src.id, rep.outcome, 0, 0, rep.detail, now=ctx.now)
        cursors.save(src.id, {**cursor, "last_run": iso(ctx.now), "last_outcome": rep.outcome})
        return rep
    discover_rx = re.compile(str(src.config["discover_regex"])) \
        if src.config.get("discover_regex") else None
    try:
        for item in FETCHERS[src.fetcher](src, dict(cursor), ctx):
            if item.uri:
                rep.fetched += 1
                res = store.put(RawRecord(
                    source_id=src.id, source_uri=item.uri, body=item.body, title=item.title,
                    publication_time=item.publication_time, acquisition_time=iso(ctx.now),
                    source_version=str(src.config.get("version") or "v1"),
                    original_language=str(item.meta.get("language") or src.language or ""),
                    immutable_time=src.immutable_time,
                    meta={**item.meta, "kind": src.kind, "priority": src.priority}),
                    now=ctx.now)
                rep.put.append(res)
                rep.new += int(res.inserted)
                if discover_rx is not None:
                    hit = discover_rx.search(item.uri)
                    if hit:
                        rep.discovered.setdefault(str(src.config.get("discover_into")), []
                                                  ).append(hit.group(1) if hit.groups()
                                                           else hit.group(0))
            if item.cursor_update:
                cursor.update(item.cursor_update)
                cursors.save(src.id, cursor)
            if rep.fetched >= ctx.max_items or ctx.expired():
                break
    except FileNotFoundError as exc:               # a lane's feed absent from this machine
        rep.outcome, rep.detail = "MISSING_FEED", str(exc)[:300]
    except Exception as exc:                       # one source's failure costs the others nothing
        rep.outcome, rep.detail = "ERROR", f"{type(exc).__name__}: {exc}"[:300]
    if rep.outcome == "ok":
        if rep.fetched == 0 and ctx.blocked and ctx.ok_fetches == 0:
            robots = all(b.endswith("ROBOTS_DISALLOWED") for b in ctx.blocked)
            rep.outcome = "BLOCKED_ROBOTS" if robots else "BLOCKED_FETCH"
            rep.detail = "; ".join(ctx.blocked[:3])[:300]
        elif rep.fetched == 0:
            rep.outcome = "empty"
    store.log_run(src.id, rep.outcome, rep.fetched, rep.new, rep.detail, now=ctx.now)
    cursor.update({"last_run": iso(ctx.now), "last_outcome": rep.outcome})
    cursors.save(src.id, cursor)
    return rep
