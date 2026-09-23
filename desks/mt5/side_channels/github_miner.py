"""GitHub trading strategy miner.

Scans GitHub for recent trading strategy repositories, extracts mentioned
symbols/patterns/algorithms, and outputs structured alpha candidates.

Uses GitHub API (free: 5,000 requests/hour).
"""

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "intelligence" / "github"
OUT.mkdir(parents=True, exist_ok=True)

TOKEN = os.environ.get("GITHUB_TOKEN", "")
HEADERS = {"Authorization": f"token {TOKEN}"} if TOKEN else {}
SEARCH_URL = "https://api.github.com/search/repositories"

QUERIES = [
    "forex trading strategy",
    "gold XAUUSD algorithm",
    "session breakout forex",
    "mean reversion trading",
    "momentum trading strategy",
    "price action algorithm",
    "central bank trading",
    "JPY carry trade",
    "algorithmic trading python",
    "quantitative finance strategy",
]

SYMBOLS = [
    "XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD",
    "USDCAD", "USDCHF", "NZDUSD", "EURJPY", "GBPJPY",
    "AUDJPY", "CADJPY", "NZDJPY", "CHFJPY", "EURAUD",
    "GBPAUD", "AUDNZD", "NZDCAD", "AUDCAD", "BTCUSD",
    "ETHUSD", "US500", "NAS100",
]


@dataclass
class GHDiscovery:
    source: str = "github"
    repo: str = ""
    url: str = ""
    description: str = ""
    stars: int = 0
    language: str = ""
    created: str = ""
    updated: str = ""
    symbols_mentioned: list = field(default_factory=list)
    patterns_mentioned: list = field(default_factory=list)
    confidence: float = 0.0


def _extract_symbols(text: str) -> list[str]:
    text_upper = text.upper()
    return [s for s in SYMBOLS if s in text_upper]


def _extract_patterns(text: str) -> list[str]:
    known = [
        "breakout", "mean reversion", "momentum", "trend following",
        "grid", "martingale", "scalping", "swing", "position",
        "fibonacci", "bollinger", "RSI", "MACD", "EMA", "SMA",
        "order block", "fair value gap", "liquidity", "smart money",
        "session range", "asia range", "london open", "NY open",
        "pairs trading", "statistical arbitrage", "cointegration",
    ]
    text_lower = text.lower()
    return [p for p in known if p.lower() in text_lower]


def search_repos(query: str, min_stars: int = 5) -> list[GHDiscovery]:
    """Search GitHub for trading strategy repos."""
    params = {
        "q": f"{query} stars:>={min_stars} pushed:>{(datetime.now(timezone.utc) - timedelta(days=30)).strftime('%Y-%m-%d')}",
        "sort": "updated",
        "order": "desc",
        "per_page": 20,
    }
    try:
        resp = requests.get(SEARCH_URL, params=params, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        items = resp.json().get("items", [])
    except Exception:
        return []

    discoveries = []
    for item in items:
        combined = f"{item.get('name', '')} {item.get('description', '') or ''}"
        syms = _extract_symbols(combined)
        pats = _extract_patterns(combined)

        if not syms and not pats:
            continue

        confidence = min(1.0, len(syms) * 0.2 + len(pats) * 0.15 + (item.get('stargazers_count', 0) / 100) * 0.1)

        d = GHDiscovery(
            repo=item.get('full_name', ''),
            url=item.get('html_url', ''),
            description=item.get('description', '') or '',
            stars=item.get('stargazers_count', 0),
            language=item.get('language', ''),
            created=item.get('created_at', ''),
            updated=item.get('updated_at', ''),
            symbols_mentioned=syms,
            patterns_mentioned=pats,
            confidence=confidence,
        )
        discoveries.append(d)

    return discoveries


def run_and_save() -> list[dict]:
    """Mine all queries and save results."""
    all_discoveries = []
    for q in QUERIES:
        all_discoveries.extend(search_repos(q))

    results = []
    for d in all_discoveries:
        results.append({
            "source": d.source,
            "repo": d.repo,
            "url": d.url,
            "description": d.description,
            "stars": d.stars,
            "language": d.language,
            "symbols": d.symbols_mentioned,
            "patterns": d.patterns_mentioned,
            "confidence": d.confidence,
        })

    out_file = OUT / f"discoveries_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.json"
    out_file.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"github: {len(results)} discoveries saved to {out_file.name}")
    return results


if __name__ == "__main__":
    run_and_save()
