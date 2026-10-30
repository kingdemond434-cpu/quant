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
gone, the Common Crawl URL index where the search engines answer with an anti-bot wall, a
rendered fetch where a shell hides the listing (a ground whose only route would bypass a
login, or whose API key is absent, is HELD and says which -- SOURCE_POLICY) -- and then
hands every URL it finds to the crawler's frontier, so the forest it opens keeps being
walked after this run ends.

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
import gzip
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
#: THE RAW LANDING (principal 2026-10-13 16:39Z: "bring in ALL public data, ugly data included").
#: A fetched page this miner would drop for its FORM -- a non-HTML body (CSV, XLS, PDF, JSON, XML,
#: ZIP, plain text), a page under MIN_PAGE_TEXT, a dataset page with no endpoints -- is landed
#: raw in the lake vault the desk already parses (`asia_collector._vault`'s layout:
#: `<id>/<sha16>.gz` + `.meta.json`), one source id per URL, so `asia_parser` (raw -> series,
#: point-in-time stamped) and `source_drain` (series -> cells -> the gauntlet) judge it like any
#: collected source. A landing is NOT a yield. Never for an IDEAS_ONLY or held source, never an
#: anti-bot page, and nothing about how a page is fetched changes.
RAW_VAULT = _DESK / "data" / "lake" / "vault"
RAW_PREFIX = "dfraw__"
RAW_MAX_PER_RUN = 200
#: The landing's BYTE bound per run (the count bound alone lets 200 bodies of polite_fetch's
#: max_bytes each through; the build box runs with about 1 GB of free disk). A body that would
#: cross it is not landed and is counted (`landed_raw_skipped_bytes_cap`).
RAW_MAX_BYTES_PER_RUN = 64 * 1024 * 1024
#: A short page that is a login / cookie / password form is not data: it is never landed
#: (`landed_raw_skipped_login`), so it occupies no vault id.
_PASSWORD_FORM = re.compile(rb"(?i)<input[^>]+type\s*=\s*[\"']?password")
_NON_HTML_TYPE = re.compile(r"(?i)csv|excel|spreadsheet|officedocument|pdf|json|xml|zip|"
                            r"octet-stream|text/plain|tab-separated")
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
#: THE COMPETITION GRAVEYARD (Asia directive PART XIV, 2026-10-06). A `competition` ground's
#: ranking TABLE is a population -- winners, the middle and the accounts that blew up or left --
#: and the claims extractor only ever read its prose. `competition_rows` reads the table; the
#: rows are appended here (never overwritten) and `book_forensics` folds them into the trader
#: genome under its terms gate.
COMPETITION_LEDGER = _DESK / "data" / "trader_genome_competition.jsonl"
#: Per-vector attempts / successes / rows / last error, beside the frontier file.
VECTOR_STATS_NAME = "deep_forest_vector_stats.json"
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


# ------------------------------------------------------------------------- source policy
#: PER-SOURCE POLICY (principal 2026-10-13: "no source should be banned"). There is no category
#: ban: every source is handled by its own row. What stays off is a METHOD -- bypassing a login,
#: paywall, CAPTCHA, rate limit or region lock; stolen data; MNPI -- never a platform. Statuses:
#:   API_PERMITTED  an official API or free tier within its published limits (NEEDS_KEY when the
#:                  row's key is absent from the environment);
#:   PUBLIC_PAGE    fetch the public page politely (the default for any host not listed);
#:   IDEAS_ONLY     read public posts for mechanism claims; NEVER registered as live input data
#:                  (a cell built from the idea trades on the desk's own MT5 data);
#:   METHOD_BLOCKED only when the ONLY route would bypass a login, paywall, CAPTCHA, rate limit
#:                  or region lock -- the reason is named and a permitted route is offered.
#: An anti-bot / CAPTCHA page met on any source is recorded ANTI_BOT and never routed around.
#: Provenance and the terms note never block a claim or a cell (rule 4): they are labels.
#:
#: ONE TABLE. The rows, their quoted terms and the wrapper / spelling resolution live in
#: `libs/data/terms_fence.py` (`SOURCE_POLICY`) and nowhere else; this miner reads them through
#: the views below, which keep the shape its callers and its status rows already use.
API_PERMITTED = _tf.API_PERMITTED
PUBLIC_PAGE = _tf.PUBLIC_PAGE
IDEAS_ONLY = _tf.IDEAS_ONLY
METHOD_BLOCKED = _tf.METHOD_BLOCKED
NEEDS_KEY = _tf.NEEDS_KEY
#: The table itself (read-only here): `libs.data.terms_fence.SOURCE_POLICY`.
SOURCE_POLICY = _tf.SOURCE_POLICY
#: The two statuses that HOLD a ground (it is not fetched this pass, and says which one).
HOLDING: frozenset[str] = _tf.HOLDING


def _host_of(u: Any) -> str:
    s_ = str(u or "").strip().lower()
    if not s_:
        return ""
    if "://" not in s_:
        s_ = "https://" + s_
    try:
        return (urlparse(s_).hostname or "").strip(".")
    except ValueError:
        return ""


def _resolve(key: str) -> dict[str, Any]:
    """A policy row with its EFFECTIVE status (`terms_fence.status`: API_PERMITTED becomes
    NEEDS_KEY when a key is absent; presence only, never read or printed)."""
    row = SOURCE_POLICY[key]
    out: dict[str, Any] = {"source": key, "status": _tf.status(key), "why": row["why"]}
    if row.get("reason"):
        out["reason"] = row["reason"]
    if row.get("permitted_route"):
        out["permitted_route"] = row["permitted_route"]
        out["permitted_route_status"] = _tf.status(str(row["permitted_route"]))
    return out


def policy_of_url(url: Any) -> dict[str, Any]:
    """The effective policy row for a URL (or bare host); PUBLIC_PAGE when unlisted. A wrapper
    (archive, cache, reader, translate proxy) reads as what it wraps (`terms_fence`)."""
    key = _tf.source_of_url(str(url or ""))
    if key:
        return _resolve(key)
    return {"source": _host_of(url), "status": PUBLIC_PAGE, "why": "unlisted host: public page"}


