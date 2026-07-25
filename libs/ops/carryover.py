"""§37 CARRY-OVER -- work owed survives an outage and is handed back when the brain returns.

The desk's brain is a metered LLM session. It dies on quota, on session limits, on a bad model
route -- and when it does, the cycle's owed work is simply gone: the next cycle starts from
whatever the sweep happens to report at that moment, with no memory that anything was already
owed, for how long, or how many cycles have passed without it being touched. Detection of the
death already exists (`max_audit.check_stub_deaths` reads the death markers out of the logs).
What did NOT exist is the other half: the work PILING UP across the outage and being handed back.

This module is that half. It keeps an append-only ledger of what each sweep found owed, and from
consecutive snapshots derives the one thing a single sweep can never know -- HOW LONG something
has been owed, and how many cycles have run past it.

THE DISTINCTION THAT MATTERS, and the reason this is not just another queue:

  LOST TO OUTAGE   -- sweeps where the brain died on quota. Items accumulated through no fault of
                      the cycle; the honest response is to hand them back with their true age, not
                      to treat the gap as neglect.
  SEEN AND SKIPPED -- sweeps where the brain RAN, was shown the item, and it survived anyway. That
                      is not a backlog, it is avoidance, and it is the failure mode a plain queue
                      hides: a long queue looks the same whether nobody was home or everybody
                      walked past it.

Only the second is a defect. Conflating them either punishes the desk for an outage or excuses it
for ignoring work -- and the second mistake is the expensive one.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

#: Log fragments that mean a brain cycle died rather than finished. Mirrors
#: ``max_audit._DEATH_MARKERS`` -- kept here so this module stays importable on its own.
DEATH_MARKERS = (
    "out of usage credits", "session limit", "hit your limit", "usage limit",
    "issue with the selected model", "rate limit", "quota",
)

SweepRow = Mapping[str, Any]


def record_sweep(
    path: Path, defect_ids: Sequence[str], *, ts: float, brain_alive: bool = True
) -> None:
    """Append one line: what was owed at this sweep, and whether the brain was up to see it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": float(ts), "ids": sorted(set(defect_ids)), "alive": bool(brain_alive)}
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


def load_sweeps(path: Path) -> list[dict[str, Any]]:
    """Read the sweep ledger, skipping corrupt lines rather than losing the whole history."""
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text("utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(r, dict) and "ts" in r and isinstance(r.get("ids"), list):
            rows.append(r)
    return sorted(rows, key=lambda r: float(r["ts"]))


class CarryItem(BaseModel):
    """One defect that has outlived at least one sweep."""

    model_config = ConfigDict(frozen=True)

    defect_id: str
    first_seen: float
    age_days: float
    sweeps_survived: int      # total sweeps this has been owed through
    seen_by_live_brain: int   # of those, how many ran with the brain UP -- the damning number

    @property
    def skipped(self) -> bool:
        """Survived sweeps the brain was awake for: shown the work, did not do it."""
        return self.seen_by_live_brain >= 2


class CarryoverState(BaseModel):
    """What is owed, how old it is, and how much of the gap was an outage."""

    model_config = ConfigDict(frozen=True)

    n_sweeps: int
    n_dead_sweeps: int        # cycles lost to quota/session death
    items: tuple[CarryItem, ...]
    verdict: str

    @property
    def skipped_items(self) -> tuple[CarryItem, ...]:
        return tuple(i for i in self.items if i.skipped)


def carryover_state(sweeps: Sequence[SweepRow], *, now: float) -> CarryoverState:
    """Derive age and skip-count per still-owed defect from consecutive sweep snapshots."""
    if not sweeps:
        return CarryoverState(n_sweeps=0, n_dead_sweeps=0, items=(),
                              verdict="no sweep history yet -- nothing carried")
    first: dict[str, float] = {}
    total: dict[str, int] = {}
    live: dict[str, int] = {}
    for row in sweeps:
        ts, alive = float(row["ts"]), bool(row.get("alive", True))
        for did in row["ids"]:
            d = str(did)
            first.setdefault(d, ts)
            total[d] = total.get(d, 0) + 1
            if alive:
                live[d] = live.get(d, 0) + 1
    still_owed = {str(d) for d in sweeps[-1]["ids"]}
    items = tuple(sorted(
        (CarryItem(defect_id=d, first_seen=first[d],
                   age_days=round((now - first[d]) / 86400.0, 2),
                   sweeps_survived=total[d], seen_by_live_brain=live.get(d, 0))
         for d in still_owed),
        key=lambda i: (-i.seen_by_live_brain, -i.age_days),
    ))
    dead = sum(1 for r in sweeps if not bool(r.get("alive", True)))
    skipped = [i for i in items if i.skipped]

    if not items:
        verdict = f"nothing owed across {len(sweeps)} sweep(s) -- the queue is genuinely empty"
    elif skipped:
        verdict = (
            f"{len(skipped)} item(s) survived sweeps the brain was AWAKE for -- shown the work and "
            f"not done. {dead} cycle(s) were lost to quota; those are not the excuse for these. "
            "A long queue looks identical whether nobody was home or everybody walked past it; "
            "this is the second case."
        )
    elif dead:
        verdict = (f"{len(items)} item(s) owed, {dead} cycle(s) lost to quota -- accumulated "
                   "through no fault of the cycle. Hand them back with their true age.")
    else:
        verdict = f"{len(items)} item(s) owed, all fresh -- nothing has been skipped yet"
    return CarryoverState(n_sweeps=len(sweeps), n_dead_sweeps=dead, items=items, verdict=verdict)


def brief(state: CarryoverState, *, max_items: int = 12) -> str:
    """The block handed to the brain at cycle start -- oldest and most-skipped first."""
    if not state.items:
        return "[§37 CARRY-OVER] queue empty -- nothing owed from previous cycles."
    lines = [
        "[§37 CARRY-OVER] WORK OWED FROM PREVIOUS CYCLES -- do these FIRST, in this order.",
        f"  {state.verdict}",
        f"  ({state.n_sweeps} sweeps on record, {state.n_dead_sweeps} lost to quota/session death)",
        "",
    ]
    for i in state.items[:max_items]:
        mark = "SKIPPED" if i.skipped else "owed"
        lines.append(
            f"  [{mark:7}] {i.defect_id}  age {i.age_days:.1f}d  "
            f"survived {i.sweeps_survived} sweep(s), {i.seen_by_live_brain} with the brain awake"
        )
    if len(state.items) > max_items:
        lines.append(f"  ... and {len(state.items) - max_items} more")
    lines += [
        "",
        "  An item marked SKIPPED was shown to a LIVE cycle at least twice and survived. Either",
        "  do it now, or record in the ledger WHY it is not being done -- silently carrying it a",
        "  third time is the behaviour this brief exists to stop.",
    ]
    return "\n".join(lines)
