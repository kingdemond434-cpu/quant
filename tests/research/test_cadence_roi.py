"""EVERY CADENCE ON THIS DESK WAS CHOSEN RATHER THAN MEASURED.

L1.28c says every schedule hunts its own ceiling; nothing had ever checked whether one is at it. The
asymmetry these tests protect: an over-run job shows up in a cost report, while an under-run one
simply finds less than it could have, forever, and nothing records the difference.
"""

from __future__ import annotations

from libs.research.cadence_roi import (
    MIN_FIRES_FOR_VERDICT,
    CadenceRecord,
    assess,
    render,
    summarise,
)


def _r(**kw) -> CadenceRecord:
    base = {"job": "j", "interval_minutes": 60.0}
    return CadenceRecord(**{**base, **kw})


def test_A_JOB_PRODUCTIVE_ALMOST_EVERY_FIRE_SHOULD_TIGHTEN() -> None:
    """The interval is the binding constraint, and the value left on the table is invisible because
    nothing errors."""
    v, why = assess(_r(fires=20, productive_fires=18))
    assert v == "TIGHTEN"
    assert "INTERVAL is the binding constraint" in why
    assert "Halve the interval" in why


def test_A_MOSTLY_BARREN_JOB_MAY_LOOSEN_ONLY_ON_A_MEASURED_YIELD() -> None:
    v, why = assess(_r(fires=100, productive_fires=3, cost_per_fire=2.0))
    assert v == "LOOSEN"
    assert "measured rather than assumed" in why


def test_AN_UNMEASURED_CADENCE_IS_NEVER_SLOWED() -> None:
    """Otherwise absence of evidence buys a reduction, which is exactly the route by which a desk
    talks itself into doing less (L1.28)."""
    v, why = assess(_r(fires=MIN_FIRES_FOR_VERDICT - 1, productive_fires=0))
    assert v == "UNMEASURED"
    assert "THE CADENCE STANDS" in why


def test_YIELD_IS_NONE_RATHER_THAN_ZERO_WHEN_UNMEASURED() -> None:
    """0.0 reads as 'measured and barren'."""
    assert _r(fires=2, productive_fires=0).yield_per_fire is None
    assert _r(fires=50, productive_fires=0).yield_per_fire == 0.0


def test_A_HARD_FLOOR_IS_CHECKED_BEFORE_ANY_UNDER_RUN_VERDICT() -> None:
    """A job that CANNOT run more often is not under-run however high its yield -- recommending a
    tighter interval there produces a queue of impossible work, which is how a fence gets ignored.
    """
    v, why = assess(_r(fires=50, productive_fires=50,
                       hard_floor_reason="funding settles every 8h"))
    assert v == "FLOORED"
    assert "cannot tighten" in why
    assert "PARALLELISM or scope per fire" in why


def test_A_WELL_TUNED_CADENCE_HOLDS() -> None:
    assert assess(_r(fires=50, productive_fires=20))[0] == "HOLD"


def test_YIELD_IS_PER_FIRE_NOT_PER_DAY() -> None:
    """A job fired 24 times for 2 findings and one fired twice for the same 2 have identical daily
    output and OPPOSITE verdicts. Per-fire is the only ratio that separates them."""
    busy = _r(job="busy", interval_minutes=60, fires=24, productive_fires=2, cost_per_fire=1)
    lean = _r(job="lean", interval_minutes=720, fires=24, productive_fires=22)
    assert assess(busy)[0] == "LOOSEN"
    assert assess(lean)[0] == "TIGHTEN"


def test_THE_HEADLINE_LEADS_WITH_UNDER_RUN_JOBS() -> None:
    """Those are the invisible loss; an over-run job at least appears in a cost report."""
    rep = summarise([_r(job="under", fires=20, productive_fires=19),
                     _r(job="over", fires=20, productive_fires=1)])
    assert "UNDER-RUN and leaving value on the table" in str(rep["headline"])
    assert str(rep["rows"][0]["job"]) == "under"


def test_WITH_NO_UNDER_RUN_JOBS_THE_HEADLINE_NAMES_THE_UNMEASURED_ONES() -> None:
    rep = summarise([_r(job="a", fires=2), _r(job="b", fires=3)])
    assert "unmeasured" in str(rep["headline"])
    assert "may be slowed on an unmeasured yield" in str(rep["headline"])


def test_AN_EMPTY_ROSTER_IS_ITSELF_THE_FINDING() -> None:
    rep = summarise([])
    assert "CHOSEN rather than measured" in str(rep["headline"])
    assert "that is the finding" in str(rep["headline"])


def test_RENDER_NAMES_THE_INTERVAL_AND_THE_REASON() -> None:
    out = render([_r(job="frontier", interval_minutes=1440, fires=30, productive_fires=29)])
    assert "TIGHTEN" in out and "frontier" in out and "1440min" in out
