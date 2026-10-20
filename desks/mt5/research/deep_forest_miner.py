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
grounds a link walk never reaches, platform APIs where they exist (Qiita, Zenn, Habr, arXiv,
Gitee, Bilibili ...), RSS where a site publishes one, the Wayback Machine for archives that are
gone, public Telegram previews and subreddit feeds (IDEAS_ONLY in libs/data/terms_fence.py),
never a nitter mirror (METHOD_BLOCKED: a login-wall workaround; X's official API is the
permitted route), a rendered fetch where a shell hides the listing -- and then hands every URL it finds to the crawler's
frontier, so the forest it opens keeps being walked after this run ends.

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

EVERY REGISTERED GROUND IS MINED (LAWS 5e, 2026-09-23). This miner used to hold two discovery
brakes of its own: a `snippets_only` flag that read the search index and REFUSED to fetch the
site, and a `route: unreachable` that recorded a ground and never reached for it -- both keyed on
robots, terms or a paywall. Both are deleted. A robots note, a terms note or a paywall is now a
ROUTING LABEL (`terms_note`) carried on every claim the ground produces: it says what the desk may
REDISTRIBUTE, never what it may read and test. The open surface of a paywalled domain is mined and
the wall itself is never bypassed -- that is hard-boundary act 2 and it is the only thing here
that still says no. Machine-translated and forum ground is FIRST CLASS.

WHY 467 OF 502 GROUNDS WERE STILL NAMED_ONLY (measured 2026-09-30, fixed here).
* THE LEG KILLED THE MINER BEFORE IT WROTE ANYTHING. The hourly leg ran this file with its
  900 s default budget under the cycle's 720 s default cap (`deep_forest_miner` had no entry in
  `LEG_BUDGET_SEC`), and every ledger -- claims, seen, cursor, frontier -- was written only at
  the END of a run. Most hours were SIGKILLed at 720 s with nothing written, so the next hour
  started from the same cursor and re-hit the same head of the list. Now: the leg carries a cap
  above the organ's own budget and exports it (`QUANT_LEG_BUDGET_S`), the miner self-stops
  inside it, and every ground's claims, datasets and frontier outcome are CHECKPOINTED the
  moment that ground finishes, so a kill costs at most the grounds in flight.
* ONE GROUND AT A TIME, MOSTLY WAITING. Grounds are now worked by `WORKERS` threads; politeness
  is per HOST (`libs.data.polite_fetch.GATE`), so a search engine shared by 177 grounds sees
  the same rate it saw sequentially while distinct hosts proceed in parallel. Every fetch has a
  hard timeout and bounded retries on 429/5xx, TLS uses certifi on top of the system store, and
  GBK / Shift_JIS pages are decoded by their declared charset instead of as UTF-8 soup.
* LEAST-RECENTLY-ATTEMPTED FIRST. Inside each frontier bucket the scheduler orders by the
  vector's last attempt, oldest first, so a budget always reaches the untried tail.
* THE FOREST LEGS NOW MINE. `forest_runner`'s practitioner role runs this miner over ITS
  forest's grounds with the leg's idle seconds (`--mine-grounds`), so eleven regional legs that
  opened no socket each work their own slice of the 502 in parallel.
"""
from __future__ import annotations

import argparse
import base64
import contextlib
import copy
import hashlib
import html as _html
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urljoin, urlparse

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_DESK / "side_channels"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from libs.data import polite_fetch as pf  # noqa: E402
from libs.data import terms_fence as _tf  # noqa: E402
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
#: Grounds worked at once. Per-HOST spacing (polite_fetch.GATE) keeps every host's rate where
#: the sequential miner had it; this only stops the run waiting on one host at a time.
WORKERS = 8
#: Seconds kept back from the cycle's cap for the end-of-run writes (report, queue, frontier).
WRITE_RESERVE_S = 90.0
#: The fetch-rate ledger `research/alt_data_yield.py` reads (one line per run).
RUNS = _DESK / "data" / "alt_fetch_runs.jsonl"
LEG = "deep_forest_miner"
#: Cross-process locks live where the desk keeps its job locks (gitignored, per machine).
LOCKS = _DESK / "data" / ".job_locks"
#: Per-vector attempts / successes / rows / last error, beside the frontier file.
VECTOR_STATS_NAME = "deep_forest_vector_stats.json"
#: THE DESK'S HONEST AGENT for every route (audit PASS5_feb86fa30 SF; auditor ruling 2026-10-14:
#: no browser impersonation). ONE constant: `polite_fetch.DESK_UA`, which `_UA` and `INDEX_UA`
#: both send, so robots.txt groups and a site's logs see one name for this desk.
FOREST_UA = pf.DESK_UA
_UA = {"User-Agent": FOREST_UA,
       "Accept": ("text/html,application/xhtml+xml,application/json,application/xml;q=0.9,"
                  "*/*;q=0.8")}
GRADE = {"competition": "COMPETITION_RECORD", "interview": "INTERVIEW",
         "community": "COMMUNITY_POST", "forum": "COMMUNITY_POST", "qa": "COMMUNITY_POST",
         "social": "COMMUNITY_POST", "blog": "COMMUNITY_POST", "column": "COMMUNITY_POST",
         "code": "CODE", "notebook": "CODE", "video": "VIDEO_METADATA", "academic": "PAPER",
         "research": "PAPER", "macro": "OFFICIAL", "dataset": "DATASET",
         "archive": "COMMUNITY_POST"}

#: Every route a ground may declare. A ground naming anything else is a configuration error the
#: grounds-file test catches before a run does. "unreachable" is a LEGACY value kept so an old
#: grounds file still loads: since LAWS 5e it is no longer a refusal -- `work()` re-routes such a
#: ground to search (or http) and mines it, because "unreachable" was almost always robots, terms
#: or a paywall wearing a measurement's clothes.
ROUTES: frozenset[str] = frozenset({
    "http", "render", "search", "juejin", "sogou", "bilibili", "gitee", "foreign", "papers",
    "rss", "reddit", "wayback", "nitter", "youtube", "telegram", "unreachable",
})
#: libs.data.foreign_sources functions a ground may name. `coinpan` (a crypto forum) is fenced
#: out by the standing order -- the ONLY exclusion here, and it is the MT5 universe mandate, not
#: an access brake. `dcinside` and `note` ride the search route because that is where their
#: content is indexed, not because their robots.txt says anything (LAWS 5e: it is a label).
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


def terms_label(g: dict[str, Any]) -> str:
    """THE ROUTING LABEL A GROUND CARRIES, never a reason to skip it (LAWS 5e, 2026-09-23).

    A robots note, a declared terms note, a paywall or a legacy `snippets_only` / `unreachable`
    flag lands here as free text and rides along on every claim the ground produces. It says what
    the desk may REDISTRIBUTE and how the row is provenanced; it has nothing to say about whether
    the desk may read, extract or test the page, and no caller may read it as a veto.
    """
    bits: list[str] = []
    note = str(g.get("terms_note") or "").strip()
    if note:
        bits.append(note)
    if g.get("snippets_only"):
        bits.append("registered snippets_only (robots or paywall): MINED IN FULL, "
                    "redistribution withheld")
    if str(g.get("route") or "") == "unreachable":
        bits.append("registered route=unreachable: re-routed and mined, the note kept as "
                    "provenance")
    if g.get("machine_use_allowed") is False:
        bits.append("ground declares machine_use_allowed=false: mined, redistribution withheld")
    why = str(g.get("why") or "")
    if bits and why:
        bits.append(why[:200])
    return "; ".join(bits)


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
def _answered(err: str) -> bool:
    """True when an error string is the SITE's answer (an HTTP status, a hold, a robots rule)
    rather than a transport failure -- only the latter counts against the network."""
    return any(t in err for t in ("HTTP", "NEEDS_KEY", "METHOD_BLOCKED", "ROBOTS_"))


class Refused(OSError):
    """A fetch the site or its robots.txt refused (NEEDS_KEY / METHOD_BLOCKED / ROBOTS_*). A
    recorded answer: the caller never renders, mirrors or otherwise routes around it."""

    def __init__(self, url: str, verdict: str, error: str = "", status: int | None = None) -> None:
        super().__init__(f"{verdict}: {error or verdict} for url: {url}")
        self.url, self.verdict = url, verdict
        #: The HTTP status that carried the refusal (401/403/429), or None (robots, a challenge).
        self.status = status


def fenced_ground(g: dict[str, Any]) -> str | None:
    """The HELD source a ground belongs to (METHOD_BLOCKED, or NEEDS_KEY until its key exists;
    libs/data/terms_fence.py), or None. IDEAS_ONLY grounds (Reddit, Telegram, X pages) are not
    held: they are mined for ideas like any other ground."""
    return _tf.fenced_ground(g)


def _http(url: str, *, timeout: float = 20.0, referer: str = "", lang: str = "") -> str:
    """One polite GET (honest UA, robots.txt per origin, per-host spacing, certifi-backed TLS,
    charset-aware decoding). retries=0: a 429 is a hard stop that holds the site, never a retry
    (audit PASS5_feb86fa30 SF). Raises `Refused` on a refusal (401/403/429, robots),
    `urllib.error.HTTPError` on another HTTP failure and `OSError` on a transport one -- the
    shapes `_Run.page` and the route helpers expect."""
    hdr = {**_UA, "Accept-Language": accept_language(lang)}
    if referer:
        hdr["Referer"] = referer
    r = pf.get(url, headers=hdr, timeout=timeout, retries=0, leg=LEG, max_bytes=2_000_000)
    if r.ok:
        return r.text
    verdict = str(getattr(r, "verdict", "") or "")
    if verdict:
        raise Refused(url, verdict, r.error, status=getattr(r, "status", None))
    if r.status is not None and r.status >= 400:
        raise urllib.error.HTTPError(url, r.status, r.error or f"HTTP {r.status}",
                                     None, None)  # type: ignore[arg-type]
    raise OSError(r.error or "fetch failed")


@contextlib.contextmanager
def _xlock(name: str, timeout_s: float = 30.0) -> Iterator[bool]:
    """Cross-process AND cross-thread exclusive lock on `LOCKS/<name>.lock`. Several forest legs
    run this miner at once over one frontier, one seen-set and one claims ledger; a read-modify-
    write without this loses the other process's attempts. Yields whether it was held -- a lock
    that cannot be taken in time degrades to an unlocked write rather than a lost ground."""
    from libs.research import artifact_chain as _ac
    with _THREAD_LOCKS.setdefault(name, threading.Lock()):
        locks = SEEN.with_name(LOCKS.name)          # beside the ledgers it guards
        with contextlib.suppress(OSError):
            locks.mkdir(parents=True, exist_ok=True)
        with _ac._locked(locks / f"{name}", timeout_s=timeout_s) as held:
            yield bool(held)


_THREAD_LOCKS: dict[str, threading.Lock] = {}


def _env_budget_cap() -> float | None:
    """The cycle cap the leg was actually given this hour (hourly_cycle exports it), or None."""
    try:
        cap = float(os.environ.get("QUANT_LEG_BUDGET_S") or 0)
    except ValueError:
        return None
    return cap if cap > 0 else None


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


# ------------------------------------------------------------------- non-Bing site-index route
# GAP 3 (2026-10-14). Bing answers this miner with an anti-bot shell on most `search` grounds,
# and the frontier records those vectors BLOCKED. The block is NOT routed around: no rotated
# agent, no header games, no CAPTCHA work. A different METHOD is used instead, reading only what
# the ground or a public index publishes for machines: the ground's own sitemap (named in its own
# robots.txt) first, else the Common Crawl URL index (the CDX server, metadata only). Every page
# then read from the site must be allowed by that site's robots.txt for every agent ("*"); a
# disallowed page is counted, never fetched.
#: Common Crawl's licence to the Service (index included): "CC grants you a limited,
#: non-assignable, non-transferable, non-sublicensable, non-exclusive, limited license to access
#: and use the Service subject to the terms and conditions of these ToU" (commoncrawl.org/
#: terms-of-use, read 2026-10-14). The index answers URL lists only; no crawled page is copied.
CC_TERMS = {"terms_url": "https://commoncrawl.org/terms-of-use",
            "terms_quote": ("CC grants you a limited, non-assignable, non-transferable, "
                            "non-sublicensable, non-exclusive, limited license to access and "
                            "use the Service subject to the terms and conditions of these ToU"),
            "restrictions_quote": ("interfering with or disrupting the Service and/or the "
                                   "servers or networks connected to the Service"),
            "verdict": "confirmed (URL index only; one request per ground per pass)",
            "checked_at": "2026-10-14"}
#: An honest agent for the index and robots reads (never a browser string).
INDEX_UA = FOREST_UA
#: the product token the index route reads robots.txt groups for (RFC 9309 s2.2.1)
INDEX_ROBOTS_TOKEN = pf.DESK_UA_PRODUCT
INDEX_URLS_PER_GROUND = 80
_STATIC_EXT = (".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".css", ".js", ".ico",
               ".woff", ".woff2", ".ttf", ".mp4", ".mp3", ".zip", ".gz", ".xml", ".json")


def _cc_index() -> str:
    try:
        from research.index_discovery import CC_INDEX
        return str(CC_INDEX)
    except Exception:
        return "CC-MAIN-2026-30"


#: The headers of EVERY request on the site-index route -- robots, sitemap, CDX and the pages it
#: lists. A rerouted page is never fetched with the browser string (`_UA`): that would be the
#: route-around the block's record forbids (audit 2026-10-14 MF1).
INDEX_HEADERS = {"User-Agent": INDEX_UA, "Accept": "*/*"}


#: THE HARD STOP (audit 2026-10-14 MF-C): the first of these from a site holds that site --
#: its registrable domain -- for the rest of the run, and the hold is persisted as the ground's
#: frontier vector BLOCKED with an ACCESS_REFUSED blocker (no second register). That row is
#: NOT on hunt_frontier's 10-day retry clock: it holds until a PERSON releases it (auditor ruling
#: 2026-10-14; the release is named at `hunt_frontier.PERSON_HELD_PREFIX`). A held site gets
#: no further request on any route, and never a Common Crawl CDX listing in its place: an
#: index of the pages the site just refused is a route-around.
ACCESS_STOP: frozenset[int] = frozenset({401, 403, 429})
#: The frontier blocker prefix a persisted site hold carries (read back at the next run's start).
ACCESS_REFUSED = "ACCESS_REFUSED"
_SLD = frozenset({"co", "com", "net", "org", "gov", "ac", "edu", "or", "ne", "go", "gob",
                  "gouv", "nic", "mil", "ltd", "plc"})


def _is_ip(host: str) -> bool:
    import ipaddress
    try:
        ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        return False
    return True


#: A Wayback capture names the page it archived: web.archive.org/web/<stamp>/<original>.
_WAYBACK_ORIG = re.compile(r"^https?://web\.archive\.org/web/[^/]+/(.+)$", re.I)


def wayback_original(url: str) -> str:
    """The archived page a Wayback capture URL stands for ('' when `url` is not a capture)."""
    m = _WAYBACK_ORIG.match(str(url or ""))
    if not m:
        return ""
    orig = m.group(1)
    return orig if "://" in orig else "http://" + orig


def registrable_domain(url_or_host: str) -> str:
    """The site a hold covers: the last two labels, or three under a two-letter country code
    with a generic second level (co.uk, com.cn, co.jp, com.hk ...). Every subdomain and the www.
    twin of a refusing site therefore share its hold."""
    s = str(url_or_host or "").strip().lower()
    host = (urlparse(s).hostname or "") if "//" in s else s.split("/")[0].split(":")[0]
    if _is_ip(host):
        return host.strip("[]")           # an IP host is held whole, never by its last octets
    labels = [x for x in host.strip(".").split(".") if x]
    if len(labels) >= 3 and len(labels[-1]) == 2 and labels[-2] in _SLD:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


class SiteRefused(OSError):
    """A 401/403/429 on the index route: the caller holds the site and stops."""

    def __init__(self, url: str, status: int) -> None:
        super().__init__(f"HTTP {status} (site held: {registrable_domain(url)})")
        self.url, self.status = url, int(status)


def _index_get(url: str) -> str:
    """One polite GET with the honest index agent. Raises SiteRefused on a 401/403/429 and
    OSError on any other failure. retries=0: a 429 is a stop, never a retry (MF-C)."""
    r = pf.get(url, headers=dict(INDEX_HEADERS), timeout=25.0, retries=0, leg=LEG,
               max_bytes=4_000_000)
    if r.ok:
        return r.text
    if r.status in ACCESS_STOP:
        raise SiteRefused(url, int(r.status or 0))
    raise OSError(r.error or f"HTTP {r.status}")


def robots_parser(robots_txt: str) -> Any:
    """robots.txt text -> THE ONE parser, `polite_fetch.RobotsRules` (RFC 9309: the desk's
    product-token group, else `*`; longest match). No second robots reader lives here."""
    return pf.parse_robots(robots_txt)


def sitemap_locs(xml: str) -> tuple[list[str], list[str]]:
    """(page urls, child sitemap urls) from a sitemap or a sitemap index."""
    locs = [_html.unescape(m.strip()) for m in re.findall(r"<loc>\s*([^<]+?)\s*</loc>", xml)]
    if "<sitemapindex" in xml:
        return [], locs
    return locs, []


def article_like(url: str, site: str) -> bool:
    p = urlparse(url)
    host = p.netloc.lower().split(":")[0]
    bare = site.lower().removeprefix("www.")
    if not (host == bare or host.endswith("." + bare)):
        return False
    path = p.path or "/"
    return path not in ("", "/") and not path.lower().endswith(_STATIC_EXT)


def rank_by_queries(urls: list[str], queries: list[str]) -> list[str]:
    """URLs whose path or query shares a token with the ground's queries first (Latin tokens of
    three or more letters; a CJK query rarely appears in a URL, so order then stays as listed)."""
    toks = {t for q in queries for t in re.findall(r"[a-z0-9]{3,}", q.lower())}

    def score(u: str) -> int:
        low = unquote(u).lower()
        return -sum(1 for t in toks if t in low)
    return sorted(dict.fromkeys(urls), key=score)


#: Extra hosts (beyond the ground's own) whose robots.txt one pass may read for listed pages.
INDEX_EXTRA_HOSTS = 4
_DEFAULT_PORT = {"http": 80, "https": 443}


def robots_origin(url: str) -> str:
    """The origin whose robots.txt governs `url`: scheme://host[:port], the default port dropped
    (RFC 9309: a robots.txt applies to its own scheme, host and port only). So a page on
    ex.com:8443 is judged by https://ex.com:8443/robots.txt, never by the one on port 443."""
    p = urlparse(url)
    scheme = (p.scheme or "https").lower()
    host = (p.hostname or "").lower()
    try:
        port = p.port
    except ValueError:
        port = None
    if port is not None and port != _DEFAULT_PORT.get(scheme):
        return f"{scheme}://{host}:{port}"
    return f"{scheme}://{host}"


