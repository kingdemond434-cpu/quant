"""Wires all external discovery channels.

Runs all 12 miners and saves combined discoveries.
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

# Direct-import miners (no relative imports)
from youtube_miner import run_and_save as youtube_mine
from github_miner import run_and_save as github_mine
from mql5_codebase import run_and_save as mql5_codebase_mine
from mql5_articles import run_and_save as mql5_articles_mine
from mql5_signals import run_and_save as mql5_signals_mine
from mql5_forum import run_and_save as mql5_forum_mine
from tradingview_miner import run_and_save as tradingview_mine
from quantconnect_miner import run_and_save as quantconnect_mine
from central_bank_miner import run_and_save as central_bank_mine
from china_miner import run_and_save as china_mine
from korea_miner import run_and_save as korea_mine

# truth_social_miner is class-based (TruthSocialCollector), no run_and_save.
# Silently skipped — runs via its own entry point.


ALL_MINERS = [
    ("youtube", youtube_mine),
    ("github", github_mine),
    ("mql5_codebase", mql5_codebase_mine),
    ("mql5_articles", mql5_articles_mine),
    ("mql5_signals", mql5_signals_mine),
    ("mql5_forum", mql5_forum_mine),
    ("tradingview", tradingview_mine),
    ("quantconnect", quantconnect_mine),
    ("central_bank", central_bank_mine),
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
