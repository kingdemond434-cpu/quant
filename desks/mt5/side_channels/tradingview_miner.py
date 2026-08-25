"""TradingView public scripts miner.

Scans TradingView's public Pine Script library for popular strategies.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
import requests

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "intelligence" / "tradingview"
OUT.mkdir(parents=True, exist_ok=True)

TV_SEARCH_URL = "https://www.tradingview.com/scripts/"
SYMBOLS = ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD",
           "EURJPY", "GBPJPY", "AUDJPY", "CADJPY", "NZDJPY", "CHFJPY", "EURAUD",
           "GBPAUD", "AUDNZD", "NZDCAD", "AUDCAD", "BTCUSD", "ETHUSD", "US500", "NAS100"]

def _extract_symbols(text: str) -> list[str]:
    return [s for s in SYMBOLS if s in text.upper()]

def _extract_patterns(text: str) -> list[str]:
    known = ["breakout", "scalping", "grid", "news trading", "session range", "asia range",
             "london open", "fibonacci", "bollinger", "RSI", "MACD", "moving average",
             "order block", "fair value gap", "liquidity", "smart money", "trend following",
             "mean reversion", "momentum", "volume profile", " VWAP", "ATR"]
    return [p for p in known if p.lower() in text.lower()]

def mine_tradingview() -> list[dict]:
    discoveries = []
    try:
        resp = requests.get(TV_SEARCH_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        resp.raise_for_status()
        text = resp.text
        scripts = re.findall(r'<a[^>]*href="(/scripts/[^"]+)"[^>]*>([^<]+)</a>', text)
        for link, title in scripts[:50]:
            syms = _extract_symbols(title)
            pats = _extract_patterns(title)
            if syms or pats:
                discoveries.append({
                    "source": "tradingview", "title": title,
                    "url": f"https://www.tradingview.com{link}",
                    "symbols": syms, "patterns": pats,
                    "confidence": min(1.0, len(syms) * 0.2 + len(pats) * 0.15),
                })
    except Exception:
        pass
    return discoveries

def run_and_save() -> list[dict]:
    discoveries = mine_tradingview()
    out_file = OUT / f"discoveries_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.json"
    out_file.write_text(json.dumps(discoveries, indent=2), encoding="utf-8")
    print(f"tradingview: {len(discoveries)} discoveries saved")
    return discoveries

if __name__ == "__main__":
    run_and_save()
