"""CME margin-change events on the forced_flow channel, fenced on CME's own terms.

THE MECHANISM (build check row 126). When a clearing house raises the performance bond on a
contract, every leveraged holder who is already near the line must post cash or cut size by the
effective date. That is a forced flow with a published trigger, so a dated margin-change cell
for gold (COMEX GC), crude (NYMEX CL, BZ) and the index futures (ES, NQ, YM) would feed the
forced_flow channel directly.

WHY NOTHING IS FETCHED. CME publishes those changes as clearing advisories on cmegroup.com, and
CME's terms were read again on 2026-11-18 (the source was already refused in #732):

  * CME DATA TERMS OF USE (``/trading/market-data-explanation-disclaimer.html``, last updated
    2023-09-07) prohibit "use of any Web browsers (other than generally available third-party
    browsers), engines, scripts, software, spiders, robots" "to navigate, access, copy in bulk,
    retrieve, harvest, index, search or analyze any portion of the Website", including "through
    framing or systematic retrieval to create collections, compilations, databases or
    directories", and say "You may access content only for your personal use for non-commercial
    purposes."
  * CME WEBSITE TERMS OF USE (``/tools-information/cme-website-terms-of-use.html``, last updated
    2025-01-31) s12 grants only "a personal, nonexclusive, limited, revocable, non-transferable,
    non-sublicensable license to use the Website", and the holder agrees "not to sell, copy,
    distribute, or create derivative works based on the Website".
  * robots.txt names ``User-agent: Python-urllib/1.17`` with ``Disallow: /``. Robots that allow a
    path never override terms that refuse the use, and here the robots file refuses as well.

A dated event cell kept in a desk database and traded on is a "systematic retrieval to create
collections ... databases" and a commercial use. So the source is TERMS_BLOCKED, cmegroup.com is
on ``libs/data/refused_hosts.py``, and this organ publishes the fence and the cell CONTRACT, with
zero cells. It never builds a request.

WHAT A CONSUMER READS. ``family_forced_flow.py`` is money path and is not edited here. The state
it can read later is ``reports/CME_MARGIN_EVENTS.json``: ``status``, ``cells`` (empty while
blocked) and ``cell_schema``, the exact row shape a lawful source would fill. Wiring that reader
is backlog work for the money-path owner, and it waits on a terms-clean source first.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.data.refused_hosts import refusal  # noqa: E402

OUT: Path = DESK / "reports" / "CME_MARGIN_EVENTS.json"
CHANNEL = "forced_flow"
STATUS = "TERMS_BLOCKED"
TERMS_READ_AT = "2026-11-18"

#: Where the advisories live. Named so the fence can be checked against the refused-host list;
#: never requested.
ADVISORY_ROOT = "https://www.cmegroup.com/notices/clearing/"

#: The exact clauses that settle the refusal, as read on TERMS_READ_AT.
TERMS: tuple[dict[str, str], ...] = (
    {"document": "CME Data Terms of Use",
     "url": "https://www.cmegroup.com/trading/market-data-explanation-disclaimer.html",
     "last_updated": "2023-09-07",
     "clause": ("use of any Web browsers (other than generally available third-party browsers), "
                "engines, scripts, software, spiders, robots ... to navigate, access, copy in "
                "bulk, retrieve, harvest, index, search or analyze any portion of the Website "
                "... through framing or systematic retrieval to create collections, "
                "compilations, databases or directories"),
     "use_clause": ("You may access content only for your personal use for non-commercial "
                    "purposes.")},
    {"document": "CME Website Terms of Use, s12 Proprietary Rights",
     "url": "https://www.cmegroup.com/tools-information/cme-website-terms-of-use.html",
     "last_updated": "2025-01-31",
     "clause": ("CME grants to you a personal, nonexclusive, limited, revocable, "
                "non-transferable, non-sublicensable license to use the Website. Except as "
                "expressly authorized by CME, you agree not to sell, copy, distribute, or create "
                "derivative works based on the Website, in whole or in part.")},
)

ROBOTS: dict[str, str] = {
    "url": "https://www.cmegroup.com/robots.txt",
    "read_at": TERMS_READ_AT,
    "reading": ("User-agent: Python-urllib/1.17 -> Disallow: / (whole site). The * group "
                "disallows /clearing/ and /market-data/ sub-paths but not /notices/. An allowed "
                "path never overrides refusing terms."),
}

#: What the cells would key on: MT5 symbol -> the CME contract whose margin moves it.
TARGETS: dict[str, str] = {
    "XAUUSD": "COMEX GC (gold)",
    "XTIUSD": "NYMEX CL (WTI crude)",
    "XBRUSD": "NYMEX BZ (Brent last-day financial)",
    "US500": "CME ES (E-mini S&P 500)",
    "NAS100": "CME NQ (E-mini Nasdaq-100)",
    "US30": "CBOT YM (E-mini Dow)",
}

#: The row shape a lawful source fills. This is the contract a forced_flow reader codes against.
CELL_SCHEMA: dict[str, str] = {
    "symbol": "MT5 symbol from TARGETS",
    "contract": "exchange contract code",
    "advisory_date": "YYYY-MM-DD the change was announced (knowable_at)",
    "effective_date": "YYYY-MM-DD the new requirement applies (the forced-flow date)",
    "direction": "raise | cut",
    "pct_change": "maintenance margin change, percent",
    "channel": CHANNEL,
    "source": "the lawful source the row came from",
}

#: What the fence costs, stated rather than hidden (GROWTH GOVERNANCE: every veto bills its loss).
MISSED_GROWTH: str = (
    "No dated margin-change cells reach forced_flow for gold, crude or the US index CFDs, so a "
    "deleveraging window after a CME performance-bond raise is unconditioned. Value UNMEASURED: "
    "no event series exists to price it. Unblock with CME's written consent, a licensed feed, "
    "or a terms-clean secondary source that republishes the advisories under a reuse licence.")


def state(now: datetime | None = None) -> dict[str, Any]:
    """The fence as a readable state. Never contacts any host."""
    now = now or datetime.now(UTC)
    host_refusal = refusal(ADVISORY_ROOT)
    return {
        "organ": "cme_margin_events",
        "generated_at": now.isoformat(timespec="seconds"),
        "channel": CHANNEL,
        "status": STATUS,
        "source": {"id": "cme_performance_bond_advisories", "owner": "CME Group",
                   "root": ADVISORY_ROOT, "terms": list(TERMS), "robots": ROBOTS,
                   "terms_read_at": TERMS_READ_AT,
                   "refused_host": host_refusal or "NOT_LISTED"},
        "fetched": 0,
        "targets": TARGETS,
        "cells": [],
        "cell_schema": CELL_SCHEMA,
        "consumer": ("family_forced_flow (money path) does not read this yet; wiring is backlog "
                     "work and waits on a terms-clean source"),
        "missed_growth": MISSED_GROWTH,
        "verdict": ("TERMS_BLOCKED: 0 cells, a gap and not a zero"
                    if host_refusal else
                    "FENCE_INCOMPLETE: cmegroup.com is missing from refused_hosts"),
    }


def write(out: Path = OUT, now: datetime | None = None) -> dict[str, Any]:
    doc = state(now)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, out)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)
    doc = write(args.out)
    print(json.dumps({"status": doc["status"], "cells": len(doc["cells"]),
                      "verdict": doc["verdict"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
