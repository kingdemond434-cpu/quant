"""A SCHEDULER SLOWER THAN THE EDGE IT IS WATCHING, AND THE LOSS IS INVISIBLE.

A job running hourly against a 20-minute half-life does not error, does not log, and reports
healthy. It simply never observes what opened and closed between fires -- and every metric the
desk keeps is computed over what WAS observed, so the missed fraction appears in none of them.
"""

from __future__ import annotations

import pytest

from libs.research.cadence_alignment import (
    MIN_SURVIVING_FRACTION,
    StrategyCadence,
    alignment,
    cadence_regret,
    recommended_mechanism,
    required_interval_minutes,
    summarise,
)


def _c(**kw) -> StrategyCadence:
    base = {"strategy": "s", "half_life_minutes": 60.0, "interval_minutes": 15.0}
    return StrategyCadence(**{**base, **kw})


def test_THE_SURVIVING_FRACTION_IS_THE_DECAY_LAW() -> None:
    """One half-life of waiting leaves half the edge, by definition."""
    assert _c(half_life_minutes=60, interval_minutes=60).surviving_fraction == pytest.approx(0.5)
    assert _c(half_life_minutes=60, interval_minutes=0.001).surviving_fraction > 0.99


def test_A_SCHEDULER_MUCH_SLOWER_THAN_THE_HALF_LIFE_IS_TOO_SLOW() -> None:
    v, why = alignment(_c(half_life_minutes=20, interval_minutes=60))
    assert v == "TOO_SLOW"
    assert "The loss is INVISIBLE" in why
    assert "does not error" in why


def test_A_FAST_ENOUGH_SCHEDULER_IS_ALIGNED() -> None:
    v, _ = alignment(_c(half_life_minutes=240, interval_minutes=15))
    assert v == "ALIGNED"


def test_A_HARD_FLOOR_IS_CHECKED_BEFORE_TOO_SLOW() -> None:
    """A strategy watching a daily bar cannot be observed faster than the bar exists, and a fence
    that emits impossible work gets muted -- taking its real findings with it."""
    v, why = alignment(_c(half_life_minutes=5, interval_minutes=1440,
                          hard_floor_reason="daily settlement bar"))
    assert v == "FLOORED"
    assert "cannot be shortened" in why
    assert "never the schedule" in why


def test_NO_HALF_LIFE_MEANS_THE_CADENCE_CAN_NEITHER_BE_JUSTIFIED_NOR_REFUSED() -> None:
    v, why = alignment(_c(half_life_minutes=0))
    assert v == "UNMEASURED"
    assert "outlive every assumption behind it" in why


def test_THE_REQUIRED_INTERVAL_INVERTS_THE_DECAY() -> None:
    need = required_interval_minutes(60.0, surviving=0.5)
    assert need == pytest.approx(60.0)
    assert required_interval_minutes(0.0) is None
    assert required_interval_minutes(60.0, surviving=1.0) is None


def test_THE_RECOMMENDATION_IS_THE_CHEAPEST_MECHANISM_THAT_SERVES() -> None:
    """Faster is not free: polling costs rate limit, compute and contention with the recorders,
    which write the one asset that cannot be re-acquired at any price."""
    assert recommended_mechanism(2000) == "daily periodic"
    assert recommended_mechanism(90) == "hourly periodic"
    assert recommended_mechanism(10) == "high-frequency polling"
    assert recommended_mechanism(0.2) == "websocket / event-driven stream"


def test_REGRET_IS_A_LOWER_BOUND_AND_SAYS_SO() -> None:
    """It prices only decay on opportunities still SEEN. Ones that opened and closed between fires
    are invisible to any measurement taken at the fire, so counting them would need a model of
    what was never observed."""
    lost, why = cadence_regret(_c(half_life_minutes=30, interval_minutes=60,
                                  edge_bps=2.0, opportunities_per_day=10.0))
    assert lost > 0
    assert "LOWER BOUND" in why
    assert "invisible to any measurement taken at the fire" in why


def test_UNMEASURED_REGRET_IS_ZERO_AND_STATES_WHY() -> None:
    """Zero here means nothing was measured, never that nothing was lost."""
    lost, why = cadence_regret(_c(edge_bps=0.0))
    assert lost == 0.0
    assert "never that nothing was lost" in why


def test_THE_HEADLINE_LEADS_WITH_TOO_SLOW_RANKED_BY_REGRET() -> None:
    rows = [
        _c(strategy="fine", half_life_minutes=600, interval_minutes=15),
        _c(strategy="slow_cheap", half_life_minutes=10, interval_minutes=60,
           edge_bps=1.0, opportunities_per_day=1.0),
        _c(strategy="slow_costly", half_life_minutes=10, interval_minutes=60,
           edge_bps=5.0, opportunities_per_day=20.0),
    ]
    rep = summarise(rows)
    assert rep["too_slow"] == 2
    assert str(rep["rows"][0]["strategy"]) == "slow_costly", "worst regret must lead"
    assert "costing at least" in str(rep["headline"])


def test_AN_EMPTY_ROSTER_IS_ITSELF_THE_FINDING() -> None:
    assert "somebody picked" in str(summarise([])["headline"])


def test_IT_IS_NOT_THE_SAME_QUESTION_AS_CADENCE_ROI() -> None:
    """cadence_roi asks whether a job PRODUCES per fire. This asks whether it can still be in
    time. A job can be productive on every fire and lose most of the edge."""
    note = str(summarise([_c()])["note"])
    assert "NOT `cadence_roi`" in note
    assert "only ever sees what survived until it looked" in note


def test_THE_ALIGNMENT_THRESHOLD_IS_NOT_NEAR_PERFECT_ON_PURPOSE() -> None:
    """Demanding 95% capture would push every strategy to streaming and spend the box's capacity
    on horizons that do not need it."""
    assert 0.5 < MIN_SURVIVING_FRACTION < 0.9
