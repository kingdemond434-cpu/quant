"""YouTube trading video miner.

Scrapes YouTube for recent trading strategy videos, extracts mentioned
symbols/timeframes/patterns, and outputs structured alpha candidates.

Uses YouTube Data API v3 (free tier: 10,000 units/day).
Falls back to web scraping if no API key available.
"""

import hashlib
import json
import time
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import requests

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "intelligence" / "youtube"
OUT.mkdir(parents=True, exist_ok=True)

#: The YouTube Data API v3 key (official API; the principal lifted the box's YouTube ban on
#: 2026-11-19). Read where read_key looks -- the box stores it as YOUTUBE -- never printed.
KEY_NAMES = ("YOUTUBE_API_KEY", "YOUTUBE")

#: Terms read 2026-11-19 (both pages "Last updated 2026-11-06 UTC").
YOUTUBE_TERMS = {
    "tos_url": "https://developers.google.com/youtube/terms/api-services-terms-of-service",
    "tos_quote": ("only access (or attempt to access) the YouTube API Services to develop and "
                  "operate your API Client(s) [...] by the means described in the Agreement"),
    "policy_url": "https://developers.google.com/youtube/terms/developer-policies",
    "policy_quote": ("You must access data from YouTube API services only according to the means "
                     "stipulated in the authorized documentation of that YouTube API service."),
    "checked": "2026-11-19",
}


def _api_key() -> str:
    try:
        import sys as _sys
        _root = str(Path(__file__).resolve().parents[3])
        if _root not in _sys.path:
            _sys.path.append(_root)
        from libs.ops.env_keys import read_key
        return next((v for v in map(read_key, KEY_NAMES) if v), "")
    except Exception:
        return next((os.environ[n] for n in KEY_NAMES if os.environ.get(n)), "")


API_KEY = _api_key()
SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"

# Trading-related search queries
QUERIES = [
    "forex trading strategy 2026",
    "gold XAUUSD trading strategy",
    "JPY trading strategy",
    "session breakout strategy forex",
    "price action trading strategy",
    "algorithmic trading strategy",
    "mean reversion trading",
    "momentum trading strategy forex",
    "central bank trading strategy",
    "NFP trading strategy",
]

SYMBOLS = [
    "XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD",
    "USDCAD", "USDCHF", "NZDUSD", "EURJPY", "GBPJPY",
    "AUDJPY", "CADJPY", "NZDJPY", "CHFJPY", "EURAUD",
    "GBPAUD", "AUDNZD", "NZDCAD", "AUDCAD", "BTCUSD",
    "ETHUSD", "US500", "NAS100",
]


@dataclass
class YTDiscovery:
    source: str = "youtube"
    title: str = ""
    channel: str = ""
    url: str = ""
    published: str = ""
    symbols_mentioned: list = field(default_factory=list)
    timeframes_mentioned: list = field(default_factory=list)
    patterns_mentioned: list = field(default_factory=list)
    raw_snippet: str = ""
    confidence: float = 0.0


def _extract_symbols(text: str) -> list[str]:
    text_upper = text.upper()
    return [s for s in SYMBOLS if s in text_upper]


def _extract_timeframes(text: str) -> list[str]:
    patterns = [
        r'\b(\d+)\s*(min|m|hour|h|day|d|week|w)\b',
        r'\b(H[1-4]|M[1-9]\d*|D1|W1|MN)\b',
        r'\b(scalp|intraday|swing|position)\b',
    ]
    found = []
    for p in patterns:
        found.extend(re.findall(p, text, re.IGNORECASE))
    return list(set(found))


def _extract_patterns(text: str) -> list[str]:
    known = [
        "breakout", "breakdown", "reversal", "pullback", "retest",
        "support", "resistance", "trendline", "fibonacci", "fib",
        "moving average", "EMA", "SMA", "RSI", "MACD", "Bollinger",
        "engulfing", "doji", "hammer", "head and shoulders", "H&S",
        "double top", "double bottom", "triangle", "flag", "pennant",
        "order block", "fair value gap", "FVG", "liquidity", "smart money",
        "ICT", "supply and demand", "zone", "accumulation", "distribution",
        "session range", "asia range", "london open", "NY open",
    ]
    text_lower = text.lower()
    return [p for p in known if p.lower() in text_lower]


