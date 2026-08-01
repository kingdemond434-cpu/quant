"""The memory layer's properties, locked.

The failure this whole module exists to prevent is subtle: a knowledge base that LOOKS present
but reaches nothing. docs/institutional_knowledge.md was 67,802 chars of real, expensive lessons
that no organ ever read, and nobody noticed for weeks because the file was right there. So the
load-bearing test here is not the ranking arithmetic -- it is
test_the_corpus_actually_reaches_a_running_organ.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from libs.research import desk_memory as dm

_ROOT = Path(__file__).resolve().parent.parent


def _row(**kw):
    base = {"id": "L9999", "learned": "2026-08-01", "cost": "blind",
            "lesson": "Do the specific measurable thing instead of assuming it.",
            "evidence": "measured in scripts/audit_gate_power.py, 2026-08-01"}
    base.update(kw)
    return base


# ---------------------------------------------------------------- the seeded ledger is sound

def test_every_shipped_lesson_is_admissible():
    """A row that would be REFUSED on the way in must not be sitting in the ledger already."""
    for line in dm.LEDGER.read_text("utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        row = json.loads(line)
        assert not dm.validate_row(row), f"{row.get('id')}: {dm.validate_row(row)}"


def test_lesson_ids_are_unique():
    """bump() rewrites a row in place and would otherwise promote a duplicated lesson twice."""
    ids = [json.loads(ln)["id"] for ln in dm.LEDGER.read_text("utf-8").splitlines()
           if ln.strip() and not ln.startswith("#")]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    assert len(ids) == len(set(ids)), f"duplicate ids: {dupes}"


# ---------------------------------------------------------------- the bar for entry

def test_a_lesson_without_evidence_is_refused():
    """Unevidenced lessons injected into every organ launder guesses into doctrine, after which
    the desk cannot separate what it measured from what it assumed."""
    assert dm.validate_row(_row(evidence=""))
    assert dm.validate_row(_row(evidence="looks right"))


def test_an_unknown_cost_class_is_refused():
    assert dm.validate_row(_row(cost="important"))


def test_a_lesson_too_short_to_change_behaviour_is_refused():
    assert dm.validate_row(_row(lesson="be careful"))


# ---------------------------------------------------------------- ranking

def test_a_relearned_lesson_outranks_a_one_off_of_the_same_cost():
    """The core idea. Recurrence is the desk telling itself which lessons do not stick, and that
    signal has to reach the top of the corpus without anyone deciding to put it there."""
    once = dm.Lesson("L1", "2026-08-01", "blind", "x" * 30, "y" * 30, recurrence=1)
    twice = dm.Lesson("L2", "2026-08-01", "blind", "x" * 30, "y" * 30, recurrence=2)
    assert twice.score > once.score


def test_recurrence_cannot_let_one_lesson_dominate_every_capital_lesson():
    """log2, not linear. An 8x-recurring hygiene note must not outrank a capital-class lesson."""
    hygiene8 = dm.Lesson("L1", "2026-08-01", "hygiene", "x" * 30, "y" * 30, recurrence=8)
    capital1 = dm.Lesson("L2", "2026-08-01", "capital", "x" * 30, "y" * 30, recurrence=1)
    assert capital1.score > hygiene8.score


def test_cost_ordering_is_by_consequence():
    order = ["hygiene", "slow", "wasted", "blind", "capital"]
    weights = [dm.COST_WEIGHT[c] for c in order]
    assert weights == sorted(weights), "cost weights must rank by consequence, not by taste"


# ---------------------------------------------------------------- the budget

def test_the_corpus_never_exceeds_its_budget():
    text, _ = dm.corpus()
    assert len(text) <= dm.BUDGET_CHARS


def test_nothing_is_dropped_silently():
    """Every active lesson is either in the injected text or named in the dropped list. A memory
    layer that truncated quietly would recreate the defect it exists to fix."""
    text, dropped = dm.corpus(budget=1500)
    active = dm.load()
    assert dropped, "budget of 1500 must force overflow for this to test anything"
    for item in active:
        assert (item.lesson.strip() in text) or (item in dropped), f"{item.id} vanished"


def test_a_tiny_budget_keeps_the_highest_scoring_lesson():
    text, dropped = dm.corpus(budget=1200)
    best = dm.load()[0]
    assert best.lesson.strip() in text
    assert best not in dropped


def test_overflow_is_by_rank_and_stays_a_small_tail():
    """The ceiling is SUPPOSED to bind eventually -- that is the whole design, and it started
    binding the moment three new lessons outranked two old ones. What must never happen is either
    of the two ways this could quietly go wrong:

      1. Something high-scoring gets dropped while something weaker is injected. Then the budget
         is not a ranking, it is a lottery.
      2. The tail grows until most of what the desk paid for reaches no organ. At that point the
         corpus is a diary again and the budget has stopped being a forcing function and started
         being the defect.

    So: strict rank ordering, and a bounded tail. If this fails on (2) the fix is to RETIRE a
    lesson whose falsifier arrived or GRADUATE one into a test, never to raise the budget --
    raising it is how the doctrine reached 95k.

    THE TAIL BOUND IS ON THE UNENFORCED TAIL, NOT THE WHOLE TAIL, and the distinction is a
    correction rather than a relaxation. The first version of this test bounded total overflow at
    25%. That was a PROXY for "lessons are being lost", and graduation made the proxy false: a
    graduated lesson sits at the bottom of the ranking BECAUSE a test enforces it, so a healthy
    mature corpus is mostly tail. Measured at 42 lessons the total tail is 26.2% and every single
    entry in it is either test-enforced or hygiene-class -- nothing is lost. Bounding the raw
    fraction would now force retirement of lessons that are fine, which is the opposite of what
    the bound was for. So the assertion moved to the property the proxy was standing in for.
    """
    _, dropped = dm.corpus()
    active = dm.load()
    kept = [item for item in active if item not in dropped]
    assert kept, "nothing injected at all"
    if dropped:
        assert min(k.score for k in kept) >= max(d.score for d in dropped), (
            "a weaker lesson was injected over a stronger one -- the budget is not ranking")
    lost = [d for d in dropped if not d.enforced_verified and d.cost not in ("hygiene", "slow")]
    assert not lost, (
        f"{len(lost)} paid-for lesson(s) reach NO organ and NO test enforces them: "
        f"{[(d.id, d.cost) for d in lost]}. Graduate one into a test, or retire one whose "
        "falsifier arrived. Do not raise the budget.")
    unenforced_tail = [d for d in dropped if not d.enforced_verified]
    assert len(unenforced_tail) / len(active) < 0.15, (
        f"{len(unenforced_tail)}/{len(active)} lessons fall off the budget with no test behind "
        "them -- the corpus is rotating rather than compounding")


# ---------------------------------------------------------------- retirement

def test_a_retired_lesson_leaves_the_corpus_but_stays_in_the_file(tmp_path):
    p = tmp_path / "l.jsonl"
    p.write_text(
        json.dumps(_row(id="L0001")) + "\n"
        + json.dumps(_row(id="L0002", retired="falsifier arrived 2026-08-01")) + "\n", "utf-8")
    ids = [item.id for item in dm.load(p)]
    assert ids == ["L0001"]
    assert "L0002" in p.read_text("utf-8"), "retirement must not delete the history"


# ---------------------------------------------------------------- write path

def test_bump_rewrites_in_place_and_does_not_duplicate(tmp_path):
    p = tmp_path / "l.jsonl"
    p.write_text(json.dumps(_row(id="L0001")) + "\n", "utf-8")
    assert dm.bump("L0001", p) == 2
    assert dm.bump("L0001", p) == 3
    rows = [json.loads(ln) for ln in p.read_text("utf-8").splitlines() if ln.strip()]
    assert len(rows) == 1 and rows[0]["recurrence"] == 3


def test_bump_of_an_unknown_lesson_raises(tmp_path):
    p = tmp_path / "l.jsonl"
    p.write_text(json.dumps(_row(id="L0001")) + "\n", "utf-8")
    with pytest.raises(KeyError):
        dm.bump("L0404", p)


def test_append_refuses_an_inadmissible_row_instead_of_writing_it(tmp_path):
    p = tmp_path / "l.jsonl"
    with pytest.raises(ValueError):
        dm.append(_row(evidence=""), p)
    assert not p.exists() or not p.read_text("utf-8").strip()


def test_next_id_increments_past_the_highest(tmp_path):
    p = tmp_path / "l.jsonl"
    p.write_text(json.dumps(_row(id="L0007")) + "\n" + json.dumps(_row(id="L0003")) + "\n", "utf-8")
    assert dm.next_id(p) == "L0008"


# ---------------------------------------------------------------- THE ONE THAT MATTERS

def test_the_corpus_actually_reaches_a_running_organ():
    """Knowledge that is not injected at runtime does not exist -- lesson L0030, encoded.

    Every miner runner sources ops/brain_env.sh, which builds the --append-system-prompt payload.
    If the render call is not in that file, the entire module is a diary: 31 expensive lessons
    sitting on disk changing nothing, exactly like the 67,802-char institutional_knowledge.md that
    prompted this build.
    """
    src = (_ROOT / "ops/brain_env.sh").read_text("utf-8")
    assert "scripts/learn.py render" in src, (
        "brain_env.sh does not inject desk memory; no organ will ever read a lesson")
    assert "_DOCTRINE" in src.split("scripts/learn.py render")[1], (
        "the rendered corpus must reach _DOCTRINE, which is what organs actually receive")


def test_memory_failure_can_never_stop_an_organ_from_running():
    """The corpus improves a working organ; it is not a precondition for one. A memory layer that
    could take down all eleven mining seats would be a far worse defect than the amnesia it
    fixes."""
    src = (_ROOT / "ops/brain_env.sh").read_text("utf-8")
    inject = src.split("scripts/learn.py render")[1].split("\n")[0]
    assert "|| true" in inject or "|| true" in src.split("scripts/learn.py render")[1][:200], (
        "the render call must not be able to fail an organ spawn")


# ------------------------------------------------------- graduation: the anti-plateau mechanism

def test_a_test_enforced_lesson_is_demoted_not_deleted():
    """Graduation is the escape from saturation. A fixed budget with a growing ledger eventually
    displaces old lessons to make room for new ones and the desk stops accumulating. Converting a
    lesson into a TEST keeps the property enforced forever at zero context cost and hands the
    budget back. Demoted rather than removed because a test locks one property in one file while
    the lesson generalises to code that does not exist yet."""
    plain = dm.Lesson("L1", "2026-08-01", "capital", "x" * 30, "y" * 30)
    grad = dm.Lesson("L2", "2026-08-01", "capital", "x" * 30, "y" * 30,
                     enforced_by="tests/t.py::test_x", enforced_verified=True)
    assert 0 < grad.score < plain.score
    assert grad.score == plain.score * dm.ENFORCED_WEIGHT


def test_enforced_lessons_rank_below_anything_a_machine_cannot_catch():
    """The ordering that makes graduation worth doing: injected context is spent on judgement
    calls, because everything mechanically checkable is already checked mechanically."""
    enforced_capital = dm.Lesson("L1", "2026-08-01", "capital", "x" * 30, "y" * 30,
                                 enforced_by="t::t", enforced_verified=True)
    unenforced_wasted = dm.Lesson("L2", "2026-08-01", "wasted", "x" * 30, "y" * 30)
    assert unenforced_wasted.score > enforced_capital.score


def test_an_unresolvable_enforcement_claim_grants_no_discount(tmp_path):
    """FAILS CLOSED, and this is the load-bearing half. If enforced_by were trusted from the file,
    a typo or a renamed test would silently drop a paid-for lesson out of every organ's context
    while the ledger still claimed the property was automated -- the exact failure this module
    exists to prevent, reintroduced one level down."""
    p = tmp_path / "l.jsonl"
    p.write_text(json.dumps(_row(id="L0001", enforced_by="tests/nope.py::test_ghost")) + "\n",
                 "utf-8")
    item = dm.load(p)[0]
    assert not item.enforced_verified
    assert item.score == dm.COST_WEIGHT["blind"], "an unverified claim must keep full weight"


def test_broken_enforcement_claims_are_reported_as_defects(tmp_path):
    p = tmp_path / "l.jsonl"
    p.write_text(
        json.dumps(_row(id="L0001", enforced_by="tests/nope.py::test_ghost")) + "\n"
        + json.dumps(_row(id="L0002")) + "\n", "utf-8")
    broken = dm.broken_enforcement(p)
    assert [b.id for b in broken] == ["L0001"]


def test_every_shipped_enforcement_claim_resolves():
    """The desk's own ledger, checked. A graduated lesson whose test vanished is a lesson nobody
    is enforcing and nobody is reading."""
    broken = dm.broken_enforcement()
    assert not broken, f"claim enforcement by a test that does not exist: {[b.id for b in broken]}"


def test_graduation_actually_freed_budget():
    """The mechanism has to pay for itself or it is bookkeeping. Everything currently over budget
    must be either test-enforced (still guarded, just not injected) or the lowest-cost class --
    never an unenforced capital or blind lesson."""
    _, dropped = dm.corpus()
    for d in dropped:
        assert d.enforced_verified or d.cost in ("hygiene", "slow"), (
            f"{d.id} ({d.cost}) reaches no organ and no test enforces it")


def test_overflow_separates_a_real_loss_from_a_deliberate_demotion(tmp_path):
    """A graduated lesson that ranks out is NOT a lesson the desk stopped telling anyone -- a test
    tells it, on every CI run. Counting the two together reported 31 lessons "reaching NO organ"
    when 20 were enforced, overstating the loss 2.8x; a number that cries wolf gets skipped, and
    the genuine losses hide inside it."""
    # load() resolves enforced_by against the ledger's grandparent, so the fixture needs a root
    # shaped like the repo: <root>/docs/l.jsonl alongside <root>/tests/.
    (tmp_path / "docs").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "t.py").write_text("def test_x():\n    pass\n", "utf-8")
    p = tmp_path / "docs" / "l.jsonl"
    p.write_text(
        json.dumps(_row(id="L0001", enforced_by="tests/t.py::test_x")) + "\n"
        + json.dumps(_row(id="L0002")) + "\n", "utf-8")
    lost, demoted = dm.unreached(budget=1, path=p)   # budget=1 -> nothing fits, all overflow
    assert [i.id for i in lost] == ["L0002"], "an unenforced lesson over budget is a real loss"
    assert [i.id for i in demoted] == ["L0001"], "a test-enforced lesson is demoted, not lost"


def test_an_unverifiable_enforcement_claim_is_counted_as_lost_not_demoted(tmp_path):
    """The half that keeps the split honest. If a bad enforced_by bought a place in `demoted`,
    writing a path that resolves to nothing would be a way to make a paid-for lesson disappear
    from every organ's context AND from the overflow report that exists to catch exactly that."""
    p = tmp_path / "l.jsonl"
    p.write_text(json.dumps(_row(id="L0001", enforced_by="tests/nope.py::test_ghost")) + "\n",
                 "utf-8")
    lost, demoted = dm.unreached(budget=1, path=p)
    assert [i.id for i in lost] == ["L0001"]
    assert demoted == []
