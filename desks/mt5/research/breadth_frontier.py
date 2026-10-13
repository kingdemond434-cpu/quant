"""THE BREADTH FRONTIER -- the coverage map of the outside world and the ontology that never closes.

    python desks/mt5/research/breadth_frontier.py --once            # the hourly leg
    python desks/mt5/research/breadth_frontier.py --once --out X    # dry run to another path

THE PRINCIPAL, 2026-10-10: four permanent breadth engines, each on a clock with an artifact --
DATASET DISCOVERY, a COVERAGE MAP (source x geography x language x actor x asset x horizon, the
empty cells ranked as the next hunt targets), REPRESENTATION DISCOVERY and an UNKNOWN-UNKNOWN
FRONTIER that proposes data types the desk has never named -- plus ten FRINGE FAMILIES placed
explicitly in the universe.

TWO OF THE FOUR ALREADY RUN, AND THIS FILE DOES NOT REBUILD THEM (no second lane):

    DATASET DISCOVERY        research/world_dataset_hunter.py  (leg world_dataset_hunt,
                             reports/DATASET_HUNT.json), research/free_stack_hunter.py (leg
                             free_stack_hunt, its catalogue feed) and the world crawler's dataset
                             endpoints (data/intelligence/world/discoveries_*.json). What they
                             lacked was ONE count of new datasets across all three doors and a
                             queue of the fringe sources whose terms are cleared; section
                             `dataset_discovery` below is that count and that queue.
    REPRESENTATION DISCOVERY research/representation_forge.py  (leg representation_forge,
                             reports/REPRESENTATION_FORGE.json; PR #297 extends it with controls,
                             vintages and lifecycle). It is READ here, into section
                             `representation_discovery`, and never re-implemented.

THE TWO THAT DID NOT EXIST, and why the near neighbours are not them:

    COVERAGE MAP        `coverage_tensor` holds the WORLD and FOREST ladders over the registry's
                        evidence; `source_frontier` holds Chao1 over claim cells. Neither has an
                        ACTOR or a HORIZON axis, and neither reads the grounds, the alt-data
                        yield, the free-stack roster and the legacy universe map side by side.
                        This map does, and it marks an absent input UNMEASURED, never empty.
    UNKNOWN-UNKNOWNS    `frontier_intel/unknowns.py` proposes unknown FIRMS and CAPABILITIES;
                        `research/unknown_unknowns.py` feeds the search model RESIDUALS. Neither
                        reads what the crawlers FOUND -- field names in endpoint paths, feed
                        types, publisher kinds -- against what the desk's ontology can name.
                        This one does, and it only ever ADDS a proposal: the ontology does not
                        close because a pass found nothing new.

THE MATRIX IS STRUCTURED, NOT A BLIND CROSS PRODUCT. Geography x language is restricted to the
pairs a region declares (plus English, plus any pair a source actually occupies), and source x
actor to the actors a source kind can carry (a central bank is not a retail forum). Inside that
frame every cell is FILLED (a source with every axis declared and either a measured yield or a
second independent source), THIN (something reaches it, but only through an undeclared axis, an
unmeasured yield, or one source) or EMPTY. An undeclared axis is never read as coverage of every
value -- it reaches them THIN at most. Empty cells are ranked by an argued product (each factor in
the row): asset weight in the hypothesis-lane universe x geography relevance to an MT5 instrument
x novelty of the cell's axis values x the source kind's measured yield prior.

NO SOURCE IS BANNED AS A CATEGORY; ONLY A METHOD IS OFF (principal's ruling, 2026-10-13). Every
source carries an access status -- API_PERMITTED, NEEDS_KEY, PUBLIC_PAGE, IDEAS_ONLY or
METHOD_BLOCKED with its reason. A live status needs a READ terms page with a verbatim quote; an
UNREAD source is IDEAS_ONLY and never fetched as live input; a ground whose fetches met an
anti-bot wall is METHOD_BLOCKED (the wall is recorded, never routed around). Idea provenance never
blocks a cell: access is censused beside the map and never changes a cell's state. This organ
fetches NOTHING -- it reads artifacts on this tree -- so a live source is only ever named as an
acquisition target for the organs that own fetching.

Nothing here sizes, gates, judges or charges a trial; it measures and proposes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
import time
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

BASE = Path(__file__).resolve().parents[1]
REPO = BASE.parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

#: Module globals, not frozen constants: the tests point the whole organ at a tmp desk.
DATA = BASE / "data"
REPORTS = BASE / "reports"
ALT_DATA_YIELD = REPORTS / "ALT_DATA_YIELD.json"
DEEP_FOREST = DATA / "deep_forest_sources.json"
FREE_STACK = DATA / "free_stack_sources.json"
FREE_STACK_YIELD = REPORTS / "FREE_STACK_YIELD.json"
DISCOVERED_CATALOGUE = DATA / "free_stack" / "discovered_catalogue.json"
UNIVERSE_MAP = REPO / "data" / "data_universe_map.json"
DATA_REGISTRY = DATA / "data_registry.json"
DATASET_HUNT = REPORTS / "DATASET_HUNT.json"
WORLD_CATALOG = DATA / "world_datasets" / "catalog.json"
WORLD_DISCOVERIES = DATA / "intelligence" / "world"
FORGE_REPORT = REPORTS / "REPRESENTATION_FORGE.json"
EFFECTIVE_BREADTH = REPORTS / "EFFECTIVE_BREADTH.json"
FRINGE = DATA / "fringe_families.json"
UNIVERSE = DATA / "universe" / "universe.json"
OUT = REPORTS / "BREADTH_FRONTIER.json"
STATE = DATA / "breadth_frontier" / "state.json"

UNMEASURED = "UNMEASURED"
RULE = ("a cell is FILLED only with every axis declared by a source that has a measured yield or "
        "a second independent source; an undeclared axis reaches THIN at most; an absent input is "
        "UNMEASURED, never empty; nothing here fetches, sizes, judges or charges a trial")

# ------------------------------------------------------------------------------- vocabulary

#: The SOURCE axis, and the actors each kind of source can carry.
SOURCE_ACTORS: dict[str, tuple[str, ...]] = {
    "official_statistics": ("official_sector",),
    "central_bank": ("official_sector",),
    "regulator_filing": ("corporate_issuer", "institutional", "official_sector"),
    "exchange_venue": ("professional_trader", "institutional"),
    "academic_research": ("academic", "institutional"),
    "practitioner_media": ("professional_trader", "institutional", "retail"),
    "community_forum": ("retail", "professional_trader"),
    "competition_leaderboard": ("professional_trader", "retail"),
    "code_repository": ("academic", "professional_trader"),
    "app_attention": ("retail",),
    "physical_sensor": ("physical_economy",),
    "open_catalogue": ("official_sector", "academic", "institutional"),
    "news_events": ("institutional", "retail", "official_sector"),
}
SOURCES: tuple[str, ...] = tuple(SOURCE_ACTORS)
ACTORS: tuple[str, ...] = ("retail", "professional_trader", "institutional", "official_sector",
                           "corporate_issuer", "academic", "physical_economy")
#: The hypothesis-lane asset classes (share CFDs are event-lane only, the two-lanes order).
ASSETS: tuple[str, ...] = ("fx", "metals", "energy", "softs", "indices", "bonds", "crypto_cfd")
HORIZONS: tuple[str, ...] = ("intraday", "daily", "weekly", "monthly_plus")

#: Every source `kind` the grounds, the free stack and the crawler use, mapped to the SOURCE
#: axis. A kind missing here is not dropped: it is an UNMAPPED PUBLISHER KIND, which the unknown
#: frontier proposes as an ontology gap.
KIND_TO_SOURCE: dict[str, str] = {
    "dataset": "open_catalogue", "catalogue": "open_catalogue", "macro": "official_statistics",
    "central_bank_data": "central_bank", "macro_vintages": "official_statistics",
    "forum": "community_forum", "community": "community_forum", "social": "community_forum",
    "qa": "community_forum", "cn_forum": "community_forum", "reddit": "community_forum",
    "telegram": "community_forum", "public_messaging": "community_forum",
    "column": "practitioner_media", "blog": "practitioner_media", "video": "practitioner_media",
    "interview": "practitioner_media", "longform_media": "practitioner_media",
    "research": "practitioner_media", "longform_research": "practitioner_media",
    "academic": "academic_research", "patent": "academic_research",
    "jp_patents": "academic_research",
    "code": "code_repository", "notebook": "code_repository", "repo_archaeology": "code_repository",
    "package": "code_repository",
    "competition": "competition_leaderboard", "verified_leaderboard": "competition_leaderboard",
    "platform_native_strategy": "competition_leaderboard",
    "copy_platform": "competition_leaderboard",
    "regulatory_filing": "regulator_filing", "fund_disclosure": "regulator_filing",
    "enforcement_court": "regulator_filing", "accounting_corporate_events": "regulator_filing",
    "jp_ir": "regulator_filing", "congress": "regulator_filing",
    "exchange_rulebook": "exchange_venue", "futures_term_structure": "exchange_venue",
    "options_volatility": "exchange_venue", "futures_volume_oi": "exchange_venue",
    "cn_exchange": "exchange_venue", "auction_fixing": "exchange_venue",
    "broker_execution_rules": "exchange_venue", "positioning": "exchange_venue",
    "app_rank_apple": "app_attention", "gtrends": "app_attention",
    "digital_activity": "app_attention", "prediction_market": "app_attention",
    "physical_commodity": "physical_sensor", "shipping_supply_chain": "physical_sensor",
    "weather_geospatial": "physical_sensor", "weather_energy": "physical_sensor",
    "shipping_freight": "physical_sensor", "commodity_inventories": "physical_sensor",
    "sentiment_news": "news_events", "archive": "news_events",
    "rates_credit": "official_statistics", "trade_data": "official_statistics",
    "fund_etf_flows": "regulator_filing", "benchmark_flows": "institutional_flow",
    "options_surfaces": "exchange_venue", "physical_premia": "exchange_venue",
    "public_filings": "regulator_filing", "rates_curves": "official_statistics",
    "akshare": "open_catalogue", "tushare": "open_catalogue", "coinpaprika": "open_catalogue",
}
# `institutional_flow` is not a SOURCE value: kept deliberately so the frontier names it.

ACTOR_OF_KIND: dict[str, str] = {
    "community_forum": "retail", "app_attention": "retail",
    "competition_leaderboard": "professional_trader", "exchange_venue": "professional_trader",
    "practitioner_media": "professional_trader", "academic_research": "academic",
    "code_repository": "academic", "official_statistics": "official_sector",
    "central_bank": "official_sector", "regulator_filing": "corporate_issuer",
    "physical_sensor": "physical_economy", "open_catalogue": "official_sector",
    "news_events": "institutional",
}
PARTICIPANT_TO_ACTOR = {"retail_heavy": "retail", "institutional": "institutional",
                        "policy_driven": "official_sector",
                        "settlement_constrained": "professional_trader"}

ASSET_WORDS: dict[str, tuple[str, ...]] = {
    "fx": ("forex", " fx", "fx ", "currency", "exchange rate", "外汇", "為替", "환율", "valuta",
           "usd", "eur", "jpy", "cny", "cnh", "krw", "inr", "carry"),
    "metals": ("gold", "silver", "copper", "nickel", "platinum", "palladium", "aluminium",
               "aluminum", "zinc", "lbma", "黄金", "金价", "金", "白银", "铜", "metal", "xau"),
    "energy": ("oil", "crude", "brent", "wti", "natural gas", "lng", "原油", "energy", "power",
               "electric", "refin", "opec"),
    "softs": ("wheat", "corn", "soy", "sugar", "coffee", "cocoa", "cotton", "grain", "crop",
              "agri", "農", "农", "palm"),
    "indices": ("index", "indices", "nikkei", "s&p", "nasdaq", "dax", "hang seng", "kospi",
                "stock", "equity", "指数", "株", "股"),
    "bonds": ("bond", "yield", "treasury", "gilt", "rates", "curve", "repo", "国债", "国債"),
    "crypto_cfd": ("bitcoin", "btc", "ether", "crypto"),
}
CADENCE_TO_HORIZON = {"hourly": "intraday", "4h": "intraday", "realtime": "intraday",
                      "intraday": "intraday", "daily": "daily", "weekly": "weekly",
                      "monthly": "monthly_plus", "quarterly": "monthly_plus",
                      "annual": "monthly_plus"}

UNIVERSE_CLASS_TO_ASSET = {"Forex": "fx", "Forex Exotics": "fx", "Commodities": "metals",
                           "Energy": "energy", "Soft Commodity": "softs", "Indices": "indices",
                           "Bonds": "bonds", "Crypto": "crypto_cfd"}

#: Region -> the currency code it prices and any MT5 instrument its economy moves directly.
REGION_LINKS: dict[str, tuple[str, ...]] = {
    "cn": ("CNH", "CHINAH", "XCUUSD"), "jp": ("JPY", "JPN225"), "kr": ("NAS100",),
    "tw": ("NAS100",), "hk": ("HKD", "HK50"), "sg": ("SGD",), "vn": ("COFROB",),
    "th": ("SUGAR",), "id": ("XNIUSD",), "my": ("SGD",), "ph": (), "in": ("XAUUSD",),
    "pk": ("COTTON",), "bd": ("COTTON",), "lk": (), "au": ("AUD", "AUS200"), "nz": ("NZD",),
    "sa": ("XBRUSD", "XTIUSD"), "ae": ("XBRUSD",), "tr": ("TRY",), "il": ("ILS",),
    "eg": ("WHEAT",), "za": ("ZAR", "XPTUSD"), "ng": ("XBRUSD",), "ke": ("COFARA",), "ma": (),
    "us": ("USD", "US500", "NAS100", "US30", "US2000"), "gb": ("GBP", "UK100", "UKGILT"),
    "ca": ("CAD", "CA60"), "global": ("USD",), "institutional": ("USD",),
    "de": ("EUR", "CHF", "GER40"), "fr": ("EUR", "FRA40"), "it": ("EUR",), "es": ("EUR", "E35"),
    "nl": ("EUR", "NETH25"), "se": ("SEK",), "dk": ("DKK",), "no": ("NOK",), "fi": ("EUR",),
    "pl": ("PLN",), "cz": ("CZK",), "hu": ("HUF",), "ua": ("WHEAT", "CORN"), "ru": ("RUB",),
    "br": ("BRL", "SOYBEAN", "COFARA"), "mx": ("MXN",), "cl": ("XCUUSD",), "co": ("COFARA",),
    "pe": ("XCUUSD",), "ar": ("SOYBEAN", "CORN"),
}

#: Tokens in the legacy universe map's category names that place it on a geography.
LEGACY_GEO = (("boj", "jp"), ("jpx", "jp"), ("japan", "jp"), ("boe", "gb"), ("gilt", "gb"),
              ("lbma", "gb"), ("ecb", "de"), ("eurex", "de"), ("buba", "de"),
              ("bundesbank", "de"), ("snb", "de"), ("six_", "de"), ("rba", "au"),
              ("rbnz", "nz"), ("riksbank", "se"), ("scb", "se"), ("norges", "no"),
              ("ssb", "no"), ("dn_", "no"), ("dst_", "dk"), ("nbp", "pl"), ("cbr", "ru"),
              ("mnb", "hu"), ("bnr", "ro"), ("bank_of_canada", "ca"), ("hkex", "hk"),
              ("b3_", "br"), ("sge", "cn"), ("cn_", "cn"), ("kr_", "kr"), ("korea", "kr"),
              ("ru_", "ru"), ("fred", "us"), ("cme", "us"), ("ice_", "us"))
#: Category names that are crypto-exchange-native: counted and set aside, never mapped (the
#: MT5 universe mandate). Brand words, not hostnames.
CRYPTO_NATIVE = ("cex", "onchain", "binance", "bybit", "bitmex", "dydx", "kraken", "solana",
                 "deribit", "airdrop", "hyperliquid", "bitfinex", "polymarket", "stablecoin",
                 "flashbots", "mev", "ethpandaops", "bitflyer", "bitbank", "gmo_coin", "kimchi",
                 "usdt", "perp", "coinalyze", "coingecko", "kaiko", "graphsense", "btcsec",
                 "crypto", "funding", "liquidation", "defillama", "fundingpulse", "dune",
                 "farside", "godzilla", "velog", "botter", "cryptopanic", "venue")

#: Feed types the desk's acquirers already read. Anything else seen is proposed.
KNOWN_FEEDS = frozenset({"csv", "tsv", "json", "jsonl", "parquet", "zip", "gz", "xlsx", "xls",
                         "txt", "api", "download", "dataset", "series", "export", "sdmx", "rest",
                         "html", "htm", "php", "aspx", "asp", "jsp", "pdf"})
API_MARKERS = frozenset({"graphql", "odata", "pxweb", "arcgis", "wfs", "wms", "ckan", "socrata",
                         "opendatasoft", "sparql", "oai", "rss", "atom", "geojson", "netcdf",
                         "grib", "hdf5", "sdmx", "jsonstat", "xbrl", "ical", "openapi",
                         "swagger", "erddap", "thredds", "ogc", "kml"})
#: Extensions that are page furniture or executables, never data: ignored, not proposed.
NOT_DATA = frozenset({"css", "js", "png", "jpg", "jpeg", "gif", "svg", "ico", "webp", "woff",
                      "woff2", "ttf", "eot", "exe", "msi", "dmg", "apk", "mp3", "mp4", "webm",
                      "mov", "avi", "map", "doc", "docx", "ppt", "pptx"})
#: Path tokens that say nothing about what the data IS.
STOPWORDS = frozenset({
    "data", "file", "files", "download", "downloads", "index", "table", "tables", "time",
    "series", "excel", "format", "report", "reports", "monthly", "weekly", "daily", "annual",
    "quarterly", "yearly", "year", "month", "latest", "current", "public", "static", "assets",
    "upload", "uploads", "document", "documents", "content", "media", "images", "default",
    "statistics", "statistic", "stats", "stat", "info", "page", "pages", "view", "html", "http",
    "https", "www", "english", "full", "list", "release", "releases", "archive", "archives",
    "other", "total", "main", "summary", "sheet", "sheets", "version", "item", "items", "dataset",
    "datasets", "export", "exports", "api", "rest", "json", "xlsx", "csv", "sdmx", "pdf",
    "manifest", "llms", "humans", "robots", "sitemap", "favicon", "trading", "financial",
    "information", "historical", "mobile", "tipo", "openapi", "swagger"})
#: Words in a fetch error that mean an automation wall answered, not an empty page.
ANTI_BOT = ("anti-bot", "captcha", "cloudflare", "challenge", "access denied", "403")
#: A proposal is offered to the ontology once this many distinct hosts carry it.
PROMOTE_HOSTS = 3
MAX_PROPOSALS = 60
MAX_SEEN = 50_000


# -------------------------------------------------------------------------------- utilities

def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _read(path: Path) -> Any:
    """The parsed file, or None when it is absent or unreadable (the caller names UNMEASURED)."""
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _write(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, ensure_ascii=False, default=str), "utf-8")
    os.replace(tmp, path)


def _text(*parts: Any) -> str:
    return " ".join(str(p) for p in parts if p).lower()


def assets_in(text: str) -> tuple[str, ...]:
    """The asset classes a piece of text names, by declared vocabulary (never a guess)."""
    t = f" {text.lower()} "
    return tuple(a for a in ASSETS if any(w in t for w in ASSET_WORDS[a]))


def horizon_of(cadence: Any) -> str | None:
    return CADENCE_TO_HORIZON.get(str(cadence or "").strip().lower())


# ---------------------------------------------------------------------------- source rows

def _row(origin: str, name: str, *, source: str | None, geo: str | None, langs: Iterable[str],
         actors: Iterable[str] = (), assets: Iterable[str] = (), horizons: Iterable[str] = (),
         yielded: bool | None = None, access: str = "IDEAS_ONLY",
         access_reason: str = "terms not read by this organ") -> dict[str, Any]:
    """One observed source, on the six axes. Empty tuple = the axis is UNDECLARED. `access` is a
    census label only: it never changes what a cell is (idea provenance never blocks a cell)."""
    return {"origin": origin, "name": name, "source": source, "geo": geo,
            "access": access, "access_reason": access_reason,
            "langs": tuple(sorted({str(x) for x in langs if x})),
            "actors": tuple(sorted(set(actors))), "assets": tuple(sorted(set(assets))),
            "horizons": tuple(sorted(set(horizons))), "yielded": yielded}


def rows_from_grounds(doc: Mapping[str, Any] | None, alt: Mapping[str, Any] | None,
                      unmapped: Counter[str]) -> list[dict[str, Any]]:
    """The deep-forest grounds, each with its ALT_DATA_YIELD outcome when that file is read."""
    if not isinstance(doc, Mapping):
        return []
    vectors = (((alt or {}).get("vectors") or {}).get("rows_by_vector") or {}) if alt else {}
    out: list[dict[str, Any]] = []
    for g in [*(doc.get("grounds") or []), *(doc.get("reading_list") or [])]:
        if not isinstance(g, Mapping):
            continue
        kind = str(g.get("dataset_class") or g.get("kind") or "")
        source = KIND_TO_SOURCE.get(kind) or KIND_TO_SOURCE.get(str(g.get("kind") or ""))
        if source is None or source not in SOURCE_ACTORS:
            unmapped[kind or "<none>"] += 1
            continue
        v = vectors.get(str(g.get("name"))) if isinstance(vectors, Mapping) else None
        yielded: bool | None = None
        access, why = "IDEAS_ONLY", "ground terms UNREAD here: mined for ideas, not live input"
        if isinstance(v, Mapping) and v.get("outcome"):
            yielded = str(v["outcome"]) == "YIELDED"
            err = str(v.get("last_error") or "").lower()
            if str(v["outcome"]) == "BLOCKED" and any(w in err for w in ANTI_BOT):
                access, why = "METHOD_BLOCKED", ("an anti-bot / CAPTCHA wall answered; recorded "
                                                 "as the blocker, never routed around")
        text = _text(g.get("name"), g.get("why"), g.get("url"), g.get("dataset_class"))
        out.append(_row("deep_forest", str(g.get("name")), source=source,
                        geo=str(g.get("region") or "") or None,
                        langs=[str(g.get("language") or "")],
                        actors=[ACTOR_OF_KIND[source]], assets=assets_in(text),
                        yielded=yielded, access=access, access_reason=why))
    return out


def rows_from_free_stack(doc: Mapping[str, Any] | None, yld: Mapping[str, Any] | None,
                         unmapped: Counter[str]) -> list[dict[str, Any]]:
    if not isinstance(doc, Mapping):
        return []
    per = {}
    if isinstance(yld, Mapping):
        src = yld.get("sources")
        if isinstance(src, Mapping):
            per = dict(src)
        elif isinstance(src, list):
            per = {str(r.get("id")): r for r in src if isinstance(r, Mapping)}
    out: list[dict[str, Any]] = []
    for s in doc.get("sources") or []:
        if not isinstance(s, Mapping):
            continue
        kind = str(s.get("kind") or "")
        source = KIND_TO_SOURCE.get(kind)
        if source is None or source not in SOURCE_ACTORS:
            unmapped[kind or "<none>"] += 1
            continue
        y = per.get(str(s.get("id")))
        yielded: bool | None = None
        if isinstance(y, Mapping):
            succ = y.get("successes")
            if isinstance(succ, (int, float)):
                yielded = succ > 0
        langs = str(s.get("language") or "").replace("+", "/").split("/")
        if s.get("machine_use_allowed") is True:
            key_env = s.get("key_env")
            access, why = (("NEEDS_KEY", f"{key_env} is not set on this host")
                           if key_env and not os.environ.get(str(key_env))
                           else ("API_PERMITTED", "roster: machine_use_allowed"))
        else:
            access, why = "IDEAS_ONLY", "roster has not proven machine use: ideas only"
        actor = PARTICIPANT_TO_ACTOR.get(str(s.get("participant_structure") or ""))
        text = _text(s.get("name"), s.get("mechanism"), json.dumps(s.get("targets") or ""),
                     s.get("kind"))
        out.append(_row("free_stack", str(s.get("id")), source=source,
                        geo=str(s.get("region") or "") or None,
                        langs=[x for x in langs if x and x != "multi"],
                        actors=[actor] if actor else [], assets=assets_in(text),
                        horizons=[h] if (h := horizon_of(s.get("cadence"))) else [],
                        yielded=yielded, access=access, access_reason=why))
    return out


def rows_from_alt_platforms(alt: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    """The copy-trading / leaderboard platforms ALT_DATA_YIELD tracks: retail and pro traders."""
    if not isinstance(alt, Mapping):
        return []
    plat = ((alt.get("platforms") or {}).get("rows_by_platform") or {})
    out: list[dict[str, Any]] = []
    never = set((alt.get("platforms") or {}).get("never_yielded") or [])
    for pid, r in plat.items() if isinstance(plat, Mapping) else ():
        if not isinstance(r, Mapping):
            continue
        langs = str(r.get("lang") or "").replace("+", "/").split("/")
        best = r.get("best_rows")
        yielded: bool | None = (True if isinstance(best, (int, float)) and best > 0
                                else (False if pid in never else None))
        out.append(_row("alt_platform", str(pid), source="competition_leaderboard",
                        geo=_platform_geo(str(r.get("region") or "")), langs=langs,
                        actors=["retail", "professional_trader"], assets=["fx", "metals"],
                        horizons=["intraday"], yielded=yielded))
    return out


def _platform_geo(region: str) -> str | None:
    r = region.strip().lower()
    return {"cis": "ru", "cn": "cn", "china": "cn", "jp": "jp", "japan": "jp", "br": "br",
            "brazil": "br", "africa": "za", "global": "global", "eu": "de", "asia": "sg",
            "latam": "br", "mena": "ae"}.get(r)


def rows_from_universe_map(doc: Mapping[str, Any] | None
                           ) -> tuple[list[dict[str, Any]], int]:
    """The legacy free-data map: MT5-relevant categories mapped, crypto-native ones counted."""
    if not isinstance(doc, Mapping):
        return [], 0
    out: list[dict[str, Any]] = []
    set_aside = 0
    for cat, entries in (doc.get("sources") or {}).items():
        low = cat.lower()
        if any(w in low for w in CRYPTO_NATIVE):
            set_aside += 1
            continue
        blob = _text(cat, json.dumps(entries, ensure_ascii=False)[:2000])
        geo = next((g for tok, g in LEGACY_GEO if tok in low), "global")
        source = ("central_bank" if any(t in low for t in ("bank", "boj", "boe", "ecb", "snb",
                                                           "rba", "rbnz", "riksbank", "norges",
                                                           "nbp", "cbr", "mnb", "bnr", "buba",
                                                           "dn_"))
                  else "exchange_venue" if any(t in low for t in ("exchange", "eurex", "hkex",
                                                                  "b3_", "lbma", "sge", "cme",
                                                                  "ice_", "six_", "jpx"))
                  else "official_statistics")
        yielded = True if any(w in blob for w in ("adopted", "ingested", "verified-clean",
                                                    "live")) else None
        out.append(_row("universe_map", cat, source=source, geo=geo, langs=["en"],
                        actors=[ACTOR_OF_KIND[source]], assets=assets_in(blob),
                        horizons=["daily"] if "daily" in blob else [], yielded=yielded))
    return out, set_aside


def rows_from_registry(doc: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    """The desk's acquired-dataset registry: an INGESTED row is a measured yield."""
    if not isinstance(doc, Mapping):
        return []
    out: list[dict[str, Any]] = []
    for key, r in (doc.get("datasets") or {}).items():
        if not isinstance(r, Mapping):
            continue
        blob = _text(key, r.get("source"), r.get("notes"), r.get("symbol"), r.get("symbols"))
        life = str(r.get("lifecycle") or "").upper()
        own = "mt5" in blob or "terminal" in blob
        out.append(_row("data_registry", str(key), access="API_PERMITTED" if own else
                        "IDEAS_ONLY", access_reason="the desk's own broker terminal" if own
                        else "terms not read by this organ", source="exchange_venue"
                        if "mt5" in blob or "terminal" in blob else "official_statistics",
                        geo="global", langs=["en"], actors=["professional_trader"]
                        if "mt5" in blob else ["official_sector"], assets=assets_in(blob),
                        yielded=True if life in ("INGESTED", "RESEARCH-USEFUL", "LIVE")
                        else None))
    return out


