"""Earnings whispers and pre-earnings sentiment miner.

Scrapes earnings calendars and pre-earnings sentiment data.
Pre-earnings drift is a well-documented anomaly.

IDEAS LANE ONLY. Yahoo is an IDEAS_ONLY row of libs/data/terms_fence.SOURCE_POLICY, so every
page is read through THE POLITE DOOR (`polite_fetch.get`: honest DESK_UA, robots.txt per hop,
401/403/429/WAF is a site hold and a hard stop) -- never `requests` directly -- and nothing read
here is ever live input: the rows are ideas for the event lane, labelled IDEAS_ONLY.
"""

import json
import re
from datetime import datetime, timezone, timedelta
from collections.abc import Callable
from pathlib import Path
from typing import Any

try:
    from libs.data import polite_fetch
    from libs.data.polite_fetch import DESK_UA
except ImportError:  # run as a script: the repo root is not on the path
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[3]))
    from libs.data import polite_fetch
    from libs.data.polite_fetch import DESK_UA

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "intelligence" / "earnings"
OUT.mkdir(parents=True, exist_ok=True)

HEADERS = {"User-Agent": DESK_UA}
LEG = "earnings_miner"


def mine_earnings_calendar(get: Callable[..., Any] | None = None) -> list[dict]:
    """Fetch upcoming earnings dates for major companies that impact FX/indices (ideas only).
    `get` is the polite door (injectable for tests); a refusal stops the sweep and is recorded."""
    fetch = get or polite_fetch.get
    discoveries: list[dict] = []
    refused: dict[str, Any] | None = None
    # Use Yahoo Finance earnings calendar
    symbols_to_track = {
        "AAPL": "US500", "MSFT": "US500", "GOOGL": "US500",
        "AMZN": "US500", "NVDA": "US500", "META": "US500",
        "TSLA": "US500", "JPM": "US500", "GS": "US500",
        "V": "US500", "MA": "US500", "BAC": "US500",
    }

    for ticker, index in symbols_to_track.items():
        try:
            url = f"https://finance.yahoo.com/quote/{ticker}/"
            # live_input=False: an IDEAS_ONLY page read for ideas; robots and holds still decide
            resp = fetch(url, headers=HEADERS, timeout=10, retries=0, leg=LEG,
                         live_input=False)
            if resp.verdict or (resp.status is None and resp.error.startswith(
                    ("METHOD_BLOCKED", "NEEDS_KEY", "IDEAS_ONLY", "terms"))):
                # a robots refusal, a site hold (401/403/429/WAF) or a terms fence: HARD STOP,
                # no further page of this site this sweep, no other route
                refused = {"source": "earnings", "kind": "walled", "url": url,
                           "verdict": resp.verdict or "TERMS_FENCED",
                           "why": (resp.error or resp.verdict)[:240],
                           "terms_status": "IDEAS_ONLY"}
                break
            if resp.ok and resp.status == 200:
                text = resp.text
                # Look for earnings date
                earn_match = re.search(r'Earnings(?:Date|s).*?(\w+ \d+,?\s*\d{4})', text)
                if earn_match:
                    date_str = earn_match.group(1)
                    discoveries.append({
                        "source": "earnings",
                        "type": "earnings_date",
                        "ticker": ticker,
                        "index": index,
                        "date": date_str,
                        "symbols": [index],
                        "confidence": 0.3,
                        "description": f"{ticker} earnings on {date_str} - may impact {index}",
                        "url": url, "terms_status": "IDEAS_ONLY",
                    })
        except Exception:
            continue

    # A 200 WITH NOTHING IN IT IS NOT A QUIET SOURCE. Measured 2026-09-01: this host serves

    # the page but not the DATA -- the Earnings Date field is rendered client-side; the served 1.1MB carries 0 matches.

    # So an empty result here means the content moved behind client-side rendering, and

    # reporting silence would be indistinguishable from a genuinely uneventful day.

    # classify_row keys on `needs_selector_work` and counts this as a STUB: never a real

    # row, never an error, and never a healthy zero (L1.28a). It needs an API or a

    # rendering fetch, not another regex.

    if refused is not None:
        discoveries.append(refused)
    elif not discoveries:

        discoveries.append({"source": "earnings", "kind": "stub",

                            "needs_selector_work": True,

                            "host": "finance.yahoo.com/quote/<ticker>/",

                            "why": "fetched OK, content is client-side rendered"})

    return discoveries


def run_and_save() -> list[dict]:
    discoveries = mine_earnings_calendar()
    out_file = OUT / f"discoveries_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.json"
    try:
        from side_channels.discovery_io import write_discoveries
    except ModuleNotFoundError:
        from discovery_io import write_discoveries
    discoveries = write_discoveries(out_file, discoveries)
    print(f"earnings: {len(discoveries)} discoveries saved")
    return discoveries


if __name__ == "__main__":
    run_and_save()
