"""Baltic Dry Index (BDI) and shipping data miner.

The Baltic Dry Index measures the cost of shipping raw materials.
It's a leading indicator of global economic activity.
Rising BDI = increasing trade = risk on.
Falling BDI = decreasing trade = risk off.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "intelligence" / "shipping"
OUT.mkdir(parents=True, exist_ok=True)

HEADERS = {"User-Agent": "Mozilla/5.0"}


def mine_bdi() -> list[dict]:
    """Fetch Baltic Dry Index data."""
    discoveries = []

    # Try multiple sources for BDI
    sources = [
        "https://tradingeconomics.com/commodity/baltic",
        "https://www.investing.com/commodities/baltic-dry-index",
    ]

    for url in sources:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code == 200:
                text = resp.text
                # Extract BDI value
                bdi_match = re.search(r'(\d{3,5})', text)
                if bdi_match:
                    bdi_value = int(bdi_match.group(1))
                    if 200 < bdi_value < 5000:  # Reasonable BDI range
                        # Historical context
                        if bdi_value > 2000:
                            signal = "strong_expansion"
                            conf = 0.6
                        elif bdi_value < 800:
                            signal = "contraction"
                            conf = 0.6
                        else:
                            signal = "neutral"
                            conf = 0.3

                        discoveries.append({
                            "source": "shipping",
                            "type": "bdi",
                            "value": bdi_value,
                            "signal": signal,
                            "symbols": ["US500", "NAS100", "AUDUSD", "NZDUSD"],
                            "confidence": conf,
                            "description": f"BDI: {bdi_value} ({signal})",
                        })
                        break  # Got data, stop trying other sources
        except Exception:
            continue

    return discoveries


def run_and_save() -> list[dict]:
    discoveries = mine_bdi()
    out_file = OUT / f"discoveries_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.json"
    out_file.write_text(json.dumps(discoveries, indent=2, default=str), encoding="utf-8")
    print(f"shipping: {len(discoveries)} discoveries saved")
    return discoveries


if __name__ == "__main__":
    run_and_save()