# ------------------------------------------------------------- independence: which payer is new

#: Which alpha clusters (libs/research/alpha_clusters: one PAYER each, the desk's definition of an
#: independent family) a source kind's information can feed. Declared, so it can be argued with.
#: A cell's value to breadth is the clusters it feeds that the book does not yet occupy.
SOURCE_FEEDS: dict[str, tuple[str, ...]] = {
    "official_statistics": ("event_surprise", "macro_rates", "cross_asset_lead_lag"),
    "central_bank": ("macro_rates", "event_surprise", "news_reaction"),
    "regulator_filing": ("positioning_flow", "event_surprise"),
    "exchange_venue": ("positioning_flow", "options_implied", "fixing_roll_calendar",
                       "relative_value"),
    "academic_research": (),
    "practitioner_media": ("news_reaction", "positioning_flow"),
    "community_forum": ("positioning_flow", "news_reaction"),
    "competition_leaderboard": ("positioning_flow", "execution_entry"),
    "code_repository": ("execution_entry",),
    "app_attention": ("positioning_flow", "news_reaction"),
    "physical_sensor": ("cross_asset_lead_lag", "event_surprise"),
    "open_catalogue": ("macro_rates", "cross_asset_lead_lag"),
    "news_events": ("news_reaction", "event_surprise"),
}
#: Options-implied state needs a listed options market on the asset class.
OPTIONED = frozenset({"fx", "metals", "energy", "indices", "bonds"})
TOP_GAPS = 25
MAX_PER_ASSET = 5


