"""THE CLOCK REGISTRY — the wire between an organ that notices and an organ that can act.

THE GAP THIS CLOSES, measured on the live box 2026-08-09 and printing in every cycle before that:

    LADDER : 9 survivor(s) owed a shadow start; 0 record(s) laddered

`scripts/run_live_ladder.py` computes which Stage-A survivors are owed a forward clock, and then
correctly declares `authority: NONE -- recommendations only`. It must not start clocks; that is
`scripts/run_axis_shadows.py`'s job. But that script read a HARDCODED `_AXES` dict, so it could not
see the list. One organ noticed and could not act; the other could act and could not see.

**THE COST IS THE ONE THING THIS DESK CANNOT BUY LATER.** A survivor waiting on a clock is not
idle, it is losing forward days that will never be recovered. Nine survivors x every day the wire
was missing is the largest silent loss in the pipeline, and it printed as a tidy status line.

**REGISTERING IS NOT STARTING A CLOCK, AND IT IS NOT A PROMOTION.** An entry here earns exactly two
things: a row in Stage-B's report and a row on the dashboard. It earns no capital, no eligibility
and no evidence. What it removes is invisibility -- the difference between an owed clock and a
forgotten one.

**AND IT REGISTERS THEM AS UNTRACKED, ON PURPOSE.** A sweep survivor key is not an axis: it has no
collector JSONL and no target symbol, so Stage-B cannot score it. The honest state is *owed and
unscoreable*, which `run_axis_shadows` already renders as UNTRACKED. Inventing a target so the row
looked complete would score a candidate against the wrong asset, which is worse than not scoring
it -- and `first registration wins`, so a later run with real inputs can fill it in without this
one having guessed first.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

__all__ = ["REGISTRY", "register_owed"]

#: Shared with libs/research/axis_screen.py and scripts/run_axis_shadows.py. One file, so an organ
#: and the tracker can never disagree about which clocks are owed.
REGISTRY = Path("data/axis_clock_registry.json")


def register_owed(names: list[str], *, source: str, registry: Path | str = REGISTRY,
                  ) -> tuple[int, str]:
    """Record survivors owed a forward clock. Returns (newly registered, why).

    IDEMPOTENT AND FIRST-WRITE-WINS. The ladder runs every cycle and would otherwise restamp the
    same nine names daily, resetting `owed_since` and erasing the very number that makes the debt
    legible -- how long it has been owed.
    """
    if not names:
        return 0, ("no survivor is owed a shadow start. On a clone with no sweep artifact this is "
                   "UNMEASURED rather than a clean queue: the sweep is gitignored and lives on "
                   "the box")
    reg = Path(registry)
    try:
        blob = json.loads(reg.read_text("utf-8")) if reg.exists() else {}
    except (OSError, ValueError):
        blob = {}
    raw = blob.get("axes")
    axes: dict[str, Any] = dict(raw) if isinstance(raw, dict) else {}

    now = datetime.now(tz=UTC).isoformat()
    added, already = 0, 0
    for name in names:
        key = str(name).strip()
        if not key:
            continue
        if key in axes:
            already += 1
            continue
        axes[key] = {
            "clock": "",
            "target_symbol": "",
            "method": "z20",
            "sign": 0,
            "registered_at": now,
            "owed_since": now,
            "registered_by": source,
            "tracked": False,
            "note": ("Stage-A survivor OWED a forward clock. Registered so Stage-B and the "
                     "dashboard can see the debt; this is not a promotion and starts no clock. "
                     "It carries no collector JSONL and no target symbol, so it lists as "
                     "UNTRACKED until one is supplied -- deliberately, because inventing a target "
                     "would score it against the wrong asset, which is worse than not scoring it. "
                     "`sign: 0` means UNKNOWN direction and must never be read as neutral."),
        }
        added += 1

    if added:
        reg.parent.mkdir(parents=True, exist_ok=True)
        blob["axes"] = axes
        blob["updated"] = now
        blob.setdefault("note", (
            "Forward clocks owed or started. Written by stage_a_screen when a screen earns a "
            "clock, and by run_live_ladder when a Stage-A survivor is owed one. Read by "
            "run_axis_shadows so a candidate reaches Stage-B and the dashboard WITHOUT a code "
            "edit -- the absence of that path stranded 9 survivors indefinitely."))
        reg.write_text(json.dumps(blob, indent=1), "utf-8")

    return added, (
        f"{added} survivor(s) newly registered as owed a forward clock, {already} already known "
        f"(source: {source}). They list as UNTRACKED until a collector and target symbol exist, "
        "which is the honest state -- owed and unscoreable is not the same as absent, and it is "
        "the difference between an owed clock and a forgotten one"
        if added else
        f"all {already} owed survivor(s) were already registered (source: {source}); "
        "`owed_since` deliberately NOT restamped, because how long a clock has been owed is the "
        "number that makes the debt legible")
