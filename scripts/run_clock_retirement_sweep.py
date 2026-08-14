#!/usr/bin/env python3
"""THE RETIREMENT SWEEP -- surface every clock that can no longer earn its seat (GAP 112).

WHY THIS EXISTS. `slot_displacement` can already tell a jammed clock from a working one, files a
pre-registered kill as REFUTED and an instrument fault as UNTESTED, and never evicts a healthy
incumbent. All of that is real and tested. But it is only ever called WITH A QUEUE -- a challenger
arrives, and the plan is computed to make room for it. With an empty queue nothing calls it, so a
clock that provably cannot resolve keeps its seat indefinitely and keeps charging every neighbour
multiplicity for it.

Measured on the live box 2026-08-13:

    m=15 [MEASURED] cap=12    15/12 slots used, 0 idle    bar 2.71 (vs 2.64 at m=12)
    walcl_reserve_impulse: DEGENERATE -- 9 dated rows yielded 2 distinct observations

Fifteen clocks against a twelve-slot cap, ZERO idle, and at least one of them an instrument fault
that cannot resolve however long it runs. Nothing could start -- and the bar every real candidate
must clear was raised by clocks returning nothing.

**IT SURFACES; IT DOES NOT RETIRE.** Removing a row SHRINKS the cohort and LOOSENS every remaining
bar, which is the phantom-edge direction. So retirement from `m` stays an explicit ledgered
decision, exactly as `slot_registry`'s own docstring requires. What this removes is invisibility:
the difference between a dead clock nobody has noticed and a dead clock with a dated, evidenced
retirement proposal waiting for a decision.

**AND IT SEPARATES THE TWO REASONS A SEAT IS WASTED**, because the remedies are opposite:

    RECLAIMABLE   the clock cannot resolve -- broken instrument, zero observations, or it reached
                  its own pre-registered kill. The seat is genuinely free to take.
    BLOCKED       the clock cannot be ASSESSED. This is a MEASUREMENT defect to fix upstream, and
                  it is deliberately NOT proposed for retirement: wrongly reclaiming destroys
                  forward evidence that cannot be re-earned at any price, while wrongly protecting
                  costs a queue position.

    python scripts/run_clock_retirement_sweep.py
"""

from __future__ import annotations

# PATH BOOTSTRAP. `python scripts/x.py` puts scripts/ on sys.path, NOT the repo root.
import sys as _sys
from pathlib import Path as _P

if str(_P(__file__).resolve().parent.parent) not in _sys.path:
    _sys.path.insert(0, str(_P(__file__).resolve().parent.parent))

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from libs.research.slot_displacement import (
    BLOCKED,
    RECLAIMABLE,
    _requeue_for,
    classify_slot,
)
from libs.research.slot_registry import MAX_FORWARD_SLOTS, derive_slots

_OUT = Path("data/clock_retirement_proposals.json")
#: THE DASHBOARD READS web/, NOT data/. Writing only the state file would repeat the defect this
#: whole area keeps producing: a correct artifact nobody can see. run_axis_shadows already sets
#: the pattern -- state under data/, the same payload under web/ for the page.
_WEB = Path("web/clock_retirement.json")


def sweep(slots: list[dict[str, Any]]) -> dict[str, Any]:
    """Classify every occupied seat and propose retirements. Pure: no writes, no decisions."""
    proposals: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    protected: list[str] = []
    for s in slots:
        state, why = classify_slot(s)
        name = str(s.get("name", "?"))
        if state == RECLAIMABLE:
            proposals.append({
                "clock": name,
                "kind": s.get("kind"),
                "evidence": s.get("evidence"),
                "observations": s.get("days"),
                "verdict": s.get("verdict") or s.get("state"),
                "why": why,
                # The mechanism of death, which decides how the hypothesis is re-filed. L1.17 turns
                # on this: a refutation re-queued as untested buys the same dead axis again, and an
                # instrument fault filed as refuted retires ground nobody ever measured.
                "requeue_as": _requeue_for(s),
                "disposition": "PROPOSED-RETIREMENT (ledgered decision required)",
            })
        elif state == BLOCKED:
            blocked.append({"clock": name, "why": why})
        else:
            protected.append(name)

    m = len(slots)
    freeable = len(proposals)
    return {
        "updated": datetime.now(tz=UTC).isoformat(),
        "m_now": m,
        "cap": MAX_FORWARD_SLOTS,
        "over_cap": m > MAX_FORWARD_SLOTS,
        "seats_free_now": max(0, MAX_FORWARD_SLOTS - m),
        "seats_freeable": freeable,
        "seats_free_if_all_retired": max(0, MAX_FORWARD_SLOTS - (m - freeable)),
        "proposals": proposals,
        "blocked": blocked,
        "protected": protected,
        "note": (
            "PROPOSALS ONLY. Retiring a clock removes a row from the Holm cohort, which shrinks m "
            "and LOOSENS every remaining bar -- the phantom-edge direction -- so it stays an "
            "explicit ledgered decision and this organ never takes it. BLOCKED clocks are listed "
            "separately and are NOT proposed: they cannot be assessed, which is a measurement "
            "defect to fix upstream, and wrongly reclaiming one destroys forward evidence that "
            "cannot be re-earned at any price."),
    }


def main() -> int:
    try:
        snap = derive_slots()
        slots = list(snap.get("slots") or [])
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"clock-retirement: registry unreadable ({type(exc).__name__}: {exc}) -- UNMEASURED, "
              "nothing written. A sweep over nothing would report 'no dead clocks', which is a "
              "different and false claim.")
        return 1
    if not slots:
        print("clock-retirement: the cohort is EMPTY, which the registry cannot produce "
              "legitimately -- it is built from hardcoded standing and derivative names. "
              "Treating this as 'nothing to retire' would hide a read failure (L1.57).")
        return 1

    rep = sweep(slots)
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(rep, indent=1), "utf-8")
    _WEB.parent.mkdir(parents=True, exist_ok=True)
    _WEB.write_text(json.dumps(rep, indent=1), "utf-8")

    head = "OVER CAP" if rep["over_cap"] else "within cap"
    print(f"clock-retirement: m={rep['m_now']} cap={rep['cap']} ({head}), "
          f"{rep['seats_free_now']} free now, {rep['seats_freeable']} freeable "
          f"-> {rep['seats_free_if_all_retired']} free if all proposals are accepted")
    for p in rep["proposals"]:
        print(f"  PROPOSE RETIRE  {p['clock']:<34} requeue_as={p['requeue_as']}")
        print(f"                  {p['why']}")
    for b in rep["blocked"]:
        print(f"  BLOCKED         {b['clock']:<34} not proposed -- fix the measurement upstream")
    if not rep["proposals"]:
        print("  no clock is currently reclaimable -- every occupied seat is either accruing or "
              "unassessable, and neither may be taken")
    print(f"-> {_OUT} and {_WEB}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