def robots_allows(url: str, *, get: Any = None,
                  cache: dict[str, Any] | None = None) -> bool:
    """True only when the robots.txt of `url`'s OWN origin was read and allows the desk's agent
    (its product-token group, else "*"). An unread robots.txt is not a permission."""
    get = get or _index_get
    cache = cache if cache is not None else {}
    origin = robots_origin(url)
    if origin not in cache:
        try:
            txt = get(f"{origin}/robots.txt")
            cache[origin] = robots_parser(txt) if txt else None
        except Exception:
            cache[origin] = None
    rp = cache[origin]
    return bool(rp is not None and rp.can_fetch(INDEX_ROBOTS_TOKEN, url))


class IndexRedirectHandler(_tf.FencedRedirectHandler):
    """The fence's redirect handler (held sources and login walls still refused), plus: a redirect
    to ANOTHER robots origin is followed only when that origin's robots.txt was read and allows
    the target; otherwise the fetch STOPS at the 30x (raised as that HTTPError, never followed)."""

    def __init__(self, allows: Any) -> None:
        super().__init__()
        self.allows = allows

    def redirect_request(self, req: urllib.request.Request, fp: Any, code: int, msg: str,
                         headers: Any, newurl: str) -> urllib.request.Request | None:
        newurl = urljoin(str(req.full_url), newurl)
        if robots_origin(newurl) != robots_origin(str(req.full_url)) and not self.allows(newurl):
            with contextlib.suppress(Exception):
                fp.read()
                fp.close()
            raise urllib.error.HTTPError(newurl, int(code), f"cross-origin redirect stopped: "
                                         f"robots.txt of {robots_origin(newurl)} unread or "
                                         "disallowing", headers, None)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def index_opener(allows: Any) -> Any:
    """A `polite_fetch.get` opener for the index route: THE ONE FETCH DOOR's checks (a held
    source or login wall refused before any request), with IndexRedirectHandler for redirects."""
    def open_(req: urllib.request.Request, timeout: float | None = None,
              context: Any = None) -> Any:
        _tf.check_request(req.full_url, dict(req.header_items()))
        if _tf.login_wall(req.full_url):
            raise _tf.TermsFenced("login_wall", req.full_url)
        hs: list[Any] = [IndexRedirectHandler(allows), _tf.TermsGuardProcessor()]
        if context is not None:
            hs.append(urllib.request.HTTPSHandler(context=context))
        op = urllib.request.build_opener(*hs)
        return op.open(req) if timeout is None else op.open(req, timeout=timeout)
    return open_


