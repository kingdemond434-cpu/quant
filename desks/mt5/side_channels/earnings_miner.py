"""Earnings-calendar miner: BLOCKED_ON_TERMS (2026-11-18).

This channel used to read ``finance.yahoo.com/quote/<ticker>/`` under a spoofed desktop-Chrome
User-Agent to scrape the next earnings date of twelve US mega-caps (mapped to US500). Both halves
broke the desk's fetch law: Yahoo's terms s2(d)(9) refuse automated collection without express
prior permission (``libs/data/refused_hosts.py``), and no desk fetcher may impersonate a browser
(``libs/data/honest_ua.py``). The fetch is gone; the channel stays registered in
``run_all_miners`` and emits one labelled stub row per pass, so its absence is visible as a held
route with a missed_growth line rather than read as a quiet day (L1.28a).

The allowed substitute already in the repository is ``research/alpha_capture.py`` source
``sec_8k_guidance``: SEC EDGAR full-text search over 8-K filings (the form an earnings release is
furnished on), run hourly as the ``alpha_capture`` leg of ``research/hourly_cycle.py`` under the
SEC's declared-contact User-Agent. No new scraper is added here.
"""

from datetime import UTC, datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "intelligence" / "earnings"
OUT.mkdir(parents=True, exist_ok=True)

#: The refused route, named so the stub says exactly what is not being read.
REFUSED_ROUTE = "finance.yahoo.com/quote/<ticker>/"
BLOCKED_ON_TERMS = ("BLOCKED_ON_TERMS: Yahoo terms s2(d)(9) refuse automated collection without "
                    "express prior permission (libs/data/refused_hosts.py)")
MISSED_GROWTH = ("missed_growth: the scraped next-earnings dates of 12 US mega-caps (US500 "
                 "event-lane timing) are no longer read from Yahoo; 8-K earnings releases still "
                 "reach the desk through alpha_capture sec_8k_guidance (SEC EDGAR), so the gap is "
                 "the forward calendar date ahead of the filing, not the event itself.")
SUBSTITUTE = "desks/mt5/research/alpha_capture.py::sec_8k_guidance (SEC EDGAR 8-K full-text search)"


def mine_earnings_calendar() -> list[dict]:
    """One stub row, no request. ``kind: stub`` with ``needs_selector_work`` keeps the shape the
    compiler and lead schema already drop as operational bookkeeping (never evidence, never an
    error, never a healthy zero)."""
    return [{"source": "earnings", "kind": "stub",
             "needs_selector_work": True,
             "status": "BLOCKED_ON_TERMS",
             "host": REFUSED_ROUTE,
             "why": BLOCKED_ON_TERMS,
             "missed_growth": MISSED_GROWTH,
             "substitute": SUBSTITUTE}]


def run_and_save() -> list[dict]:
    discoveries = mine_earnings_calendar()
    out_file = OUT / f"discoveries_{datetime.now(UTC).strftime('%Y%m%d_%H%M')}.json"
    try:
        from side_channels.discovery_io import write_discoveries
    except ModuleNotFoundError:
        from discovery_io import write_discoveries
    discoveries = write_discoveries(out_file, discoveries)
    print(f"earnings: {len(discoveries)} discoveries saved (BLOCKED_ON_TERMS stub)")
    return discoveries


if __name__ == "__main__":
    run_and_save()