def ground_policy(g: dict[str, Any]) -> dict[str, Any]:
    """The effective policy for a ground: its route's row, else the most restrictive row among
    its url, alt, site, feeds and mirrors (a HOLD outranks IDEAS_ONLY outranks PUBLIC_PAGE)."""
    route = str(g.get("route") or "")
    for key, spec in SOURCE_POLICY.items():
        if route and route in (spec.get("routes") or ()):
            return _resolve(key)
    rank = {METHOD_BLOCKED: 0, NEEDS_KEY: 1, IDEAS_ONLY: 2, API_PERMITTED: 3, PUBLIC_PAGE: 4}
    best: dict[str, Any] | None = None
    for u in (g.get("url"), g.get("site"), *(g.get("alt") or []), *(g.get("feeds") or []),
              *(g.get("mirrors") or [])):
        if not u:
            continue
        p = policy_of_url(u)
        if best is None or rank[p["status"]] < rank[best["status"]]:
            best = p
    return best or {"source": "", "status": PUBLIC_PAGE, "why": "no address listed"}


def held_ground(g: dict[str, Any]) -> dict[str, Any] | None:
    """The policy row that HOLDS this ground (METHOD_BLOCKED or NEEDS_KEY), or None."""
    p = ground_policy(g)
    return p if p["status"] in HOLDING else None


def held_row(p: dict[str, Any]) -> dict[str, Any]:
    """A ground's status row when its policy holds it: HELD, labelled with WHICH hold."""
    why = f"{p['source']}: {p['why']}"
    if p.get("reason"):
        why = f"{p['source']} ({p['reason']}): {p['why']}"
    out = {"status": "HELD", "cause": p["status"], "held_by": p["status"],
           "source_policy": p["source"], "why": why}
    if p.get("permitted_route"):
        out["permitted_route"] = p["permitted_route"]
        out["permitted_route_status"] = p.get("permitted_route_status")
    return out


# ------------------------------------------------------------------- Common Crawl URL index
#: THE PERMITTED SEARCH FALLBACK (2026-10-13). Bing answers this desk with an anti-bot shell and
#: DuckDuckGo with nothing; an anti-bot page is recorded as the blocker and NEVER retried with
#: other headers. The Common Crawl URL index enumerates a ground's own `site` pages instead, and
#: those pages are then read from the site itself through `_Run.page`. One CDX query per ground
#: per pass, a small limit, a wide per-host spacing, an honest user agent, and the index's own
#: robots.txt consulted first (a disallow stands the route down, never routed around).
#: web.archive.org is NOT used here: its terms could not be read, so it stays as it was.
TERMS_EVIDENCE: dict[str, dict[str, str]] = {
    "commoncrawl_index": {
        "terms_url": "https://commoncrawl.org/terms-of-use",
        "terms_quote": ("CC grants you a limited, non-assignable, non-transferable, "
                        "non-sublicensable, non-exclusive, limited license [...] to access and "
                        "use the Service subject to the terms and conditions of these ToU. "
                        "(Preamble:) for the purpose of enabling a new wave of innovation, "
                        "education and research."),
        "restrictions": ("no \"interfering with or disrupting the Service\"; no \"forging or "
                         "intentionally modifying headers\"; no collecting personal information"),
        "service_note": ("index.commoncrawl.org: \"Please do not overload the URL index "
                         "server.\""),
        "robots": ("consulted at run time (ccindex_robots); on 2026-10-13 a reader agent was "
                   "refused the CDX query path by robots, so a disallow for this agent is "
                   "recorded and the route stands down"),
        "checked_at": "2026-10-13"},
}
CCINDEX_HOST = "index.commoncrawl.org"
CCINDEX_COLLINFO = f"https://{CCINDEX_HOST}/collinfo.json"
CCINDEX_LIMIT = 15
CCINDEX_PAGES = 4
CCINDEX_AGENT = "quant-desk-deep-forest"
CCINDEX_UA = {"User-Agent": f"{CCINDEX_AGENT}/1.0 (research; Common Crawl URL index, one "
                            "query per ground per pass)",
              "Accept": "application/json,text/plain;q=0.9,*/*;q=0.5"}
#: Its own gate: the index host is spaced far wider than an ordinary site.
_CC_GATE = pf.HostGate(default_s=4.0)
_CC_STATE: dict[str, Any] = {}
_CC_LOCK = threading.Lock()


def _cc_get(url: str) -> pf.Response:
    return pf.get(url, headers=CCINDEX_UA, timeout=25.0, retries=0, leg=LEG,
                  gate=_CC_GATE, max_bytes=1_000_000)


def ccindex_robots() -> tuple[bool, str]:
    """(allowed, why) for the CDX query path under this agent, read once per process."""
    with _CC_LOCK:
        if "robots" in _CC_STATE:
            return _CC_STATE["robots"]
        r = _cc_get(f"https://{CCINDEX_HOST}/robots.txt")
        if r.ok:
            ok = robots_allows(r.text, CCINDEX_AGENT,
                               "/CC-MAIN-0000-00-index?url=example.org/*&output=json")
            out = (ok, "robots.txt allows the CDX path" if ok else
                   "robots.txt disallows the CDX query path for this agent; route stands down")
        elif r.status == 404:
            out = (True, "robots.txt absent (404): no rules")
        else:
            # Unreadable is not permission: the route stands down this pass (fail closed).
            out = (False, f"robots.txt unreadable ({r.error or r.status}); route stands down")
        _CC_STATE["robots"] = out
        return out


