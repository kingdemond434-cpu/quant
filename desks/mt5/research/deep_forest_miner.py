"""The deep-forest story miner: the WORLD's practitioner ground, reverse-engineered for the gates.

    Discover (search-engine + platform routes, every region) -> Extract (claims in 26 languages)
      -> dedupe on mechanism key -> queue (story_mechanism, one task per mechanism, N provenance
      rows) -> deepening worker Reimplement -> compiler -> gauntlet
      -> world crawler frontier (every URL found here becomes crawlable ground)
      -> dataset discoveries (every downloadable series found here reaches acquire_datasets)

WHY A SECOND MINER BESIDE THE WORLD CRAWLER. The crawler follows LINKS; it reaches what its
frontier links to. Most of the deep forest -- Chinese, Japanese, Korean, Vietnamese, Brazilian,
Polish, Turkish, Russian ... -- is not linked from anywhere the crawler has been: it is indexed
by search engines, sits behind JavaScript shells, or lives on platforms with their own APIs. This
miner reaches those by ROUTE -- search-engine `site:` queries in the ground's own locale for
grounds that refuse direct fetches, platform APIs where they exist (Qiita, Zenn, Habr, arXiv,
Gitee, Bilibili ...), RSS where a site publishes one, the Wayback Machine for archives that are
gone, public Telegram previews, nitter mirrors when one is up, a rendered fetch where a shell
hides the listing -- and then hands every URL it finds to the crawler's frontier, so the forest
it opens keeps being walked after this run ends.

THE WHOLE WORLD, ROTATED (principal 2026-09-05: "asia west russia middle east south america
oceania every place ... whole world crawling and mining fully"). The grounds file carries a
`regions` index and several hundred grounds; a run cannot touch them all in its budget, so they
are scheduled round-robin across REGION CLUSTERS, heaviest `weight` first inside a cluster, from
a cursor the previous run left, and each ground gets a time share proportional to its weight.
No region gets credit for coverage, only for conversion: every ground records its own status,
re-measured each run, and the report lists per region what was worked, what converted, and
whether a ground yields nothing but the four-hundredth momentum variant.

WHAT IT KEEPS. Sentences that name a market quantity, a direction and a horizon
(`libs.research.mechanism_claims`), verbatim, with the instrument mapped to its Fusion analogue
(direct) or reached through an information channel (indirect: Brazilian soy -> USDBRL, the CBRT
-> USDTRY) or marked as a mechanism-class transfer; a claim that maps to nothing is dropped and
counted. Every kept claim carries PIT-safe provenance -- event_time when the sentence states
one, published_time when the page does, available_time (the fetch), ingested_time (the write),
revision, source_hash -- and a mechanism key, so the same story told on ten sites is ONE
deepening task with ten provenance rows. A dubious trader story is still a testable mechanism --
that is the principal's point -- and the gauntlet, not the miner, decides what it was worth.

EVERY GROUND RECORDS ITS OWN STATUS, re-measured each run. Off the box the network is usually
absent; then the miner rebuilds the queue from its claims ledger and says so.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import html as _html
import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urljoin, urlparse

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_DESK / "side_channels"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from libs.research import mechanism_claims as mc  # noqa: E402

SOURCE = "deep_forest"
KIND = "story_mechanism"
SOURCES = _DESK / "data" / "deep_forest_sources.json"
CLAIMS = _DESK / "data" / "deep_forest_claims.jsonl"
DATASETS = _DESK / "data" / "deep_forest_datasets.jsonl"
SEEN = _DESK / "data" / "deep_forest_seen.json"
REPORT = _DESK / "reports" / "DEEP_FOREST.json"
#: Where the world crawler writes its discoveries and `acquire_datasets._endpoints` reads them.
#: Dataset pages this miner finds are written there in the crawler's own row shape, so the
#: acquirer registers their endpoints without a second reader.
WORLD = _DESK / "data" / "intelligence" / "world"
#: The provenance ledger every extracted claim is appended to (libs.data.datahub's own file);
#: a constant here so a test can point it elsewhere instead of writing into the desk's ledger.
PROVENANCE = _DESK / "data" / "mined_sources.jsonl"
MAX_TASKS = 400
PAGE_FETCH_PER_QUERY = 3
DEEP_LINKS_PER_GROUND = 6
MIN_PAGE_TEXT = 1500
#: A ground's time share is its weight's share of the run budget, spread over SPREAD runs so a
#: run works a useful number of grounds deeply rather than every ground for three seconds; the
#: cursor carries the rotation across runs. Never below MIN_GROUND_S: one fetch takes that long.
SPREAD = 6.0
MIN_GROUND_S = 20.0
_UA = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
       "Accept": ("text/html,application/xhtml+xml,application/json,application/xml;q=0.9,"
                  "*/*;q=0.8")}
GRADE = {"competition": "COMPETITION_RECORD", "interview": "INTERVIEW",
         "community": "COMMUNITY_POST", "forum": "COMMUNITY_POST", "qa": "COMMUNITY_POST",
         "social": "COMMUNITY_POST", "blog": "COMMUNITY_POST", "column": "COMMUNITY_POST",
         "code": "CODE", "notebook": "CODE", "video": "VIDEO_METADATA", "academic": "PAPER",
         "research": "PAPER", "macro": "OFFICIAL", "dataset": "DATASET",
         "archive": "COMMUNITY_POST"}

#: Every route a ground may declare. A ground naming anything else is a configuration error the
#: grounds-file test catches before a run does; "unreachable" is a recorded gap, never a route.
ROUTES: frozenset[str] = frozenset({
    "http", "render", "search", "juejin", "sogou", "bilibili", "gitee", "foreign", "papers",
    "rss", "reddit", "wayback", "nitter", "youtube", "telegram", "unreachable",
})
#: libs.data.foreign_sources functions a ground may name. `coinpan` (a crypto forum) is fenced
#: out by the standing order; `dcinside` and `note` are excluded because their robots.txt names
#: this agent family (OP-041) -- those grounds ride the search-index route, snippets only.
FOREIGN_FNS: frozenset[str] = frozenset({
    "qiita", "zenn", "hatena", "velog", "habr", "vcru", "smartlab", "tinhte", "eksisozluk",
})
PAPER_FNS: frozenset[str] = frozenset({"arxiv", "ssrn", "openreview"})
#: The dataset classes a ground of kind `dataset` must declare (principal 2026-09-05).
DATASET_CLASSES: frozenset[str] = frozenset({
    "macro_vintages", "rates_curves", "positioning", "futures_volume_oi",
    "commodity_inventories", "shipping_freight", "physical_premia", "fund_etf_flows",
    "options_surfaces", "central_bank_data", "trade_data", "auction_fixing", "public_filings",
    "sentiment_news", "weather_energy",
})

#: Region -> cluster. One SOURCE per cluster (`source_of`) so the research P&L, which censuses
#: hypotheses by source, can learn which forests pay; every cluster resolves to the external
#: arm in `libs.research.bandit.SOURCE_ARM`. The Chinese forest keeps the founding source name
#: `deep_forest` so its decided-claim ids stay stable.
REGION_CLUSTER: dict[str, str] = {
    "cn": "cn", "jp": "jp", "kr": "kr", "tw": "tw_hk", "hk": "tw_hk", "sg": "sea", "vn": "sea",
    "th": "sea", "id": "sea", "my": "sea", "ph": "sea", "in": "in", "pk": "south_asia",
    "bd": "south_asia", "lk": "south_asia", "au": "anz", "nz": "anz", "sa": "mena", "ae": "mena",
    "qa": "mena", "tr": "mena", "il": "mena", "eg": "africa", "za": "africa", "ng": "africa",
    "ke": "africa", "ma": "africa", "us": "west", "gb": "west", "ca": "west", "global": "west",
    "de": "eu", "fr": "eu", "it": "eu", "es": "eu", "nl": "eu", "se": "nordics", "dk": "nordics",
    "no": "nordics", "fi": "nordics", "pl": "east_eu", "cz": "east_eu", "hu": "east_eu",
    "ua": "east_eu", "ru": "ru", "br": "latam", "mx": "latam", "cl": "latam", "co": "latam",
    "pe": "latam", "ar": "latam", "institutional": "institutional",
}


def cluster_of(g: dict[str, Any]) -> str:
    c = g.get("cluster")
    if c:
        return str(c)
    # A ground that names no region is a legacy Chinese entry: the founding forest.
    return REGION_CLUSTER.get(str(g.get("region") or "cn"), "cn")


def source_of(cluster: str) -> str:
    return SOURCE if cluster in ("cn", "", SOURCE) else f"{SOURCE}_{cluster}"


#: Search-engine locale per language: (bing setlang, bing cc, duckduckgo kl). A ground's
#: `market` (ISO country) overrides the country half, so Hong Kong searches Hong Kong and
#: Singapore searches Singapore even though both write the same language as somewhere else.
_LOCALE: dict[str, tuple[str, str, str]] = {
    "zh": ("zh-CN", "CN", "cn-zh"), "zh-Hant": ("zh-TW", "TW", "tw-tzh"),
    "ja": ("ja", "JP", "jp-jp"),
    "ko": ("ko", "KR", "kr-kr"), "ru": ("ru", "RU", "ru-ru"), "uk": ("uk", "UA", "ua-uk"),
    "vi": ("vi", "VN", "vn-vi"), "th": ("th", "TH", "th-th"), "id": ("id", "ID", "id-id"),
    "ms": ("ms", "MY", "my-ms"), "hi": ("hi", "IN", "in-en"), "en": ("en", "US", "us-en"),
    "de": ("de", "DE", "de-de"), "fr": ("fr", "FR", "fr-fr"), "it": ("it", "IT", "it-it"),
    "es": ("es", "ES", "es-es"), "pt": ("pt-BR", "BR", "br-pt"), "ar": ("ar", "SA", "xa-ar"),
    "tr": ("tr", "TR", "tr-tr"), "he": ("he", "IL", "il-he"), "pl": ("pl", "PL", "pl-pl"),
    "nl": ("nl", "NL", "nl-nl"), "sv": ("sv", "SE", "se-sv"), "da": ("da", "DK", "dk-da"),
    "no": ("nb", "NO", "no-no"), "fi": ("fi", "FI", "fi-fi"), "sw": ("sw", "KE", "ke-en"),
}
_MARKET_KL: dict[str, str] = {
    "HK": "hk-tzh", "SG": "sg-en", "AU": "au-en", "NZ": "nz-en", "IN": "in-en", "ZA": "za-en",
    "NG": "ng-en", "GB": "uk-en", "CA": "ca-en", "MX": "mx-es", "AR": "ar-es", "CL": "cl-es",
    "CO": "co-es", "PE": "pe-es", "PH": "ph-en", "MY": "my-ms", "AE": "xa-ar", "EG": "xa-ar",
    "PK": "pk-en", "KE": "ke-en", "IL": "il-he", "TR": "tr-tr", "BR": "br-pt", "TW": "tw-tzh",
    "CN": "cn-zh", "JP": "jp-jp", "KR": "kr-kr", "RU": "ru-ru", "UA": "ua-uk", "VN": "vn-vi",
    "TH": "th-th", "ID": "id-id", "SA": "xa-ar", "QA": "xa-ar", "MA": "ma-fr", "DE": "de-de",
    "FR": "fr-fr", "IT": "it-it", "ES": "es-es", "NL": "nl-nl", "SE": "se-sv", "DK": "dk-da",
    "NO": "no-no", "FI": "fi-fi", "PL": "pl-pl", "CZ": "cz-cs", "HU": "hu-hu", "US": "us-en",
}


def locale_of(lang: str, market: str = "") -> tuple[str, str, str]:
    setlang, cc, kl = _LOCALE.get(lang or "en", _LOCALE["en"])
    if market:
        cc = market.upper()
        kl = _MARKET_KL.get(cc, kl)
    return setlang, cc, kl


def accept_language(lang: str) -> str:
    setlang = _LOCALE.get(lang or "en", _LOCALE["en"])[0]
    return f"{setlang},{(lang or 'en').split('-')[0]};q=0.9,en;q=0.6"


# ------------------------------------------------------------------------------- fetching
def _http(url: str, *, timeout: float = 20.0, referer: str = "", lang: str = "") -> str:
    hdr = {**_UA, "Accept-Language": accept_language(lang)}
    if referer:
        hdr["Referer"] = referer
    req = urllib.request.Request(url, headers=hdr)
    with urllib.request.urlopen(req, timeout=timeout) as fh:
        body: str = fh.read(2_000_000).decode("utf-8", errors="replace")
    return body


def html_text(page: str) -> str:
    """Visible text of a page: scripts and styles dropped, tags removed, entities decoded."""
    s = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", page or "")
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    s = _html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def html_links(page: str, base: str) -> list[tuple[str, str]]:
    out = []
    for m in re.finditer(r'(?is)<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', page or ""):
        href, anchor = m.group(1), html_text(m.group(2))[:120]
        if href.startswith(("javascript:", "mailto:", "#")):
            continue
        out.append((urljoin(base, href).split("#")[0], anchor))
    return out[:400]


def _title(page: str) -> str:
    m = re.search(r"(?is)<title[^>]*>(.*?)</title>", page or "")
    return html_text(m.group(1))[:160] if m else ""


_META_PUBLISHED = (
    r'(?is)<meta[^>]+(?:property|name)=["\'](?:article:published_time|pubdate|publishdate|'
    r'dc\.date|date|og:published_time|parsely-pub-date|sailthru\.date)["\'][^>]+'
    r'content=["\']([^"\']+)',
    r'(?is)"datePublished"\s*:\s*"([^"]+)"',
    r'(?is)<time[^>]+datetime=["\']([^"\']+)',
)
_META_MODIFIED = (
    r'(?is)<meta[^>]+(?:property|name)=["\'](?:article:modified_time|og:updated_time|'
    r'lastmod|last-modified)["\'][^>]+content=["\']([^"\']+)',
    r'(?is)"dateModified"\s*:\s*"([^"]+)"',
)


def page_meta(page: str) -> dict[str, str | None]:
    """published_time / revision as the page STATES them -- never inferred. Absent is None."""
    out: dict[str, str | None] = {"published_time": None, "revision": None}
    for rx in _META_PUBLISHED:
        m = re.search(rx, page or "")
        if m:
            out["published_time"] = _html.unescape(m.group(1)).strip()[:40]
            break
    for rx in _META_MODIFIED:
        m = re.search(rx, page or "")
        if m:
            out["revision"] = _html.unescape(m.group(1)).strip()[:40]
            break
    return out


# --------------------------------------------------------------------------- search routes
def parse_bing(page: str) -> list[dict[str, str]]:
    rows = []
    for block in re.split(r'<li class="b_algo"', page or "")[1:]:
        m = re.search(r'(?is)<h2>\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', block)
        if not m:
            continue
        snip = re.search(r'(?is)<p[^>]*>(.*?)</p>', block)
        rows.append({"url": _html.unescape(m.group(1)), "title": html_text(m.group(2)),
                     "snippet": html_text(snip.group(1)) if snip else ""})
    return rows


def parse_ddg(page: str) -> list[dict[str, str]]:
    rows = []
    for m in re.finditer(r'(?is)<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>'
                         r'(.*?)(?=<a[^>]*class="result__a"|$)', page or ""):
        href = _html.unescape(m.group(1))
        if "uddg=" in href:
            q = parse_qs(urlparse(href).query).get("uddg") or []
            href = unquote(q[0]) if q else href
        snip = re.search(r'(?is)class="result__snippet"[^>]*>(.*?)</a>', m.group(3))
        rows.append({"url": href, "title": html_text(m.group(2)),
                     "snippet": html_text(snip.group(1)) if snip else ""})
    return rows


def bing_search(query: str, site: str = "", lang: str = "zh", market: str = ""
                ) -> tuple[list[dict[str, str]], str | None]:
    q = f"site:{site} {query}" if site else query
    setlang, cc, _kl = locale_of(lang, market)
    url = f"https://www.bing.com/search?q={quote(q)}&setlang={setlang}&cc={cc}&count=20"
    try:
        page = _http(url, referer="https://www.bing.com/", lang=lang)
    except Exception as exc:
        return [], f"{type(exc).__name__}: {str(exc)[:120]}"
    rows = parse_bing(page)
    if not rows:
        return [], (f"bing returned no parseable results ({len(page)} bytes -- an anti-bot "
                    "shell or a layout change, not an empty forest)")
    return rows, None


def ddg_search(query: str, site: str = "", lang: str = "zh", market: str = ""
               ) -> tuple[list[dict[str, str]], str | None]:
    q = f"site:{site} {query}" if site else query
    _setlang, _cc, kl = locale_of(lang, market)
    url = f"https://html.duckduckgo.com/html/?q={quote(q)}&kl={kl}"
    try:
        page = _http(url, referer="https://duckduckgo.com/", lang=lang)
    except Exception as exc:
        return [], f"{type(exc).__name__}: {str(exc)[:120]}"
    rows = parse_ddg(page)
    if not rows:
        return [], f"duckduckgo returned no parseable results ({len(page)} bytes)"
    return rows, None


def engine_search(query: str, site: str = "", lang: str = "zh", market: str = ""
                  ) -> tuple[list[dict[str, str]], str, list[str]]:
    """Bing first, DuckDuckGo second, in the ground's locale. (rows, engine, errors)."""
    errs = []
    for name, fn in (("bing", bing_search), ("duckduckgo", ddg_search)):
        rows, err = fn(query, site, lang, market)
        if rows:
            return rows, name, errs
        errs.append(f"{name}: {err}")
        time.sleep(1.0)
    return [], "", errs


