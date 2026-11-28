"""FENCED: UN Comtrade is REFUSED_ON_TERMS for this desk. This module fetches nothing.

The China knowledge graph (`libs/research/china_graph.py`, GAP_MAP 31) was built to take its
`china -> country` and `commodity -> country` weights from UN Comtrade's annual export tables.
The Auditor's ruling on #1155 (2026-11-14): the UN Comtrade licence agreement
(comtradeplus.un.org/en/license-agreement, section 5) prohibits automated browsing, downloading,
redistribution or commercial use without the UN's prior written permission, and the no-key
public API is given no exception. So, exactly as the desk treats FRED:

  * no request is sent to any Comtrade host from this repository -- there is no fetch code here;
  * no Comtrade-derived number (share, ratio or value) is committed or written on the box;
  * the graph runs on its labelled STRUCTURAL priors (ordinal weights with their published
    basis named), and `research/china_contagion.py` publishes the missed-growth line for the
    measured-weights gap in its own report.

What would lift the fence: written permission from the UN, or a lawful substitute source whose
terms are read and allow this use. Either goes through the same terms review before any code
reads it; this file is where that decision is recorded.

    python desks/mt5/research/china_exposure_ingest.py      # prints the fence, fetches nothing
"""
from __future__ import annotations

import sys
from typing import Any

STATUS = "REFUSED_ON_TERMS"
TERMS_URL = "https://comtradeplus.un.org/en/license-agreement"
WHY = ("UN Comtrade licence section 5: no automated browsing, downloading, redistribution or "
       "commercial use without prior written UN permission; the no-key API has no exception")
LIFTED_BY = ("written UN permission, or a lawful substitute source whose terms are read and "
             "allow automated retrieval and this use")


def refresh(**_: Any) -> dict[str, Any]:
    """The fence's answer, in the shape the leg reads. Sends nothing, writes nothing."""
    return {"status": STATUS, "refreshed": False, "n_measured": 0, "year": None,
            "terms": TERMS_URL, "why": WHY, "lifted_by": LIFTED_BY}


def main(argv: list[str] | None = None) -> int:
    d = refresh()
    print(f"china_exposure_ingest: {d['status']} -- {d['why']} ({d['terms']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
