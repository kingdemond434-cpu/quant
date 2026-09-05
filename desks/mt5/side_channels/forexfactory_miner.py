"""ForexFactory economic calendar miner.

Scrapes ForexFactory's economic calendar for high-impact events,
which drive major FX moves. Also mines the FF forum for strategy ideas.

Calendar events are the #1 cause of intraday FX volatility.
Knowing when NFP, CPI, rate decisions happen = alpha.
"""

import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "intelligence" / "forexfactory"
OUT.mkdir(parents=True, exist_ok=True)

CALENDAR_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
CALENDAR_NEXT_URL = "https://nfs.faireconomy.media/ff_calendar_nextweek.json"

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"}

# Impact levels that move markets
HIGH_IMPACT = {"High", "Red"}
MEDIUM_IMPACT = {"Medium", "Orange"}

SYMBOL_IMPACT = {
    "USD": ["EURUSD", "GBPUSD", "USDJPY", "USDCAD", "USDCHF", "AUDUSD", "NZDUSD", "XAUUSD", "US500", "NAS100"],
    "EUR": ["EURUSD", "EURJPY", "EURAUD", "GBPEUR"],
    "GBP": ["GBPUSD", "GBPJPY", "GBPAUD"],
    "JPY": ["USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "CADJPY", "NZDJPY", "CHFJPY", "XAUUSD"],
    "AUD": ["AUDUSD", "AUDJPY", "AUDNZD", "AUDCAD", "EURAUD", "GBPAUD"],
    "NZD": ["NZDUSD", "NZDJPY", "NZDCAD", "AUDNZD"],
    "CAD": ["USDCAD", "NZDCAD", "AUDCAD"],
    "CHF": ["USDCHF", "CHFJPY"],
    "CNY": ["USDJPY", "AUDUSD", "NZDUSD"],
}


def mine_calendar() -> list[dict]:
    """Fetch economic calendar for this week + next week."""
    discoveries = []

    for url in [CALENDAR_URL, CALENDAR_NEXT_URL]:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            events = resp.json()

            for event in events:
                impact = event.get("impact", "")
                currency = event.get("country", "") or event.get("currency", "")
                title = event.get("title", "")
                date_str = event.get("date", "")

                # Only care about medium+ impact
                if impact not in HIGH_IMPACT and impact not in MEDIUM_IMPACT:
                    continue

                # Get affected symbols
                syms = SYMBOL_IMPACT.get(currency, [])
                if not syms:
                    continue

                is_high = impact in HIGH_IMPACT

                # Parse title for additional symbols/patterns
                combined = f"{title} {currency}"
                extra_syms = []
                for s in ["XAUUSD", "GOLD", "OIL", "BTCUSD"]:
                    if s.upper() in combined.upper():
                        extra_syms.append(s)
                syms = list(set(syms + extra_syms))

                discoveries.append({
                    "source": "forexfactory",
                    "type": "calendar_event",
                    "title": title,
                    "currency": currency,
                    "impact": "HIGH" if is_high else "MEDIUM",
                    "date": date_str,
                    "symbols": syms,
                    "confidence": 0.7 if is_high else 0.4,
                    "description": f"{impact} impact {currency} event: {title}",
                })

        except Exception as e:
            print(f"  forexfactory calendar: {e}")
        # A SWALLOWED EXCEPTION IS A SILENT ZERO: printing and returning [] makes a
        # crashed miner indistinguishable from a quiet source. classify_row keys on
        # "kind", so this counts as an error and never as a real row (L1.28a).
        discoveries.append({"source": "forexfactory",
                            "kind": "fetch_error",
                            "error": f"{type(e).__name__}: {e}"})

    return discoveries


def mine_forum() -> list[dict]:
    """Mine ForexFactory forum for strategy discussions."""
    discoveries = []
    forums = [
        ("https://www.forexfactory.com/thread/post/14458923", "trading_systems"),
    ]
    # FF forum requires auth for most content — skip for now
    # Calendar is the high-value target anyway
    return discoveries


def run_and_save() -> list[dict]:
    """Mine calendar and forum, save results."""
    cal = mine_calendar()
    forum = mine_forum()
    all_disc = cal + forum

    out_file = OUT / f"discoveries_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.json"
    out_file.write_text(json.dumps(all_disc, indent=2, default=str), encoding="utf-8")
    print(f"forexfactory: {len(all_disc)} calendar events saved")
    return all_disc


if __name__ == "__main__":
    run_and_save()
