#!/usr/bin/env python3
"""A SCHEDULED LEG WHOSE ARTIFACT HAS STOPPED MOVING IS RED -- by name, every hour.

THE CASE (row 72, measured 2026-11-03). `BREADTH_MANDATE.json` was last written 2026-10-29
16:35Z. The `empty_cluster_forcer` leg -- the organ that consumes it -- sat in hourly_cycle.py and
ran; the mandate's own writer was a fence in the rotating battery that timed out loading a
1.8M-cell docket inside a 150 s slice, and wrote only at its end. Five days of a frozen mandate,
no reader told. A scheduled leg is not a fresh artifact, and nothing on the desk compared the two
for this pair.

THE RULE. Each row below names a LEG and the artifact(s) it must refresh, with a max age (the
leg's cadence plus room for a missed pass). A row is:

    GREEN       the leg is scheduled and every artifact's own stamp is inside its max age
    RED         the leg is scheduled (a `_costed("<leg>"` literal in hourly_cycle.py) and an
                artifact is missing, unstamped-and-old, or older than its max age
    UNSCHEDULED the leg is not in the cycle source: also RED -- a contracted artifact with no
                clock is III.16
    UNMEASURED  the cycle source is unreadable here, so "scheduled" cannot be decided

RED exits 2 and UNMEASURED exits 3; neither is a declared verdict in `hourly_cycle.VERDICT_EXITS`,
so both record as `exit_code=N` and `scripts/check_silent_organs.py` names this leg, which pages.
The artifact's OWN stamp (`generated_utc` / `generated_at` / `at`) is preferred to its mtime: a
box checkout rewrites mtimes, the stamp is what the writer said.

    python scripts/check_leg_artifact_liveness.py
    python scripts/check_leg_artifact_liveness.py --json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DESK = ROOT / "desks" / "mt5"
CYCLE = DESK / "research" / "hourly_cycle.py"
MARKER = DESK / "data" / "sync_marker.json"
OUT = DESK / "reports" / "LEG_ARTIFACT_LIVENESS.json"

#: leg -> ((artifact relative to ROOT, max age in hours), ...). Add a row whenever a leg's
#: artifact is read by something that would decide on a stale copy without knowing.
CONTRACTS: dict[str, tuple[tuple[str, float], ...]] = {
    # the breadth mandate is written by the forcer leg every pass (before and after its plan)
    "empty_cluster_forcer": (("desks/mt5/reports/BREADTH_MANDATE.json", 6.0),
                             ("desks/mt5/reports/EMPTY_CLUSTER_FORCER.json", 6.0)),
    # the per-region forest yield report (row 75)
    "region_yield": (("desks/mt5/reports/REGION_YIELD.json", 3.0),),
}

STAMP_KEYS = ("generated_utc", "generated_at", "at", "updated_at", "written_at")
GREEN, RED, UNSCHEDULED, UNMEASURED = "GREEN", "RED", "UNSCHEDULED", "UNMEASURED"


def _parse(stamp: Any) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def artifact_age_h(path: Path, now: datetime) -> tuple[float | None, str]:
    """(age in hours, basis). None age means the artifact does not exist."""
    if not path.exists():
        return None, "missing"
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        doc = None
    if isinstance(doc, dict):
        for k in STAMP_KEYS:
            t = _parse(doc.get(k))
            if t is not None:
                return round((now - t).total_seconds() / 3600.0, 2), f"stamp `{k}`"
    try:
        mt = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
    except OSError:
        return None, "unreadable"
    return round((now - mt).total_seconds() / 3600.0, 2), "mtime (no stamp in the artifact)"


def scheduled_legs(cycle: Path | None = None) -> set[str] | None:
    """Legs with a `_costed("<leg>"` literal in the cycle source; None when unreadable."""
    try:
        text = (cycle or CYCLE).read_text(encoding="utf-8")
    except OSError:
        return None
    return set(re.findall(r'_costed\(\s*"([A-Za-z0-9_]+)"', text))


def check(*, now: datetime | None = None, root: Path | None = None,
          contracts: dict[str, tuple[tuple[str, float], ...]] | None = None,
          cycle: Path | None = None, marker: Path | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    base = root or ROOT
    legs = scheduled_legs(cycle)
    try:
        mk = json.loads((marker or MARKER).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        mk = {}
    rows: list[dict[str, Any]] = []
    for leg, arts in sorted((contracts or CONTRACTS).items()):
        last = mk.get(leg) if isinstance(mk, dict) else None
        art_rows = []
        for rel, max_h in arts:
            age, basis = artifact_age_h(base / rel, now)
            fresh = age is not None and age <= max_h
            art_rows.append({"path": rel, "max_age_h": max_h, "age_h": age, "basis": basis,
                             "fresh": fresh})
        stale = [a for a in art_rows if not a["fresh"]]
        if legs is None:
            verdict, why = UNMEASURED, f"{CYCLE} is unreadable: cannot tell whether {leg} runs"
        elif leg not in legs:
            verdict, why = UNSCHEDULED, (f"{leg} has no `_costed` literal in hourly_cycle.py: a "
                                         f"contracted artifact with no clock (III.16)")
        elif stale:
            worst = stale[0]
            verdict, why = RED, (f"{leg} is scheduled and {worst['path']} is "
                                 f"{'MISSING' if worst['age_h'] is None else str(worst['age_h']) + 'h old'}"
                                 f" against {worst['max_age_h']:g}h: the leg runs and its "
                                 f"artifact does not move")
        else:
            verdict, why = GREEN, f"{leg} scheduled and every artifact inside its max age"
        rows.append({"leg": leg, "verdict": verdict, "why": why, "artifacts": art_rows,
                     "last_marker_row": last if isinstance(last, dict) else None})
    red = [r["leg"] for r in rows if r["verdict"] in (RED, UNSCHEDULED)]
    unmeasured = [r["leg"] for r in rows if r["verdict"] == UNMEASURED]
    status = RED if red else (UNMEASURED if unmeasured else GREEN)
    return {"generated_utc": now.isoformat(timespec="seconds"), "status": status,
            "red": red, "unmeasured": unmeasured, "rows": rows,
            "rule": ("a scheduled leg whose contracted artifact is missing or older than its max "
                     "age is RED; an unscheduled contract is RED; an unreadable cycle source is "
                     "UNMEASURED, never GREEN (L1.28a)")}


def write(doc: dict[str, Any], out: Path | None = None) -> None:
    path = out or OUT
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    tmp.replace(path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    doc = check()
    write(doc)
    if args.json:
        print(json.dumps(doc, indent=1, default=str))
    else:
        print(f"leg artifact liveness: {doc['status']} ({len(doc['rows'])} contract(s))")
        for r in doc["rows"]:
            print(f"  {r['verdict']:11} {r['leg']:24} {r['why'][:120]}")
        print(f"  -> {OUT}")
    return {RED: 2, UNMEASURED: 3}.get(doc["status"], 0)


if __name__ == "__main__":
    sys.exit(main())
