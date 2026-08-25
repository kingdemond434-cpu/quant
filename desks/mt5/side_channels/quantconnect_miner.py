"""QuantConnect strategy miner.

Scans QuantConnect's public algorithm library for trading strategies.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
import requests

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "intelligence" / "quantconnect"
OUT.mkdir(parents=True, exist_ok=True)

QC_URL = "https://www.quantconnect.com/tutorials/strategy-library"
SYMBOLS = ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD",
           "EURJPY", "GBPJPY", "AUDJPY", "CADJPY", "NZDJPY", "CHFJPY", "EURAUD",
           "GBPAUD", "AUDNZD", "NZDCAD", "AUDCAD", "BTCUSD", "ETHUSD", "US500", "NAS100"]

def _extract_symbols(text: str) -> list[str]:
    return [s for s in SYMBOLS if s in text.upper()]

def _extract_patterns(text: str) -> list[str]:
    known = ["pairs trading", "mean reversion", "momentum", "trend following",
             "breakout", "grid", "carry trade", "volatility", "statistical arbitrage",
             "cointegration", "market making", "sentiment", "fundamental"]
    return [p for p in known if p.lower() in text.lower()]

def mine_quantconnect() -> list[dict]:
    discoveries = []
    try:
        resp = requests.get(QC_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        resp.raise_for_status()
        text = resp.text
        strategies = re.findall(r'<h3[^>]*><a[^>]*href="([^"]+)"[^>]*>([^<]+)</a></h3>', text)
        for link, title in strategies[:30]:
            syms = _extract_symbols(title)
            pats = _extract_patterns(title)
            if syms or pats:
                url = link if link.startswith("http") else f"https://www.quantconnect.com{link}"
                discoveries.append({
                    "source": "quantconnect", "title": title,
                    "url": url, "symbols": syms, "patterns": pats,
                    "confidence": min(1.0, len(syms) * 0.2 + len(pats) * 0.15),
                })
    except Exception:
        pass
    return discoveries

def run_and_save() -> list[dict]:
    discoveries = mine_quantconnect()
    out_file = OUT / f"discoveries_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.json"
    out_file.write_text(json.dumps(discoveries, indent=2), encoding="utf-8")
    print(f"quantconnect: {len(discoveries)} discoveries saved")
    return discoveries

if __name__ == "__main__":
    run_and_save()