def site_index_urls(site: str, *, get: Any = None, holds: Any = None) -> dict[str, Any]:
    """The ground's own sitemap(s), else the Common Crawl CDX listing for `site/*`; each URL
    filtered to article-like pages on that site and to what ITS OWN HOST's robots.txt allows for
    "*". A page on another host (a subdomain, the bare or www. twin) is judged by that exact
    host's robots.txt, read here; an unread one fetches nothing (audit 2026-10-14 MF2).
    Returns {"route", "urls", "robots_disallowed", "robots_unread", "errors"}; never raises.

    `holds` (a `SiteHolds`, the run's) is the hard stop: a held site is never requested, the
    first 401/403/429 from any site holds it, and once the ground's own site is held the listing
    STOPS -- route "held", no sitemap child, no CDX fallback, no page (audit 2026-10-14 MF-C)."""
    raw_get = get or _index_get
    holds = holds if holds is not None else SiteHolds()
    site_dom = registrable_domain(site)

    def fetch(u: str) -> str:
        if holds.held(u):
            raise SiteRefused(u, int(holds.held(u).get("status") or 0))
        try:
            return str(raw_get(u))
        except SiteRefused as exc:
            holds.hold(u, exc.status)
            raise
    errors: list[str] = []
    robots_txt = ""
    site_origin = robots_origin(f"https://{site.lower().split('/')[0]}/")
    try:
        robots_txt = fetch(f"{site_origin}/robots.txt")
    except Exception as exc:
        errors.append(f"robots: {str(exc)[:80]}")
    if holds.held(site_dom):
        return _held_listing(site_dom, holds, errors)
    rp = robots_parser(robots_txt) if robots_txt else None
    rps: dict[str, Any] = {site_origin: rp}

    def host_rp(origin: str) -> Any:
        """By ORIGIN (scheme, host, port): a subdomain, a twin host or another port each needs its
        own robots.txt read."""
        if origin not in rps:
            if len(rps) > INDEX_EXTRA_HOSTS:
                rps[origin] = None                     # over the read budget: unread, unfetched
            else:
                try:
                    txt = fetch(f"{origin}/robots.txt")
                    rps[origin] = robots_parser(txt) if txt else None
                except Exception as exc:
                    errors.append(f"robots {origin}: {str(exc)[:60]}")
                    rps[origin] = None
        return rps[origin]
    urls: list[str] = []
    route = ""
    maps = [ln.split(":", 1)[1].strip() for ln in robots_txt.splitlines()
            if ln.lower().startswith("sitemap:")][:2]
    for sm in maps:
        try:
            pages, kids = sitemap_locs(fetch(sm))
            for kid in kids[:2]:
                pages += sitemap_locs(fetch(kid))[0]
            urls += pages
        except Exception as exc:
            errors.append(f"sitemap: {str(exc)[:80]}")
        if holds.held(site_dom):
            # A REFUSED SITEMAP IS A STOP, NOT A CUE FOR THE CDX: no fallback, no page.
            return _held_listing(site_dom, holds, errors)
    if urls:
        route = "sitemap"
    else:
        q = quote(f"{site}/*", safe="")
        cdx = (f"https://index.commoncrawl.org/{_cc_index()}-index?url={q}&output=json"
               f"&limit={INDEX_URLS_PER_GROUND * 2}&filter=status:200&fl=url")
        try:
            for ln in fetch(cdx).splitlines():
                with contextlib.suppress(ValueError):
                    u = str((json.loads(ln) or {}).get("url") or "")
                    if u:
                        urls.append(u)
            route = "cdx" if urls else ""
        except Exception as exc:
            errors.append(f"cdx: {str(exc)[:80]}")
    keep = [u for u in dict.fromkeys(urls) if article_like(u, site)]
    # EACH PAGE BY ITS OWN HOST'S robots.txt. An unread robots.txt is not a permission, so a
    # page whose exact host's file was not read is never fetched (counted as robots_unread).
    allowed: list[str] = []
    disallowed = unread = 0
    for u in keep:
        hrp = host_rp(robots_origin(u))
        if hrp is None:
            unread += 1
        elif hrp.can_fetch(INDEX_ROBOTS_TOKEN, u):
            allowed.append(u)
        else:
            disallowed += 1
    if unread:
        errors.append(f"robots.txt unread for {unread} listed page(s): none of them fetched")
    return {"route": route or "none", "urls": allowed[:INDEX_URLS_PER_GROUND],
            "listed": len(keep), "robots_disallowed": disallowed, "robots_unread": unread,
            "errors": errors[:4]}


def _held_listing(site_dom: str, holds: Any, errors: list[str]) -> dict[str, Any]:
    h = holds.held(site_dom) or {}
    errors.append(f"site held: HTTP {h.get('status')} from {site_dom}; no further request, "
                  "no CDX fallback")
    return {"route": "held", "urls": [], "listed": 0, "robots_disallowed": 0,
            "robots_unread": 0, "errors": errors[:4], "held": {site_dom: h}}


class SiteHolds:
    """The run's site holds (registrable domain -> {status, url, at, persisted}), shared by
    every fork of a run. Not a register: a hold lives for the run, and is persisted only as the
    holding ground's frontier vector (BLOCKED, blocker ACCESS_REFUSED ...), from which every
    later run re-seeds it until a person releases the row (never by the retry clock)."""

    def __init__(self) -> None:
        self.sites: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()

    def held(self, url_or_host: str) -> dict[str, Any] | None:
        dom = registrable_domain(url_or_host)
        with self._lock:
            return self.sites.get(dom) if dom else None

    def hold(self, url: str, status: int, *, persisted: bool = False,
             ground: str = "") -> dict[str, Any]:
        dom = registrable_domain(url)
        with self._lock:
            if dom not in self.sites:
                self.sites[dom] = {"status": int(status), "url": url[:200], "ground": ground,
                                   "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
                                   "persisted": persisted}
            return self.sites[dom]


def access_hold_missed_growth(site: str, hold: dict[str, Any]) -> dict[str, Any]:
    """GROWTH GOVERNANCE: the missed-growth line a site hold carries (delta E[log W] UNMEASURED,
    never zero, with its cause)."""
    return {"source": site, "kind": "access_hold", "status": ACCESS_REFUSED,
            "http": hold.get("status"), "delta_elogw": "UNMEASURED",
            "unblock": (f"a PERSON releases it: delete the ground's vector from {FRONTIER_NAME} "
                        "(or rewrite its blocker without the ACCESS_REFUSED prefix); never "
                        f"lapsed by the {_BLOCKED_RETRY_D()}d hunt_frontier retry clock"),
            "cause": (f"HTTP {hold.get('status')} from {site}: the site refused this agent, so "
                      "the ground is not read until a person releases the hold; what it would "
                      "have yielded is UNMEASURED")}


def _BLOCKED_RETRY_D() -> int:
    try:
        from libs.research.hunt_frontier import BLOCKED_RETRY_D
        return int(BLOCKED_RETRY_D)
    except Exception:
        return 10


#: The frontier vector a SITE hold is persisted under (one register: hunt_frontier's file). It
#: names the REFUSING registrable domain, so the next run holds the site that refused -- never
#: the ground's own site when a third site refused it (audit PASS5_feb86fa30 MF2).
SITE_VECTOR_PREFIX = "site:"
#: The blocker a hold carries when the frontier file itself is damaged: fail CLOSED.
FRONTIER_UNREADABLE = "FRONTIER_UNREADABLE"


def _refusing_domain(blocker: str) -> str:
    m = re.search(r"\bfrom ([A-Za-z0-9.\[\]:-]+\.[A-Za-z0-9\]]+)", str(blocker or ""))
    return registrable_domain(m.group(1)) if m else ""


def persisted_site_holds(grounds: list[dict[str, Any]], frontier_state: Any,
                         now: datetime | None = None) -> dict[str, dict[str, Any]]:
    """Every site the frontier holds, keyed by the REFUSING registrable domain -- WHATEVER ITS
    AGE. A 401/403/429 waits for a person (auditor ruling 2026-10-14): hunt_frontier's 10-day
    BLOCKED retry never lifts it, and neither does an unparseable stamp (no clock is read).

    Read from every BLOCKED vector whose blocker starts ACCESS_REFUSED: a `site:<domain>` vector
    holds that domain; a ground vector holds the domain its blocker names ("HTTP nnn from
    <site>"), or -- fail closed, only when the blocker names none -- the ground's own site.

    `frontier_state=None` means the frontier file is DAMAGED: every ground's site is held
    (FRONTIER_UNREADABLE) until a person repairs or removes the file; holds are never silently
    lost with it. THE RELEASE: a person deletes the hold's vector (`site:<domain>`, and the
    ground's own ACCESS_REFUSED vector where one names it) from deep_forest_frontier.json --
    see `hunt_frontier.PERSON_HELD_PREFIX`."""
    del now                                # deliberately unused: no clock decides a hold
    out: dict[str, dict[str, Any]] = {}
    by_name = {str(g.get("name") or ""): g for g in grounds}
    if frontier_state is None:
        for g in grounds:
            dom = registrable_domain(str(g.get("site") or g.get("url") or ""))
            if dom and dom not in out:
                out[dom] = {"ground": str(g.get("name") or ""), "last_attempt": "",
                            "blocker": (f"{ACCESS_REFUSED}: {FRONTIER_UNREADABLE}: the frontier "
                                        "file is damaged, so every hold it carried is kept")}
        return out
    vectors = getattr(frontier_state, "vectors", {}) or {}
    for name, v in vectors.items():
        blocker = str(getattr(v, "blocker", "") or "")
        if str(getattr(v, "outcome", "")) != "BLOCKED" or not blocker.startswith(ACCESS_REFUSED):
            continue
        name = str(name)
        if name.startswith(SITE_VECTOR_PREFIX):
            dom = registrable_domain(name[len(SITE_VECTOR_PREFIX):])
        else:
            dom = _refusing_domain(blocker)
            if not dom and name in by_name:
                g = by_name[name]
                dom = registrable_domain(str(g.get("site") or g.get("url") or ""))
        if dom and dom not in out:
            out[dom] = {"ground": name, "blocker": blocker[:200],
                        "last_attempt": str(getattr(v, "last_attempt", "") or "")}
    return out


def person_held_grounds(grounds: list[dict[str, Any]],
                        frontier_state: Any) -> dict[str, dict[str, Any]]:
    """Ground name -> hold, FAIL CLOSED: a ground whose own ACCESS_REFUSED vector names no
    refusing domain and whose row names no site has nothing to key a site hold on, so the
    ground itself is held by name. A refusal that names its domain holds that domain only
    (`persisted_site_holds`), never the ground. Released only by a person, never by age."""
    vectors = getattr(frontier_state, "vectors", {}) or {}
    out: dict[str, dict[str, Any]] = {}
    for g in grounds:
        name = str(g.get("name") or "")
        v = vectors.get(name)
        blocker = str(getattr(v, "blocker", "") or "")
        if (v is None or str(getattr(v, "outcome", "")) != "BLOCKED"
                or not blocker.startswith(ACCESS_REFUSED) or _refusing_domain(blocker)
                or registrable_domain(str(g.get("site") or g.get("url") or ""))):
            continue
        code = re.search(r"HTTP (\d{3})", blocker)
        out[name] = {"status": int(code.group(1)) if code else 0, "site": "",
                     "blocker": blocker[:200]}
    return out


def seed_persisted_holds(run: Any, grounds: list[dict[str, Any]], frontier_state: Any) -> None:
    """Seed a run's holds from the frontier: held until a PERSON releases the row, whatever its
    age (auditor ruling 2026-10-14). A damaged frontier (`None`) holds every ground."""
    for dom, h in persisted_site_holds(grounds, frontier_state).items():
        code = re.search(r"HTTP (\d{3})", h["blocker"])
        run.holds.hold(f"https://{dom}/", int(code.group(1)) if code else 0, persisted=True,
                       ground=h["ground"])
    run.held_grounds.update(person_held_grounds(grounds, frontier_state))
    if frontier_state is None:
        run.frontier_damaged = True


def frontier_damaged(path: Path) -> bool:
    """True when the frontier file EXISTS but cannot be read as a vector document. A missing
    file is a fresh box (nothing held yet); a damaged one may have carried holds, so the run
    fails closed and the file is never overwritten until a person repairs or removes it."""
    try:
        raw = path.read_text("utf-8")
    except FileNotFoundError:
        return False
    except OSError:
        return True
    try:
        blob = json.loads(raw)
    except ValueError:
        return True
    return not isinstance(blob, dict) or not isinstance(blob.get("vectors", {}), dict)


