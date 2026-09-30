#!/usr/bin/env python3
"""PAID-SUBSTITUTE ENGINE -- every paid dataset the industry sells, matched to the free series that
replicate it, and every match that holds enrolled as a source that feeds cells.

THE PRINCIPAL'S STANDING ORDER (2026-09-30): "our global hunts discoveries n deep forest minings
must discover all paid datasets alternatives thousands there's free versions replicas we can match
them".
Before this organ the desk knew the NAMES of paid products only as words in source registries
(asia_quant_gap row 3: "0 of 14 alt platforms yield"; row 22: "no automated crawl of public
catalogues into that queue"). Nothing enumerated what the paid market sells, nothing hunted a free
replica for each, and nothing measured how much of the paid map the desk now covers for free.

WHAT ONE PASS DOES (leg `paid_substitute_engine`, hourly):

  1. CATALOGUE. `data/paid_dataset_catalogue/<class>.json` is the seeded, public-listing-only map of
     paid products (vendor, dataset, class, region, measure, frequency) with an honest
     `seed_source` on every row. A bounded, robots-respecting crawl of public listing pages
     (`_listings.json`) adds rows to `data/paid_substitutes/catalogue_crawled.json` -- only names a
     listing page itself shows, never an invented vendor. The Asia thread's table is read (never
     written) and its nine classes are tagged `owner: asia`.
  2. HUNT. For every paid set: the free library (`data/paid_substitute_library.json`) sources that
     share its class, and multilingual search targets (en zh ja ko ru pt es de fr tr ar hi) over
     government open-data portals, statistics offices, central banks, exchanges, regulators,
     academic replication archives, GitHub, Kaggle, Zenodo and the open web. They are EMITTED into
     the machinery that already fetches: search grounds into `data/deep_forest_queue/` (read by
     deep_forest_miner), portal seeds into `data/paid_substitutes/crawl_seeds.json` (read by
     world_crawler), roster rows into `data/source_rosters/paid_substitutes.json` (read by the
     global mining roster's `external_rosters` glob), and machine endpoints into
     `data/intelligence/world/discoveries_paidsub_<day>.json` (read by acquire_datasets).
     Datasets the forest finds on these grounds come back as DISCOVERED candidates next pass.
  3. SCORE. Coverage = class, region, frequency, history and latency match, each a component that
     is either measured or UNMEASURED (an unmeasured component is excluded from the mean and
     named, never scored 0). Correlation is computed only where BOTH series are on disk (a paid
     vendor's public sample and the substitute's acquired series); otherwise it is UNMEASURED.
  4. ENROL. A free, reachable substitute whose best coverage clears ENROL_THRESHOLD with at least
     MIN_MEASURED_COMPONENTS measured, and whose correlation (when measured) clears
     MIN_CORRELATION, is enrolled under a stable `dataset_id` (`psub_<library id>`). At enrolment it
     feeds ALL THREE USES (standing rule 2026-09-30, "every enrolled substitute feeds all three
     uses within 24h"):
       * DIRECT cells -- `exogenous_conditioner` on the instruments the substitute maps to;
       * INDIRECT cells -- `exogenous_gate` on price-only base families while the series is in a
         band (world_cells' shape exactly);
       * ALLOCATION -- an entry in `reports/WORLD_STATE_INPUTS.json` under `paid_substitutes`.
     Every cell carries the dataset_id as `params.source` AND as the registry's `source_id`, plus
     `campaign_id = paid_substitute:<dataset_id>`, so a fence can match cell to dataset.
     ENROLMENT IS HAVING THE SERIES: a ready match whose series acquire_datasets has not fetched
     is AWAITING_ACQUISITION (its endpoint is in this hour's discoveries, drained by the
     acquirer's own hourly leg). Nothing is minted on a series that does not exist -- no trial is
     charged to the shared multiple-testing budget for a question that cannot be asked yet, and
     nothing is parked in the registry (no-queues law, 2026-09-23): every cell is `queued`.
  5. REPORT. `reports/PAID_SUBSTITUTE_COVERAGE.json` + `.md`: per class and region -- paid sets,
     sets with a matched substitute, match strength, enrolled substitutes, the cells they fed.

FREE AND LAWFUL ONLY: key-less sources, or free keys whose environment variable NAME is present on
the box (the value is never read). No login-walled page, no paid tier, nothing against a
publisher's terms; the catalogue crawler honours robots.txt. No crypto-exchange ground is ever
emitted (MT5 universe mandate): `BANNED_HOSTS` is checked on every emitted URL.

Nothing here sizes, vetoes or trades. UNMEASURED is never zero.

    python research/paid_substitute_engine.py              # full pass
    python research/paid_substitute_engine.py --no-fetch   # no network (catalogue crawl skipped)
    python research/paid_substitute_engine.py --dry-run    # measure, write only the report
"""

from __future__ import annotations

import argparse
import contextlib
import glob
import hashlib
import html
import json
import os
import re
import sqlite3
import sys
import time
import urllib.parse
import urllib.robotparser
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

UNMEASURED = "UNMEASURED"
GENERATOR = "paid_substitute_engine"
LEG = "paid_substitute_engine"

CATALOGUE_DIR = DESK / "data" / "paid_dataset_catalogue"
CLASSES = CATALOGUE_DIR / "_classes.json"
LISTINGS = CATALOGUE_DIR / "_listings.json"
FLOOR = CATALOGUE_DIR / "_floor.json"
LIBRARY = DESK / "data" / "paid_substitute_library.json"
STATE_DIR = DESK / "data" / "paid_substitutes"
CRAWLED = STATE_DIR / "catalogue_crawled.json"
STATE = STATE_DIR / "state.json"
SEEDS = STATE_DIR / "crawl_seeds.json"
ENROLLED = STATE_DIR / "enrolled.json"
ROSTER = DESK / "data" / "source_rosters" / "paid_substitutes.json"
FOREST_QUEUE = DESK / "data" / "deep_forest_queue" / "paid_substitutes.json"
WORLD_INTEL = DESK / "data" / "intelligence" / "world"
LAKE = DESK / "data" / "lake" / "series"
ACQUIRED = DESK / "data" / "acquired" / "registry.json"
UNIVERSE = DESK / "data" / "universe" / "universe.json"
REPORT = DESK / "reports" / "PAID_SUBSTITUTE_COVERAGE.json"
REPORT_MD = DESK / "reports" / "PAID_SUBSTITUTE_COVERAGE.md"
WORLD_STATE = DESK / "reports" / "WORLD_STATE_INPUTS.json"

#: Where the Asia thread's paid-substitute table may be. Read only; never written. The first
#: existing match wins; an absent table is UNMEASURED in the report, never an empty class.
ASIA_TABLE_ENV = "PAID_SUBSTITUTE_ASIA_TABLE"
ASIA_TABLE_GLOBS: tuple[str, ...] = (
    "/mnt/project-files/reports/paid_data_substitutes_*.md",
    str(DESK / "reports" / "paid_data_substitutes_*.md"),
    str(DESK / "reports" / "paid_data_substitutes_*.json"),
    str(DESK / "data" / "paid_data_substitutes_*.json"),
)
#: The Asia thread's nine classes, in its own words -> this catalogue's class ids.
ASIA_CLASSES: dict[str, str] = {
    "ticks": "ticks",
    "consensus": "consensus_estimates",
    "calendars": "calendars",
    "options": "options_vol",
    "positioning": "positioning",
    "gdelt": "news_nlp",
    "card": "card_consumer",
    "foot traffic": "foot_traffic",
    "satellite": "satellite",
}

#: MT5 UNIVERSE MANDATE: no crypto-exchange ground is emitted, whatever a listing or row says.
BANNED_HOSTS: tuple[str, ...] = (
    "binance.",
    "bybit.",
    "okx.",
    "hyperliquid.",
    "deribit.",
    "coinbase.",
    "kraken.",
    "bitmex.",
    "bitfinex.",
    "kucoin.",
    "gate.io",
    "huobi.",
    "htx.",
    "mexc.",
    "bitget.",
    "coinglass.",
    "glassnode.",
    "cryptoquant.",
    "dydx.",
    "gmx.io",
)

#: Coverage components and their weights. A component the paid side leaves UNSTATED is not
#: scored; the mean is over the measured ones, and the row names which were measured.
WEIGHTS: dict[str, float] = {
    "class": 0.35,
    "region": 0.25,
    "frequency": 0.15,
    "history": 0.15,
    "latency": 0.10,
}
ENROL_THRESHOLD = 0.70
MIN_REGION = 0.7
MIN_MEASURED_COMPONENTS = 4
MIN_CORRELATION = 0.50
#: The history a substitute needs to be judged at all: the gauntlet's walk-forward wants years.
HISTORY_REQUIREMENT_YEARS = 10.0

FREQ_RANK: dict[str, float] = {
    "intraday": 0,
    "hourly": 1,
    "daily": 2,
    "weekly": 3,
    "10-day": 3.3,
    "semi-monthly": 3.5,
    "semimonthly": 3.5,
    "monthly": 4,
    "quarterly": 5,
    "semiannual": 6,
    "annual": 7,
    "triennial": 8,
}