# --------------------------------------------------------------------------- platform routes
def gitee_search(query: str) -> tuple[list[dict[str, Any]], str | None]:
    url = (f"https://gitee.com/api/v5/search/repositories?q={quote(query)}"
           "&sort=stars_count&order=desc&per_page=20")
    try:
        rows = json.loads(_http(url))
    except Exception as exc:
        return [], f"{type(exc).__name__}: {str(exc)[:120]}"
    if not isinstance(rows, list):
        return [], "gitee search did not return a list"
    return [{"full": r.get("full_name") or r.get("path_with_namespace") or "",
             "url": r.get("html_url") or "", "description": r.get("description") or "",
             "license": (r.get("license") or "NONE"), "stars": r.get("stargazers_count"),
             "pushed": r.get("pushed_at") or r.get("updated_at")} for r in rows
            if isinstance(r, dict)], None


def gitee_readme(full: str) -> str:
    try:
        doc = json.loads(_http(f"https://gitee.com/api/v5/repos/{full}/readme"))
        return base64.b64decode(doc.get("content", "")).decode("utf-8", errors="replace")
    except Exception:
        return ""


def bilibili_transcript(bvid: str) -> tuple[str, str | None]:
    """Public subtitles via view -> cid -> player/v2. Empty with a reason when there are none."""
    try:
        view = json.loads(_http(f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"))
        data = view.get("data") or {}
        cid = data.get("cid")
        pl = json.loads(_http(f"https://api.bilibili.com/x/player/v2?bvid={bvid}&cid={cid}"))
        subs = ((pl.get("data") or {}).get("subtitle") or {}).get("subtitles") or []
        if not subs:
            return "", "no public subtitle track (login-gated on most videos)"
        url = str(subs[0].get("subtitle_url") or "")
        url = "https:" + url if url.startswith("//") else url
        body = json.loads(_http(url))
        return " ".join(str(x.get("content", "")) for x in body.get("body", [])), None
    except Exception as exc:
        return "", f"{type(exc).__name__}: {str(exc)[:120]}"


def youtube_transcript(video_id: str, lang: str = "en") -> tuple[str, str | None]:
    """A YouTube transcript through the desk's keyless mirror rotation (Piped, Invidious),
    which `scripts/fetch_video_transcript.py` owns. MEASURED DEAD on every route 2026-08-27;
    youtube.com's own caption endpoints are barred by its robots.txt and are never tried. The
    reason is recorded per video, never an empty transcript."""
    try:
        sp = str(_ROOT / "scripts")
        if sp not in sys.path:
            sys.path.insert(0, sp)
        import fetch_video_transcript as fvt  # type: ignore[import-not-found]
        text, route = fvt.youtube(video_id, lang=lang.split("-")[0])
        return str(text), None if text else f"{route}: empty transcript"
    except Exception as exc:
        return "", f"{type(exc).__name__}: {str(exc)[:120]}"


_FEED_ITEM = re.compile(r"(?is)<(item|entry)\b[^>]*>(.*?)</\1>")


def _feed_field(block: str, *names: str) -> str:
    for n in names:
        m = re.search(rf"(?is)<{re.escape(n)}\b[^>]*>(.*?)</{re.escape(n)}>", block)
        if m:
            return html_text(re.sub(r"(?s)<!\[CDATA\[(.*?)\]\]>", r"\1", m.group(1)))
    return ""


def parse_feed(xml: str) -> list[dict[str, str]]:
    """Items of an RSS 2.0 / RSS 1.0 / Atom feed: title, url, summary, published. One shallow
    parser for all three, so a site's feed shape never decides whether its forest is read."""
    rows: list[dict[str, str]] = []
    for m in _FEED_ITEM.finditer(xml or ""):
        block = m.group(2)
        link = ""
        lm = re.search(r'(?is)<link\b[^>]*href=["\']([^"\']+)["\']', block)
        if lm:
            link = lm.group(1)
        else:
            lt = re.search(r"(?is)<link\b[^>]*>(.*?)</link>", block)
            link = html_text(lt.group(1)) if lt else ""
            if not link:
                gm = re.search(r"(?is)<guid\b[^>]*>(https?://.*?)</guid>", block)
                link = html_text(gm.group(1)) if gm else ""
        rows.append({"title": _feed_field(block, "title")[:200],
                     "url": _html.unescape(link.strip()),
                     "summary": _feed_field(block, "content:encoded", "description", "summary",
                                            "content")[:4000],
                     "published": _feed_field(block, "pubDate", "published", "updated",
                                              "dc:date")[:40]})
    return rows


def wayback_snapshot(url: str, timestamp: str = "") -> tuple[str, str | None]:
    """Nearest Wayback Machine capture of `url`, via the public availability API."""
    api = f"https://archive.org/wayback/available?url={quote(url, safe='')}"
    if timestamp:
        api += f"&timestamp={timestamp}"
    try:
        doc = json.loads(_http(api))
    except Exception as exc:
        return "", f"{type(exc).__name__}: {str(exc)[:120]}"
    snap = ((doc.get("archived_snapshots") or {}).get("closest") or {})
    if not snap.get("url"):
        return "", "no capture in the Wayback Machine"
    return str(snap["url"]), None


def parse_nitter(page: str) -> list[dict[str, str]]:
    """Tweet texts on a nitter search page, with the status link when the markup carries one."""
    rows: list[dict[str, str]] = []
    for m in re.finditer(r'(?is)<div class="tweet-content[^"]*"[^>]*>(.*?)</div>', page or ""):
        text = html_text(m.group(1))
        if not text:
            continue
        before = (page or "")[max(0, m.start() - 1500):m.start()]
        lm = list(re.finditer(r'href="(/[^"]+/status/\d+[^"]*)"', before))
        rows.append({"text": text[:600], "url": lm[-1].group(1) if lm else ""})
    return rows


# --------------------------------------------------------------------------- dataset pages
_ENDPOINT_RE = re.compile(
    r"""href=["']([^"']+?\.(?:csv|tsv|json|jsonl|parquet|zip|gz|xlsx?|txt|xml)(?:\?[^"']*)?)["']""",
    re.IGNORECASE)
_API_RE = re.compile(
    r"""href=["']([^"']*(?:/api/|/download|/dataset|/series|/data\?|format=csv|type=csv|export|"""
    r"""bulkdownload|/sdmx|/rest/data|/statistics/|/opendata)[^"']*)["']""", re.IGNORECASE)


def data_endpoints(page: str, base: str) -> list[str]:
    """Absolute URLs on the page that ARE data (files, data APIs). The crawler's own extractor
    when it is importable, so the two never disagree; the same regexes otherwise."""
    try:
        import world_crawler as wc
        return list(wc.data_endpoints(page, base))
    except Exception:
        pass
    out: list[str] = []
    seen: set[str] = set()
    for rx in (_ENDPOINT_RE, _API_RE):
        for m in rx.findall(page or ""):
            try:
                full = urljoin(base, str(m))
            except ValueError:
                continue
            if full.startswith(("http://", "https://")) and full not in seen:
                seen.add(full)
                out.append(full)
            if len(out) >= 200:
                return out
    return out


# ------------------------------------------------------------------------------- ledgers
def _load_sources() -> dict[str, Any]:
    try:
        return json.loads(SOURCES.read_text("utf-8"))
    except (OSError, ValueError):
        return {"grounds": []}


def _load_seen() -> dict[str, Any]:
    try:
        d = json.loads(SEEN.read_text("utf-8"))
        return d if isinstance(d, dict) else {"claims": [], "urls": []}
    except (OSError, ValueError):
        return {"claims": [], "urls": []}


def _save_seen(seen: dict[str, Any]) -> None:
    SEEN.parent.mkdir(parents=True, exist_ok=True)
    SEEN.write_text(json.dumps({"claims": sorted(set(seen.get("claims") or []))[-50_000:],
                                "urls": sorted(set(seen.get("urls") or []))[-50_000:],
                                "cursor": int(seen.get("cursor") or 0),
                                "runs": int(seen.get("runs") or 0),
                                "updated_utc": datetime.now(tz=UTC).isoformat()}), "utf-8")


def _claims_rows() -> list[dict[str, Any]]:
    try:
        return [json.loads(ln) for ln in CLAIMS.read_text("utf-8").splitlines() if ln.strip()]
    except (OSError, ValueError):
        return []


def _universe() -> set[str]:
    try:
        meta = json.loads((_DESK / "data" / "universe" / "universe.json").read_text("utf-8"))
        return {str(k).upper() for k in meta}
    except (OSError, ValueError):
        return set()


# ------------------------------------------------------------------------------- scheduling
def schedule(grounds: list[dict[str, Any]], cursor: int = 0, *, only: set[str] | None = None,
             region: str | None = None) -> list[dict[str, Any]]:
    """The order a run works grounds in: round-robin across clusters (heaviest weight first
    inside each), rotated by the cursor the previous run left, so every forest gets its turn
    across runs and no region is worked only because it sorts first in a file."""
    picked = []
    for g in grounds:
        if region and str(g.get("region")) != region and cluster_of(g) != region:
            continue
        if only and not ({str(g.get("name")), str(g.get("route")), str(g.get("region")),
                          cluster_of(g)} & only):
            continue
        picked.append(g)
    by_cluster: dict[str, list[dict[str, Any]]] = {}
    for g in picked:
        by_cluster.setdefault(cluster_of(g), []).append(g)
    for lst in by_cluster.values():
        lst.sort(key=lambda g: -float(g.get("weight") or 1.0))
    order = sorted(by_cluster)
    out: list[dict[str, Any]] = []
    i = 0
    while any(by_cluster.values()):
        for c in order:
            if i < len(by_cluster[c]):
                out.append(by_cluster[c][i])
        i += 1
        if all(i >= len(v) for v in by_cluster.values()):
            break
    if not out:
        return out
    start = cursor % len(out)
    return out[start:] + out[:start]


# ------------------------------------------------------------------------------- the run
class _Run:
    def __init__(self, budget_s: float, fetch: bool, only: set[str] | None,
                 region: str | None = None) -> None:
        self.budget_s, self.fetch, self.only, self.region = budget_s, fetch, only, region
        self.started = time.monotonic()
        self.g_end = self.started + budget_s
        self.seen = _load_seen()
        self.seen_claims = set(self.seen.get("claims") or [])
        self.seen_urls = set(self.seen.get("urls") or [])
        self.universe = _universe()
        self.new: list[dict[str, Any]] = []
        self.datasets: list[dict[str, Any]] = []
        self.status: list[dict[str, Any]] = []
        self.frontier: list[tuple[str, str, str]] = []
        self.counts = {"queries": 0, "pages": 0, "transcripts": 0, "rendered": 0,
                       "dropped_venue": 0, "dropped_unmappable": 0, "duplicate_mechanisms": 0,
                       "claims_seen_before": 0, "net_failures": 0, "dataset_pages": 0,
                       "dataset_endpoints": 0, "feeds": 0}
        self.network: bool | None = None
        self.render_used = 0
        self.ground: dict[str, Any] = {}
        self.ground_claims: list[dict[str, Any]] = []
        self.mech_keys: set[str] = set()

    def over(self) -> bool:
        return time.monotonic() > min(self.g_end, self.started + self.budget_s)

    def _net_ok(self) -> bool:
        """After three straight transport failures the box has no network; stop trying."""
        return self.fetch and self.network is not False

    def _note_net(self, ok: bool) -> None:
        if ok:
            self.network = True
            self.counts["net_failures"] = 0
        else:
            self.counts["net_failures"] += 1
            if self.network is None and self.counts["net_failures"] >= 3:
                self.network = False

    @property
    def lang(self) -> str:
        return str(self.ground.get("language") or "en")

    def page(self, url: str, referer: str = "") -> str:
        if not self._net_ok():
            return ""
        try:
            body = _http(url, referer=referer, lang=self.lang)
            self._note_net(True)
            self.counts["pages"] += 1
            return body
        except urllib.error.HTTPError as exc:
            self._note_net(True)
            self.status.append({"url": url, "http": exc.code})
            return ""
        except Exception as exc:
            self._note_net(False)
            self.status.append({"url": url, "error": f"{type(exc).__name__}: {str(exc)[:80]}"})
            return ""

    def rendered(self, url: str) -> str:
        try:
            from libs.data.render_fetch import render
            page, err = render(url, timeout_s=25.0, lang=locale_of(self.lang)[0])
        except Exception as exc:
            page, err = "", f"{type(exc).__name__}: {str(exc)[:80]}"
        if err:
            self.status.append({"url": url, "render": err[:120]})
            return ""
        self.counts["rendered"] += 1
        return page

    # ------------------------------------------------------------------ what a page yields
    def take(self, text: str, *, ground: dict[str, Any], url: str, title: str,
             route: str, grade: str | None = None, extra: dict[str, Any] | None = None,
             page: str = "") -> int:
        r = mc.extract(text, universe=self.universe or None)
        self.counts["dropped_venue"] += int(r["dropped_venue"])
        self.counts["dropped_unmappable"] += int(r["dropped_unmappable"])
        self.counts["duplicate_mechanisms"] += int(r["duplicate_mechanisms"])
        meta = page_meta(page) if page else {"published_time": None, "revision": None}
        now = datetime.now(tz=UTC).isoformat(timespec="seconds")
        src_hash = hashlib.sha256((text or "").encode("utf-8")).hexdigest()
        n = 0
        for c in r["claims"]:
            if c["claim_hash"] in self.seen_claims:
                self.counts["claims_seen_before"] += 1
                continue
            self.seen_claims.add(c["claim_hash"])
            row = {**c, "kind": KIND, "ground": ground.get("name"),
                   "ground_kind": ground.get("kind"),
                   "region": ground.get("region"), "language": ground.get("language"),
                   "cluster": cluster_of(ground), "source": source_of(cluster_of(ground)),
                   "route": route, "url": url, "title": title[:160],
                   "evidence_grade": grade or GRADE.get(str(ground.get("kind")), "COMMUNITY_POST"),
                   # PIT-SAFE PROVENANCE (principal 2026-09-05): what the sentence states, what
                   # the page states, when the desk could first have read it, when it wrote it.
                   "published_time": meta["published_time"], "available_time": now,
                   "ingested_time": now, "revision": meta["revision"], "source_hash": src_hash,
                   "fetched_utc": now, "score": mc.claim_score(c), **(extra or {})}
            if c.get("mechanism_key") in self.mech_keys:
                self.counts["duplicate_mechanisms"] += 1
                row["duplicate_of_key"] = c["mechanism_key"]
            else:
                self.mech_keys.add(str(c.get("mechanism_key")))
            self.new.append(row)
            self.ground_claims.append(row)
            n += 1
            self._provenance(row)
        return n

    def _provenance(self, row: dict[str, Any]) -> None:
        try:
            from libs.data.datahub import record_mined_source
            record_mined_source(repo=str(row.get("ground")), url=str(row.get("url")),
                                commit=f"{row.get('available_time')} sha256:"
                                       f"{str(row.get('source_hash'))[:16]}",
                                license_=str(row.get("license") or "WEB-PUBLIC"),
                                file=str(row.get("route")), mechanism=str(row["claim"])[:200],
                                code_copied=False, commercial_restriction=True,
                                path=PROVENANCE)
        except Exception:
            pass

    def dataset(self, page: str, *, ground: dict[str, Any], url: str, title: str) -> int:
        """A page that hands over DATA: its endpoints become a discovery row in the crawler's
        own shape (kind "dataset"), so `acquire_datasets` registers them, and a row in the
        datasets ledger, so the report can count what each region's forest yields."""
        eps = data_endpoints(page, url)
        if ground.get("kind") != "dataset" and not eps:
            return 0
        now = datetime.now(tz=UTC).isoformat(timespec="seconds")
        digest = hashlib.sha256((page or "").encode("utf-8")).hexdigest()[:20]
        row = {"source": SOURCE, "kind": "dataset", "title": title[:160] or url[:120], "url": url,
               "published": now, "symbols": [], "timeframes": [], "patterns": [],
               "confidence": round(min(0.95, 0.35 + 0.05 * min(len(eps), 10)), 2),
               "lang": ground.get("language"), "endpoints": eps[:200], "n_endpoints": len(eps),
               "vault_sha": digest, "host": urlparse(url).netloc,
               "ground": ground.get("name"), "region": ground.get("region"),
               "cluster": cluster_of(ground), "dataset_class": ground.get("dataset_class"),
               "available_time": now, "ingested_time": now, "source_hash": digest,
               "claims": [], "n_claims": 0}
        self.datasets.append(row)
        self.counts["dataset_pages"] += 1
        self.counts["dataset_endpoints"] += len(eps)
        self.follow(url, title, via=f"{SOURCE}:{ground.get('name')}:dataset")
        return len(eps)

    def follow(self, url: str, anchor: str, via: str) -> None:
        if url in self.seen_urls or not url.startswith(("http://", "https://")):
            return
        self.frontier.append((url, via, self.lang))
        self.seen_urls.add(url)

    # ---------------------------------------------------------------- routes per ground
    def _read_page(self, g: dict[str, Any], page: str, url: str, title: str, route: str) -> int:
        n = self.take(html_text(page), ground=g, url=url, title=title, route=route, page=page)
        self.dataset(page, ground=g, url=url, title=title)
        return n

    def ground_http(self, g: dict[str, Any], *, render_first: bool = False,
                    urls: list[str] | None = None, deep: bool = True) -> dict[str, Any]:
        urls = urls if urls is not None else [g.get("url"), *list(g.get("alt") or [])]
        got = claims = pages = 0
        for u in [str(x) for x in urls if x]:
            if self.over():
                break
            page = self.page(u)
            text = html_text(page)
            if (len(text) < MIN_PAGE_TEXT or render_first) and self._net_ok():
                rp = self.rendered(u)
                if rp:
                    page, text = rp, html_text(rp)
            if not text:
                continue
            got += 1
            claims += self._read_page(g, page, u, _title(page) or u, str(g.get("route", "http")))
            if not deep:
                continue
            host = urlparse(u).netloc
            n_deep = 0
            for href, anchor in html_links(page, u):
                if urlparse(href).netloc != host:
                    continue
                if self._worth(href, anchor):
                    self.follow(href, anchor, via=f"{SOURCE}:{g.get('name')}")
                    if n_deep < DEEP_LINKS_PER_GROUND and not self.over() and href not in urls:
                        sub = self.page(href, referer=u)
                        if len(html_text(sub)) >= MIN_PAGE_TEXT:
                            pages += 1
                            n_deep += 1
                            claims += self._read_page(g, sub, href, _title(sub) or anchor,
                                                      "http:deep")
                        time.sleep(1.0)
        return {"fetched": got, "deep_pages": pages, "claims": claims}

    def ground_search(self, g: dict[str, Any]) -> dict[str, Any]:
        site = str(g.get("site") or "")
        snippets_only = bool(g.get("snippets_only"))
        claims = pages = 0
        engines: dict[str, int] = {}
        errors: list[str] = []
        for q in g.get("queries") or []:
            if self.over() or not self._net_ok():
                break
            self.counts["queries"] += 1
            rows, engine, errs = engine_search(str(q), site, self.lang, str(g.get("market") or ""))
            self._note_net(bool(rows) or any("HTTPError" in e for e in errs))
            errors.extend(errs[:2])
            if not rows:
                continue
            engines[engine] = engines.get(engine, 0) + 1
            fetched = 0
            for r in rows:
                url = r.get("url") or ""
                text = f"{r.get('title', '')}. {r.get('snippet', '')}"
                claims += self.take(text, ground=g, url=url, title=r.get("title", ""),
                                    route=f"search:{engine}")
                self.follow(url, r.get("title", ""), via=f"{SOURCE}:{g.get('name')}")
                # SNIPPETS ONLY where the ground's robots.txt names this agent family (OP-041):
                # the engine's index is read, the site itself is never fetched.
                if not snippets_only and fetched < PAGE_FETCH_PER_QUERY and not self.over():
                    body = self.page(url)
                    if len(html_text(body)) >= MIN_PAGE_TEXT:
                        fetched += 1
                        pages += 1
                        claims += self._read_page(g, body, url, r.get("title", ""),
                                                  f"search:{engine}:page")
                    time.sleep(1.0)
            time.sleep(1.5)
        return {"queries": len(g.get("queries") or []), "engines": engines, "pages": pages,
                "claims": claims, "errors": errors[:4]}

    def ground_cn_api(self, g: dict[str, Any]) -> dict[str, Any]:
        from libs.data import cn_sources
        fn = cn_sources.juejin if g.get("route") == "juejin" else cn_sources.sogou_weixin
        return self._articles(g, fn, str(g.get("route")))

    def ground_foreign(self, g: dict[str, Any]) -> dict[str, Any]:
        """A libs.data.foreign_sources platform route (Qiita, Zenn, Hatena, Velog, Habr, vc.ru,
        smart-lab, Tinhte, Eksi) -- the same Article shape, one parser per language."""
        name = str(g.get("fn") or "")
        if name not in FOREIGN_FNS:
            return {"error": f"foreign fn {name!r} is not on the allowlist"}
        from libs.data import foreign_sources
        return self._articles(g, getattr(foreign_sources, name), f"foreign:{name}")

    def _articles(self, g: dict[str, Any], fn: Any, route: str) -> dict[str, Any]:
        claims = articles = 0
        errors: list[str] = []
        for q in g.get("queries") or []:
            if self.over() or not self._net_ok():
                break
            self.counts["queries"] += 1
            arts, err = fn(str(q))
            self._note_net(err is None or "HTTP" in str(err))
            if err:
                errors.append(str(err)[:100])
            for a in arts:
                articles += 1
                claims += self.take(a.searchable, ground=g, url=a.url, title=a.title, route=route)
                self.follow(a.url, a.title, via=f"{SOURCE}:{g.get('name')}")
            time.sleep(1.2)
        return {"queries": len(g.get("queries") or []), "articles": articles, "claims": claims,
                "errors": errors[:4]}

    def ground_papers(self, g: dict[str, Any]) -> dict[str, Any]:
        """arXiv / SSRN / OpenReview through libs.data.papers: mechanism claims from ABSTRACTS."""
        name = str(g.get("fn") or "arxiv")
        if name not in PAPER_FNS:
            return {"error": f"papers fn {name!r} is not on the allowlist"}
        from libs.data import papers
        claims = n_papers = 0
        errors: list[str] = []
        calls: list[Any] = []
        if name == "arxiv":
            for cat in g.get("categories") or ["q-fin.TR"]:
                for q in g.get("queries") or [""]:
                    calls.append(lambda q=q, cat=cat: papers.arxiv(str(q), category=str(cat)))
        elif name == "ssrn":
            for b in g.get("bindings") or [204]:
                calls.append(lambda b=b: papers.ssrn(int(b)))
        else:
            for q in g.get("queries") or []:
                calls.append(lambda q=q: papers.openreview(str(q)))
        for call in calls:
            if self.over() or not self._net_ok():
                break
            self.counts["queries"] += 1
            rows, err = call()
            self._note_net(err is None or "HTTP" in str(err))
            if err:
                errors.append(str(err)[:100])
            for p in rows:
                n_papers += 1
                claims += self.take(p.searchable, ground=g, url=p.url, title=p.title,
                                    route=f"papers:{name}", grade="PAPER",
                                    extra={"published_time": p.published or None})
                self.follow(p.url, p.title, via=f"{SOURCE}:{g.get('name')}")
            time.sleep(1.0)
        return {"queries": len(calls), "papers": n_papers, "claims": claims, "errors": errors[:4]}

    def ground_rss(self, g: dict[str, Any], feeds: list[str] | None = None) -> dict[str, Any]:
        """Any site that publishes a feed: items are claims, links are frontier, and the top
        items' pages are read when the ground asks (`fetch_items`)."""
        feeds = feeds if feeds is not None else [str(f) for f in (g.get("feeds") or [])]
        claims = items = pages = 0
        errors: list[str] = []
        for f in feeds:
            if self.over() or not self._net_ok():
                break
            xml = self.page(f)
            rows = parse_feed(xml)
            if not rows:
                errors.append(f"{f}: no items parsed ({len(xml)} bytes)")
                continue
            self.counts["feeds"] += 1
            fetched = 0
            for r in rows:
                items += 1
                text = f"{r['title']}. {r['summary']}"
                claims += self.take(text, ground=g, url=r["url"] or f, title=r["title"],
                                    route="rss", extra={"published_time": r["published"] or None})
                if r["url"]:
                    self.follow(r["url"], r["title"], via=f"{SOURCE}:{g.get('name')}")
                if r["url"] and fetched < int(g.get("fetch_items") or 0) and not self.over():
                    body = self.page(r["url"], referer=f)
                    if len(html_text(body)) >= MIN_PAGE_TEXT:
                        fetched += 1
                        pages += 1
                        claims += self._read_page(g, body, r["url"], r["title"], "rss:page")
                    time.sleep(1.0)
        return {"feeds": len(feeds), "items": items, "pages": pages, "claims": claims,
                "errors": errors[:4]}

    def ground_reddit(self, g: dict[str, Any]) -> dict[str, Any]:
        """Subreddits through their public feeds (the JSON API answers 403 to a datacenter;
        the feeds do not -- measured by side_channels/reddit_miner)."""
        feeds = []
        for sub in g.get("subs") or []:
            feeds.append(f"https://www.reddit.com/r/{sub}/top/.rss?t=month")
            feeds.append(f"https://www.reddit.com/r/{sub}/new/.rss")
        out = self.ground_rss(g, feeds)
        out["subs"] = len(g.get("subs") or [])
        return out

    def ground_wayback(self, g: dict[str, Any]) -> dict[str, Any]:
        """A ground that no longer exists (the Quantopian forum) through the Wayback Machine:
        nearest capture of the seed, then the capture's own links on the same original host."""
        original = str(g.get("url") or "")
        snap, err = wayback_snapshot(original, str(g.get("timestamp") or ""))
        self._note_net(err is None or "HTTP" in str(err))
        if err:
            return {"fetched": 0, "claims": 0, "errors": [err]}
        page = self.page(snap)
        if not html_text(page):
            return {"fetched": 0, "claims": 0, "errors": [f"empty capture {snap}"]}
        claims = self._read_page(g, page, snap, _title(page) or original, "wayback")
        host = urlparse(original).netloc
        pages = 0
        for href, anchor in html_links(page, snap):
            if host not in href or href == snap:
                continue
            self.follow(href, anchor, via=f"{SOURCE}:{g.get('name')}")
            if pages < DEEP_LINKS_PER_GROUND and not self.over():
                sub = self.page(href, referer=snap)
                if len(html_text(sub)) >= MIN_PAGE_TEXT:
                    pages += 1
                    claims += self._read_page(g, sub, href, _title(sub) or anchor, "wayback:deep")
                time.sleep(1.0)
        return {"fetched": 1, "snapshot": snap, "deep_pages": pages, "claims": claims}

    def ground_nitter(self, g: dict[str, Any]) -> dict[str, Any]:
        """Public tweets through whichever nitter mirror answers; never an API key, never a
        login. Mirrors die weekly, so every one is tried and the last reason is recorded."""
        mirrors = [str(m) for m in (g.get("mirrors") or [])]
        claims = tweets = 0
        errors: list[str] = []
        live: str | None = None
        for q in g.get("queries") or []:
            if self.over() or not self._net_ok():
                break
            self.counts["queries"] += 1
            rows: list[dict[str, str]] = []
            for m in ([live] if live else []) + [x for x in mirrors if x != live]:
                page = self.page(f"https://{m}/search?f=tweets&q={quote(str(q))}")
                rows = parse_nitter(page)
                if rows:
                    live = m
                    break
                errors.append(f"{m}: no tweets parsed")
            for r in rows:
                tweets += 1
                url = (f"https://{live}{r['url']}" if r.get("url")
                       else f"https://{live}/search?q={quote(str(q))}")
                claims += self.take(r["text"], ground=g, url=url, title=r["text"][:80],
                                    route="nitter", grade="COMMUNITY_POST")
            time.sleep(1.0)
        if not live and mirrors:
            errors.append("no nitter mirror reachable -- recorded, not routed around")
        return {"queries": len(g.get("queries") or []), "tweets": tweets, "mirror": live,
                "claims": claims, "errors": errors[-4:]}

    def ground_youtube(self, g: dict[str, Any]) -> dict[str, Any]:
        """The Bilibili route generalised: video METADATA through the search index (titles and
        descriptions state mechanisms too), then transcripts for the best few through the
        keyless mirror rotation -- currently dead from this box, and said so per video."""
        claims = 0
        videos: list[tuple[str, str, str]] = []
        errors: list[str] = []
        engines: dict[str, int] = {}
        for q in g.get("queries") or []:
            if self.over() or not self._net_ok():
                break
            self.counts["queries"] += 1
            rows, engine, errs = engine_search(str(q), "youtube.com", self.lang,
                                               str(g.get("market") or ""))
            self._note_net(bool(rows) or any("HTTPError" in e for e in errs))
            errors.extend(errs[:2])
            if rows:
                engines[engine] = engines.get(engine, 0) + 1
            for r in rows:
                url = r.get("url") or ""
                m = re.search(r"(?:v=|youtu\.be/|shorts/)([A-Za-z0-9_-]{11})", url)
                if not m:
                    continue
                videos.append((m.group(1), url, r.get("title", "")))
                claims += self.take(f"{r.get('title', '')}. {r.get('snippet', '')}", ground=g,
                                    url=url, title=r.get("title", ""), route="youtube:metadata",
                                    grade="VIDEO_METADATA")
                self.follow(url, r.get("title", ""), via=f"{SOURCE}:{g.get('name')}")
            time.sleep(1.5)
        n_tr = 0
        seen_ids: set[str] = set()
        for vid, url, title in videos:
            if vid in seen_ids or n_tr >= int(g.get("transcripts") or 0) or self.over():
                continue
            seen_ids.add(vid)
            text, err = youtube_transcript(vid, self.lang)
            if err:
                errors.append(f"{vid}: {err}"[:100])
                continue
            n_tr += 1
            self.counts["transcripts"] += 1
            claims += self.take(text, ground=g, url=url, title=title, route="youtube:transcript",
                                grade="VIDEO_TRANSCRIPT")
        return {"queries": len(g.get("queries") or []), "engines": engines, "videos": len(videos),
                "transcripts": n_tr, "claims": claims, "errors": errors[:4]}

    def ground_telegram(self, g: dict[str, Any]) -> dict[str, Any]:
        """Public channel previews at t.me/s/<channel>: server-rendered, no account, the last
        twenty posts. The Russian market conversation lives here more than on any forum."""
        urls = [f"https://t.me/s/{c}" for c in (g.get("channels") or [])]
        out = self.ground_http(g, urls=urls, deep=False)
        out["channels"] = len(urls)
        return out

    def ground_bilibili(self, g: dict[str, Any]) -> dict[str, Any]:
        from libs.data import bilibili
        try:
            from libs.research.video_triage import score_title
        except Exception:
            def score_title(text: str) -> tuple[float, list[str]]:  # type: ignore[misc]
                return 0.0, []
        claims = 0
        videos: list[Any] = []
        errors: list[str] = []
        for q in g.get("queries") or []:
            if self.over() or not self._net_ok():
                break
            self.counts["queries"] += 1
            vids, err = bilibili.search(str(q))
            self._note_net(err is None or "code=" in str(err) or "SOFT" in str(err))
            if err:
                errors.append(str(err)[:100])
                if "SOFT REFUSAL" in str(err):
                    break
            for v in vids:
                claims += self.take(v.searchable, ground=g, url=v.url, title=v.title,
                                    route="bilibili:metadata")
                self.follow(v.url, v.title, via=f"{SOURCE}:{g.get('name')}")
            videos.extend(vids)
            time.sleep(0.5)
        ranked = sorted({v.bvid: v for v in videos}.values(),
                        key=lambda v: -score_title(v.searchable)[0])
        n_tr = 0
        tr_err: list[str] = []
        for v in ranked[: int(g.get("transcripts") or 0)]:
            if self.over() or not self._net_ok():
                break
            text, err = bilibili_transcript(v.bvid)
            if err:
                tr_err.append(f"{v.bvid}: {err}")
                continue
            n_tr += 1
            self.counts["transcripts"] += 1
            claims += self.take(text, ground=g, url=v.url, title=v.title,
                                route="bilibili:transcript", grade="VIDEO_TRANSCRIPT")
            time.sleep(0.5)
        return {"queries": len(g.get("queries") or []), "videos": len(videos),
                "transcripts": n_tr, "claims": claims, "errors": (errors + tr_err)[:4]}

    def ground_gitee(self, g: dict[str, Any]) -> dict[str, Any]:
        try:
            from libs.data.datahub import copy_allowed
        except Exception:
            def copy_allowed(lic: str) -> bool:                  # type: ignore[misc]
                return False
        claims = repos = 0
        errors: list[str] = []
        seen_repo: set[str] = set()
        for q in g.get("queries") or []:
            if self.over() or not self._net_ok():
                break
            self.counts["queries"] += 1
            rows, err = gitee_search(str(q))
            self._note_net(err is None or "HTTPError" in str(err))
            if err:
                errors.append(err[:100])
                continue
            for r in rows:
                full = str(r.get("full") or "")
                if not full or full in seen_repo or self.over():
                    continue
                seen_repo.add(full)
                repos += 1
                readme = gitee_readme(full)
                text = f"{r.get('description', '')}\n{readme}"
                claims += self.take(text, ground=g, url=str(r.get("url")), title=full,
                                    route="gitee:readme", grade="CODE",
                                    extra={"license": r.get("license"), "stars": r.get("stars"),
                                           "copy_allowed": copy_allowed(str(r.get("license")))})
                self.follow(str(r.get("url")), full, via=f"{SOURCE}:{g.get('name')}")
                time.sleep(0.5)
        return {"queries": len(g.get("queries") or []), "repos": repos, "claims": claims,
                "errors": errors[:4]}

    @staticmethod
    def _worth(url: str, anchor: str) -> bool:
        try:
            import world_frontier as wf
            return bool(wf.worth_following(url, anchor))
        except Exception:
            return bool(mc.is_cjk(anchor) or "trad" in url.lower())

    def work(self, g: dict[str, Any], share_s: float | None = None) -> None:
        name, route = str(g.get("name")), str(g.get("route") or "http")
        row: dict[str, Any] = {"ground": name, "route": route, "kind": g.get("kind"),
                               "region": g.get("region"), "cluster": cluster_of(g),
                               "language": g.get("language")}
        if route == "unreachable":
            self.status.append({**row, "status": "UNREACHABLE", "why": g.get("why")})
            return
        if not self.fetch:
            self.status.append({**row, "status": "SKIPPED", "why": "--no-fetch"})
            return
        if not self._net_ok():
            self.status.append({**row, "status": "NO_NETWORK",
                                "why": "three straight transport failures on this box"})
            return
        self.ground, self.ground_claims = g, []
        seen_before = self.counts["claims_seen_before"]
        t0 = time.monotonic()
        self.g_end = min(self.started + self.budget_s, t0 + (share_s or self.budget_s))
        try:
            if route == "http":
                out = self.ground_http(g)
            elif route == "render":
                out = self.ground_http(g, render_first=True)
            elif route == "search":
                out = self.ground_search(g)
            elif route in ("juejin", "sogou"):
                out = self.ground_cn_api(g)
            elif route == "bilibili":
                out = self.ground_bilibili(g)
            elif route == "gitee":
                out = self.ground_gitee(g)
            elif route == "foreign":
                out = self.ground_foreign(g)
            elif route == "papers":
                out = self.ground_papers(g)
            elif route == "rss":
                out = self.ground_rss(g)
            elif route == "reddit":
                out = self.ground_reddit(g)
            elif route == "wayback":
                out = self.ground_wayback(g)
            elif route == "nitter":
                out = self.ground_nitter(g)
            elif route == "youtube":
                out = self.ground_youtube(g)
            elif route == "telegram":
                out = self.ground_telegram(g)
            else:
                out = {"error": f"unknown route {route}"}
        except Exception as exc:
            out = {"error": f"{type(exc).__name__}: {str(exc)[:120]}"}
        n_claims = int(out.get("claims") or 0)
        # REACHED means the route answered: pages, results, articles, papers, feeds -- or claims
        # this run had already banked from another ground (a repeat is a measurement, not a
        # blocked route).
        reached = any(out.get(k) for k in ("fetched", "engines", "videos", "repos", "papers",
                                            "items", "tweets", "channels", "feeds", "articles")
                      ) or self.counts["claims_seen_before"] > seen_before
        status = "PRODUCTIVE" if n_claims else ("REACHED_NO_CLAIMS" if reached else "BLOCKED")
        classes: dict[str, int] = {}
        for c in self.ground_claims:
            k = str(c.get("mechanism_class"))
            classes[k] = classes.get(k, 0) + 1
        self.status.append({**row, "status": status, **out,
                            "elapsed_s": round(time.monotonic() - t0, 1), "classes": classes,
                            # ORTHOGONALITY: a ground that yields only momentum says so.
                            "momentum_only": bool(classes) and set(classes) <= {"momentum"},
                            "datasets": sum(1 for d in self.datasets if d.get("ground") == name)})


def _feed_frontier(urls: list[tuple[str, str, str]]) -> int:
    if not urls:
        return 0
    try:
        import world_frontier as wf
        sources = wf.load()
        added = 0
        # EVERY URL A MECHANISM QUERY SURFACED IS GROUND. The vocabulary filter the crawler
        # applies to anchors would reject a Thai or Hebrew article URL that carries no Latin
        # trading word; the query that found it is the evidence it is worth a fetch, and the
        # frontier's yield ranking charges it forever if that turns out wrong. The language
        # travels with it, so the crawler reads the page in the right script.
        for url, via, lang in urls:
            if url.startswith(("http://", "https://")):
                added += int(wf.add(sources, url, via=via, lang=lang or "en"))
        wf.save(sources, note=f"{SOURCE} {datetime.now(tz=UTC):%Y-%m-%dT%H:%MZ}")
        return added
    except Exception:
        return 0


def _write_discoveries(rows: list[dict[str, Any]]) -> Path | None:
    """Dataset pages in the crawler's discovery-row shape, where the acquirer already looks."""
    if not rows:
        return None
    try:
        WORLD.mkdir(parents=True, exist_ok=True)
        out = WORLD / f"discoveries_deepforest_{datetime.now(tz=UTC):%Y%m%d_%H%M}.json"
        out.write_text(json.dumps(rows, indent=1, ensure_ascii=False, default=str), "utf-8")
        return out
    except OSError:
        return None


def _task(row: dict[str, Any], tellings: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    inst = row.get("instruments") or {}
    perf = row.get("claimed_performance") or {}
    prov = [{"url": t.get("url"), "ground": t.get("ground"), "route": t.get("route"),
             "available_time": t.get("available_time") or t.get("fetched_utc"),
             "published_time": t.get("published_time"), "source_hash": t.get("source_hash"),
             "lang": t.get("lang")} for t in (tellings or [row])][:20]
    desc = (f"CLAIM ({row.get('lang')}, {row.get('evidence_grade')}, channel="
            f"{row.get('channel') or 'direct'}, class={row.get('mechanism_class') or 'other'}): "
            f"\"{row['claim']}\". "
            f"MT5 analogues: {inst.get('analogues') or 'none'}"
            + (f"; indirect targets: {inst.get('indirect')}" if inst.get("indirect") else "")
            + (f"; transfer-only: {inst.get('transfer_only')}" if inst.get("transfer_only") else "")
            + (f"; channels: {inst.get('channels')}" if inst.get("channels") else "")
            + (" (instrument inherited from the document)" if row.get("instrument_from_context")
               else "")
            + (f". Story's own numbers: {perf}" if perf else "")
            + (f". Told {len(prov)} times across grounds" if len(prov) > 1 else "")
            + f". Provenance: {row.get('ground')} ({row.get('region')}) via {row.get('route')} at "
              f"{row.get('available_time') or row.get('fetched_utc')}, {row.get('url')}. Extract "
              "the exact mechanism as an MT5 family and parameters if the text states one; "
              "otherwise reject with why. Concept only -- never copy code; stated performance "
              "is not evidence.")
    src = str(row.get("source") or source_of(str(row.get("cluster") or "cn")))
    return {"source": src, "kind": KIND,
            "title": f"{row.get('ground')}: {row['claim'][:90]}",
            "description": desc, "url": row.get("url"),
            "symbols": list(inst.get("analogues") or inst.get("indirect") or []),
            "mechanism_tags": list(row.get("quantities") or []), "lang": row.get("lang"),
            "region": row.get("region"), "cluster": row.get("cluster"),
            "channel": row.get("channel") or "direct",
            "mechanism_class": row.get("mechanism_class") or "other",
            "mechanism_key": row.get("mechanism_key") or row.get("claim_hash"),
            "evidence_grade": row.get("evidence_grade"), "claimed_performance": perf,
            "transfer_only": inst.get("transfer_only") or [], "claim_hash": row.get("claim_hash"),
            "provenance": prov, "n_tellings": len(prov),
            "event_time": row.get("event_time"), "published_time": row.get("published_time"),
            "available_time": row.get("available_time") or row.get("fetched_utc"),
            "score": row.get("score"), "status": None,
            "consumer": "deepening_worker (story_mechanism) -> miner_candidate_compiler "
                        "-> gauntlet"}


def build_tasks(rows: list[dict[str, Any]], *, decided: set[str] | None = None,
                cap: int = MAX_TASKS) -> list[dict[str, Any]]:
    """Every undecided MECHANISM, best first: rows sharing a mechanism key fold into one task
    carrying every telling as provenance. Decided ones (the worker's ledger) are not re-asked."""
    try:
        from research.deepening_worker import task_id
    except Exception:
        def task_id(t: dict[str, Any]) -> str:                   # type: ignore[misc]
            return hashlib.sha256(f"{t.get('source')}|{t.get('url')}|{t.get('title')}"
                                  .encode()).hexdigest()[:16]
    groups: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        key = str(r.get("mechanism_key") or r.get("claim_hash") or "")
        if key:
            groups.setdefault(key, []).append(r)
    tasks = []
    for tellings in groups.values():
        best = max(tellings, key=lambda r: (float(r.get("score") or 0.0),
                                            str(r.get("fetched_utc"))))
        tasks.append(_task(best, tellings))
    if decided:
        tasks = [t for t in tasks if task_id(t) not in decided]
    tasks.sort(key=lambda t: (-float(t.get("score") or 0.0), -int(t.get("n_tellings") or 1)))
    return tasks[:cap]


#: Field names of every ledger row this miner writes, ON THE REPORT so the health/ROI organ
#: that reads them never has to reverse-engineer a shape from samples.
LEDGER_SCHEMA: dict[str, list[str]] = {
    "claims (data/deep_forest_claims.jsonl)": [
        "claim", "lang", "quantities", "direction", "horizon", "instruments{analogues,mentioned,"
        "transfer_only,indirect,channels}", "instrument_from_context", "channel",
        "mechanism_class", "mechanism_key", "duplicate_of_key?", "event_time",
        "claimed_performance", "claim_hash", "kind", "ground", "ground_kind", "region",
        "language", "cluster", "source", "route", "url", "title", "evidence_grade",
        "published_time", "available_time", "ingested_time", "revision", "source_hash",
        "fetched_utc", "score", "license?", "stars?", "copy_allowed?"],
    "datasets (data/deep_forest_datasets.jsonl; intelligence/world/discoveries_deepforest_*)": [
        "source", "kind=dataset", "title", "url", "published", "symbols", "timeframes",
        "patterns", "confidence", "lang", "endpoints", "n_endpoints", "vault_sha", "host",
        "ground", "region", "cluster", "dataset_class", "available_time", "ingested_time",
        "source_hash", "claims", "n_claims"],
    "deepening task (data/hypotheses/miner_deepening_queue.json)": [
        "source", "kind=story_mechanism", "title", "description", "url", "symbols",
        "mechanism_tags", "lang", "region", "cluster", "channel", "mechanism_class",
        "mechanism_key", "evidence_grade", "claimed_performance", "transfer_only", "claim_hash",
        "provenance[{url,ground,route,available_time,published_time,source_hash,lang}]",
        "n_tellings", "event_time", "published_time", "available_time", "score", "status",
        "consumer"],
    "mined_sources.jsonl (libs.data.datahub.record_mined_source)": [
        "at", "repo=ground", "url", "commit='<available_time> sha256:<source_hash16>'", "license",
        "file=route", "mechanism", "code_copied", "attribution_required",
        "commercial_restriction", "policy"],
}


def run(budget_s: float = 900.0, fetch: bool = True, only: list[str] | None = None,
        write: bool = True, region: str | None = None) -> dict[str, Any]:
    cfg = _load_sources()
    grounds = list(cfg.get("grounds") or [])
    r = _Run(budget_s, fetch, set(only or []) or None, region)
    cursor = int(r.seen.get("cursor") or 0) if not (only or region) else 0
    order = schedule(grounds, cursor, only=r.only, region=region)
    total_w = sum(float(g.get("weight") or 1.0) for g in order) or 1.0
    worked = 0
    for g in order:
        if r.over() or time.monotonic() - r.started > budget_s:
            r.status.append({"ground": g.get("name"), "region": g.get("region"),
                             "cluster": cluster_of(g), "status": "BUDGET_EXHAUSTED",
                             "why": "the cursor resumes here next run"})
            continue
        share = max(MIN_GROUND_S, budget_s * float(g.get("weight") or 1.0) / total_w * SPREAD)
        r.work(g, share_s=share)
        worked += 1
    if write and r.new:
        CLAIMS.parent.mkdir(parents=True, exist_ok=True)
        with CLAIMS.open("a", encoding="utf-8") as fh:
            for row in r.new:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    if write and r.datasets:
        with DATASETS.open("a", encoding="utf-8") as fh:
            for row in r.datasets:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    discoveries = _write_discoveries(r.datasets) if write else None
    frontier_added = _feed_frontier(r.frontier) if write else 0
    all_rows = _claims_rows() if write else list(r.new)
    try:
        from research.deepening_worker import worked_ids
        decided = worked_ids()
    except Exception:
        decided = set()
    tasks = build_tasks(all_rows, decided=decided)
    if write:
        r.seen["claims"] = list(r.seen_claims)
        r.seen["urls"] = list(r.seen_urls)
        if not (only or region) and order:
            r.seen["cursor"] = (cursor + worked) % len(order)
        r.seen["runs"] = int(r.seen.get("runs") or 0) + 1
        _save_seen(r.seen)
        if tasks:
            try:
                from research.regime_coverage import _merge_into_queue
                by_src: dict[str, list[dict[str, Any]]] = {}
                for t in tasks:
                    by_src.setdefault(str(t.get("source")), []).append(t)
                # ONE SOURCE PER REGION CLUSTER: each replaces only its own rows.
                for src, ts in by_src.items():
                    _merge_into_queue(ts, source=src)
            except Exception:
                pass
    grounds_status = [s for s in r.status if "ground" in s]
    by_region: dict[str, dict[str, Any]] = {}
    for g in grounds:
        reg = str(g.get("region") or "?")
        b = by_region.setdefault(reg, {"cluster": cluster_of(g), "grounds": 0, "worked": 0,
                                       "productive": 0, "blocked": 0, "claims": 0, "datasets": 0,
                                       "story": 0, "dataset": 0, "macro": 0, "momentum_only": 0,
                                       "languages": []})
        b["grounds"] += 1
        kind = "dataset" if g.get("kind") == "dataset" else ("macro" if g.get("kind") == "macro"
                                                              else "story")
        b[kind] += 1
        if g.get("language") and g.get("language") not in b["languages"]:
            b["languages"].append(g.get("language"))
    for s in grounds_status:
        b = by_region.get(str(s.get("region") or "?"))
        if not b:
            continue
        if s.get("status") not in ("BUDGET_EXHAUSTED", "SKIPPED"):
            b["worked"] += 1
        if s.get("status") == "PRODUCTIVE":
            b["productive"] += 1
        if s.get("status") in ("BLOCKED", "NO_NETWORK", "UNREACHABLE"):
            b["blocked"] += 1
        b["claims"] += int(s.get("claims") or 0)
        b["datasets"] += int(s.get("datasets") or 0)
        b["momentum_only"] += int(bool(s.get("momentum_only")))
    doc = {"generated_utc": datetime.now(tz=UTC).isoformat(timespec="seconds"),
           "budget_s": budget_s, "elapsed_s": round(time.monotonic() - r.started, 1),
           "network": r.network, "fetch": fetch, "region_filter": region,
           "grounds_total": len(grounds), "grounds_scheduled": len(order),
           "grounds_worked": worked, "cursor_next": r.seen.get("cursor"),
           "grounds": grounds_status,
           "productive": sum(1 for s in grounds_status if s.get("status") == "PRODUCTIVE"),
           "blocked": [s.get("ground") for s in grounds_status
                       if s.get("status") in ("BLOCKED", "NO_NETWORK", "UNREACHABLE")],
           "momentum_only_grounds": [s.get("ground") for s in grounds_status
                                     if s.get("momentum_only")],
           "by_region": by_region,
           "languages": sorted({str(g.get("language")) for g in grounds if g.get("language")}),
           "counts": r.counts, "claims_new": len(r.new), "claims_total": len(all_rows),
           "claims_by_channel": {ch: sum(1 for c in r.new if c.get("channel") == ch)
                                 for ch in ("direct", "indirect")},
           "claims_by_class": {cls: sum(1 for c in r.new if c.get("mechanism_class") == cls)
                               for cls in (*mc.MECHANISM_CLASSES, "other")},
           "datasets_new": len(r.datasets),
           "discoveries_file": str(discoveries) if discoveries else None,
           "tasks_queued": len(tasks), "tasks_by_source": {
               src: sum(1 for t in tasks if t.get("source") == src)
               for src in sorted({str(t.get("source")) for t in tasks})},
           "frontier_added": frontier_added,
           "fetch_notes": [s for s in r.status if "url" in s][:40],
           "top_claims": [{k: t.get(k) for k in ("title", "symbols", "channel", "mechanism_class",
                                                 "n_tellings", "evidence_grade",
                                                 "claimed_performance", "score", "url")}
                          for t in tasks[:12]],
           "ledger_schema": LEDGER_SCHEMA,
           "loop": ("Discover (search/platform/feed/archive routes, every region, rotated by "
                    "cursor) -> Extract (claims in 26 languages, direct/indirect channel, "
                    "mechanism class) -> dedupe on mechanism key -> queue story_mechanism per "
                    "region-cluster source -> worker Reimplement -> compiler -> gauntlet -> "
                    "allocator; URLs feed the world crawler frontier; dataset pages feed "
                    "acquire_datasets")}
    if write:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(doc, indent=1, ensure_ascii=False, default=str), "utf-8")
    return doc


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--budget-s", type=float, default=900.0)
    ap.add_argument("--no-fetch", action="store_true", help="rebuild the queue from the ledger")
    ap.add_argument("--only", action="append", default=None,
                    help="ground name, route, region or cluster to work (repeatable)")
    ap.add_argument("--region", default=None, help="work one region (or cluster) this pass")
    a = ap.parse_args()
    d = run(budget_s=a.budget_s, fetch=not a.no_fetch, only=a.only, region=a.region)
    print(f"DEEP FOREST  network={d['network']} grounds={d['grounds_worked']}/{d['grounds_total']} "
          f"productive={d['productive']} claims_new={d['claims_new']} total={d['claims_total']} "
          f"datasets={d['datasets_new']} tasks={d['tasks_queued']} "
          f"frontier+={d['frontier_added']} counts={d['counts']}")
    for reg, b in sorted(d["by_region"].items()):
        print(f"  region {reg:14s} grounds={b['grounds']:3d} worked={b['worked']:3d} "
              f"productive={b['productive']:3d} claims={b['claims']:4d} datasets={b['datasets']}")
    for g in d["grounds"]:
        if g.get("status") == "BUDGET_EXHAUSTED":
            continue
        print(f"  {g.get('ground')!s:34s} {g.get('route')!s:9s} {g.get('status')} "
              f"claims={g.get('claims', 0)} {g.get('errors') or g.get('why') or ''}")
    print(f"written: {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
