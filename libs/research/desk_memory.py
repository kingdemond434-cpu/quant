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

#: Injection weight of a lesson that a TEST already enforces mechanically.
#:
#: THIS CONSTANT IS THE DIFFERENCE BETWEEN COMPOUNDING AND PLATEAUING, so it is worth stating why.
#: A fixed budget with a growing ledger saturates: lesson 60 displaces lesson 40, and the desk
#: stops accumulating even though it keeps learning. The only escape that does not mean forgetting
#: is GRADUATION -- converting a lesson from something an agent must READ AND REMEMBER into
#: something a test CHECKS MECHANICALLY. A graduated lesson keeps its enforcement forever at zero
#: context cost, and hands its budget back to a lesson that no test can catch.
#:
#: NOT zero, deliberately. A test locks one property in one file; the lesson generalises to code
#: that does not exist yet. "A `> 0` guard does not survive floating-point dust" is enforced in
#: volatility_signals.py and still worth telling whoever writes the next guard. So graduation
#: demotes, it does not delete.
#:
#: 0.35 is set so an enforced CAPITAL lesson (5 x 0.35 = 1.75) ranks below an unenforced WASTED
#: one (3.0). That ordering is the point: injected context should be spent on what a machine
#: cannot catch, because everything a machine can catch should be caught by the machine.
ENFORCED_WEIGHT = 0.35


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
    enforced_by: str = ""
    #: Set by load() after CHECKING the named test exists. Never trusted from the file -- an
    #: unverifiable enforced_by must not buy a budget discount, or the field becomes a way to
    #: smuggle lessons out of the corpus by writing a path that resolves to nothing.
    enforced_verified: bool = False

    @property
    def score(self) -> float:
        """Cost of ignorance, amplified by how often the desk has had to re-learn it, discounted
        when a test already enforces it mechanically.

        log2 rather than linear on the recurrence term: the 2nd occurrence is the strong signal
        (it proves the first lesson did not stick); the 8th is more of the same and should not be
        able to crowd out every capital-class lesson on its own.
        """
        w = COST_WEIGHT.get(self.cost, 1)
        base = w * (1.0 + math.log2(max(self.recurrence, 1)))
        return base * (ENFORCED_WEIGHT if self.enforced_verified else 1.0)

    def render(self) -> str:
        mark = f"  [enforced by {self.enforced_by}]" if self.enforced_verified else ""
        return f"- {self.lesson.strip()}{mark}\n    EVIDENCE: {self.evidence.strip()}"


def _test_exists(ref: str, root: Path | None = None) -> bool:
    """Does `tests/x.py::test_name` name a test that is really there?

    FAILS CLOSED. An enforced_by that cannot be resolved returns False, so the lesson keeps its
    full weight and stays in the corpus. The alternative -- trusting the field -- means a typo,
    a renamed test or a deleted file silently drops a paid-for lesson out of every organ's
    context while the ledger still claims it is handled. That is the exact failure this whole
    module exists to prevent, reintroduced one level down.

    CLASS-QUALIFIED REFS RESOLVE TOO (2026-08-01). This split on the FIRST `::` and treated the
    whole remainder as a function name, so `test_x.py::TestGroup::test_case` -- pytest's standard
    form and the dominant style in this repo (tests/ops/test_carryover.py is entirely classes) --
    could never resolve. The failure was silent and pointed the wrong way: a lesson genuinely
    covered by a class-based test was REFUSED graduation, kept full weight, and was then squeezed
    out of the char budget by newer lessons, reaching no organ at all. Fail-closed protected the
    weight but not the outcome.
    """
    if "::" not in ref:
        return False
    parts = [s.strip() for s in ref.split("::")]
    rel, name = parts[0], parts[-1]
    p = (root or _ROOT) / rel
    if not p.exists():
        return False
    src = p.read_text("utf-8", errors="ignore")
    # Every intermediate segment must be a real class, so a typo'd container cannot pass on the
    # strength of a same-named method elsewhere in the file.
    if any(f"class {seg}" not in src for seg in parts[1:-1]):
        return False
    return f"def {name}(" in src


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
        ref = str(row.get("enforced_by", "")).strip()
        out.append(Lesson(
            id=str(row["id"]), learned=str(row["learned"]), cost=str(row["cost"]),
            lesson=str(row["lesson"]), evidence=str(row["evidence"]),
            recurrence=int(row.get("recurrence", 1)),
            tags=tuple(row.get("tags", ())), source=str(row.get("source", "")),
            enforced_by=ref,
            # VERIFIED, never trusted. See _test_exists: a stale or mistyped reference must not
            # buy the budget discount, or the field becomes a silent way out of the corpus.
            enforced_verified=bool(ref) and _test_exists(ref, p.parent.parent),
        ))
    out.sort(key=lambda item: (-item.score, item.id))
    return out


