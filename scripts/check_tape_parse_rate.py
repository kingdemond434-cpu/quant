#!/usr/bin/env python3
"""TAPE PARSE-RATE FENCE (R0529, L1.57/L1.60) -- a venue the reader cannot read must never look
like a venue that simply had nothing to say.

WHY THIS EXISTS, AND WHAT IT COST. `scripts/build_bars.py:trades_from` dropped an entry it could
not parse with a bare `continue`. Bybit labels its nested prints `price`/`time`/`size` and the
reader accepted only `p`/`T`/`v`, so it discarded 221,000 of 221,000 sampled entries -- the ENTIRE
bybit trade tape, 27% of `data/moat` -- and every consumer downstream saw a venue with no trades.
`build()` counted only SUCCESSES, so the artifact said `venues: {spot: ..., fut: ...}` and a
reader had no way to tell that from a quiet venue. Every bar, every moat screen and every verdict
computed over bybit rested on zero prints and looked like an honest data-poor null.

THE SECOND HALF, WHICH IS WHY A PARSE-RATE CHECK ALONE IS NOT ENOUGH. When the parse bug was
fixed the tape STILL never reached a bar: the per-symbol budget sliced a venue-major path sort
with `[-each:]`, so it took the alphabetically-last venue rather than the newest files, and
`bybit` < `fut` < `spot` put bybit permanently last in line. Measured 2026-08-19: 440 bybit files
on disk, ZERO budgeted. A fence that only watched parse rates would have reported a clean 100%
for a venue it was not reading at all -- absence of a venue is exactly as invisible as a silent
drop, so both are checked here.

STATUSES (exit 2 on everything except OK -- a gate, not a report; ALL live breaches are listed,
never just the headline):
  NO-ARTIFACT   data/build_bars.json absent or unreadable. Nothing can be measured.
  UNMEASURED    the artifact carries no `parse` block, so attempts were never counted. This is
                NOT a pass: an uncounted discard is the defect, not the absence of one (L1.28a).
  COLLAPSED     a venue parsed below PARSE_FLOOR of what it attempted. The reader is broken for
                that schema.
  VENUE-UNREAD  a venue has tape on disk and contributed ZERO attempted entries -- it was never
                budgeted. This is the R0378-inert-for-seven-days case.
  OK            every venue with tape on disk was read, and each parsed at or above the floor.

THE FLOOR IS SET WHERE A READER DEFECT LIVES, NOT WHERE NOISE DOES. A venue dropping more than
half of what it attempts is a schema mismatch, never bad luck; the measured rate on every venue
this desk records is 1.0000. `MIN_ENTRIES` keeps a handful of malformed lines in a nearly-empty
partition from firing it -- below that the honest answer is that the sample cannot decide, and
the venue is reported as UNJUDGED rather than passed.

    python scripts/check_tape_parse_rate.py [--report-only] [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.ops.fence_exit import fence_exit  # noqa: E402
from libs.ops.lawful import guard as _law_guard  # noqa: E402

REPORT = _ROOT / "data/build_bars.json"
OUT = _ROOT / "data/tape_parse_rate.json"

#: Below this share of ATTEMPTED entries actually parsed, the reader is broken for that venue's
#: schema. Not a tuning knob: a real venue parses at 1.0, and the defect this fence exists for
#: parsed at 0.0. Anything in between is already a loud finding.
PARSE_FLOOR = 0.50
#: Fewer attempted entries than this and the venue is UNJUDGED -- a sample too small to separate a
#: broken reader from a few corrupt lines. Refusing to grade is a real answer (L1.28a).
MIN_ENTRIES = 100

PASSING = ("OK",)


def _venues_on_disk(moat: Path) -> set[str]:
    """Venue directories that actually hold tape.

    A venue dir with no `*.jsonl.gz` under it is not evidence of a missing read -- there is
    nothing there to read. Counted rather than skipped silently (L1.60): the caller is told how
    many directories were examined to produce this set.
    """
    if not moat.is_dir():
        return set()
    out: set[str] = set()
    for vdir in sorted(p for p in moat.iterdir() if p.is_dir()):
        if next(vdir.glob("*/*.jsonl.gz"), None) is not None:
            out.add(vdir.name)
    return out


def build_report(report: Path = REPORT, moat: Path | None = None) -> dict[str, Any]:
    moat = (_ROOT / "data/moat") if moat is None else moat
    on_disk = _venues_on_disk(moat)
    base: dict[str, Any] = {
        "ts": datetime.now(tz=UTC).isoformat(),
        "law": "R0529 (L1.57 denominator / L1.60 attrition)",
        "source": str(report.relative_to(_ROOT)) if report.is_relative_to(_ROOT) else str(report),
        "venues_on_disk": sorted(on_disk),
        "parse_floor": PARSE_FLOOR, "min_entries": MIN_ENTRIES,
    }
    try:
        doc = json.loads(report.read_text("utf-8"))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return {**base, "status": "NO-ARTIFACT", "n_venues": 0, "venues": {}, "breaches": [],
                "detail": f"{base['source']} is absent or unreadable ({type(exc).__name__})",
                "next_action": "run scripts/build_bars.py -- nothing here can be measured without it"}

    parse = doc.get("parse")
    if not isinstance(parse, dict) or not parse:
        return {**base, "status": "UNMEASURED", "n_venues": 0, "venues": {}, "breaches": [],
                "detail": ("the artifact declares no `parse` block, so discarded entries were "
                           "never counted -- a 100% parse loss is still invisible"),
                "next_action": ("re-run scripts/build_bars.py on a build that passes "
                                "ParseAttrition into trades_from")}

    venues: dict[str, Any] = {}
    breaches: list[str] = []
    for name in sorted(set(parse) | on_disk):
        row = parse.get(name)
        entries = int(row.get("entries", 0)) if isinstance(row, dict) else 0
        parsed = int(row.get("parsed", 0)) if isinstance(row, dict) else 0
        rate = (parsed / entries) if entries else None
        if name in on_disk and entries == 0:
            verdict = "UNREAD"
            breaches.append(
                f"{name}: tape on disk but ZERO entries attempted -- the builder never read it, "
                f"so its parse rate is unmeasured rather than clean")
        elif entries < MIN_ENTRIES:
            verdict = "UNJUDGED"
        elif rate is not None and rate < PARSE_FLOOR:
            verdict = "COLLAPSED"
            breaches.append(
                f"{name}: parsed {parsed}/{entries} = {rate:.4%} of attempted entries, below the "
                f"{PARSE_FLOOR:.0%} floor -- the reader does not understand this venue's schema")
        else:
            verdict = "OK"
        venues[name] = {"entries": entries, "parsed": parsed,
                        "dropped": (entries - parsed) if entries else 0,
                        "parse_rate": (None if rate is None else round(rate, 6)),
                        "on_disk": name in on_disk, "verdict": verdict}

    if any(v["verdict"] == "COLLAPSED" for v in venues.values()):
        status, detail = "COLLAPSED", "a venue parsed below the floor of what it attempted"
    elif any(v["verdict"] == "UNREAD" for v in venues.values()):
        status, detail = "VENUE-UNREAD", "a venue with tape on disk contributed no attempted entries"
    else:
        status = "OK"
        detail = (f"{sum(1 for v in venues.values() if v['verdict'] == 'OK')} venue(s) read and "
                  f"parsing at or above the floor")
    return {**base, "status": status, "n_venues": len(venues), "venues": venues,
            "breaches": breaches, "detail": detail,
            "next_action": ("none" if status == "OK" else
                            "fix the reader or the budget -- never the floor (the floor is what "
                            "makes a silent drop visible)")}


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = build_report()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rep, indent=2) + "\n", "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"tape parse rate (R0529): {rep['status']} -- {rep['detail']}")
        for name, v in rep["venues"].items():
            rate = "unmeasured" if v["parse_rate"] is None else f"{v['parse_rate']:.4%}"
            print(f"  {name:10s} {v['verdict']:9s} parsed {v['parsed']}/{v['entries']} = {rate}")
        for b in rep["breaches"]:
            print(f"  BREACH: {b}")
        print(f"  next: {rep['next_action']}")
    if args.report_only:
        return 0
    return fence_exit(rep["status"], PASSING, scanned=rep["n_venues"], of="recorded venues")


if __name__ == "__main__":
    sys.exit(main())
