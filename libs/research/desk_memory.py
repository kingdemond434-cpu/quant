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

AND THE BUDGET IS SPENT PER ORGAN, NOT ONCE FOR EVERYONE (2026-09-05). A fixed budget with one
global ranking saturates the moment the ledger outgrows it: measured at 228 lessons, exactly 25
were reaching anybody and 106 the desk had paid for were read by nothing at all. The ceiling was
never the problem -- the assumption that the gateway and the free-data miner need the SAME lessons
was. `corpus(organ=...)` spends the identical 12,000 chars on the lessons that apply to the organ
reading them, which took reach from 25 lessons to 141 without any organ receiving one extra
character. `reach()` is the number to watch: what fraction of what the desk paid for is read by
somebody. See the block above `relevance` for why routing needs BOTH rarity and repetition.
"""

from __future__ import annotations

import json
import math
import re
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

#: Every field a row may carry. NOT decoration: the ledger is an append-only text file, and a row
#: written by hand instead of by `scripts/learn.py add` can be shaped however its writer felt.
#:
#: MEASURED 2026-09-05, and this is the reason the set exists. Three rows (L0228-L0230) were
#: appended with a parallel vocabulary -- `recorded` for `learned`, `recurrences` for `recurrence`,
#: `tag` for `tags`, `accept_uninjected` for `accepted_uninjected`, plus a stored `weight` and
#: `injected` that are both DERIVED. load() raised KeyError on the first of them, which meant the
#: ENTIRE corpus failed to load: every organ that reads desk memory got nothing, silently, because
#: three rows out of 230 used the wrong noun. A memory layer that fails whole rather than
#: per-row is a memory layer one bad append can switch off.
#:
#: So malformed rows are now SKIPPED AND NAMED (see `malformed`), never fatal -- and never silent
#: either, because `tests/test_desk_memory.py` asserts the shipped ledger has none.
KNOWN_FIELDS = frozenset({
    "id", "learned", "cost", "recurrence", "lesson", "evidence", "tags", "source",
    "enforced_by", "enforcement_retired", "accepted_uninjected", "retired",
})

#: Wrong nouns seen in the wild, mapped to the right one. Used only to make the DIAGNOSTIC
#: actionable -- a row is never silently repaired by this, because silently accepting an alias is
#: how two vocabularies become permanent and how `weight` gets to disagree with `cost`.
_ALIASES: dict[str, str] = {
    "recorded": "learned",
    "recurrences": "recurrence",
    "tag": "tags",
    "accept_uninjected": "accepted_uninjected",
    "weight": "cost (weight is DERIVED: COST_WEIGHT[cost])",
    "injected": "enforced_by (injection is DERIVED, never stored)",
}

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

#: Characters of EVIDENCE carried into an organ's context, per lesson. The lesson itself is never
#: cut; see `Lesson.render` for why the two fields are treated differently.
#:
#: 160 IS A MEASURED TRADE, not a round number. Evidence is 46% of the rendered corpus. Dropping
#: it entirely would fit 37 lessons per organ instead of 19 -- and would turn the corpus into 37
#: assertions with nothing behind them, which is precisely the "opinions injected into every
#: organ" this module's admission bar exists to refuse. At 160 the head of the evidence still
#: carries the number and the source (it is written key-fact-first), the marker names the row for
#: anyone who wants the rest, and 24.6 lessons reach each organ instead of 18.8.
EVIDENCE_CHARS = 160


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
    #: The test this lesson USED to graduate to, and which no longer exists.
    #:
    #: A GRADUATION CAN BE UNDONE BY A DELETION SOMEWHERE ELSE, and when it is, the lesson has to
    #: come back to full weight and back into the corpus -- the property stopped being enforced,
    #: so the desk has to remember it again. Measured 2026-09-05: ten lessons named tests that
    #: were deleted along with the retired crypto desk (the Binance campaign panel, the OKX ticker
    #: redenomination, the Bybit bar shape, the cash-carry entry gate...). Blanking `enforced_by`
    #: is what makes them honest; recording WHICH test went is what stops the next reader
    #: concluding the lesson was never graduated and re-doing the work.
    enforcement_retired: str = ""
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
        """One lesson, as compactly as it can be stated without becoming unfalsifiable.

        THE LESSON IS NEVER TRUNCATED, THE EVIDENCE IS. They do different jobs: the lesson is the
        behaviour change, and a half-stated instruction is worse than none; the evidence exists so
        the claim is CHECKABLE, and a pointer that points is enough for that. Measured over the
        228-lesson ledger, evidence is 46% of the rendered corpus at a mean of 294 chars, and it
        is written key-fact-first -- "BIS WS_XRU: all 1,067,834 daily rows are titled..." -- so
        the head of it carries the number and the source that make the lesson believable.

        Capping it at EVIDENCE_CHARS takes the mean lesson from 639 chars to 459, which is 24.6
        lessons per organ instead of 18.8: a third more of what the desk has paid for reaching
        each organ, for the same 12,000 characters and no loss of any instruction.

        THE TRUNCATION IS MARKED AND THE ROW IS NAMED. `...(L0187 full)` is not decoration -- a
        silently shortened quote is a fabricated one, and the id is what lets a reader who doubts
        the claim open the ledger and read all of it.
        """
        mark = f"  [enforced by {self.enforced_by}]" if self.enforced_verified else ""
        ev = " ".join(self.evidence.split())
        if len(ev) > EVIDENCE_CHARS:
            ev = f"{ev[:EVIDENCE_CHARS].rstrip()}...({self.id} full)"
        return f"- {' '.join(self.lesson.split())}{mark}\n  EV: {ev}"


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


def _row_defects(row: dict[str, object]) -> list[str]:
    """Why a row cannot be TURNED INTO a Lesson, empty when it can.

    Distinct from `validate_row`, which grades whether a lesson is worth carrying (has evidence,
    says what to do differently). This grades whether the row is even readable, and it is the
    check `load` needs: a row can be perfectly admissible in content and still be unloadable
    because its writer called the date `recorded` instead of `learned`.
    """
    problems = []
    for k in _REQUIRED:
        if not str(row.get(k, "")).strip():
            hint = next((a for a, canon in _ALIASES.items()
                         if canon.split(" ")[0] == k and a in row), "")
            problems.append(f"missing {k}" + (f" (row calls it {hint!r})" if hint else ""))
    for k in sorted(set(row) - KNOWN_FIELDS):
        canon = _ALIASES.get(k)
        problems.append(f"unknown field {k!r}" + (f" -- did you mean {canon}?" if canon else ""))
    return problems


def malformed(path: Path | None = None) -> list[tuple[int, str, list[str]]]:
    """Rows `load()` had to skip: (line number, id if it has one, why).

    THE OTHER HALF OF SKIPPING RATHER THAN RAISING. Skipping keeps one bad append from switching
    the whole memory layer off; this keeps skipping from being silent. Surfaced by
    scripts/learn.py audit, and held at zero on the shipped ledger by a test -- so the tolerant
    reader never becomes a reason the ledger is allowed to rot.
    """
    p = path or LEDGER
    if not p.exists():
        return []
    out: list[tuple[int, str, list[str]]] = []
    for n, line in enumerate(p.read_text("utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            out.append((n, "", [f"unparseable JSON: {exc}"]))
            continue
        defects = _row_defects(row)
        if defects:
            out.append((n, str(row.get("id", "")), defects))
    return out


def load(path: Path | None = None, root: Path | None = None) -> list[Lesson]:
    """Every ACTIVE lesson, highest-scoring first. Retired rows stay in the file as history and
    are excluded here -- the ledger is append-only so that a retired lesson can be audited later,
    which is impossible if retirement means deletion.

    `root` EXISTS SO A CALLER CAN SCORE A LEDGER THAT IS NOT IN THE REPO. It defaults to the
    ledger's own grandparent, which is right for the real file. A caller probing a CANDIDATE
    corpus writes it to a scratch path, and without this the `enforced_by` references would then
    be resolved against the scratch directory, every graduated lesson would silently lose its
    discount, and the probe would answer a different question from the one that was asked.
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
        if row.get("retired"):
            continue
        # SKIPPED, NEVER FATAL. See KNOWN_FIELDS: one hand-appended row in a foreign vocabulary
        # used to raise KeyError here and take the whole corpus with it, so every organ silently
        # read no memory at all. Losing one lesson is a bounded cost; losing all of them because
        # of one is the failure this module exists to prevent. `malformed()` names what was
        # skipped and a shipped-ledger test holds the count at zero.
        if _row_defects(row):
            continue
        ref = str(row.get("enforced_by", "")).strip()
        out.append(Lesson(
            id=str(row["id"]), learned=str(row["learned"]), cost=str(row["cost"]),
            lesson=str(row["lesson"]), evidence=str(row["evidence"]),
            recurrence=int(row.get("recurrence", 1)),
            tags=tuple(row.get("tags", ())), source=str(row.get("source", "")),
            enforced_by=ref,
            enforcement_retired=str(row.get("enforcement_retired", "")).strip(),
            # VERIFIED, never trusted. See _test_exists: a stale or mistyped reference must not
            # buy the budget discount, or the field becomes a silent way out of the corpus.
            enforced_verified=bool(ref) and _test_exists(ref, root or p.parent.parent),
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


# ------------------------------------------------------------------ relevance routing
#
# WHY THE CORPUS IS ROUTED AND NOT JUST RANKED (2026-09-05). One global ranking against one 12,000
# char budget worked while the ledger was small. Measured today at 228 lessons -- 167 of them
# genuinely paid for by this desk, rendering to 103,492 chars -- exactly 25 fit. 142 paid-for
# lessons reached NO organ, and the corpus had gone back to being the diary it was built to
# replace, just with a ranking on the front.
#
# THE BUDGET IS NOT THE PROBLEM AND MUST NOT BE RAISED. It is 12,000 because organs measurably got
# WORSE past ~16k of stacked context: doctrine reached 95,204 chars precisely because every time it
# bound, somebody raised it. That number stays.
#
# WHAT WAS ACTUALLY WRONG IS THE ASSUMPTION THAT EVERY ORGAN NEEDS THE SAME LESSONS. The gateway
# does not need the lesson about a BIS dataflow mislabelling its own statistic; the free-data
# miner does not need the one about widening a fill bar to rescue a limit entry. Selecting per
# organ leaves the per-call budget untouched at 12,000 -- no organ reads one character more than
# before -- while the number of lessons that reach SOME organ rises with the ledger instead of
# saturating at 25. That is the difference between a memory that compounds and one that rotates.
#
# FAILS BACK TO THE GLOBAL RANKING. An unknown organ, or one whose vocabulary matches nothing,
# scores every lesson at relevance 0, and the ordering is exactly what it was before this existed.
# Routing can therefore only ever add reach; it cannot take a lesson away from an organ that was
# already getting it on rank alone.

#: How much a perfectly on-topic lesson may outrank an off-topic one. Multiplies the score, so
#: cost and recurrence still dominate: at 2.0 a fully-relevant `wasted` lesson (3.0 -> 9.0) can
#: overtake an irrelevant `capital` one (5.0), which is the intended trade -- a capital lesson
#: about something this organ cannot do is worth less TO THIS ORGAN than a directly applicable
#: cheaper one. It cannot invert the cost scale wholesale: the lift is bounded, so a relevant
#: hygiene note (1.0 -> 3.0) still ranks below an irrelevant capital lesson.
RELEVANCE_LIFT = 2.0

#: Share of an organ's budget reserved for the lessons most about THIS organ, regardless of what
#: they cost the desk. The rest goes to the desk-wide ranking, so the costliest lessons still lead
#: every organ's context. 0.4 was chosen as the smallest share that actually changes reach: at 0.0
#: it is the pure cost ranking (25 lessons reach an organ), at 0.4 the specific lessons have a
#: pool they cannot be crowded out of. Unspent topic budget is handed straight back to the cost
#: pool, so the reservation can never leave an organ with LESS context than it had.
TOPIC_SHARE = 0.4

#: Words that appear in so many lessons they carry no routing signal. Kept small on purpose: an
#: over-long stop list quietly deletes the vocabulary that distinguishes organs from each other.
_STOP = frozenset("""
a an and are as at be because been before but by can cannot could desk did do does for from get
had has have how if in into is it its more must never no not of on once one only or over own read
run runs same so than that the their then there these they this to too under until up use used
was what when where which while who why will with without would you your
""".split())  # noqa: SIM905 -- a prose block is the readable form for a word list this long

_TOKEN = re.compile(r"[a-z_][a-z0-9_]{2,}")


def _terms(text: str) -> set[str]:
    """Distinctive lowercase tokens, with snake_case split so `edge_search` also matches `search`.

    Splitting matters more than it looks: organ names and artifact names are snake_case while the
    prose of a lesson is not, so without the split an organ called `hourly_discovery` shares no
    token at all with a lesson that says "the discovery leg ran hourly".
    """
    out: set[str] = set()
    for tok in _TOKEN.findall(text.lower()):
        parts = [p for p in tok.split("_") if len(p) > 2]
        out.update(parts)
        if len(parts) > 1:
            out.add(tok)
    return out - _STOP


#: Tokens that name a LOCATION or a FORMAT rather than a subject. They are removed from an ORGAN's
#: vocabulary only -- a lesson that says "json" is still saying something, but an organ whose
#: terms include "json" matches every lesson in the ledger and routes nothing. Measured: without
#: this, `hourly_discovery` had 10 terms of which 6 were `data json reports desks mt5 state`, and
#: the relevance signal was almost entirely those six firing everywhere.
_GENERIC = frozenset("""
data json jsonl csv parquet txt md py sh ps1 cmd yaml yml log logs file files path paths dir
desks libs scripts ops docs tests reports report state states tmp out output outputs src bin
mt5 quant desk main run runs runner script new old current latest local remote root base
""".split())  # noqa: SIM905 -- as above: one line per idea beats a 40-element list literal

#: Weighted term hits at which a lesson counts as fully on-topic. SATURATING, not a fraction of
#: the lesson's own length: a lesson that names four of this organ's concrete nouns is about this
#: organ whether it says so in 30 words or 90. The first version divided by the lesson's term
#: count, which put every relevance in [0, 0.17] and left the lift too small to reorder anything --
#: the routing was present, measurable, and doing almost nothing.
_FULLY_RELEVANT_HITS = 6.0


#: An organ's vocabulary keeps only terms used by at most this share of organs. TF-IDF's idea in
#: one constant: a word every organ says identifies none of them.
#:
#: MEASURED, and both failure modes were reached before this existed. Restricted to names and
#: graph artifacts, `hourly_discovery` had 10 terms, 6 of them location nouns, and relevance
#: topped out at 0.17 -- too weak to reorder anything. Adding the organs' own prompts took
#: `cro_ai` to 989 terms and relevance saturated at 1.00 for the top NINE TENTHS of the ledger --
#: a constant, which routes exactly as well as no routing at all, and reach FELL to 26%. The
#: signal is in the middle: the words this organ uses that its neighbours do not.
DISTINCTIVE_MAX_SHARE = 0.34


#: A term entering an organ's vocabulary from its BRIEF must be repeated, and only the most
#: repeated survive. A word said once in a 20,000-char prompt is incidental to it; a word said
#: eight times is what the organ is for.
#:
#: THIS IS WHAT STOPS A LONG PROMPT FROM SWALLOWING THE LEDGER. Distinctiveness alone could not:
#: `cro_ai` has the longest brief on the desk and it is the ONLY organ using most of its words, so
#: every one of them survived a cross-organ filter and it kept 766 terms -- relevance 1.00 at the
#: median, which is a constant, which is no routing. Frequency and rarity have to be applied
#: together; either on its own is defeated by the other's failure mode. Names and graph artifacts
#: bypass both, because they are identifiers rather than prose and appearing once is all they do.
_BRIEF_MIN_COUNT = 2
_BRIEF_MAX_TERMS = 120


def _organ_vocabulary(organ: str, base: Path) -> set[str]:
    """Everything this organ says, before the distinctiveness filter."""
    terms = _terms(organ)
    try:
        from libs.ops.capability_graph import NODES
        want = terms | {organ.lower()}
        for n in NODES:
            name = str(getattr(n, "name", ""))
            if not name or (name.lower() not in want and not (_terms(name) & terms)):
                continue
            terms |= _terms(name)
            for attr in ("reads", "writes"):
                for art in getattr(n, attr, ()) or ():
                    terms |= _terms(str(art))
    except Exception:
        pass
    counts: dict[str, int] = {}
    for pat in (f"{organ}*prompt*.txt", f"run_{organ}.sh"):
        for p in sorted((base / "ops").glob(pat)) if (base / "ops").is_dir() else ():
            try:
                text = p.read_text("utf-8", errors="ignore")[:20_000]
            except OSError:
                continue
            for tok in _TOKEN.findall(text.lower()):
                for part in ([tok] if "_" not in tok else [tok, *tok.split("_")]):
                    if len(part) > 2:
                        counts[part] = counts.get(part, 0) + 1
    brief = [t for t, n in counts.items() if n >= _BRIEF_MIN_COUNT]
    brief.sort(key=lambda t: (-counts[t], t))
    terms |= set(brief[:_BRIEF_MAX_TERMS])
    return terms - _STOP - _GENERIC


_COMMON_CACHE: dict[Path, frozenset[str]] = {}


def _too_common(base: Path) -> frozenset[str]:
    """Terms so widely shared across organs that they cannot distinguish one from another."""
    if base in _COMMON_CACHE:
        return _COMMON_CACHE[base]
    roster = organs(base)
    if len(roster) < 3:
        _COMMON_CACHE[base] = frozenset()
        return _COMMON_CACHE[base]
    seen: dict[str, int] = {}
    for name in roster:
        for term in _organ_vocabulary(name, base):
            seen[term] = seen.get(term, 0) + 1
    ceiling = max(1, int(len(roster) * DISTINCTIVE_MAX_SHARE))
    _COMMON_CACHE[base] = frozenset(t for t, n in seen.items() if n > ceiling)
    return _COMMON_CACHE[base]


def organ_terms(organ: str, root: Path | None = None) -> set[str]:
    """What this organ is about, in words its neighbours do NOT also use.

    THREE SOURCES THEN ONE FILTER. The organ's name is two or three tokens and matches almost
    nothing on its own. The capability graph adds the artifacts it reads and writes --
    `UNIVERSAL_SURVIVORS.json`, `edge_search_results.json`, `live_guard.json` -- and a lesson
    naming a file this organ opens is relevant to it almost by definition. Its own prompt and run
    script add what it is FOR, in the words somebody chose to explain it, and that is the only
    source which stays current by itself: rewrite what an organ does and its routing follows.

    Then everything the other organs also say is removed, because a term they all share tells you
    nothing about which of them a lesson belongs to. What survives is this organ's subject.

    An unknown organ still gets its name tokens rather than an exception, so a script that is not
    in the capability graph yet gets a less well-routed corpus and never an empty one.
    """
    base = root or _ROOT
    return _organ_vocabulary(organ, base) - _too_common(base)


def relevance(item: Lesson, terms: set[str]) -> float:
    """0.0 to 1.0: how much of this organ's subject matter this lesson actually speaks to.

    A SATURATING COUNT OF WEIGHTED HITS, not a fraction of the lesson. Dividing by the lesson's
    own length punishes a thorough lesson for being thorough and rewards a terse one for being
    vague, and in practice it compressed every score into the bottom sixth of the range where the
    lift could not reorder anything.

    Tags count triple. They are the one field somebody wrote specifically to say what a lesson is
    ABOUT, and treating them as ordinary prose throws that intent away.
    """
    if not terms:
        return 0.0
    body = _terms(f"{item.lesson} {item.evidence}")
    tags = _terms(" ".join(item.tags))
    hit = len(body & terms) + 3 * len(tags & terms)
    return min(1.0, hit / _FULLY_RELEVANT_HITS)


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


def corpus(budget: int = BUDGET_CHARS, path: Path | None = None,
           root: Path | None = None, organ: str = "") -> tuple[str, list[Lesson]]:
    """The injected text, plus EVERY lesson that did not fit.

    Returning the dropped list is not a nicety. A memory layer that truncated silently would
    reproduce the exact defect it was built to fix: the desk believing it carries knowledge it
    does not carry. Callers are expected to surface the overflow, and check_memory_reach does.

    `organ` NAMES WHO IS READING, and re-ranks by `score x (1 + RELEVANCE_LIFT x relevance)` so a
    12,000-char budget spends itself on the lessons that apply to THIS organ. Empty (the default)
    is the old global ranking exactly, so every existing caller keeps its current behaviour and an
    unroutable organ degrades to it rather than to nothing.
    """
    items = load(path, root)
    used = len(_HEADER) + len(_FOOTER)
    kept: list[Lesson] = []

    def _pack(pool: list[Lesson], ceiling: int) -> None:
        """Fill up to `ceiling` total chars in STRICT RANK ORDER.

        The `full` latch is the whole reason this is not a greedy pack. Greedy packing skips an
        over-long lesson and takes a shorter lower-scoring one behind it, which silently lets a
        terse hygiene note outrank a verbose capital-class lesson -- at which point the budget is
        not a ranking, it is a length contest. The moment one lesson does not fit, everything
        below it in that pool is left for the next pool or dropped. Costs a little unused budget;
        buys the invariant.
        """
        nonlocal used
        full = False
        for it in pool:
            if it in kept:
                continue
            block = len(it.render()) + 1
            if full or used + block > ceiling:
                full = True
                continue
            kept.append(it)
            used += block

    if organ:
        # TWO POOLS, AND THE SPLIT IS WHAT MAKES MEMORY COMPOUND RATHER THAN ROTATE.
        #
        # Ranking by `score x (1 + lift x relevance)` alone still lets the desk's costliest
        # lessons win in EVERY organ, because cost is common to all of them and relevance only
        # tilts. Measured: reach rose from 25 lessons to 103, then stopped -- the same expensive
        # lessons occupied the top of all 29 rankings and the specific ones never surfaced
        # anywhere.
        #
        # So part of each organ's budget is spent on what the desk paid most to learn, and part on
        # what this organ is actually FOR. Neither pool can starve the other, the per-call budget
        # is untouched at 12,000 chars, and a lesson that is highly specific to one organ now has
        # somewhere it always lands instead of competing desk-wide against a capital-class lesson
        # about something this organ cannot even do.
        terms = organ_terms(organ, root)
        rel = {i.id: relevance(i, terms) for i in items}
        by_cost = sorted(items, key=lambda i: (-(i.score * (1.0 + RELEVANCE_LIFT * rel[i.id])),
                                               i.id))
        by_topic = sorted(items, key=lambda i: (-rel[i.id], -i.score, i.id))
        _pack(by_cost, int(budget * (1.0 - TOPIC_SHARE)))
        _pack([i for i in by_topic if rel[i.id] > 0.0], budget)
        _pack(by_cost, budget)          # any budget the topic pool left unspent goes back
        order = {i.id: n for n, i in enumerate(by_cost)}
        kept.sort(key=lambda i: order[i.id])
    else:
        _pack(items, budget)

    ids = {i.id for i in kept}
    dropped = [i for i in items if i.id not in ids]
    if not kept:
        return "", dropped
    body = "\n".join(item.render() for item in kept)
    return _HEADER + body + _FOOTER, dropped


def organs(root: Path | None = None) -> tuple[str, ...]:
    """Every organ that actually receives an injection, read off the tree rather than listed.

    `ops/run_*.sh` IS the roster because those are the scripts that source ops/brain_env.sh and
    therefore the only things that ever see a corpus. A hand-maintained list would drift the
    moment someone adds an organ, and it would drift in the direction that makes this module's
    reach number look better than it is -- an organ nobody listed is an organ whose lessons are
    never counted as unreached.
    """
    base = (root or _ROOT) / "ops"
    if not base.is_dir():
        return ()
    return tuple(sorted(p.stem[4:] for p in base.glob("run_*.sh") if p.stem != "run_"))


def reach(budget: int = BUDGET_CHARS, path: Path | None = None,
          root: Path | None = None) -> dict[str, list[Lesson]]:
    """Which lessons reach SOME organ, and which reach none at all.

    THE NUMBER THAT REPLACED A PROXY. The old health check asked what fraction of the ledger fell
    out of ONE global corpus, which answered "is the ledger bigger than 12,000 chars" -- true and
    uninteresting once it is. The question worth asking is whether a lesson the desk paid for is
    read by anybody, and with a routed corpus that is a different and much harder bar: a lesson
    reaches an organ if it survives that organ's ranking, and `unreached` means all 29 organs
    ranked it out.

    Returns `{"reached": [...], "unreached": [...], "lost": [...]}` where `lost` is the subset of
    unreached that no test enforces either -- knowledge the desk paid for that is now held by
    nothing at all. That list is the one to act on.
    """
    every = {i.id: i for i in load(path, root)}
    seen: set[str] = set()
    for organ in organs(root):
        text, dropped = corpus(budget, path, root, organ=organ)
        gone = {d.id for d in dropped}
        seen |= {i for i in every if i not in gone}
        if not text:
            continue
    reached = [every[i] for i in sorted(seen)]
    missed = [every[i] for i in sorted(set(every) - seen)]
    return {
        "reached": reached,
        "unreached": missed,
        "lost": [m for m in missed if not m.enforced_verified],
    }


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


# THE FRAMING COSTS BUDGET TOO. At 613 chars the old header and footer were 5% of every organ's
# 12,000 -- about one whole lesson, spent every call on prose that says the same thing each time.
# Compressed to ~250 without losing either instruction that changes behaviour: read these as your
# own likely mistakes (not as background), and record what you learn (or the desk pays twice).
# Everything else in the old text explained the RANKING, which is a property of this module and
# not something the reader has to act on.
_HEADER = """
=== DESK MEMORY: what this desk has already paid to learn, costliest first (from
docs/desk_lessons.jsonl -- do not summarise, do not skip). Each line is a specific thing that
went wrong HERE. Read it as a list of your own likely mistakes. EV = the evidence, truncated;
the id in brackets opens the full row. ===
"""

_FOOTER = """
Learned something durable? `python scripts/learn.py add ...` -- an unrecorded lesson is paid for
twice.
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