def broken_enforcement(path: Path | None = None) -> list[Lesson]:
    """Lessons claiming a test that does not resolve.

    A DEFECT, not a warning. The ledger says the property is mechanically guarded, the guard is
    missing, and the lesson is still carrying full weight in a budget that is already binding --
    so the desk is paying context for a claim it also believes is automated. Surfaced by
    scripts/learn.py audit and by max_audit.
    """
    p = path or LEDGER
    if not p.exists():
        return []
    out: list[Lesson] = []
    for line in p.read_text("utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        row = json.loads(line)
        ref = str(row.get("enforced_by", "")).strip()
        if row.get("retired") or not ref:
            continue
        if not _test_exists(ref, p.parent.parent):
            out.append(Lesson(id=str(row["id"]), learned=str(row["learned"]),
                              cost=str(row["cost"]), lesson=str(row["lesson"]),
                              evidence=str(row["evidence"]), enforced_by=ref))
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
    full = False
    for item in items:
        block = item.render()
        # STRICT RANK, and the `full` latch is the whole reason this is not a greedy pack. Greedy
        # packing skips an over-long lesson and takes a shorter lower-scoring one behind it, which
        # silently lets a terse hygiene note outrank a verbose capital-class lesson -- at which
        # point the budget is not a ranking, it is a length contest. The moment one lesson does
        # not fit, everything below it in rank is dropped too, so what reaches an organ is always
        # a strict prefix of the ranking. Costs a little unused budget; buys the invariant.
        if not full and used + len(block) + 1 <= budget:
            kept.append(item)
            used += len(block) + 1
        else:
            full = True
            dropped.append(item)
    if not kept:
        return "", dropped
    body = "\n".join(item.render() for item in kept)
    return _HEADER + body + _FOOTER, dropped


def unreached(budget: int = BUDGET_CHARS,
              path: Path | None = None) -> tuple[list[Lesson], list[Lesson]]:
    """Split the overflow into what is genuinely LOST and what is merely DEMOTED.

    NOT EVERY DROPPED LESSON IS A LOSS, and conflating the two is how this fence dies. A lesson
    that has graduated to a test is enforced MECHANICALLY on every CI run; ranking it out of the
    char budget is precisely what ENFORCED_WEIGHT exists to cause, so its absence from an organ's
    context costs nothing. Measured 2026-08-01: 31 lessons overflowed and 20 of them were
    graduated, so the raw count overstated the real loss by 2.8x. A number that cries wolf like
    that trains its reader to skip it, and a fence nobody reads is a fence that has been switched
    off -- the expensive failure, because the 11 genuine losses hide inside the noise.

    THE DISCOUNT IS SAFE ONLY BECAUSE `enforced_verified` IS EARNED, NEVER CLAIMED. load() sets it
    by RESOLVING the named test on disk and fails closed, so a typo, a renamed test or a deleted
    file leaves the lesson at full weight and it lands here in `lost` where it belongs. Without
    that check this split would be a way to smuggle a paid-for lesson out of every organ's context
    by writing a path that points at nothing.
    """
    _text, over = corpus(budget, path)
    lost = [item for item in over if not item.enforced_verified]
    demoted = [item for item in over if item.enforced_verified]
    return lost, demoted


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
