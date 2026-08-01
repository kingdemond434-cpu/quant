"""COMPOUNDING DESK MEMORY -- the lessons this desk has PAID for, ranked, budgeted, injected.

WHY THIS EXISTS. A model's weights do not update between sessions. Nothing this desk learns on
2026-08-01 is inside the model on 2026-08-02. The only thing that can actually compound is a
corpus that is READ AT RUNTIME by every organ, and on 2026-08-01 the desk had two of those and
neither worked:

  ops/principal_doctrine.txt      95,204 chars, injected into EVERY organ call -- 6.0x past the
                                  16,000-char bloat threshold max_audit itself enforces. Past that
                                  point the stacked blocks dilute the mission instructions they
                                  are supposed to sharpen. More knowledge made organs WORSE.
  docs/institutional_knowledge.md 67,802 chars of genuinely hard-won lessons -- every venue
                                  incident, every phantom-PnL autopsy, every dead-man fire --
                                  referenced only from Python COMMENTS. It reaches no prompt, no
                                  runner, no organ. It is a diary, not a memory.

So the desk was simultaneously over-fed and amnesiac, and both got worse as it learned more.

THE FIX IS A FIXED BUDGET WITH COMPETITION. Lessons live in an append-only ledger. They are
SCORED, and only the top ones fitting a hard character budget are injected. Growing the corpus
therefore makes organs smarter WITHOUT making their context longer: a new lesson has to outrank
an existing one to get in. That is the property that lets memory accumulate for years without
ever becoming the next 95k file.

THE RANKING, and the second term is the whole idea:

    score = COST_WEIGHT[cost_class] x (1 + log2(recurrence))

  COST is what it cost the desk to NOT know this -- capital lost, or a false belief about itself,
  or compute burned on a known-dead path. Not how interesting it is.
  RECURRENCE is how many times the desk has RE-LEARNED it. A lesson re-learned four times scores
  3x a one-off, and it should: recurrence is direct evidence the lesson is not sticking, and a
  lesson that is not sticking is precisely the one worth spending context on. The desk thereby
  measures its own repeated failures and promotes them, automatically, without anyone deciding to.

NO RECENCY DECAY. An incident from July is not less true in August. A lesson leaves the corpus
exactly one way: someone retires it with a named falsifier that has actually arrived. Silence is
not retirement.

NOTHING IS SILENTLY DROPPED. corpus() returns what it cut along with what it kept. A memory layer
that quietly truncated would recreate the failure it exists to fix -- the desk believing it
carries knowledge it does not carry.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
LEDGER = _ROOT / "docs/desk_lessons.jsonl"

#: Hard ceiling on what memory costs every organ, every call. The doctrine file reached 95k
#: because nothing ever said no; this says no by construction, and the pressure it creates is the
#: mechanism -- past this point a lesson only enters by displacing a weaker one.
#:
#: SET BY MEASUREMENT, not by taste. The seed corpus of 31 paid-for lessons renders at ~11.6k, so
#: 6k (the first guess) silently withheld 16 of them on day one -- an under-provisioned corpus
#: masquerading as a well-ranked one. 12k carries every lesson the desk has actually paid for
#: while staying 7.9x smaller than the doctrine it rides beside. The ceiling is meant to bind
#: LATER, when lessons genuinely compete; a ceiling that binds on day one is just data loss.
#: Raising it again is the wrong reflex and is how the doctrine got to 95k -- retire a lesson
#: whose falsifier arrived instead.
BUDGET_CHARS = 12_000

#: What it cost the desk NOT to know this. The scale is about consequence, never about how
#: interesting the lesson is; "interesting" is how a corpus fills with things nobody acts on.
COST_WEIGHT: dict[str, int] = {
    "capital": 5,   # real money lost, or the book flattened
    "blind": 4,     # the desk believed something false ABOUT ITSELF and acted on it
    "wasted": 3,    # compute, calendar time, or multiplicity budget spent on a known-dead path
    "slow": 2,      # the right answer reached inefficiently
    "hygiene": 1,   # correctness housekeeping with no measured loss behind it yet
}

_REQUIRED = ("id", "learned", "cost", "lesson", "evidence")


@dataclass(frozen=True)
class Lesson:
    id: str
    learned: str
    cost: str
    lesson: str
    evidence: str
    recurrence: int = 1
    tags: tuple[str, ...] = ()
    source: str = ""
    retired: str = ""

    @property
    def score(self) -> float:
        """Cost of ignorance, amplified by how often the desk has had to re-learn it.

        log2 rather than linear on purpose: the 2nd occurrence is the strong signal (it proves the
        first lesson did not stick); the 8th is more of the same and should not be able to crowd
        out every capital-class lesson on its own.
        """
        w = COST_WEIGHT.get(self.cost, 1)
        return w * (1.0 + math.log2(max(self.recurrence, 1)))

    def render(self) -> str:
        return f"- {self.lesson.strip()}\n    EVIDENCE: {self.evidence.strip()}"


def load(path: Path | None = None) -> list[Lesson]:
    """Every ACTIVE lesson, highest-scoring first. Retired rows stay in the file as history and
    are excluded here -- the ledger is append-only so that a retired lesson can be audited later,
    which is impossible if retirement means deletion."""
    p = path or LEDGER
    if not p.exists():
        return []
    out: list[Lesson] = []
    for line in p.read_text("utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        row = json.loads(line)
        if row.get("retired"):
            continue
        out.append(Lesson(
            id=str(row["id"]), learned=str(row["learned"]), cost=str(row["cost"]),
            lesson=str(row["lesson"]), evidence=str(row["evidence"]),
            recurrence=int(row.get("recurrence", 1)),
            tags=tuple(row.get("tags", ())), source=str(row.get("source", "")),
        ))
    out.sort(key=lambda item: (-item.score, item.id))
    return out


def validate_row(row: dict[str, object]) -> list[str]:
    """Why a row is REFUSED, empty when it is admissible.

    The bar is deliberately not about writing quality. A lesson with no evidence is an opinion,
    and a corpus of opinions injected into every organ is worse than no corpus -- it launders
    guesses into doctrine. The evidence field must name where the thing was measured.
    """
    problems = []
    for k in _REQUIRED:
        if not str(row.get(k, "")).strip():
            problems.append(f"missing required field: {k}")
    cost = str(row.get("cost", ""))
    if cost and cost not in COST_WEIGHT:
        problems.append(f"cost must be one of {sorted(COST_WEIGHT)}, got {cost!r}")
    ev = str(row.get("evidence", "")).strip()
    if ev and len(ev) < 12:
        problems.append("evidence too thin to be checkable -- name a file, a number, or a date")
    les = str(row.get("lesson", "")).strip()
    if les and len(les) < 25:
        problems.append("lesson too short to change behaviour -- state what to DO differently")
    return problems


def corpus(budget: int = BUDGET_CHARS, path: Path | None = None) -> tuple[str, list[Lesson]]:
    """The injected text, plus EVERY lesson that did not fit.

    Returning the dropped list is not a nicety. A memory layer that truncated silently would
    reproduce the exact defect it was built to fix: the desk believing it carries knowledge it
    does not carry. Callers are expected to surface the overflow, and check_memory_reach does.
    """
    items = load(path)
    kept: list[Lesson] = []
    dropped: list[Lesson] = []
    used = len(_HEADER) + len(_FOOTER)
    for item in items:
        block = item.render()
        if used + len(block) + 1 <= budget:
            kept.append(item)
            used += len(block) + 1
        else:
            dropped.append(item)
    if not kept:
        return "", dropped
    body = "\n".join(item.render() for item in kept)
    return _HEADER + body + _FOOTER, dropped


_HEADER = """
=== DESK MEMORY -- lessons this desk PAID for, ranked by what ignorance cost (injected at
runtime from docs/desk_lessons.jsonl; do not summarise, do not skip) ===
These are not principles. Each one is a specific thing that went wrong here, with the evidence
still on disk. They are ordered by cost x how many times the desk has had to re-learn them, so
the top of this list is where this desk repeatedly fails. Read it as a list of your own likely
mistakes, not as background.
"""

_FOOTER = """
When you learn something durable, record it:  python scripts/learn.py add ...
A lesson nobody records is one the desk pays for twice.
"""


def next_id(path: Path | None = None) -> str:
    p = path or LEDGER
    if not p.exists():
        return "L0001"
    n = 0
    for line in p.read_text("utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        raw = str(json.loads(line).get("id", "L0000")).lstrip("L")
        n = max(n, int(raw) if raw.isdigit() else 0)
    return f"L{n + 1:04d}"


def append(row: dict[str, object], path: Path | None = None) -> str:
    """Append one validated lesson. Raises on an inadmissible row rather than writing it."""
    problems = validate_row(row)
    if problems:
        raise ValueError("; ".join(problems))
    p = path or LEDGER
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return str(row["id"])


def bump(lesson_id: str, path: Path | None = None) -> int:
    """Record that a lesson was RE-LEARNED, and return its new recurrence count.

    This is the single most valuable write in the module. Re-learning is the desk telling itself
    which lessons do not stick, and the ranking converts that straight into injected context. It
    rewrites in place (rather than appending) because recurrence is a property of one lesson, not
    a new lesson -- two rows for one lesson would double-count it into the top of the corpus.
    """
    p = path or LEDGER
    lines = p.read_text("utf-8").splitlines()
    out, found = [], 0
    for line in lines:
        s = line.strip()
        if not s or s.startswith("#"):
            out.append(line)
            continue
        row = json.loads(s)
        if str(row.get("id")) == lesson_id:
            found = int(row.get("recurrence", 1)) + 1
            row["recurrence"] = found
            out.append(json.dumps(row, ensure_ascii=False))
        else:
            out.append(line)
    if not found:
        raise KeyError(f"no lesson {lesson_id}")
    p.write_text("\n".join(out) + "\n", "utf-8")
    return found
