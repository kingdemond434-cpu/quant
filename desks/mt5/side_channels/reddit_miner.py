"""Reddit trading community miner.

Scrapes Reddit RSS feeds for trading ideas from r/Forex, r/algotrading,
r/wallstreetbets, r/gold, r/silverbugs.
Uses RSS (not blocked like JSON API).
"""

import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parent.parent
_ROOT = str(BASE.parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
from libs.data.refused_hosts import refusal  # noqa: E402

OUT = BASE / "data" / "intelligence" / "reddit"
OUT.mkdir(parents=True, exist_ok=True)

# RSS feeds are not blocked
SUBREDDITS = ["Forex", "algotrading", "wallstreetbets", "Gold",
              "silverbugs", "ForexTrading", "Daytrading"]

HEADERS = {"User-Agent": "quant-desk-research/1.0 (automated research; honours robots.txt)"}

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
    """Mine via RSS feed. A host refused on its terms is never requested."""
    url = f"https://www.reddit.com/r/{sub}/.rss?limit=50"
    why = refusal(url)
    if why:
        print(f"  reddit r/{sub}: BLOCKED_ON_TERMS ({why[:120]})")
        return []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        return _parse_rss(resp.text, sub)
    except Exception as e:
        print(f"  reddit r/{sub}: {e}")
        return []


def blocked_on_terms() -> str | None:
    """Why Reddit may not be contacted, or None."""
    return refusal("https://www.reddit.com/")


def mine_all() -> list[dict]:
    why = blocked_on_terms()
    if why:
        # One line, no requests: every subreddit is the same refused host.
        print(f"reddit: UNMEASURED, BLOCKED_ON_TERMS ({why[:160]})")
        return []
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
    if blocked_on_terms():
        mine_all()  # prints the refusal
        return []   # no discoveries file: a refused ground donates nothing, not an empty batch
    discoveries = mine_all()
    out_file = OUT / f"discoveries_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.json"
    try:
        from side_channels.discovery_io import write_discoveries
    except ModuleNotFoundError:
        from discovery_io import write_discoveries
    discoveries = write_discoveries(out_file, discoveries)
    print(f"reddit: {len(discoveries)} discoveries saved")
    return discoveries


if __name__ == "__main__":
    run_and_save()