def robots_allows(robots: str, agent: str, path: str) -> bool:
    """RFC 9309 reading of a robots.txt for `agent` on `path` (path + query), WITH the `*` and
    `$` wildcards the standard library's parser ignores: the group naming the agent, else `*`;
    the longest matching rule wins and Allow wins a tie. No rule matching means allowed."""
    groups: list[tuple[list[str], list[tuple[str, str]]]] = []
    agents: list[str] = []
    rules: list[tuple[str, str]] = []
    for raw in (robots or "").splitlines():
        line = raw.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        key, val = (x.strip() for x in line.split(":", 1))
        key = key.lower()
        if key == "user-agent":
            if rules:
                groups.append((agents, rules))
                agents, rules = [], []
            agents.append(val.lower())
        elif key in ("allow", "disallow") and agents:
            rules.append((key, val))
    if agents:
        groups.append((agents, rules))
    mine = [r for a, r in groups if any(x != "*" and x in agent.lower() for x in a)]
    chosen = [rule for rs in (mine or [r for a, r in groups if "*" in a]) for rule in rs]
    best: tuple[int, bool] | None = None
    for kind, pat in chosen:
        if not pat:
            continue                      # an empty Disallow allows everything
        rx = "^" + re.escape(pat).replace(r"\*", ".*")
        if rx.endswith(r"\$"):
            rx = rx[:-2] + "$"
        if re.match(rx, path):
            cand = (len(pat), kind == "allow")
            if best is None or cand > best:
                best = cand
    return True if best is None else best[1]


def ccindex_collection() -> tuple[str, str | None]:
    """The newest collection's CDX endpoint from collinfo.json, read once per process."""
    with _CC_LOCK:
        if "api" in _CC_STATE:
            return _CC_STATE["api"]
        r = _cc_get(CCINDEX_COLLINFO)
        out: tuple[str, str | None]
        if not r.ok:
            out = ("", f"collinfo: {r.error or f'HTTP {r.status}'}")
        else:
            try:
                info = json.loads(r.text)
                api = str(info[0].get("cdx-api") or "") if info else ""
                out = (api, None) if api.startswith(f"https://{CCINDEX_HOST}/") else (
                    "", "collinfo: no cdx-api in the newest collection")
            except (ValueError, TypeError, AttributeError, IndexError) as exc:
                out = ("", f"collinfo unparseable: {type(exc).__name__}")
        _CC_STATE["api"] = out
        return out


def parse_cdx(text: str) -> list[str]:
    """Page URLs from a CDX `output=json` answer (one JSON object per line), HTML 200s only,
    de-duplicated in order."""
    out: list[str] = []
    for line in (text or "").splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if not isinstance(row, dict):
            continue
        url = str(row.get("url") or "")
        if not url.startswith(("http://", "https://")):
            continue
        if str(row.get("status") or "200") != "200":
            continue
        mime = str(row.get("mime") or row.get("mime-detected") or "text/html")
        if "html" not in mime:
            continue
        if url not in out:
            out.append(url)
    return out


def ccindex_pages(site: str, limit: int = CCINDEX_LIMIT) -> tuple[list[str], str | None]:
    """(page URLs on `site`, error). ONE CDX query; a 404 is "no captures", not an error."""
    pol = policy_of_url(site)
    if pol["status"] in HOLDING:
        return [], f"{pol['status']}:{pol['source']}"
    ok, why = ccindex_robots()
    if not ok:
        return [], why
    api, err = ccindex_collection()
    if err:
        return [], err
    q = (f"{api}?url={quote(site.strip('/'), safe='.-_~')}/*&output=json"
         f"&limit={int(limit)}&filter=status:200&filter=mime:text/html")
    r = _cc_get(q)
    if r.status == 404:
        return [], None
    if not r.ok:
        return [], f"ccindex: {r.error or f'HTTP {r.status}'}"
    return parse_cdx(r.text), None


# ------------------------------------------------------------------------------- fetching
#: Markers of an anti-bot interstitial served with a 200. Read only on SHORT pages, where a
#: challenge is the whole page rather than a footer link.
_ANTI_BOT_PAGE = re.compile(r"(?i)cf-chl|just a moment\.\.\.|attention required!? \| cloudflare|"
                            r"ddos-guard|are you a robot|captcha-delivery|px-captcha")


#: The last polite_fetch Response on this thread, so `_Run.page` can land the BYTES of a page
#: whose form it drops (`_http` returns text, and stays the seam tests replace).
_LAST = threading.local()


def fenced_ground(g: dict[str, Any]) -> str | None:
    """The HELD source key a ground belongs to (METHOD_BLOCKED, or NEEDS_KEY until its key
    exists; `held_ground` over libs/data/terms_fence.py), or None. Kept for its callers."""
    p = held_ground(g)
    return str(p["source"]) if p else None


def _http(url: str, *, timeout: float = 20.0, referer: str = "", lang: str = "") -> str:
    """One polite GET (per-host spacing, bounded retry on 429/5xx/transport, certifi-backed TLS,
    charset-aware decoding). Raises `urllib.error.HTTPError` on an HTTP failure and `OSError`
    on a transport one, exactly the two shapes `_Run.page` and the route helpers expect."""
    hdr = {**_UA, "Accept-Language": accept_language(lang)}
    if referer:
        hdr["Referer"] = referer
    r = pf.get(url, headers=hdr, timeout=timeout, retries=1, leg=LEG, max_bytes=2_000_000)
    _LAST.resp = r
    if r.ok:
        return r.text
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


