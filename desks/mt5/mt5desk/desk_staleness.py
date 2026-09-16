"""Staleness must disarm: a desk whose research organs have all gone silent stops opening risk.

THE RULE, THE PRINCIPAL'S (2026-09-16): "if no cycle has completed in N days: flatten, disarm,
report loudly, wait for a human." The desk already applies "a position you cannot measure is a
position you do not hold" to positions; this applies it to the desk. It sat ARMED for thirty days
against state from 2026-08-17 while eighteen scheduled tasks did not exist, and nothing objected,
because every check the gateway ran was a check of the gateway.

WHAT COUNTS AS A COMPLETED CYCLE. Not one file -- one organ can die alone -- but the NEWEST of
several artifacts that only exist because a research organ finished: the allocator's book, the
CEO docket, the survivors sweep and the compute ledger every hourly leg appends to. All four
silent for `DISARM_DAYS` means the desk is trading on a picture nobody has refreshed; that is
blind, and blind does not open new risk. All four silent for `FLATTEN_DAYS` means nobody is
coming, and the book goes flat and waits.

WHAT IT DOES NOT DO. It never touches an open position before `FLATTEN_DAYS`, never lowers heat
while the desk is alive, and never fires on a weekend gap: the artifacts are written every hour
the box is up, so a healthy desk is measured in hours and the thresholds are in days. It is an
INTEGRITY kill switch in `capital_modifiers` terms, not a risk preference.
"""
from __future__ import annotations

import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]

#: Days of total research silence before new risk is refused, and before the book is flattened.
DISARM_DAYS = float(os.environ.get("DESK_DISARM_DAYS", "3"))
FLATTEN_DAYS = float(os.environ.get("DESK_FLATTEN_DAYS", "7"))

#: The artifacts whose NEWEST write is "the last time a research cycle completed".
HEARTBEATS: tuple[Path, ...] = (
    BASE / "reports" / "pf_allocation.json",
    BASE / "reports" / "CEO_DOCKET.json",
    BASE / "reports" / "UNIVERSAL_SURVIVORS.json",
    BASE / "data" / "compute_ledger.jsonl",
)
OUT = BASE / "reports" / "DESK_STALE.json"


def staleness(now: float | None = None, heartbeats: tuple[Path, ...] = HEARTBEATS,
              ) -> dict[str, Any]:
    """Age in days of the newest heartbeat, every heartbeat's own age, and the verdict.

    A heartbeat that does not exist is reported as absent and contributes nothing; if NONE
    exists the desk is UNMEASURED and treated as stale at the disarm level, never as fresh --
    absence is not health (L1.28a).
    """
    t = now if now is not None else time.time()
    ages: dict[str, float | None] = {}
    for p in heartbeats:
        try:
            ages[p.name] = round((t - p.stat().st_mtime) / 86400.0, 3)
        except OSError:
            ages[p.name] = None
    known = [a for a in ages.values() if a is not None]
    if not known:
        return {"status": "UNMEASURED", "verdict": "DISARM", "age_days": None, "newest": None,
                "ages": ages, "disarm_days": DISARM_DAYS, "flatten_days": FLATTEN_DAYS,
                "why": "no research heartbeat exists on this box; nothing has ever completed"}
    age = min(known)
    newest = min((k for k, a in ages.items() if a is not None), key=lambda k: ages[k] or 0.0)
    if age >= FLATTEN_DAYS:
        verdict, why = "FLATTEN", (f"every research heartbeat is >= {FLATTEN_DAYS:g} days old "
                                   f"(newest {newest} {age:.1f}d): the desk is blind and nobody "
                                   f"is coming; the book goes flat and waits for a human")
    elif age >= DISARM_DAYS:
        verdict, why = "DISARM", (f"every research heartbeat is >= {DISARM_DAYS:g} days old "
                                  f"(newest {newest} {age:.1f}d): no new risk until a cycle "
                                  f"completes; open positions keep their brackets and exits")
    else:
        verdict, why = "OK", f"newest heartbeat {newest} is {age * 24:.1f}h old"
    return {"status": "MEASURED", "verdict": verdict, "age_days": round(age, 3),
            "newest": newest, "ages": ages, "disarm_days": DISARM_DAYS,
            "flatten_days": FLATTEN_DAYS, "why": why}


def publish(doc: dict[str, Any], *, flattened: int | None = None) -> None:
    """Write the verdict where the dashboard and the next human can see it. Never raises."""
    try:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps({**doc, "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
                                   **({"flattened_positions": flattened}
                                      if flattened is not None else {})}, indent=1), "utf-8")
    except OSError:
        pass
