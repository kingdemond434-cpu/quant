"""WHICH MINER, MODEL OR PROMPT ACTUALLY PRODUCES VALIDATED ALPHA.

The desk knows how many documents each miner found. It has never measured whether any of them
became a survivor. Volume is a COST here, never an output.
"""

from __future__ import annotations

import pytest

from libs.research.source_roi import (
    EXPLORATION_FLOOR,
    MIN_TESTED_FOR_VERDICT,
    SourceRecord,
    allocate,
    bottleneck,
    summarise,
    verdict,
)


def _r(**kw) -> SourceRecord:
    base = {"name": "s", "kind": "miner"}
    return SourceRecord(**{**base, **kw})


def test_ZERO_SURVIVORS_ON_A_SMALL_SAMPLE_IS_UNMEASURED_NOT_BARREN() -> None:
    """Survivors are rare and lumpy. With 5 tests the expected count was under one anyway, so
    judging the source would defund every slow-burn search in favour of this month's lucky one --
    the exact selection error the desk polices in its alpha research."""
    r = _r(tested=5, survivors=0, cost_units=10)
    assert verdict(r) == "UNMEASURED"
    assert r.roi is None, "roi must be None, not 0.0 -- 0.0 reads as measured-and-worthless"
    stage, why = bottleneck(r)
    assert stage == "UNMEASURED" and "never evidence the source is barren" in why


def test_A_REAL_SAMPLE_WITH_NO_SURVIVORS_IS_REDUCE_NEVER_DELETE() -> None:
    r = _r(tested=MIN_TESTED_FOR_VERDICT + 10, survivors=0, cost_units=10)
    assert verdict(r) == "REDUCE"
    assert bottleneck(r)[0] == "YIELD"


def test_NO_SOURCE_IS_EVER_CUT_TO_ZERO() -> None:
    """L1.52 forbids reducing exploration to zero, and a source pruned to nothing can never produce
    the evidence that would justify restoring it -- the defunding becomes self-confirming."""
    good = _r(name="good", tested=100, survivors=5, independent=4, portfolio_positive=3,
              cost_units=10)
    bad = _r(name="bad", tested=100, survivors=0, cost_units=50)
    shares = allocate([good, bad])
    assert shares["bad"] == pytest.approx(EXPLORATION_FLOOR)
    assert shares["good"] > shares["bad"]
    assert sum(shares.values()) == pytest.approx(1.0, abs=1e-3)


def test_AN_UNMEASURED_SOURCE_GETS_THE_FLOOR_NOT_ZERO() -> None:
    """Defunding it would guarantee it never reaches the sample that would settle the question."""
    shares = allocate([_r(name="new", tested=2, cost_units=1),
                       _r(name="proven", tested=100, independent=4, cost_units=10)])
    assert shares["new"] >= EXPLORATION_FLOOR


def test_WITH_NOTHING_PROVEN_THE_FREE_SHARE_SPREADS_EVENLY() -> None:
    """Exploration is the correct default when nothing is measured -- freezing every source at the
    floor would leave most of the budget unspent, which is idle capacity."""
    shares = allocate([_r(name="a", tested=1), _r(name="b", tested=1)])
    assert shares["a"] == shares["b"] == pytest.approx(0.5)


def test_AN_EXECUTOR_BOTTLENECK_IS_NOT_THE_SOURCES_FAULT() -> None:
    """The central distinction. A single ROI number cannot tell a redundant source from a starved
    executor, and cutting the source's budget is the right answer to exactly one of them."""
    stage, why = bottleneck(_r(found=200, novel=150, hypotheses=90, tested=0))
    assert stage == "EXECUTION"
    assert "NOT this source's" in why and "wrong stage" in why


def test_A_REDUNDANT_SOURCE_IS_NAMED_AS_A_NOVELTY_PROBLEM() -> None:
    stage, why = bottleneck(_r(found=5000, novel=0))
    assert stage == "NOVELTY" and "change the search, not the volume" in why


def test_AN_EXTRACTION_GAP_IS_ATTRIBUTED_TO_THE_DESK() -> None:
    stage, why = bottleneck(_r(found=100, novel=80, hypotheses=0))
    assert stage == "EXTRACTION" and "not a fault in the source" in why


def test_RE_FINDING_KNOWN_MECHANISMS_IS_AN_INDEPENDENCE_PROBLEM() -> None:
    stage, _ = bottleneck(_r(tested=100, survivors=6, independent=0))
    assert stage == "INDEPENDENCE"


def test_DISTINCT_IS_NOT_THE_SAME_AS_ADDITIVE() -> None:
    stage, why = bottleneck(_r(tested=100, survivors=6, independent=4, portfolio_positive=0))
    assert stage == "PORTFOLIO" and "after correlation and capacity" in why


def test_A_SILENT_SOURCE_IS_FLAGGED_SEPARATELY() -> None:
    """Producing nothing at all is an operational fault, not a research verdict."""
    stage, why = bottleneck(_r())
    assert stage == "SILENT" and "still runs" in why


def test_VALUE_FALLS_BACK_TO_INDEPENDENT_WHEN_PORTFOLIO_TESTING_HAS_NOT_RUN() -> None:
    """Otherwise a desk with no portfolio stage scores every source zero and concludes all research
    is worthless -- a measurement artifact, not a finding."""
    assert _r(independent=3, portfolio_positive=0).value == 3
    assert _r(independent=3, portfolio_positive=1).value == 1


def test_MORE_SOURCES_THAN_THE_FLOOR_CAN_FUND_YIELDS_EQUAL_SHARES() -> None:
    """Any ranking there would be a distinction the budget cannot express."""
    many = [_r(name=f"s{i}", tested=100, independent=i, cost_units=1) for i in range(30)]
    shares = allocate(many)
    assert len(set(shares.values())) == 1


def test_AN_EMPTY_ROSTER_IS_UNMEASURED() -> None:
    assert "UNMEASURED, not zero value" in str(summarise([])["headline"])


def test_VOLUME_IS_DOCUMENTED_AS_A_COST() -> None:
    rep = summarise([_r(tested=100, independent=1, cost_units=1)])
    assert "volume is a COST" in str(rep["note"])
