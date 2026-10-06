"""MQL5 codebase miner.

Scans MQL5.com codebase for new trading robots/indicators,
extracts mentioned symbols/patterns/logic, and outputs structured alpha candidates.

Uses MQL5 public pages (no API key needed).
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
REFUSAL = OUT / "discoveries_blocked_terms_codebase.json"

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
    # FAIL-CLOSED TERMS FENCE: MQL5 ToU 3.7/3.9/3.13 prohibit this fetch.
    mql5_terms.guard(CODEBASE_URL)
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
    # Refused before any request; the refusal is the hour's recorded artifact.
    if mql5_terms.is_mql5_url(CODEBASE_URL):
        mql5_terms.refuse("mql5_codebase", REFUSAL)
        return []
    discoveries = mine_codebase()
    out_file = OUT / f"codebase_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.json"
    try:
        from side_channels.discovery_io import write_discoveries
    except ModuleNotFoundError:
        from discovery_io import write_discoveries
    discoveries = write_discoveries(out_file, discoveries)
    print(f"mql5_codebase: {len(discoveries)} discoveries saved to {out_file.name}")
    return discoveries


if __name__ == "__main__":
    run_and_save()
