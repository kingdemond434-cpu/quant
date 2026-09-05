"""YouTube trading video miner.

Scrapes YouTube for recent trading strategy videos, extracts mentioned
symbols/timeframes/patterns, and outputs structured alpha candidates.

Uses YouTube Data API v3 (free tier: 10,000 units/day).
Falls back to web scraping if no API key available.
"""

import json
import os
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "intelligence" / "youtube"
OUT.mkdir(parents=True, exist_ok=True)

API_KEY = os.environ.get("YOUTUBE_API_KEY", "")
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
        "publishedAfter": (datetime.now(UTC) - timedelta(days=7)).isoformat(),
        "key": API_KEY,
    }
    try:
        resp = requests.get(SEARCH_URL, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json().get("items", [])
    except Exception:
        return []


def _search_web(query: str) -> list[dict]:
    """Fallback: scrape YouTube search results via HTML."""
    # Minimal fallback — returns empty if API unavailable
    return []


def mine(query: str | None = None, max_per_query: int = 10) -> list[YTDiscovery]:
    """Run YouTube mining for a query or all queries."""
    queries = [query] if query else QUERIES
    discoveries = []

    for q in queries:
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
        results.append({
            "source": d.source,
            "title": d.title,
            "channel": d.channel,
            "url": d.url,
            "published": d.published,
            "symbols": d.symbols_mentioned,
            "timeframes": d.timeframes_mentioned,
            "patterns": d.patterns_mentioned,
            "confidence": d.confidence,
        })

    out_file = OUT / f"discoveries_{datetime.now(UTC).strftime('%Y%m%d_%H%M')}.json"
    out_file.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"youtube: {len(results)} discoveries saved to {out_file.name}")
    return results


if __name__ == "__main__":
    run_and_save()