#: Direct/indirect cell shape: world_cells' own (research/world_cells.py on #123), so the two
#: producers mint the same kind of cell and the fence reads them the same way.
CHARTS: tuple[str, ...] = ("H1", "D1")
TRANSFORMS: tuple[str, ...] = ("level_z", "delta", "delta_z")
GATE_BANDS: tuple[str, ...] = ("high", "low", "calm")
GATE_THRESHOLD = 1.0
GATE_CHART = "H1"
#: Price-only bases the indirect cells gate, each checked with `wrappable` before minting.
GATE_BASES: tuple[str, ...] = (
    "trend_ma_cross",
    "mean_reversion_bollinger",
    "session_range_breakout",
    "volatility_squeeze",
    "momentum_volgate",
    "range_reversion",
)
SIGNAL = "value"
#: Cells per pass. PACING, never a ceiling: the minted set is remembered and the next pass
#: resumes, so every enrolled substitute reaches all three uses on its first pass unless the
#: pass itself is truncated (then the next hour finishes it, inside the 24h rule).
CELLS_PER_PASS = 4_000
#: Deep-forest grounds kept in the queue file. The forest round-robins clusters, and this whole
#: file is ONE cluster (`paid_substitutes`), so it takes a fair turn and never starves the
#: practitioner grounds; this cap only bounds the file.
FOREST_QUEUE_CAP = 6_000
CRAWL_BUDGET_S = 240.0
CRAWL_PAGES_PER_PASS = 40
USER_AGENT = "quant-desk-paid-substitute-engine/1 (research; robots-respecting)"


# ------------------------------------------------------------------------------------ io
def _now() -> datetime:
    return datetime.now(tz=UTC)


def _iso(t: datetime) -> str:
    return t.isoformat(timespec="seconds")


def _read_json(path: Path) -> Any:
    try:
        return json.loads(Path(path).read_text("utf-8-sig"))
    except (OSError, ValueError):
        return None


def _atomic_json(path: Path, doc: Any, *, indent: int | None = 1) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(doc, indent=indent, ensure_ascii=False, default=str), "utf-8")
    for i in range(6):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:  # Windows: a held destination is retried
            with contextlib.suppress(OSError):
                os.chmod(path, 0o666)
            time.sleep(0.2 * (i + 1))
    try:
        path.write_text(tmp.read_text("utf-8"), "utf-8")
    finally:
        with contextlib.suppress(OSError):
            tmp.unlink()


def _slug(s: str, n: int = 48) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(s).lower()).strip("_")[:n]


def _key(*parts: Any) -> str:
    return hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()[:14]


def banned(url: str) -> bool:
    host = urllib.parse.urlparse(str(url)).netloc.lower() or str(url).lower()
    return any(b in host for b in BANNED_HOSTS)


# ----------------------------------------------------------------------------- catalogue
def load_classes(path: Path | None = None) -> dict[str, Any]:
    doc = _read_json(path or CLASSES) or {}
    return doc if isinstance(doc, dict) else {}


def seed_entries(catalogue_dir: Path | None = None) -> list[dict[str, Any]]:
    """Every seeded paid entry (the authored class files; `_*.json` are metadata)."""
    out: list[dict[str, Any]] = []
    for f in sorted((catalogue_dir or CATALOGUE_DIR).glob("*.json")):
        if f.name.startswith("_"):
            continue
        doc = _read_json(f) or {}
        for e in doc.get("entries") or []:
            if isinstance(e, dict) and e.get("id"):
                out.append(dict(e))
    return out


def load_catalogue(
    *,
    catalogue_dir: Path | None = None,
    crawled: Path | None = None,
    classes: Mapping[str, Any] | None = None,
    asia_rows: Iterable[Mapping[str, Any]] = (),
) -> list[dict[str, Any]]:
    """Seed + crawled + Asia-table entries, de-duplicated by id (first definition wins), each
    tagged with the owner of its class."""
    cls = (classes or load_classes()).get("classes") or {}
    rows = seed_entries(catalogue_dir)
    cdoc = _read_json(crawled or CRAWLED) or {}
    rows.extend(dict(e) for e in (cdoc.get("entries") or []) if isinstance(e, dict))
    rows.extend(dict(e) for e in asia_rows)
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for e in rows:
        pid = str(e.get("id") or "")
        if not pid or pid in seen:
            continue
        seen.add(pid)
        c = str(e.get("class") or "")
        e.setdefault("owner", "asia" if (cls.get(c) or {}).get("owner") == "asia" else GENERATOR)
        if (cls.get(c) or {}).get("owner") == "asia":
            e["owner"] = "asia"
        out.append(e)
    return out


def catalogue_floor(path: Path | None = None) -> int:
    doc = _read_json(path or FLOOR) or {}
    try:
        return int(doc.get("floor") or 0)
    except (TypeError, ValueError):
        return 0


# ----------------------------------------------------------------------- Asia's table
def find_asia_table(globs: Iterable[str] | None = None) -> Path | None:
    env = os.environ.get(ASIA_TABLE_ENV, "").strip()
    cands = [env] if env else []
    for g in globs if globs is not None else ASIA_TABLE_GLOBS:
        cands.extend(sorted(glob.glob(g), reverse=True))
    for c in cands:
        if c and Path(c).is_file():
            return Path(c)
    return None


#: Words in an Asia-table row -> class, most specific first (checked on the paid column first).
_ASIA_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("foot traffic", "foot_traffic"),
    ("safegraph", "foot_traffic"),
    ("placer", "foot_traffic"),
    ("satellite", "satellite"),
    ("orbital", "satellite"),
    ("spaceknow", "satellite"),
    ("card", "card_consumer"),
    ("consensus", "consensus_estimates"),
    ("i/b/e/s", "consensus_estimates"),
    ("calendar", "calendars"),
    ("optionmetrics", "options_vol"),
    ("option", "options_vol"),
    ("put-call", "options_vol"),
    ("tick", "ticks"),
    ("gdelt", "news_nlp"),
    ("news", "news_nlp"),
    ("ravenpack", "news_nlp"),
    ("positioning", "positioning"),
    ("flow", "positioning"),
    ("sentiment", "positioning"),
    ("gold premium", "commodities_physical"),
)


def _asia_class(text: str) -> str | None:
    t = str(text).strip().lower()
    for k, v in _ASIA_KEYWORDS:
        if k in t:
            return v
    return None


def parse_asia_table(path: Path) -> dict[str, Any]:
    """The Asia thread's paid-vs-free rows, from its markdown table or structured JSON.

    Markdown: the first table whose header names a class column and a paid or free column. Every
    row becomes a catalogue entry (owner=asia) when it names a paid product, and a named free
    substitute when it names one. Columns are found by header words, never by position."""
    out: dict[str, Any] = {
        "path": str(path),
        "rows": 0,
        "entries": [],
        "substitutes": [],
        "classes": [],
    }
    try:
        text = path.read_text("utf-8")
    except OSError as exc:
        out["error"] = f"{type(exc).__name__}"
        return out
    rows: list[dict[str, str]] = []
    if path.suffix == ".json":
        try:
            doc = json.loads(text)
        except ValueError:
            doc = None
        items = doc.get("rows") if isinstance(doc, dict) else doc
        rows = [
            {str(k).lower(): str(v) for k, v in r.items()}
            for r in (items or [])
            if isinstance(r, dict)
        ]
    else:
        header: list[str] | None = None
        for line in text.splitlines():
            ln = line.strip()
            if not (ln.startswith("|") and ln.endswith("|")):
                header = None if not ln else header
                continue
            cells = [html.unescape(c.strip()) for c in ln.strip("|").split("|")]
            if header is None:
                low = [c.lower() for c in cells]
                if any("class" in c or "category" in c or "data" in c for c in low) and any(
                    w in c for c in low for w in ("paid", "free", "substitut", "vendor")
                ):
                    header = low
                continue
            if all(set(c) <= set("-: ") for c in cells):
                continue
            rows.append(dict(zip(header, cells, strict=False)))

    def col(r: Mapping[str, str], *words: str) -> str:
        for k, v in r.items():
            if any(w in k for w in words):
                return str(v).strip()
        return ""

    classes: set[str] = set()
    for r in rows:
        c = (
            _asia_class(col(r, "class", "category"))
            or _asia_class(col(r, "paid"))
            or _asia_class(col(r, "free", "substitut"))
        )
        if not c:
            continue
        classes.add(c)
        out["rows"] += 1
        paid = re.sub(r"[*`]", "", col(r, "paid", "vendor"))
        free = re.sub(r"[*`]", "", col(r, "free", "substitut", "replica", "alternative"))
        region = col(r, "region", "market", "country") or "global"
        if paid:
            out["entries"].append(
                {
                    "id": f"paid:asia:{_slug(c, 24)}:{_slug(paid)}",
                    "vendor": paid.split("(")[0].strip()[:80],
                    "dataset": paid[:160],
                    "class": c,
                    "region": region[:24],
                    "measures": col(r, "measure", "what"),
                    "frequency": col(r, "freq") or "UNSTATED",
                    "history_years": UNMEASURED,
                    "latency_days": UNMEASURED,
                    "seed_source": f"asia_thread_table:{path.name}",
                    "owner": "asia",
                    "public_sample": None,
                }
            )
        if free:
            out["substitutes"].append(
                {"class": c, "region": region, "name": free[:200], "owner": "asia"}
            )
    out["classes"] = sorted(classes)
    return out


# ----------------------------------------------------------------- catalogue crawler
def _robots_ok(
    url: str,
    fetch: Callable[[str], tuple[int | None, str]],
    cache: dict[str, urllib.robotparser.RobotFileParser | None],
) -> bool:
    p = urllib.parse.urlparse(url)
    base = f"{p.scheme}://{p.netloc}"
    if base not in cache:
        status, body = fetch(base + "/robots.txt")
        if status is None or status >= 500:
            cache[base] = None  # unreachable robots: do not fetch (conservative)
        else:
            parser = urllib.robotparser.RobotFileParser()
            parser.parse(body.splitlines() if status < 400 else [])
            cache[base] = parser
    rp = cache[base]
    return bool(rp is not None and rp.can_fetch(USER_AGENT, url))


