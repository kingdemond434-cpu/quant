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
import html as _html
import json
import os
import re
import time
import urllib.parse
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


def _as_int(v: Any, default: int) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def normalise_row(row: Mapping[str, Any], *, origin: str) -> Source | None:
    """A roster row from this file OR from another lane's source table, as it is.

    The breadth thread keeps every source as a data row (id, cadence, auth, licence, cursor,
    region/language); those rows are read here without reshaping: `source_id` or `id`,
    cadence in minutes, seconds or hours, `license` or `licence`, `lang` or `language`."""
    sid = str(row.get("id") or row.get("source_id") or "").strip()
    if not sid:
        return None
    cadence = row.get("cadence_minutes")
    if cadence is None and row.get("cadence_s") is not None:
        cadence = _as_int(row.get("cadence_s"), 3600) // 60
    if cadence is None and row.get("cadence_hours") is not None:
        cadence = _as_int(row.get("cadence_hours"), 1) * 60
    if cadence is None and isinstance(row.get("cadence"), (int, float, str)):
        c = str(row.get("cadence")).strip().lower()
        named = {"hourly": 60, "daily": 1440, "weekly": 10080, "continuous": 15}
        cadence = named.get(c, _as_int(c.rstrip("m"), 60))
    auth = str(row.get("auth") or "none").lower()
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
    fetcher = str(row.get("fetcher") or ("rss" if row.get("feeds") or row.get("rss")
                                         else "external_feed" if row.get("paths")
                                         else "html_listing"))
    if fetcher == "rss" and "feeds" not in cfg and row.get("rss"):
        cfg["feeds"] = [row.get("rss")] if isinstance(row.get("rss"), str) else row.get("rss")
    return Source(
        id=sid, fetcher=fetcher, kind=str(row.get("kind") or "text"),
        priority=_as_int(row.get("priority"), 9), name=str(row.get("name") or sid),
        cadence_minutes=max(1, _as_int(cadence, 60)), auth=auth,
        auth_env=str(row.get("auth_env") or ""), region=str(row.get("region") or "global"),
        language=str(row.get("language") or row.get("lang") or ""),
        licence=str(row.get("licence") or row.get("license") or ""),
        owner=str(row.get("owner") or "global_mining"), mode=str(row.get("mode") or "primary"),
        owner_feed=str(row.get("owner_feed") or ""),
        immutable_time=bool(row.get("immutable_time", False)),
        handoff_deepening=bool(row.get("handoff_deepening", True)),
        feeds=[str(x) for x in (row.get("feeds_to") or [])],
        enabled=bool(row.get("enabled", True)), config=cfg, origin=origin)


def load_roster(path: Path = ROSTER, *, root: Path | None = None) -> list[Source]:
    """The roster, plus every external roster its `external_rosters` globs name.

    Later rows with an id already seen are ignored (the first definition wins), so another lane
    adding a row can never silently redefine one of ours."""
    doc = yaml.safe_load(Path(path).read_text("utf-8")) or {}
    out: list[Source] = []
    seen: set[str] = set()
    for row in doc.get("sources") or []:
        s = normalise_row(row, origin=str(path)) if isinstance(row, Mapping) else None
        if s and s.id not in seen:
            seen.add(s.id)
            out.append(s)
    base = root or Path(path).resolve().parents[2]
    for pattern in doc.get("external_rosters") or []:
        for fp in sorted(glob.glob(str(base / str(pattern)), recursive=True)):
            for row in _rows_of(Path(fp)):
                s = normalise_row(row, origin=fp)
                if s and s.id not in seen:
                    seen.add(s.id)
                    out.append(s)
    return out


def _rows_of(fp: Path) -> list[Mapping[str, Any]]:
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
    if isinstance(doc, Mapping):
        doc = doc.get("sources") or doc.get("rows") or list(doc.values())
    return [r for r in doc if isinstance(r, Mapping)] if isinstance(doc, list) else []


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


@dataclass
class FetchContext:
    http_get: HttpGet
    deadline: float
    max_items: int = 200
    now: datetime = field(default_factory=utcnow)
    root: Path = field(default_factory=Path.cwd)         # relative paths in the roster resolve here
    blocked: list[str] = field(default_factory=list)     # hosts/urls that refused this run
    ok_fetches: int = 0

    def expired(self) -> bool:
        return time.monotonic() >= self.deadline

    def fetch(self, url: str, headers: Mapping[str, str] | None = None) -> HttpResult:
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


def fetch_json_api(src: Source, cursor: dict[str, Any], ctx: FetchContext) -> Iterator[Item]:
    """A generic JSON listing: `url` (with {q} and {page}), `items_path`, and field paths."""
    cfg = src.config
    fields = dict(cfg.get("fields") or {})
    seen = _seen(cursor)
    for q in cfg.get("queries") or [""]:
        page = _as_int((cursor.get("page") or {}).get(str(q)), 1) \
            if isinstance(cursor.get("page"), dict) else 1
        for p in (1, page) if page > 1 else (1,):
            if ctx.expired():
                return
            url = str(cfg.get("url") or "").replace("{q}", urllib.parse.quote(str(q))) \
                .replace("{page}", str(p))
            r = ctx.fetch(url, {"Accept": "application/json"})
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
                yield Item(uri=uri, title=str(_dig(it, str(fields.get("title") or "title"))
                                              or ""),
                           body=html_to_text(str(_dig(it, str(fields.get("body") or "body"))
                                                 or "")),
                           publication_time=str(_dig(it, str(fields.get("time") or "time"))
                                                or "") or None,
                           cursor_update=_seen_add(cursor, uri))
            pg = dict(cursor.get("page") or {})
            pg[str(q)] = p + 1
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
    for pattern in cfg.get("paths") or []:
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


FETCHERS: dict[str, Fetcher] = {
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
    if not src.enabled:
        rep.outcome = "DISABLED"
    elif not force and not is_due(src, cursor, ctx.now):
        rep.outcome = "NOT_DUE"
        return rep                                     # not a run; nothing to log
    elif auth_missing(src):
        rep.outcome, rep.detail = "BLOCKED_AUTH", f"needs {src.auth} ({src.auth_env or '?'})"
    elif root is not None and owner_feed_present(src, root):
        rep.outcome, rep.detail = "DEFERRED_TO_OWNER", f"{src.owner} feed {src.owner_feed}"
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
    except Exception as exc:                       # one source's failure costs the others nothing
        rep.outcome, rep.detail = "ERROR", f"{type(exc).__name__}: {exc}"[:300]
    if rep.outcome == "ok":
        if rep.fetched == 0 and ctx.blocked and ctx.ok_fetches == 0:
            rep.outcome, rep.detail = "BLOCKED_FETCH", "; ".join(ctx.blocked[:3])[:300]
        elif rep.fetched == 0:
            rep.outcome = "empty"
    store.log_run(src.id, rep.outcome, rep.fetched, rep.new, rep.detail, now=ctx.now)
    cursor.update({"last_run": iso(ctx.now), "last_outcome": rep.outcome})
    cursors.save(src.id, cursor)
    return rep
