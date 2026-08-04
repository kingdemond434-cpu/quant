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
  SEEN AND DEFERRED -- (added 2026-08-01) sweeps where the brain RAN, judged the item, and wrote a
                      DATED ack with a reason and a lifting condition into the ack registry. That
                      is a disposition, not avoidance: doctrine is explicit that "a settled
                      decision with ledgered reasoning and a falsifier is NOT a defect".

Only the second is a defect. Conflating them either punishes the desk for an outage or excuses it
for ignoring work -- and the second mistake is the expensive one.

THE THIRD CATEGORY WAS MISSING FOR 6.6 DAYS, AND THE COST WAS THE BRIEF ITSELF. This module was
built to separate outage from avoidance and did that correctly -- but it never modelled DEFERRAL,
so every dated ack was filed under avoidance. Measured 2026-08-01: of 47 items the brief reported
owed, 26 were currently acked and 1 was already fixed (57% false positive), and because the sort
is by age the OLDEST acks floated to the top -- the 12 items handed to the brain FIRST were 12/12
acked, several blocked on principal-only actions (a Tier-3 flip, a manual re-arm) or on cron dates
that had not arrived. The brief's own closing line tells the brain to "record in the ledger WHY it
is not being done"; the desk did exactly that, 26 times, and the brief had no reader for it. So it
escalated its own false alarm every cycle -- each cycle that correctly walked past an acked item
incremented ``seen_by_live_brain``, which made the accusation louder. A gate whose top of queue is
100% false gets walked past, and that is how enforcement actually dies.

The fix is NOT to mute the acks. Doctrine forbids permanent burial (30d ack cap), so a dated ack
renewed forever is burial by instalments -- exactly what nothing was watching. Deferral is now
recorded separately and surfaced as its own TREADMILL signal, which is strictly more enforcement
than existed before: the false alarm is removed and a real one nobody had is added.
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

#: Doctrine caps an ack at 30 days -- "no permanent burial, ever". Past that span an item has been
#: deferred by instalments, which is the thing the ack expiry alone cannot catch: each individual
#: ack is legal and renewing it is free.
TREADMILL_DAYS = 30.0