def _robots_unreachable(url: str, cache: Mapping[str, Any]) -> bool:
    p = urllib.parse.urlparse(url)
    return f"{p.scheme}://{p.netloc}" in cache and cache[f"{p.scheme}://{p.netloc}"] is None


#: Link shapes on public catalogue pages that NAME a vendor or product, and how to read the name.
_LINK_RE = re.compile(r"""<a[^>]+href=["']([^"'#]+)["'][^>]*>(.*?)</a>""", re.I | re.S)
_LISTING_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "datarade_provider",
        re.compile(r"datarade\.ai/data-providers/([a-z0-9-]+)/(?:profile|data-products)", re.I),
    ),
    ("datarade_product", re.compile(r"datarade\.ai/data-products/([a-z0-9-]+)", re.I)),
    ("neudata_vendor", re.compile(r"neudata\.co/1/vendors/([a-z0-9-]+)", re.I)),
    (
        "eaglealpha_vendor",
        re.compile(r"eaglealpha\.com/(?:vendors|data-vendors|partners)/([a-z0-9-]+)", re.I),
    ),
    (
        "lse_directory",
        re.compile(r"londonstrategicedge\.com/directory/alternative-data/([a-z0-9-]+)/?$", re.I),
    ),
    ("battlefin_vendor", re.compile(r"battlefin\.com/(?:vendors|data-vendors)/([a-z0-9-]+)", re.I)),
)


def extract_listing(
    page: str, base_url: str, *, class_hint: str, source: str, region: str = "UNSTATED"
) -> list[dict[str, Any]]:
    """Vendor/product rows a listing page itself names: anchor text of links whose href is a
    vendor or product page on a known catalogue. Nothing is inferred beyond the page."""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for href, inner in _LINK_RE.findall(page or ""):
        url = urllib.parse.urljoin(base_url, html.unescape(href))
        if banned(url):
            continue
        for kind, rx in _LISTING_PATTERNS:
            m = rx.search(url)
            if not m:
                continue
            name = re.sub(r"<[^>]+>", " ", inner)
            name = html.unescape(re.sub(r"\s+", " ", name)).strip()
            if (
                not name
                or len(name) < 2
                or len(name) > 120
                or name.lower() in ("profile", "view", "more", "learn more", "read more", "see all")
            ):
                name = m.group(1).replace("-", " ").title()
            product = kind.endswith("product")
            vendor = "UNSTATED" if product else name
            pid = f"paid:crawl:{_slug(kind, 16)}:{_slug(m.group(1))}"
            if pid in seen:
                break
            seen.add(pid)
            out.append(
                {
                    "id": pid,
                    "vendor": vendor,
                    "dataset": name if product else "UNSTATED",
                    "class": class_hint,
                    "region": region,
                    "measures": "UNSTATED",
                    "frequency": "UNSTATED",
                    "history_years": UNMEASURED,
                    "latency_days": UNMEASURED,
                    "seed_source": f"crawl:{source}",
                    "listing_url": url,
                    "public_sample": None,
                }
            )
            break
    return out


def _http_fetch(deadline: float) -> Callable[[str], tuple[int | None, str]]:
    from libs.data import polite_fetch as pf

    def fetch(url: str) -> tuple[int | None, str]:
        r = pf.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=20.0,
            retries=1,
            deadline=deadline,
            leg=LEG,
        )
        return r.status, r.text

    return fetch


def crawl_catalogue(
    *,
    listings_path: Path | None = None,
    crawled_path: Path | None = None,
    budget_s: float = CRAWL_BUDGET_S,
    fetch: Callable[[str], tuple[int | None, str]] | None = None,
    now: datetime | None = None,
    write: bool = True,
) -> dict[str, Any]:
    """One bounded pass over the public listing pages; new rows appended to the crawled file."""
    now = now or _now()
    listings = (_read_json(listings_path or LISTINGS) or {}).get("listings") or []
    cpath = crawled_path or CRAWLED
    doc = _read_json(cpath) or {}
    entries: list[dict[str, Any]] = [e for e in (doc.get("entries") or []) if isinstance(e, dict)]
    have = {str(e.get("id")) for e in entries}
    cursor = int(doc.get("cursor") or 0)
    stats: dict[str, Any] = {
        "pages_tried": 0,
        "pages_ok": 0,
        "robots_refused": 0,
        "host_unreachable": 0,
        "new_entries": 0,
        "errors": [],
        "listings": len(listings),
    }
    if not listings:
        stats["status"] = f"{UNMEASURED}: no listings declared"
        return stats
    deadline = time.monotonic() + max(1.0, budget_s)
    try:
        get = fetch or _http_fetch(deadline)
    except Exception as exc:
        stats["status"] = f"{UNMEASURED}: fetch unavailable ({type(exc).__name__})"
        return stats
    robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
    n = len(listings)
    for i in range(min(n, CRAWL_PAGES_PER_PASS)):
        if time.monotonic() >= deadline:
            break
        lst = listings[(cursor + i) % n]
        url = str(lst.get("url") or "")
        if not url or banned(url):
            continue
        stats["pages_tried"] += 1
        try:
            if not _robots_ok(url, get, robots):
                # an unreachable robots.txt is not fetched either -- counted apart, because it is a
                # network verdict about this host, not the site's refusal
                key = "host_unreachable" if _robots_unreachable(url, robots) else "robots_refused"
                stats[key] += 1
                continue
            status, body = get(url)
        except Exception as exc:
            stats["errors"].append(f"{url[:60]}: {type(exc).__name__}")
            continue
        if status is None or status >= 400:
            stats["errors"].append(f"{url[:60]}: HTTP {status}")
            continue
        stats["pages_ok"] += 1
        for e in extract_listing(
            body,
            url,
            class_hint=str(lst.get("class") or "UNSTATED"),
            source=str(lst.get("source") or url),
            region=str(lst.get("region") or "UNSTATED"),
        ):
            if e["id"] in have:
                continue
            e["first_seen_utc"] = _iso(now)
            entries.append(e)
            have.add(e["id"])
            stats["new_entries"] += 1
    stats["errors"] = stats["errors"][:12]
    stats["status"] = "OK" if stats["pages_ok"] else f"{UNMEASURED}: no listing page answered"
    if write:
        _atomic_json(
            cpath,
            {
                "updated_at": _iso(now),
                "cursor": (cursor + CRAWL_PAGES_PER_PASS) % n,
                "note": "rows a public listing page named; vendor/product names only",
                "entries": entries,
            },
        )
    return stats


# ---------------------------------------------------------------------------- library
def load_library(path: Path | None = None) -> list[dict[str, Any]]:
    doc = _read_json(path or LIBRARY) or {}
    return [dict(s) for s in (doc.get("sources") or []) if isinstance(s, dict) and s.get("id")]


def key_present(env_name: str, environ: Mapping[str, str] | None = None) -> bool:
    """Is the NAMED key configured? Reads presence only -- the value never leaves os.environ."""
    env = os.environ if environ is None else environ
    return bool(env_name) and bool(str(env.get(env_name, "")).strip())


def usable(src: Mapping[str, Any], environ: Mapping[str, str] | None = None) -> tuple[bool, str]:
    """Free and reachable on this box? (ok, reason)."""
    url = str(src.get("url") or "")
    if banned(url) or banned(str(src.get("endpoint") or "")):
        return False, "crypto-exchange ground (MT5 mandate)"
    auth = str(src.get("auth") or "none")
    if auth == "none":
        return True, "key-less"
    if auth in ("free_key", "ua"):
        env = str(src.get("auth_env") or "")
        if key_present(env, environ):
            return True, f"free key configured ({env})"
        return False, f"free key not configured: {env or 'unnamed'}"
    return False, f"auth {auth} is not free"


# ------------------------------------------------------------------------------ scoring
_BLOCS: dict[str, str] = {
    "DE": "EU",
    "FR": "EU",
    "ES": "EU",
    "IT": "EU",
    "NL": "EU",
    "GB": "EUROPE",
    "EU": "EUROPE",
    "HK": "CN",
    "TW": "GREATER_CHINA",
    "CN": "GREATER_CHINA",
    "SA": "MENA",
    "TR": "MENA",
    "MENA": "MENA",
    "BR": "LATAM",
    "LATAM": "LATAM",
    "MX": "LATAM",
}


def region_score(paid: str, sub: str) -> float:
    p, s = str(paid or "global"), str(sub or "global")
    if p.lower() in ("", "unstated"):
        p = "global"
    if p == s:
        return 1.0
    if s == "global":
        return 0.7
    if _BLOCS.get(p) and _BLOCS.get(p) in (_BLOCS.get(s), s):
        return 0.8
    if _BLOCS.get(s) and _BLOCS.get(s) == p:
        return 0.8
    if p == "global":
        return 0.3  # a one-country series cannot replicate a global panel
    return 0.0


def _freq_rank(f: Any) -> float | None:
    return FREQ_RANK.get(str(f or "").strip().lower())


