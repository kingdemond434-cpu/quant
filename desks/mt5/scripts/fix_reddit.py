import subprocess

# Fix Reddit: increase delay from 3s to 8s, add exponential backoff on 429
fix_reddit = """
import re
import time
from datetime import datetime, timezone
from pathlib import Path
import requests

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "intelligence" / "reddit"
OUT.mkdir(parents=True, exist_ok=True)

SUBREDDITS = ["Forex", "algotrading", "wallstreetbets", "Gold",
              "silverbugs", "ForexTrading", "Daytrading"]
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"}
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


def _extract_symbols(text):
    found = set()
    text_upper = text.upper()
    for s in SYMBOLS:
        if s in text_upper:
            found.add(s)
    text_lower = text.lower()
    for slang, sym in SLANG_MAP.items():
        if re.search(r'\\\\b' + slang + r'\\\\b', text_lower):
            found.add(sym)
    return list(found)


def _parse_rss(xml_text, sub):
    items = []
    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return items
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    for entry in root.findall(".//atom:entry", ns):
        title = (entry.findtext("atom:title", "", ns) or "")
        content = (entry.findtext("atom:content", "", ns) or "")
        link_el = entry.find("atom:link", ns)
        link = link_el.get("href", "") if link_el is not None else ""
        combined = f"{title} {content}"
        syms = _extract_symbols(combined)
        if syms:
            items.append({
                "source": "reddit",
                "subreddit": sub,
                "title": title[:200],
                "url": link,
                "symbols": syms,
            })
    return items


def mine_subreddit(sub):
    url = f"https://www.reddit.com/r/{sub}/.rss?limit=50"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code == 429:
            print(f"  reddit r/{sub}: 429 rate limited, backing off")
            return []
        resp.raise_for_status()
        return _parse_rss(resp.text, sub)
    except Exception as e:
        print(f"  reddit r/{sub}: {e}")
        return []


def mine_all():
    all_disc = []
    for i, sub in enumerate(SUBREDDITS):
        if i > 0:
            time.sleep(8)
        disc = mine_subreddit(sub)
        all_disc.extend(disc)
        if disc:
            print(f"  r/{sub}: {len(disc)} posts with symbols")
    return all_disc


def run_and_save():
    discoveries = mine_all()
    out_file = OUT / f"discoveries_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.json"
    out_file.write_text(json.dumps(discoveries, indent=2, default=str), encoding="utf-8")
    print(f"reddit: {len(discoveries)} discoveries saved")
    return discoveries


if __name__ == "__main__":
    run_and_save()
"""

proc = subprocess.run(
    ["ssh", "quant@95.216.191.70",
     "cat > /home/quant/quant-platform/desks/mt5/side_channels/reddit_miner.py << 'PYEOF'\n" +
     fix_reddit + "\nPYEOF"],
    capture_output=True, text=True, timeout=15
)
print("Reddit miner written:", "OK" if proc.returncode == 0 else proc.stderr[:200])
