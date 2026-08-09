"""HUNT FRONTIER — what has actually been mined, what was only NAMED, and what was MISSED.

THE DEFECT THIS REMOVES, and it is the expensive kind because it looks like discipline.
`kimi_hunter` recorded every territory its model NAMED into a coverage file, then excluded
everything in that file from the next 45 days of hunting. The exclusion text is emphatic --
*"ALREADY HUNTED -- do NOT return to these, they are picked over"* -- and for a territory that was
genuinely mined, it is right.

But three different things were all being stamped with the same mark:

    YIELDED       hunted, and it produced findings. Genuinely picked over.
    EMPTY         hunted, and there was nothing there. Real negative knowledge; also done.
    NAMED_ONLY    the mapping wave named it and no hunt ever ran. NOT hunted.
    BLOCKED       a hunt was attempted and could not complete -- paywall, no transcript, dead
                  link, rate limit. NOT hunted, and the reason may not last.

`kimi_hunter`'s Wave 1 is mapping only (`if w == 1: continue` -- findings are not even permitted),
so **every territory the mapping wave identified was locked out for 45 days before it was ever
hunted.** The organ was systematically excluded from exactly the ground it had just judged most
interesting, and the coverage file recorded that as progress.

**THE FRONTIER IS THE INVERSE OF COVERAGE, AND IT IS THE THING WORTH SPENDING ON.** A hunt that
returns to picked-over ground wastes a reasoning pass; a hunt that never returns to BLOCKED ground
loses the finding permanently, because nothing else will ever go back for it. So NAMED_ONLY and
BLOCKED are not exclusions -- they are the priority queue, surfaced ahead of anything new.

**AND IT ANSWERS "SHOULD WE RUN AT ALL" FOR FREE.** `should_hunt` reads local state and decides
whether frontier exists, with no model call. That is the whole saving: a hunter firing every three
hours pays a full reasoning pass to discover that the world has not changed, when a file on disk
already knew.

Pure state accounting. Calls nothing, fetches nothing, and never decides what a hunter concludes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

__all__ = [
    "BLOCKED_RETRY_D",
    "OUTCOMES",
    "Vector",
    "VectorState",
    "frontier",
    "load",
    "prompt_sections",
    "record",
    "save",
    "should_hunt",
    "summarise",
]

#: What a hunt against one territory actually achieved. Ordered least to most conclusive.
OUTCOMES: tuple[str, ...] = (
    "NAMED_ONLY",   # a mapping wave named it; no hunt has run. NOT covered.
    "BLOCKED",      # hunted and could not complete. NOT covered, and the blocker may lift.
    "EMPTY",        # hunted, nothing there. Covered -- this is real negative knowledge.
    "YIELDED",      # hunted, produced findings. Covered.
)

#: A blocker is a fact about a moment, not about a territory. Paywalls lapse, transcripts appear,
#: rate limits reset. Long enough not to thrash, short enough that a lifted blocker is noticed.
BLOCKED_RETRY_D: int = 10

#: Default cooldown for genuinely covered ground. Callers pass their own; kimi_hunter uses 45.
COVERED_COOLDOWN_D: int = 45


@dataclass(frozen=True)
class Vector:
    """One named territory and everything known about hunting it."""

    name: str
    outcome: str = "NAMED_ONLY"
    first_seen: str = ""
    last_attempt: str = ""
    attempts: int = 0
    findings: int = 0
    blocker: str = ""

    def __post_init__(self) -> None:
        if self.outcome not in OUTCOMES:
            raise ValueError(f"unknown outcome {self.outcome!r}; expected one of {OUTCOMES}")

    @property
    def covered(self) -> bool:
        """Only a completed hunt covers ground. Naming it does not; failing to reach it does not."""
        return self.outcome in ("YIELDED", "EMPTY")

    def _age_days(self, stamp: str, now: datetime) -> float | None:
        if not stamp:
            return None
        try:
            return (now - datetime.fromisoformat(stamp)).total_seconds() / 86400.0
        except ValueError:
            return None

    def huntable(self, now: datetime, *, cooldown_d: int = COVERED_COOLDOWN_D) -> tuple[bool, str]:
        """(may hunt now, why). UNKNOWN AGES ARE HUNTABLE, deliberately.

        An unparseable timestamp means the record is damaged, and the safe direction for damaged
        coverage is to allow the hunt: re-hunting known ground costs one pass, while wrongly
        excluding live frontier costs the finding permanently and silently.
        """
        if self.outcome == "NAMED_ONLY":
            return True, f"{self.name}: NAMED but never hunted -- this is frontier, not coverage"
        if self.outcome == "BLOCKED":
            age = self._age_days(self.last_attempt, now)
            if age is None or age >= BLOCKED_RETRY_D:
                return True, (f"{self.name}: BLOCKED"
                              + (f" ({self.blocker})" if self.blocker else "")
                              + f", last tried {'unknown' if age is None else f'{age:.0f}d'} ago "
                                "-- a blocker is a fact about a moment, not about the territory")
            return False, (f"{self.name}: BLOCKED {age:.0f}d ago, retry at {BLOCKED_RETRY_D}d")
        age = self._age_days(self.last_attempt or self.first_seen, now)
        if age is None:
            return True, (f"{self.name}: timestamp unreadable -- allowing the hunt. Re-hunting "
                          "known ground costs one pass; wrongly excluding live frontier costs "
                          "the finding permanently and silently")
        if age >= cooldown_d:
            return True, (f"{self.name}: {self.outcome} {age:.0f}d ago, past the "
                          f"{cooldown_d}d cooldown")
        return False, f"{self.name}: {self.outcome} {age:.0f}d ago -- picked over"


@dataclass
class VectorState:
    """The whole coverage file, migrated and outcome-aware."""

    vectors: dict[str, Vector] = field(default_factory=dict)
    note: str = ""

    def upsert(self, v: Vector) -> None:
        self.vectors[v.name] = v


def load(path: Path | str) -> VectorState:
    """Read coverage, MIGRATING the legacy `{name: {first_seen}}` shape.

    Legacy records carry no outcome, and the honest reading of "somebody wrote this name down and
    recorded nothing else" is NAMED_ONLY -- not YIELDED. Migrating them as covered would preserve
    the exact bug this module exists to remove, on the entire existing history.
    """
    p = Path(path)
    try:
        blob = json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return VectorState()
    out = VectorState(note=str(blob.get("note", "")))
    for name, rec in (blob.get("vectors") or {}).items():
        if not isinstance(rec, dict):
            continue
        out.upsert(Vector(
            name=str(name),
            outcome=str(rec.get("outcome") or "NAMED_ONLY"),
            first_seen=str(rec.get("first_seen") or ""),
            last_attempt=str(rec.get("last_attempt") or ""),
            attempts=int(rec.get("attempts") or 0),
            findings=int(rec.get("findings") or 0),
            blocker=str(rec.get("blocker") or ""),
        ))
    return out


def save(state: VectorState, path: Path | str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({
        "updated": datetime.now(tz=UTC).isoformat(),
        "vectors": {n: {"outcome": v.outcome, "first_seen": v.first_seen,
                        "last_attempt": v.last_attempt, "attempts": v.attempts,
                        "findings": v.findings, "blocker": v.blocker}
                    for n, v in sorted(state.vectors.items())},
        "note": ("NAMED_ONLY and BLOCKED are FRONTIER, not coverage -- they are surfaced to the "
                 "hunter as priority targets, never as exclusions. Only YIELDED and EMPTY are "
                 "picked-over ground. A mapping wave that names a territory has not hunted it."),
    }, indent=1), "utf-8")


def record(state: VectorState, name: str, *, outcome: str, findings: int = 0,
           blocker: str = "") -> Vector:
    """Record the RESULT of a hunt, not merely that a name was uttered."""
    now = datetime.now(tz=UTC).isoformat()
    prev = state.vectors.get(name)
    v = Vector(
        name=name, outcome=outcome,
        first_seen=(prev.first_seen if prev and prev.first_seen else now),
        last_attempt=(now if outcome != "NAMED_ONLY" else (prev.last_attempt if prev else "")),
        attempts=(prev.attempts if prev else 0) + (0 if outcome == "NAMED_ONLY" else 1),
        findings=(prev.findings if prev else 0) + max(0, findings),
        blocker=blocker,
    )
    state.upsert(v)
    return v


def frontier(state: VectorState, *, now: datetime | None = None,
             cooldown_d: int = COVERED_COOLDOWN_D) -> dict[str, list[Vector]]:
    """Split the world into what is worth hunting and what is not."""
    n = now or datetime.now(tz=UTC)
    unhunted, blocked, ready, picked = [], [], [], []
    for v in state.vectors.values():
        ok, _ = v.huntable(n, cooldown_d=cooldown_d)
        if not ok:
            picked.append(v)
        elif v.outcome == "NAMED_ONLY":
            unhunted.append(v)
        elif v.outcome == "BLOCKED":
            blocked.append(v)
        else:
            ready.append(v)
    return {"unhunted": unhunted, "blocked": blocked, "ready": ready, "picked_over": picked}


def should_hunt(state: VectorState, *, now: datetime | None = None,
                cooldown_d: int = COVERED_COOLDOWN_D,
                min_frontier: int = 1) -> tuple[bool, str]:
    """THE FREE GATE. Decide whether an expensive pass is worth firing, with no model call.

    AN EMPTY COVERAGE FILE ALWAYS HUNTS. Run #1 has no history and must bootstrap; a gate that
    refused on no evidence would ensure it never acquired any.

    Returns False only when every known territory is genuinely picked over AND nothing is blocked
    or unhunted -- the one state where a reasoning pass can be predicted to rediscover what the
    desk already has.
    """
    n = now or datetime.now(tz=UTC)
    if not state.vectors:
        return True, ("no hunt history -- run #1 bootstraps. A gate that refused here would "
                      "guarantee the file stayed empty forever")
    f = frontier(state, now=n, cooldown_d=cooldown_d)
    live = len(f["unhunted"]) + len(f["blocked"]) + len(f["ready"])
    if live >= min_frontier:
        return True, (
            f"{live} territory/territories open: {len(f['unhunted'])} NAMED-but-never-hunted, "
            f"{len(f['blocked'])} BLOCKED past retry, {len(f['ready'])} off cooldown. "
            f"{len(f['picked_over'])} genuinely picked over")
    soonest = None
    for v in f["picked_over"]:
        age = v._age_days(v.last_attempt or v.first_seen, n)
        if age is not None:
            d = cooldown_d - age
            soonest = d if soonest is None else min(soonest, d)
    return False, (
        f"all {len(f['picked_over'])} known territory/territories are picked over and nothing is "
        "blocked or unhunted -- a reasoning pass now would rediscover what the desk already has"
        + (f". Next opens in {soonest:.0f}d" if soonest is not None else ""))


def prompt_sections(state: VectorState, *, now: datetime | None = None,
                    cooldown_d: int = COVERED_COOLDOWN_D, limit: int = 40) -> dict[str, str]:
    """Text for the hunter: what to CHASE first, and what to avoid.

    The priority block is the change that matters. Previously every named territory became an
    exclusion, so ground the mapping wave had just flagged as interesting was buried for the full
    cooldown. Now it is the first thing the hunter is pointed at.
    """
    n = now or datetime.now(tz=UTC)
    f = frontier(state, now=n, cooldown_d=cooldown_d)
    chase: list[str] = []
    for v in f["unhunted"][:limit]:
        chase.append(f"{v.name} -- NAMED by a previous mapping wave and NEVER hunted")
    for v in f["blocked"][:limit]:
        chase.append(f"{v.name} -- BLOCKED previously"
                     + (f" ({v.blocker})" if v.blocker else "")
                     + f", {v.attempts} attempt(s); the blocker may have lifted")
    # A BLOCKED TERRITORY IS NOT PICKED OVER, EVEN INSIDE ITS RETRY WINDOW. Telling the model it
    # is "already mined" is the same conflation this module removes, just relocated into the
    # prompt -- and prompts are where a wrong label actually changes behaviour.
    mined = [f"{v.name} ({v.outcome.lower()}, {v.findings} finding(s))"
             for v in f["picked_over"] if v.covered]
    cooling = [f"{v.name} (blocked{': ' + v.blocker if v.blocker else ''}, retry pending)"
               for v in f["picked_over"] if not v.covered]
    avoid = mined
    priority = ("HUNT THESE FIRST -- known frontier, already identified and never mined:\n  "
                + "\n  ".join(chase)
                + "\n\nThese are not suggestions to consider; they are ground this desk has "
                  "already judged interesting and never reached. Exhaust them before generating "
                  "new vectors."
                if chase else
                "No known unhunted or blocked territory. Generate NEW vectors -- name the "
                "territories yourself and say why the herd cannot see them.")
    exclude = ("ALREADY MINED -- do NOT return, they are picked over:\n  " + "\n  ".join(avoid)
               if avoid else "")
    if cooling:
        exclude += (("\n\n" if exclude else "")
                    + "BLOCKED AND RETRIED RECENTLY -- skip THIS run only, they are not mined:\n  "
                    + "\n  ".join(cooling))
    return {"priority": priority, "exclude": exclude,
            "counts": (f"{len(f['unhunted'])} unhunted, {len(f['blocked'])} blocked, "
                       f"{len(f['ready'])} off-cooldown, {len(f['picked_over'])} picked over")}


def summarise(state: VectorState, *, cooldown_d: int = COVERED_COOLDOWN_D) -> dict[str, Any]:
    """Report shape."""
    f = frontier(state, cooldown_d=cooldown_d)
    go, why = should_hunt(state, cooldown_d=cooldown_d)
    yielded = [v for v in state.vectors.values() if v.outcome == "YIELDED"]
    return {
        "vectors": len(state.vectors),
        "unhunted": len(f["unhunted"]), "blocked": len(f["blocked"]),
        "off_cooldown": len(f["ready"]), "picked_over": len(f["picked_over"]),
        "total_findings": sum(v.findings for v in state.vectors.values()),
        "yield_rate": (round(len(yielded) / len(state.vectors), 3) if state.vectors else None),
        "should_hunt": go, "why": why,
        "headline": (
            f"{len(f['unhunted'])} territory/territories NAMED and never hunted, "
            f"{len(f['blocked'])} blocked past retry. {why}"),
        "note": ("Naming a territory is not hunting it and failing to reach one is not covering "
                 "it. Only YIELDED and EMPTY are picked-over ground; NAMED_ONLY and BLOCKED are "
                 "the priority queue, because nothing else will ever go back for them."),
    }