def bing_reroute_census(grounds: list[dict[str, Any]],
                        vectors: dict[str, Any] | None = None) -> dict[str, Any]:
    """How many Bing-dependent grounds (route `search`, including legacy `unreachable` re-routed
    to search) now have a non-Bing route, and which stay BLOCKED with cause. With the frontier's
    vectors, the same count over the vectors recorded BLOCKED."""
    dep = [g for g in grounds if str(g.get("route") or "http") in ("search", "youtube")
           or (str(g.get("route")) == "unreachable" and g.get("site"))]
    rerouted = sorted(str(g.get("name")) for g in dep
                      if g.get("site") and str(g.get("route")) != "youtube")
    no_site = sorted(str(g.get("name")) for g in dep
                     if not g.get("site") and str(g.get("route")) != "youtube")
    tube = sorted(str(g.get("name")) for g in dep if str(g.get("route")) == "youtube")
    out: dict[str, Any] = {
        "bing_dependent_grounds": len(dep), "rerouted": len(rerouted),
        "route": "site sitemap (robots.txt Sitemap:) else Common Crawl CDX, robots-gated pages",
        "still_blocked": {**dict.fromkeys(no_site,
                                          "no site to index: a search engine was its only "
                                          "address"),
                          **dict.fromkeys(tube, "youtube.com is found through the engine; its "
                                          "own index is the YouTube Data API, whose key is not "
                                          "on the box, and its site is not crawled around "
                                          "that")},
        "terms": CC_TERMS,
        "live_yield": "UNMEASURED until the box runs the deep_forest leg"}
    if vectors is not None:
        by_name = {str(g.get("name")): g for g in grounds}
        blocked = [n for n, v in vectors.items()
                   if isinstance(v, dict) and v.get("outcome") == "BLOCKED"]
        bing = [n for n in blocked if by_name.get(n) in dep]
        out["frontier_blocked_vectors"] = len(blocked)
        out["frontier_blocked_bing_dependent"] = len(bing)
        out["frontier_blocked_rerouted"] = sum(1 for n in bing if by_name[n].get("site"))
        out["frontier_blocked_other_cause"] = {
            n: "not a search ground: its own route failed (not Bing)"
            for n in blocked if n not in bing}
    return out


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
    """MERGE, never overwrite: several forest legs mine at once, and a plain write would drop
    the claims another process banked since this one loaded -- which re-mints them next run."""
    SEEN.parent.mkdir(parents=True, exist_ok=True)
    with _xlock("deep_forest_seen"):
        disk = _load_seen()
        claims = set(disk.get("claims") or []) | set(seen.get("claims") or [])
        urls = set(disk.get("urls") or []) | set(seen.get("urls") or [])
        _atomic_text(SEEN, json.dumps({"claims": sorted(claims)[-50_000:],
                                       "urls": sorted(urls)[-50_000:],
                                       "cursor": int(seen.get("cursor") or 0),
                                       "runs": int(seen.get("runs") or 0),
                                       "updated_utc": datetime.now(tz=UTC).isoformat()}))


def _atomic_text(path: Path, text: str) -> None:
    """Write-then-replace, Windows-safe (a held or read-only destination is retried)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    tmp.write_text(text, "utf-8")
    for i in range(6):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            with contextlib.suppress(OSError):
                os.chmod(path, 0o666)
            time.sleep(0.2 * (i + 1))
    try:
        path.write_text(text, "utf-8")
    finally:
        with contextlib.suppress(OSError):
            tmp.unlink()


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
def _fair_order(grounds: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Round-robin clusters while keeping measured ROI weight inside each cluster."""
    by_cluster: dict[str, list[dict[str, Any]]] = {}
    for g in grounds:
        by_cluster.setdefault(cluster_of(g), []).append(g)
    for lst in by_cluster.values():
        lst.sort(key=lambda g: -float(g.get("weight") or 1.0))
    clusters = sorted(by_cluster)
    out: list[dict[str, Any]] = []
    for i in range(max((len(v) for v in by_cluster.values()), default=0)):
        out.extend(by_cluster[c][i] for c in clusters if i < len(by_cluster[c]))
    return out


#: THE DAILY FLOOR (2026-09-30): a ground not attempted inside this many hours is scheduled ahead
#: of every ground that was, whatever its cooldown says. The 45-day covered cooldown and the
#: 10-day blocked retry decide the order of FRONTIER work; they may never let a registered ground
#: go a day unattempted while the pass still has budget (`research/forest_attempts.py`).
DAILY_FLOOR_H = 24.0
N_BUCKETS = 6


def _frontier_bucket(g: dict[str, Any], frontier_state: Any | None,
                     now: datetime, retired: set[str] | frozenset[str] = frozenset()) -> int:
    """0 NAMED_ONLY, 1 retry-due BLOCKED, 2 cooldown-due covered, 3 not attempted in 24h (the
    daily floor), 4 attempted in 24h, 5 LOW_EV_RETIRED and not reopen-due (still scheduled --
    last, never dropped)."""
    name = str(g.get("name") or "")
    vector = getattr(frontier_state, "vectors", {}).get(name) \
        if frontier_state is not None else None
    if vector is None or str(getattr(vector, "outcome", "NAMED_ONLY")) == "NAMED_ONLY":
        return 0
    if name in retired:
        return 5
    if str(getattr(vector, "outcome", "")) == "BLOCKED" and vector.huntable(now)[0]:
        return 1
    if str(getattr(vector, "outcome", "")) != "BLOCKED" and vector.huntable(now)[0]:
        return 2
    try:
        last = datetime.fromisoformat(str(getattr(vector, "last_attempt", "") or ""))
        last = last if last.tzinfo else last.replace(tzinfo=UTC)
        recent = (now - last).total_seconds() < DAILY_FLOOR_H * 3600.0
    except ValueError:
        recent = False                    # an unreadable stamp is overdue, never exempt
    return 4 if recent else 3


def schedule(grounds: list[dict[str, Any]], cursor: int = 0, *, only: set[str] | None = None,
             region: str | None = None, frontier_state: Any | None = None,
             retired: set[str] | frozenset[str] = frozenset()) -> list[dict[str, Any]]:
    """The order a run works grounds in: round-robin across clusters (heaviest weight first
    inside each), rotated by the cursor the previous run left, so every forest gets its turn
    across runs and no region is worked only because it sorts first in a file."""
    picked = []
    for g in grounds:
        # A HELD ground (METHOD_BLOCKED or NEEDS_KEY; libs/data/terms_fence.py) is never
        # scheduled: it is registered, reported by name under `terms_fenced`, and not fetched.
        if fenced_ground(g):
            continue
        if region and str(g.get("region")) != region and cluster_of(g) != region:
            continue
        if only and not ({str(g.get("name")), str(g.get("route")), str(g.get("region")),
                          cluster_of(g)} & only):
            continue
        picked.append(g)
    # FRONTIER BEFORE COVERAGE.  The coverage ledger already distinguishes ground that was only
    # named, a transiently blocked attempt, covered ground whose cooldown expired, and genuinely
    # picked-over ground.  Until now this scheduler ignored that information, so the 467
    # NAMED_ONLY grounds competed equally with places the desk had already exhausted.  Preserve
    # regional fairness and the ROI weights, but rotate each frontier bucket independently and
    # place uncovered/retry-due ground first.  A mapping row can therefore never masquerade as a
    # completed hunt or starve behind already-covered ground.
    buckets: list[list[dict[str, Any]]] = [[] for _ in range(N_BUCKETS)]
    now = datetime.now(tz=UTC)
    for g in picked:
        buckets[_frontier_bucket(g, frontier_state, now, retired)].append(g)
    # LEAST-RECENTLY-ATTEMPTED FIRST (2026-09-30). Inside a bucket the fair, cursor-rotated
    # order is then sorted -- stably -- by the vector's last attempt, oldest first. Never-tried
    # ground has no attempt and sorts first; ground tried an hour ago sorts behind ground tried a
    # week ago. The cursor alone could not do this: it only advanced when a run finished, and a
    # run the cycle killed left it where it was, so every hour re-hit the same head.
    out: list[dict[str, Any]] = []
    for bucket in buckets:
        ordered = _fair_order(bucket)
        if ordered:
            start = cursor % len(ordered)
            rotated = ordered[start:] + ordered[:start]
            out.extend(sorted(rotated, key=lambda g: _last_attempt(g, frontier_state)))
    return out


