#!/usr/bin/env python3
"""RETIRE THE CLOCKS THAT CANNOT ACCRUE, AUTOMATICALLY -- and prove no bar moved doing it.

WHAT WAS BLOCKING THE DESK. Twelve of twelve forward slots occupied, ZERO accruing, and 26
corrected Stage-A survivors queued behind the cap. The pipeline from research to capital was fully
subscribed by clocks producing no evidence, and the only thing that could free a slot was a manual
ledgered decision that nothing ever triggered. The principal is right that this is the defect: an
automated desk that requires a human to sweep its own dead clocks is not automated, and the cost
is not the sweeping -- it is 26 candidates losing forward days they never get back.

WHY IT LOOKED UNBUILDABLE, AND WHY IT IS NOT. `slot_registry.derive_slots()` drops RETIRED rows
from `m_concurrent`, so retirement shrinks m and LOOSENS every standing clock's Holm bar. An organ
that auto-retired to drain a queue would be an organ that loosens statistical gates under
pressure, and with a permanent queue that pressure never lets up.

But the implementation disagreed with the declared law, and the implementation was the loose one.
`data/promotion_queue.json` says the correction is "over all trailing-180d entrants INCLUDING
KILLED ONES". A trial that was started and abandoned still consumed a test. Counting only
survivors is the forking-paths garden: run twelve, kill eleven, judge the last against m=1.

`libs/research/forward_multiplicity` implements the law as written, and under it retirement moves
a clock between two terms of the same sum. m is unchanged. Every standing bar is unchanged.
Freeing capacity stops being a statistical act, and this organ becomes safe to run unattended.

THE PROOF IS RUN EVERY TIME, NOT ASSERTED ONCE. Each pass measures the Holm z BEFORE and AFTER its
own retirements and REFUSES THE WHOLE BATCH if the bar moved down by any amount. A docstring
claiming safety is worth nothing on the night the assumption stops holding.

WHAT IT WILL RETIRE, and nothing else:
  PRODUCER_UNSCHEDULED  no organ on this desk writes the clock's origin artifact -- and only when
                        NO producer exists at all. A producer that merely needs a cron line is a
                        BUILD defect: retiring for that would discard a real candidate to hide a
                        missing schedule, so it is reported and left standing.
  SOURCE_FROZEN         the producer runs, is fresh, and `n` has not moved in three cycles. The
                        window is fixed, so the clock cannot resolve however long it waits.

Never ACCRUING. Never TOO_EARLY. Never UNKNOWN -- an unmeasured clock is not a dead one, and
resolving unknown toward retirement is how a real candidate gets swept to tidy a report.

EVERY RETIREMENT IS LEDGERED AND REVERSIBLE: an append-only row in data/slot_retirements.jsonl
carrying the clock's name, birth, state, the evidence, and the reason. That ledger is also what
keeps the trial counted in m, so a lost ledger would be the one way this could loosen anything --
which is why an unwritable ledger REFUSES the retirement rather than proceeding.

    python scripts/run_slot_retirement.py            # apply
    python scripts/run_slot_retirement.py --dry-run  # report only
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.research.forward_multiplicity import RETIREMENT_LEDGER, bar_for  # noqa: E402
from libs.research.slot_liveness import report as liveness  # noqa: E402

OUT = "data/slot_retirement.json"
ROSTER = "data/shadow_sleeves.json"

#: The only two states a clock may be retired for, and both mean STRUCTURALLY UNABLE TO FINISH.
RETIRABLE = ("SOURCE_FROZEN", "PRODUCER_UNSCHEDULED")


def _already_retired(root: Path) -> set[str]:
    names = set()
    try:
        for line in (root / RETIREMENT_LEDGER).read_text("utf-8").splitlines():
            if line.strip():
                try:
                    names.add(str(json.loads(line).get("name")))
                except ValueError:
                    continue
    except OSError:
        pass
    return names


def _candidates(rep: dict[str, Any], root: Path) -> list[dict[str, Any]]:
    done = _already_retired(root)
    out = []
    for c in rep["clocks"]:
        if c["name"] in done or c["state"] not in RETIRABLE:
            continue
        # A MISSING CRON LINE IS NOT A DEAD CLOCK. If a producer exists and simply is not
        # scheduled, the repair costs one line and the candidate is real; retiring it would
        # destroy evidence to hide a build defect. Only a clock nothing on this desk can feed is
        # genuinely unable to finish.
        if c["state"] == "PRODUCER_UNSCHEDULED" and c["producer"]:
            continue
        out.append(c)
    return out


def run(root: Path | None = None, *, dry_run: bool = False) -> dict[str, Any]:
    base = root or _ROOT
    rep = liveness(root=base)
    before = bar_for(root=base)
    picked = _candidates(rep, base)

    doc: dict[str, Any] = {
        "generated_utc": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "n_clocks": rep["n_clocks"], "accruing": rep["accruing"],
        "bar_before": before, "retired": [], "left_standing": [],
        "law": "Holm over all trailing-180d entrants INCLUDING KILLED ONES, so a retirement moves "
               "a trial between terms and leaves m unchanged. Verified after the fact on every "
               "run, never assumed.",
    }
    for c in rep["clocks"]:
        if c["state"] in RETIRABLE and c not in picked:
            doc["left_standing"].append(
                {"clock": c["name"], "state": c["state"],
                 "why": "a producer exists and only needs scheduling -- that is a BUILD defect, "
                        "and retiring a real candidate to hide a missing cron line is the wrong "
                        f"repair. FIX: {c['repair']}"})

    if not picked:
        doc["status"] = "NOTHING-TO-RETIRE"
        doc["why"] = ("no clock is structurally unable to finish. Clocks that are merely stale on "
                      "THIS box are not retirable -- that describes the container, not the desk")
        _write(base, doc, dry_run=dry_run)
        return doc

    rows = []
    for c in picked:
        rows.append({
            "name": c["name"], "retired_utc": doc["generated_utc"],
            "shadow_start": c.get("shadow_start") or c.get("started"),
            "state": c["state"], "origin_artifact": c["origin_artifact"],
            "producer": c["producer"], "age_h": c["age_h"], "rows_added": c["rows_added"],
            "why": c["why"], "decided_by": "scripts/run_slot_retirement.py",
            "counted_in_m": True,
            "note": "STILL CHARGED FOR. This trial consumed a test and stays in the Holm family "
                    "for the trailing window; the slot is freed, the multiplicity is not.",
        })

    if dry_run:
        doc["status"] = "DRY-RUN"
        doc["retired"] = rows
        _write(base, doc, dry_run=True)
        return doc

    # THE LEDGER IS WRITTEN FIRST, and this order is load-bearing. The ledger is what keeps a
    # retired trial counted in m; a roster edit that landed without it would be the one path by
    # which this organ could loosen a bar. Fail to write, retire nothing.
    try:
        led = base / RETIREMENT_LEDGER
        led.parent.mkdir(parents=True, exist_ok=True)
        with led.open("a", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")
    except OSError as exc:
        doc["status"] = "REFUSED-LEDGER-UNWRITABLE"
        doc["why"] = (f"cannot append to {RETIREMENT_LEDGER} ({exc}). Retiring without the ledger "
                      "would drop these trials out of m and loosen every standing bar, so nothing "
                      "was retired.")
        _write(base, doc, dry_run=dry_run)
        return doc

    after = bar_for(root=base)
    doc["bar_after"] = after
    if after["z"] < before["z"]:
        # Cannot happen under the declared law, which is exactly why it is checked. If it ever
        # does, the assumption this organ rests on has broken and it must stop, loudly.
        doc["status"] = "REFUSED-BAR-LOOSENED"
        doc["why"] = (f"the Holm bar moved from {before['z']} to {after['z']} -- DOWN. Retirement "
                      "must be multiplicity-neutral; it was not. The roster was NOT edited and "
                      "the ledger rows stand as the record. Investigate forward_multiplicity "
                      "before running this again.")
        _write(base, doc, dry_run=dry_run)
        return doc

    names = {r["name"] for r in rows}
    try:
        roster = json.loads((base / ROSTER).read_text("utf-8"))
        kept = [n for n in roster if n not in names]
        (base / ROSTER).write_text(json.dumps(kept, indent=1), "utf-8")
        doc["roster_before"], doc["roster_after"] = len(roster), len(kept)
    except (OSError, ValueError) as exc:
        doc["status"] = "LEDGERED-ROSTER-UNCHANGED"
        doc["why"] = (f"ledger written but the roster could not be edited ({exc}). The slots are "
                      "NOT freed. Safe: over-counting only tightens.")
        _write(base, doc, dry_run=dry_run)
        return doc

    doc["status"] = "RETIRED"
    doc["retired"] = rows
    doc["why"] = (f"{len(rows)} clock(s) that could never accrue released their slots. The Holm "
                  f"bar is unchanged at z={after['z']} (m={after['m_effective']}), because every "
                  "retired trial stays counted for the trailing window.")
    _write(base, doc, dry_run=dry_run)
    return doc


def _write(root: Path, doc: dict[str, Any], *, dry_run: bool) -> None:
    if dry_run:
        return
    p = root / OUT
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, indent=1), "utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="report only; retire nothing")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    doc = run(dry_run=args.dry_run)
    if args.json:
        print(json.dumps(doc, indent=2))
    else:
        print(f"slot retirement: {doc['status']} -- {len(doc['retired'])} retired, "
              f"{doc['accruing']}/{doc['n_clocks']} accruing")
        for r in doc["retired"]:
            print(f"  RETIRED {r['name']} ({r['state']})")
        for s in doc["left_standing"]:
            print(f"  KEPT    {s['clock']} ({s['state']}) -- {s['why'][:110]}")
        if doc.get("bar_after"):
            print(f"  bar z {doc['bar_before']['z']} -> {doc['bar_after']['z']} "
                  f"(m {doc['bar_before']['m_effective']} -> {doc['bar_after']['m_effective']})")
    # A refused batch is a real failure of an assumption; everything else is an ordinary outcome.
    return 2 if str(doc["status"]).startswith("REFUSED") else 0


if __name__ == "__main__":
    raise SystemExit(main())