def coverage(
    paid: Mapping[str, Any], sub: Mapping[str, Any], *, now: datetime | None = None
) -> dict[str, Any]:
    """The five-component coverage of `paid` by `sub`: each measured component in [0,1], each
    unmeasured one named, and the weighted mean over the measured ones."""
    now = now or _now()
    comp: dict[str, float | str] = {}
    comp["class"] = 1.0 if str(paid.get("class")) in (sub.get("classes") or []) else 0.0
    comp["region"] = region_score(
        str(paid.get("region") or "global"), str(sub.get("region") or "global")
    )
    pr, sr = _freq_rank(paid.get("frequency")), _freq_rank(sub.get("frequency"))
    if pr is None or sr is None:
        comp["frequency"] = UNMEASURED
    else:
        comp["frequency"] = round(max(0.0, 1.0 - 0.25 * max(0.0, sr - pr)), 3)
    hist = sub.get("history_start")
    try:
        years = max(0.0, now.year - int(hist)) if hist is not None else None
    except (TypeError, ValueError):
        years = None
    need = paid.get("history_years")
    try:
        need_y = float(need) if need not in (None, UNMEASURED, "") else HISTORY_REQUIREMENT_YEARS
    except (TypeError, ValueError):
        need_y = HISTORY_REQUIREMENT_YEARS
    comp["history"] = UNMEASURED if years is None else round(min(1.0, years / max(1.0, need_y)), 3)
    lat = sub.get("latency_days")
    try:
        lat_d = float(lat) if lat is not None else None
    except (TypeError, ValueError):
        lat_d = None
    if lat_d is None or lat_d >= 9999:
        comp["latency"] = UNMEASURED if lat_d is None else 0.0
    else:
        comp["latency"] = (
            1.0
            if lat_d <= 1
            else 0.8
            if lat_d <= 7
            else 0.5
            if lat_d <= 31
            else 0.25
            if lat_d <= 90
            else 0.1
        )
    measured = {k: float(v) for k, v in comp.items() if v != UNMEASURED}
    wsum = sum(WEIGHTS[k] for k in measured)
    score = (
        round(sum(WEIGHTS[k] * v for k, v in measured.items()) / wsum, 4) if wsum else UNMEASURED
    )
    return {
        "score": score,
        "components": comp,
        "measured": sorted(measured),
        "unmeasured": sorted(k for k in comp if k not in measured),
    }


def _series_for(name: str, *, lake: Path, acquired: Mapping[str, Any] | None) -> Any:
    """A numeric series by lake id or acquired-series name, else None."""
    try:
        import pandas as pd
    except Exception:
        return None
    for suf in (".parquet", ".csv"):
        p = lake / f"{name}{suf}"
        if p.exists():
            try:
                df = pd.read_parquet(p) if suf == ".parquet" else pd.read_csv(p)
                if "available_time" in df.columns and SIGNAL in df.columns:
                    return pd.Series(
                        pd.to_numeric(df[SIGNAL], errors="coerce").to_numpy(),
                        index=pd.to_datetime(df["available_time"], utc=True, errors="coerce"),
                    ).dropna()
            except Exception:
                return None
    rec = ((acquired or {}).get("series") or {}).get(name)
    if isinstance(rec, dict) and rec.get("path"):
        try:
            df = pd.read_parquet(Path(str(rec["path"])))
            col = df.columns[0]
            return pd.to_numeric(df[col], errors="coerce").dropna()
        except Exception:
            return None
    return None


def correlation(
    paid: Mapping[str, Any],
    sub: Mapping[str, Any],
    *,
    lake: Path | None = None,
    acquired: Mapping[str, Any] | None = None,
) -> float | str:
    """Pearson correlation of monthly changes when BOTH series are on disk; else UNMEASURED.

    The paid side is only ever a vendor's PUBLIC sample or a published proxy the catalogue row
    names in `public_sample`; no paid data is fetched."""
    sample = paid.get("public_sample")
    if not sample:
        return UNMEASURED
    lk = lake or LAKE
    a = _series_for(str(sample), lake=lk, acquired=acquired)
    b = _series_for(dataset_id(sub), lake=lk, acquired=acquired)
    if b is None:
        for name in _acquired_names(sub, acquired) or []:
            b = _series_for(name, lake=lk, acquired=acquired)
            if b is not None:
                break
    if a is None or b is None:
        return UNMEASURED
    try:
        am = a.resample("ME").last().diff()
        bm = b.resample("ME").last().diff()
        j = am.to_frame("a").join(bm.to_frame("b"), how="inner").dropna()
        if len(j) < 12:
            return UNMEASURED
        c = float(j["a"].corr(j["b"]))
        return round(c, 4) if c == c else UNMEASURED
    except Exception:
        return UNMEASURED


# ------------------------------------------------------------------------------- hunter
def dataset_id(sub: Mapping[str, Any]) -> str:
    """The stable id every cell, state entry and fence row carries for this substitute."""
    return f"psub_{_slug(str(sub.get('id')), 56)}"


def _terms(classes: Mapping[str, Any], cls: str, lang: str) -> str:
    return str((((classes.get("classes") or {}).get(cls) or {}).get("terms") or {}).get(lang) or "")


def _sites(classes: Mapping[str, Any], ttype: str, lang: str) -> list[str]:
    t = (classes.get("targets") or {}).get(ttype) or {}
    sites = t.get(lang)
    if sites is None:
        sites = t.get("*") or []
    return [str(s) for s in sites]


def search_targets(
    catalogue: list[dict[str, Any]], classes: Mapping[str, Any]
) -> list[dict[str, Any]]:
    """Multilingual search targets: one per (class, region, language, target type, site), plus
    vendor-specific replica hunts per paid product. Every one is a deep-forest `search` ground."""
    langs_by_region = classes.get("region_languages") or {}
    all_langs = list(classes.get("languages") or ["en"])
    by_cr: dict[tuple[str, str], list[str]] = defaultdict(list)
    for e in catalogue:
        by_cr[(str(e.get("class")), str(e.get("region") or "global"))].append(str(e.get("id")))
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for (cls, region), pids in sorted(by_cr.items()):
        rkey = region if region in langs_by_region else "global"
        langs = list(dict.fromkeys(["en", *(langs_by_region.get(rkey) or all_langs)]))
        for lang in langs:
            term = _terms(classes, cls, lang)
            if not term:
                continue
            for ttype in classes.get("targets") or {}:
                for site in _sites(classes, ttype, lang):
                    if site and banned(site):
                        continue
                    name = f"paidsub|{cls}|{region}|{lang}|{ttype}|{site or 'web'}"
                    if name in seen:
                        continue
                    seen.add(name)
                    qs = (
                        [term, f"{term} csv", f"{term} api"]
                        if ttype != "public_web"
                        else [term, f"{term} free download", f"{term} historical"]
                    )
                    out.append(
                        {
                            "name": name,
                            "cluster": "paid_substitutes",
                            "kind": "dataset",
                            "route": "search",
                            "site": site,
                            "language": lang,
                            "region": region.lower(),
                            "weight": 0.8,
                            "queries": qs,
                            "class": cls,
                            "target_type": ttype,
                            "paid_ids": sorted(pids)[:25],
                            "why": (
                                f"free substitutes for paid {cls} data ({region}), hunted in "
                                f"{lang} on {site or 'the open web'}"
                            ),
                        }
                    )
    for e in catalogue:
        vendor, ds = str(e.get("vendor") or ""), str(e.get("dataset") or "")
        if vendor in ("", "UNSTATED") and ds in ("", "UNSTATED"):
            continue
        label = " ".join(x for x in (vendor, ds) if x and x != "UNSTATED")
        for ttype, site in (("github", "github.com"), ("public_web", ""), ("zenodo", "zenodo.org")):
            name = f"paidsub|vendor|{e['id']}|{ttype}"
            if name in seen:
                continue
            seen.add(name)
            out.append(
                {
                    "name": name,
                    "cluster": "paid_substitutes",
                    "kind": "dataset",
                    "route": "search",
                    "site": site,
                    "language": "en",
                    "region": str(e.get("region") or "global").lower(),
                    "weight": 0.7,
                    "queries": [
                        f"{label} free alternative data",
                        f"{label} open data replica",
                        f"{label} proxy public dataset",
                    ],
                    "class": str(e.get("class")),
                    "target_type": f"vendor_{ttype}",
                    "paid_ids": [e["id"]],
                    "why": f"a free replica of {label}",
                }
            )
    return out