def _last_attempt(g: dict[str, Any], frontier_state: Any | None) -> str:
    """The vector's last attempt stamp ('' = never), the least-recently-attempted sort key."""
    if frontier_state is None:
        return ""
    v = getattr(frontier_state, "vectors", {}).get(str(g.get("name") or ""))
    return str(getattr(v, "last_attempt", "") or "") if v is not None else ""


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
        #: URLs a site or its robots.txt refused this run: never rendered or mirrored around.
        self.refused: set[str] = set()
        self.frontier: list[tuple[str, str, str]] = []
        self.counts = {"queries": 0, "pages": 0, "transcripts": 0, "rendered": 0,
                       "dropped_venue": 0, "dropped_unmappable": 0, "duplicate_mechanisms": 0,
                       "claims_seen_before": 0, "net_failures": 0, "dataset_pages": 0,
                       "dataset_endpoints": 0, "feeds": 0, "urls_new": 0}
        #: Shared by every fork of this run: the network verdict and its failure streak.
        self._shared: dict[str, Any] = {"network": None, "fails": 0}
        #: The run's site holds (MF-C), shared by every fork like the network verdict.
        self.holds = SiteHolds()
        #: Grounds whose OWN frontier vector is a persisted ACCESS_REFUSED hold (ground name ->
        #: hold). Such a ground is never requested, even when its row names no site to key the
        #: hold on, until a person releases the row (`hunt_frontier.PERSON_HELD_PREFIX`).
        self.held_grounds: dict[str, dict[str, Any]] = {}
        #: The frontier file was damaged at the run's start: FAIL CLOSED, no ground is fetched
        #: (its holds may be in there) until a person repairs or removes the file.
        self.frontier_damaged = False
        self._lock = threading.RLock()
        self.render_used = 0
        self.ground: dict[str, Any] = {}
        self.ground_claims: list[dict[str, Any]] = []
        self.mech_keys: set[str] = set()
        #: The site holds THIS ground raised (domain names), for its status and frontier row.
        self.ground_holds: list[str] = []

    @property
    def network(self) -> bool | None:
        return self._shared["network"]

    @network.setter
    def network(self, value: bool | None) -> None:
        self._shared["network"] = value

    def fork(self) -> _Run:
        """A worker's view of this run: its OWN ground, deadline and result lists, the run's
        SHARED dedup sets, universe, network verdict and lock. One fork works one ground; the
        parent merges it back, so the per-ground state the routes keep on `self` can never be
        crossed between threads."""
        f = copy.copy(self)
        f.new, f.datasets, f.status, f.frontier = [], [], [], []
        f.counts = dict.fromkeys(self.counts, 0)
        f.ground, f.ground_claims = {}, []
        f.render_used = 0
        f.ground_holds = []
        return f

    def merge(self, f: _Run) -> None:
        with self._lock:
            self.new.extend(f.new)
            self.datasets.extend(f.datasets)
            self.status.extend(f.status)
            self.frontier.extend(self.unheld(f.frontier))
            for k, v in f.counts.items():
                if k != "net_failures":
                    self.counts[k] = self.counts.get(k, 0) + v
            self.counts["net_failures"] = self._shared["fails"]
            self.render_used += f.render_used

    def over(self) -> bool:
        return time.monotonic() > min(self.g_end, self.started + self.budget_s)

    def _net_ok(self) -> bool:
        """After three straight transport failures the box has no network; stop trying."""
        return self.fetch and self.network is not False

    def _note_net(self, ok: bool) -> None:
        with self._lock:
            sh = self._shared
            if ok:
                sh["network"] = True
                sh["fails"] = 0
                self.counts["net_failures"] = 0
            else:
                sh["fails"] += 1
                self.counts["net_failures"] += 1
                if sh["network"] is None and sh["fails"] >= 3:
                    sh["network"] = False

    @property
    def lang(self) -> str:
        return str(self.ground.get("language") or "en")

    def page(self, url: str, referer: str = "") -> str:
        # Held before the network check and before any request: a method refusal is recorded by
        # name and is NOT a transport failure (it must never count toward the three-strike
        # NO_NETWORK verdict, nor be retried).
        fenced = _tf.platform_of_url(url)
        if fenced:
            self.status.append({"url": url, **_tf.refusal(fenced)})
            return ""
        if self._site_held(url):
            return ""
        if not self._net_ok():
            return ""
        try:
            body = _http(url, referer=referer, lang=self.lang)
            self._note_net(True)
            self.counts["pages"] += 1
            return body
        except Refused as exc:
            self._note_net(True)
            self.refused.add(url)
            self.status.append({"url": url, "refused": exc.verdict})
            # THE HARD STOP REACHES THE RUN'S SITE HOLDS: polite_fetch's HostAccess has already
            # held the site on disk (no retry, no other route); a 401/403/429 also holds it in
            # this run's SiteHolds, so every route, the frontier and the persisted
            # `site:<domain>` vector see it -- exactly as the index route's refusals do.
            if exc.status in ACCESS_STOP:
                self._hold_site(url, int(exc.status or 0))
            return ""
        except urllib.error.HTTPError as exc:
            self._note_net(True)
            self.status.append({"url": url, "http": exc.code})
            if exc.code in ACCESS_STOP:
                self._hold_site(url, exc.code)
            return ""
        except Exception as exc:
            self._note_net(False)
            self.status.append({"url": url, "error": f"{type(exc).__name__}: {str(exc)[:80]}"})
            return ""

    def index_page(self, url: str) -> str:
        """A page the site-index route listed, fetched with INDEX_HEADERS (the honest agent):
        the same fence, network and status bookkeeping as `page`, never the browser `_UA`."""
        fenced = _tf.platform_of_url(url)
        if fenced:
            self.status.append({"url": url, **_tf.refusal(fenced)})
            return ""
        if self._site_held(url):
            return ""
        if not self._net_ok():
            return ""
        # a redirect to another robots origin is followed only on that origin's own robots.txt,
        # and never into a held site (whose robots.txt is not requested either)
        cache = self.__dict__.setdefault("_index_robots", {})

        def allows(u: str) -> bool:
            return not self.holds.held(u) and robots_allows(u, cache=cache, get=self._index_get)
        # retries=0: a 429 is a hard stop, never retried (audit 2026-10-14 MF-C)
        r = pf.get(url, headers=dict(INDEX_HEADERS), timeout=20.0, retries=0, leg=LEG,
                   max_bytes=2_000_000, opener=index_opener(allows))
        if r.ok:
            self._note_net(True)
            self.counts["pages"] += 1
            return str(r.text)
        if r.status is not None and r.status >= 400:
            self._note_net(True)
            self.status.append({"url": url, "http": r.status})
            if r.status in ACCESS_STOP:
                self._hold_site(url, int(r.status))
        else:
            self._note_net(False)
            self.status.append({"url": url, "error": str(r.error or "fetch failed")[:80]})
        return ""

    def held_url(self, url: str) -> dict[str, Any] | None:
        """The hold covering `url`: its own site's, or -- for a Wayback capture -- the hold of
        the site it archived (an archive of a refusing site is a route-around)."""
        h = self.holds.held(url)
        orig = wayback_original(url)
        return h or (self.holds.held(orig) if orig else None)

    def _site_held(self, url: str) -> bool:
        """True (and recorded) when `url` is on a site this run holds: no request is made."""
        h = self.held_url(url)
        if h:
            self.status.append({"url": url,
                                "site_held": registrable_domain(wayback_original(url) or url)
                                if not self.holds.held(url) else registrable_domain(url),
                                "http": h.get("status")})
        return bool(h)

    def unheld(self, rows: list[tuple[str, str, str]]) -> list[tuple[str, str, str]]:
        """Frontier rows minus every URL on a held site (a hold placed AFTER a URL was followed
        still keeps it from world_crawler)."""
        return [r for r in rows if not self.held_url(r[0])]

    def _hold_site(self, url: str, status: int) -> None:
        self.holds.hold(url, status, ground=str(self.ground.get("name") or ""))
        dom = registrable_domain(url)
        if dom not in self.ground_holds:
            self.ground_holds.append(dom)
        # URLs of the now-held site this ground already followed never reach world_crawler
        # (audit PASS5_feb86fa30 MF3): purged here, and filtered again at merge and emission.
        self.frontier[:] = self.unheld(self.frontier)

    def _index_get(self, url: str) -> str:
        """`_index_get` behind the run's holds: a held site is not requested; a refusal holds."""
        if self.holds.held(url):
            raise SiteRefused(url, int((self.holds.held(url) or {}).get("status") or 0))
        try:
            return _index_get(url)
        except SiteRefused as exc:
            self._hold_site(url, exc.status)
            raise

    def rendered(self, url: str) -> str:
        fenced = _tf.platform_of_url(url)
        if fenced:
            self.status.append({"url": url, **_tf.refusal(fenced)})
            return ""
        if self._site_held(url):
            return ""
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
            with self._lock:                 # the seen-set is shared by every worker thread
                fresh = c["claim_hash"] not in self.seen_claims
                if fresh:
                    self.seen_claims.add(c["claim_hash"])
                    dup_key = c.get("mechanism_key") in self.mech_keys
                    if not dup_key:
                        self.mech_keys.add(str(c.get("mechanism_key")))
            if not fresh:
                self.counts["claims_seen_before"] += 1
                continue
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
                   # THE LABEL, NOT A BRAKE: robots/terms/paywall provenance rides with the
                   # claim so redistribution can be routed later. It never gates the claim.
                   "terms_note": terms_label(ground),
                   "fetched_utc": now, "score": mc.claim_score(c), **(extra or {})}
            if dup_key:
                self.counts["duplicate_mechanisms"] += 1
                row["duplicate_of_key"] = c["mechanism_key"]
            self.new.append(row)
            self.ground_claims.append(row)
            n += 1
            self._provenance(row)
        return n

    def _provenance(self, row: dict[str, Any]) -> None:
        try:
            from libs.data.datahub import record_mined_source
            with self._lock:                 # one appender at a time into the shared ledger
                record_mined_source(repo=str(row.get("ground")), url=str(row.get("url")),
                    commit=f"{row.get('available_time')} sha256:"
                           f"{str(row.get('source_hash'))[:16]}",
                    license_=str(row.get("license") or "WEB-PUBLIC"),
                    file=str(row.get("route")), mechanism=str(row["claim"])[:200],
                    code_copied=False, commercial_restriction=True,
                    path=PROVENANCE)
        except Exception:
            pass

    def dataset(self, page: str, *, ground: dict[str, Any], url: str, title: str,
                route: str = "") -> int:
        """A page that hands over DATA: its endpoints become a discovery row in the crawler's
        own shape (kind "dataset"), so `acquire_datasets` registers them, and a row in the
        datasets ledger, so the report can count what each region's forest yields.

        ON THE INDEX ROUTE (`route` "index:..."), the page is NEVER followed into the frontier
        (world_crawler fetches that with a browser agent) and the row is tagged `route: "index"`
        with `fetch_policy` naming INDEX_UA plus robots.txt, so no downstream fetcher may take
        its endpoints with a browser string or without the robots check (audit 2026-10-14
        MF-B, second path)."""
        eps = data_endpoints(page, url)
        if ground.get("kind") != "dataset" and not eps:
            return 0
        now = datetime.now(tz=UTC).isoformat(timespec="seconds")
        digest = hashlib.sha256((page or "").encode("utf-8")).hexdigest()[:20]
        row = {"source": SOURCE, "kind": "dataset", "title": title[:160] or url[:120], "url": url,
               "published": now, "symbols": [], "timeframes": [], "patterns": [],
               "confidence": round(min(0.95, 0.35 + 0.05 * min(len(eps), 10)), 2),
               "lang": ground.get("language"), "language": ground.get("language"),
               "endpoints": eps[:200], "n_endpoints": len(eps),
               "vault_sha": digest, "host": urlparse(url).netloc,
               "ground": ground.get("name"), "region": ground.get("region"),
               "cluster": cluster_of(ground), "dataset_class": ground.get("dataset_class"),
               "available_time": now, "ingested_time": now, "source_hash": digest,
               "claims": [], "n_claims": 0}
        index_route = route.startswith("index")
        if index_route:
            row["route"] = "index"
            row["fetch_policy"] = {"user_agent": INDEX_UA, "robots_txt": "required",
                                   "on_401_403_429": "stop"}
        self.datasets.append(row)
        self.counts["dataset_pages"] += 1
        self.counts["dataset_endpoints"] += len(eps)
        if not index_route:
            self.follow(url, title, via=f"{SOURCE}:{ground.get('name')}:dataset")
        return len(eps)

    def follow(self, url: str, anchor: str, via: str) -> None:
        if not url.startswith(("http://", "https://")):
            return
        # A URL on a held site (or a Wayback capture of one) is never handed to world_crawler:
        # its fetcher would route around the stop (audit PASS5_feb86fa30 MF3).
        if self.held_url(url):
            return
        with self._lock:
            if url in self.seen_urls:
                return
            self.seen_urls.add(url)
        # THE DELTA SCAN: a fork works one ground, so this count is THAT ground's new URLs
        # against the durable seen-set -- what the attempt found that no earlier pass had.
        self.counts["urls_new"] = self.counts.get("urls_new", 0) + 1
        self.frontier.append((url, via, self.lang))

    # ---------------------------------------------------------------- routes per ground
    def _read_page(self, g: dict[str, Any], page: str, url: str, title: str, route: str) -> int:
        n = self.take(html_text(page), ground=g, url=url, title=title, route=route, page=page)
        self.dataset(page, ground=g, url=url, title=title, route=route)
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
            if u in self.refused:
                continue                 # a refusal is never rendered around
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
                # THE SITE ITSELF IS ALSO READ (LAWS 5e, 2026-09-23). The old `snippets_only`
                # flag stopped here whenever a ground's robots.txt named this agent family or a
                # paywall was declared; that was a discovery brake, not a legal requirement, and
                # it is deleted. The note now travels as `terms_note` on every claim instead.
                if fetched < PAGE_FETCH_PER_QUERY and not self.over():
                    body = self.page(url)
                    if len(html_text(body)) >= MIN_PAGE_TEXT:
                        fetched += 1
                        pages += 1
                        claims += self._read_page(g, body, url, r.get("title", ""),
                                                  f"search:{engine}:page")
                    time.sleep(1.0)
            time.sleep(1.5)
        out: dict[str, Any] = {"queries": len(g.get("queries") or []), "engines": engines,
                               "pages": pages, "claims": claims, "errors": errors[:4]}
        # NO ENGINE ANSWERED (Bing's anti-bot shell, DuckDuckGo empty): the block is recorded,
        # never routed around, and the ground is read by a different METHOD -- its own sitemap
        # or the Common Crawl URL index -- with every page gated by the site's robots.txt.
        if not engines and site and not self.over() and self._net_ok():
            out["index_route"] = self.ground_site_index(g)
            out["claims"] = claims + int(out["index_route"].get("claims") or 0)
            out["pages"] = pages + int(out["index_route"].get("fetched") or 0)
            if out["index_route"].get("fetched"):
                out["fetched"] = out["index_route"]["fetched"]
        return out

    def ground_site_index(self, g: dict[str, Any]) -> dict[str, Any]:
        site = str(g.get("site") or "")
        if self.holds.held(site):
            h = self.holds.held(site) or {}
            return {"route": "held", "listed": 0, "allowed": 0, "robots_disallowed": 0,
                    "robots_unread": 0, "fetched": 0, "claims": 0,
                    "errors": [f"site held: HTTP {h.get('status')}; not listed, not fetched"]}
        idx = site_index_urls(site, get=self._index_get, holds=self.holds)
        queries = [str(q) for q in g.get("queries") or []]
        claims = fetched = 0
        cap = PAGE_FETCH_PER_QUERY * max(1, len(queries))
        for url in rank_by_queries(idx["urls"], queries)[: cap * 2]:
            if fetched >= cap or self.over():
                break
            if self.holds.held(url):
                # THE HARD STOP: the first 401/403/429 ends every request to that site
                break
            # NOT `follow`: the frontier is fetched by world_crawler with a browser agent and no
            # robots check, so an index-route URL never enters it (audit 2026-10-14 MF-B). It is
            # marked seen BEFORE it is read, so nothing the read reaches (`dataset`, a deep link)
            # can put it in the frontier as new.
            with self._lock:
                self.seen_urls.add(url)
            body = self.index_page(url)          # the honest INDEX_UA, never the browser string
            if len(html_text(body)) < MIN_PAGE_TEXT:
                continue
            fetched += 1
            claims += self._read_page(g, body, url, _title(body), f"index:{idx['route']}:page")
            time.sleep(1.0)
        return {"route": idx["route"], "listed": idx["listed"], "allowed": len(idx["urls"]),
                "robots_disallowed": idx["robots_disallowed"],
                "robots_unread": idx.get("robots_unread", 0), "fetched": fetched,
                "claims": claims, "errors": idx["errors"]}

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
            self._note_net(err is None or _answered(str(err)))
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
            self._note_net(err is None or _answered(str(err)))
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
        the feeds do not -- measured by side_channels/reddit_miner). Reddit is IDEAS_ONLY in the
        per-source policy (libs/data/terms_fence.py, ruling of 2026-10-13): posts are read for
        mechanism ideas, and any cell built from one trades on the desk's own MT5 data."""
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
        # polite_fetch's HostAccess record first: a site that refused the desk (401/403/429,
        # a challenge) is not read through its archive copy either -- an archive is not a route
        # around a refusal. The hold lapses on its own clock (429/WAF) or a person's word.
        held = pf.default_access().hold(original) if original else ""
        if held:
            self.status.append({"url": original, "refused": held, "route": "wayback"})
            return {"fetched": 0, "claims": 0, "refused": held,
                    "errors": [f"{held}: {urlparse(original).netloc} is held; its archive "
                               "copy is not read while the hold stands"]}
        # Then the run's SiteHolds: the ORIGINAL site's hold is re-checked before every
        # archive.org request -- the availability API, the capture and each deep link (audit
        # PASS5_feb86fa30 SF): an archive of a site that refused this agent is a route-around.
        if self._site_held(original):
            return {"fetched": 0, "claims": 0, "errors": [f"site held: {original}"]}
        snap, err = wayback_snapshot(original, str(g.get("timestamp") or ""))
        self._note_net(err is None or _answered(str(err)))
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
            if self.held_url(original) or self.held_url(href):
                break                              # held mid-run: no further archive request
            self.follow(href, anchor, via=f"{SOURCE}:{g.get('name')}")
            if pages < DEEP_LINKS_PER_GROUND and not self.over():
                sub = self.page(href, referer=snap)
                if len(html_text(sub)) >= MIN_PAGE_TEXT:
                    pages += 1
                    claims += self._read_page(g, sub, href, _title(sub) or anchor, "wayback:deep")
                time.sleep(1.0)
        return {"fetched": 1, "snapshot": snap, "deep_pages": pages, "claims": claims}

    def ground_nitter(self, g: dict[str, Any]) -> dict[str, Any]:
        """HELD, METHOD_BLOCKED (libs/data/terms_fence.py `nitter`): a nitter mirror exists to get
        around X's login wall, which is a method the desk does not use -- X itself is not banned,
        and its official API (`x_api`, NEEDS_KEY until X_BEARER_TOKEN exists) is the permitted
        route. `work` and `schedule` hold a nitter ground before any request; this holds too, so
        a direct call cannot fetch either."""
        return {**_tf.refusal("nitter"), "claims": 0, "mirrors": len(g.get("mirrors") or [])}

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
        label = terms_label(g)
        # LEGACY `unreachable` IS NOT A REFUSAL ANY MORE (LAWS 5e, 2026-09-23). It was recorded
        # for a paywall or a robots Disallow, which are labels; so the ground is RE-ROUTED to the
        # route its own fields support and mined, with the old reason kept as `terms_note`.
        # Only a ground that names neither a site nor a url has nothing to reach for.
        if route == "unreachable":
            route = "search" if g.get("site") else ("http" if g.get("url") else "unreachable")
        row: dict[str, Any] = {"ground": name, "route": route, "kind": g.get("kind"),
                               "region": g.get("region"), "cluster": cluster_of(g),
                               "language": g.get("language"),
                               "terms_note": label}
        if route == "unreachable":
            self.status.append({**row, "status": "NO_ADDRESS",
                                "why": f"no site and no url to reach for: {g.get('why')}"})
            return
        # THE PER-SOURCE POLICY (libs/data/terms_fence.py, ruling of 2026-10-13: no source is
        # banned). Only a HELD ground -- METHOD_BLOCKED (its only route bypasses a login,
        # paywall, CAPTCHA, rate limit or region lock) or NEEDS_KEY (its official API's key is
        # absent) -- is not fetched; its row names the status, the reason and the permitted route.
        fenced = fenced_ground(g)
        if fenced:
            self.status.append({**row, **_tf.refusal(fenced), "claims": 0})
            return
        if not self.fetch:
            self.status.append({**row, "status": "SKIPPED", "why": "--no-fetch"})
            return
        # A HELD SITE (MF-C): a 401/403/429 earlier this run, or a persisted ACCESS_REFUSED
        # frontier vector (held until a person releases it, whatever its age). Not fetched, and
        # SITE_HELD is not a frontier outcome, so the BLOCKED row is left as it stands.
        if self.frontier_damaged:
            # FAIL CLOSED: the frontier file (the one register of holds) is damaged, so any
            # site may be held; nothing is requested until a person repairs or removes it.
            self.status.append({**row, "status": "SITE_HELD", "claims": 0,
                                "why": f"{FRONTIER_UNREADABLE}: frontier file damaged",
                                "missed_growth": access_hold_missed_growth(
                                    name, {"status": FRONTIER_UNREADABLE})})
            return
        site_key = str(g.get("site") or g.get("url") or "")
        held = self.holds.held(site_key) if site_key else None
        if not held and name in self.held_grounds:
            # the ground's OWN row is a persisted refusal: held whatever site it names
            held = {**self.held_grounds[name], "persisted": True}
            site_key = site_key or str(held.get("site") or name)
        if held:
            dom = registrable_domain(site_key)
            when = "persisted" if held.get("persisted") else "this run"
            self.status.append({**row, "status": "SITE_HELD", "claims": 0,
                                "why": f"site {dom} held: HTTP {held.get('status')} ({when})",
                                "missed_growth": access_hold_missed_growth(dom, held)})
            return
        if not self._net_ok():
            self.status.append({**row, "status": "NO_NETWORK",
                                "why": "three straight transport failures on this box"})
            return
        self.ground, self.ground_claims = g, []
        self.ground_holds = []
        seen_before = self.counts["claims_seen_before"]
        urls_before = self.counts.get("urls_new", 0)
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
        if self.ground_holds:
            # THE HARD STOP, PERSISTED: the ground is BLOCKED in the frontier with an
            # ACCESS_REFUSED blocker, and every later run re-seeds the hold from it until a
            # person releases the row (never the retry clock). Claims already read still count.
            dom = self.ground_holds[0]
            h = self.holds.held(dom) or {}
            status = ACCESS_REFUSED
            out = {**out, "why": (f"HTTP {h.get('status')} from {dom}: site held for the run, "
                                  "no further request, no CDX fallback"),
                   "held_sites": list(self.ground_holds),
                   "missed_growth": access_hold_missed_growth(dom, h)}
        classes: dict[str, int] = {}
        for c in self.ground_claims:
            k = str(c.get("mechanism_class"))
            classes[k] = classes.get(k, 0) + 1
        self.status.append({**row, "status": status, **out,
                            "elapsed_s": round(time.monotonic() - t0, 1), "classes": classes,
                            # ORTHOGONALITY: a ground that yields only momentum says so.
                            "momentum_only": bool(classes) and set(classes) <= {"momentum"},
                            "datasets": sum(1 for d in self.datasets if d.get("ground") == name),
                            # the per-ground DELTA against the durable seen-sets
                            "delta": {"urls_new": self.counts.get("urls_new", 0) - urls_before,
                                      "claims_new": n_claims,
                                      "claims_seen_before": (self.counts["claims_seen_before"]
                                                             - seen_before)}})


