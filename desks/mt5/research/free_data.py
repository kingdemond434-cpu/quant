"""FREE_DATA: keyless public-data collectors (no API keys, no paid feeds).

Sources (all lawful, public, first-party):
  - FRED / ALFRED: REFUSED ON TERMS (2026-11-13). `fred_series` keeps its name and contract
    but never contacts FRED; it serves only a mapped primary-publisher mirror (BACKLOG 609).
  - Yahoo Finance: REFUSED ON TERMS (refused_hosts); `_get` refuses it before the wire.
  - Official government RSS feeds (Fed, BLS, ...; parsed with stdlib)
  - GitHub search + Reddit JSON (crowding/adoption proxies; no key)

Every collector is isolated: one failing source never blocks the others.
Network timeouts are short; results are cached to data/free_data_cache/.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
CACHE = BASE / "data" / "free_data_cache"
CACHE.mkdir(parents=True, exist_ok=True)

UA = "Mozilla/5.0 (research desk; point-in-time collector; contact: local)"


def _refusal(url: str) -> str | None:
    """Why `url` may not be contacted (libs.data.refused_hosts), or None. FAILS CLOSED: if the
    list cannot be imported, every URL is refused, because unclear terms are a refusal."""
    try:
        import sys as _sys
        _root = str(Path(__file__).resolve().parents[3])
        if _root not in _sys.path:
            _sys.path.insert(0, _root)
        from libs.data.refused_hosts import refusal
    except Exception as exc:  # any import failure is a refusal
        return f"refused-host list unimportable ({type(exc).__name__}); unclear terms fail closed"
    return refusal(url)


def _get(url: str, timeout: int = 25, headers: dict | None = None) -> bytes:
    why = _refusal(url)
    if why:
        # BEFORE THE WIRE (BACKLOG 609). Raised as a URLError so every collector here that
        # already treats a failed fetch as "no data" treats a terms refusal the same way.
        raise urllib.error.URLError(f"{FRED_STATUS}: {why}")
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _cache_file(name: str) -> Path:
    return CACHE / f"{name.replace('/', '_').replace('?', '_')}.json"


def _cache_get(name: str):
    p = _cache_file(name)
    if p.exists() and (time.time() - p.stat().st_mtime) < 21600:
        try:
            return json.loads(p.read_text("utf-8"))
        except Exception:
            pass
    return None


def _cache_put(name: str, obj) -> None:
    try:
        _cache_file(name).write_text(json.dumps(obj), "utf-8")
    except Exception as exc:
        # LOUD, NOT SILENT (2026-09-23 swallowed-write audit). A cache that silently never writes
        # re-fetches every call forever and looks exactly like a cache that is working.
        print(f"free_data: cache {name!r} NOT written ({type(exc).__name__}: {exc})", flush=True)


# ----------------------------------------------------------------- FRED ----
FRED_FIELDS = {"DGS2", "DGS10", "T10Y2Y", "DFEDTARU", "DFF", "SOFR", "RRPONTSYD",
               "WALCL", "T10YIE", "T5YIE", "PAYEMS", "UNRATE", "INDPRO",
               "CPIAUCSL", "CPILFESL", "RETAILSMxSA", "UMCSENT", "VIXCLS",
               "GOLDAMGBD228NLBM", "DCOILWTICO", "DTWEXBGS", "DTWEXM",
               "CP0000EZ19M086NEST", "JPNCPIALLMINMEI", "BAMLH0A0HYM2",
               "DEXJPUS", "DEXUSEU", "DEXCAUS", "DEXUSUK", "DEXCHUS"}


#: FRED IS REFUSED FOR EVERY AUTOMATED FETCH (terms ruling 2026-11-13; BACKLOG 609). The status a
#: refused series is recorded under is the repo's existing word for a terms refusal.
FRED_STATUS = "BLOCKED_ON_TERMS"
FRED_RULING = "FRED: refused for all automated fetches (terms ruling 2026-11-13)"
FRED_MISSED_GROWTH = {
    "mechanism": "fred_terms_refusal",
    "lost": ("every series this collector used to read from fredgraph.csv / ALFRED: rates, "
             "spreads, dollar, breakevens, VIX and the macro prints, and every ALFRED vintage"),
    "stand_in": ("the DBnomics mirror of the PRIMARY publisher (BLS, Federal Reserve) where one "
                 "is mapped; the primary-source liquidity axis (research/usd_liquidity_primary) "
                 "for WRESBAL/WTREGEN/RRPONTSYD/SOFR; no stand-in for ALFRED vintages"),
    "verdict": "a gap, not a zero",
}
#: series id -> the refusal record, for every series asked for this process. Read by callers and
#: reports that want to say BLOCKED_ON_TERMS rather than "fetch failed".
FRED_REFUSALS: dict[str, dict] = {}


def fred_series(series_id: str, start: str = "2010-01-01",
                vintage: str | None = None) -> dict[str, float] | None:
    """A FRED series id as {iso_date: value} -- NEVER FROM FRED (BACKLOG 609).

    The FRED/ALFRED fredgraph.csv fetch that lived here is REMOVED, not switched off: FRED's terms
    refuse automated access (2026-11-13), so no request to stlouisfed.org is built for the wire.
    The refusal is checked against `libs.data.refused_hosts` (and is also fixed here, so patching
    that list empty, or failing to import it, still opens no socket), recorded in
    `FRED_REFUSALS` with status BLOCKED_ON_TERMS and its missed-growth line, and then the series
    is served ONLY from a mapped primary-publisher mirror (`scripts/data_alternates`). With no
    mirror, or for any ALFRED vintage, the answer is None -- the same value every caller already
    handles as a failed fetch, so nothing crashes and nothing reads a refusal as data."""
    url = ("https://alfred.stlouisfed.org/graph/fredgraph.csv" if vintage
           else "https://fred.stlouisfed.org/graph/fredgraph.csv")
    why = _refusal(url) or FRED_RULING
    FRED_REFUSALS[series_id] = {"series": series_id, "status": FRED_STATUS, "why": why,
                                "vintage": vintage, "missed_growth": FRED_MISSED_GROWTH}
    print(f"free_data: {series_id} {FRED_STATUS} ({why}); FRED not contacted", flush=True)
    return _fred_alternate(series_id, vintage, f"fred_{series_id}_{vintage or 'cur'}_alt")


def _fred_alternate(series_id: str, vintage: str | None, cache_key: str):
    if vintage:
        return None          # point-in-time vintages exist only at ALFRED; never fake one
    try:
        import sys as _sys
        _root = str(Path(__file__).resolve().parents[3] / "scripts")
        if _root not in _sys.path:
            _sys.path.insert(0, _root)
        from data_alternates import dbnomics_route
        out = dbnomics_route(series_id)
        if len(out) > 30:
            _cache_put(cache_key, out)
            print(f"free_data: {series_id} served by DBNOMICS mirror (primary blocked)")
            return out
    except Exception:
        pass
    return None


def fred_vintage_series(series_id: str, vintage_dates: list[str],
                        start: str = "2010-01-01") -> dict[str, dict[str, float]]:
    """Point-in-time lake: {vintage_date: {date: value}} as of each vintage."""
    out: dict[str, dict[str, float]] = {}
    for vd in vintage_dates:
        s = fred_series(series_id, start=start, vintage=vd)
        if s:
            out[vd] = s
    return out


# ---------------------------------------------------------------- YAHOO ----
YAHOO_TICKERS = {"DX-Y.NYB": "DXY", "^VIX": "VIX", "^TNX": "TNX", "^GSPC": "SPX",
                 "GC=F": "GC", "CL=F": "CL", "^N225": "NKY", "EURUSD=X": "EURUSD",
                 "USDJPY=X": "USDJPY", "GBPUSD=X": "GBPUSD", "AUDUSD=X": "AUDUSD",
                 "USDCAD=X": "USDCAD", "NZDUSD=X": "NZDUSD", "USDCHF=X": "USDCHF"}


def yahoo_daily(ticker: str) -> dict[str, float] | None:
    """Daily close history {iso_date: close}. Keyless via the public chart API
    (direct urllib - no yfinance dependency, honors our timeouts)."""
    key = f"yahoo_{ticker}"
    hit = _cache_get(key)
    if hit:
        return hit
    try:
        url = ("https://query1.finance.yahoo.com/v8/finance/chart/" +
               urllib.parse.quote(ticker) +
               "?range=10y&interval=1d&events=div%2Csplit")
        data = json.loads(_get(url, timeout=20))
        res = data.get("chart", {}).get("result")
        if not res:
            return None
        ts = res[0].get("timestamp", [])
        closes = res[0].get("indicators", {}).get("quote", [{}])[0].get("close", [])
        out: dict[str, float] = {}
        for t, c in zip(ts, closes):
            if c is None:
                continue
            d = datetime.fromtimestamp(int(t), tz=UTC).date().isoformat()
            out[d] = float(c)
        if len(out) > 60:
            _cache_put(key, out)
            return out
        return None
    except Exception:
        return None


# ------------------------------------------------------------------ RSS ----
RSS_FEEDS = {
    "FED": "https://www.federalreserve.gov/feeds/press_all.xml",
    "BLS": "https://www.bls.gov/feed/news_release_all.xml",
    "ECB": "https://www.ecb.europa.eu/rss/press.html",
    "BOJ": "https://www.boj.or.jp/en/announcements/rss.rdf",
    "BOE": "https://www.bankofengland.co.uk/rss/news",
    "SNB": "https://www.snb.ch/en/node/10532/rss",
}


def rss_fetch(url: str) -> list[dict]:
    """Parse an RSS/Atom feed into [{title, link, pub, guid}]. Stdlib only."""
    out: list[dict] = []
    try:
        raw = _get(url, timeout=15)
        root = ET.fromstring(raw)
        for item in root.iter():
            tag = item.tag.rsplit("}", 1)[-1]
            if tag in ("item", "entry"):
                d: dict[str, str] = {}
                for child in item:
                    t = child.tag.rsplit("}", 1)[-1]
                    if t in ("title", "link", "pubDate", "published", "updated", "guid", "id"):
                        d[t] = (child.text or "").strip()
                if d.get("title") or d.get("link"):
                    out.append(d)
    except Exception:
        pass
    return out


# -------------------------------------------------------- CROWDING (free) --
GITHUB_QUERIES = [
    "quant trading strategy", "trading bot forex", "gold trading algorithm",
    "mean reversion forex", "breakout trading", "xauusd strategy",
]


def github_search(query: str) -> dict:
    """Unauthenticated GitHub search (rate-limited ~10/min; call sparingly)."""
    url = ("https://api.github.com/search/repositories?q=" +
           urllib.parse.quote(query) + "&sort=stars&order=desc&per_page=5")
    try:
        data = json.loads(_get(url, headers={"Accept": "application/vnd.github+json"}))
        repos = data.get("items", [])
        return {"count": data.get("total_count", 0),
                "top_stars": [r.get("stargazers_count", 0) for r in repos[:5]],
                "top_names": [r.get("full_name", "") for r in repos[:5]]}
    except Exception:
        return {}


def reddit_hot(subreddit: str = "algotrading", limit: int = 25) -> list[dict]:
    url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit={limit}"
    try:
        data = json.loads(_get(url, headers={"User-Agent": "research-crowding/1.0"}))
        posts = []
        for c in data.get("data", {}).get("children", []):
            p = c.get("data", {})
            posts.append({"title": p.get("title", ""), "score": p.get("score", 0),
                          "num_comments": p.get("num_comments", 0),
                          "created_utc": p.get("created_utc", 0)})
        return posts
    except Exception:
        return []


def now_iso() -> str:
    return datetime.now(UTC).isoformat()
