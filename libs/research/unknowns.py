"""THE UNKNOWNS LEDGER — assumptions, contradictions and unknowns are ONE object at three
confidence levels, and splitting them into three registries would hide the transitions that matter.

WHY ONE MODULE. The principal asked for an assumption registry, a contradiction engine and an
unknowns database. Built as three, they would share a schema, a lifecycle and a consumer, and the
interesting events are precisely the MOVES BETWEEN them:

    an ASSUMPTION that gets tested becomes KNOWN or CONTRADICTED
    a CONTRADICTION that gets resolved becomes KNOWN and retires a search space
    an UNKNOWN that gets named becomes an ASSUMPTION (someone has now stated a belief)
    a KNOWN that live evidence disputes becomes CONTRADICTED -- the most expensive move on the desk

Three tables cannot see a transition; one can, and the transition is the research signal.

THE STATES, and each carries a different action:

    UNKNOWN       nobody has stated a belief          -> name it, then it can be tested
    ASSUMED       a belief is load-bearing, untested  -> design the experiment that breaks it
    TESTING       an experiment is running            -> wait, and record what it will settle
    KNOWN         measured and held                   -> record what would falsify it
    CONTRADICTED  evidence disagrees with a belief    -> HIGHEST priority; something downstream
                                                         was sized on this
    UNMEASURABLE  cannot be tested with reachable data -> a DATA acquisition object, not a dead end

`UNMEASURABLE` IS THE STATE THAT STOPS THIS BECOMING A GRAVEYARD. "We do not have the data" is the
sentence that most often ends a research thread on this desk, and it must convert into an
acquisition target instead. An item parked there carries the DATA it would need, by name.

WHAT WOULD CHANGE OUR MIND IS A REQUIRED FIELD ON ANY BELIEF. A KNOWN with no falsifier is not
knowledge, it is a habit: nothing can ever dislodge it, so it will survive its own obsolescence.
The constructor refuses it, because a field that can be skipped is a field that will be.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime

__all__ = [
    "PRIORITY",
    "STATES",
    "Item",
    "acquire_targets",
    "contradict",
    "ranked",
    "render",
    "resolve",
    "summarise",
]

STATES: tuple[str, ...] = (
    "UNKNOWN", "ASSUMED", "TESTING", "KNOWN", "CONTRADICTED", "UNMEASURABLE",
)

#: Work order. CONTRADICTED first because something downstream was already sized on the belief it
#: breaks -- the cost is being paid now, not hypothetically. ASSUMED outranks UNKNOWN because a
#: load-bearing untested belief is more dangerous than an acknowledged blank: the blank is visible.
PRIORITY: tuple[str, ...] = (
    "CONTRADICTED", "ASSUMED", "UNMEASURABLE", "UNKNOWN", "TESTING", "KNOWN",
)

#: States that assert something about the world and therefore owe a falsifier.
_BELIEF_STATES: frozenset[str] = frozenset({"ASSUMED", "KNOWN"})


@dataclass(frozen=True)
class Item:
    """One thing the desk believes, does not know, or has been contradicted about."""

    key: str
    state: str
    statement: str
    #: What observation would change the desk's mind. REQUIRED for a belief.
    falsifier: str = ""
    #: What the belief is load-bearing FOR -- so a contradiction can be costed.
    depends_on_it: tuple[str, ...] = field(default_factory=tuple)
    #: Named data the item needs before it can be tested. Required for UNMEASURABLE.
    needs_data: tuple[str, ...] = field(default_factory=tuple)
    evidence: str = ""
    #: What created this item. L1.55: a question with no trigger is accumulation.
    trigger: str = ""
    updated: str = ""

    def __post_init__(self) -> None:
        if self.state not in STATES:
            raise ValueError(f"unknown state {self.state!r}; known: {STATES}")
        if self.state in _BELIEF_STATES and not self.falsifier.strip():
            raise ValueError(
                f"{self.key!r} is {self.state} with no falsifier. A belief nothing can dislodge is "
                "a HABIT, not knowledge -- it survives its own obsolescence because no observation "
                "is allowed to count against it. State what would change the desk's mind")
        if self.state == "UNMEASURABLE" and not self.needs_data:
            raise ValueError(
                f"{self.key!r} is UNMEASURABLE and names no data. 'We do not have the data' is the "
                "sentence that most often ends a research thread here, and it must convert into an "
                "ACQUISITION TARGET rather than a dead end. Name the data")
        if not self.trigger.strip():
            raise ValueError(
                f"{self.key!r} has no trigger. L1.55: expansion is driven by information gain, "
                "unexplained observations, contradictions, failures and named blind spots -- never "
                "by accumulation. An item with no trigger is bloat by definition")

    @property
    def rank(self) -> int:
        return PRIORITY.index(self.state)

    @property
    def blast_radius(self) -> int:
        """How many things were reasoned or sized on this. The cost of being wrong."""
        return len(self.depends_on_it)


def contradict(item: Item, *, evidence: str, now: str = "") -> tuple[Item, str]:
    """Live or test evidence disagrees with a belief. THE MOST EXPENSIVE MOVE ON THE DESK.

    Everything in `depends_on_it` was sized and reasoned as though this held, so the contradiction
    is not one defect -- it is one defect plus every decision that rested on it. The returned reason
    names the blast radius, because a contradiction reported without it reads as a curiosity.
    """
    if not evidence.strip():
        return item, ("REFUSED: a contradiction needs its evidence. Moving a belief to "
                      "CONTRADICTED on an assertion would let one unverified claim invalidate "
                      "measured work -- which is the failure mode in the opposite direction")
    stamp = now or datetime.now(tz=UTC).isoformat()
    out = replace(item, state="CONTRADICTED", evidence=evidence, updated=stamp)
    if item.depends_on_it:
        why = (f"CONTRADICTED with blast radius {item.blast_radius}: "
               f"{', '.join(item.depends_on_it)} were sized or reasoned as though this held. Each "
               "must be re-examined, and until they are the desk is running on a belief it knows "
               "is wrong")
    else:
        why = ("CONTRADICTED with no recorded dependents -- which may mean nothing rested on "
               "it, or may mean nobody recorded what did. The second is likelier and worse")
    return out, why


def resolve(item: Item, *, state: str, evidence: str, falsifier: str = "",
            now: str = "") -> tuple[Item, str]:
    """Move an item to a settled state with its evidence.

    A move INTO a belief state must supply a falsifier, and this is where that rule earns its keep:
    resolving a contradiction into new knowledge is exactly the moment a desk is most inclined to
    write down a conclusion and no way to overturn it.
    """
    if state not in STATES:
        return item, f"REFUSED: {state!r} is not a state"
    if not evidence.strip():
        return item, "REFUSED: a resolution needs its evidence, or it is a preference"
    try:
        out = replace(item, state=state, evidence=evidence,
                      falsifier=falsifier or item.falsifier,
                      updated=now or datetime.now(tz=UTC).isoformat())
    except ValueError as e:
        return item, f"REFUSED: {e}"
    return out, f"{item.state} -> {state}"


def ranked(items: list[Item]) -> list[Item]:
    """Work order: state priority, then blast radius. The widest wrong belief first."""
    return sorted(items, key=lambda i: (i.rank, -i.blast_radius, i.key))


def acquire_targets(items: list[Item]) -> dict[str, list[str]]:
    """dataset -> the items it would unblock. THE UNMEASURABLE PILE, INVERTED.

    Ranking datasets by how many blocked questions they open is the concrete form of "prioritise
    data by expected hypothesis-space expansion" -- and unlike a scored guess, this count is
    measured from questions the desk actually has.
    """
    out: dict[str, list[str]] = {}
    for i in items:
        if i.state != "UNMEASURABLE":
            continue
        for d in i.needs_data:
            out.setdefault(d, []).append(i.key)
    return dict(sorted(out.items(), key=lambda kv: (-len(kv[1]), kv[0])))


def summarise(items: list[Item]) -> dict[str, object]:
    """Report shape. An empty ledger is UNMEASURED, never a clean bill."""
    if not items:
        return {"items": 0, "tally": {},
                "headline": ("EMPTY LEDGER -- which is a statement about what has been RECORDED, "
                             "never about what the desk knows. A desk with no recorded assumptions "
                             "has unrecorded ones"),
                "top": [], "acquisition_targets": {}}
    tally = Counter(i.state for i in items)
    order = ranked(items)
    contradicted = [i for i in order if i.state == "CONTRADICTED"]
    return {
        "items": len(items), "tally": dict(tally),
        "headline": (
            f"{len(contradicted)} CONTRADICTED belief(s), widest blast radius "
            f"{max((i.blast_radius for i in contradicted), default=0)}"
            if contradicted else
            f"{tally['ASSUMED']} load-bearing untested assumption(s); no active contradiction"),
        "top": [{"key": i.key, "state": i.state, "blast_radius": i.blast_radius,
                 "statement": i.statement, "falsifier": i.falsifier} for i in order[:20]],
        "acquisition_targets": acquire_targets(items),
        "note": ("assumptions, contradictions and unknowns are ONE object at three confidence "
                 "levels; three registries could not see the transitions, and the transitions are "
                 "the research signal"),
    }


def render(items: list[Item], *, limit: int = 10) -> str:
    if not items:
        return ("unknowns ledger EMPTY -- a statement about what has been recorded, not about what "
                "the desk knows")
    lines: list[str] = []
    for i in ranked(items)[:limit]:
        radius = f" (blast radius {i.blast_radius})" if i.blast_radius else ""
        lines.append(f"[{i.state}]{radius} {i.key}: {i.statement}")
        if i.state in _BELIEF_STATES:
            lines.append(f"    falsified by: {i.falsifier}")
        if i.needs_data:
            lines.append(f"    needs data: {', '.join(i.needs_data)}")
    return "\n".join(lines)
