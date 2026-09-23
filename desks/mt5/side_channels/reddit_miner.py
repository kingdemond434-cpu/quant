"""Reddit trading community miner.

Scrapes Reddit RSS feeds for trading ideas from r/Forex, r/algotrading,
r/wallstreetbets, r/gold, r/silverbugs.
Uses RSS (not blocked like JSON API).
"""

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "intelligence" / "reddit"
OUT.mkdir(parents=True, exist_ok=True)

# RSS feeds are not blocked
SUBREDDITS = ["Forex", "algotrading", "wallstreetbets", "Gold",
              "silverbugs", "ForexTrading", "Daytrading"]

HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}

SYMBOLS = [
    "XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF",
    "NZDUSD", "EURJPY", "GBPJPY", "AUDJPY", "CADJPY", "NZDJPY", "CHFJPY",
    "EURAUD", "GBPAUD", "AUDNZD", "NZDCAD", "AUDCAD", "BTCUSD", "ETHUSD",
    "US500", "NAS100",
]

SLANG_MAP = {
    "gold": "XAUUSD", "xau": "XAUUSD", "xauusd": "XAUUSD",
    "silver": "XAGUSD", "xag": "XAGUSD",
    "oil": "USOIL", "crude": "USOIL", "wti": "USOIL",
    "dollar": "DXY", "dxy": "DXY",
    "bitcoin": "BTCUSD", "btc": "BTCUSD", "eth": "ETHUSD",
    "spy": "US500", "qqq": "NAS100", "nasdaq": "NAS100",
    "eurusd": "EURUSD", "gbpusd": "GBPUSD", "usdjpy": "USDJPY",
    "audusd": "AUDUSD", "nzdusd": "NZDUSD", "usdcad": "USDCAD",
    "eurjpy": "EURJPY", "gbpjpy": "GBPJPY", "audjpy": "AUDJPY",
}


def _extract_symbols(text: str) -> list[str]:
    found = set()
    text_upper = text.upper()
    for s in SYMBOLS:
        if s in text_upper:
            found.add(s)
    text_lower = text.lower()
    for slang, sym in SLANG_MAP.items():
        if re.search(r'\b' + slang + r'\b', text_lower):
            found.add(sym)
    return list(found)


def _extract_patterns(text: str) -> list[str]:
    known = [
        "breakout", "reversal", "pullback", "retest", "support", "resistance",
        "fibonacci", "RSI", "MACD", "EMA", "SMA", "order block",
        "fair value gap", "liquidity", "smart money", "scalp", "swing",
        "trend", "momentum", "mean reversion",
    ]
    text_lower = text.lower()
    return [p for p in known if p.lower() in text_lower]


def _parse_rss(xml_text: str, sub: str) -> list[dict]:
    """Parse Reddit RSS XML."""
    import xml.etree.ElementTree as ET
    items = []
    try:
        root = ET.fromstring(xml_text)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        for entry in root.findall("atom:entry", ns):
            title = entry.findtext("atom:title", "", ns)
            link = entry.findtext("atom:link", "", ns)
            content = entry.findtext("atom:content", "", ns) or ""
            # Strip HTML
            clean = re.sub(r'<[^>]+>', ' ', content)[:500]
            combined = f"{title} {clean}"

            syms = _extract_symbols(combined)
            if not syms:
                continue

            pats = _extract_patterns(combined)
            items.append({
                "source": "reddit",
                "subreddit": sub,
                "title": re.sub(r'<[^>]+>', '', title)[:200],
                "url": link,
                "symbols": syms,
                "patterns": pats,
                "confidence": 0.3,
            })
    except ET.ParseError:
        pass
    return items


def mine_subreddit(sub: str) -> list[dict]:
    """Mine via RSS feed."""
    url = f"https://www.reddit.com/r/{sub}/.rss?limit=50"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        return _parse_rss(resp.text, sub)
    except Exception as e:
        print(f"  reddit r/{sub}: {e}")
        return []


def mine_all() -> list[dict]:
    all_disc = []
    for i, sub in enumerate(SUBREDDITS):
        if i > 0:
            time.sleep(3)  # Rate limit: 1 request per 3 seconds
        disc = mine_subreddit(sub)
        all_disc.extend(disc)
        if disc:
            print(f"  r/{sub}: {len(disc)} posts with symbols")
    return all_disc


def run_and_save() -> list[dict]:
    discoveries = mine_all()
    out_file = OUT / f"discoveries_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.json"
    out_file.write_text(json.dumps(discoveries, indent=2, default=str), encoding="utf-8")
    print(f"reddit: {len(discoveries)} discoveries saved")
    return discoveries


if __name__ == "__main__":
    run_and_save()
