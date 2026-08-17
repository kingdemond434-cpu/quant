"""FREE_DATA: keyless public-data collectors (no API keys, no paid feeds).

Sources (all lawful, public, first-party):
  - FRED / ALFRED fredgraph.csv (rates, policy, macro, gold, oil, DXY, VIX)
    vintage_date param => point-in-time history (no API key needed)
  - Deribit public REST (crypto options implied vols; no key)
  - Yahoo Finance via yfinance (DXY, VIX, TNX, GC=F, CL=F, indices; no key)
  - Official government RSS feeds (Fed, BLS, ...; parsed with stdlib)
  - GitHub search + Reddit JSON (crowding/adoption proxies; no key)

Every collector is isolated: one failing source never blocks the others.
Network timeouts are short; results are cached to data/free_data_cache/.
"""

from __future__ import annotations

import csv
import io
import json
import time
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
CACHE = BASE / "data" / "free_data_cache"
CACHE.mkdir(parents=True, exist_ok=True)

UA = "Mozilla/5.0 (research desk; point-in-time collector; contact: local)"


def _get(url: str, timeout: int = 25, headers: dict | None = None) -> bytes:
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
    except Exception:
        pass


# ----------------------------------------------------------------- FRED ----
FRED_FIELDS = {"DGS2", "DGS10", "T10Y2Y", "DFEDTARU", "DFF", "SOFR", "RRPONTSYD",
               "WALCL", "T10YIE", "T5YIE", "PAYEMS", "UNRATE", "INDPRO",
               "CPIAUCSL", "CPILFESL", "RETAILSMxSA", "UMCSENT", "VIXCLS",
               "GOLDAMGBD228NLBM", "DCOILWTICO", "DTWEXBGS", "DTWEXM",
               "CP0000EZ19M086NEST", "JPNCPIALLMINMEI", "BAMLH0A0HYM2",
               "DEXJPUS", "DEXUSEU", "DEXCAUS", "DEXUSUK", "DEXCHUS"}


def fred_series(series_id: str, start: str = "2010-01-01",
                vintage: str | None = None) -> dict[str, float] | None:
    """Fetch a FRED series as {iso_date: value}. Keyless via fredgraph.csv.
    vintage_date => ALFRED point-in-time view of that series."""
    base = "https://alfred.stlouisfed.org/graph/fredgraph.csv" if vintage \
        else "https://fred.stlouisfed.org/graph/fredgraph.csv"
    q = {"id": series_id, "cosd": start}
    if vintage:
        q["vintage_date"] = vintage
    url = base + "?" + urllib.parse.urlencode(q)
    key = f"fred_{series_id}_{vintage or 'cur'}"
    hit = _cache_get(key)
    if hit:
        return hit
    try:
        raw = _get(url).decode("utf-8", "replace")
        rows = list(csv.reader(io.StringIO(raw)))
        out: dict[str, float] = {}
        for row in rows[1:]:
            if len(row) < 2 or row[0].startswith("."):
                continue
            v = row[1].strip()
            if v and v != ".":
                try:
                    out[row[0]] = float(v)
                except ValueError:
                    pass
        if len(out) > 30:
            _cache_put(key, out)
            return out
        return None
    except Exception:
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


# ------------------------------------------------------------- DERIBIT ----
def deribit_book_summary(currency: str = "BTC") -> list[dict] | None:
    """All option contracts with mark_iv for a currency (one public call)."""
    url = (f"https://www.deribit.com/api/v2/public/get_book_summary_by_currency"
           f"?currency={currency}&kind=option")
    key = f"deribit_{currency}"
    hit = _cache_get(key)
    if hit:
        return hit
    try:
        data = json.loads(_get(url))
        res = data.get("result", []) if data.get("result") is not None else []
        if res:
            _cache_put(key, res)
        return res
    except Exception:
        return None


def deribit_index(currency: str = "BTC") -> float | None:
    try:
        url = f"https://www.deribit.com/api/v2/public/get_index_price?index_name={currency.lower()}_usd"
        data = json.loads(_get(url))
        return float(data["result"]["index_price"])
    except Exception:
        return None


def deribit_vol_index(currency: str = "BTC") -> float | None:
    try:
        url = (f"https://www.deribit.com/api/v2/public/get_volatility_index_data"
               f"?currency={currency}&start_timestamp=0&end_timestamp=9999999999999&resolution=3600")
        data = json.loads(_get(url))
        rows = data.get("result", {}).get("data", [])
        if rows:
            return float(rows[-1][1]) / 100.0
        return None
    except Exception:
        return None


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
            d = datetime.fromtimestamp(int(t), tz=timezone.utc).date().isoformat()
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
    "crypto options implied volatility", "mean reversion forex", "breakout trading",
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
    return datetime.now(timezone.utc).isoformat()