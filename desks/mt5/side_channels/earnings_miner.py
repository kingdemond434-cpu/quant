"""Earnings whispers and pre-earnings sentiment miner.

Scrapes earnings calendars and pre-earnings sentiment data.
Pre-earnings drift is a well-documented anomaly.
"""

import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "intelligence" / "earnings"
OUT.mkdir(parents=True, exist_ok=True)

HEADERS = {"User-Agent": "Mozilla/5.0"}


def mine_earnings_calendar() -> list[dict]:
    """Fetch upcoming earnings dates for major companies that impact FX/indices."""
    discoveries = []
    # Use Yahoo Finance earnings calendar
    symbols_to_track = {
        "AAPL": "US500", "MSFT": "US500", "GOOGL": "US500",
        "AMZN": "US500", "NVDA": "US500", "META": "US500",
        "TSLA": "US500", "JPM": "US500", "GS": "US500",
        "V": "US500", "MA": "US500", "BAC": "US500",
    }

    for ticker, index in symbols_to_track.items():
        try:
            url = f"https://finance.yahoo.com/quote/{ticker}/"
            resp = requests.get(url, headers=HEADERS, timeout=10)
            if resp.status_code == 200:
                text = resp.text
                # Look for earnings date
                earn_match = re.search(r'Earnings(?:Date|s).*?(\w+ \d+,?\s*\d{4})', text)
                if earn_match:
                    date_str = earn_match.group(1)
                    discoveries.append({
                        "source": "earnings",
                        "type": "earnings_date",
                        "ticker": ticker,
                        "index": index,
                        "date": date_str,
                        "symbols": [index],
                        "confidence": 0.3,
                        "description": f"{ticker} earnings on {date_str} - may impact {index}",
                    })
        except Exception:
            continue

    return discoveries


def run_and_save() -> list[dict]:
    discoveries = mine_earnings_calendar()
    out_file = OUT / f"discoveries_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.json"
    out_file.write_text(json.dumps(discoveries, indent=2, default=str), encoding="utf-8")
    print(f"earnings: {len(discoveries)} discoveries saved")
    return discoveries


if __name__ == "__main__":
    run_and_save()
