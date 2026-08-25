"""MQL5 forum miner.

Scans MQL5.com forum for strategy discussions and ideas.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
import requests

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "intelligence" / "mql5"
OUT.mkdir(parents=True, exist_ok=True)

FORUM_URL = "https://www.mql5.com/en/forum"
SYMBOLS = ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD",
           "EURJPY", "GBPJPY", "AUDJPY", "CADJPY", "NZDJPY", "CHFJPY", "EURAUD",
           "GBPAUD", "AUDNZD", "NZDCAD", "AUDCAD", "BTCUSD", "ETHUSD", "US500", "NAS100"]

def _extract_symbols(text: str) -> list[str]:
    return [s for s in SYMBOLS if s in text.upper()]

def mine_forum(max_pages: int = 3) -> list[dict]:
    discoveries = []
    for page in range(1, max_pages + 1):
        try:
            resp = requests.get(FORUM_URL, params={"page": page},
                              headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
            resp.raise_for_status()
            text = resp.text
            threads = re.findall(r'<a[^>]*href="(/en/forum/[^"]+)"[^>]*>([^<]+)</a>', text)
            for link, title in threads[:30]:
                syms = _extract_symbols(title)
                if syms:
                    discoveries.append({
                        "source": "mql5_forum", "title": title,
                        "url": f"https://www.mql5.com{link}",
                        "symbols": syms, "confidence": 0.2,
                    })
        except Exception:
            continue
    return discoveries

def run_and_save() -> list[dict]:
    discoveries = mine_forum()
    out_file = OUT / f"forum_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.json"
    out_file.write_text(json.dumps(discoveries, indent=2), encoding="utf-8")
    print(f"mql5_forum: {len(discoveries)} discoveries saved")
    return discoveries

if __name__ == "__main__":
    run_and_save()
