"""MQL5 articles miner.

Scans MQL5.com articles for trading strategy ideas and research.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
import requests

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "intelligence" / "mql5"
OUT.mkdir(parents=True, exist_ok=True)

ARTICLES_URL = "https://www.mql5.com/en/articles"
SYMBOLS = ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD",
           "EURJPY", "GBPJPY", "AUDJPY", "CADJPY", "NZDJPY", "CHFJPY", "EURAUD",
           "GBPAUD", "AUDNZD", "NZDCAD", "AUDCAD", "BTCUSD", "ETHUSD", "US500", "NAS100"]

def _extract_symbols(text: str) -> list[str]:
    return [s for s in SYMBOLS if s in text.upper()]

def _extract_patterns(text: str) -> list[str]:
    known = ["breakout", "scalping", "grid", "news trading", "session range", "asia range",
             "london open", "fibonacci", "bollinger", "RSI", "MACD", "moving average",
             "order block", "fair value gap", "liquidity", "smart money", "trend following",
             "mean reversion", "momentum", "pairs trading", "carry trade", "volatility"]
    return [p for p in known if p.lower() in text.lower()]

def mine_articles(max_pages: int = 3) -> list[dict]:
    discoveries = []
    for page in range(1, max_pages + 1):
        try:
            resp = requests.get(ARTICLES_URL, params={"page": page},
                              headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
            resp.raise_for_status()
            text = resp.text
            links = re.findall(r'href="(/en/articles/[^"]+)"', text)
            titles = re.findall(r'<h3[^>]*>([^<]+)</h3>', text)
            for i, link in enumerate(links[:20]):
                title = titles[i] if i < len(titles) else ""
                syms = _extract_symbols(title)
                pats = _extract_patterns(title)
                if syms or pats:
                    discoveries.append({
                        "source": "mql5_articles", "title": title,
                        "url": f"https://www.mql5.com{link}",
                        "symbols": syms, "patterns": pats,
                        "confidence": min(1.0, len(syms) * 0.2 + len(pats) * 0.15),
                    })
        except Exception:
            continue
    return discoveries

def run_and_save() -> list[dict]:
    discoveries = mine_articles()
    out_file = OUT / f"articles_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.json"
    out_file.write_text(json.dumps(discoveries, indent=2), encoding="utf-8")
    print(f"mql5_articles: {len(discoveries)} discoveries saved")
    return discoveries

if __name__ == "__main__":
    run_and_save()