def land_raw(url: str, body: bytes, ctype: str, *, ground: dict[str, Any],
             reason: str) -> dict[str, Any] | None:
    """Land one fetched body raw in the lake vault with point-in-time stamps (available_time is
    the moment it was fetched; source_hash is the sha256 of the bytes). Content-addressed:
    the same bytes land once. Returns the landing, or None when nothing was written or found."""
    if not body:
        return None
    digest = hashlib.sha256(body).hexdigest()
    sid = RAW_PREFIX + hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
    d = RAW_VAULT / sid
    blob = d / f"{digest[:16]}.gz"
    fresh = not blob.exists()
    now = datetime.now(tz=UTC).isoformat(timespec="seconds")
    try:
        if fresh:
            d.mkdir(parents=True, exist_ok=True)
            blob.write_bytes(gzip.compress(body))
            _atomic_text(blob.with_name(f"{digest[:16]}.meta.json"), json.dumps({
                "source_id": sid, "url": url, "content_type": ctype, "sha256": digest,
                "bytes": len(body), "fetched_utc": now, "available_time": now,
                "source_hash": digest, "landed_by": "deep_forest_miner", "reason": reason,
                "ground": ground.get("name"), "region": ground.get("region"),
                "language": ground.get("language")}, ensure_ascii=False, indent=1))
    except OSError:
        return None
    return {"source_id": sid, "sha256": digest, "new": fresh, "reason": reason}


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
        # A HELD ground (METHOD_BLOCKED or NEEDS_KEY) is not scheduled: reported HELD by name.
        if held_ground(g):
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
        #: Per-URL fetch errors (http code, transport, render, terms, anti-bot). They belong to
        #: the ground being worked and are folded into ITS row by `work`; `status` holds ground
        #: rows only. The report's `fetch_notes` reads the first forty of these.
        self.fetch_errors: list[dict[str, Any]] = []
        self.frontier: list[tuple[str, str, str]] = []
        #: Pages a landing cap deferred to the next pass (shared by forks; see `_defer_raw`).
        self.raw_deferred: list[dict[str, str]] = []
        self.counts = {"queries": 0, "pages": 0, "transcripts": 0, "rendered": 0,
                       "dropped_venue": 0, "dropped_unmappable": 0, "duplicate_mechanisms": 0,
                       "claims_seen_before": 0, "net_failures": 0, "dataset_pages": 0,
                       "dataset_endpoints": 0, "feeds": 0, "ccindex_queries": 0,
                       "landed_raw": 0, "landed_raw_new": 0, "urls_new": 0}
        #: Shared by every fork of this run: the network verdict and its failure streak.
        self._shared: dict[str, Any] = {"network": None, "fails": 0}
        self._lock = threading.RLock()
        self.render_used = 0
        self.ground: dict[str, Any] = {}
        self.ground_claims: list[dict[str, Any]] = []
        self.mech_keys: set[str] = set()

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
        f.fetch_errors = []
        f.counts = dict.fromkeys(self.counts, 0)
        f.ground, f.ground_claims = {}, []
        f.render_used = 0
        return f

    def merge(self, f: _Run) -> None:
        with self._lock:
            self.new.extend(f.new)
            self.datasets.extend(f.datasets)
            self.status.extend(f.status)
            if len(self.fetch_errors) < 200:
                self.fetch_errors.extend(f.fetch_errors[:40])
            self.frontier.extend(f.frontier)
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
        # A HELD source (METHOD_BLOCKED or NEEDS_KEY) is refused before any request; it
        # is not a transport failure and never counts toward the NO_NETWORK verdict.
        pol = policy_of_url(url)
        if pol["status"] in HOLDING:
            self.fetch_errors.append({"url": url, "held": pol["status"], "source": pol["source"]})
            return ""
        if not self._net_ok():
            return ""
        try:
            _LAST.resp = None
            body = _http(url, referer=referer, lang=self.lang)
            self._note_net(True)
            self.counts["pages"] += 1
            if len(body) < 40_000:
                m = _ANTI_BOT_PAGE.search(body)
                if m:
                    # RECORDED, never routed around: no retry with other headers.
                    self.fetch_errors.append({"url": url, "anti_bot": m.group(0)[:40]})
                    return body
            self._land_if_dropped(url, body, pol["status"])
            return body
        except urllib.error.HTTPError as exc:
            self._note_net(True)
            self.fetch_errors.append({"url": url, "http": exc.code})
            return ""
        except Exception as exc:
            self._note_net(False)
            self.fetch_errors.append({"url": url,
                                      "error": f"{type(exc).__name__}: {str(exc)[:80]}"})
            return ""

    def _defer_raw(self, url: str, cap: str) -> None:
        """A per-run landing cap DEFERS a page, never drops it: the URL is released from the
        durable seen-set so the next pass fetches and lands it, and it is named in the report
        (`raw_deferred`). Without the release a capped CSV/PDF was marked seen and never
        fetched again -- mining reduced by a disk bound."""
        with self._lock:
            self.seen_urls.discard(url)
            if len(self.raw_deferred) < 500:
                self.raw_deferred.append({"url": url, "cap": cap})
        key = f"landed_raw_deferred_{cap}"
        self.counts[key] = self.counts.get(key, 0) + 1

    def _land(self, url: str, raw: bytes, ctype: str, reason: str) -> None:
        if self.counts.get("landed_raw", 0) >= RAW_MAX_PER_RUN:
            self._defer_raw(url, "count_cap")
            return
        if self.counts.get("landed_raw_bytes", 0) + len(raw) > RAW_MAX_BYTES_PER_RUN:
            self.counts["landed_raw_skipped_bytes_cap"] = (
                self.counts.get("landed_raw_skipped_bytes_cap", 0) + 1)
            self._defer_raw(url, "bytes_cap")
            return
        got = land_raw(url, raw, ctype, ground=self.ground or {}, reason=reason)
        if got:
            self.counts["landed_raw"] = self.counts.get("landed_raw", 0) + 1
            if got["new"]:
                self.counts["landed_raw_bytes"] = (self.counts.get("landed_raw_bytes", 0)
                                                   + len(raw))
            self.counts["landed_raw_new"] = (self.counts.get("landed_raw_new", 0)
                                             + int(bool(got["new"])))

    def _land_if_dropped(self, url: str, body: str, status: str) -> None:
        """Land the raw bytes of a page dropped for its form: a non-HTML body, or a page whose
        visible text is under MIN_PAGE_TEXT. IDEAS_ONLY pages are never landed as data."""
        if status == IDEAS_ONLY or not body:
            return
        resp = getattr(_LAST, "resp", None)
        ok = resp is not None and resp.ok and str(resp.url) == url
        raw = (resp.body or body.encode("utf-8")) if ok else body.encode("utf-8")
        ctype = str(resp.content_type or "") if ok else ""
        if ctype and "html" not in ctype.lower() and _NON_HTML_TYPE.search(ctype):
            self._land(url, raw, ctype, f"format:{ctype.split(';')[0].strip()}")
        elif len(html_text(body)) < MIN_PAGE_TEXT:
            final = str(resp.url) if resp is not None and getattr(resp, "url", None) else url
            if _tf.login_wall(url) or _tf.login_wall(final) or _PASSWORD_FORM.search(raw):
                self.counts["landed_raw_skipped_login"] = (
                    self.counts.get("landed_raw_skipped_login", 0) + 1)
                return
            self._land(url, raw, ctype, "short_page")

    def rendered(self, url: str) -> str:
        pol = policy_of_url(url)
        if pol["status"] in HOLDING:
            self.fetch_errors.append({"url": url, "held": pol["status"], "source": pol["source"]})
            return ""
        try:
            from libs.data.render_fetch import render
            page, err = render(url, timeout_s=25.0, lang=locale_of(self.lang)[0])
        except Exception as exc:
            page, err = "", f"{type(exc).__name__}: {str(exc)[:80]}"
        if err:
            self.fetch_errors.append({"url": url, "render": err[:120]})
            return ""
        self.counts["rendered"] += 1
        return page

    # ------------------------------------------------------------------ what a page yields
    def take(self, text: str, *, ground: dict[str, Any], url: str, title: str,
             route: str, grade: str | None = None, extra: dict[str, Any] | None = None,
             page: str = "") -> int:
        if page and str(ground.get("kind")) == "competition":
            self._competition(page, ground=ground, url=url)
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
                   # The source's policy status rides along as a LABEL (rule 4: provenance
                   # never blocks a claim or a cell; only live input data is checked).
                   "source_policy": policy_of_url(url)["status"],
                   "fetched_utc": now, "score": mc.claim_score(c), **(extra or {})}
            if dup_key:
                self.counts["duplicate_mechanisms"] += 1
                row["duplicate_of_key"] = c["mechanism_key"]
            self.new.append(row)
            self.ground_claims.append(row)
            n += 1
            self._provenance(row)
        return n

    def _competition(self, page: str, *, ground: dict[str, Any], url: str) -> int:
        """Append a competition page's ranking rows to the genome's competition ledger."""
        try:
            meta = page_meta(page)
            now = datetime.now(tz=UTC).isoformat(timespec="seconds")
            rows = competition_rows(page, ground=str(ground.get("name")), url=url,
                                    published_time=meta.get("published_time"),
                                    available_time=now, region=str(ground.get("region") or ""),
                                    language=str(ground.get("language") or ""))
            if not rows:
                return 0
            with self._lock, _xlock("trader_genome_competition"):
                COMPETITION_LEDGER.parent.mkdir(parents=True, exist_ok=True)
                with COMPETITION_LEDGER.open("a", encoding="utf-8") as fh:
                    for row in rows:
                        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            self.counts["competition_rows"] = self.counts.get("competition_rows", 0) + len(rows)
            return len(rows)
        except Exception as exc:                 # a table we cannot read never costs the claims
            self.status.append({"url": url, "competition_table": f"{type(exc).__name__}: {exc}"})
            return 0

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

    def dataset(self, page: str, *, ground: dict[str, Any], url: str, title: str) -> int:
        """A page that hands over DATA: its endpoints become a discovery row in the crawler's
        own shape (kind "dataset"), so `acquire_datasets` registers them, and a row in the
        datasets ledger, so the report can count what each region's forest yields."""
        # IDEAS_ONLY sources are read for mechanism claims and NEVER registered as live input
        # data: their endpoints are not handed to the acquirer (SOURCE_POLICY).
        eps = [] if policy_of_url(url)["status"] == IDEAS_ONLY else data_endpoints(page, url)
        if ground.get("kind") != "dataset" and not eps:
            return 0
        if not eps and page and policy_of_url(url)["status"] != IDEAS_ONLY:
            # A dataset page with no endpoints is a page, not a yield -- and its raw bytes are
            # landed so the parser can find the table the link scan could not.
            self._land(url, page.encode("utf-8"), "text/html", "dataset_no_endpoints")
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
        self.datasets.append(row)
        self.counts["dataset_pages"] += 1
        self.counts["dataset_endpoints"] += len(eps)
        self.follow(url, title, via=f"{SOURCE}:{ground.get('name')}:dataset")
        return len(eps)

    def follow(self, url: str, anchor: str, via: str) -> None:
        if not url.startswith(("http://", "https://")):
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
        # THE PERMITTED FALLBACK: no engine returned a row (an anti-bot shell, or nothing), so
        # the Common Crawl URL index enumerates the ground's own site -- once per ground per
        # pass -- and those pages are read from the site itself.
        if not engines and site and not self.over() and self._net_ok():
            cc = self.ground_ccindex(g, site)
            out["claims"] = claims + int(cc.pop("claims_ccindex", 0))
            out["pages"] = pages + int(cc.get("ccindex_pages") or 0)
            out.update(cc)
            out["errors"] = (errors[:3] + list(out.pop("cc_errors", [])))[:5]
        return out

    def ground_ccindex(self, g: dict[str, Any], site: str) -> dict[str, Any]:
        """One CDX query for `site`, then up to CCINDEX_PAGES of its pages through `page`."""
        self.counts["ccindex_queries"] = self.counts.get("ccindex_queries", 0) + 1
        urls, err = ccindex_pages(site)
        errs = [f"ccindex: {err}"] if err else []
        claims = pages = 0
        for u in urls:
            self.follow(u, "", via=f"{SOURCE}:{g.get('name')}:ccindex")
        for u in urls[:CCINDEX_PAGES]:
            if self.over():
                break
            body = self.page(u)
            if len(html_text(body)) >= MIN_PAGE_TEXT:
                pages += 1
                claims += self._read_page(g, body, u, _title(body) or u, "search:ccindex")
            time.sleep(1.0)
        res: dict[str, Any] = {"ccindex": len(urls), "ccindex_pages": pages, "cc_errors": errs}
        if urls:
            res["route_used"] = "search:ccindex"
        res["claims_ccindex"] = claims
        return res

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
        """METHOD_BLOCKED (login): a nitter mirror is a third-party front-end that exists to get
        around X's login wall. The permitted route to X posts is X's official API (NEEDS_KEY
        until a key is on the box). `work` holds the ground first; nothing here fetches."""
        return {**held_row(_resolve("nitter")), "claims": 0,
                "mirrors": len(g.get("mirrors") or [])}

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
            self.status.append({**row, "status": "NO_ADDRESS", "cause": "NO_ADDRESS",
                                "why": f"no site and no url to reach for: {g.get('why')}"})
            return
        # THE METHOD FENCE: a ground whose only route would bypass a login (or whose API key is
        # absent) is HELD, labelled with which, and not fetched (not even with
        # --no-fetch would it be), and is reported HELD -- never yield, never BLOCKED.
        held = held_ground(g)
        if held:
            self.status.append({**row, **held_row(held), "claims": 0})
            return
        if not self.fetch:
            self.status.append({**row, "status": "SKIPPED", "why": "--no-fetch"})
            return
        if not self._net_ok():
            self.status.append({**row, "status": "NO_NETWORK", "cause": "NO_NETWORK",
                                "why": "three straight transport failures on this box"})
            return
        self.ground, self.ground_claims = g, []
        seen_before = self.counts["claims_seen_before"]
        errs_before = len(self.fetch_errors)
        landed_before = self.counts.get("landed_raw", 0)
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
                                            "items", "tweets", "channels", "feeds", "articles",
                                            "ccindex")
                      ) or self.counts["claims_seen_before"] > seen_before
        # THE YIELD RULE IS PER KIND (2026-10-13). A ground yields when it produced claims, OR
        # data endpoints (a dataset row with 0 endpoints is a PAGE, not a yield), OR -- for an
        # academic ground -- papers. The rule that fired is recorded on the row.
        mine = [d for d in self.datasets if d.get("ground") == name]
        endpoints = sum(int(d.get("n_endpoints") or 0) for d in mine)
        n_papers = (int(out.get("papers") or 0)
                    if route == "papers" or str(g.get("kind") or "") in ACADEMIC_KINDS else 0)
        rule = yield_rule(n_claims, endpoints, n_papers)
        status = "PRODUCTIVE" if rule else ("REACHED_NO_CLAIMS" if reached else "BLOCKED")
        # THE GROUND'S OWN FETCH ERRORS travel on its row, so its blocker names a cause.
        fetched_errs = self.fetch_errors[errs_before:]
        if fetched_errs:
            out["errors"] = [*list(out.get("errors") or [])[:4],
                             *[_fmt_fetch_error(e) for e in fetched_errs[:4]]]
            out["fetch_errors"] = fetched_errs[:8]
        extra: dict[str, Any] = {}
        if rule:
            extra["yield_rule"] = rule
        if status == "BLOCKED":
            from research.alt_data_yield import classify_cause
            cause, code = classify_cause(
                status, [*fetched_errs, *(out.get("errors") or [])[:4],
                         *([out["error"]] if out.get("error") else [])],
                over_budget=self.over())
            extra["cause"] = cause
            if code:
                extra["http_code"] = code
        classes: dict[str, int] = {}
        for c in self.ground_claims:
            k = str(c.get("mechanism_class"))
            classes[k] = classes.get(k, 0) + 1
        self.status.append({**row, "status": status, **out, **extra,
                            "elapsed_s": round(time.monotonic() - t0, 1), "classes": classes,
                            # ORTHOGONALITY: a ground that yields only momentum says so.
                            "momentum_only": bool(classes) and set(classes) <= {"momentum"},
                            "datasets": len(mine), "endpoints": endpoints,
                            # raw pages landed for the parser: counted, never a yield
                            "landed_raw": self.counts.get("landed_raw", 0) - landed_before,
                            # the per-ground DELTA against the durable seen-sets
                            "delta": {"urls_new": self.counts.get("urls_new", 0) - urls_before,
                                      "claims_new": n_claims,
                                      "claims_seen_before": (self.counts["claims_seen_before"]
                                                             - seen_before)}})


