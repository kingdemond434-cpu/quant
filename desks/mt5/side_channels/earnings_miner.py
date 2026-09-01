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

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"}


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

    # A 200 WITH NOTHING IN IT IS NOT A QUIET SOURCE. Measured 2026-09-01: this host serves

    # the page but not the DATA -- the Earnings Date field is rendered client-side; the served 1.1MB carries 0 matches.

    # So an empty result here means the content moved behind client-side rendering, and

    # reporting silence would be indistinguishable from a genuinely uneventful day.

    # classify_row keys on `needs_selector_work` and counts this as a STUB: never a real

    # row, never an error, and never a healthy zero (L1.28a). It needs an API or a

    # rendering fetch, not another regex.

    if not discoveries:

        discoveries.append({"source": "earnings", "kind": "stub",

                            "needs_selector_work": True,

                            "host": "finance.yahoo.com/quote/<ticker>/",

                            "why": "fetched OK, content is client-side rendered"})

    return discoveries


def run_and_save() -> list[dict]:
    discoveries = mine_earnings_calendar()
    out_file = OUT / f"discoveries_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.json"
    out_file.write_text(json.dumps(discoveries, indent=2, default=str), encoding="utf-8")
    print(f"earnings: {len(discoveries)} discoveries saved")
    return discoveries


if __name__ == "__main__":
    run_and_save()
