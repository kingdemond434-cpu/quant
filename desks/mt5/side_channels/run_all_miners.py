"""Wires all 25 external discovery channels.

Runs all miners and saves combined discoveries.
Can be invoked standalone or imported by hourly_controller.
"""

import sys
import os
import json
from datetime import datetime, timezone
from pathlib import Path

# Ensure side_channels dir is on path for direct imports
_dir = os.path.dirname(os.path.abspath(__file__))
if _dir not in sys.path:
    sys.path.insert(0, _dir)

# --- Tier 1: Social/Web miners ---
from youtube_miner import run_and_save as youtube_mine
from github_miner import run_and_save as github_mine
from mql5_codebase import run_and_save as mql5_codebase_mine
from mql5_articles import run_and_save as mql5_articles_mine
from mql5_signals import run_and_save as mql5_signals_mine
from mql5_forum import run_and_save as mql5_forum_mine
from tradingview_miner import run_and_save as tradingview_mine
from quantconnect_miner import run_and_save as quantconnect_mine
from reddit_miner import run_and_save as reddit_mine

# --- Tier 2: Institutional/Calendar miners ---
from central_bank_miner import run_and_save as central_bank_mine
from forexfactory_miner import run_and_save as forexfactory_mine
from cot_miner import run_and_save as cot_mine
from sec_edgar_miner import run_and_save as sec_edgar_mine
from earnings_miner import run_and_save as earnings_mine

# --- Tier 3: Sentiment miners ---
from aaii_sentiment_miner import run_and_save as aaii_mine
from cnn_fear_greed_miner import run_and_save as fear_greed_mine
from investing_miner import run_and_save as investing_mine
from google_trends_miner import run_and_save as google_trends_mine

# --- Tier 4: Academic/Research miners ---
from academic_miner import run_and_save as academic_mine

# --- Tier 5: Macro/Physical miners ---
from correlation_miner import run_and_save as correlation_mine
from seasonality_miner import run_and_save as seasonality_mine
from weather_miner import run_and_save as weather_mine
from shipping_miner import run_and_save as shipping_mine

# --- Tier 6: Regional miners ---
from china_miner import run_and_save as china_mine
from korea_miner import run_and_save as korea_mine

# truth_social_miner is class-based (TruthSocialCollector), no run_and_save.
# Silently skipped.


ALL_MINERS = [
    # Social/Web
    ("youtube", youtube_mine),
    ("github", github_mine),
    ("mql5_codebase", mql5_codebase_mine),
    ("mql5_articles", mql5_articles_mine),
    ("mql5_signals", mql5_signals_mine),
    ("mql5_forum", mql5_forum_mine),
    ("tradingview", tradingview_mine),
    ("quantconnect", quantconnect_mine),
    ("reddit", reddit_mine),
    # Institutional/Calendar
    ("central_bank", central_bank_mine),
    ("forexfactory", forexfactory_mine),
    ("cot", cot_mine),
    ("sec_edgar", sec_edgar_mine),
    ("earnings", earnings_mine),
    # Sentiment
    ("aaii", aaii_mine),
    ("fear_greed", fear_greed_mine),
    ("investing", investing_mine),
    ("google_trends", google_trends_mine),
    # Academic
    ("academic", academic_mine),
    # Macro/Physical
    ("correlations", correlation_mine),
    ("seasonality", seasonality_mine),
    ("weather", weather_mine),
    ("shipping", shipping_mine),
    # Regional
    ("china", china_mine),
    ("korea", korea_mine),
]


def run_all_miners() -> dict:
    results = {}
    total = 0
    for name, fn in ALL_MINERS:
        try:
            disc = fn()
            results[name] = {"count": len(disc), "discoveries": disc}
            total += len(disc)
            print(f"  {name}: {len(disc)} discoveries")
        except Exception as e:
            results[name] = {"count": 0, "error": str(e)}
            print(f"  {name}: FAILED ({e})")

    ok = sum(1 for r in results.values() if r.get("count", 0) > 0)
    results["summary"] = {
        "total_miners": len(ALL_MINERS),
        "total_discoveries": total,
        "successful_miners": ok,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return results


if __name__ == "__main__":
    print("=== EXTERNAL DISCOVERY: ALL CHANNELS ===")
    r = run_all_miners()
    s = r["summary"]
    print(f"\n{s['successful_miners']}/{s['total_miners']} miners returned {s['total_discoveries']} discoveries")

    out = Path(__file__).resolve().parent.parent / "data" / "intelligence" / "latest_discoveries.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(r, indent=2, default=str), encoding="utf-8")
    print(f"Saved to {out}")