#: Ground kinds whose papers count as yield on their own (rule `papers`).
ACADEMIC_KINDS: frozenset[str] = frozenset({"academic"})


def yield_rule(claims: int, endpoints: int, papers: int) -> str:
    """The rule a ground's attempt yielded by, or "" -- claims, else endpoints, else papers."""
    if claims > 0:
        return "claims"
    if endpoints > 0:
        return "endpoints"
    if papers > 0:
        return "papers"
    return ""


def _fmt_fetch_error(e: dict[str, Any]) -> str:
    u = str(e.get("url") or "")[:100]
    if e.get("held"):
        return f"{e['held']}:{e.get('source')} {u}"
    if e.get("anti_bot"):
        return f"anti-bot page ({e['anti_bot']}) {u}"
    if e.get("http") is not None:
        return f"HTTP {e['http']} {u}"
    if e.get("render"):
        return f"render: {e['render']} {u}"
    return f"{e.get('error') or 'fetch failed'} {u}"


# ------------------------------------------------------------ competition ranking tables

#: Header vocabulary of public futures/FX competition ranking tables. Based on the published
#: layout of the 期货日报 全国期货(期权)实盘交易大赛 ranking pages (名次 / 参赛者 / 净值 /
#: 累计净值增长率 / 最大回撤 / 风险度 / 组别 / 状态) and its English and Russian equivalents
#: (MOEX ЛЧИ: Место / Участник / Доходность). A column is matched by substring.
_COMP_COLS: dict[str, tuple[str, ...]] = {
    "rank": ("名次", "排名", "rank", "место", "#"),
    "name": ("参赛者", "参赛账户", "昵称", "选手", "账户", "trader", "participant", "участник",
             "name"),
    "nav": ("净值", "nav", "权益"),
    "return_pct": ("收益率", "增长率", "return", "доходность", "profit %"),
    "max_dd_pct": ("回撤", "drawdown", "просадка"),
    "group": ("组别", "group", "division", "лига"),
    "status": ("状态", "status", "статус"),
}
#: Words that put a competitor in the graveyard: a blown, liquidated, withdrawn or disqualified
#: account. Matched against the row's status cell and its name cell.
_COMP_DEAD = ("爆仓", "清盘", "退赛", "出局", "淘汰", "强平", "取消资格", "blown", "liquidated",
              "withdrawn", "disqualified", "выбыл", "дисквал")


