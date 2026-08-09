#!/usr/bin/env python3
"""Build the scheduled-event calendar `libs/execution/event_guard.py` blocks on (R0276).

WHY A GENERATOR AND NOT A HAND-WRITTEN JSON. The dates are published in US Eastern wall-clock and
the guard compares against UTC. Typing the UTC stamps by hand means typing a daylight-saving
offset by hand eight times a year, and getting one wrong produces the exact failure the guard
exists to prevent: it would decline good entries on a quiet hour and wave trades through during
the actual repricing, while reporting healthy. The offsets here are COMPUTED from the IANA
database, so the only hand-entered facts are the calendar dates themselves and each one carries
its source.

*** WHAT IS DELIBERATELY NOT IN THIS FILE, AND WHY THAT IS THE POINT ***

R0276 named FOMC *and* the BLS CPI/NFP releases. Only FOMC is populated here. bls.gov returns
HTTP 403 to this host on every schedule path tried (news_release/cpi.htm, news_release/
2026_sched.htm, schedule/2026/home.htm), so the primary source could not be read, and the
secondary sources that carry the same dates are aggregators. The desk's rule is that a documented
failed search is a result and an undocumented assumption is not: writing CPI dates from an
aggregator would put unverified stamps into a guard whose entire value is that its stamps are
right. `pending_sources` in the output records what is missing, why, and where to get it, so the
gap is arguable rather than invisible.

THE CONSEQUENCE IS STATED HONESTLY: with FOMC alone the guard blocks ~8 windows a year rather
than ~30. It is a REAL guard over a VERIFIED subset, and adding CPI/NFP later only ever widens
it. A narrower true calendar is worth more than a wide invented one.

DATES ARE TENTATIVE AND THE FED SAYS SO: "Each meeting date is tentative until confirmed at the
meeting immediately preceding it." That is why the file carries `refresh_by` -- the schedule is
re-pulled annually, and a revised date is a diff.

    python scripts/build_event_calendar.py [--out PATH] [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from libs.ops.lawful import guard as _law_guard  # noqa: E402

_OUT = _ROOT / "data" / "event_calendar.json"

#: Where the FOMC schedule was read from, and what it said.
_FOMC_SOURCE = "federalreserve.gov/monetarypolicy/fomccalendars.htm"
#: Statement release: 2:00 p.m. Eastern for every regularly scheduled meeting. The press
#: conference follows at 2:30 p.m.; the STATEMENT is the repricing event, so 14:00 is the stamp.
_FOMC_LOCAL_TIME = (14, 0)
_EASTERN = ZoneInfo("America/New_York")

#: DECISION DAYS ONLY -- the SECOND day of each two-day meeting, which is when the statement is
#: released. The first day reprices nothing. Read from the Fed's own calendar page 2026-08-06;
#: both years are listed there, 2027 carrying the same tentative-until-confirmed caveat.
_FOMC_DECISION_DAYS = (
    # 2026: Jan 27-28, Mar 17-18*, Apr 28-29, Jun 16-17*, Jul 28-29, Sep 15-16*,
    #       Oct 27-28, Dec 8-9*   (* = with a Summary of Economic Projections)
    "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17",
    "2026-07-29", "2026-09-16", "2026-10-28", "2026-12-09",
    # 2027: Jan 26-27, Mar 16-17*, Apr 27-28, Jun 8-9*, Jul 27-28, Sep 14-15*,
    #       Oct 26-27, Dec 7-8*
    "2027-01-27", "2027-03-17", "2027-04-28", "2027-06-09",
    "2027-07-28", "2027-09-15", "2027-10-27", "2027-12-08",
)

#: Named, dated, and pointed at the primary source -- so "we never got round to it" and "the
#: source refused us" stay distinguishable, and the next run inherits the resolution either way.
_PENDING = [
    {"series": "CPI", "agency": "BLS", "impact": "high",
     "release_local": "08:30 America/New_York",
     "source": "bls.gov/schedule/news_release/cpi.htm",
     "why_absent": "bls.gov returned HTTP 403 to this host on every schedule path tried "
                   "2026-08-06; dates from aggregators are not verified stamps and were "
                   "refused rather than written into a guard whose value is that its stamps "
                   "are right"},
    {"series": "Employment Situation (NFP)", "agency": "BLS", "impact": "high",
     "release_local": "08:30 America/New_York",
     "source": "bls.gov/schedule/news_release/empsit.htm",
     "why_absent": "same 403 as CPI"},
]


def _utc_stamp(day: str, hh: int, mm: int) -> str:
    """Eastern wall-clock -> UTC, with the DST offset taken from the IANA database, not typed.

    Eight of these a year straddle the March and November transitions; a hand-typed offset is
    wrong for half the year and silently so.
    """
    local = datetime.fromisoformat(f"{day}T{hh:02d}:{mm:02d}:00").replace(tzinfo=_EASTERN)
    return local.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%SZ")


def build() -> dict[str, Any]:
    hh, mm = _FOMC_LOCAL_TIME
    events = [
        {"utc": _utc_stamp(d, hh, mm),
         "name": "FOMC decision",
         "impact": "high",
         "local": f"{d} {hh:02d}:{mm:02d} America/New_York",
         "source": _FOMC_SOURCE}
        for d in _FOMC_DECISION_DAYS
    ]
    events.sort(key=lambda e: e["utc"])
    last = max(_FOMC_DECISION_DAYS)
    return {
        # The guard blocks past valid_through, so this is the honest end of the verified schedule
        # -- never a round number chosen to postpone the question.
        "valid_through": last,
        "refresh_by": f"{int(last[:4])}-01-31",
        "source": _FOMC_SOURCE,
        "generated": datetime.now(tz=ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generator": "scripts/build_event_calendar.py",
        "law": "R0276 -- a stop is a promise the book cannot keep across a scheduled repricing. "
               "Entries are DEFERRED inside the window, never cancelled; costs zero statistical "
               "power because nothing here judges whether an edge is real.",
        "note": "FOMC decision days only (the SECOND day of each two-day meeting, when the "
                "statement is released at 14:00 ET). Dates are tentative until confirmed at the "
                "preceding meeting -- re-pull annually; a revised date is a diff.",
        "pending_sources": _PENDING,
        "events": events,
    }


def refusal(doc: dict[str, Any]) -> str | None:
    """Why this calendar must NOT be written, or None if it is fit to ship.

    A REAL refusal path, not vocabulary. The guard reading this file blocks when it is empty, so
    an empty write is merely useless -- but a file with a malformed or non-monotonic stamp is
    WORSE THAN NO FILE: it would clear a window that is actually a repricing while reporting
    healthy, which is the precise failure the whole organ exists to prevent. Better to leave the
    last good calendar in place and exit loud.
    """
    events = doc.get("events") or []
    if not events:
        return ("REFUSED: no events built -- an empty calendar is INCOMPLETE, and writing it "
                "would replace a good calendar with one that blocks every entry")
    stamps = [e.get("utc") for e in events]
    if any(not isinstance(s, str) or not s.endswith("Z") for s in stamps):
        return ("REFUSED: a stamp is UNPARSEABLE or not UTC -- a wrong offset clears the very "
                "window it exists to block")
    if stamps != sorted(stamps):
        return "REFUSED: events are not in ascending UTC order -- the writer is INCOMPLETE"
    if len(set(stamps)) != len(stamps):
        return "REFUSED: DUPLICATE event stamps -- the source list has been edited by hand"
    return None


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=str(_OUT))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    doc = build()
    bad = refusal(doc)
    if bad is not None:
        print(bad, file=sys.stderr)
        return 2
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2) + "\n", "utf-8")

    if args.json:
        print(json.dumps(doc, indent=2))
    else:
        print(f"event calendar -> {out}: {len(doc['events'])} high-impact event(s), "
              f"valid through {doc['valid_through']}, "
              f"{len(doc['pending_sources'])} series still UNPOPULATED "
              f"({', '.join(p['series'] for p in doc['pending_sources'])})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
