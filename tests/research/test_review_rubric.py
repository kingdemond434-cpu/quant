"""The rubric injection, and the two ways it could quietly stop working.

Wiring a checklist is only half the job. The other half is that a WIRED rubric which resolves to
nothing is worse than an unwired one: the injection keeps succeeding, review organs keep reporting
that they applied it, and the classes are gone. test_a_gutted_rubric_is_reported_not_silently_empty
is the one that matters.
"""
from __future__ import annotations

from pathlib import Path

from libs.research.review_rubric import (
    EXPECTED_CLASSES,
    RUBRIC,
    RUBRIC_BUDGET_CHARS,
    audit,
    parse,
    preamble,
)

_ROOT = Path(__file__).resolve().parents[2]


def test_the_shipped_rubric_parses_all_its_classes():
    rep = audit()
    assert rep["ok"], rep["problems"]
    assert rep["n_classes"] >= EXPECTED_CLASSES


def test_the_injected_block_carries_the_real_instances_not_just_titles():
    """The instances are the entire value. "Gate that fails open" is a phrase anyone nods at;
    "beats_baselines returns True when no benchmark is supplied and no production caller supplies
    one" is a thing you go and check. A 4,000-char budget silently dropped every one of them."""
    p = preamble()
    assert "beats_baselines" in p, "the shipped instances were dropped"
    assert "Test:" in p, "the per-class test instructions were dropped"


def test_the_budget_is_above_what_the_rubric_actually_renders():
    full = preamble(max_chars=10 ** 6)
    assert len(full) <= RUBRIC_BUDGET_CHARS, (
        f"the rubric renders at {len(full)} chars but the budget is {RUBRIC_BUDGET_CHARS} -- "
        "the injection has silently degraded to titles")


def test_it_reaches_the_doctrine_every_llm_caller_already_injects():
    """The whole point. Before this, `grep -rn ADVERSARIAL_REVIEW_RUBRIC` returned one hit -- a
    max_audit exclusion list -- so the rubric fired only when an agent happened to remember it."""
    import sys
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    from scripts.doctrine import preamble as doctrine_preamble
    p = doctrine_preamble("reviewer")
    assert "ADVERSARIAL REVIEW RUBRIC" in p
    assert "beats_baselines" in p


# ------------------------------------------------------------------ the two silent failures

def test_a_missing_rubric_degrades_to_empty_rather_than_raising(tmp_path):
    """A broken enrichment must never take down a working organ. Every review seat would die
    because a documentation file moved."""
    assert preamble(path=tmp_path / "gone.md") == ""


def test_a_missing_rubric_is_reported_as_a_problem(tmp_path):
    rep = audit(tmp_path / "gone.md")
    assert not rep["ok"] and rep["problems"]


def test_a_gutted_rubric_is_reported_not_silently_empty(tmp_path):
    """THE failure this module guards. A file that still exists but whose heading format changed
    parses to zero classes -- the injection keeps succeeding and injects nothing."""
    p = tmp_path / "r.md"
    p.write_text("# Adversarial review\n\nSome prose but no `### N. Name` headings.\n", "utf-8")
    rep = audit(p)
    assert rep["n_classes"] == 0
    assert not rep["ok"]
    assert "silently empty" in " ".join(str(x) for x in rep["problems"])


def test_a_vanished_class_is_reported(tmp_path):
    p = tmp_path / "r.md"
    p.write_text("### 1. One class\nbody\n\n### 2. Another\nbody\n", "utf-8")
    rep = audit(p)
    assert rep["n_classes"] == 2 and not rep["ok"]
    assert "vanished" in " ".join(str(x) for x in rep["problems"])


def test_adding_an_eleventh_class_is_not_treated_as_a_failure():
    """EXPECTED_CLASSES is a change detector for DISAPPEARANCE, not a cap. Growing the rubric is
    the intended direction and must not fail the audit."""
    text = RUBRIC.read_text("utf-8") + "\n### 11. A new class\nbody here\n"
    tmp = _ROOT / "reports" / "_rubric_probe.md"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    try:
        tmp.write_text(text, "utf-8")
        rep = audit(tmp)
        assert rep["n_classes"] == 11 and rep["ok"]
    finally:
        tmp.unlink(missing_ok=True)


def test_parsing_is_driven_by_the_document_not_a_second_copy():
    """A restated list here would drift from the markdown within a month and the desk would have
    two rubrics. Every parsed name must actually appear in the source file."""
    text = RUBRIC.read_text("utf-8")
    for c in parse():
        assert c.name in text