def _reroute_census(grounds: list[dict[str, Any]]) -> dict[str, Any]:
    """`bing_reroute_census` over the frontier file as it stands; never raises."""
    try:
        doc = json.loads(_frontier_path().read_text(encoding="utf-8"))
        vectors = doc.get("vectors") if isinstance(doc, dict) else None
    except (OSError, ValueError):
        vectors = None
    try:
        return bing_reroute_census(grounds, vectors if isinstance(vectors, dict) else None)
    except Exception as exc:
        return {"status": "UNMEASURED", "why": f"{type(exc).__name__}: {str(exc)[:120]}"}


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


FRONTIER_NAME = "deep_forest_frontier.json"
#: Ground status -> hunt_frontier outcome. PRODUCTIVE yielded claims; REACHED_NO_CLAIMS is real
#: negative knowledge; the three failure statuses are BLOCKED (the blocker may lift); a ground
#: the budget or --no-fetch never reached stays NAMED_ONLY -- named, not hunted.
_FRONTIER_OUTCOME: dict[str, str] = {
    "PRODUCTIVE": "YIELDED", "REACHED_NO_CLAIMS": "EMPTY", "BLOCKED": "BLOCKED",
    "NO_NETWORK": "BLOCKED", "UNREACHABLE": "BLOCKED",
    # A HELD source (libs/data/terms_fence.py: METHOD_BLOCKED, or NEEDS_KEY until its key
    # exists) is BLOCKED in the frontier's vocabulary, with the policy row as the blocker. The
    # two older spellings stay mapped so a pre-ruling status row still reads.
    "METHOD_BLOCKED": "BLOCKED", "NEEDS_KEY": "BLOCKED",
    # A 401/403/429 hard stop (MF-C): BLOCKED with blocker "ACCESS_REFUSED: ...", which is how
    # the next run re-seeds the site hold. SITE_HELD (skipped under a hold) is deliberately
    # absent, so a skip never refreshes the hold's stamp.
    ACCESS_REFUSED: "BLOCKED",
    "BLOCKED_WITH_SUBSTITUTE": "BLOCKED", "BLOCKED_TERMS": "BLOCKED",
}


def _frontier_path() -> Path:
    """Beside the cursor file, so a test that redirects SEEN redirects this too."""
    return SEEN.with_name(FRONTIER_NAME)


