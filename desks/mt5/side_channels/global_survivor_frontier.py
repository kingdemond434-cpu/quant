"""GLOBAL SURVIVOR FRONTIER -- the adaptive discovery cell (principal 2026-08-26).

THE PROPERTY THIS BUYS, and why it replaces writing another 50 manual miners: every language
gets a permanent discovery CELL that mutates native terminology into native queries, finds
source populations we never listed, collapses localized duplicates onto one underlying
platform, scores what it finds, and GRADUATES high-value sources into permanent miners by
writing them to a registry the regional hunters read. A new foreign ecosystem appearing
tomorrow is discovered by the machinery, not by a human remembering to add it.

NO CELL IS EVER "DONE". Coverage is a measured ratchet per locale (native operators exercised,
unique populations found, graduation count, rediscovery freshness) -- KO/TR/FA stay OPEN
frontiers with standing canary searches rather than being falsely marked exhausted.

DEDUP IS THE ANTI-FAKE-BREADTH RULE: an Arabic and a Vietnamese window onto LiteFinance are ONE
population, not two. Registration keys on the resolved apex domain, and localized hosts are
recorded as language windows of the same population.

Zero LLM. Rotating locale cursor: a few queries per hour, every locale revisited forever.
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.parse
from datetime import UTC, datetime
from pathlib import Path

import requests

_dir = str(Path(__file__).resolve().parent)
if _dir not in sys.path:
    sys.path.insert(0, _dir)
from lang_intel import LEXICON  # noqa: E402

BASE = Path(__file__).resolve().parent.parent
INTEL = BASE / "data" / "intelligence"
OUT = INTEL / "frontier"
POPULATIONS = INTEL / "source_populations.json"
FRONTIER = INTEL / "frontier_coverage.json"
STATE = INTEL / "frontier_state.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"}

#: Every locale is a permanent cell. "open_frontier" cells are the ones no strong native
#: survivor pool has been found for YET -- they get canary priority, never a "done" flag.
LOCALES = {
    "zh": {"region": "China", "open_frontier": False},
    "ja": {"region": "Japan", "open_frontier": False},
    "ru": {"region": "CIS", "open_frontier": False},
    "ar": {"region": "MENA", "open_frontier": False},
    "es": {"region": "LATAM/Spain", "open_frontier": False},
    "pt": {"region": "Brazil/Portugal", "open_frontier": False},
    "vi": {"region": "Vietnam", "open_frontier": False},
    "id": {"region": "Indonesia", "open_frontier": True},
    "ko": {"region": "Korea", "open_frontier": True},
    "tr": {"region": "Turkey", "open_frontier": True},
    "de": {"region": "DACH", "open_frontier": True},
    "fr": {"region": "France/Africa francophone", "open_frontier": True},
    "en": {"region": "global", "open_frontier": False},
}

#: Concepts mutated into native queries. Cross-product with LEXICON gives native operators in
#: every script -- the frontier-dig discipline, applied by a script instead of a session.
QUERY_CONCEPTS = ("copy_trading", "return", "drawdown", "ea_robot", "followers")
QUERIES_PER_RUN = 3
RESULTS_PER_QUERY = 12

#: Platforms already mined -- discovered hosts resolving to these are language windows, not
#: new populations (anti-fake-breadth).
KNOWN_APEX = {
    "mql5.com", "myfxbook.com", "fxblue.com", "ctrader.com", "darwinex.com",
    "collective2.com", "quantconnect.com", "tradingview.com", "followme.com",
    "amarkets.com", "litefinance.org", "instaforex.com", "roboforex.pro",
    "roboforex.com", "hfm.com", "octabroker.com", "share4you.com", "markets4you.com",
    "duplitrade.com", "equiti.com", "trading-latam.com", "min-fx.jp", "mylivefx.com",
    "ready-trade.com", "puprime.com", "zulutrade.com", "fbs.com", "tradetron.tech",
    "comon.ru", "alpari.com", "cxm.com", "pepperstone.com", "forexpeacearmy.com",
}

#: Evidence markers, multilingual: a page scores by what it actually EXPOSES.
SIGNAL_PATTERNS = {
    "has_ranking": ("ranking", "rating", "leaderboard", "排行", "排名", "ランキング",
                    "рейтинг", "순위", "ترتيب", "clasificación", "xếp hạng", "sıralama"),
    "has_return": tuple(t for lg in ("en", "zh", "ja", "ru", "ar", "es", "vi", "ko", "tr")
                        for t in LEXICON["return"].get(lg, [])),
    "has_drawdown": tuple(t for lg in ("en", "zh", "ja", "ru", "ar", "es", "vi", "ko", "tr")
                          for t in LEXICON["drawdown"].get(lg, [])),
    "has_mt": ("metatrader", "mt4", "mt5", "мт4", "мт5", "متاتريدر"),
    "has_copy": tuple(t for lg in ("en", "zh", "ja", "ru", "ar", "es", "vi", "ko", "tr")
                      for t in LEXICON["copy_trading"].get(lg, [])),
    "has_live_account": ("real account", "live account", "verified", "实盘", "実績",
                         "реальный счет", "حساب حقيقي", "cuenta real", "tài khoản thực"),
}


def _read(p: Path, default):
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def apex(url: str) -> str:
    try:
        host = urllib.parse.urlparse(url).netloc.lower().split(":")[0]
    except ValueError:
        return ""
    host = host[4:] if host.startswith("www.") else host
    parts = host.split(".")
    if len(parts) > 2 and parts[-2] in ("co", "com", "org", "net") and len(parts[-1]) == 2:
        return ".".join(parts[-3:])                     # co.uk / com.br style
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def search(query: str) -> list[dict]:
    """Keyless multi-engine discovery: DuckDuckGo HTML, then Mojeek as a second index."""
    hits: list[dict] = []
    for engine, url, pat in (
        ("ddg", "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query),
         r'href="(https?://[^"]+)"[^>]*class="result__a"[^>]*>(.{3,120}?)</a>'),
        ("ddg2", "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query),
         r'class="result__a"[^>]*href="(https?://[^"]+)"[^>]*>(.{3,120}?)</a>'),
        ("mojeek", "https://www.mojeek.com/search?q=" + urllib.parse.quote(query),
         r'<a class="ob"[^>]*href="(https?://[^"]+)"[^>]*>(.{3,120}?)</a>'),
    ):
        if hits:
            break
        try:
            time.sleep(1.5)
            r = requests.get(url, headers=HEADERS, timeout=25)
            r.raise_for_status()
            for m in re.finditer(pat, r.text, re.DOTALL):
                title = re.sub(r"<[^>]+>", "", m.group(2)).strip()
                hits.append({"url": urllib.parse.unquote(m.group(1)), "title": title,
                             "engine": engine})
                if len(hits) >= RESULTS_PER_QUERY:
                    break
        except Exception:                                                # noqa: BLE001
            continue
    return hits


def score_source(url: str) -> dict:
    """Fetch once and score what the page actually EXPOSES, in any language."""
    try:
        time.sleep(1.2)
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        low = r.text.lower()
    except Exception as exc:                                             # noqa: BLE001
        return {"reachable": False, "error": type(exc).__name__, "score": 0}
    flags = {k: any(t.lower() in low for t in terms)
             for k, terms in SIGNAL_PATTERNS.items()}
    # population size proxy: how many distinct account/strategy-shaped links exist
    links = len(set(re.findall(r'href="[^"]*(?:trader|strategy|signal|account|manager|'
                               r'provider|pamm)[^"]*"', low)))
    flags["population_links"] = links
    score = sum(3 for k, v in flags.items() if k.startswith("has_") and v is True)
    score += min(links // 10, 6)
    return {"reachable": True, "score": score, **flags}


def run_and_save() -> dict:
    now = datetime.now(tz=UTC)
    st = _read(STATE, {"cursor": 0})
    pops = _read(POPULATIONS, {"note": "unique survivor populations keyed by apex domain; "
                                       "localized hosts are language WINDOWS, not new "
                                       "populations", "populations": {}})
    cov = _read(FRONTIER, {"note": "measured frontier coverage per locale -- never a "
                                   "completion claim; open_frontier cells keep canary "
                                   "priority forever", "locales": {}})
    # rotating cell: open frontiers get double weight in the rotation
    order = [lg for lg in LOCALES] + [lg for lg, m in LOCALES.items() if m["open_frontier"]]
    locale = order[st["cursor"] % len(order)]
    st["cursor"] = st["cursor"] + 1
    meta = LOCALES[locale]

    # mutate native terminology into native queries
    terms = []
    for concept in QUERY_CONCEPTS:
        terms.extend(LEXICON.get(concept, {}).get(locale, []))
    if not terms:
        terms = LEXICON["copy_trading"]["en"]
    seen_q = set(st.get("queries_done", {}).get(locale, []))
    queries = []
    for i, t in enumerate(terms):
        for pair in ("MT5", "MT4", "ranking"):
            q = f"{t} {pair}"
            if q not in seen_q:
                queries.append(q)
        if len(queries) >= QUERIES_PER_RUN * 2:
            break
    queries = queries[:QUERIES_PER_RUN]

    rows, graduated, new_pops = [], [], 0
    for q in queries:
        for hit in search(q):
            ax = apex(hit["url"])
            if not ax or ax in ("duckduckgo.com", "mojeek.com", "google.com",
                                "youtube.com", "facebook.com", "wikipedia.org"):
                continue
            entry = pops["populations"].get(ax)
            if ax in KNOWN_APEX or entry:
                if entry is not None:
                    windows = set(entry.get("language_windows", []))
                    windows.add(locale)
                    entry["language_windows"] = sorted(windows)
                    entry["last_seen"] = now.isoformat(timespec="seconds")
                continue                                  # already a known population
            sc = score_source(hit["url"])
            pops["populations"][ax] = {
                "apex": ax, "first_seen": now.isoformat(timespec="seconds"),
                "last_seen": now.isoformat(timespec="seconds"),
                "discovered_via": {"locale": locale, "query": q},
                "language_windows": [locale], "title": hit["title"][:120],
                "url": hit["url"], **sc,
                "status": "GRADUATED" if sc.get("score", 0) >= 12 else
                          ("CANDIDATE" if sc.get("score", 0) >= 7 else "LOW_VALUE"),
            }
            new_pops += 1
            rows.append({"source": "frontier", "kind": "source_discovery",
                         "title": hit["title"][:200], "url": hit["url"],
                         "found_at": now.isoformat(timespec="seconds"),
                         "locale": locale, "region": meta["region"], "apex": ax,
                         "score": sc.get("score", 0),
                         "status": pops["populations"][ax]["status"]})
            if pops["populations"][ax]["status"] == "GRADUATED":
                graduated.append(ax)
        st.setdefault("queries_done", {}).setdefault(locale, []).extend(queries)

    # coverage ratchet for this cell -- measured, never a completion claim
    c = cov["locales"].setdefault(locale, {"region": meta["region"],
                                           "open_frontier": meta["open_frontier"],
                                           "queries_exercised": 0, "populations_found": 0,
                                           "graduated": 0})
    c["queries_exercised"] += len(queries)
    c["populations_found"] += new_pops
    c["graduated"] += len(graduated)
    c["last_swept"] = now.isoformat(timespec="seconds")
    c["native_terms_available"] = len(terms)

    OUT.mkdir(parents=True, exist_ok=True)
    if rows:
        (OUT / f"discoveries_{now:%Y%m%d_%H%M}.json").write_text(
            json.dumps(rows, indent=1, default=str), "utf-8")
    POPULATIONS.write_text(json.dumps(pops, indent=1), "utf-8")
    FRONTIER.write_text(json.dumps(cov, indent=1), "utf-8")
    st["queries_done"][locale] = sorted(set(st["queries_done"][locale]))[-400:]
    STATE.write_text(json.dumps(st, indent=0), "utf-8")
    print(f"frontier [{locale}/{meta['region']}"
          f"{' OPEN' if meta['open_frontier'] else ''}]: {len(queries)} native queries, "
          f"{new_pops} new populations, {len(graduated)} graduated "
          f"(total known {len(pops['populations'])})")
    return {"locale": locale, "new_populations": new_pops, "graduated": graduated,
            "discoveries": rows, "count": len(rows)}


if __name__ == "__main__":
    run_and_save()