def _search_api(query: str, max_results: int = 10) -> list[dict]:
    """Search YouTube via Data API v3."""
    if not API_KEY:
        return []
    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "maxResults": max_results,
        "order": "date",
        "publishedAfter": (datetime.now(timezone.utc) - timedelta(days=7)).isoformat(),
        "key": API_KEY,
    }
    try:
        resp = requests.get(SEARCH_URL, params=params, timeout=15, headers={
            "User-Agent": "quant-desk-research/1.0 (youtube data api; research)"})
        resp.raise_for_status()
        return resp.json().get("items", [])
    except Exception:
        return []


def _search_web(query: str) -> list[dict]:
    """Fallback: scrape YouTube search results via HTML."""
    # Minimal fallback — returns empty if API unavailable
    return []


def mine(query: str = None, max_per_query: int = 10) -> list[YTDiscovery]:
    """Run YouTube mining for a query or all queries."""
    queries = [query] if query else QUERIES
    discoveries = []

    # FINISH INSIDE THE HARNESS BUDGET, OR THE HARNESS KILLS US AND WE RETURN NOTHING.
    # run_all_miners kills a miner at QUANT_MINER_TIMEOUT_S (180s default) and a killed miner
    # loses every discovery it had already collected. Ten queries at the 15s request timeout is
    # 150s before any parsing, so a few slow responses put this miner over the edge -- it was
    # reported TIMED OUT on most runs and had produced nothing for seven days. Stop issuing new
    # queries once the budget is nearly spent and RETURN WHAT WE HAVE: partial evidence is a
    # result, being killed is not.
    _budget = float(os.environ.get("QUANT_MINER_TIMEOUT_S", "180"))
    _deadline = time.monotonic() + max(20.0, _budget * 0.75)

    for q in queries:
        if time.monotonic() >= _deadline:
            print(f"youtube: budget reached, stopping after {len(discoveries)} discovery(ies) "
                  f"from {queries.index(q)} of {len(queries)} queries")
            break
        items = _search_api(q) if API_KEY else _search_web(q)
        for item in items:
            snippet = item.get("snippet", {})
            title = snippet.get("title", "")
            desc = snippet.get("description", "")
            combined = f"{title} {desc}"

            syms = _extract_symbols(combined)
            tfs = _extract_timeframes(combined)
            pats = _extract_patterns(combined)

            if not syms:
                continue

            confidence = min(1.0, len(syms) * 0.2 + len(pats) * 0.15 + len(tfs) * 0.1)

            d = YTDiscovery(
                title=title,
                channel=snippet.get("channelTitle", ""),
                url=f"https://youtube.com/watch?v={item.get('id', {}).get('videoId', '')}",
                published=snippet.get("publishedAt", ""),
                symbols_mentioned=syms,
                timeframes_mentioned=tfs,
                patterns_mentioned=pats,
                raw_snippet=desc[:500],
                confidence=confidence,
            )
            discoveries.append(d)

    return discoveries


def run_and_save() -> list[dict]:
    """Mine all queries and save results."""
    all_discoveries = mine()
    results = []
    for d in all_discoveries:
        # Derived readings only: YouTube API Data is never stored (Developer Policies III.E:
        # non-authorized data at most 30 days), so no title, channel or video id is kept --
        # only what the desk computed from them, and a one-way reference.
        results.append({
            "source": d.source,
            "video_ref": hashlib.sha256(d.url.encode("utf-8")).hexdigest()[:16],
            "published": d.published,
            "symbols": d.symbols_mentioned,
            "timeframes": d.timeframes_mentioned,
            "patterns": d.patterns_mentioned,
            "confidence": d.confidence,
        })

    out_file = OUT / f"discoveries_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.json"
    try:
        from side_channels.discovery_io import write_discoveries
    except ModuleNotFoundError:
        from discovery_io import write_discoveries
    results = write_discoveries(out_file, results)
    print(f"youtube: {len(results)} discoveries saved to {out_file.name}")
    return results


if __name__ == "__main__":
    run_and_save()
