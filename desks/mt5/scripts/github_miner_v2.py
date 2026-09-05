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

import sys
sys.path.insert(0, str(BASE / "desks" / "mt5" / "side_channels"))
from symbol_loader import get_all_symbols, get_symbols_by_category, extract_symbols

TOKEN = os.environ.get("GITHUB_TOKEN", "")
HEADERS = {"Authorization": f"token {TOKEN}"} if TOKEN else {}
SEARCH_URL = "https://api.github.com/search/repositories"

# Expanded queries covering ALL asset classes
QUERIES = [
    # Forex
    "forex trading strategy", "XAUUSD gold algorithm", "session breakout forex",
    "EURUSD algorithm", "GBPUSD strategy", "USDJPY mean reversion",
    # Indices
    "US500 strategy", "NAS100 algorithm", "S&P 500 trading", "US30 dow jones",
    "GER40 dax strategy", "UK100 ftse", "JPN225 nikkei",
    # Crypto
    "BTCUSD bitcoin algorithm", "ETHUSD ethereum strategy", "crypto trading bot",
    "bitcoin mean reversion", "ethereum momentum",
    # Equities
    "AAPL algorithm", "MSFT strategy", "NVDA trading", "TSLA mean reversion",
    "stock trading python", "equity momentum",
    # Commodities
    "XAGUSD silver strategy", "copper trading", "platinum algorithm",
    # Energy
    "WTI oil strategy", "brent crude algorithm", "natural gas trading",
    # General quant
    "mean reversion trading", "momentum trading strategy", "price action algorithm",
    "central bank trading", "carry trade", "algorithmic trading python",
    "quantitative finance strategy", "statistical arbitrage",
    "pairs trading", "cointegration",
]

# Load all symbols from universe dynamically
SYMBOLS = get_all_symbols()


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
    return extract_symbols(text)


def _extract_patterns(text: str) -> list[str]:
    known = [
        "breakout", "mean reversion", "momentum", "trend following",
        "grid", "martingale", "scalping", "swing", "position",
        "fibonacci", "bollinger", "RSI", "MACD", "EMA", "SMA",
        "order block", "fair value gap", "liquidity", "smart money",
        "session range", "asia range", "london open", "NY open",
        "pairs trading", "statistical arbitrage", "cointegration",
        "seasonality", "earnings", "volatility", "correlation",
    ]
    text_lower = text.lower()
    return [p for p in known if p.lower() in text_lower]


def run() -> dict:
    discoveries = []
    for query in QUERIES:
        params = {"q": query, "sort": "updated", "order": "desc", "per_page": 30}
        try:
            r = requests.get(SEARCH_URL, headers=HEADERS, params=params, timeout=10)
            r.raise_for_status()
            items = r.json().get("items", [])
        except Exception as e:
            print(f"  github query '{query}' failed: {e}")
            continue

        for item in items:
            desc = item.get("description", "") or ""
            combined = f"{item.get('full_name', '')} {desc}"
            syms = _extract_symbols(combined)
            pats = _extract_patterns(combined)
            if not syms and not pats:
                continue
            discoveries.append({
                "repo": item.get("full_name", ""),
                "url": item.get("html_url", ""),
                "description": desc[:300],
                "stars": item.get("stargazers_count", 0),
                "language": item.get("language", ""),
                "created": item.get("created_at", ""),
                "updated": item.get("updated_at", ""),
                "symbols": syms,
                "patterns": pats,
                "confidence": min(0.5 + len(syms) * 0.05 + len(pats) * 0.03, 0.9),
            })

    out_file = OUT / f"discoveries_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.json"
    out_file.write_text(json.dumps({"discoveries": discoveries}, indent=2, default=str))
    return {"discoveries": discoveries}


if __name__ == "__main__":
    result = run()
    print(f"GitHub miner: {len(result['discoveries'])} discoveries")
    syms = set()
    for d in result['discoveries']:
        syms.update(d['symbols'])
    print(f"  Symbols found: {sorted(syms)}")