def _pct(v: str) -> float | None:
    t = str(v or "").replace(",", "").replace("%", "").replace("\uff05", "").strip()
    try:
        return float(t)
    except ValueError:
        return None


def _tables(page: str) -> list[list[list[str]]]:
    from html.parser import HTMLParser

    class _P(HTMLParser):
        def __init__(self) -> None:
            super().__init__(convert_charrefs=True)
            self.tables: list[list[list[str]]] = []
            self.row: list[str] | None = None
            self.cell: list[str] | None = None

        def handle_starttag(self, tag: str, attrs: Any) -> None:
            if tag == "table":
                self.tables.append([])
            elif tag == "tr" and self.tables:
                self.row = []
            elif tag in ("td", "th") and self.row is not None:
                self.cell = []

        def handle_endtag(self, tag: str) -> None:
            if tag in ("td", "th") and self.row is not None and self.cell is not None:
                self.row.append(" ".join("".join(self.cell).split()))
                self.cell = None
            elif tag == "tr" and self.row is not None and self.tables:
                if self.row:
                    self.tables[-1].append(self.row)
                self.row = None

        def handle_data(self, data: str) -> None:
            if self.cell is not None:
                self.cell.append(data)

    p = _P()
    p.feed(page)
    return p.tables


def competition_rows(page: str, *, ground: str, url: str, published_time: str | None,
                     available_time: str, region: str = "", language: str = ""
                     ) -> list[dict[str, Any]]:
    """Every competitor row of every ranking table on a page, the dead ones included.

    A table qualifies when its header names a competitor column and at least one of NAV /
    return / drawdown. Values are kept verbatim beside their parse; an unparseable number is
    None, never zero. PIT: a row is knowable from the FETCH (`knowable_from` = available_time).
    Ranking tables are republished in place under one URL, so the page's meta date says when the
    page was first published, not when THESE standings were; the row a fetch reads may be weeks
    newer than that date. `published_time` is kept as provenance only.
    """
    out: list[dict[str, Any]] = []
    for t in _tables(page):
        if len(t) < 2:
            continue
        head = [h.lower() for h in t[0]]
        col: dict[str, int] = {}
        for key, words in _COMP_COLS.items():
            for i, h in enumerate(head):
                if i in col.values():
                    continue
                if any(w.lower() in h for w in words):
                    col[key] = i
                    break
        if "name" not in col or not ({"nav", "return_pct", "max_dd_pct"} & set(col)):
            continue
        for cells in t[1:]:
            if len(cells) <= col["name"]:
                continue

            def cell(k: str, cells: list[str] = cells, col: dict[str, int] = col) -> str:
                return cells[col[k]] if k in col and col[k] < len(cells) else ""

            name = cell("name").strip()
            if not name:
                continue
            nav, ret, dd = _pct(cell("nav")), _pct(cell("return_pct")), _pct(cell("max_dd_pct"))
            status = cell("status")
            dead_word = next((w for w in _COMP_DEAD if w in status.lower() or w in name.lower()),
                             None)
            if dead_word or (nav is not None and nav <= 0.05) or (ret is not None and ret <= -95.0):
                outcome = "BLOWN"
            else:
                outcome = "ALIVE"
            raw = "|".join(cells)
            out.append({
                "ground": ground, "url": url, "region": region, "language": language,
                "name": name, "rank": cell("rank") or None, "group": cell("group") or None,
                "nav": nav, "return_pct": ret, "max_dd_pct": (-abs(dd) if dd is not None else None),
                "status_text": status or None, "outcome": outcome,
                "outcome_why": (f"status/name says {dead_word!r}" if dead_word else
                                "NAV/return at the blow-up floor" if outcome == "BLOWN" else
                                "listed in the ranking"),
                "published_time": published_time, "available_time": available_time,
                "knowable_from": available_time,
                "row_hash": hashlib.sha256(f"{url}|{raw}".encode()).hexdigest()[:16],
                "raw": raw[:400]})
    return out


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
    "NO_NETWORK": "BLOCKED", "UNREACHABLE": "BLOCKED", "NO_ADDRESS": "BLOCKED",
    # METHOD_BLOCKED / NEEDS_KEY: HELD, apart from BLOCKED and from yield.
    "HELD": "HELD",
    # Pre-ruling spellings of a hold, so an older status row still reads.
    "METHOD_BLOCKED": "HELD", "NEEDS_KEY": "HELD",
    "BLOCKED_WITH_SUBSTITUTE": "BLOCKED", "BLOCKED_TERMS": "BLOCKED",
}


