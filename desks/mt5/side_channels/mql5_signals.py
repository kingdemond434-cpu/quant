"""MQL5 signals miner.

Scans MQL5.com trading signals for profitable strategies,
extracts performance metrics and trading patterns.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
import requests

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "intelligence" / "mql5"
OUT.mkdir(parents=True, exist_ok=True)

SIGNALS_URL = "https://www.mql5.com/en/signals"

def mine_signals() -> list[dict]:
    discoveries = []
    try:
        resp = requests.get(SIGNALS_URL, params={"tab": "all", "sort": "profit"},
                          headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        resp.raise_for_status()
        text = resp.text
        # Extract signal cards
        signals = re.findall(r'<div class="signal[^"]*"[^>]*>(.*?)</div>', text, re.DOTALL)
        for sig in signals[:30]:
            name = re.search(r'<a[^>]*>([^<]+)</a>', sig)
            profit = re.search(r'profit[^>]*>([^<]+)<', sig)
            drawdown = re.search(r'drawdown[^>]*>([^<]+)<', sig)
            if name:
                discoveries.append({
                    "source": "mql5_signals",
                    "name": name.group(1).strip(),
                    "profit": profit.group(1).strip() if profit else "",
                    "drawdown": drawdown.group(1).strip() if drawdown else "",
                    "url": SIGNALS_URL,
                    "confidence": 0.3,
                })
    except Exception:
        pass
    return discoveries

def run_and_save() -> list[dict]:
    discoveries = mine_signals()
    out_file = OUT / f"signals_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.json"
    out_file.write_text(json.dumps(discoveries, indent=2), encoding="utf-8")
    print(f"mql5_signals: {len(discoveries)} discoveries saved")
    return discoveries

if __name__ == "__main__":
    run_and_save()
