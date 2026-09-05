"""MQL5 codebase miner.

Scans MQL5.com codebase for new trading robots/indicators,
extracts mentioned symbols/patterns/logic, and outputs structured alpha candidates.

Uses MQL5 public pages (no API key needed).
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "intelligence" / "mql5"
OUT.mkdir(parents=True, exist_ok=True)

CODEBASE_URL = "https://www.mql5.com/en/code_base"
SYMBOLS = [
    "XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD",
    "USDCAD", "USDCHF", "NZDUSD", "EURJPY", "GBPJPY",
    "AUDJPY", "CADJPY", "NZDJPY", "CHFJPY", "EURAUD",
    "GBPAUD", "AUDNZD", "NZDCAD", "AUDCAD", "BTCUSD",
    "ETHUSD", "US500", "NAS100",
]


def _extract_symbols(text: str) -> list[str]:
    text_upper = text.upper()
    return [s for s in SYMBOLS if s in text_upper]


def _extract_patterns(text: str) -> list[str]:
    known = [
        "breakout", "scalping", "grid", "martingale", "hedging",
        "news trading", "session range", "asia range", "london open",
        "fibonacci", "bollinger", "RSI", "MACD", "moving average",
        "order block", "fair value gap", "liquidity", "smart money",
        "trend following", "mean reversion", "momentum",
    ]
    text_lower = text.lower()
    return [p for p in known if p.lower() in text_lower]


def mine_codebase(max_pages: int = 3) -> list[dict]:
    """Scrape MQL5 codebase for recent EAs and indicators."""
    discoveries = []

    for page in range(1, max_pages + 1):
        try:
            resp = requests.get(
                CODEBASE_URL,
                params={"page": page, "sort": "date"},
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"},
                timeout=15,
            )
            resp.raise_for_status()
            text = resp.text

            # Extract product links and descriptions
            links = re.findall(r'href="(/en/market/product/[^"]+)"', text)
            titles = re.findall(r'<h3[^>]*>([^<]+)</h3>', text)
            descs = re.findall(r'<p[^>]*class="[^"]*desc[^"]*"[^>]*>([^<]+)</p>', text)

            for i, link in enumerate(links[:20]):
                title = titles[i] if i < len(titles) else ""
                desc = descs[i] if i < len(descs) else ""
                combined = f"{title} {desc}"

                syms = _extract_symbols(combined)
                pats = _extract_patterns(combined)

                if syms or pats:
                    discoveries.append({
                        "source": "mql5_codebase",
                        "title": title,
                        "url": f"https://www.mql5.com{link}",
                        "description": desc,
                        "symbols": syms,
                        "patterns": pats,
                        "confidence": min(1.0, len(syms) * 0.2 + len(pats) * 0.15),
                    })
        except Exception:
            continue

    return discoveries


def run_and_save() -> list[dict]:
    """Mine codebase and save results."""
    discoveries = mine_codebase()
    out_file = OUT / f"codebase_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.json"
    out_file.write_text(json.dumps(discoveries, indent=2), encoding="utf-8")
    print(f"mql5_codebase: {len(discoveries)} discoveries saved to {out_file.name}")
    return discoveries


if __name__ == "__main__":
    run_and_save()