def library_candidates(
    catalogue: list[dict[str, Any]],
    library: list[dict[str, Any]],
    *,
    environ: Mapping[str, str] | None = None,
    now: datetime | None = None,
    lake: Path | None = None,
    acquired: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """(paid, free) pairs sharing a class and a compatible region, each scored."""
    by_class: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for s in library:
        for c in s.get("classes") or []:
            by_class[str(c)].append(s)
    out: list[dict[str, Any]] = []
    for p in catalogue:
        for s in by_class.get(str(p.get("class")), []):
            if (
                region_score(str(p.get("region") or "global"), str(s.get("region") or "global"))
                <= 0
            ):
                continue
            cov = coverage(p, s, now=now)
            ok, why = usable(s, environ)
            out.append(
                {
                    "paid_id": p["id"],
                    "class": p.get("class"),
                    "paid_region": p.get("region"),
                    "owner": p.get("owner"),
                    "substitute_id": s["id"],
                    "dataset_id": dataset_id(s),
                    "kind": "library",
                    "coverage": cov["score"],
                    "components": cov["components"],
                    "unmeasured": cov["unmeasured"],
                    "correlation": correlation(p, s, lake=lake, acquired=acquired),
                    "usable": ok,
                    "usable_reason": why,
                    "machine_route": str(s.get("endpoint") or "").startswith("http"),
                }
            )
    return out


def discovered_candidates(
    catalogue: list[dict[str, Any]], *, intel_dir: Path | None = None, limit_files: int = 400
) -> list[dict[str, Any]]:
    """Datasets the deep forest FOUND on this engine's grounds (cluster `paid_substitutes`).
    Coverage is measured on class and region only -- frequency/history/latency are UNMEASURED
    until the acquirer characterises the series -- so these never enrol on partial evidence."""
    by_cr: dict[tuple[str, str], list[str]] = defaultdict(list)
    for e in catalogue:
        by_cr[(str(e.get("class")), str(e.get("region") or "global").lower())].append(e["id"])
    out: list[dict[str, Any]] = []
    files = sorted(glob.glob(str((intel_dir or WORLD_INTEL) / "discoveries_*.json")), reverse=True)[
        :limit_files
    ]
    seen: set[str] = set()
    for f in files:
        rows = _read_json(Path(f))
        if not isinstance(rows, list):
            continue
        for r in rows:
            if not isinstance(r, dict) or r.get("cluster") != "paid_substitutes":
                continue
            ground = str(r.get("ground") or "")
            parts = ground.split("|")
            if len(parts) < 3 or parts[0] != "paidsub":
                continue
            url = str(r.get("url") or "")
            if not url or url in seen or banned(url):
                continue
            seen.add(url)
            if parts[1] == "vendor":
                pids = [parts[2]]
                cls = next((e["class"] for e in catalogue if e["id"] == parts[2]), "")
            else:
                cls = parts[1]
                pids = by_cr.get((cls, parts[2].lower()), [])
            sub = {
                "id": f"found_{_key(url)}",
                "classes": [cls],
                "region": parts[2] if parts[1] != "vendor" else "global",
            }
            for pid in pids[:25]:
                p = next((e for e in catalogue if e["id"] == pid), None)
                if p is None:
                    continue
                cov = coverage(
                    p, {**sub, "frequency": None, "history_start": None, "latency_days": None}
                )
                out.append(
                    {
                        "paid_id": pid,
                        "class": cls,
                        "paid_region": p.get("region"),
                        "owner": p.get("owner"),
                        "substitute_id": sub["id"],
                        "dataset_id": dataset_id(sub),
                        "kind": "discovered",
                        "url": url,
                        "endpoints": list(r.get("endpoints") or [])[:10],
                        "coverage": cov["score"],
                        "components": cov["components"],
                        "unmeasured": cov["unmeasured"],
                        "correlation": UNMEASURED,
                        "usable": True,
                        "usable_reason": "found by the forest; UNCHARACTERISED",
                        "machine_route": bool(r.get("endpoints")),
                    }
                )
    return out


def is_match(c: Mapping[str, Any]) -> bool:
    """A substitute MATCHES a paid set: same class, a compatible region (>= MIN_REGION), and
    coverage over the measured components at or above ENROL_THRESHOLD."""
    comp = c.get("components") or {}
    cov = c.get("coverage")
    return (
        comp.get("class") == 1.0
        and isinstance(comp.get("region"), (int, float))
        and float(comp["region"]) >= MIN_REGION
        and isinstance(cov, (int, float))
        and cov >= ENROL_THRESHOLD
    )


def enrolable(c: Mapping[str, Any]) -> bool:
    """A match that is free, reachable, machine-readable, measured enough, and not contradicted
    by a measured correlation. Page-only matches stay hunted (crawl seeds, roster) until an
    endpoint is found; they are never enrolled on a landing page."""
    corr = c.get("correlation")
    live = (c.get("components") or {}).get("latency") != 0.0  # an ended archive: never enrolled
    return (
        is_match(c)
        and live
        and bool(c.get("usable"))
        and bool(c.get("machine_route"))
        and len(WEIGHTS) - len(c.get("unmeasured") or []) >= MIN_MEASURED_COMPONENTS
        and (corr == UNMEASURED or (isinstance(corr, (int, float)) and corr >= MIN_CORRELATION))
    )


# ------------------------------------------------------------------------------ emission
def roster_rows(library: list[dict[str, Any]], matched: set[str]) -> list[dict[str, Any]]:
    """Global-mining roster rows (libs/mining acquirer `external_rosters` glob) for every free
    source that matched at least one paid set."""
    rows: list[dict[str, Any]] = []
    for s in library:
        if s["id"] not in matched or not str(s.get("url") or "").startswith("http"):
            continue
        ep = s.get("endpoint")
        auth = {"none": "none", "ua": "none", "free_key": "key"}.get(str(s.get("auth")), "login")
        rows.append(
            {
                "id": f"paidsub_{s['id']}",
                "name": s.get("name"),
                "url": ep or s.get("url"),
                "fetcher": "page_snapshot",
                "kind": "mechanics",
                "region": s.get("region"),
                "language": (s.get("languages") or ["en"])[0],
                "cadence": {"intraday": "hourly", "hourly": "hourly", "daily": "daily"}.get(
                    str(s.get("frequency")), "daily"
                ),
                "auth": auth,
                "auth_env": s.get("auth_env") or "",
                "licence": s.get("licence"),
                "uses": ["direct_cells", "indirect_cells", "allocation_intel"],
                "consumer": "desks/mt5/research/paid_substitute_engine.py",
                "owner": GENERATOR,
                "dataset_id": dataset_id(s),
                "immutable_time": False,
            }
        )
    return rows


def crawl_seed_urls(library: list[dict[str, Any]], matched: set[str]) -> list[str]:
    out: list[str] = []
    for s in library:
        u = str(s.get("url") or "")
        if s["id"] in matched and u.startswith("http") and not banned(u) and u not in out:
            out.append(u)
    return out


def discovery_rows(
    library: list[dict[str, Any]],
    matched: set[str],
    now: datetime,
    environ: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
    """acquire_datasets reads `endpoints` from world discoveries: one row per matched key-less
    source that publishes a machine endpoint."""
    rows: list[dict[str, Any]] = []
    for s in library:
        ep = str(s.get("endpoint") or "")
        if s["id"] not in matched or not ep.startswith("http") or banned(ep):
            continue
        if str(s.get("auth")) != "none":
            continue
        rows.append(
            {
                "source": GENERATOR,
                "kind": "dataset",
                "title": str(s.get("name"))[:160],
                "url": s.get("url"),
                "published": _iso(now),
                "symbols": list(s.get("instruments") or []),
                "timeframes": [],
                "patterns": [],
                "confidence": 0.8,
                "lang": (s.get("languages") or ["en"])[0],
                "endpoints": [ep],
                "n_endpoints": 1,
                "dataset_class": (s.get("classes") or [""])[0],
                "dataset_id": dataset_id(s),
                "host": urllib.parse.urlparse(ep).netloc,
            }
        )
    return rows


# ------------------------------------------------------------------------------ enrolment
def _universe(path: Path | None = None) -> set[str]:
    doc = _read_json(path or UNIVERSE)
    return set(doc) if isinstance(doc, dict) else set()


def admissible_targets(symbols: Iterable[str], family: str, universe: set[str]) -> list[str]:
    try:
        from universe_policy import may_hypothesise  # type: ignore[import-not-found]
    except Exception:

        def may_hypothesise(symbol: str, family: object = None) -> bool:
            return False

    out: list[str] = []
    for s in symbols:
        s = str(s)
        if s in universe and s not in out:
            try:
                if may_hypothesise(s, family):
                    out.append(s)
            except Exception:
                continue
    return out


def targets_of(sub: Mapping[str, Any], classes: Mapping[str, Any]) -> list[str]:
    inst = sub.get("instruments")
    if inst:
        return [str(x) for x in inst]
    cls = (classes.get("classes") or {}).get(str((sub.get("classes") or [""])[0])) or {}
    m = cls.get("instruments") or {}
    return [str(x) for x in (m.get(str(sub.get("region"))) or m.get("global") or [])]


def gate_family_available() -> bool:
    try:
        import mt5desk.family_exogenous_gate  # noqa: F401

        return True
    except Exception:
        return False


def gate_bases() -> list[str]:
    try:
        from mt5desk.family_exit_operated import wrappable
    except Exception:
        return []
    out = []
    for b in GATE_BASES:
        try:
            if wrappable(b):
                out.append(b)
        except Exception:
            continue
    return out


def series_present(did: str, lake: Path | None = None) -> bool:
    base = lake or LAKE
    return any((base / f"{did}{s}").exists() for s in (".parquet", ".csv"))


def _acquired_names(sub: Mapping[str, Any], acquired: Mapping[str, Any] | None) -> list[str]:
    ep = str(sub.get("endpoint") or "")
    rec = ((acquired or {}).get("by_url") or {}).get(ep) if ep else None
    return [str(x) for x in (rec or {}).get("series") or []] if isinstance(rec, dict) else []


def materialise(
    sub: Mapping[str, Any], *, lake: Path | None = None, acquired: Mapping[str, Any] | None = None
) -> str:
    """Write the substitute's lake frame from what acquire_datasets fetched: `value` plus a
    point-in-time `available_time` = period + the source's declared latency (at least a day).
    Returns the status. Never invents a stamp: no acquired series means NOT_ACQUIRED."""
    did = dataset_id(sub)
    base = lake or LAKE
    if series_present(did, base):
        return "PRESENT"
    names = _acquired_names(sub, acquired)
    if not names:
        return "NOT_ACQUIRED"
    try:
        import pandas as pd

        rec = ((acquired or {}).get("series") or {}).get(names[0]) or {}
        df = pd.read_parquet(Path(str(rec.get("path"))))
        col = df.columns[0]
        idx = pd.to_datetime(df.index, utc=True, errors="coerce")
        lat = float(sub.get("latency_days") or 1)
        frame = pd.DataFrame(
            {
                SIGNAL: pd.to_numeric(df[col], errors="coerce").to_numpy(),
                "available_time": idx + pd.Timedelta(days=max(1.0, min(lat, 400.0))),
                "source_id": did,
            }
        ).dropna(subset=[SIGNAL, "available_time"])
        if frame.empty:
            return "EMPTY"
        base.mkdir(parents=True, exist_ok=True)
        frame.to_parquet(base / f"{did}.parquet", index=False)
        return "WRITTEN"
    except Exception as exc:
        return f"ERROR: {type(exc).__name__}"


def _registry_door() -> Callable[..., tuple[str, bool]]:
    from libs.moat.registry import enqueue_candidate

    return enqueue_candidate


def _culture(sub: Mapping[str, Any]) -> dict[str, str]:
    """The three culture keys (cell_culture's names). Declared on the library row where it has
    them; the jurisdiction from the region otherwise; UNMEASURED never guessed."""
    region = str(sub.get("region") or "")
    lang = (sub.get("languages") or [""])[0]
    culture = UNMEASURED
    try:
        from libs.research.cell_culture import culture_tag  # type: ignore[import-not-found]

        culture = culture_tag(region if region != "global" else "GLOBAL", lang) or UNMEASURED
    except Exception:
        culture = (
            f"{region.upper()}/{lang}"
            if region and region != "global" and lang
            else ("GLOBAL" if region == "global" else UNMEASURED)
        )
    return {
        "source_culture": culture,
        "participant_structure": str(sub.get("participant_structure") or UNMEASURED),
        "failure_mode_hypothesis": str(
            sub.get("failure_mode_hypothesis")
            or (
                f"a free {'/'.join(sub.get('classes') or [])} series read by every desk with "
                f"the same "
                f"public release; it should fail when that release is crowded or revised, not when "
                f"the paid vendor's panel is"
            )
        ),
    }


def emit_uses(
    sub: Mapping[str, Any],
    *,
    classes: Mapping[str, Any],
    minted: set[str],
    universe: set[str],
    lake: Path | None = None,
    door: Callable[..., Any] | None = None,
    budget: list[int] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """The three uses of one ENROLLED substitute (its lake frame exists). Idempotent: a cell is
    enqueued once, ever, as `queued` -- claimable on arrival, never parked (the no-queues law,
    2026-09-23). An indirect cell needs `family_exogenous_gate`; on a tree without it the use is
    reported BLOCKED with that reason instead of minting cells nothing can execute."""
    did = dataset_id(sub)
    have_series = series_present(did, lake)
    have_gate = gate_family_available()
    bases = gate_bases() if have_gate else []
    raw = targets_of(sub, classes)
    d_targets = admissible_targets(raw, "exogenous_conditioner", universe)
    g_targets = admissible_targets(raw, "exogenous_gate", universe)
    culture = _culture(sub)
    mech = (
        f"{sub.get('name')} is the free replica of a paid {'/'.join(sub.get('classes') or [])} "
        f"dataset; while its series is at an extreme, {', '.join(d_targets) or 'its instruments'} "
        f"trade differently"
    )
    common = {
        "origin": GENERATOR,
        "generator": GENERATOR,
        "department": "information",
        "source_id": did,
        "campaign_id": f"paid_substitute:{did}",
        "pit_status": "STAMPED",
        "required_data": [f"desks/mt5/data/lake/series/{did}.parquet"],
        "causal_rationale": mech,
        **culture,
    }
    stats: dict[str, Any] = {
        "dataset_id": did,
        "direct": 0,
        "indirect": 0,
        "created": 0,
        "already": 0,
        "deferred": 0,
        "errors": [],
        "direct_targets": d_targets,
        "gate_targets": g_targets,
        "gate_bases": bases,
        "indirect_blocked": (
            None
            if have_gate
            else "family_exogenous_gate is not on this tree (it lands with the world factory, #123)"
        ),
    }
    if not have_series:
        stats["errors"].append("no lake frame: not enrolled, nothing minted")
        return stats
    left = budget if budget is not None else [CELLS_PER_PASS]
    enqueue = None if dry_run else (door or _registry_door())

    def put(kind: str, k: str, **kw: Any) -> None:
        if k in minted:
            stats["already"] += 1
            stats[kind] += 1
            return
        if left[0] <= 0:
            stats["deferred"] += 1
            return
        left[0] -= 1
        stats[kind] += 1
        if enqueue is None:
            return
        try:
            _cid, new = enqueue(**kw, **common)
            stats["created"] += int(bool(new))
            minted.add(k)
        except Exception as exc:
            stats["errors"].append(f"{kind}: {type(exc).__name__}: {str(exc)[:60]}")

    for tf in TRANSFORMS:
        for sym in d_targets:
            for chart in CHARTS:
                put(
                    "direct",
                    _key("d", did, SIGNAL, tf, sym, chart),
                    family="exogenous_conditioner",
                    symbol=sym,
                    status="queued",
                    params={"source": did, "signal": SIGNAL, "transform": tf},
                    mechanism=mech,
                    chart=chart,
                    horizon=chart,
                    asset_class="",
                    transformation="paid_substitute_series",
                    falsifier=(
                        f"the {tf} of {did}.{SIGNAL} has no measurable relation to {sym} at "
                        f"{chart} out of sample"
                    ),
                )
    for base in bases:
        for sym in g_targets:
            for band in GATE_BANDS:
                put(
                    "indirect",
                    _key("g", did, SIGNAL, base, sym, band),
                    family="exogenous_gate",
                    symbol=sym,
                    status="queued",
                    params={
                        "base_family": base,
                        "base_params": {},
                        "source": did,
                        "signal": SIGNAL,
                        "transform": "level_z",
                        "threshold": GATE_THRESHOLD,
                        "band": band,
                    },
                    mechanism=f"{base} on {sym} behaves differently while {did}.{SIGNAL} is {band}",
                    chart=GATE_CHART,
                    horizon=GATE_CHART,
                    asset_class="",
                    transformation="paid_substitute_gate",
                    falsifier=(
                        f"{base} on {sym} gated to {did}.{SIGNAL} {band} is no better than "
                        "the ungated base out of sample"
                    ),
                )
    stats["errors"] = stats["errors"][:6]
    return stats


def cells_fed(*, conn: sqlite3.Connection | None = None) -> dict[str, dict[str, int]] | str:
    """Registry rows this engine minted, per dataset_id and status; UNMEASURED if unreachable."""
    close = conn is None
    try:
        if conn is None:
            from libs.moat import registry as reg

            if not Path(reg.path()).exists():
                return f"{UNMEASURED}: no candidate registry on this host"
            conn = reg.connect()
        rows = conn.execute(
            "SELECT source_id, family, status, COUNT(*) FROM research_candidates "
            "WHERE origin=? GROUP BY source_id, family, status",
            (GENERATOR,),
        ).fetchall()
    except Exception as exc:
        return f"{UNMEASURED}: {type(exc).__name__}"
    finally:
        if close and conn is not None:
            with contextlib.suppress(Exception):
                conn.close()
    out: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for sid, fam, status, n in rows:
        key = "direct" if fam == "exogenous_conditioner" else "indirect"
        out[str(sid)][f"{key}_{status}"] += int(n)
        out[str(sid)][key] += int(n)
    return {k: dict(v) for k, v in out.items()}


def state_inputs(
    enrolled: list[dict[str, Any]],
    *,
    classes: Mapping[str, Any],
    universe: set[str],
    now: datetime,
    lake: Path | None = None,
) -> list[dict[str, Any]]:
    """The ALLOCATION use: current lagged z of each enrolled series (UNMEASURED until its lake
    frame exists), per instrument. ADVISORY; nothing here is read by the sealed allocator."""
    rows: list[dict[str, Any]] = []
    for sub in enrolled:
        did = dataset_id(sub)
        z: float | str = UNMEASURED
        at = None
        try:
            from mt5desk.family_exogenous_conditioner import conditioner

            cond = conditioner(did, SIGNAL, "level_z", root=lake or LAKE)
            if cond is not None and not cond.empty:
                import pandas as pd

                known = cond[cond.index <= pd.Timestamp(now)]
                if not known.empty:
                    z, at = round(float(known.iloc[-1]), 4), known.index[-1]
        except Exception:
            pass
        rows.append(
            {
                "dataset_id": did,
                "source": did,
                "signal": SIGNAL,
                "z_lagged": z,
                "usable_since": str(at) if at is not None else None,
                "age_h": (
                    round((now - at.to_pydatetime()).total_seconds() / 3600, 1)
                    if at is not None
                    else UNMEASURED
                ),
                "instruments": admissible_targets(
                    targets_of(sub, classes), "exogenous_conditioner", universe
                ),
                "classes": list(sub.get("classes") or []),
                "substitute": sub.get("id"),
                "origin": GENERATOR,
            }
        )
    return rows


def write_world_state(rows: list[dict[str, Any]], now: datetime, path: Path | None = None) -> None:
    """Upsert this engine's block into WORLD_STATE_INPUTS.json, preserving every other key (the
    world factory owns the rest of the document and rewrites it on its own clock)."""
    p = path or WORLD_STATE
    doc = _read_json(p)
    if not isinstance(doc, dict):
        doc = {"generated_at": _iso(now), "advisory": True, "series": [], "by_instrument": {}}
    doc["paid_substitutes"] = {
        "generated_at": _iso(now),
        "generator": GENERATOR,
        "advisory": True,
        "n": len(rows),
        "rule": (
            "one entry per enrolled paid substitute, keyed by dataset_id; z is the series' "
            "own level z lagged a publication day, UNMEASURED until its lake frame exists"
        ),
        "series": rows,
    }
    _atomic_json(p, doc)


# -------------------------------------------------------------------------------- report
def summarise(
    catalogue: list[dict[str, Any]],
    cands: list[dict[str, Any]],
    enrolled_ids: set[str],
    fed: Any,
    asia_classes: Iterable[str] = (),
) -> list[dict[str, Any]]:
    """Per (class, region): paid sets, matched, best strength, enrolled substitutes, cells fed."""
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    for e in catalogue:
        g = groups.setdefault(
            (str(e.get("class")), str(e.get("region") or "global")),
            {
                "class": str(e.get("class")),
                "region": str(e.get("region") or "global"),
                "owner": "asia" if str(e.get("class")) in set(asia_classes) else GENERATOR,
                "asia_rows": 0,
                "paid_sets": 0,
                "matched": 0,
                "enrolled_substitutes": set(),
                "best_coverage": None,
                "best_correlation": UNMEASURED,
                "_paid": set(),
            },
        )
        g["paid_sets"] += 1
        g["_paid"].add(e["id"])
        if str(e.get("seed_source") or "").startswith("asia_thread_table"):
            g["asia_rows"] += 1
    best_by_paid: dict[str, dict[str, Any]] = {}
    matched_paid: set[str] = set()
    for c in cands:
        if is_match(c):
            matched_paid.add(c["paid_id"])
        b = best_by_paid.get(c["paid_id"])
        cov = c.get("coverage")
        if isinstance(cov, (int, float)) and (b is None or cov > (b.get("coverage") or 0)):
            best_by_paid[c["paid_id"]] = c
    by_paid_enrolled: dict[str, set[str]] = defaultdict(set)
    for c in cands:
        if c.get("dataset_id") in enrolled_ids and enrolable(c):
            by_paid_enrolled[c["paid_id"]].add(c["dataset_id"])
    for g in groups.values():
        for pid in g["_paid"]:
            b = best_by_paid.get(pid)
            if pid in matched_paid:
                g["matched"] += 1
            if b is not None and isinstance(b.get("coverage"), (int, float)):
                g["best_coverage"] = max(g["best_coverage"] or 0.0, b["coverage"])
                if isinstance(b.get("correlation"), (int, float)):
                    g["best_correlation"] = (
                        b["correlation"]
                        if g["best_correlation"] == UNMEASURED
                        else max(g["best_correlation"], b["correlation"])
                    )
            g["enrolled_substitutes"] |= by_paid_enrolled.get(pid, set())
    out = []
    for g in sorted(groups.values(), key=lambda x: (x["class"], x["region"])):
        enr = sorted(g.pop("enrolled_substitutes"))
        g.pop("_paid")
        best_cov = g.pop("best_coverage")
        best_corr = g.pop("best_correlation")
        if isinstance(fed, dict):
            cells: Any = {
                "direct": sum(int((fed.get(d) or {}).get("direct", 0)) for d in enr),
                "indirect": sum(int((fed.get(d) or {}).get("indirect", 0)) for d in enr),
                "queued": sum(
                    int((fed.get(d) or {}).get("direct_queued", 0))
                    + int((fed.get(d) or {}).get("indirect_queued", 0))
                    for d in enr
                ),
            }
        else:
            cells = fed
        g.update(
            enrolled_substitutes=enr,
            n_enrolled=len(enr),
            cells_fed=cells,
            match_strength={
                "coverage": best_cov if best_cov is not None else UNMEASURED,
                "correlation": best_corr,
            },
            match_share=round(g["matched"] / g["paid_sets"], 4) if g["paid_sets"] else UNMEASURED,
        )
        out.append(g)
    return out


def render_md(doc: Mapping[str, Any]) -> str:
    h = doc["headline"]
    lines = [
        "# PAID SUBSTITUTE COVERAGE",
        "",
        "<!-- DERIVED. Written by desks/mt5/research/paid_substitute_engine.py on the clock "
        "`hourly_cycle:paid_substitute_engine`. Edit the organ, never this file. -->",
        "",
        f"Generated **{doc['generated_at']}**. Catalogue **{h['catalogue_size']}** paid sets "
        f"(floor {h['catalogue_floor']}); **{h['paid_with_match']}** have a free substitute at "
        f"coverage >= {ENROL_THRESHOLD} -- coverage share **{h['coverage_share']}**. "
        f"Candidates generated **{h['candidates_generated']}** "
        f"({h['search_targets']} multilingual search targets + {h['library_candidates']} library "
        f"pairs + {h['discovered_candidates']} found by the forest); scored "
        f"**{h['candidates_scored']}**; enrolled substitutes **{h['enrolled']}**.",
        "",
        f"Asia table: `{doc['asia']['status']}`.",
        "",
        "| class | region | owner | paid sets | matched | share | best coverage | correlation "
        "| enrolled | cells fed |",
        "|---|---|---|---:|---:|---:|---:|---|---:|---|",
    ]
    for r in doc["by_class_region"]:
        ms = r["match_strength"]
        cf = r["cells_fed"]
        cf_s = (
            cf
            if isinstance(cf, str)
            else f"{cf['direct']}d/{cf['indirect']}i ({cf['queued']} queued)"
        )
        lines.append(
            f"| {r['class']} | {r['region']} | {r['owner']} | {r['paid_sets']} | {r['matched']} | "
            f"{r['match_share']} | {ms['coverage']} | {ms['correlation']} | {r['n_enrolled']} "
            f"| {cf_s} |"
        )
    lines += [
        "",
        "Correlation is UNMEASURED wherever the paid side has no public sample on disk -- "
        "it is never scored as zero. Coverage averages only the measured components.",
        "",
    ]
    return "\n".join(lines)


# ----------------------------------------------------------------------------------- run
def run(
    *,
    now: datetime | None = None,
    fetch: bool = True,
    dry_run: bool = False,
    paths: Mapping[str, Path] | None = None,
    environ: Mapping[str, str] | None = None,
    door: Callable[..., Any] | None = None,
    http: Callable[[str], tuple[int | None, str]] | None = None,
    registry_conn: sqlite3.Connection | None = None,
    asia_globs: Iterable[str] | None = None,
    crawl_budget_s: float = CRAWL_BUDGET_S,
) -> dict[str, Any]:
    now = now or _now()
    p = {
        "catalogue": CATALOGUE_DIR,
        "classes": CLASSES,
        "listings": LISTINGS,
        "floor": FLOOR,
        "library": LIBRARY,
        "crawled": CRAWLED,
        "state": STATE,
        "seeds": SEEDS,
        "enrolled": ENROLLED,
        "roster": ROSTER,
        "forest": FOREST_QUEUE,
        "intel": WORLD_INTEL,
        "lake": LAKE,
        "acquired": ACQUIRED,
        "universe": UNIVERSE,
        "report": REPORT,
        "report_md": REPORT_MD,
        "world_state": WORLD_STATE,
        **dict(paths or {}),
    }
    t0 = time.monotonic()
    classes = load_classes(p["classes"])
    crawl = (
        {"status": "SKIPPED (--no-fetch)"}
        if not fetch
        else crawl_catalogue(
            listings_path=p["listings"],
            crawled_path=p["crawled"],
            fetch=http,
            now=now,
            budget_s=crawl_budget_s,
            write=not dry_run,
        )
    )
    asia_path = find_asia_table(asia_globs)
    asia: dict[str, Any] = (
        parse_asia_table(asia_path)
        if asia_path
        else {
            "status": f"{UNMEASURED}: the Asia table is not on this host",
            "searched": [
                os.environ.get(ASIA_TABLE_ENV, "") or "(env unset)",
                *(asia_globs if asia_globs is not None else ASIA_TABLE_GLOBS),
            ],
            "entries": [],
            "substitutes": [],
            "classes": [],
        }
    )
    if asia_path:
        asia["status"] = f"READ {asia_path.name}: {asia['rows']} rows"
    asia["owned_classes"] = sorted(set(ASIA_CLASSES.values()))
    catalogue = load_catalogue(
        catalogue_dir=p["catalogue"],
        crawled=p["crawled"],
        classes=classes,
        asia_rows=asia.get("entries") or [],
    )
    library = load_library(p["library"])
    acquired = _read_json(p["acquired"])
    acquired = acquired if isinstance(acquired, dict) else None
    lib_c = library_candidates(
        catalogue, library, environ=environ, now=now, lake=p["lake"], acquired=acquired
    )
    disc_c = discovered_candidates(catalogue, intel_dir=p["intel"])
    grounds = search_targets(catalogue, classes)
    cands = lib_c + disc_c
    matched = {c["substitute_id"] for c in lib_c if is_match(c)}
    ready_ids = sorted({c["substitute_id"] for c in lib_c if enrolable(c)})
    lib_by_id = {s["id"]: s for s in library}
    ready = [lib_by_id[i] for i in ready_ids if i in lib_by_id]

    state = _read_json(p["state"]) or {}
    minted = set(state.get("minted") or [])
    prev_enrolled = dict(state.get("enrolled_at") or {})
    universe = _universe(p["universe"])
    uses: list[dict[str, Any]] = []
    materialised: dict[str, str] = {}
    budget = [CELLS_PER_PASS]
    # ENROLMENT IS HAVING THE SERIES. A ready substitute (matched, free, machine endpoint) whose
    # series acquire_datasets has not fetched yet is AWAITING_ACQUISITION: its endpoint is in this
    # hour's discoveries, which the acquirer drains on its own hourly leg. Nothing is minted on a
    # series that does not exist, so no trial is charged against the shared multiple-testing budget
    # for a question that cannot yet be asked, and nothing is parked in the registry.
    enrolled: list[dict[str, Any]] = []
    for sub in ready:
        did = dataset_id(sub)
        materialised[did] = (
            materialise(sub, lake=p["lake"], acquired=acquired)
            if not dry_run
            else ("PRESENT" if series_present(did, p["lake"]) else "NOT_ACQUIRED")
        )
        if not series_present(did, p["lake"]):
            continue
        enrolled.append(sub)
        prev_enrolled.setdefault(did, _iso(now))
        uses.append(
            emit_uses(
                sub,
                classes=classes,
                minted=minted,
                universe=universe,
                lake=p["lake"],
                door=door,
                budget=budget,
                dry_run=dry_run,
            )
        )
    ws_rows = state_inputs(enrolled, classes=classes, universe=universe, now=now, lake=p["lake"])
    fed = (
        cells_fed(conn=registry_conn)
        if (registry_conn is not None or not dry_run)
        else f"{UNMEASURED}: dry run"
    )

    if not dry_run:
        forest = grounds[:FOREST_QUEUE_CAP]
        _atomic_json(
            p["forest"],
            {
                "note": (
                    "paid-substitute search grounds; ONE cluster "
                    "(`paid_substitutes`) so the forest's round-robin "
                    "gives it a fair turn. Written hourly by "
                    "research/paid_substitute_engine.py."
                ),
                "generated_at": _iso(now),
                "grounds": forest,
            },
        )
        _atomic_json(
            p["seeds"], {"generated_at": _iso(now), "urls": crawl_seed_urls(library, matched)}
        )
        _atomic_json(
            p["roster"],
            {
                "note": "free substitutes for paid datasets (paid_substitute_engine)",
                "generated_at": _iso(now),
                "sources": roster_rows(library, matched),
            },
        )
        drows = discovery_rows(library, matched, now, environ)
        if drows:
            _atomic_json(p["intel"] / f"discoveries_paidsub_{now:%Y%m%d}.json", drows)
        write_world_state(ws_rows, now, p["world_state"])
        _atomic_json(
            p["enrolled"],
            {
                "generated_at": _iso(now),
                "enrolled": [
                    {
                        "dataset_id": dataset_id(s),
                        "substitute": s["id"],
                        "name": s.get("name"),
                        "classes": s.get("classes"),
                        "region": s.get("region"),
                        "enrolled_at": prev_enrolled.get(dataset_id(s)),
                        "lake": materialised.get(dataset_id(s)),
                        "uses": ["direct_cells", "indirect_cells", "WORLD_STATE_INPUTS"],
                        **_culture(s),
                    }
                    for s in enrolled
                ],
            },
        )
        _atomic_json(
            p["state"],
            {
                "updated_at": _iso(now),
                "minted": sorted(minted),
                "enrolled_at": prev_enrolled,
                "catalogue_high_water": max(
                    int(state.get("catalogue_high_water") or 0), len(catalogue)
                ),
            },
        )

    enrolled_ids = {dataset_id(s) for s in enrolled}
    rows = summarise(catalogue, cands, enrolled_ids, fed, asia["owned_classes"])
    paid_with_match = sum(r["matched"] for r in rows)
    n_scored = sum(1 for c in cands if isinstance(c.get("coverage"), (int, float)))
    floor = catalogue_floor(p["floor"])
    seeds_by_src = Counter(str(e.get("seed_source") or "").split(":", 1)[0] for e in catalogue)
    three = {
        "direct_cells": sum(u["direct"] for u in uses),
        "indirect_cells": sum(u["indirect"] for u in uses),
        "world_state_inputs": len(ws_rows),
        "created_this_pass": sum(u["created"] for u in uses),
        "deferred_to_next_pass": sum(u["deferred"] for u in uses),
        "gate_family_available": gate_family_available(),
        "enrolled_missing_a_use": sorted(
            u["dataset_id"] for u in uses if not (u["direct"] and u["indirect"])
        ),
        "indirect_blocked": next((u["indirect_blocked"] for u in uses if u["indirect_blocked"]),
                                 None),
    }
    doc: dict[str, Any] = {
        "generated_at": _iso(now),
        "generator": GENERATOR,
        "dry_run": dry_run,
        "headline": {
            "catalogue_size": len(catalogue),
            "catalogue_floor": floor,
            "catalogue_by_seed_source": dict(seeds_by_src),
            "classes": len({e.get("class") for e in catalogue}),
            "free_library": len(library),
            "candidates_generated": len(grounds) + len(cands),
            "search_targets": len(grounds),
            "library_candidates": len(lib_c),
            "discovered_candidates": len(disc_c),
            "candidates_scored": n_scored,
            "enrolled": len(enrolled),
            "ready_awaiting_acquisition": len(ready) - len(enrolled),
            "paid_with_match": paid_with_match,
            "coverage_share": round(paid_with_match / len(catalogue), 4)
            if catalogue
            else UNMEASURED,
            "coverage_basis": (
                "class/region/frequency/history/latency match of a FREE series to the "
                "paid set -- not entity-level replication; replication is the "
                "correlation, measured only where both series are on disk"
            ),
            "paid_with_enrolled": len(
                {
                    c["paid_id"]
                    for c in cands
                    if c.get("dataset_id") in enrolled_ids and enrolable(c)
                }
            ),
            "correlation_measured_pairs": sum(
                1 for c in cands if isinstance(c.get("correlation"), (int, float))
            ),
            "languages": sorted({g["language"] for g in grounds}),
            "unusable_free_key_missing": sorted(
                {c["usable_reason"] for c in lib_c if not c["usable"]}
            )[:20],
        },
        "three_uses": three,
        "lake_frames": dict(Counter(materialised.values())),
        "cells_fed": fed
        if isinstance(fed, str)
        else {
            "datasets": len(fed),
            "total": sum(v.get("direct", 0) + v.get("indirect", 0) for v in fed.values()),
        },
        "catalogue_crawl": crawl,
        "asia": {k: v for k, v in asia.items() if k != "entries"},
        "by_class_region": rows,
        "rule": (
            "coverage = weighted mean of the MEASURED components among class .35, region .25, "
            f"frequency .15, history .15, latency .10; enrol at >= {ENROL_THRESHOLD} with >= "
            f"{MIN_MEASURED_COMPONENTS} measured and correlation UNMEASURED or >= "
            f"{MIN_CORRELATION}; "
            "an enrolled substitute feeds direct cells, exogenous_gate cells and "
            "WORLD_STATE_INPUTS under one dataset_id"
        ),
        "wall_s": round(time.monotonic() - t0, 2),
    }
    _atomic_json(p["report"], doc)
    p["report_md"].parent.mkdir(parents=True, exist_ok=True)
    p["report_md"].write_text(render_md(doc), "utf-8")
    return doc


# --------------------------------------------------------------------------------- fence
#: The report is stale past this. Six hours, not two: the leg is in CORE_LEGS, but the core plan
#: itself rotates legs across passes when a pass overruns (libs/ops/leg_rotation), so a healthy
#: leg can miss an hour; three missed passes in a row is a clock that has stopped.
FENCE_MAX_AGE_S = 6 * 3600


def fence(
    report: Path | None = None,
    *,
    catalogue_dir: Path | None = None,
    floor_path: Path | None = None,
    max_age_s: float = FENCE_MAX_AGE_S,
    now: datetime | None = None,
    require_report: bool = True,
) -> list[str]:
    """Failures, empty when clean: the report is present and fresh, and the catalogue has not
    shrunk below its committed floor (or below the report's own recorded size)."""
    now = now or _now()
    fails: list[str] = []
    n = len(
        load_catalogue(
            catalogue_dir=catalogue_dir or CATALOGUE_DIR,
            crawled=Path("/nonexistent"),
            classes=load_classes((catalogue_dir or CATALOGUE_DIR) / "_classes.json"),
        )
    )
    floor = catalogue_floor(floor_path or ((catalogue_dir or CATALOGUE_DIR) / "_floor.json"))
    if n < floor:
        fails.append(f"catalogue shrank: {n} seeded paid sets < floor {floor}")
    doc = _read_json(report or REPORT)
    if not isinstance(doc, dict):
        if require_report:
            fails.append(f"report absent: {report or REPORT}")
        return fails
    try:
        at = datetime.fromisoformat(str(doc.get("generated_at")))
        age = (now - at).total_seconds()
    except (TypeError, ValueError):
        fails.append("report carries no readable generated_at")
        return fails
    if age > max_age_s:
        fails.append(f"report stale: {age / 3600:.1f}h old (> {max_age_s / 3600:.1f}h)")
    h = doc.get("headline") or {}
    if int(h.get("catalogue_size") or 0) < floor:
        fails.append(f"report's catalogue {h.get('catalogue_size')} < floor {floor}")
    return fails


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--no-fetch", action="store_true", help="skip the catalogue crawl")
    ap.add_argument("--dry-run", action="store_true", help="measure; write only the report")
    ap.add_argument("--crawl-budget-s", type=float, default=CRAWL_BUDGET_S)
    ap.add_argument(
        "--fence", action="store_true", help="check freshness and the floor; exit 1 on failure"
    )
    a = ap.parse_args(argv)
    if a.fence:
        fails = fence()
        for f in fails:
            print(f"FAIL {f}")
        print("paid_substitute fence:", "FAIL" if fails else "OK")
        return 1 if fails else 0
    doc = run(fetch=not a.no_fetch, dry_run=a.dry_run, crawl_budget_s=a.crawl_budget_s)
    h = doc["headline"]
    print(
        f"paid_substitute_engine: catalogue={h['catalogue_size']} "
        f"generated={h['candidates_generated']} scored={h['candidates_scored']} "
        f"enrolled={h['enrolled']} coverage_share={h['coverage_share']} "
        f"direct={doc['three_uses']['direct_cells']} "
        f"indirect={doc['three_uses']['indirect_cells']} "
        f"state_inputs={doc['three_uses']['world_state_inputs']} wall={doc['wall_s']}s"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
