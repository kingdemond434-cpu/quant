"""SPDR GLD physical holdings: BLOCKED_ON_TERMS (no network path).

spdrgoldshares.com's terms allow "personal, non-commercial use" only and forbid
access "other than using the Website's navigational structure" (re-read
2026-11-17), so the desk never downloads GLD_US_holdings.xlsx. The same verdict
sits in alt_proxies.MACRO_FLOW_TERMS (us_spdr_gld_holdings). This module keeps
its name so data_scout's pointer and the component registry resolve, and it
says why it fetches nothing.
"""

from __future__ import annotations

import json

GLD_XLSX = "https://www.spdrgoldshares.com/usa/assets/uploads/GLD_US_holdings.xlsx"

BLOCKED_ON_TERMS = (
    "spdrgoldshares.com terms: personal, non-commercial use only; no access other "
    "than the website's navigational structure"
)

MISSED_GROWTH = {
    "mechanism": "gld_terms_refusal",
    "what_is_lost": "GLD daily physical holdings flow as a conditioner for XAUUSD/XAGUSD",
    "size": "UNMEASURED",
    "stand_in": "none; CFTC COT metals positioning remains the flow read",
    "reopens_when": "SPDR grants written permission for automated retrieval",
}


def status() -> dict[str, object]:
    return {"source": GLD_XLSX, "status": "BLOCKED_ON_TERMS",
            "why": BLOCKED_ON_TERMS, "missed_growth": MISSED_GROWTH}


def main() -> int:
    print(json.dumps(status(), indent=2))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