def _record_frontier(grounds_status: list[dict[str, Any]],
                     grounds: list[dict[str, Any]],
                     holds: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    """Every ground's hunt outcome in `libs.research.hunt_frontier`'s vocabulary, stamped with
    the ground's language and region, so the four outcomes roll up PER LANGUAGE.

    Every registered ground is in the state (NAMED_ONLY until a run reaches it), so the
    denominator is the whole registry rather than the grounds one budget happened to touch. A
    ground already hunted is never demoted back to NAMED_ONLY by a run that skipped it.
    """
    from libs.research import hunt_frontier as hf

    path = _frontier_path()
    if frontier_damaged(path):
        # Never overwrite a damaged frontier: the holds it may carry would be lost with it.
        return {"status": "UNMEASURED", "why": f"{FRONTIER_UNREADABLE}: {path} is damaged; "
                "not overwritten -- a person repairs or removes it", "path": str(path)}
    state = hf.load(path)
    # EVERY SITE HOLD IS PERSISTED UNDER ITS REFUSING DOMAIN (`site:<domain>`), so it survives
    # the ground's own vector being re-recorded and lapses only when a person deletes it. A
    # persisted hold already on file keeps its row (and stamp) untouched.
    for dom, h in sorted((holds or {}).items()):
        vname = f"{SITE_VECTOR_PREFIX}{dom}"
        if not dom or vname in state.vectors:
            continue
        hf.record(state, vname, outcome="BLOCKED",
                  blocker=(f"{ACCESS_REFUSED}: HTTP {h.get('status')} from {dom}: site refused "
                           f"this agent (ground {h.get('ground') or '?'}); held until a person "
                           "deletes this row"))
    for g in grounds:
        name = str(g.get("name") or "")
        # A held ground is not frontier work waiting to happen: never seeded NAMED_ONLY.
        if name and name not in state.vectors and not fenced_ground(g):
            hf.record(state, name, outcome="NAMED_ONLY", language=str(g.get("language") or ""),
                      region=str(g.get("region") or ""))
    for s in grounds_status:
        name = str(s.get("ground") or "")
        outcome = _FRONTIER_OUTCOME.get(str(s.get("status") or ""))
        if not name or outcome is None:
            continue
        hf.record(state, name, outcome=outcome, findings=int(s.get("claims") or 0),
                  blocker=(f"{s.get('status')}: {s.get('why') or s.get('error') or ''}".strip(": ")
                           if outcome == "BLOCKED" else ""),
                  language=str(s.get("language") or ""), region=str(s.get("region") or ""))
    hf.save(state, path)
    summary = hf.summarise(state)
    return {k: summary.get(k) for k in ("vectors", "unhunted", "blocked", "off_cooldown",
                                         "picked_over", "total_findings", "yield_rate",
                                         "by_language", "by_region", "languages_yielded",
                                         "languages_named_only", "by_language_note")} | {
        "path": str(path)}


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
            # `lang` is the claim's own language as extracted; `language` is the GROUND's
            # declared language from deep_forest_sources.json, which is the key the
            # per-language yield accounting joins on.
            "language": row.get("language") or row.get("lang"),
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
        "patterns", "confidence", "lang", "language", "endpoints", "n_endpoints", "vault_sha",
        "host", "ground", "region", "cluster", "dataset_class", "available_time",
        "ingested_time", "source_hash", "claims", "n_claims"],
    "deepening task (data/hypotheses/miner_deepening_queue.json)": [
        "source", "kind=story_mechanism", "title", "description", "url", "symbols",
        "mechanism_tags", "lang", "language", "region", "cluster", "channel", "mechanism_class",
        "mechanism_key", "evidence_grade", "claimed_performance", "transfer_only", "claim_hash",
        "provenance[{url,ground,route,available_time,published_time,source_hash,lang}]",
        "n_tellings", "event_time", "published_time", "available_time", "score", "status",
        "consumer"],
    "mined_sources.jsonl (libs.data.datahub.record_mined_source)": [
        "at", "repo=ground", "url", "commit='<available_time> sha256:<source_hash16>'", "license",
        "file=route", "mechanism", "code_copied", "attribution_required",
        "commercial_restriction", "policy"],
    "frontier (data/deep_forest_frontier.json; libs.research.hunt_frontier)": [
        "vectors{<ground>: {outcome=NAMED_ONLY|BLOCKED|EMPTY|YIELDED, first_seen, last_attempt, "
        "attempts, findings, blocker, language, region}}", "updated", "note"],
}


