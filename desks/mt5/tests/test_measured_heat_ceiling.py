"""The heat ceiling is a reading of the growth curve, not a number somebody chose.

The principal removed the fixed 30% cap on 2026-09-05: "if growth optimum permits 32 35 40 45
wtv in future w new edges etc it can use those w 20 as minimum floor". The floor stays.

Deleting the constant would have been the wrong reading, and the constant says why: 0.30 recorded
a measurement in which the robust score was already NEGATIVE at 30% on the book as it stood.
Allowing 45% on that book would have been sizing into measured loss. So the bound became a
reading of the curve instead: it rises when new edges lift the curve, and falls below 30% when
the opportunity set is thin.

Pinned here: a richer curve earns more heat, a poorer one earns less, the bound never runs past
the last heat anyone actually measured, a missing curve is never permission, and the floor's cost
is recorded whenever the floor is what binds.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

hp = pytest.importorskip("research.heat_policy", reason="heat policy ships with the research pkg")


def _rising_to(top: float, peak_g: float = 0.0020) -> dict[float, float]:
    """A curve that climbs all the way to `top` -- a genuinely richer opportunity set."""
    return {round(h, 3): peak_g * (h / top) for h in
            [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45] if h <= top + 1e-9}


def test_a_richer_opportunity_set_earns_more_than_the_old_thirty_percent_cap() -> None:
    """THE INSTRUCTION. New edges lift the curve; the allocator may follow it up."""
    ceiling, why = hp.measured_ceiling(_rising_to(0.45))
    assert ceiling == pytest.approx(0.45)
    assert "45" in why
    assert ceiling > 0.30, "the old constant must no longer be the bound when growth supports more"


def test_a_thin_opportunity_set_is_held_tighter_than_the_old_cap() -> None:
    """The bound moves BOTH ways. A curve that turns at 22% must not permit 30%."""
    curve = {0.10: 0.0010, 0.15: 0.0018, 0.20: 0.0022, 0.22: 0.0023,
             0.25: 0.0009, 0.30: -0.0004, 0.35: -0.0020}
    ceiling, _ = hp.measured_ceiling(curve)
    assert ceiling < 0.30
    assert ceiling >= hp.HEAT_TARGET, "never below the mandate floor"


def test_the_bound_never_runs_past_the_last_heat_anyone_measured() -> None:
    """A heat nobody sampled is a heat nobody certified. This is the property that separates
    following evidence from extrapolating an overestimated edge, which is how Kelly sizing kills
    accounts."""
    ceiling, why = hp.measured_ceiling(_rising_to(0.30))
    assert ceiling == pytest.approx(0.30)
    assert "edge of the measurement" in why, "it must say the sweep, not the market, is the limit"


def test_an_unmeasured_curve_is_never_permission() -> None:
    """A monitoring gap must not read as 'unlimited'. That is how it becomes a margin call."""
    for curve in ({}, {0.2: 0.001}, {0.2: 0.001, 0.3: 0.002}):
        ceiling, why = hp.measured_ceiling(curve)
        assert ceiling == pytest.approx(hp.HEAT_HARD_CEILING)
        assert "UNMEASURED" in why and "not permission" in why


def test_a_curve_that_never_turns_positive_falls_to_the_floor() -> None:
    """No exposure is the growth optimum here. Only the mandate keeps the desk in the market,
    and the reason must say exactly that rather than implying the book is healthy."""
    curve = {0.10: -0.0004, 0.20: -0.0011, 0.30: -0.0030}
    ceiling, why = hp.measured_ceiling(curve)
    assert ceiling == pytest.approx(hp.HEAT_TARGET)
    assert "non-positive" in why and "floor" in why


def test_the_floor_binding_is_recorded_with_the_growth_it_costs() -> None:
    """"A real Tier-6 system should measure the incremental growth cost of that policy
    continuously, rather than hiding it." So the artifact carries it."""
    curve = {0.05: 0.0020, 0.10: 0.0024, 0.15: 0.0021, 0.20: 0.0014, 0.25: 0.0004}
    doc = hp.heat_accounting(raw=0.11, robust=0.10, curve=curve)
    assert doc["floor_binding"] is True
    assert doc["heat_deployed"] == pytest.approx(hp.HEAT_TARGET)
    # the robust optimum earned more per day than the mandated floor does; that gap is the price
    assert doc["growth_cost_of_floor_per_day"] > 0
    assert doc["growth_cost_of_floor_per_year"] == pytest.approx(
        doc["growth_cost_of_floor_per_day"] * 252.0, rel=1e-6)


def test_all_three_heats_are_reported_even_when_nothing_binds() -> None:
    """The unconstrained answer stays visible. A floor that is never audited is a belief."""
    doc = hp.heat_accounting(raw=0.32, robust=0.27, curve=_rising_to(0.45))
    assert doc["heat_raw"] == pytest.approx(0.32)
    assert doc["heat_robust"] == pytest.approx(0.27)
    assert doc["heat_deployed"] == pytest.approx(0.27)
    assert doc["floor_binding"] is False and doc["ceiling_binding"] is False
    assert "ceiling_reason" in doc and doc["ceiling_reason"]


def test_a_robust_optimum_above_the_measured_ceiling_is_clipped_and_said_so() -> None:
    curve = {0.10: 0.0010, 0.20: 0.0020, 0.25: 0.0021, 0.30: 0.0006, 0.35: -0.0009}
    doc = hp.heat_accounting(raw=0.50, robust=0.44, curve=curve)
    assert doc["ceiling_binding"] is True
    assert doc["heat_deployed"] == pytest.approx(doc["heat_ceiling"])
    assert doc["heat_deployed"] < 0.44
