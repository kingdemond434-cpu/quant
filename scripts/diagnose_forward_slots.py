#!/usr/bin/env python3
"""WHY IS THIS SLOT UNMEASURED -- named per slot, so the queue's bottleneck becomes a work item.

Measured on the box 2026-08-15: the forward cohort holds 13 slots against a cap of 12, ZERO free,
so a new candidate waits ~90 days for a seat before starting its own 90-day clock. Breadth is the
only route to a higher combined Sharpe, the queue is what rations breadth, and an unusable seat is
therefore the most expensive object on the desk.

The displacement plan already refuses to judge two of them:

    2 slot(s) UNMEASURED and therefore NOT reclaimed -- wrongly evicting destroys forward evidence
    that cannot be re-earned, while wrongly keeping costs a queue position. This is a MEASUREMENT
    DEFECT UPSTREAM, not a displacement decision.

That refusal is correct and it is also a dead end: it names the defect and stops. Nothing said
WHICH artifact was consulted, whether it existed, or which process was supposed to write it -- so
the item was unactionable and the seats stayed blocked. This answers exactly that, per slot.

**IT DIAGNOSES AND NEVER RECLAIMS.** No slot is retired, no registry written, no clock killed.
Turning "I cannot see this" into "therefore take it" is the one failure the displacement module
refuses by design, and a diagnostic that could act would reintroduce it one file over.

**AN UNSPAWNABLE CLOCK IS THE FINDING WORTH HAVING.** A name can be registered, charged its
multiplicity, and structurally unable to publish -- because whatever spawned it announced nothing
about where its rows live. That clock holds a seat forever and can never resolve, and it is
invisible unless something asks this question.

    python scripts/diagnose_forward_slots.py
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

_ROOT = Path(__file__).resolve().parent.parent
_OUT = Path("web/forward_slot_diagnosis.json")

#: Name fragment -> the process that spawns clocks like it, and where that process must announce.
#: A slot whose owner cannot be named is reported as ORPHAN, which is a stronger finding than an
#: unmeasured one: nothing is responsible for making it measurable.
_SPAWNERS: tuple[tuple[str, str, str], ...] = (
    ("conv_moat", "scripts/conversion_engine.py",
     "libs.research.clock_registry.register_owed(..., source='conversion_engine')"),
    ("full_sweep", "scripts/run_paper_sleeve_spawner.py",
     "data/paper_sleeve_forward.json, written by run_paper_sleeve_forward.py"),
    ("perpdex_funding", "scripts/screen_perpdex_funding.py",
     "libs.research.axis_screen.stage_a_screen(clock=...)"),
    ("cat|", "scripts/run_axis_shadows.py", "data/axis_shadow_state.json"),
)


def _owner(name: str) -> tuple[str, str]:
    for frag, script, where in _SPAWNERS:
        if frag in name:
            return script, where
    return "UNKNOWN", "nothing on this desk claims responsibility for publishing its accrual"


def _read(rel: str) -> Any | None:
    try:
        return json.loads((_ROOT / rel).read_text("utf-8"))
    except (OSError, ValueError):
        return None


def diagnose(slot: dict[str, Any]) -> dict[str, Any]:
    """One slot -> the artifact chain that was consulted, and the first link that broke.

    THE CHAIN IS REPORTED WHOLE, not just its failure. `_evidence` tries the fixed map, then the
    clock registry, then the paper-sleeve artifact, and "UNMEASURED" collapses all three into one
    word. Which link broke is the difference between registering a clock and writing a runner --
    two completely different pieces of work, and the word alone distinguishes neither.
    """
    name = str(slot.get("name", "?"))
    ev = str(slot.get("evidence", "") or "")
    row: dict[str, Any] = {"name": name, "evidence": ev, "days": slot.get("days"),
                           "verdict": slot.get("verdict") or slot.get("state")}
    if ev != "UNMEASURED":
        row["state"] = "MEASURABLE"
        row["action"] = "none -- this slot publishes accrual and can be judged"
        return row

    script, where = _owner(name)
    reg = _read("data/axis_clock_registry.json") or {}
    axes = reg.get("axes") if isinstance(reg, dict) else None
    registered = isinstance(axes, dict) and name in axes
    rec = (axes or {}).get(name) if registered else None
    clock_rel = rec.get("clock") if isinstance(rec, dict) else None
    clock_exists = bool(clock_rel) and (_ROOT / str(clock_rel)).exists()

    paper = _read("data/paper_sleeve_forward.json") or {}
    sleeves = paper.get("sleeves") if isinstance(paper, dict) else None
    in_paper = isinstance(sleeves, dict) and name in sleeves

    row.update({"registered_in_clock_registry": registered, "registered_clock_path": clock_rel,
                "clock_file_exists": clock_exists, "in_paper_sleeve_artifact": in_paper,
                "owner_script": script, "owner_should_announce_via": where})

    if registered and clock_rel and not clock_exists:
        row["state"] = "REGISTERED-BUT-ABSENT"
        row["action"] = (
            f"registered against {clock_rel}, which does not exist. Either the collector that "
            f"writes it is not running, or the registry points at the wrong path. FIX: run "
            f"{script}, or correct the registry entry. Do NOT reclaim -- registered-but-absent is "
            "UNKNOWN, and a clock whose rows cannot be found has not been shown to have none")
    elif not registered and not in_paper:
        row["state"] = "ORPHAN"
        row["action"] = (
            "appears in NO accrual artifact: not in the clock registry, not in the paper-sleeve "
            "file. It was spawned, charged its multiplicity, and given no way to publish -- it "
            "holds a seat forever while being structurally unable to resolve. FIX: have "
            f"{script} announce it via {where}. If nothing owns it, the correct action is a "
            "LEDGERED retirement recording that it was never measurable -- a decision, not a "
            "cleanup")
    else:
        row["state"] = "PUBLISHED-BUT-UNPARSEABLE"
        row["action"] = (
            "has a row in an accrual artifact that yielded no day count or timestamp. FIX: "
            f"inspect the row written by {script}; the shape changed or the write is partial")
    return row


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    from libs.research.slot_registry import derive_slots

    slots = derive_slots()
    rows = [diagnose(s) for s in slots.get("slots", [])]
    blocked = [r for r in rows if r["state"] != "MEASURABLE"]
    # THE KEYS ARE `seats_used`/`seats_free`, NOT `occupied`/`idle_slots`. The first run of this
    # script printed "None occupied / cap 12, 0 unmeasurable" against a queue reporting 13 and 2 --
    # `.get()` on the wrong name returns None and a report full of Nones reads like a clean desk.
    # That is the same substitution this whole file exists to catch, made by the catcher.
    rep = {"updated": datetime.now(tz=UTC).isoformat(),
           "seats_used": slots.get("seats_used"), "cap": slots.get("cap"),
           "seats_free": slots.get("seats_free"), "over_cap": slots.get("over_cap"),
           "m_upper": slots.get("m_upper"), "complete": slots.get("complete"),
           "n_unmeasurable": len(blocked), "slots": rows,
           "why_this_matters": (
               "the forward queue rations BREADTH, and breadth is the only route to a higher "
               "combined Sharpe. A seat nobody can judge is held forever, costing a real "
               "candidate ~90 days of queue wait on top of its own 90-day clock")}
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(rep, indent=1), "utf-8")

    if args.json:
        print(json.dumps(rep, indent=1))
        return 0
    print(f"=== FORWARD SLOT DIAGNOSIS === seats {slots.get('seats_used')} used "
          f"({slots.get('seats_free')} free) of cap {slots.get('cap')}, "
          f"multiplicity high-water {slots.get('m_upper')}, "
          f"{len(blocked)} unmeasurable, complete={slots.get('complete')}")
    if not rows:
        print("  derive_slots() returned NO rows on this host -- that is UNMEASURED, not an empty "
              "queue. data/ is gitignored, so a clone sees none of the clocks the box is running")
    for r in blocked:
        print(f"\n  [{r['state']}] {r['name'][:78]}")
        print(f"    registered={r.get('registered_in_clock_registry')} "
              f"clock={r.get('registered_clock_path')} exists={r.get('clock_file_exists')} "
              f"paper_row={r.get('in_paper_sleeve_artifact')}")
        print(f"    owner: {r.get('owner_script')}")
        print(f"    -> {r['action']}")
    if not blocked:
        print("  every slot publishes accrual and can be judged")
    print(f"\n-> {_OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
