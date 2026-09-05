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

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"}


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
                # ANCHOR ON THE LABEL, NOT ON POSITION. This searched for the FIRST 3-5 digit
                # number anywhere in the page and then required 200 < v < 5000. Measured
                # 2026-09-01 against the live 417KB page, that first match is `157` -- a
                # fragment of markup -- which fails the range test, so the miner appended
                # nothing and reported a healthy fetch with no rows. A positional regex over
                # modern HTML is a lottery, not an extraction.
                #
                # The value that follows the "Baltic Dry" label is the quote: 3,157.00 on the
                # day this was fixed. Thousands separators are stripped, which the old pattern
                # could not even represent (\d{3,5} cannot match "3,157").
                #
                # The sanity band is widened because the old one was itself wrong: the BDI
                # traded above 5,000 in 2021, so `< 5000` would have discarded a real reading
                # as garbage. It stays a band -- an unanchored number is still rejected -- just
                # one that spans the index's actual history.
                m = re.search(r'(?is)Baltic\s*Dry.{0,400}?>\s*([\d,]{3,8}\.?\d*)\s*<', text)
                bdi_match = m
                if bdi_match:
                    bdi_value = int(float(bdi_match.group(1).replace(",", "")))
                    if 100 < bdi_value < 15000:  # BDI's real historical range
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
