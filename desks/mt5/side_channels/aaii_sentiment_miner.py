"""AAII Sentiment Survey miner.

Scrapes AAII (American Association of Individual Investors) weekly
sentiment survey. When retail is extremely bullish = potential top.
When retail is extremely bearish = potential bottom.
Contrarian indicator with proven track record.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "intelligence" / "aaii"
OUT.mkdir(parents=True, exist_ok=True)

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"}
AAII_URL = "https://www.aaii.com/sentimentsurvey"


def mine_aaii() -> list[dict]:
    """Fetch AAII sentiment survey data."""
    discoveries = []
    try:
        resp = requests.get(AAII_URL, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        text = resp.text

        # Extract sentiment percentages
        bullish = re.search(r'bullish.*?(\d+\.?\d*)%', text, re.IGNORECASE)
        bearish = re.search(r'bearish.*?(\d+\.?\d*)%', text, re.IGNORECASE)
        neutral = re.search(r'neutral.*?(\d+\.?\d*)%', text, re.IGNORECASE)

        if bullish and bearish:
            bull_pct = float(bullish.group(1))
            bear_pct = float(bearish.group(1))
            bull_bear_ratio = bull_pct / bear_pct if bear_pct > 0 else 999

            # Extreme readings
            if bull_pct > 60:
                discoveries.append({
                    "source": "aaii",
                    "type": "extreme_sentiment",
                    "reading": "extreme_bullish",
                    "bullish_pct": bull_pct,
                    "bearish_pct": bear_pct,
                    "bull_bear_ratio": round(bull_bear_ratio, 2),
                    "symbols": ["US500", "NAS100", "XAUUSD"],
                    "confidence": min(0.8, bull_pct / 100),
                    "description": f"AAII: {bull_pct:.1f}% bullish (extreme) - contrarian sell signal",
                })
            elif bear_pct > 60:
                discoveries.append({
                    "source": "aaii",
                    "type": "extreme_sentiment",
                    "reading": "extreme_bearish",
                    "bullish_pct": bull_pct,
                    "bearish_pct": bear_pct,
                    "bull_bear_ratio": round(bull_bear_ratio, 2),
                    "symbols": ["US500", "NAS100", "XAUUSD"],
                    "confidence": min(0.8, bear_pct / 100),
                    "description": f"AAII: {bear_pct:.1f}% bearish (extreme) - contrarian buy signal",
                })
            else:
                discoveries.append({
                    "source": "aaii",
                    "type": "sentiment_reading",
                    "reading": "neutral",
                    "bullish_pct": bull_pct,
                    "bearish_pct": bear_pct,
                    "bull_bear_ratio": round(bull_bear_ratio, 2),
                    "symbols": ["US500", "NAS100"],
                    "confidence": 0.3,
                    "description": f"AAII: {bull_pct:.1f}% bullish, {bear_pct:.1f}% bearish",
                })

    except Exception as e:
        print(f"  aaii: {e}")
        # A SWALLOWED EXCEPTION IS A SILENT ZERO: printing and returning [] makes a
        # crashed miner indistinguishable from a quiet source. classify_row keys on
        # "kind", so this counts as an error and never as a real row (L1.28a).
        discoveries.append({"source": "aaii_sentiment",
                            "kind": "fetch_error",
                            "error": f"{type(e).__name__}: {e}"})

    return discoveries


def run_and_save() -> list[dict]:
    discoveries = mine_aaii()
    out_file = OUT / f"discoveries_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.json"
    out_file.write_text(json.dumps(discoveries, indent=2, default=str), encoding="utf-8")
    print(f"aaii: {len(discoveries)} discoveries saved")
    return discoveries


if __name__ == "__main__":
    run_and_save()
