"""A lesson that does not fit the injected budget is a WISH, and `learn.py add` now says so (R0346).

THE CAUSAL CHAIN THIS EXISTS TO BREAK, measured 2026-08-01: commit 0240cfa recorded L0057 ("a red
pytest leg can mean zero tests ran"); its OWN commit message observed that the lesson rendered at
659 chars against 156 chars of free budget and so "does not fit and reaches no organ"; the class it
warned about then recurred THREE times within 21 minutes, killing pytest collection repo-wide each
time. The overflow was visible at render time and at audit time. At neither of those moments was
anybody deciding anything -- so the desk kept recording lessons it believed it had learned and had
not. The forcing function has to be at WRITE time, which is the only moment the author is present.

The escape hatch is deliberately cheap (one flag) and deliberately RECORDED: the point is not to
block writing, it is to make "this one reaches no organ" a decision somebody made on the record
rather than a silent property of a ranking.
"""

from __future__ import annotations

import argparse
import json

import pytest

from libs.research import desk_memory
from scripts import learn


def _row(i: int, cost: str = "capital", recurrence: int = 16) -> str:
    """A long, high-scoring lesson -- used to fill the budget ahead of the candidate."""
    return json.dumps({
        "id": f"L{i:04d}", "learned": "2026-08-01", "cost": cost, "recurrence": recurrence,
        "lesson": f"Filler lesson {i} stating what to do differently in enough words to occupy "
                  f"a meaningful slice of the character budget. " + ("padding words " * 18),
        "evidence": f"tests/ops/test_learn_budget_forcing.py filler row {i}",
    })


@pytest.fixture
def ledger(tmp_path, monkeypatch):
    """Redirect BOTH bindings -- learn.py imported LEDGER by value, desk_memory reads its own."""
    p = tmp_path / "desk_lessons.jsonl"
    p.write_text("", "utf-8")
    monkeypatch.setattr(desk_memory, "LEDGER", p)
    monkeypatch.setattr(learn, "LEDGER", p)
    return p


def _add(**over) -> int:
    args = {"cost": "hygiene", "lesson": "A lesson stating clearly what to do differently here.",
            "evidence": "tests/ops/test_learn_budget_forcing.py", "tag": [], "source": "test",
            "enforced_by": "", "accept_uninjected": ""}
    args.update(over)
    return learn.cmd_add(argparse.Namespace(**args))


def _full(ledger, n: int = 40, cost: str = "capital", recurrence: int = 16) -> None:
    ledger.write_text("\n".join(_row(i, cost, recurrence) for i in range(1, n + 1)) + "\n",
                      "utf-8")


def test_a_fitting_lesson_is_recorded_and_reported_as_injected(ledger, capsys):
    """On an empty ledger everything fits -- and the report says so instead of staying silent."""
    assert _add() == 0
    out = capsys.readouterr().out
    assert "recorded" in out
    assert "INJECTED" in out
    assert len(ledger.read_text("utf-8").strip().splitlines()) == 1


def test_an_over_budget_lesson_is_REFUSED_and_not_written(ledger, capsys):
    """THE FORCING FUNCTION. Silence here is what let 32 of 57 lessons reach no organ."""
    _full(ledger)
    before = ledger.read_text("utf-8")
    assert _add() == 1
    err = capsys.readouterr().err
    assert "does NOT fit" in err
    assert "--enforced-by" in err and "--accept-uninjected" in err
    assert "RAISING THE BUDGET IS NOT ON THAT LIST" in err
    assert ledger.read_text("utf-8") == before, "a refused lesson must not be half-written"


def test_an_explicit_accepted_uninjected_note_is_recorded_on_the_row(ledger, capsys):
    """The escape hatch works, and it leaves an auditable trace rather than a silent drop."""
    _full(ledger)
    assert _add(accept_uninjected="no test can catch a judgement call about tone") == 0
    assert "NOT injected (over budget), accepted knowingly" in capsys.readouterr().out
    last = json.loads(ledger.read_text("utf-8").strip().splitlines()[-1])
    assert last["accepted_uninjected"] == "no test can catch a judgement call about tone"


def test_a_graduating_test_is_accepted_and_VERIFIED_not_trusted(ledger):
    """The preferred path -- but a reference that does not resolve must not buy its way in."""
    assert _add(enforced_by="tests/ops/test_learn_budget_forcing.py::test_a_fitting_lesson_"
                            "is_recorded_and_reported_as_injected") == 0
    last = json.loads(ledger.read_text("utf-8").strip().splitlines()[-1])
    assert last["enforced_by"].startswith("tests/ops/test_learn_budget_forcing.py::")


def test_a_bogus_graduating_test_is_refused_in_part(ledger, capsys):
    """A path that resolves to nothing would leave the lesson neither injected nor enforced --
    which is exactly the silent way out of the corpus `_test_exists` fails closed against."""
    _full(ledger)
    assert _add(enforced_by="tests/does_not_exist.py::test_nope") == 1
    assert "does not name a real test" in capsys.readouterr().err


def test_displacement_is_named_because_the_pack_is_strict_rank(ledger, capsys):
    """Adding a lesson can push ANOTHER one out. That victim is now the wish, so it is named."""
    # Low-scoring fillers overflow the budget; a capital-class lesson outranks the whole tail,
    # takes its slice at the top of the pack, and the last filler that used to fit no longer does.
    _full(ledger, n=40, cost="hygiene", recurrence=1)
    # The candidate is deliberately LONGER than one filler block, so the eviction is arithmetic
    # rather than a coin flip on however much headroom the last filler happened to leave.
    assert _add(cost="capital",
                lesson="A high-ranking lesson that displaces a weaker one and states plainly "
                       "what to do differently. " + ("padding words " * 30)) == 0
    out = capsys.readouterr().out
    assert "INJECTED" in out
    assert "DISPLACED" in out, ("the strict-rank latch means a new lesson evicts the tail; a "
                                "silent eviction is the same defect one row down")


def test_the_probe_resolves_enforced_by_against_the_REPO_not_the_scratch_dir(tmp_path):
    """`would_reach_organs` scores a SCRATCH ledger, and `enforced_by` paths are repo-relative.

    Without `root=` pinned to the repo, every graduated lesson in the probe resolves against the
    scratch directory, fails, and silently regains full weight -- so the probe would answer a
    different question from the one asked. This pins the parameter directly: same file, two roots,
    opposite verdicts.
    """
    ref = ("tests/ops/test_learn_budget_forcing.py::"
           "test_a_fitting_lesson_is_recorded_and_reported_as_injected")
    probe = tmp_path / "desk_lessons.jsonl"
    row = json.loads(_row(1))
    row["enforced_by"] = ref
    probe.write_text(json.dumps(row) + "\n", "utf-8")

    pinned = desk_memory.load(path=probe, root=learn._ROOT)
    assert pinned[0].enforced_verified is True, "the repo root must resolve a real test reference"
    assert pinned[0].score == pytest.approx(5 * (1 + 4) * desk_memory.ENFORCED_WEIGHT)

    unpinned = desk_memory.load(path=probe)
    assert unpinned[0].enforced_verified is False, (
        "resolving against the scratch dir must fail closed -- which is precisely why the probe "
        "has to pass root=, or it would score a corpus nobody will ever inject")