def clusters_fed(source: str, actor: str, asset: str) -> tuple[str, ...]:
    out = [c for c in SOURCE_FEEDS.get(source, ())
           if c != "options_implied" or asset in OPTIONED]
    if actor == "professional_trader" and source in ("exchange_venue",
                                                     "competition_leaderboard"):
        out.append("execution_entry")
    if actor == "retail" and "positioning_flow" not in out:
        out.append("positioning_flow")
    return tuple(dict.fromkeys(out))


def cluster_occupancy() -> tuple[dict[str, float], str]:
    """How NEW each alpha cluster is to the book, from reports/EFFECTIVE_BREADTH.json: empty in
    both the traded and the certified book 1.0, traded but uncertified 0.5, certified 0.0. When
    the report is absent every cluster reads 1.0 and the source says UNMEASURED."""
    doc = _read(EFFECTIVE_BREADTH)
    cl = (doc or {}).get("clusters") if isinstance(doc, Mapping) else None
    if not isinstance(cl, Mapping):
        return {}, UNMEASURED
    certified = set(cl.get("occupied_certified") or [])
    traded = set(cl.get("occupied_traded") or []) | set(cl.get("occupied_either") or [])
    keys = set(SOURCE_FEEDS_ALL) | certified | traded | set(cl.get("empty_in_both") or [])
    return ({k: 0.0 if k in certified else 0.5 if k in traded else 1.0 for k in keys},
            "measured")