def run(budget_s: float = 900.0, fetch: bool = True, only: list[str] | None = None,
        write: bool = True, region: str | None = None, *, workers: int | None = None,
        report_path: Path | None = None, leg: str = LEG) -> dict[str, Any]:
    # SELF-STOP INSIDE THE CAP THE CYCLE ACTUALLY GAVE. A budget above the cap is a run that is
    # SIGKILLed before it writes, at the same prefix every hour -- the reason 467 grounds stayed
    # NAMED_ONLY. The cap is exported by hourly_cycle; a missing export changes nothing.
    requested_s = float(budget_s)
    cap = _env_budget_cap()
    if cap is not None:
        budget_s = max(MIN_GROUND_S, min(float(budget_s), cap - WRITE_RESERVE_S))
    n_workers = max(1, int(workers if workers is not None else WORKERS))
    pf.reset_stats(LEG)
    cfg = _load_sources()
    grounds = list(cfg.get("grounds") or [])
    # THE CRAWL BUDGET IS THE SOURCE REGISTRY'S SHARES (Tier-1 W17). `schedule()` sorts on
    # `weight` and the loop below divides `budget_s` by it, so reweighting the grounds IN MEMORY
    # makes both the order and the seconds follow measured intel ROI. Guarded and reversible:
    # an absent, empty or stale SOURCE_REGISTRY.json returns the grounds untouched and says so,
    # which is exactly today's behaviour. The registered weight on disk is never rewritten.
    share_meta: dict[str, Any] = {"status": "unavailable", "why": "source_shares not importable"}
    try:
        from research import source_shares
        _share_state = source_shares.load()
        grounds, share_meta = source_shares.weight_grounds(grounds, _share_state)
    except Exception as exc:
        share_meta = {"status": "unavailable", "why": f"{type(exc).__name__}: {exc}"}
        _share_state = None
    r = _Run(budget_s, fetch, set(only or []) or None, region)
    cursor = int(r.seen.get("cursor") or 0) if not (only or region) else 0
    try:
        from libs.research import hunt_frontier as _hf
        # A DAMAGED frontier fails CLOSED (audit PASS5_feb86fa30 MF1): hunt_frontier.load
        # reads an unparseable file as empty, which would silently drop every hold in it.
        frontier_state = (None if frontier_damaged(_frontier_path())
                          else _hf.load(_frontier_path()))
    except Exception:  # unreadable accounting fails closed: every ground held, none fetched
        frontier_state = None
    # THE PERSISTED HOLDS (MF-C): a site that refused this agent stays held across runs.
    seed_persisted_holds(r, grounds, frontier_state)
    # LOW_EV_RETIRED is derived from the counters every pass (`research/forest_attempts.py`):
    # retired grounds are scheduled LAST, never dropped, and reopen on a named condition.
    try:
        from research import forest_attempts as _fa
        retired = _fa.retired_names(grounds, frontier=_frontier_path(),
                                    stats=_vector_stats_path())
    except Exception:  # a damaged accounting file may never stop the miner
        retired = set()
    order = schedule(grounds, cursor, only=r.only, region=region,
                     frontier_state=frontier_state, retired=retired)
    # THE PROPOSER SEAT, OPTIONAL: which registered GROUND is worth this pass's seconds first.
    # An ORDER over the grounds the registry already holds -- the seat may reorder the crawl and
    # may never widen it, so a name it invents is discarded and no unregistered ground can be
    # reached by being named. Unchanged order, and no call at all, on a box with no panel.
    seat_hint: dict[str, Any] = {"verdict": "UNMEASURED"}
    try:
        from libs.research import proposer_seat as _ps
        _names = [str(g.get("name") or "") for g in order if g.get("name")]
        _reply = _ps.ask("deep_forest_miner", "order", options=_names,
                         task=("Order these practitioner-forest grounds by which is most likely "
                               "to yield a NEW testable market mechanism this pass. Return the "
                               "full list, best first."))
        seat_hint = _reply.to_row()
        if _reply.measured and _reply.ordered != _names:
            _rank = {n: i for i, n in enumerate(_reply.ordered)}
            # The seat may rank WITHIN the frontier, never move picked-over ground ahead of a
            # NAMED_ONLY or retry-due vector.  Re-applying the frontier rank after its suggestion
            # makes that boundary structural rather than prompt-dependent.
            seat_order = sorted(order,
                                key=lambda g: _rank.get(str(g.get("name") or ""), 10 ** 6))
            now = datetime.now(tz=UTC)
            # frontier bucket first, then least-recently-attempted, the seat's rank breaking ties
            order = sorted(seat_order,
                           key=lambda g: (_frontier_bucket(g, frontier_state, now, retired),
                                          _last_attempt(g, frontier_state)))
    except Exception as _exc:                             # pragma: no cover - optional seat
        seat_hint = {"verdict": "UNMEASURED", "why": f"{type(_exc).__name__}: {_exc}"}
    total_w = sum(float(g.get("weight") or 1.0) for g in order) or 1.0
    # THE WORK QUEUE: `n_workers` threads pull the next ground in schedule order, each on its
    # own fork of the run, and every finished ground is CHECKPOINTED at once (claims, datasets,
    # frontier outcome, vector stats) -- so a kill costs the grounds in flight, never the hour.
    queue_lock = threading.Lock()
    cursor_at = [0]
    worked_n = [0]
    ckpt = {"last_seen_save": time.monotonic()}

    def _next_ground() -> dict[str, Any] | None:
        with queue_lock:
            if cursor_at[0] >= len(order):
                return None
            g = order[cursor_at[0]]
            cursor_at[0] += 1
            return g

    def _worker() -> None:
        while True:
            g = _next_ground()
            if g is None:
                return
            if r.over() or time.monotonic() - r.started > budget_s:
                with r._lock:
                    r.status.append({"ground": g.get("name"), "region": g.get("region"),
                                     "cluster": cluster_of(g), "status": "BUDGET_EXHAUSTED",
                                     "why": "least-recently-attempted order resumes here"})
                continue
            share = max(MIN_GROUND_S,
                        budget_s * float(g.get("weight") or 1.0) / total_w * SPREAD)
            f = r.fork()
            f.work(g, share_s=share)
            r.merge(f)
            with queue_lock:
                worked_n[0] += 1
            if write:
                _checkpoint(r, f, ckpt)

    if n_workers == 1 or len(order) <= 1:
        _worker()
    else:
        threads = [threading.Thread(target=_worker, name=f"deep-forest-{i}", daemon=True)
                   for i in range(min(n_workers, len(order)))]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
    worked = worked_n[0]
    # NOTHING ON A HELD SITE LEAVES THE RUN (audit PASS5_feb86fa30 MF3): the frontier and the
    # dataset rows are filtered by the run's final holds before world_crawler / the acquirer see
    # them, so a hold placed after a URL was followed still keeps it out.
    r.frontier[:] = r.unheld(r.frontier)
    r.datasets[:] = [d for d in r.datasets if not r.held_url(str(d.get("url") or ""))]
    for d in r.datasets:
        if d.get("endpoints"):
            d["endpoints"] = [u for u in d["endpoints"] if not r.held_url(str(u))]
            d["n_endpoints"] = len(d["endpoints"])
    discoveries = _write_discoveries(r.datasets) if write else None
    frontier_added = _feed_frontier(r.frontier) if write else 0
    # SOURCE EXPANSION: a ground whose ROI share ROSE has the links it actually served promoted
    # to candidate grounds in the REGISTERED grounds file -- authors, linked forums, archives,
    # citations, code repos, adjacent terminology. `r.frontier` is (url, via, lang); `via` is the
    # page that served it, which is the parent this expansion is about. Nothing is invented and
    # nothing is hard-coded: the registry prices the new grounds on its next pass.
    expansion: dict[str, Any] = {"status": "unavailable", "why": "source_shares not importable"}
    try:
        from research import source_shares as _ss
        _obs: dict[str, list[tuple[str, str]]] = {}
        for _url, _via, _ in r.frontier:
            _obs.setdefault(str(_via), []).append((str(_url), ""))
        expansion = _ss.expand(_obs, _share_state, apply=write)
    except Exception as exc:
        expansion = {"status": "unavailable", "why": f"{type(exc).__name__}: {exc}"}
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
                # ONE SOURCE PER REGION CLUSTER: each replaces only its own rows. Serialised
                # across the forest legs that now run this miner concurrently.
                with _xlock("deepening_queue", timeout_s=120.0):
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
                                       "languages": [], "terms_fenced": 0})
        if fenced_ground(g):
            # Registered, never workable: counted apart, so `worked == grounds` stays a
            # statement about the grounds the desk may actually fetch.
            b["terms_fenced"] += 1
            continue
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
    # THE PER-LANGUAGE FRONTIER. Accounting only: it changes nothing about which ground is
    # worked next, and a failure to write it is reported on the doc rather than raised.
    frontier: dict[str, Any]
    if write:
        try:
            done = ckpt.get("done") or set()
            rest = [s for s in grounds_status
                    if str(s.get("ground") or "") not in done and s.get("status") != "NO_NETWORK"]
            with _xlock("deep_forest_frontier"):
                frontier = _record_frontier(rest, grounds, dict(r.holds.sites))
        except Exception as exc:
            frontier = {"status": "UNMEASURED",
                        "why": f"frontier accounting failed: {type(exc).__name__}: {exc}"}
    else:
        frontier = {"status": "UNMEASURED", "why": "write=False: frontier state not touched"}
    doc = {"generated_utc": datetime.now(tz=UTC).isoformat(timespec="seconds"),
           "budget_s": budget_s, "elapsed_s": round(time.monotonic() - r.started, 1),
           "network": r.network, "fetch": fetch, "region_filter": region,
           "grounds_total": len(grounds), "grounds_scheduled": len(order),
           "grounds_worked": worked, "cursor_next": r.seen.get("cursor"),
           "grounds": grounds_status,
           "productive": sum(1 for s in grounds_status if s.get("status") == "PRODUCTIVE"),
           "blocked": [s.get("ground") for s in grounds_status
                       if s.get("status") in ("BLOCKED", "NO_NETWORK", "UNREACHABLE")],
           # Registered HELD grounds (METHOD_BLOCKED / NEEDS_KEY): never scheduled, never
           # fetched, named here so the gap is visible (libs/data/terms_fence.py).
           "terms_fenced": sorted({str(g.get("name")) for g in grounds if fenced_ground(g)}),
           "momentum_only_grounds": [s.get("ground") for s in grounds_status
                                     if s.get("momentum_only")],
           "by_region": by_region,
           "languages": sorted({str(g.get("language")) for g in grounds if g.get("language")}),
           "frontier": frontier,
           "bing_reroute": _reroute_census(grounds),
           "scheduler": {"policy": ("NAMED_ONLY -> retry-due BLOCKED -> cooldown-due covered "
                                    "-> not attempted in 24h (daily floor) -> attempted in 24h "
                                    "-> LOW_EV_RETIRED; inside each bucket least-recently-"
                                    "attempted first over a regional round-robin"),
                         "retired_scheduled_last": len(retired),
                         "frontier_state_loaded": frontier_state is not None,
                         "workers": n_workers, "requested_budget_s": requested_s,
                         "cycle_cap_s": cap,
                         "checkpointed_grounds": len(ckpt.get("done") or ()),
                         "checkpoint_errors": ckpt.get("errors") or []},
           "fetch_stats": {**pf.stats(LEG), "leg": leg,
                     "fetches_per_s": _rate(pf.stats(LEG)["fetches"],
                                            time.monotonic() - r.started)},
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
           "source_shares": share_meta,
           "proposer_seat": seat_hint,
           "source_expansion": expansion,
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
        out = report_path or REPORT
        _atomic_text(out, json.dumps(doc, indent=1, ensure_ascii=False, default=str))
        if fetch:
            _append_run({"at": doc["generated_utc"], "leg": leg, "region_filter": region,
                         "only": len(only or []), "seconds": doc["elapsed_s"],
                         "workers": n_workers, "grounds_worked": worked,
                         "grounds_scheduled": len(order), "claims_new": len(r.new),
                         "datasets_new": len(r.datasets), **doc["fetch_stats"]})
        # THE YIELD ARTIFACT IS WRITTEN BY THE LEG THAT MOVES IT: every scheduled pass of this
        # miner (the deep_forest leg and every forest_* leg's practitioner role) republishes it.
        with contextlib.suppress(Exception):
            from research import alt_data_yield
            alt_data_yield.write(out=REPORT.with_name(alt_data_yield.ARTIFACT_NAME),
                                 frontier=_frontier_path(), vector_stats=_vector_stats_path(),
                                 runs=_runs_path())
    return doc


def _rate(n: float, seconds: float) -> float | None:
    return round(n / seconds, 4) if seconds > 0 else None


def _runs_path() -> Path:
    """Beside the cursor file, so a test that redirects SEEN redirects this too."""
    return SEEN.with_name(RUNS.name)


def _vector_stats_path() -> Path:
    return SEEN.with_name(VECTOR_STATS_NAME)


def _append_run(row: dict[str, Any]) -> None:
    with contextlib.suppress(OSError), _xlock("alt_fetch_runs"):
        p = _runs_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def _record_vector_stats(statuses: list[dict[str, Any]]) -> None:
    """Cumulative per-vector attempts / successes / rows / last error. The frontier keeps the
    outcome; this keeps the COUNTS the yield artifact needs (a success is a ground that
    produced at least one claim or dataset)."""
    p = _vector_stats_path()
    with _xlock("deep_forest_vector_stats"):
        try:
            doc = json.loads(p.read_text("utf-8"))
            vec = doc.get("vectors") if isinstance(doc, dict) else None
        except (OSError, ValueError):
            vec = None
        vec = vec if isinstance(vec, dict) else {}
        now = datetime.now(tz=UTC).isoformat(timespec="seconds")
        for s in statuses:
            name = str(s.get("ground") or "")
            if not name:
                continue
            e = vec.setdefault(name, {"attempts": 0, "successes": 0, "rows": 0,
                                      "datasets": 0, "counted_since": now})
            rows = int(s.get("claims") or 0)
            dsets = int(s.get("datasets") or 0)
            e["attempts"] = int(e.get("attempts") or 0) + 1
            e["successes"] = int(e.get("successes") or 0) + (1 if rows or dsets else 0)
            e["rows"] = int(e.get("rows") or 0) + rows
            e["datasets"] = int(e.get("datasets") or 0) + dsets
            e["last_status"] = s.get("status")
            e["last_attempt"] = now
            e["last_elapsed_s"] = s.get("elapsed_s")
            e["region"] = s.get("region")
            e["language"] = s.get("language")
            e["route"] = s.get("route")
            err = s.get("error") or "; ".join(str(x) for x in (s.get("errors") or [])[:2]) \
                or (s.get("why") if s.get("status") not in ("PRODUCTIVE",
                                                            "REACHED_NO_CLAIMS") else "")
            if rows or dsets:
                e["last_success"] = now
            if err or s.get("status") in ("BLOCKED", "NO_ADDRESS", "UNREACHABLE"):
                e["last_error"] = str(err or s.get("status"))[:200]
            # THE STANDING failure reason: this attempt's, or none when the route answered.
            # `last_error` stays sticky -- it is history; this is the current state.
            e["failure_reason"] = (str(err or s.get("status"))[:200]
                                   if err or s.get("status") not in ("PRODUCTIVE",
                                                                    "REACHED_NO_CLAIMS")
                                   else "")
            # THE DURABLE DELTA CURSOR. The seen-sets (deep_forest_seen.json) are the scan's
            # memory; this is its per-ground reading: what the last attempt added, when the
            # ground last showed anything new, and how many attempts running it showed nothing.
            delta = s.get("delta") if isinstance(s.get("delta"), dict) else None
            if delta is not None:
                e["last_delta"] = delta
                fresh = int(delta.get("urls_new") or 0) + int(delta.get("claims_new") or 0) \
                    + dsets
                if fresh:
                    e["last_new_content_at"] = now
                    e["empty_delta_streak"] = 0
                else:
                    e["empty_delta_streak"] = int(e.get("empty_delta_streak") or 0) + 1
        _atomic_text(p, json.dumps({"updated": now, "vectors": vec,
                                    "note": "per-vector cumulative counts since counted_since; "
                                            "written by deep_forest_miner at each ground's "
                                            "checkpoint"}, ensure_ascii=False, indent=0))


def _checkpoint(r: _Run, f: _Run, ckpt: dict[str, Any]) -> None:
    """Persist ONE finished ground now: its claims and datasets (appended), its frontier
    outcome and its vector counts, and -- at most once a minute -- the merged seen-set. Never
    raises: a failed checkpoint is recorded on the report and the end-of-run write retries."""
    try:
        if f.new:
            with _xlock("deep_forest_claims"):
                CLAIMS.parent.mkdir(parents=True, exist_ok=True)
                with CLAIMS.open("a", encoding="utf-8") as fh:
                    for row in f.new:
                        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        if f.datasets:
            with _xlock("deep_forest_datasets"):
                DATASETS.parent.mkdir(parents=True, exist_ok=True)
                with DATASETS.open("a", encoding="utf-8") as fh:
                    for row in f.datasets:
                        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        # A ground the box could not reach because the BOX had no network was not attempted;
        # recording it BLOCKED would move it out of NAMED_ONLY without anyone having tried it.
        sts = [s for s in f.status if "ground" in s and s.get("status") != "NO_NETWORK"]
        if sts:
            with _xlock("deep_forest_frontier"):
                _record_frontier(sts, [], dict(r.holds.sites))
            _record_vector_stats(sts)
        with r._lock:
            ckpt.setdefault("done", set()).update(str(s.get("ground") or "")
                                                  for s in f.status if "ground" in s)
            due = time.monotonic() - ckpt["last_seen_save"] > 60.0
            if due:
                ckpt["last_seen_save"] = time.monotonic()
                snap = {**r.seen, "claims": list(r.seen_claims), "urls": list(r.seen_urls)}
        if due:
            _save_seen(snap)
    except Exception as exc:
        with r._lock:
            ckpt.setdefault("errors", []).append(f"{type(exc).__name__}: {str(exc)[:160]}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--budget-s", type=float, default=900.0)
    ap.add_argument("--no-fetch", action="store_true", help="rebuild the queue from the ledger")
    ap.add_argument("--only", action="append", default=None,
                    help="ground name, route, region or cluster to work (repeatable)")
    ap.add_argument("--region", default=None, help="work one region (or cluster) this pass")
    ap.add_argument("--workers", type=int, default=WORKERS,
                    help="grounds worked at once (politeness stays per host)")
    a = ap.parse_args()
    d = run(budget_s=a.budget_s, fetch=not a.no_fetch, only=a.only, region=a.region,
            workers=a.workers)
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
