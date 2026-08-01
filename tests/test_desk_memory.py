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
    lesson whose falsifier arrived, never to raise the budget -- raising it is how the doctrine
    reached 95k.
    """
    _, dropped = dm.corpus()
    active = dm.load()
    kept = [item for item in active if item not in dropped]
    assert kept, "nothing injected at all"
    if dropped:
        assert min(k.score for k in kept) >= max(d.score for d in dropped), (
            "a weaker lesson was injected over a stronger one -- the budget is not ranking")
    assert len(dropped) / len(active) < 0.25, (
        f"{len(dropped)}/{len(active)} paid-for lessons reach no organ: "
        f"{[d.id for d in dropped]}. Retire one whose falsifier arrived.")


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
