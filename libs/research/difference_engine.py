"""THE DIFFERENCE ENGINE — two research corpora, and the only part worth paying for.

THE PROBLEM. The desk runs a primary researcher and a set of external seats. Given the same brief
they overlap heavily, and the overlap is the expensive part: it is paid for twice and adds nothing.
The valuable output of a second intelligence is the DIFFERENCE — what one found and the other did
not, and above all where they CONTRADICT.

`RESIDUAL_MANDATE` tells a seat to hunt the residual and to label each item. That is necessary and
not sufficient: a label is the seat's OWN opinion about whether the desk already knew something,
and a seat cannot be the judge of what it was never shown. This module computes the classification
from the two corpora instead of trusting either side's account of them.

FIVE CLASSES, and the ranking is the point:

    CONTRADICTION   both address the same mechanism and disagree      -> HIGHEST value
    A_ONLY / B_ONLY one corpus has it and the other does not          -> residual value
    SAME_EFFECT     same effect claimed via DIFFERENT mechanisms      -> possible independence
    AGREEMENT       both reached it independently                     -> evidence, not waste

CONTRADICTION RANKS FIRST AND NOT BECAUSE DISAGREEMENT IS TRUTH. Neither side is more likely to be
right. A contradiction is valuable because it localises UNCERTAINTY: two competent searches reached
opposite conclusions, so an experiment there resolves something, whereas an experiment where both
agree mostly confirms. The engine never picks a winner — that is the validator's job, and a module
that adjudicated its own inputs would be the bypass this desk keeps building fences against.

AGREEMENT IS NOT DISCARDED, and that is a deliberate correction to the obvious design. Overlap
removal that DELETES the overlap throws away independent convergence, which is real evidence when
the two searches did not read each other. It is kept, reported, and flagged — with the provenance
caveat `convergence` already established: two observers who read the same paper are one observer.

MATCHING IS ON MECHANISM, NOT WORDS. Two descriptions of "funding flips negative before a squeeze"
in different vocabularies are one claim; "momentum works" in two vocabularies is two claims wearing
one phrase. The mechanism key is supplied by the caller (`mechanism_fingerprint` is the intended
source) so this module never invents a similarity judgement it cannot defend.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

__all__ = [
    "CLASS_RANK",
    "Claim",
    "Difference",
    "diff",
    "render",
    "summarise",
]


@dataclass(frozen=True)
class Claim:
    """One corpus's position on one mechanism.

    `direction` is the SIGN of the claim -- what the corpus says happens. Two claims on the same
    mechanism with opposite directions are a contradiction; with the same direction, agreement.
    `None` means the corpus raised the mechanism without committing, which is a lead rather than a
    position and must never be scored as agreement with whatever the other side said.
    """

    mechanism: str
    corpus: str
    direction: str | None = None      # e.g. "positive" | "negative" | None
    effect: str = ""                  # what OUTCOME is claimed, for SAME_EFFECT detection
    detail: str = ""
    source: str = ""
    #: Set only when the corpus recorded where the claim came from. Absence is not independence.
    provenance_recorded: bool = False


#: Order is the priority the desk works them in. Contradiction first: it localises uncertainty,
#: which is the only thing an experiment can spend itself resolving.
CLASS_RANK: tuple[str, ...] = (
    "CONTRADICTION", "A_ONLY", "B_ONLY", "SAME_EFFECT_DIFFERENT_MECHANISM", "AGREEMENT",
)


@dataclass(frozen=True)
class Difference:
    """One classified mechanism, with the reason and what to do about it."""

    mechanism: str
    classification: str
    reason: str
    action: str
    a: tuple[Claim, ...] = field(default_factory=tuple)
    b: tuple[Claim, ...] = field(default_factory=tuple)
    caveats: tuple[str, ...] = field(default_factory=tuple)

    @property
    def rank(self) -> int:
        return CLASS_RANK.index(self.classification)


def _directions(claims: tuple[Claim, ...]) -> set[str]:
    return {c.direction for c in claims if c.direction}


def diff(a: list[Claim], b: list[Claim], *, a_name: str = "A", b_name: str = "B",
         ) -> list[Difference]:
    """Classify every mechanism appearing in either corpus. Ranked, contradictions first.

    A MECHANISM RAISED WITHOUT A DIRECTION IS NEVER AGREEMENT. `direction=None` means the corpus
    surfaced the mechanism and did not commit; scoring that as agreement with the other side's
    position would manufacture convergence out of a shrug, which is the cheapest possible way to
    make two searches look like they confirmed each other.
    """
    keys = sorted({c.mechanism for c in (*a, *b)})
    by_a = {k: tuple(c for c in a if c.mechanism == k) for k in keys}
    by_b = {k: tuple(c for c in b if c.mechanism == k) for k in keys}
    out: list[Difference] = []

    # SAME_EFFECT needs a cross-mechanism view: two DIFFERENT mechanisms claiming one outcome.
    effects: dict[str, set[str]] = {}
    for c in (*a, *b):
        if c.effect:
            effects.setdefault(c.effect, set()).add(c.mechanism)

    for k in keys:
        ca, cb = by_a[k], by_b[k]
        shared_effect = any(
            c.effect and len(effects.get(c.effect, set())) > 1 for c in (*ca, *cb))
        if ca and not cb:
            out.append(Difference(
                k, "A_ONLY", f"{a_name} raised it; {b_name} did not",
                f"residual for {b_name}: was it never searched, or searched and dismissed? Only "
                "the second is information, and only the record can say which",
                ca, cb))
            continue
        if cb and not ca:
            out.append(Difference(
                k, "B_ONLY", f"{b_name} raised it; {a_name} did not",
                f"residual for {a_name}: test it, or record why it cannot be tested. A pedigree "
                "rejection is forbidden (L1.53a) -- only unexecutable, already-killed or measured",
                ca, cb))
            continue

        da, db = _directions(ca), _directions(cb)
        if da and db and not (da & db):
            out.append(Difference(
                k, "CONTRADICTION",
                f"{a_name} says {sorted(da)}, {b_name} says {sorted(db)} on the same mechanism",
                "HIGHEST-VALUE EXPERIMENT. Two competent searches reached opposite conclusions, so "
                "a test here resolves something rather than confirming it. Do NOT adjudicate "
                "between the corpora -- neither is more likely to be right, and the point is that "
                "the uncertainty is now localised",
                ca, cb))
            continue
        if not da or not db:
            out.append(Difference(
                k, "SAME_EFFECT_DIFFERENT_MECHANISM" if shared_effect else "A_ONLY",
                "one corpus raised the mechanism WITHOUT committing to a direction",
                "an uncommitted mention is a LEAD, never agreement -- scoring it as agreement "
                "manufactures convergence out of a shrug. Ask the uncommitted side for a "
                "direction, or test it directly",
                ca, cb,
                ("direction missing on one side: this is not a measured disagreement and not a "
                 "measured agreement",)))
            continue

        caveats: list[str] = []
        if not all(c.provenance_recorded for c in (*ca, *cb)):
            caveats.append(
                "PROVENANCE NOT RECORDED on at least one side, so independent convergence cannot "
                "be distinguished from two readings of one source. The apparent agreement is an "
                "UPPER BOUND on its own evidential weight (GAP #85)")
        out.append(Difference(
            k, "AGREEMENT", f"both corpora claim {sorted(da)}",
            "KEPT, NOT DISCARDED. Overlap removal that deletes the overlap throws away "
            "independent convergence, which is real evidence when the searches did not read each "
            "other. It buys a QUEUE PLACE, never a lower bar",
            ca, cb, tuple(caveats)))

    out.sort(key=lambda d: (d.rank, d.mechanism))
    return out


def summarise(diffs: list[Difference], *, a_name: str = "A",
              b_name: str = "B") -> dict[str, object]:
    """Report shape. THE HEADLINE IS THE RESIDUAL RATE, because that is what the second seat buys.

    A pair of corpora that is 95% AGREEMENT is telling the desk it is paying twice for one search.
    That is a finding about the RESEARCH PROCESS, and it is the number the model/prompt attribution
    layer needs in order to decide whether a seat is earning its budget.
    """
    tally = Counter(d.classification for d in diffs)
    total = max(len(diffs), 1)
    residual = tally["A_ONLY"] + tally["B_ONLY"] + tally["CONTRADICTION"]
    return {
        "corpora": [a_name, b_name],
        "mechanisms": len(diffs),
        "tally": dict(tally),
        "residual_rate": round(residual / total, 4),
        "contradictions": [d.mechanism for d in diffs if d.classification == "CONTRADICTION"],
        "headline": (
            f"residual {residual}/{len(diffs)} -- " + (
                "the second corpus is earning its budget" if residual / total >= 0.2 else
                f"only {residual / total:.0%} of mechanisms are residual: the two searches are "
                "largely the SAME search, and the desk is paying twice for one. That is a finding "
                "about the research process, not about the market")),
        "note": ("AGREEMENT is kept rather than removed -- independent convergence is evidence. "
                 "CONTRADICTION ranks first because it localises uncertainty, not because "
                 "disagreement is truth; this module never picks a winner"),
    }


def render(diffs: list[Difference], *, limit: int = 10) -> str:
    lines: list[str] = []
    for d in diffs[:limit]:
        lines.append(f"[{d.classification}] {d.mechanism} -- {d.reason}")
        for c in d.caveats:
            lines.append(f"    caveat: {c}")
    return "\n".join(lines) or "no mechanisms in either corpus -- UNMEASURED, not agreement"