def _num(v: Any) -> float:
    return float(v) if isinstance(v, (int, float)) else 0.0


def price_templates() -> tuple[dict[str, int] | None, str]:
    """Per asset class, how many distinct price-family templates (sleeve name minus its symbol)
    the book runs: the parents a new conditioner or regime state spawns indirect children over.
    From reports/EFFECTIVE_BREADTH.json `sleeve_clusters`; absent reads UNMEASURED."""
    doc = _read(EFFECTIVE_BREADTH)
    sc = (doc or {}).get("sleeve_clusters") if isinstance(doc, Mapping) else None
    uni = _read(UNIVERSE)
    if not isinstance(sc, Mapping) or not isinstance(uni, Mapping):
        return None, UNMEASURED
    by: dict[str, set[str]] = defaultdict(set)
    for name in sc:
        sym, _, template = str(name).partition("_")
        cls = UNIVERSE_CLASS_TO_ASSET.get(str((uni.get(sym) or {}).get("asset_class")))
        if cls and template:
            by[cls].add(template)
    return {a: len(by[a]) for a in ASSETS}, "measured"


SOURCE_FEEDS_ALL = frozenset(c for v in SOURCE_FEEDS.values() for c in v) | {"execution_entry"}


# ------------------------------------------------------------------- next actions for the gaps

#: Rows this organ REGISTERED with an existing generic route, each verified twice: its terms are
#: PERMITTED by `libs.research.equivalence_ontology.TERMS_EVIDENCE` (www.eia.gov, quoted there),
#: and the URL is the publisher's own "Download Data (XLS File)" link, read with WebFetch on
#: 2026-10-13. They are seeds in `research/acquire_datasets._SEED_ENDPOINTS`, whose BIFF8 reader
#: already parses the EIA history workbooks; the test pins both facts.
REGISTERED: tuple[dict[str, Any], ...] = (
    {"id": "eia_weekly_crude_stocks", "url": "https://www.eia.gov/dnav/pet/hist_xls/WCESTUS1w.xls",
     "name": "EIA weekly U.S. ending stocks of crude oil (excl. SPR)",
     "cell": {"source": "physical_sensor", "geography": "us", "asset": "energy"},
     "clusters": ("event_surprise", "cross_asset_lead_lag"),
     "route": "acquire_datasets (seed endpoint)", "access": "PUBLIC_PAGE"},
    {"id": "eia_weekly_ng_storage",
     "url": "https://www.eia.gov/dnav/ng/hist_xls/NW2_EPG0_SWO_R48_BCFw.xls",
     "name": "EIA Lower 48 natural gas working underground storage (weekly)",
     "cell": {"source": "physical_sensor", "geography": "us", "asset": "energy"},
     "clusters": ("event_surprise", "cross_asset_lead_lag"),
     "route": "acquire_datasets (seed endpoint)", "access": "PUBLIC_PAGE"},
)
DBNOMICS_KINDS = frozenset({"official_statistics", "central_bank", "open_catalogue"})


