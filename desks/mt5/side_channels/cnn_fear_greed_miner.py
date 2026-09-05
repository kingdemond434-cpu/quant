"""CNN Fear & Greed Index miner.

Scrapes CNN's Fear & Greed Index for market sentiment extremes.
When fear is extreme = potential bottom.
When greed is extreme = potential top.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "intelligence" / "fear_greed"
OUT.mkdir(parents=True, exist_ok=True)

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"}
FNG_URL = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"


def mine_fear_greed() -> list[dict]:
    """Fetch CNN Fear & Greed Index."""
    discoveries = []
    try:
        resp = requests.get(FNG_URL, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        fng = data.get("fear_and_greed", {})
        score = fng.get("score", 0)
        rating = fng.get("rating", "")
        previous_close = fng.get("previous_close", 0)
        week_ago = fng.get("week_ago", 0)
        month_ago = fng.get("month_ago", 0)

        if score:
            # Extreme fear (< 25) = contrarian buy
            if score < 25:
                discoveries.append({
                    "source": "cnn_fear_greed",
                    "type": "extreme_sentiment",
                    "reading": "extreme_fear",
                    "score": score,
                    "rating": rating,
                    "symbols": ["US500", "NAS100", "XAUUSD"],
                    "confidence": min(0.8, (25 - score) / 25),
                    "description": f"Fear & Greed: {score} ({rating}) - contrarian buy signal",
                })
            # Extreme greed (> 75) = contrarian sell
            elif score > 75:
                discoveries.append({
                    "source": "cnn_fear_greed",
                    "type": "extreme_sentiment",
                    "reading": "extreme_greed",
                    "score": score,
                    "rating": rating,
                    "symbols": ["US500", "NAS100"],
                    "confidence": min(0.8, (score - 75) / 25),
                    "description": f"Fear & Greed: {score} ({rating}) - contrarian sell signal",
                })
            else:
                discoveries.append({
                    "source": "cnn_fear_greed",
                    "type": "sentiment_reading",
                    "reading": "neutral",
                    "score": score,
                    "rating": rating,
                    "symbols": ["US500", "NAS100"],
                    "confidence": 0.3,
                    "description": f"Fear & Greed: {score} ({rating})",
                })

            # Rapid change detection
            if previous_close and abs(score - previous_close) > 10:
                direction = "improving" if score > previous_close else "worsening"
                discoveries.append({
                    "source": "cnn_fear_greed",
                    "type": "rapid_change",
                    "score": score,
                    "previous_close": previous_close,
                    "change": round(score - previous_close, 1),
                    "symbols": ["US500", "NAS100"],
                    "confidence": min(0.6, abs(score - previous_close) / 20),
                    "description": f"Fear & Greed changed {direction} by {abs(score - previous_close):.0f} pts in 1 day",
                })

    except Exception as e:
        print(f"  fear_greed: {e}")
        # A SWALLOWED EXCEPTION IS A SILENT ZERO: printing and returning [] makes a
        # crashed miner indistinguishable from a quiet source. classify_row keys on
        # "kind", so this counts as an error and never as a real row (L1.28a).
        discoveries.append({"source": "cnn_fear_greed",
                            "kind": "fetch_error",
                            "error": f"{type(e).__name__}: {e}"})

    return discoveries


def run_and_save() -> list[dict]:
    discoveries = mine_fear_greed()
    out_file = OUT / f"discoveries_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.json"
    out_file.write_text(json.dumps(discoveries, indent=2, default=str), encoding="utf-8")
    print(f"fear_greed: {len(discoveries)} discoveries saved")
    return discoveries


if __name__ == "__main__":
    run_and_save()
