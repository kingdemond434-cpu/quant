"""ASSUMPTIONS, CONTRADICTIONS AND UNKNOWNS ARE ONE OBJECT AT THREE CONFIDENCE LEVELS.

Three registries would share a schema and a lifecycle and could not see the transitions between
them -- and the transitions are the research signal.
"""

from __future__ import annotations

import pytest

from libs.research.unknowns import (
    PRIORITY,
    Item,
    acquire_targets,
    contradict,
    ranked,
    render,
    resolve,
    summarise,
)


def _item(**kw) -> Item:
    base = {"key": "k", "state": "ASSUMED", "statement": "s", "falsifier": "f",
            "trigger": "unexplained result"}
    return Item(**{**base, **kw})


def test_A_BELIEF_WITH_NO_FALSIFIER_IS_REFUSED() -> None:
    """A belief nothing can dislodge is a HABIT: it survives its own obsolescence because no
    observation is allowed to count against it."""
    for state in ("ASSUMED", "KNOWN"):
        with pytest.raises(ValueError, match="HABIT, not knowledge"):
            _item(state=state, falsifier="")


def test_A_NON_BELIEF_STATE_OWES_NO_FALSIFIER() -> None:
    """UNKNOWN asserts nothing about the world, so demanding a falsifier would make the honest
    state the expensive one to record."""
    assert _item(state="UNKNOWN", falsifier="").state == "UNKNOWN"


def test_UNMEASURABLE_MUST_NAME_ITS_DATA() -> None:
    """'We do not have the data' is the sentence that most often ends a research thread here, and
    it must convert into an ACQUISITION TARGET rather than a dead end."""
    with pytest.raises(ValueError, match="ACQUISITION TARGET"):
        _item(state="UNMEASURABLE", falsifier="")
    ok = _item(state="UNMEASURABLE", falsifier="", needs_data=("options_iv",))
    assert ok.needs_data == ("options_iv",)


def test_AN_ITEM_WITH_NO_TRIGGER_IS_BLOAT_BY_DEFINITION() -> None:
    """L1.55: expansion is driven by information gain, unexplained observations, contradictions and
    named blind spots -- never by accumulation."""
    with pytest.raises(ValueError, match="bloat by definition"):
        _item(trigger="")


def test_CONTRADICTED_OUTRANKS_EVERYTHING() -> None:
    """Something downstream was ALREADY sized on the belief it breaks, so the cost is being paid
    now rather than hypothetically."""
    assert PRIORITY[0] == "CONTRADICTED"


def test_ASSUMED_OUTRANKS_UNKNOWN() -> None:
    """A load-bearing untested belief is more dangerous than an acknowledged blank, because the
    blank is visible and the belief is not."""
    assert PRIORITY.index("ASSUMED") < PRIORITY.index("UNKNOWN")


def test_A_CONTRADICTION_REPORTS_ITS_BLAST_RADIUS() -> None:
    """A contradiction reported without it reads as a curiosity rather than as one defect plus
    every decision that rested on it."""
    it = _item(state="KNOWN", depends_on_it=("sizing", "carry_sleeve", "cost_model"))
    out, why = contradict(it, evidence="live shows the opposite sign over 40 closes")
    assert out.state == "CONTRADICTED"
    assert "blast radius 3" in why
    assert "carry_sleeve" in why


def test_A_CONTRADICTION_WITH_NO_RECORDED_DEPENDENTS_SAYS_SO() -> None:
    """It may mean nothing rested on it, or that nobody recorded what did -- and the second is
    likelier and worse."""
    _out, why = contradict(_item(state="KNOWN"), evidence="e")
    assert "nobody recorded what did" in why


def test_A_CONTRADICTION_NEEDS_EVIDENCE() -> None:
    """Otherwise one unverified claim could invalidate measured work -- the failure mode in the
    opposite direction."""
    it = _item(state="KNOWN")
    out, why = contradict(it, evidence="  ")
    assert out is it and "needs its evidence" in why


def test_RESOLVING_INTO_A_BELIEF_STILL_REQUIRES_A_FALSIFIER() -> None:
    """Resolving a contradiction is exactly when a desk is most inclined to write down a conclusion
    and no way to overturn it."""
    it = _item(state="CONTRADICTED", falsifier="")
    out, why = resolve(it, state="KNOWN", evidence="measured", falsifier="")
    assert out.state == "CONTRADICTED" and "REFUSED" in why
    ok, _ = resolve(it, state="KNOWN", evidence="measured", falsifier="t falls below 2")
    assert ok.state == "KNOWN"


def test_A_RESOLUTION_NEEDS_EVIDENCE() -> None:
    out, why = resolve(_item(), state="KNOWN", evidence="", falsifier="f")
    assert out.state == "ASSUMED" and "or it is a preference" in why


def test_WORK_ORDER_IS_STATE_THEN_BLAST_RADIUS() -> None:
    """Two contradictions are not equal: the one more things were sized on comes first."""
    small = _item(key="small", state="KNOWN", depends_on_it=("a",))
    big = _item(key="big", state="KNOWN", depends_on_it=("a", "b", "c"))
    s, _ = contradict(small, evidence="e")
    b, _ = contradict(big, evidence="e")
    assert [i.key for i in ranked([s, b])] == ["big", "small"]


def test_ACQUISITION_TARGETS_INVERT_THE_UNMEASURABLE_PILE() -> None:
    """Ranking datasets by how many blocked questions they open is the concrete form of
    'prioritise data by expected hypothesis-space expansion' -- measured, not guessed."""
    items = [
        _item(key="q1", state="UNMEASURABLE", falsifier="", needs_data=("options_iv", "oi")),
        _item(key="q2", state="UNMEASURABLE", falsifier="", needs_data=("options_iv",)),
        _item(key="q3", state="ASSUMED"),
    ]
    targets = acquire_targets(items)
    assert list(targets) == ["options_iv", "oi"]
    assert targets["options_iv"] == ["q1", "q2"]


def test_AN_EMPTY_LEDGER_IS_NOT_A_CLEAN_BILL() -> None:
    """A desk with no recorded assumptions has unrecorded ones."""
    rep = summarise([])
    assert "EMPTY LEDGER" in str(rep["headline"])
    assert "unrecorded ones" in str(rep["headline"])
    assert "EMPTY" in render([])


def test_THE_HEADLINE_LEADS_WITH_CONTRADICTIONS_WHEN_ANY_EXIST() -> None:
    c, _ = contradict(_item(key="c", state="KNOWN", depends_on_it=("x", "y")), evidence="e")
    rep = summarise([c, _item(key="a")])
    assert "CONTRADICTED" in str(rep["headline"])
    assert "blast radius 2" in str(rep["headline"])


def test_AN_UNKNOWN_STATE_IS_REFUSED() -> None:
    with pytest.raises(ValueError, match="unknown state"):
        _item(state="PROBABLY_FINE")