def _instrument_assets(instruments: Iterable[str]) -> set[str]:
    doc = _read(UNIVERSE)
    if not isinstance(doc, Mapping):
        return set(ASSETS)
    return {UNIVERSE_CLASS_TO_ASSET[c] for i in instruments
            if (c := str((doc.get(i) or {}).get("asset_class"))) in UNIVERSE_CLASS_TO_ASSET}


def next_actions(top: list[dict[str, Any]], fringe_doc: Mapping[str, Any] | None,
                 fringe_st: Mapping[str, Any], free_stack: Mapping[str, Any] | None,
                 forest: Mapping[str, Any] | None) -> None:
    """Give every ranked gap a concrete candidate source, its access state and the EXISTING
    route it plugs into, best first: a row registered here, a fringe source with live access, a
    free-stack roster row, a deep-forest ground to deepen, DBnomics through world_dataset_hunt,
    and only then a new deep-forest search ground. An UNREAD source is IDEAS_ONLY."""
    access = {s["id"]: s for f in fringe_st.get("families") or [] for s in f["sources"]}
    fringe = []
    for f in (fringe_doc or {}).get("families") or []:
        assets = _instrument_assets((f.get("mt5_mapping") or {}).get("instruments") or [])
        for s in f.get("sources") or []:
            st = access.get(s.get("id")) or {}
            fringe.append((f, s, assets, st))
    for t in top:
        c = t["cell"]
        src, geo, lang, asset = c["source"], c["geography"], c["language"], c["asset"]
        cands: list[dict[str, Any]] = []
        for r in REGISTERED:
            rc = r["cell"]
            if (rc["source"], rc["geography"], rc["asset"]) == (src, geo, asset):
                cands.append({"candidate": r["name"], "url": r["url"], "access": r["access"],
                              "route": r["route"], "registered": True})
        for f, s, assets, st in fringe:
            if (f.get("source_kind") == src and s.get("geo") in (geo, "global")
                    and asset in assets and st.get("access") != "IDEAS_ONLY"):
                cands.append({"candidate": s.get("name"), "url": s.get("url"),
                              "access": st.get("access"), "fringe_family": f.get("id"),
                              "route": (f"collector {s['owner']}" if st.get("stage") in
                                        ("COLLECTOR_EXISTS", "INGESTED") and s.get("owner")
                                        else "free_stack_hunt roster row (data/"
                                             "free_stack_sources.json) -- a new kind needs its "
                                             "fetcher there")})
        for r in (free_stack or {}).get("sources") or []:
            if (KIND_TO_SOURCE.get(str(r.get("kind"))) == src
                    and str(r.get("region")) == geo):
                acc = ("API_PERMITTED" if r.get("machine_use_allowed") is True
                       else "IDEAS_ONLY")
                cands.append({"candidate": r.get("name") or r.get("id"), "url": r.get("url"),
                              "access": acc, "route": "free_stack_hunt (existing roster row: "
                                                      "widen its targets to this asset)"})
        grounds = [g for g in (forest or {}).get("grounds") or []
                   if g.get("region") == geo and KIND_TO_SOURCE.get(
                       str(g.get("dataset_class") or g.get("kind"))) == src]
        for g in grounds[:1]:
            cands.append({"candidate": g.get("name"), "url": g.get("url"),
                          "access": "IDEAS_ONLY",
                          "route": "deep_forest (deepen this existing ground toward "
                                   f"{asset}; terms UNREAD here, so ideas until read)"})
        if src in DBNOMICS_KINDS:
            cands.append({"candidate": f"DBnomics provider(s) for {geo}", "url":
                          "https://db.nomics.world/", "access": "IDEAS_ONLY",
                          "route": "world_dataset_hunt (DBnomics backbone; terms UNREAD by "
                                   "this organ, the hunter owns the door)"})
        cands.append({"candidate": f"new {src.replace('_', ' ')} ground, {geo} ({lang})",
                      "url": None, "access": "IDEAS_ONLY",
                      "route": ("deep_forest search ground (route=search) in "
                                f"data/deep_forest_sources.json: '{src.replace('_', ' ')} "
                                f"{asset} {geo}' in {lang}")})
        t["next_action"] = cands[0]
        t["alternatives"] = cands[1:4]


# ------------------------------------------------------------------------- the coverage map

def _frame(regions: Mapping[str, Any]) -> dict[str, tuple[str, ...]]:
    """Geography -> its languages: the declared ones plus English."""
    out: dict[str, tuple[str, ...]] = {}
    for code, r in regions.items():
        langs = set((r or {}).get("languages") or []) | {"en"}
        out[str(code)] = tuple(sorted(langs))
    return out


def build_map(rows: list[dict[str, Any]], regions: Mapping[str, Any],
              asset_weight: Mapping[str, float], source_prior: Mapping[str, float],
              occupancy: Mapping[str, float] | None = None,
              templates: Mapping[str, int] | None = None) -> dict[str, Any]:
    occupancy = occupancy or {}
    frame = _frame(regions)
    # an occupied pair the frame did not declare is evidence, so the frame grows to hold it
    for r in rows:
        if r["geo"] and r["langs"]:
            for lang in r["langs"]:
                if r["geo"] not in frame or lang not in frame[r["geo"]]:
                    frame[r["geo"]] = tuple(sorted({*frame.get(r["geo"], ()), lang}))
    size = sum(len(langs) for langs in frame.values()) * sum(
        len(a) for a in SOURCE_ACTORS.values()) * len(ASSETS) * len(HORIZONS)

    declared: dict[tuple[str, ...], set[str]] = defaultdict(set)   # cell -> sources, all declared
    measured: set[tuple[str, ...]] = set()
    reached: set[tuple[str, ...]] = set()                          # through an undeclared axis
    for r in rows:
        geo, source = r["geo"], r["source"]
        if not geo or source not in SOURCE_ACTORS or geo not in frame:
            continue
        langs = r["langs"] or frame[geo]
        actors = tuple(a for a in (r["actors"] or SOURCE_ACTORS[source])
                       if a in SOURCE_ACTORS[source]) or SOURCE_ACTORS[source]
        assets = r["assets"] or ASSETS
        horizons = r["horizons"] or HORIZONS
        full = bool(r["langs"] and r["actors"] and r["assets"] and r["horizons"])
        for lang in langs:
            if lang not in frame[geo]:
                continue
            for actor in actors:
                for asset in assets:
                    for hz in horizons:
                        cell: tuple[str, ...] = (source, geo, lang, actor, asset, hz)
                        if full:
                            declared[cell].add(f"{r['origin']}:{r['name']}")
                            if r["yielded"]:
                                measured.add(cell)
                        else:
                            reached.add(cell)
    filled = {c for c, srcs in declared.items() if c in measured or len(srcs) >= 2}
    thin = (set(declared) | reached) - filled

    # marginal occupancy: the share of each axis value's frame that something reaches
    occ: dict[int, Counter[str]] = {i: Counter() for i in range(6)}
    for cell in filled | thin:
        for i, v in enumerate(cell):
            occ[i][v] += 1
    tot: dict[int, Counter[str]] = {i: Counter() for i in range(6)}
    for geo, langs in frame.items():
        for lang in langs:
            for source, actors in SOURCE_ACTORS.items():
                for actor in actors:
                    n = len(ASSETS) * len(HORIZONS)
                    for i, v in ((0, source), (1, geo), (2, lang), (3, actor)):
                        tot[i][v] += n
                    for a in ASSETS:
                        tot[4][a] += len(HORIZONS)
                    for h in HORIZONS:
                        tot[5][h] += len(ASSETS)
    geo_rel = _geo_relevance(frame)

    def novelty(cell: tuple[str, ...]) -> float:
        return sum(1.0 - occ[i][v] / max(1, tot[i][v]) for i, v in enumerate(cell)) / 6.0

    # EVERY GROUP (source, geo, language, actor, asset) with no FILLED horizon is a GAP: EMPTY when
    # nothing reaches any horizon, THIN otherwise. Gaps are ranked by how many NEW INDEPENDENT
    # families they would open -- the alpha clusters (one payer each, libs/research/alpha_clusters)
    # their data feeds that the book does not yet occupy -- and never by raw cell count.
    gaps: dict[tuple[str, ...], dict[str, Any]] = {}
    n_empty = 0
    for geo, langs in frame.items():
        for lang in langs:
            for source, actors in SOURCE_ACTORS.items():
                for actor in actors:
                    for asset in ASSETS:
                        states = []
                        for hz in HORIZONS:
                            cell = (source, geo, lang, actor, asset, hz)
                            st = ("FILLED" if cell in filled else "THIN" if cell in thin
                                  else "EMPTY")
                            n_empty += st == "EMPTY"
                            states.append(st)
                        if "FILLED" in states:
                            continue
                        key: tuple[str, ...] = (source, geo, lang, actor, asset)
                        parts = {"asset_weight": round(asset_weight.get(asset, 0.0), 4),
                                 "geo_relevance": round(geo_rel.get(geo, 0.1), 4),
                                 "novelty": round(novelty((*key, HORIZONS[0])), 4),
                                 "source_prior": round(source_prior.get(source, 0.5), 4)}
                        feeds = clusters_fed(source, actor, asset)
                        gaps[key] = {
                            "state": "EMPTY" if all(s == "EMPTY" for s in states) else "THIN",
                            "horizons": dict(zip(HORIZONS, states, strict=True)),
                            "clusters": feeds,
                            "new_independent_families": round(sum(
                                occupancy.get(c, 1.0) for c in feeds), 2),
                            # every dataset also spawns regime / conditioner CHILDREN over the
                            # price families already trading the asset: all new for an EMPTY
                            # cell, half for a THIN one (its information is partly reached)
                            "new_indirect_families": (
                                round(templates[asset] * (1.0 if all(
                                    s == "EMPTY" for s in states) else 0.5), 1)
                                if templates is not None else UNMEASURED),
                            "factors": parts,
                            "score": round(parts["asset_weight"] * parts["geo_relevance"]
                                           * (0.5 + parts["novelty"]) * parts["source_prior"],
                                           6)}
    # ONE ROW PER GROUP, at most two per (source, geography), four per source and MAX_PER_ASSET
    # per asset class: a ranking that repeats one country or one asset forty times is a ranking
    # nobody can spend.
    axes = ("source", "geography", "language", "actor", "asset", "horizon")
    order = sorted(gaps.items(), key=lambda kv: (-kv[1]["new_independent_families"],
                                                 -_num(kv[1]["new_indirect_families"]),
                                                 kv[1]["state"] != "EMPTY",
                                                 -kv[1]["score"], kv[0]))
    per_sg: Counter[tuple[str, ...]] = Counter()
    per_s: Counter[str] = Counter()
    per_a: Counter[str] = Counter()
    top: list[dict[str, Any]] = []
    for key, g in order:
        if per_sg[key[:2]] >= 2 or per_s[key[0]] >= 4 or per_a[key[4]] >= MAX_PER_ASSET:
            continue
        per_sg[key[:2]] += 1
        per_s[key[0]] += 1
        per_a[key[4]] += 1
        top.append({"rank": len(top) + 1, "cell": dict(zip(axes[:5], key, strict=True)), **g,
                    "clusters": [{"cluster": c, "new": occupancy.get(c, 1.0)}
                                 for c in g["clusters"]]})
        if len(top) >= TOP_GAPS:
            break
    marginals = {axes[i]: {v: {"reached": occ[i][v], "of": tot[i][v]}
                           for v in sorted(tot[i])} for i in range(6)}
    if len(filled) + len(thin) + n_empty != size:
        raise AssertionError("the frame must partition into filled, thin and empty")
    return {"axes": list(axes), "size": size, "filled": len(filled), "thin": len(thin),
            "empty": n_empty, "frame_pairs": sum(len(v) for v in frame.values()),
            "gap_groups": len(gaps),
            "gap_groups_opening_a_new_family": sum(1 for g in gaps.values()
                                                   if g["new_independent_families"] > 0),
            "top_gaps": top, "top_empty": [t for t in top if t["state"] == "EMPTY"],
            "marginals": marginals,
            "rank": ("new_independent_families desc (empty alpha cluster 1.0, traded but "
                     "uncertified 0.5, certified 0), then new_indirect_families desc (regime/"
                     "conditioner children over the price-family templates trading the asset; "
                     "EMPTY 1.0, THIN 0.5), then EMPTY before THIN, then score"),
            "indirect_templates_by_asset": (dict(templates) if templates is not None
                                            else UNMEASURED),
            "score": "asset_weight x geo_relevance x (0.5 + novelty) x source_prior"}