def _blocker(s: dict[str, Any]) -> str:
    """The frontier blocker: the closed-enum cause first (`HTTP_4xx(403): ...`), then the
    detail, so the yield artifact can count causes instead of reading the word BLOCKED."""
    from research.alt_data_yield import cause_label, classify_cause
    cause = str(s.get("cause") or "")
    code = s.get("http_code")
    if not cause:
        cause, code = classify_cause(str(s.get("status") or ""),
                                     [*(s.get("fetch_errors") or []), *(s.get("errors") or []),
                                      *([s["error"]] if s.get("error") else [])])
    errs = s.get("errors") or []
    detail = str(s.get("why") or s.get("error") or (errs[0] if errs else "") or "")
    return f"{cause_label(cause, code)}: {detail}".strip(": ")[:300]


def _frontier_path() -> Path:
    """Beside the cursor file, so a test that redirects SEEN redirects this too."""
    return SEEN.with_name(FRONTIER_NAME)


def _record_frontier(grounds_status: list[dict[str, Any]],
                     grounds: list[dict[str, Any]]) -> dict[str, Any]:
    """Every ground's hunt outcome in `libs.research.hunt_frontier`'s vocabulary, stamped with
    the ground's language and region, so the four outcomes roll up PER LANGUAGE.

    Every registered ground is in the state (NAMED_ONLY until a run reaches it), so the
    denominator is the whole registry rather than the grounds one budget happened to touch. A
    ground already hunted is never demoted back to NAMED_ONLY by a run that skipped it.
    """
    from libs.research import hunt_frontier as hf

    path = _frontier_path()
    state = hf.load(path)
    for g in grounds:
        name = str(g.get("name") or "")
        held = held_ground(g) if name else None
        if held:
            # A HELD ground is HELD whatever an older pass recorded; never NAMED_ONLY
            # frontier work, never BLOCKED. Recording it is not an attempt.
            v = state.vectors.get(name)
            if v is None or v.outcome != "HELD":
                hf.record(state, name, outcome="HELD", blocker=_blocker(held_row(held)),
                          language=str(g.get("language") or ""),
                          region=str(g.get("region") or ""))
            continue
        prev = state.vectors.get(name) if name else None
        if name and (prev is None or prev.outcome == "HELD"):
            # RE-ADMITTED (2026-10-13): a ground an older policy held is frontier work again.
            hf.record(state, name, outcome="NAMED_ONLY", language=str(g.get("language") or ""),
                      region=str(g.get("region") or ""))
    for s in grounds_status:
        name = str(s.get("ground") or "")
        outcome = _FRONTIER_OUTCOME.get(str(s.get("status") or ""))
        if not name or outcome is None:
            continue
        hf.record(state, name, outcome=outcome, findings=int(s.get("claims") or 0),
                  blocker=(_blocker(s) if outcome in ("BLOCKED", "HELD") else ""),
                  language=str(s.get("language") or ""), region=str(s.get("region") or ""))
    hf.save(state, path)
    summary = hf.summarise(state)
    return {k: summary.get(k) for k in ("vectors", "unhunted", "blocked", "held", "off_cooldown",
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
        frontier_state = _hf.load(_frontier_path())
    except Exception:  # a damaged accounting file may never stop the miner
        frontier_state = None
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
                                       "languages": [], "held": 0})
        if held_ground(g):
            # Registered, never workable: counted apart, so `worked == grounds` stays a
            # statement about the grounds the desk may actually fetch.
            b["held"] += 1
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
                frontier = _record_frontier(rest, grounds)
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
           # Registered grounds HELD by their source policy (METHOD_BLOCKED or NEEDS_KEY):
           # named here so the gap is visible; the frontier records them HELD.
           "held": {str(g.get("name")): str(p["status"]) for g in grounds
                    for p in [held_ground(g)] if p},
           "yield_rules": {k: sum(1 for s in grounds_status if s.get("yield_rule") == k)
                           for k in ("claims", "endpoints", "papers")},
           "blocked_causes": {c: sum(1 for s in grounds_status
                                     if s.get("status") == "BLOCKED" and s.get("cause") == c)
                              for c in sorted({str(s.get("cause")) for s in grounds_status
                                               if s.get("status") == "BLOCKED"})},
           "momentum_only_grounds": [s.get("ground") for s in grounds_status
                                     if s.get("momentum_only")],
           "by_region": by_region,
           "languages": sorted({str(g.get("language")) for g in grounds if g.get("language")}),
           "frontier": frontier,
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
           "fetch_notes": r.fetch_errors[:40],
           "raw_deferred": r.raw_deferred[:200],
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
                                 runs=_runs_path(), sources=SOURCES, datasets=DATASETS)
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
    outcome; this keeps the COUNTS the yield artifact needs. A success is an attempt whose
    per-kind yield rule fired (claims, endpoints, or papers for an academic ground) -- the same
    rule the frontier outcome uses, so the two never disagree. A dataset row with 0 endpoints is
    counted under `datasets` and is NOT a success."""
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
            eps = int(s.get("endpoints") or 0)
            # The rule the attempt yielded by; a PRODUCTIVE row written without one (an older
            # status row) reads its rule off its own counts, so a success is never lost.
            rule = str(s.get("yield_rule") or "") or (
                yield_rule(rows, eps, 0) if s.get("status") == "PRODUCTIVE" else "")
            held = s.get("status") == "HELD"
            # A hold is not an attempt: nothing was fetched.
            e["attempts"] = int(e.get("attempts") or 0) + (0 if held else 1)
            e["successes"] = int(e.get("successes") or 0) + (1 if rule else 0)
            e["rows"] = int(e.get("rows") or 0) + rows
            e["datasets"] = int(e.get("datasets") or 0) + dsets
            e["endpoints"] = int(e.get("endpoints") or 0) + eps
            e["landed_raw"] = int(e.get("landed_raw") or 0) + int(s.get("landed_raw") or 0)
            if rule:
                e["last_yield_rule"] = rule
                rules = e.get("yield_rules") if isinstance(e.get("yield_rules"), dict) else {}
                rules[rule] = int(rules.get(rule) or 0) + 1
                e["yield_rules"] = rules
            # THE STANDING CAUSE of this attempt's failure (closed enum), or "" when it reached.
            e["last_cause"] = str(s.get("cause") or "")
            if s.get("http_code"):
                e["last_http_code"] = s.get("http_code")
            else:
                e.pop("last_http_code", None)
            e["last_status"] = s.get("status")
            e["last_attempt"] = now
            e["last_elapsed_s"] = s.get("elapsed_s")
            e["region"] = s.get("region")
            e["language"] = s.get("language")
            e["route"] = s.get("route")
            err = s.get("error") or "; ".join(str(x) for x in (s.get("errors") or [])[:2]) \
                or (s.get("why") if s.get("status") not in ("PRODUCTIVE",
                                                            "REACHED_NO_CLAIMS") else "")
            if rule:
                e["last_success"] = now
            if err or s.get("status") in ("BLOCKED", "NO_ADDRESS", "UNREACHABLE", "HELD"):
                cause = str(s.get("cause") or "")
                text = str(err or s.get("status"))
                e["last_error"] = (f"{cause}: {text}" if cause and not text.startswith(cause)
                                   else text)[:200]
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
                _record_frontier(sts, [])
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
