"""MQL5 signals miner.

Scans MQL5.com trading signals for profitable strategies,
extracts performance metrics and trading patterns.
"""

import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

try:
    from side_channels import mql5_terms
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import mql5_terms

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "intelligence" / "mql5"
OUT.mkdir(parents=True, exist_ok=True)
#: Fixed name: a refused hour overwrites the last refusal (mql5_terms).
REFUSAL = OUT / "discoveries_blocked_terms_signals.json"

SIGNALS_URL = "https://www.mql5.com/en/signals"

def mine_signals() -> list[dict]:
    # FAIL-CLOSED TERMS FENCE: MQL5 ToU 3.7/3.9/3.13 prohibit this fetch.
    mql5_terms.guard(SIGNALS_URL)
    discoveries = []
    try:
        resp = requests.get(SIGNALS_URL, params={"tab": "all", "sort": "profit"},
                          headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"}, timeout=15)
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
    # Refused before any request; the refusal is the hour's recorded artifact.
    if mql5_terms.is_mql5_url(SIGNALS_URL):
        mql5_terms.refuse("mql5_signals", REFUSAL)
        return []
    discoveries = mine_signals()
    out_file = OUT / f"signals_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.json"
    try:
        from side_channels.discovery_io import write_discoveries
    except ModuleNotFoundError:
        from discovery_io import write_discoveries
    discoveries = write_discoveries(out_file, discoveries)
    print(f"mql5_signals: {len(discoveries)} discoveries saved")
    return discoveries

if __name__ == "__main__":
    run_and_save()