def record_sweep(
    path: Path,
    defect_ids: Sequence[str],
    *,
    ts: float,
    brain_alive: bool = True,
    acked_ids: Sequence[str] = (),
    ack_state: str = "unknown",
) -> None:
    """Append one line: what was OWED, what was DEFERRED, and whether the brain was up to see it.

    ``defect_ids`` must be the LIVE (un-acked) defects only -- an acked item belongs in
    ``acked_ids``. ``ack_state`` is "known" when the caller genuinely resolved the ack registry and
    "unknown" when it could not; it defaults to "unknown" so a caller that has not been taught the
    difference degrades to a stated uncertainty rather than a silent claim.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": float(ts),
        "ids": sorted(set(defect_ids)),
        "alive": bool(brain_alive),
        "acked": sorted(set(acked_ids)),
        "ack_state": str(ack_state),
    }
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
    sweeps_deferred: int = 0  # sweeps this carried a DATED ack -- deferral, never avoidance
    deferred_days: float | None = None   # span of unbroken deferral; None = not yet measurable

    @property
    def skipped(self) -> bool:
        """Survived sweeps the brain was awake for: shown the work, did not do it."""
        return self.seen_by_live_brain >= 2

    @property
    def treadmill(self) -> bool:
        """Deferred past the 30d burial line: legal acks, renewed until the work never happens.

        ``None`` deferral span means the ledger has not carried ack history long enough to judge --
        which reports as unmeasurable, never as clean.
        """
        return self.deferred_days is not None and self.deferred_days >= TREADMILL_DAYS


class CarryoverState(BaseModel):
    """What is owed, how old it is, how much of the gap was an outage, and what is deferred."""

    model_config = ConfigDict(frozen=True)

    n_sweeps: int
    n_dead_sweeps: int        # cycles lost to quota/session death
    items: tuple[CarryItem, ...]
    verdict: str
    deferred: tuple[CarryItem, ...] = ()   # dated acks -- disposed, but watched for the treadmill
    ack_state: str = "unknown"             # did the last sweep resolve the ack registry?

    @property
    def skipped_items(self) -> tuple[CarryItem, ...]:
        return tuple(i for i in self.items if i.skipped)

    @property
    def treadmill_items(self) -> tuple[CarryItem, ...]:
        return tuple(i for i in self.deferred if i.treadmill)


def carryover_state(sweeps: Sequence[SweepRow], *, now: float) -> CarryoverState:
    """Derive age and skip-count per still-owed defect from consecutive sweep snapshots."""
    if not sweeps:
        return CarryoverState(n_sweeps=0, n_dead_sweeps=0, items=(),
                              verdict="no sweep history yet -- nothing carried")
    first: dict[str, float] = {}
    total: dict[str, int] = {}
    live: dict[str, int] = {}
    defer_n: dict[str, int] = {}
    defer_first: dict[str, float] = {}
    for row in sweeps:
        ts, alive = float(row["ts"]), bool(row.get("alive", True))
        for did in row["ids"]:
            d = str(did)
            first.setdefault(d, ts)
            total[d] = total.get(d, 0) + 1
            if alive:
                live[d] = live.get(d, 0) + 1
        # An ack is a DISPOSITION, so it never counts toward the skip tally -- but its age does
        # count toward the treadmill, and its first sighting still dates the underlying defect.
        acked_row = row.get("acked") or []
        for did in acked_row:
            d = str(did)
            first.setdefault(d, ts)
            defer_n[d] = defer_n.get(d, 0) + 1
            defer_first.setdefault(d, ts)
        # A sweep in which an item is NOT acked breaks the deferral run: re-acking after a live
        # spell is a fresh decision, not thirty unbroken days of burial.
        for d in list(defer_first):
            if d not in {str(x) for x in acked_row}:
                defer_first.pop(d, None)

    last = sweeps[-1]
    still_owed = {str(d) for d in last["ids"]}
    still_deferred = {str(d) for d in (last.get("acked") or [])}

    def _mk(d: str) -> CarryItem:
        span = defer_first.get(d)
        return CarryItem(
            defect_id=d, first_seen=first[d],
            age_days=round((now - first[d]) / 86400.0, 2),
            sweeps_survived=total.get(d, 0), seen_by_live_brain=live.get(d, 0),
            sweeps_deferred=defer_n.get(d, 0),
            deferred_days=(round((now - span) / 86400.0, 2) if span is not None else None),
        )

    items = tuple(sorted((_mk(d) for d in still_owed),
                         key=lambda i: (-i.seen_by_live_brain, -i.age_days)))
    deferred = tuple(sorted((_mk(d) for d in still_deferred),
                            key=lambda i: -(i.deferred_days or 0.0)))
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
    return CarryoverState(n_sweeps=len(sweeps), n_dead_sweeps=dead, items=items, verdict=verdict,
                          deferred=deferred, ack_state=str(last.get("ack_state", "unknown")))


def _treadmill_block(state: CarryoverState) -> list[str]:
    """Dated acks that have outlived the 30d burial line -- the signal ack expiry cannot give."""
    worst = state.treadmill_items
    if not worst:
        return []
    lines = [
        "",
        f"  [§37 TREADMILL] {len(worst)} item(s) DEFERRED past the {TREADMILL_DAYS:.0f}d burial "
        "line. Each ack was legal; renewing one is free, and that is the point -- doctrine caps an",
        "  ack at 30d precisely so nothing is buried by instalments. Close these or escalate them;",
        "  a fourth renewal is not a decision.",
    ]
    lines += [f"    {i.defect_id}  deferred {i.deferred_days:.1f}d "
              f"across {i.sweeps_deferred} sweep(s)" for i in worst[:8]]
    return lines


def brief(state: CarryoverState, *, max_items: int = 12) -> str:
    """The block handed to the brain at cycle start -- oldest and most-skipped first."""
    if not state.items:
        head = "[§37 CARRY-OVER] queue empty -- nothing owed from previous cycles."
        if state.deferred:
            head += (f" ({len(state.deferred)} item(s) deferred under a dated ack -- disposed, not "
                     "owed.)")
        return "\n".join([head, *_treadmill_block(state)])
    lines = [
        "[§37 CARRY-OVER] WORK OWED FROM PREVIOUS CYCLES -- do these FIRST, in this order.",
        f"  {state.verdict}",
        f"  ({state.n_sweeps} sweeps on record, {state.n_dead_sweeps} lost to quota/session death)",
    ]
    if state.deferred:
        lines.append(f"  {len(state.deferred)} further item(s) carry a DATED ack and are NOT "
                     "listed here -- a reasoned, expiring deferral is a disposition, not "
                     "avoidance.")
    if state.ack_state != "known":
        lines.append("  ACK STATE UNMEASURED for the latest sweep: the ack registry could not be "
                     "read, so this list may contain items that are in fact disposed. Treat the "
                     "ranking as unverified until it reads 'known' again.")
    lines.append("")
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
        "  An item marked SKIPPED was shown to a LIVE cycle at least twice and survived, with NO",
        "  dated ack recorded against it. Either do it now, or record in the ledger WHY it is not",
        "  being done -- silently carrying it a third time is the behaviour this brief exists to",
        "  stop. Writing a dated, reasoned ack IS doing the second thing: it moves the item to the",
        "  deferred list, where the treadmill check then watches it.",
    ]
    lines += _treadmill_block(state)
    return "\n".join(lines)