def _geo_relevance(frame: Mapping[str, Any]) -> dict[str, float]:
    syms = _universe_symbols()
    counts: dict[str, int] = {}
    for geo in frame:
        links = REGION_LINKS.get(geo, ())
        counts[geo] = sum(1 for s in syms if any(lk in s for lk in links)) if syms else len(links)
    top = max(counts.values() or [1]) or 1
    return {g: max(0.1, math.log1p(n) / math.log1p(top)) for g, n in counts.items()}


def _universe_symbols() -> list[str]:
    doc = _read(UNIVERSE)
    if not isinstance(doc, Mapping):
        return []
    return [s for s, r in doc.items()
            if isinstance(r, Mapping) and r.get("asset_class") in UNIVERSE_CLASS_TO_ASSET]


def asset_weights() -> tuple[dict[str, float], str]:
    """log-share of hypothesis-lane symbols per class; the flat 1.0 when the registry is absent."""
    doc = _read(UNIVERSE)
    if not isinstance(doc, Mapping):
        return dict.fromkeys(ASSETS, 1.0), UNMEASURED
    n = Counter(UNIVERSE_CLASS_TO_ASSET.get(str((r or {}).get("asset_class")))
                for r in doc.values() if isinstance(r, Mapping))
    top = max((n[a] for a in ASSETS), default=0) or 1
    return {a: max(0.1, math.log1p(n[a]) / math.log1p(top)) for a in ASSETS}, "measured"


def source_priors(rows: list[dict[str, Any]]) -> dict[str, float]:
    """Laplace-smoothed share of attempted sources of each kind that yielded."""
    yes: Counter[str] = Counter()
    att: Counter[str] = Counter()
    for r in rows:
        if r["yielded"] is None or r["source"] not in SOURCE_ACTORS:
            continue
        att[r["source"]] += 1
        yes[r["source"]] += 1 if r["yielded"] else 0
    return {s: (yes[s] + 1) / (att[s] + 2) for s in SOURCES}


# ------------------------------------------------------------------- fringe families (ontology)

#: The access statuses (principal's ruling, 2026-10-13): no source is banned as a category; only
#: a METHOD is off. IDEAS_ONLY is read for ideas and
#: never fetched as input (every UNREAD source lands here); METHOD_BLOCKED names the method.
#: API_PERMITTED and PUBLIC_PAGE may be fetched as live input; NEEDS_KEY may once its key is set.
ACCESS_STATUSES: tuple[str, ...] = ("API_PERMITTED", "NEEDS_KEY", "PUBLIC_PAGE", "IDEAS_ONLY",
                                    "METHOD_BLOCKED")
LIVE_ACCESS = frozenset({"API_PERMITTED", "PUBLIC_PAGE"})


def access_of(s: Mapping[str, Any]) -> tuple[str, str]:
    """(status, reason) for one fringe source, re-derived: a live status needs a READ terms page
    with a quote, and a key the box does not hold reads NEEDS_KEY, never zero."""
    declared = str(s.get("access_status") or "")
    if declared not in ACCESS_STATUSES:
        return "IDEAS_ONLY", f"undeclared status {declared!r}: never fetched as live input"
    if declared == "METHOD_BLOCKED":
        return declared, str(s.get("status_reason") or "method named in the registry")
    if declared in ("API_PERMITTED", "NEEDS_KEY", "PUBLIC_PAGE"):
        if s.get("terms_read") != "READ" or not s.get("quote"):
            return "IDEAS_ONLY", "terms UNREAD or no verbatim quote: never fetched as live input"
        key_env = s.get("key_env")
        if key_env and not os.environ.get(str(key_env)):
            return "NEEDS_KEY", f"{key_env} is not set on this host"
        if declared == "NEEDS_KEY":
            return "API_PERMITTED", f"{key_env} present"
        return declared, str(s.get("conditions") or "")
    return "IDEAS_ONLY", str(s.get("status_reason") or "")


