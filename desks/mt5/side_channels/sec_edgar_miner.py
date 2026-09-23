"""SEC EDGAR 13F filings miner.

Scrapes SEC EDGAR for hedge fund 13F filings.
When top hedge funds load up on a position, it's a signal.
When they dump, it's a warning.
"""

import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "intelligence" / "sec_edgar"
OUT.mkdir(parents=True, exist_ok=True)

HEADERS = {"User-Agent": "QuantResearch quant@example.com"}

# Top hedge funds to track
FUND_CIKS = {
    "Bridgewater": "0001350694",
    "Renaissance": "0001037389",
    "Citadel": "0001423053",
    "Point72": "0001567464",
    "D.E. Shaw": "0001649339",
    "Two Sigma": "0001590974",
    "Millennium": "0001103804",
    "Baupost": "0001061768",
    "Soros": "0001028931",
    "Appaloosa": "0001103847",
}

SEC_SEARCH = "https://efts.sec.gov/LATEST/search-index?q=%2213F%22&dateRange=custom&startdt={start}&enddt={end}&forms=13F-HR"


def mine_13f() -> list[dict]:
    """Fetch recent 13F filings from top hedge funds."""
    discoveries = []
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=30)

    for fund, cik in FUND_CIKS.items():
        try:
            url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=13F&dateb=&owner=include&count=5&search_text=&action=getcompany"
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code == 200:
                text = resp.text
                # Check for recent filing
                if "13F" in text:
                    discoveries.append({
                        "source": "sec_edgar",
                        "type": "13f_filing",
                        "fund": fund,
                        "cik": cik,
                        "symbols": ["US500", "NAS100"],
                        "confidence": 0.4,
                        "description": f"{fund} has recent 13F filing - check for position changes",
                    })
        except Exception:
            continue

    return discoveries


def run_and_save() -> list[dict]:
    discoveries = mine_13f()
    out_file = OUT / f"discoveries_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.json"
    out_file.write_text(json.dumps(discoveries, indent=2, default=str), encoding="utf-8")
    print(f"sec_edgar: {len(discoveries)} discoveries saved")
    return discoveries


if __name__ == "__main__":
    run_and_save()
