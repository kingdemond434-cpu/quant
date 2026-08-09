"""INJECT THE REVIEW RUBRIC. The best artifact any transcript produced, and nothing was reading it.

PROVENANCE. The "dual-brain" transcript (2026-08-01 batch) argued for having a second model with
different blind spots review the first's work -- correct in principle, because you cannot mark
your own exam. The desk's response was to note that the reviewing MODEL is interchangeable
(Codex, another Claude, a person) while KNOWING WHAT TO LOOK FOR ON THIS DESK is not, and to
write docs/research/ADVERSARIAL_REVIEW_RUBRIC.md: ten defect classes, each with the real shipped
instance that produced it. A generic "review this code" prompt finds none of them; it finds style.

WHY THIS MODULE EXISTS. That rubric is, by measured outcome, the highest-quality artifact any
mined transcript produced -- and `grep -rn ADVERSARIAL_REVIEW_RUBRIC` across the entire repo
returns ONE hit, in scripts/max_audit.py, as a terminal-artifact EXCLUSION. Nothing injects it.
It has worked exactly when a human or agent happened to remember it, which on 2026-08-01 caught
three real defects in code written that same morning:

    a `> 0` guard that floating-point dust walked through, producing a 1.4e31 signal
    a docstring claiming Garman-Klass can go negative when the algebra proves it cannot
    64.4 "independent bets" reported from 29 assets, the estimator extrapolating past its domain

Three real bugs, from remembering. That is the entire argument for wiring it: a checklist that
only fires when someone recalls it is not a control, and the desk has a name for this exact
shape -- lesson L0030, knowledge that is not injected at runtime does not exist.

WHY IT PARSES THE DOC RATHER THAN RESTATING IT. A second copy of the ten classes here would drift
from the markdown within a month and the desk would then have two rubrics. The doc is the source;
this reads it. If the doc is edited the injection changes on the next call, and if the doc is
deleted or gutted `audit()` reports it loudly rather than silently injecting nothing -- an empty
rubric that reads as a passed check is the failure this whole module is about.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
RUBRIC = _ROOT / "docs/research/ADVERSARIAL_REVIEW_RUBRIC.md"

#: The rubric had exactly ten classes when it was written. This is a CHANGE DETECTOR, not a cap:
#: adding an eleventh is expected and good, and the audit reports the count so a class silently
#: VANISHING (the failure that matters) is visible. Deleting classes to make this pass would be
#: editing the guard to fit the violation.
EXPECTED_CLASSES = 10

_HEAD = """
=== ADVERSARIAL REVIEW RUBRIC -- the defect classes this desk has actually shipped ===
Every class below was found HERE, in production code, usually by measurement after the fact. A
generic "review this code" pass finds none of them; it finds style. When you review, audit or
verify anything on this desk, walk these explicitly and say which ones you checked.
"""

_TAIL = """
The rule that generates all ten: a thing is only true if something READS it. A gate nobody calls,
a constant nobody produces, an artifact nobody opens, a correction applied where another already
applies -- each looks correct in isolation and is inert or harmful in place. Check the readers.
"""


@dataclass(frozen=True)
class DefectClass:
    number: int
    name: str
    body: str

    def render(self) -> str:
        return f"{self.number}. {self.name}\n{self.body.strip()}"


def parse(path: Path | None = None) -> list[DefectClass]:
    """The rubric's classes, read from the markdown rather than duplicated here."""
    p = path or RUBRIC
    if not p.exists():
        return []
    text = p.read_text("utf-8", errors="ignore")
    out: list[DefectClass] = []
    # Split on the "### N. Name" headings; everything until the next heading is the body.
    parts = re.split(r"^###\s+(\d+)\.\s+(.+)$", text, flags=re.MULTILINE)
    for i in range(1, len(parts) - 2, 3):
        num, name, body = parts[i], parts[i + 1], parts[i + 2]
        body = body.split("\n## ")[0]          # stop at the next top-level section
        out.append(DefectClass(number=int(num), name=name.strip(), body=body.strip()))
    return out


#: Budget for the injected block. SET BY MEASUREMENT: the ten classes with their real shipped
#: instances render at 4,437 chars, and a 4,000 budget silently dropped every instance and
#: injected bare titles. The instances are the entire value -- "gate that fails open" is a phrase
#: anyone can nod at, while "beats_baselines returns True when no benchmark is supplied and no
#: production caller supplies one" is a thing you go and check. 6,000 leaves headroom for an
#: eleventh class without re-tuning; the titles-only fallback stays as a floor, not as the
#: expected path.
RUBRIC_BUDGET_CHARS = 6_000


def preamble(*, max_chars: int = RUBRIC_BUDGET_CHARS, path: Path | None = None) -> str:
    """The rubric as an injectable prompt block, budgeted.

    RETURNS EMPTY WHEN THE RUBRIC IS MISSING, and that is deliberate rather than lazy: a caller
    prepending "" gets its normal prompt, whereas raising would take down every review organ
    because a documentation file moved. `audit()` is what makes the absence loud. This is the same
    split the memory layer uses -- a broken enrichment must never stop an organ from running.

    TITLES ONLY WHEN THE BODIES WILL NOT FIT. Ten classes with their real instances run past a
    reasonable prompt budget; the instances are what make the classes concrete, so they are kept
    while they fit and the fallback degrades to names rather than truncating mid-example. A
    half-quoted defect instance is worse than a bare title -- it reads as complete and is not.
    """
    classes = parse(path)
    if not classes:
        return ""
    full = _HEAD + "\n\n".join(c.render() for c in classes) + _TAIL
    if len(full) <= max_chars:
        return full
    titles = "\n".join(f"{c.number}. {c.name}" for c in classes)
    return (_HEAD + titles + "\n(bodies omitted for budget -- read "
            "docs/research/ADVERSARIAL_REVIEW_RUBRIC.md for the shipped instance behind each)"
            + _TAIL)


def audit(path: Path | None = None) -> dict[str, object]:
    """Is the rubric present, parseable, and still carrying its classes?

    Exists because the only thing worse than an unwired rubric is a wired one that quietly
    resolves to nothing -- the injection would keep succeeding, the review organs would keep
    reporting that they applied it, and the classes would be gone.
    """
    p = path or RUBRIC
    classes = parse(p)
    problems: list[str] = []
    if not p.exists():
        problems.append(f"{p} is absent -- every review organ is injecting an empty rubric")
    elif not classes:
        problems.append(f"{p} exists but no '### N. Name' classes parsed -- the format changed "
                        "and the injection is silently empty")
    elif len(classes) < EXPECTED_CLASSES:
        problems.append(f"only {len(classes)} classes parsed, expected at least "
                        f"{EXPECTED_CLASSES} -- a class has vanished")
    return {
        "path": str(p), "exists": p.exists(), "n_classes": len(classes),
        "expected": EXPECTED_CLASSES,
        "classes": [f"{c.number}. {c.name}" for c in classes],
        "chars": len(preamble(path=p)), "problems": problems, "ok": not problems,
    }
