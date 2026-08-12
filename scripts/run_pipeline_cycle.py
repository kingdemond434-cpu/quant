#!/usr/bin/env python3
"""ONE CYCLE, DEPENDENCY-ORDERED -- the whole research-to-capital chain in about six seconds.

WHY THIS EXISTS RATHER THAN MORE CRON LINES. Every stage below was already scheduled, each at its
own hand-picked minute, and TWO OF THEM WERE IN THE WRONG ORDER. Neither failure was visible in
any log -- both organs ran, both exited 0, both reported success:

  * `finalize_axis_screens` ran at 07:08 and the vol-risk-premium screen at 10:37. So the screen
    wrote raw verdicts that were not CORRECTED until 07:08 the NEXT DAY, and the spawner -- which
    admits only on `verdict_adjusted` -- could not see them. The 11:05 spawner pass I added to cut
    latency was reading corrections computed BEFORE the screen it was meant to catch. It bought
    nothing at all for that axis.
  * `run_slot_retirement` ran at 11:45, forty minutes AFTER the last spawner pass. A slot freed by
    a retirement therefore sat empty until 08:45 the following morning: twenty-one hours of the
    desk's scarcest resource, idle, with twenty-six survivors queued for it.

Cron minutes are a terrible place to encode a dependency graph. You cannot see the ordering by
reading the file, nothing checks it, and every future edit is another chance to invert one. So the
order lives HERE, in one list, in the order the data actually flows -- and a test reads that list.

THE MEASURED COST OF THE ENTIRE CHAIN IS 6.5 SECONDS. finalize 0.4s, forward 1.1s, liveness 1.5s,
retire 1.4s, spawn 1.0s, actuate 1.0s, publish 0.1s. All pure local CPU: no model call, no venue
call, no credit spent. There was never a throughput reason for any of it to be daily -- the
schedule was inherited from when each organ was built alone, and nothing revisited it once they
formed a chain.

WHAT RUNS EVERY CYCLE, and why in this order:

  1. finalize_axis_screens   raw screen verdicts -> corrected. Nothing downstream may read a raw
                             verdict, so this is always first.
  2. run_paper_sleeve_forward  observe accrual on every standing clock. Before retirement, so a
                             clock is judged on its freshest evidence rather than yesterday's.
  3. check_slot_liveness     WHY each clock is or is not breathing. Before retirement, because it
                             is the evidence retirement acts on.
  4. run_slot_retirement     release slots held by clocks that cannot accrue. BEFORE the spawner,
                             which is the whole point -- a freed slot is claimed in the same cycle
                             rather than the next morning.
  5. run_paper_sleeve_spawner  corrected survivors -> paper sleeves, into whatever slots are free.
  6. run_promotion_actuator  the gate's verdict -> what real capital may do.
  7. publish_pipeline        the dashboard, last, so it shows the state after everything moved.

THE FORWARD OBSERVER IS RATE-LIMITED AND NOTHING ELSE IS. It APPENDS an observation row per run;
at a 15-minute cycle that is 96 rows per sleeve per day describing sources that regenerate at most
daily -- a ledger of the observer's cadence rather than of the desk's evidence. It runs at most
hourly, and the skip is reported rather than silent. Every other stage is a pure recompute whose
output depends only on current state, so running it more often costs milliseconds and can only
make the desk fresher.

SPEED MUST NOT ERODE A SAFETY PROPERTY, and it nearly did here. The promotion actuator's
confirmation hold was `CONFIRM_RUNS = 2` -- correct only because the actuator happened to run
daily. Moving to a 15-minute cycle would have turned two days of required agreement into THIRTY
MINUTES, with no edit to the safety logic and nothing to notice. It is `CONFIRM_HOLD_H` now, in
wall-clock hours, so cadence and safety are independent.

A STAGE THAT FAILS DOES NOT STOP THE CYCLE. Each is independently useful and independently
idempotent; skipping the rest because one screen was mid-write would turn a transient into an
outage. Failures are recorded per stage and the cycle exits non-zero if any failed, so a
persistently broken stage is visible without costing the others their run.

    python scripts/run_pipeline_cycle.py [--json] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

OUT = "data/pipeline_cycle.json"

#: THE DEPENDENCY ORDER. (script, args, why it sits here). Read top to bottom, this is the path a
#: discovery takes from a raw screen verdict to a position size. A test asserts the sequence.
STAGES: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("finalize_axis_screens.py", (),
     "raw verdicts -> corrected. Nothing downstream may read a raw verdict"),
    ("run_paper_sleeve_forward.py", (),
     "observe accrual before anything judges a clock on it"),
    ("check_slot_liveness.py", ("--page",),
     "why each clock is or is not breathing -- the evidence retirement acts on"),
    ("run_slot_retirement.py", (),
     "release slots that cannot accrue BEFORE the spawner, so a freed slot is claimed this cycle"),
    ("run_paper_sleeve_spawner.py", (),
     "corrected survivors -> paper sleeves, into whatever slots are now free"),
    ("run_promotion_actuator.py", (),
     "the gate's verdict -> what real capital may do"),
    ("publish_pipeline.py", (),
     "the dashboard, last, so it shows the state after everything moved"),
)

#: The one stage that APPENDS rather than recomputes, and therefore the one whose cadence is
#: bounded by what it is measuring rather than by how fast it can run.
_APPEND_ONLY = "run_paper_sleeve_forward.py"
_FORWARD_LEDGER = "data/paper_sleeve_forward.jsonl"
FORWARD_MIN_GAP_H = 1.0

#: Per-stage ceiling. Generous against a 1.5s worst case -- this is a hang guard, not a budget.
STAGE_TIMEOUT_S = 600


def _ledger_age_h(root: Path) -> float | None:
    try:
        p = root / _FORWARD_LEDGER
        return (datetime.now(tz=UTC).timestamp() - p.stat().st_mtime) / 3600.0
    except OSError:
        return None


def run(root: Path | None = None, *, dry_run: bool = False) -> dict[str, Any]:
    base = root or _ROOT
    started = datetime.now(tz=UTC)
    t0 = time.monotonic()
    rows: list[dict[str, Any]] = []

    for script, args, why in STAGES:
        if script == _APPEND_ONLY:
            age = _ledger_age_h(base)
            if age is not None and age < FORWARD_MIN_GAP_H:
                # SKIPPED, AND SAID SO. A silent skip is indistinguishable from a stage that ran
                # and found nothing, which is the exact ambiguity this pipeline keeps paying for.
                rows.append({"stage": script, "status": "SKIPPED-RATE-LIMIT", "seconds": 0.0,
                             "why": f"observation ledger is {age * 60:.0f} min old; this stage "
                                    f"APPENDS a row per run and its sources regenerate at most "
                                    f"daily, so it runs at most every {FORWARD_MIN_GAP_H:g}h. "
                                    "Not a failure and not an absence of evidence."})
                continue
        if dry_run:
            rows.append({"stage": script, "status": "DRY-RUN", "seconds": 0.0, "why": why})
            continue

        s0 = time.monotonic()
        try:
            r = subprocess.run([sys.executable, f"scripts/{script}", *args],
                               cwd=base, capture_output=True, text=True, timeout=STAGE_TIMEOUT_S)
            rc, tail = r.returncode, (r.stderr or r.stdout or "").strip().splitlines()
        except subprocess.TimeoutExpired:
            rc, tail = 124, [f"timed out after {STAGE_TIMEOUT_S}s"]
        except OSError as exc:
            rc, tail = 127, [f"{type(exc).__name__}: {exc}"]
        rows.append({
            "stage": script, "status": "OK" if rc == 0 else f"FAILED rc={rc}",
            "seconds": round(time.monotonic() - s0, 2), "why": why,
            "detail": " | ".join(tail[-3:])[:400] if rc != 0 else "",
        })

    failed = [r for r in rows if str(r["status"]).startswith("FAILED")]
    doc = {
        "generated_utc": started.isoformat(timespec="seconds"),
        "seconds_total": round(time.monotonic() - t0, 2),
        "n_stages": len(rows), "n_failed": len(failed),
        "stages": rows,
        "order_law": "the sequence is a DEPENDENCY GRAPH, not a preference. Two orderings were "
                     "inverted while each stage lived on its own cron minute -- finalize ran "
                     "before the screen it corrected, and retirement ran after the spawner that "
                     "needed the slot. Both organs exited 0 the whole time.",
        "isolation_law": "a failed stage never stops the rest. Each is independently useful and "
                         "idempotent; skipping the chain because one screen was mid-write would "
                         "turn a transient into an outage.",
        "speed_law": "every stage is pure local CPU -- no model, no venue, no credit. Running the "
                     "cycle more often costs milliseconds. The ONE thing it must not shorten is "
                     "the promotion hold, which is why that is wall-clock hours and not a run "
                     "count.",
    }
    if not dry_run:
        p = base / OUT
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(doc, indent=1), "utf-8")
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="show the order; run nothing")
    args = ap.parse_args(argv)

    doc = run(dry_run=args.dry_run)
    if args.json:
        print(json.dumps(doc, indent=2))
    else:
        print(f"pipeline cycle: {doc['n_stages'] - doc['n_failed']}/{doc['n_stages']} ok "
              f"in {doc['seconds_total']}s")
        for r in doc["stages"]:
            # Only a real FAILURE gets flagged. A rate-limit skip is a correct
            # outcome, and marking it like a fault teaches the reader to ignore the mark.
            mark = "! " if str(r["status"]).startswith("FAILED") else "  "
            print(f"{mark}{r['seconds']:5.1f}s  {r['stage']:<32} {r['status']}")
            if r.get("detail"):
                print(f"           {r['detail'][:160]}")
    return 1 if doc["n_failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
