"""THE DIFFERENCE IS THE ONLY PART OF A SECOND SEARCH WORTH PAYING FOR.

`RESIDUAL_MANDATE` asks a seat to label each item GPT_ONLY / AGREEMENT / CONTRADICTION. That is the
seat's own opinion about what the desk already knew, and a seat cannot judge what it was never
shown. These tests fence the computed version.
"""

from __future__ import annotations

from libs.research.difference_engine import CLASS_RANK, Claim, diff, render, summarise


def _c(mech, corpus, direction=None, effect="", prov=False) -> Claim:
    return Claim(mechanism=mech, corpus=corpus, direction=direction, effect=effect,
                 provenance_recorded=prov)


def _cls(diffs) -> dict[str, str]:
    return {d.mechanism: d.classification for d in diffs}


def test_CONTRADICTION_RANKS_FIRST() -> None:
    """Not because disagreement is truth -- neither side is more likely to be right. Because it
    localises UNCERTAINTY, and an experiment there resolves something instead of confirming."""
    assert CLASS_RANK[0] == "CONTRADICTION"
    ds = diff([_c("m1", "desk", "positive", prov=True), _c("m2", "desk", "positive", prov=True)],
              [_c("m1", "ext", "negative", prov=True), _c("m2", "ext", "positive", prov=True)])
    assert ds[0].classification == "CONTRADICTION"
    assert "Do NOT adjudicate" in ds[0].action


def test_A_ONLY_AND_B_ONLY_ARE_THE_RESIDUAL() -> None:
    ds = _cls(diff([_c("only_desk", "desk", "positive")], [_c("only_ext", "ext", "positive")]))
    assert ds == {"only_desk": "A_ONLY", "only_ext": "B_ONLY"}


def test_A_B_ONLY_ITEM_MAY_NOT_BE_REJECTED_FOR_ITS_PEDIGREE() -> None:
    """L1.53(a): the only admissible rejections are unexecutable, already-killed, or measured."""
    d = diff([], [_c("weird_idea", "ext", "positive")])[0]
    assert "pedigree rejection is forbidden" in d.action


def test_AGREEMENT_IS_KEPT_NOT_DISCARDED() -> None:
    """Overlap removal that DELETES the overlap throws away independent convergence, which is real
    evidence when the two searches did not read each other."""
    d = diff([_c("m", "desk", "positive", prov=True)],
             [_c("m", "ext", "positive", prov=True)])[0]
    assert d.classification == "AGREEMENT"
    assert "KEPT, NOT DISCARDED" in d.action
    assert "never a lower bar" in d.action


def test_AGREEMENT_WITHOUT_PROVENANCE_CARRIES_THE_ECHO_CAVEAT() -> None:
    """Two observers who read the same paper are ONE observer (GAP #85)."""
    d = diff([_c("m", "desk", "positive")], [_c("m", "ext", "positive")])[0]
    assert d.classification == "AGREEMENT"
    assert any("PROVENANCE NOT RECORDED" in c for c in d.caveats)
    assert any("UPPER BOUND" in c for c in d.caveats)


def test_AN_UNCOMMITTED_MENTION_IS_NEVER_AGREEMENT() -> None:
    """Scoring a shrug as agreement is the cheapest possible way to make two searches look like
    they confirmed each other."""
    d = diff([_c("m", "desk", "positive")], [_c("m", "ext", None)])[0]
    assert d.classification != "AGREEMENT"
    assert "never agreement" in d.action
    assert any("not a measured agreement" in c for c in d.caveats)


def test_SAME_EFFECT_VIA_DIFFERENT_MECHANISMS_IS_ITS_OWN_CLASS() -> None:
    """Potentially two INDEPENDENT routes to one outcome, which is more valuable than one route
    found twice -- and invisible if mechanisms are only matched pairwise."""
    ds = diff([_c("funding_flip", "desk", "positive", effect="squeeze")],
              [_c("funding_flip", "ext", None, effect="squeeze"),
               _c("oi_divergence", "ext", "positive", effect="squeeze")])
    assert _cls(ds)["funding_flip"] == "SAME_EFFECT_DIFFERENT_MECHANISM"


def test_A_MOSTLY_AGREEING_PAIR_IS_REPORTED_AS_A_PROCESS_FINDING() -> None:
    """95% agreement means the desk is paying twice for one search. That is a finding about the
    RESEARCH PROCESS, and it is what the model-attribution layer needs."""
    a = [_c(f"m{i}", "desk", "positive", prov=True) for i in range(10)]
    b = [_c(f"m{i}", "ext", "positive", prov=True) for i in range(10)]
    rep = summarise(diff(a, b))
    assert rep["residual_rate"] == 0.0
    assert "paying twice for one" in str(rep["headline"])


def test_A_HIGH_RESIDUAL_PAIR_IS_REPORTED_AS_EARNING() -> None:
    a = [_c(f"d{i}", "desk", "positive") for i in range(5)]
    b = [_c(f"e{i}", "ext", "positive") for i in range(5)]
    assert "earning its budget" in str(summarise(diff(a, b))["headline"])


def test_THE_ENGINE_NEVER_PICKS_A_WINNER() -> None:
    """A module that adjudicated its own inputs would be the bypass this desk builds fences
    against. No output field names a correct side."""
    ds = diff([_c("m", "desk", "positive", prov=True)], [_c("m", "ext", "negative", prov=True)])
    blob = " ".join(f"{d.reason} {d.action}" for d in ds).lower()
    for word in ("desk is correct", "external is correct", "desk is right", "ext is right"):
        assert word not in blob


def test_AN_EMPTY_PAIR_IS_UNMEASURED_NOT_AGREEMENT() -> None:
    assert diff([], []) == []
    assert "UNMEASURED" in render([])
