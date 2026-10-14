"""Google Trends mining miner.

Scrapes Google Trends for search volume spikes on trading terms.
High search volume for "buy gold" = retail FOMO = potential top.
Low search volume = indifference = potential bottom.

Uses Google Trends RSS/CSV (no API key needed).
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "intelligence" / "google_trends"
OUT.mkdir(parents=True, exist_ok=True)

HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}

# Search terms that move markets
SEARCH_TERMS = {
    "forex": ["buy gold", "sell euro", "forex trading", "gold price", "usd jpy"],
    "commodities": ["oil price", "silver price", "copper price", "natural gas price"],
    "crypto": ["bitcoin buy", "ethereum buy", "crypto crash"],
    "macro": ["recession", "inflation", "interest rates", "fed rate"],
    "sentiment": ["stock market crash", "bull market", "bear market", "buy stocks"],
}

# Map search terms to symbols
TERM_TO_SYMBOLS = {
    "buy gold": ["XAUUSD"], "gold price": ["XAUUSD"], "sell gold": ["XAUUSD"],
    "silver price": ["XAGUSD"], "buy silver": ["XAGUSD"],
    "oil price": ["USOIL"], "natural gas price": ["NATGAS"],
    "copper price": ["COPPER"],
    "usd jpy": ["USDJPY"], "sell euro": ["EURUSD"], "buy euro": ["EURUSD"],
    "forex trading": ["EURUSD", "GBPUSD", "USDJPY"],
    "bitcoin buy": ["BTCUSD"], "bitcoin crash": ["BTCUSD"],
    "ethereum buy": ["ETHUSD"],
    "stock market crash": ["US500", "NAS100"],
    "bull market": ["US500"], "bear market": ["US500"],
    "recession": ["USDJPY", "XAUUSD", "US500"],
    "interest rates": ["USDJPY", "EURUSD", "XAUUSD"],
}


#: Weeks the trend reading needs: four recent against the four before them.
MIN_TIMELINE = 8


def trend_reading(timeline: list[dict]) -> float | None:
    """Last 4 weeks vs the 4 before, in percent; None (UNMEASURED) when it cannot be computed.

    NEVER A ZERO FOR "NO DATA". A short timeline or a zero base used to be written as
    trend_pct=0, which the seat series (`alt_seat_cells`, seat_google_trends) cannot tell from a
    genuinely flat month -- a silent zero entering a PIT series. No reading emits no row.
    """
    if len(timeline) < MIN_TIMELINE:
        return None
    try:
        vals = [float(t.get("value", [0])[0]) for t in timeline[-MIN_TIMELINE:]]
    except (TypeError, ValueError, IndexError, AttributeError):
        return None
    recent = sum(vals[-4:]) / 4
    prev = sum(vals[:4]) / 4
    if prev <= 0:
        return None
    return (recent - prev) / prev * 100


def mine_google_trends() -> list[dict]:
    """Fetch Google Trends data for trading terms."""
    discoveries = []

    for category, terms in SEARCH_TERMS.items():
        for term in terms:
            try:
                # Use Google Trends explore page (HTML scraping)
                url = f"https://trends.google.com/trends/explore?q={term.replace(' ', '+')}&date=today+12-m"
                resp = requests.get(url, headers=HEADERS, timeout=15)

                if resp.status_code == 200:
                    # Extract trend data from HTML
                    text = resp.text
                    # Look for JSON data embedded in page
                    match = re.search(r'"timelineData":\s*(\[.*?\])', text)
                    if match:
                        timeline = json.loads(match.group(1))
                        if timeline:
                            # Get latest value
                            latest = timeline[-1].get("value", [0])[0]
                            # Calculate trend (last 4 weeks vs previous 4); unmeasurable
                            # emits nothing rather than a zero
                            trend_pct = trend_reading(timeline)

                            syms = TERM_TO_SYMBOLS.get(term, [])
                            if syms and latest > 0 and trend_pct is not None:
                                discoveries.append({
                                    "source": "google_trends",
                                    "type": "search_volume",
                                    "term": term,
                                    "category": category,
                                    "current_value": latest,
                                    "trend_pct": round(trend_pct, 1),
                                    "symbols": syms,
                                    "confidence": min(0.7, abs(trend_pct) / 50),
                                    "description": f"'{term}' search volume {trend_pct:+.1f}% vs 4-week avg",
                                })
            except Exception:
                pass

    return discoveries


def run_and_save() -> list[dict]:
    discoveries = mine_google_trends()
    out_file = OUT / f"discoveries_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.json"
    try:
        from side_channels.discovery_io import write_discoveries
    except ModuleNotFoundError:
        from discovery_io import write_discoveries
    discoveries = write_discoveries(out_file, discoveries)
    print(f"google_trends: {len(discoveries)} discoveries saved")
    return discoveries


if __name__ == "__main__":
    run_and_save()
