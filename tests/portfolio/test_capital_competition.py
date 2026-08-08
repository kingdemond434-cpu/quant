"""NO STRATEGY OWNS ITS ALLOCATION BECAUSE IT GOT THERE FIRST.

Capital sitting in a strategy whose forward expectation has collapsed is not neutral: it is the
best remaining opportunity being declined, every day, silently.
"""

from __future__ import annotations

import pytest

from libs.portfolio.capital_competition import (
    MIN_MEANINGFUL_WEIGHT,
    AlphaCandidate,
    allocate,
    half_life_days,
    kelly_fraction,
    score,
    summarise,
)


def _a(**kw) -> AlphaCandidate:
    base = {"name": "a", "edge_bps": 2.0, "vol_bps": 10.0, "effective_n": 500.0}
    return AlphaCandidate(**{**base, **kw})


def test_AGE_IS_NOT_A_FIELD_AND_CANNOT_BE_AN_INPUT() -> None:
    """The mechanism by which incumbency confers privilege is simply not representable."""
    assert not any("age" in f or "since" in f or "incumb" in f
                   for f in AlphaCandidate.__dataclass_fields__)


def test_LIFETIME_PNL_IS_RECORDED_AND_NEVER_SCORED() -> None:
    """A strategy can be +500 lifetime on luck while its forward expectation is zero, and a new
    one slightly negative on variance while carrying excellent evidence. Funding the first and
    starving the second is the natural reading of a P&L table and it is backwards."""
    rich = _a(name="rich", lifetime_pnl=500_000.0)
    poor = _a(name="poor", lifetime_pnl=-2_000.0)
    assert score(rich)[0] == pytest.approx(score(poor)[0])


def test_AN_IDENTICAL_TWIN_OF_THE_BOOK_SCORES_ZERO() -> None:
    """At rho=1 the alpha adds exposure and no diversification, so marginal contribution is zero
    however good its standalone Sharpe looks."""
    s, why = score(_a(correlation_to_book=1.0))
    assert s == 0.0
    assert "nothing incremental" in why


def test_A_NEGATIVE_EDGE_IS_CAPITAL_BEING_DECLINED_ELSEWHERE() -> None:
    s, why = score(_a(edge_bps=-1.0))
    assert s < 0
    assert "next-best opportunity being declined" in why


def test_UNCERTAINTY_SHRINKS_BUT_DOES_NOT_VETO() -> None:
    """The whole point of a canary: learning while earning. Zero-until-certain-then-full throws
    away the option value of the learning period."""
    thin = _a(name="thin", effective_n=10.0)
    assert 0 < thin.confidence < 0.25
    assert score(thin)[0] > 0, "a thin-evidence alpha still earns a real, small position"


def test_CONFIDENCE_IS_CAPPED_BELOW_ONE() -> None:
    """The edge is an estimate and Kelly's penalty for over-betting one is asymmetric."""
    assert _a(effective_n=1_000_000.0).confidence < 1.0


def test_AN_UNMEASURED_ALPHA_SCORES_ZERO_AS_A_STATEMENT_ABOUT_EVIDENCE() -> None:
    s, why = score(_a(effective_n=0.0))
    assert s == 0.0
    assert "not about the alpha" in why


def test_A_BETTER_NEW_ALPHA_TAKES_RISK_FROM_A_WORSE_INCUMBENT() -> None:
    """A new survivor economically superior to an incumbent must be able to displace it."""
    old = _a(name="incumbent", edge_bps=1.0, effective_n=5000.0, state="LIVE")
    new = _a(name="newcomer", edge_bps=4.0, effective_n=400.0, state="LIVE_CANARY")
    w = allocate([old, new])
    assert w["newcomer"] > w["incumbent"]


def test_A_DEAD_INCUMBENT_GOES_TO_ZERO_THE_SAME_RUN() -> None:
    dead = _a(name="dead", edge_bps=-0.5, effective_n=9000.0)
    live = _a(name="live", edge_bps=3.0)
    w = allocate([dead, live])
    assert w["dead"] == 0.0 and w["live"] > 0


def test_A_SUB_MEANINGFUL_WEIGHT_IS_REPORTED_AS_ZERO() -> None:
    """A 0.02% allocation pays fees to express an opinion too small to matter."""
    strong = _a(name="strong", edge_bps=50.0)
    tiny = _a(name="tiny", edge_bps=0.02, effective_n=40.0)
    w = allocate([strong, tiny])
    assert w["tiny"] == 0.0
    assert w["strong"] > MIN_MEANINGFUL_WEIGHT


def test_CAPACITY_EXCESS_IS_LEFT_UNALLOCATED_NOT_PUSHED_ELSEWHERE() -> None:
    """Silently over-funding a weaker mechanism because a stronger one filled up is how a capacity
    limit becomes a sizing error."""
    capped = _a(name="capped", edge_bps=10.0, capacity=0.10)
    weak = _a(name="weak", edge_bps=0.5)
    rep = summarise([capped, weak])
    assert float(rep["risk_unallocated"]) > 0
    assert "UNALLOCATED" in str(rep["headline"])


def test_NO_POSITIVE_SCORES_MEANS_NOTHING_IS_FUNDED() -> None:
    w = allocate([_a(name="x", edge_bps=-1.0), _a(name="y", edge_bps=-2.0)])
    assert set(w.values()) == {0.0}


def test_AN_EMPTY_BOOK_IS_NOT_SAFE() -> None:
    assert "best remaining opportunity being declined" in str(summarise([])["headline"])


def test_KELLY_SHRINKS_THE_EDGE_BEFORE_THE_RATIO() -> None:
    """Over-betting an over-estimated edge loses more growth than under-betting the same edge
    gains, so shrinking first is the conservative order and it is not the intuitive one."""
    assert kelly_fraction(4.0, 10.0, 0.2) < kelly_fraction(4.0, 10.0, 0.9)
    assert kelly_fraction(4.0, 0.0, 0.9) == 0.0
    assert kelly_fraction(1e9, 10.0, 1.0) <= 0.25, "capped"


def test_HALF_LIFE_IS_NONE_WHEN_THE_EDGE_IS_NOT_DECAYING() -> None:
    """None rather than infinity: a caller formatting infinity prints something meaningless."""
    # edge_now < edge_then IS the decay direction. Halving over 10 days is a 10-day half-life.
    assert half_life_days(1.0, 2.0, 10.0) == pytest.approx(10.0)
    assert half_life_days(2.0, 1.0, 10.0) is None, "an edge that GREW is not decaying"
    assert half_life_days(1.0, 2.0, 0.0) is None, "no elapsed time, nothing measurable"


def test_IT_PLACES_NOTHING() -> None:
    from pathlib import Path
    src = Path("libs/portfolio/capital_competition.py").read_text("utf-8").lower()
    for token in ("place_order", "place_market", "api_key", "def arm"):
        assert token not in src
    assert "places nothing, arms nothing" in src
