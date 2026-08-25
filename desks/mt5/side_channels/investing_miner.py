"""Investing.com sentiment and economic calendar miner.

Scrapes Investing.com for:
- Economic calendar (alternative to ForexFactory)
- Sentiment indicators (retail vs institutional positioning)
- Analyst recommendations
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "intelligence" / "investing"
OUT.mkdir(parents=True, exist_ok=True)

HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}

# Sentiment pages for major pairs
SENTIMENT_URLS = {
    "EURUSD": "https://www.investing.com/currencies/eur-usd-sentiment",
    "GBPUSD": "https://www.investing.com/currencies/gbp-usd-sentiment",
    "USDJPY": "https://www.investing.com/currencies/usd-jpy-sentiment",
    "XAUUSD": "https://www.investing.com/commodities/gold-sentiment",
    "AUDUSD": "https://www.investing.com/currencies/aud-usd-sentiment",
}


def mine_sentiment() -> list[dict]:
    """Fetch sentiment from Investing.com."""
    discoveries = []
    for sym, url in SENTIMENT_URLS.items():
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                continue
            text = resp.text

            # Extract retail sentiment (buy/sell percentages)
            buy_match = re.search(r'(\d+\.?\d*)%\s*(?:are\s+)?buy', text, re.IGNORECASE)
            sell_match = re.search(r'(\d+\.?\d*)%\s*(?:are\s+)?sell', text, re.IGNORECASE)

            if buy_match and sell_match:
                buy_pct = float(buy_match.group(1))
                sell_pct = float(sell_match.group(1))
                # Retail is often wrong at extremes (contrarian)
                if buy_pct > 70:
                    signal = "contrarian_sell"
                    conf = min(0.7, buy_pct / 100)
                elif sell_pct > 70:
                    signal = "contrarian_buy"
                    conf = min(0.7, sell_pct / 100)
                else:
                    signal = "neutral"
                    conf = 0.2

                discoveries.append({
                    "source": "investing",
                    "type": "retail_sentiment",
                    "symbol": sym,
                    "buy_pct": buy_pct,
                    "sell_pct": sell_pct,
                    "signal": signal,
                    "symbols": [sym],
                    "confidence": conf,
                    "description": f"{sym} retail: {buy_pct:.1f}% buy / {sell_pct:.1f}% sell",
                })
        except Exception:
            continue
    return discoveries


def run_and_save() -> list[dict]:
    discoveries = mine_sentiment()
    out_file = OUT / f"discoveries_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.json"
    out_file.write_text(json.dumps(discoveries, indent=2, default=str), encoding="utf-8")
    print(f"investing: {len(discoveries)} discoveries saved")
    return discoveries


if __name__ == "__main__":
    run_and_save()
