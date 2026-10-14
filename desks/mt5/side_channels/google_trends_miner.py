"""Google Trends mining miner.

Scrapes Google Trends for search volume spikes on trading terms.
High search volume for "buy gold" = retail FOMO = potential top.
Low search volume = indifference = potential bottom.

Uses Google Trends RSS/CSV (no API key needed).
"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parent.parent
for _p in (str(BASE), str(BASE / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
try:
    from research import hard_stop
except ImportError:                                         # pragma: no cover - layout
    import hard_stop  # type: ignore[no-redef,import-not-found]

OUT = BASE / "data" / "intelligence" / "google_trends"
OUT.mkdir(parents=True, exist_ok=True)
#: THE HARD STOP (standing project rule, `research/hard_stop.py`): the persisted backoff marker
#: and the register the block is recorded in. A 401/403/429 ends the pass; later passes request
#: nothing until the backoff expires; no retry around it, no UA rotation, no other host.
BLOCK_STATE = BASE / "data" / "google_trends_block.json"
BLOCKED_REGISTER = hard_stop.BLOCKED_REGISTER
REGISTER_KEY = "google_trends"
#: What the last pass did (status, requests, block), for the caller's one-line summary.
LAST_PASS: dict = {}

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


def timeline_from(text: str) -> list[dict]:
    """The embedded `timelineData` array, decoded whole. The old non-greedy bracket match stopped at
    the first `]`, which is inside the first point's own `"value": [n]`, so it never decoded."""
    m = re.search(r'"timelineData":\s*', text)
    if not m:
        return []
    try:
        val, _end = json.JSONDecoder().raw_decode(text, m.end())
    except ValueError:
        return []
    return [t for t in val if isinstance(t, dict)] if isinstance(val, list) else []


def _load_block() -> dict | None:
    try:
        doc = json.loads(BLOCK_STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


def mine_google_trends(now: datetime | None = None) -> list[dict]:
    """Fetch Google Trends data for trading terms, under the hard stop."""
    now = now or datetime.now(timezone.utc)
    discoveries: list[dict] = []
    prior = _load_block()
    LAST_PASS.clear()
    LAST_PASS.update({"requests": 0, "ok_responses": 0, "block": None})
    if hard_stop.active(prior, now):
        assert prior is not None
        LAST_PASS.update({"status": prior.get("status"), "skipped": True, "block": prior})
        return discoveries

    blocked = False
    for category, terms in SEARCH_TERMS.items():
        if blocked:
            break
        for term in terms:
            try:
                # Use Google Trends explore page (HTML scraping)
                url = f"https://trends.google.com/trends/explore?q={term.replace(' ', '+')}&date=today+12-m"
                resp = requests.get(url, headers=HEADERS, timeout=15)
                LAST_PASS["requests"] += 1
                status = int(resp.status_code)
                if status in hard_stop.HARD_STOP:
                    marker = hard_stop.block_marker(status, "explore",
                                                    dict(getattr(resp, "headers", None) or {}),
                                                    now, prior)
                    BLOCK_STATE.parent.mkdir(parents=True, exist_ok=True)
                    BLOCK_STATE.write_text(json.dumps(marker, indent=1), encoding="utf-8")
                    hard_stop.record_block(marker, BLOCKED_REGISTER, key=REGISTER_KEY,
                                           host="trends.google.com")
                    LAST_PASS.update({"status": marker["status"], "block": marker})
                    blocked = True
                    break                    # THE HARD STOP: no further request this pass

                if resp.status_code == 200:
                    LAST_PASS["ok_responses"] += 1
                    # Extract trend data from HTML
                    text = resp.text
                    # Look for JSON data embedded in page
                    timeline = timeline_from(text)
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

    if not blocked:
        LAST_PASS["status"] = "FETCHED" if LAST_PASS["ok_responses"] else "FAILED"
        if LAST_PASS["ok_responses"] and prior is not None:
            BLOCK_STATE.unlink(missing_ok=True)   # an answered, unrefused pass ends the ladder
    return discoveries


def run_and_save() -> list[dict]:
    discoveries = mine_google_trends()
    out_file = OUT / f"discoveries_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.json"
    try:
        from side_channels.discovery_io import write_discoveries
    except ModuleNotFoundError:
        from discovery_io import write_discoveries
    discoveries = write_discoveries(out_file, discoveries)
    print(f"google_trends: {len(discoveries)} discoveries saved "
          f"(pass {LAST_PASS.get('status')}, {LAST_PASS.get('requests')} requests)")
    return discoveries


if __name__ == "__main__":
    run_and_save()
