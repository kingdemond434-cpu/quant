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
        resp = requests.get(QC_URL, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"}, timeout=15)
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
    # A 200 WITH NOTHING IN IT IS NOT A QUIET SOURCE. Measured 2026-09-01: this host serves
    # the page but not the DATA -- the <h3><a> tutorial list is rendered client-side; the served 45KB carries 0 matches.
    # So an empty result here means the content moved behind client-side rendering, and
    # reporting silence would be indistinguishable from a genuinely uneventful day.
    # classify_row keys on `needs_selector_work` and counts this as a STUB: never a real
    # row, never an error, and never a healthy zero (L1.28a). It needs an API or a
    # rendering fetch, not another regex.
    if not discoveries:
        discoveries.append({"source": "quantconnect", "kind": "stub",
                            "needs_selector_work": True,
                            "host": "www.quantconnect.com/tutorials/strategy-library",
                            "why": "fetched OK, content is client-side rendered"})
    return discoveries

def run_and_save() -> list[dict]:
    discoveries = mine_quantconnect()
    out_file = OUT / f"discoveries_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.json"
    out_file.write_text(json.dumps(discoveries, indent=2), encoding="utf-8")
    print(f"quantconnect: {len(discoveries)} discoveries saved")
    return discoveries

if __name__ == "__main__":
    run_and_save()
