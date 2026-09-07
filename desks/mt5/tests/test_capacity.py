"""CAPACITY: the floor binds long before any ceiling does, and the ceiling is refused.

One of the twelve capability groups `ontology.unaddressed()` reports as owned by no module here.
The institutional version of this question -- "at what size does my own order move the price" --
is the WRONG one at EUR 742 on 0.01-lot minimums, and importing its machinery would be complexity
rent: modelling the impact of orders that have none.

The binding constraint at this size is a LOWER bound. The venue's minimum lot forces more risk
per trade than the policy asks for, which is exactly why `decision_core.realised_q` exists -- "a
book configured for 0.75% could run at 5.9% with nothing in the code, the log or the state file
ever saying so". Nothing reported it per sleeve until now.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parent.parent
for _p in (str(BASE), str(BASE.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import decision_core as core  # noqa: E402
from research import capacity  # noqa: E402


def test_the_floor_binding_equity_is_the_min_lot_risk_over_the_target() -> None:
    """Exact, not modelled. One minimum lot risks a knowable number of EUR."""
    q = 0.005
    expected = core.min_lot_risk_eur("XAUUSD", None) / q
    assert capacity.floor_binding_equity(q, "XAUUSD") == pytest.approx(expected)


def test_this_desks_actual_account_is_deep_inside_the_binding_region() -> None:
    """The measurement that makes the module worth having.

    At EUR 742 a sleeve targeting 0.5% runs several times that, because 0.01 lots of gold risks
    far more than 0.5% of this account. That is not a modelling opinion -- it is arithmetic on
    the venue's own minimum, and no state file was saying it.
    """
    over = capacity.realised_over_policy(742.0, 0.005, "XAUUSD")
    assert over > 2.0, "expected the lot floor to dominate at this account size"
    assert capacity.floor_binding_equity(0.005, "XAUUSD") > 742.0


def test_a_large_enough_account_runs_exactly_its_policy() -> None:
    """Above the binding equity the floor stops mattering and the multiple is exactly 1."""
    q = 0.005
    big = capacity.floor_binding_equity(q, "XAUUSD") * 10
    assert capacity.realised_over_policy(big, q, "XAUUSD") == pytest.approx(1.0)


def test_the_multiple_falls_monotonically_as_equity_grows() -> None:
    """A capacity curve that is not monotone in the floor regime is a computation defect."""
    q = 0.005
    curve = capacity.capacity_curve(q, "XAUUSD")
    vals = [row["over_policy"] for row in curve]
    assert vals == sorted(vals, reverse=True)
    assert vals[-1] == pytest.approx(1.0)
    assert curve[0]["binding"] is True


def test_a_sleeve_with_no_declared_target_is_unmeasured_not_assumed() -> None:
    """There is no policy for the floor to be compared against, and inventing one would lie.

    UNMEASURED IS A VERDICT, NOT A ZERO -- the desk's standing rule, and the reason this returns
    a status rather than defaulting q_target to something plausible.
    """
    row = capacity.assess({"name": "no_policy", "symbol": "EURUSD"}, 742.0)
    assert row["status"] == "UNMEASURED"
    assert "no target risk fraction" in row["why"]
    assert capacity.over_risked([row]) == []


def test_a_zero_target_reports_infinite_rather_than_a_comparable_number() -> None:
    """A sleeve targeting no risk is over-sized by any lot at all.

    Returning a finite number would invite the reader to compare it with a real one.
    """
    assert capacity.floor_binding_equity(0.0, "XAUUSD") == float("inf")
    assert capacity.realised_over_policy(742.0, 0.0, "XAUUSD") == float("inf")


def test_the_ceiling_is_refused_rather_than_estimated() -> None:
    """Market impact needs realised fills, and matched_fills is 0 -- nothing has ever filled.

    A ceiling derived from a cost model nobody has validated against a fill is a number that
    would be believed and should not be. This is the same discipline the execution panel already
    applies to markout.
    """
    row = capacity.assess({"name": "g", "symbol": "XAUUSD", "q_target": 0.005}, 742.0)
    assert row["ceiling_eur"] is None
    assert row["ceiling_status"] == "UNMEASURED"
    assert "matched_fills is 0" in row["ceiling_why"]


def test_over_risked_is_the_consumer_that_makes_this_more_than_an_artifact() -> None:
    """A capability that writes a file nobody reads is code, not a capability."""
    rows = [
        capacity.assess({"name": "bound", "symbol": "XAUUSD", "q_target": 0.005}, 742.0),
        capacity.assess({"name": "free", "symbol": "XAUUSD", "q_target": 0.005}, 10_000_000.0),
    ]
    flagged = [r["sleeve"] for r in capacity.over_risked(rows)]
    assert "bound" in flagged
    assert "free" not in flagged


def test_the_tolerance_is_a_reporting_threshold_and_is_pinned() -> None:
    """Reporting less over-risk does not make an account safer.

    Pinned so it cannot drift upward to quiet a board -- the same rule as every other threshold
    on this desk.
    """
    assert capacity.OVER_RISK_TOLERANCE == 1.25


def test_measure_survives_an_empty_desk() -> None:
    """It runs on a tree with no roster and no state file, and says so rather than raising."""
    out = capacity.measure(sleeves=[], equity=742.0)
    assert out["sleeves"] == 0
    assert out["ceiling_status"] == "UNMEASURED"
    assert "FLOOR problem" in out["law"]


def test_headroom_says_how_much_room_this_account_has_left() -> None:
    """The small-capital advantage stated as a number.

    An edge whose floor stops binding only far above this account is one a large fund cannot
    hold -- that is an asset, and it should be legible as one.
    """
    row = capacity.assess({"name": "g", "symbol": "XAUUSD", "q_target": 0.005}, 742.0)
    assert row["headroom_multiple"] > 1.0
    assert row["headroom_multiple"] == pytest.approx(
        row["floor_binding_below_eur"] / 742.0, rel=1e-3)