def fringe_status(doc: Mapping[str, Any] | None) -> dict[str, Any]:
    """Each family's stage, DERIVED from the tree: access, a collector module, ingested evidence."""
    if not isinstance(doc, Mapping):
        return {"status": UNMEASURED, "why": f"{FRINGE} absent"}
    order = list(doc.get("stage_ladder") or ["NAMED", "TERMS_CLEARED", "COLLECTOR_EXISTS",
                                              "INGESTED"])
    fams = []
    for f in doc.get("families") or []:
        srcs = []
        for s in f.get("sources") or []:
            status, reason = access_of(s)
            stage = "NAMED"
            if status in LIVE_ACCESS or status == "NEEDS_KEY":
                stage = "TERMS_CLEARED"
                owner = s.get("owner")
                if owner and (REPO / owner).exists():
                    stage = "COLLECTOR_EXISTS"
                if any(any(BASE.glob(g)) for g in s.get("evidence_globs") or []):
                    stage = "INGESTED"
            srcs.append({"id": s.get("id"), "access": status, "reason": reason,
                         "terms_read": s.get("terms_read") or "UNREAD", "stage": stage})
        stage = max((s["stage"] for s in srcs), key=order.index, default="NAMED")
        counts = Counter(s["access"] for s in srcs)
        fams.append({"id": f.get("id"), "name": f.get("name"),
                     "information_type": f.get("information_type"),
                     "mt5_instruments": list((f.get("mt5_mapping") or {}).get("instruments")
                                             or []),
                     "channel": (f.get("mt5_mapping") or {}).get("channel"),
                     "stage": stage, "access": {a: counts[a] for a in ACCESS_STATUSES},
                     "live_sources": sum(counts[a] for a in LIVE_ACCESS),
                     "sources": srcs})
    every = Counter(s["access"] for f in fams for s in f["sources"])
    return {"families": fams, "n": len(fams),
            "with_live_source": sum(1 for f in fams if f["live_sources"]),
            "with_key_pending_only": sum(1 for f in fams if not f["live_sources"]
                                         and f["access"]["NEEDS_KEY"]),
            "ideas_only": sum(1 for f in fams if not f["live_sources"]
                              and not f["access"]["NEEDS_KEY"]),
            "sources_by_access": {a: every[a] for a in ACCESS_STATUSES},
            "sources_terms_unread": sum(1 for f in fams for s in f["sources"]
                                        if s["terms_read"] != "READ"),
            "by_stage": dict(Counter(f["stage"] for f in fams)),
            "rule": doc.get("terms_rule")}


# ------------------------------------------------------------------ the unknown-unknown frontier

def _known_vocabulary(fringe: Mapping[str, Any] | None, registry: Mapping[str, Any] | None
                      ) -> set[str]:
    words: set[str] = set(STOPWORDS) | set(KNOWN_FEEDS)
    for k, v in KIND_TO_SOURCE.items():
        words |= set(re.split(r"[^a-z0-9]+", f"{k} {v}"))
    for vocab in (SOURCES, ACTORS, ASSETS, HORIZONS):
        for x in vocab:
            words |= set(x.split("_"))
    for ws in ASSET_WORDS.values():
        words |= {w.strip() for w in ws}
    try:
        from libs.research import coverage as CV
        for x in (*CV.INFORMATION_TYPES, *CV.SOURCE_LAYERS, *CV.SECTORS):
            words |= set(x.split("_"))
    except ImportError:  # the algebra is optional here; the vocabulary only shrinks
        pass
    if isinstance(fringe, Mapping):
        for f in fringe.get("families") or []:
            words |= set(re.split(r"[^a-z0-9]+", _text(f.get("id"), f.get("name"),
                                                       f.get("information_type"))))
    if isinstance(registry, Mapping):
        for k in (registry.get("datasets") or {}):
            words |= set(re.split(r"[^a-z0-9]+", str(k).lower()))
    return {w for w in words if w}


def _path_tokens(url: str) -> tuple[list[str], str | None, list[str]]:
    """(field-name tokens, file extension, API markers) from one endpoint URL."""
    p = urlparse(url)
    path = p.path.lower()
    base = path.rsplit("/", 1)[-1]
    ext = base.rsplit(".", 1)[-1] if "." in base else None
    stem = base.rsplit(".", 1)[0] if ext else base
    toks = [t for t in re.split(r"[^a-z]+", stem) if 4 <= len(t) <= 30]
    words = set(re.split(r"[^a-z0-9]+", f"{path} {p.query.lower()}"))
    markers = sorted(API_MARKERS & words)
    if ext in NOT_DATA:
        return [], None, []
    ok = ext and ext.isalnum() and len(ext) <= 7 and ext not in NOT_DATA
    return toks, (ext if ok else None), markers


def _public_host(host: str) -> bool:
    """A named public host: a loopback, a bare IP or a port-only host is never evidence."""
    h = host.split(":", 1)[0].lower()
    return "." in h and not re.fullmatch(r"[0-9.]+", h) and h != "localhost"


def discoveries(limit_files: int = 400) -> tuple[list[dict[str, Any]], int | str]:
    """The world crawler's recent discovery rows (newest files first), or UNMEASURED."""
    if not WORLD_DISCOVERIES.is_dir():
        return [], UNMEASURED
    files = sorted(WORLD_DISCOVERIES.glob("discoveries_*.json"))[-limit_files:]
    rows: list[dict[str, Any]] = []
    for f in files:
        doc = _read(f)
        items = doc if isinstance(doc, list) else (doc or {}).get("rows") if isinstance(
            doc, Mapping) else None
        rows.extend(dict(r) for r in items or [] if isinstance(r, Mapping))
    return rows, len(files)


def unknown_frontier(rows: list[dict[str, Any]], unmapped: Counter[str],
                     known: set[str], catalogue: Mapping[str, Any] | None,
                     state: dict[str, Any], now: str) -> dict[str, Any]:
    field_hosts: dict[str, set[str]] = defaultdict(set)
    feed_hosts: dict[str, set[str]] = defaultdict(set)
    kind_hosts: dict[str, set[str]] = defaultdict(set)
    examples: dict[str, str] = {}
    for r in rows:
        host = str(r.get("host") or urlparse(str(r.get("url") or "")).netloc)
        # `kind` on a crawler row is the ROW type (prose / story / dataset), not a publisher
        # kind; the publisher kind is `dataset_class`
        k = r.get("dataset_class")
        if k and str(k) not in KIND_TO_SOURCE:
            kind_hosts[str(k)].add(host)
        for ep in r.get("endpoints") or []:
            toks, ext, markers = _path_tokens(str(ep))
            ep_host = urlparse(str(ep)).netloc or host
            if not _public_host(ep_host):
                continue
            for t in toks:
                if t not in known:
                    field_hosts[t].add(ep_host)
                    examples.setdefault(f"field:{t}", str(ep))
            for m in [*markers, *([ext] if ext and ext not in KNOWN_FEEDS else [])]:
                feed_hosts[m].add(ep_host)
                examples.setdefault(f"feed:{m}", str(ep))
    if isinstance(catalogue, Mapping):
        for c in catalogue.get("rows") or []:
            sec = str((c or {}).get("section") or "").strip().lower()
            for t in re.split(r"[^a-z]+", sec):
                if 4 <= len(t) <= 30 and t not in known:
                    field_hosts[t].add(str((c or {}).get("catalogue") or "catalogue"))
    for k, n in unmapped.items():
        kind_hosts.setdefault(k, set()).add(f"<{n} declared source(s)>")

    seen: dict[str, str] = dict(state.get("terms_seen") or {})
    props: list[dict[str, Any]] = []
    for kind, table in (("publisher_kind", kind_hosts), ("feed_type", feed_hosts),
                        ("field_name", field_hosts)):
        for term, hosts in table.items():
            key = f"{kind}:{term}"
            new = key not in seen
            seen.setdefault(key, now)
            props.append({"kind": kind, "term": term, "hosts": len(hosts),
                          "example_hosts": sorted(hosts)[:5],
                          "example": examples.get(f"{'feed' if kind == 'feed_type' else 'field'}"
                                                  f":{term}"),
                          "first_seen_utc": seen[key], "new_this_pass": new,
                          "proposed_to_ontology": len(hosts) >= PROMOTE_HOSTS
                          or kind == "publisher_kind"})
    props.sort(key=lambda p: (-p["proposed_to_ontology"], -p["hosts"], p["kind"], p["term"]))
    if len(seen) > MAX_SEEN:   # keep the newest; the ontology still never shrinks below them
        seen = dict(sorted(seen.items(), key=lambda kv: kv[1])[-MAX_SEEN:])
    state["terms_seen"] = seen
    return {"terms_observed": len(props),
            "new_this_pass": sum(p["new_this_pass"] for p in props),
            "proposed_to_ontology": sum(p["proposed_to_ontology"] for p in props),
            "by_kind": dict(Counter(p["kind"] for p in props)),
            "terms_ever_seen": len(seen),
            "proposals": props[:MAX_PROPOSALS],
            "rule": ("a term is proposed when no axis, kind map, coverage vocabulary, fringe "
                     f"family or registry key names it and >= {PROMOTE_HOSTS} distinct hosts "
                     "carry it (publisher kinds always); proposals accumulate across passes")}


# ------------------------------------------------------------- the two engines read, not rebuilt

