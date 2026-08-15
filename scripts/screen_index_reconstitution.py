#!/usr/bin/env python3
"""STAGE-A RUNNER: index reconstitution flow (census gap #1, score 0.4800, NO-CANDIDATE).

The entire pre-registration -- mechanism, three constructions, horizons, alignment rule, benchmark,
multiplicity charge and kill criteria -- lives in the module docstring of
`libs/research/index_reconstitution` and was written before a single event was fetched. This file
only wires it to disk. It holds no threshold and performs no analysis, so there is nothing here to
tune after seeing a result.

**IT EXISTS BECAUSE THE SCREEN WITHOUT IT WAS AN ORPHAN.** `libs/research/index_reconstitution` was
committed with a full test suite and NO IMPORTER -- the desk's own "built but never runs" class
(III.16), caught by `max_audit.check_unwired_modules` on the same day it was written. A module with
green tests and no caller produces exactly as much E[log W] as not having been written, and takes
longer. That the checker caught it within the hour is the checker working; that it happened at all
is worth recording where the next screen author will read it.

**THE EVENT FEED IS NOT BUILT AND THIS SAYS SO EVERY RUN.** `data/index_reconstitution_events.json`
has no collector yet: index methodology documents and constituent lists are free and public, and
nobody has fetched them. So this runs daily and reports UNMEASURED with the missing input NAMED,
which is the state that gets an absent collector built. A screen that only runs once the data
arrives is a screen nobody remembers to run.

    python scripts/screen_index_reconstitution.py [--json]
"""

from __future__ import annotations

# PATH BOOTSTRAP. `python scripts/x.py` puts scripts/ on sys.path, NOT the repo root.
import sys as _sys
from pathlib import Path as _P

if str(_P(__file__).resolve().parent.parent) not in _sys.path:
    _sys.path.insert(0, str(_P(__file__).resolve().parent.parent))

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from libs.research.index_reconstitution import ReconEvent, run_screen

_ROOT = Path(__file__).resolve().parent.parent
_EVENTS = _ROOT / "data/index_reconstitution_events.json"
_OUT = _ROOT / "reports/axis_screens/index_reconstitution.json"


def _events() -> tuple[list[ReconEvent], str]:
    """Published index changes, or a NAMED reason there are none.

    A ROW THAT WILL NOT PARSE IS DROPPED AND COUNTED, never coerced. An effective date that reads
    as earlier than its announcement is a parsing error in a methodology document; swapping the
    two, or taking the absolute window, would invent an event that nobody published.
    """
    try:
        doc = json.loads(_EVENTS.read_text("utf-8"))
    except (OSError, ValueError) as exc:
        return [], (
            f"{_EVENTS} unreadable ({type(exc).__name__}) -- there is NO COLLECTOR for this feed "
            "yet. The census records the data as FREE-ACQUIRABLE: index methodology documents "
            "publish announcement and effective dates, and constituent lists are published before "
            "and after each review. Nobody has fetched them. That is a collection gap, not a kill")
    rows = doc.get("events") if isinstance(doc, dict) else doc
    out, bad = [], 0
    for r in rows or []:
        if not isinstance(r, dict):
            bad += 1
            continue
        try:
            ev = ReconEvent(
                symbol=str(r["symbol"]).upper(), index_name=str(r.get("index", "?")),
                announced_at=datetime.fromisoformat(str(r["announced_at"])),
                effective_at=datetime.fromisoformat(str(r["effective_at"])),
                direction=int(r["direction"]),
                weight_change=float(r.get("weight_change", 0.0) or 0.0))
        except (KeyError, TypeError, ValueError):
            bad += 1
            continue
        if ev.valid:
            out.append(ev)
        else:
            bad += 1
    return out, f"{len(out)} usable event(s) from {_EVENTS}, {bad} row(s) dropped as unparseable"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    from scripts.build_daily_panel import load_panel

    events, why_events = _events()
    panel = load_panel()
    report: dict[str, Any] = run_screen(events, panel)
    report["events_source"] = why_events
    report["panel_symbols"] = len(panel)
    report["updated"] = datetime.now(tz=UTC).isoformat()
    if not events:
        report.setdefault("missing_inputs", []).append(why_events)
    if not panel:
        report.setdefault("missing_inputs", []).append(
            "daily price panel absent -- run scripts/build_daily_panel.py")

    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(report, indent=1) + "\n", "utf-8")

    if args.json:
        print(json.dumps(report, indent=1))
        return 0
    print(f"index-reconstitution: status={report.get('status')} "
          f"verdict={report.get('verdict')} events={report['n_events_valid']} "
          f"panel={report['panel_symbols']} symbol(s)")
    print(f"  {report.get('why', '')}")
    for miss in report.get("missing_inputs", []):
        print(f"  MISSING: {miss}")
    print(f"-> {_OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