def dataset_discovery(rows: list[dict[str, Any]], n_files: int | str,
                      fringe: Mapping[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    hunt = _read(DATASET_HUNT)
    totals = (hunt or {}).get("totals") if isinstance(hunt, Mapping) else None
    eps = {str(e) for r in rows for e in (r.get("endpoints") or [])}
    seen = set(state.get("endpoints_seen") or [])
    digests = {hashlib.sha1(e.encode()).hexdigest()[:16] for e in eps}
    new = digests - seen
    state["endpoints_seen"] = sorted(seen | digests)[-MAX_SEEN:]
    cat = _read(DISCOVERED_CATALOGUE)
    targets = [{"family": f["id"], "source": s["id"], "stage": s["stage"],
                "access": s["access"]}
               for f in fringe.get("families") or [] for s in f["sources"]
               if s["access"] in ("API_PERMITTED", "PUBLIC_PAGE", "NEEDS_KEY")
               and s["stage"] in ("TERMS_CLEARED", "COLLECTOR_EXISTS")]
    return {
        "owner": {"world_dataset_hunt": "research/world_dataset_hunter.py -> "
                                        "reports/DATASET_HUNT.json",
                  "free_stack_hunt": "research/free_stack_hunter.py -> "
                                     "data/free_stack/discovered_catalogue.json",
                  "world_crawler": "side_channels/world_crawler.py -> "
                                   "data/intelligence/world/discoveries_*.json"},
        "world_hunt_datasets_discovered": (totals or {}).get("datasets_discovered", UNMEASURED)
        if totals else UNMEASURED,
        "world_hunt_new_datasets": (((hunt or {}).get("pass") or {}).get("new_datasets",
                                                                           UNMEASURED)
                                    if isinstance(hunt, Mapping) else UNMEASURED),
        "crawler_files_read": n_files,
        "crawler_endpoints_distinct": len(eps) if n_files != UNMEASURED else UNMEASURED,
        "crawler_endpoints_new_this_pass": len(new) if n_files != UNMEASURED else UNMEASURED,
        "catalogue_rows": (len((cat or {}).get("rows") or []) if isinstance(cat, Mapping)
                           else UNMEASURED),
        "fringe_acquisition_targets": targets,
        "live_yield": "UNMEASURED here: the hunters measure fetch yield on the box",
    }


def representation_discovery() -> dict[str, Any]:
    rep = _read(FORGE_REPORT)
    if not isinstance(rep, Mapping):
        return {"owner": "research/representation_forge.py (leg representation_forge)",
                "status": UNMEASURED, "why": f"{FORGE_REPORT.name} absent on this tree",
                "pr_297": "claude/gdd-representations extends the same organ and artifact"}
    grammar = rep.get("grammar") or {}
    by_t = rep.get("counts_by_transform") or {}
    registered = list(grammar.get("registered") or [])
    return {"owner": "research/representation_forge.py (leg representation_forge)",
            "status": "measured", "at": rep.get("at"),
            "minted_last_pass": rep.get("minted", UNMEASURED),
            "store_total": (rep.get("store") or {}).get("n_total", UNMEASURED),
            "input_series": (rep.get("inputs") or {}).get("series", UNMEASURED),
            "transforms_registered": len(registered) if registered else UNMEASURED,
            "transforms_used": len([t for t, n in by_t.items() if n]),
            "transforms_never_used": sorted(set(registered) - {t for t, n in by_t.items() if n}),
            "pr_297": "claude/gdd-representations extends the same organ and artifact"}


# ------------------------------------------------------------------------------------- run

def run(*, out: Path | None = None, state_path: Path | None = None,
        write_state: bool = True) -> dict[str, Any]:
    started = time.monotonic()
    now = _now_iso()
    state_path = state_path or STATE
    state = _read(state_path) or {}
    if not isinstance(state, dict):
        state = {}

    inputs: dict[str, Any] = {}
    docs: dict[str, Any] = {}
    for name, path in (("alt_data_yield", ALT_DATA_YIELD), ("deep_forest", DEEP_FOREST),
                       ("free_stack", FREE_STACK), ("free_stack_yield", FREE_STACK_YIELD),
                       ("universe_map", UNIVERSE_MAP), ("data_registry", DATA_REGISTRY),
                       ("discovered_catalogue", DISCOVERED_CATALOGUE),
                       ("fringe_families", FRINGE)):
        docs[name] = _read(path)
        inputs[name] = {"path": str(path), "status": "read" if docs[name] is not None
                        else UNMEASURED}

    unmapped: Counter[str] = Counter()
    rows = [*rows_from_grounds(docs["deep_forest"], docs["alt_data_yield"], unmapped),
            *rows_from_free_stack(docs["free_stack"], docs["free_stack_yield"], unmapped),
            *rows_from_alt_platforms(docs["alt_data_yield"]),
            *rows_from_registry(docs["data_registry"])]
    legacy, set_aside = rows_from_universe_map(docs["universe_map"])
    rows.extend(legacy)

    regions = ((docs["deep_forest"] or {}).get("regions") or {}) if isinstance(
        docs["deep_forest"], Mapping) else {}
    if not rows or not regions:
        cmap: dict[str, Any] = {"status": UNMEASURED,
                                "why": "no source rows or no region frame could be read",
                                "size": UNMEASURED, "filled": UNMEASURED, "thin": UNMEASURED,
                                "empty": UNMEASURED, "top_empty": []}
    else:
        weights, wstat = asset_weights()
        occ, ostat = cluster_occupancy()
        tmpl, tstat = price_templates()
        cmap = {"status": "measured", "asset_weight_source": wstat,
                "cluster_occupancy_source": ostat, "cluster_occupancy": occ,
                "indirect_templates_source": tstat,
                **build_map(rows, regions, weights, source_priors(rows), occ, tmpl)}
    cmap["rows_by_origin"] = dict(Counter(r["origin"] for r in rows))
    cmap["access_census"] = {a: sum(1 for r in rows if r["access"] == a)
                             for a in ACCESS_STATUSES}
    cmap["access_rule"] = "a census only: access never changes a cell's state"
    cmap["rows_without_yield_measure"] = sum(1 for r in rows if r["yielded"] is None)
    cmap["legacy_crypto_native_set_aside"] = set_aside
    cmap["inputs_unmeasured"] = [k for k, v in inputs.items() if v["status"] == UNMEASURED]

    fringe = fringe_status(docs["fringe_families"])
    if cmap.get("status") == "measured":
        next_actions(cmap["top_gaps"], docs["fringe_families"], fringe, docs["free_stack"],
                     docs["deep_forest"])
        cmap["top_empty"] = [t for t in cmap["top_gaps"] if t["state"] == "EMPTY"]
    cmap["registered_this_organ"] = [dict(r, clusters=list(r["clusters"])) for r in REGISTERED]
    disc_rows, n_files = discoveries()
    unknown = unknown_frontier(disc_rows, unmapped,
                               _known_vocabulary(docs["fringe_families"], docs["data_registry"]),
                               docs["discovered_catalogue"], state, now)
    report = {
        "at": now, "rule": RULE, "elapsed_s": 0.0,
        "engines": {
            "dataset_discovery": "EXISTS: world_dataset_hunt + free_stack_hunt + world_crawler; "
                                 "this leg adds the cross-door new-dataset count and the fringe "
                                 "acquisition queue",
            "coverage_map": "this leg (breadth_frontier)",
            "representation_discovery": "EXISTS: representation_forge (PR #297 extends it); "
                                        "this leg reads its coverage",
            "unknown_unknown_frontier": "this leg (breadth_frontier)"},
        "inputs": inputs,
        "coverage_map": cmap,
        "fringe_families": fringe,
        "dataset_discovery": dataset_discovery(disc_rows, n_files,
                                               fringe if "families" in fringe else {}, state),
        "representation_discovery": representation_discovery(),
        "unknown_unknown_frontier": unknown,
    }
    report["elapsed_s"] = round(time.monotonic() - started, 2)
    _write(out or OUT, report)
    if write_state:
        state["updated"] = now
        _write(state_path, state)
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--once", action="store_true", help="one pass (the hourly leg)")
    ap.add_argument("--out", type=Path, default=None, help="write the report here instead")
    ap.add_argument("--state", type=Path, default=None, help="state file (default under data/)")
    ap.add_argument("--json", action="store_true", help="print the report")
    a = ap.parse_args(argv)
    rep = run(out=a.out, state_path=a.state)
    cm, ff, uk = rep["coverage_map"], rep["fringe_families"], rep["unknown_unknown_frontier"]
    if a.json:
        print(json.dumps(rep, indent=1, ensure_ascii=False, default=str))
    else:
        print(f"breadth_frontier: map size={cm.get('size')} filled={cm.get('filled')} "
              f"thin={cm.get('thin')} empty={cm.get('empty')} | fringe families "
              f"{ff.get('n')} live={ff.get('with_live_source')} "
              f"key_pending={ff.get('with_key_pending_only')} "
              f"ideas_only={ff.get('ideas_only')} | unknown terms={uk['terms_observed']} "
              f"new={uk['new_this_pass']} proposed={uk['proposed_to_ontology']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
