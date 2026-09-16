"""Two money-path defects measured 2026-09-16 on the live account.

1. The 19:30 UTC gold-book backstop force-closed FAMILY-lane positions seconds after they opened
   (34 positions in 24h, -20.60 EUR of spread): `keep` protected the scalp lane only.
2. A scalp plan's stop landed 1.8 pips from entry on EURGBP -- inside the spread's reach -- and
   the lot sizer inverted it into 0.27 lots; three stop-outs for -11.87 EUR.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for p in (str(_DESK), str(_DESK / "research")):
    if p not in sys.path:
        sys.path.insert(0, p)

from mt5desk import gateway  # noqa: E402


def test_family_lane_positions_are_protected_from_the_close_hour_backstop() -> None:
    sleeves = [
        {"name": "eurchf_discovered_asia_p_6c", "exec": "family_market", "symbol": "EURCHF"},
        {"name": "xau_m15_anti_breakout", "exec": "scalp_market", "symbol": "XAUUSD"},
        {"name": "gold_asia", "exec": "bracket", "symbol": "XAUUSD"},
    ]
    fam = gateway.family_position_tags(sleeves)
    scalp = gateway.scalp_position_tags(sleeves)
    assert fam == {gateway.order_comment("eurchf_discovered_asia_p_6c")}
    assert scalp == {gateway.order_comment("xau_m15_anti_breakout")}
    # The gold window's own bracket stays closable: its tag is in neither set.
    assert gateway.order_comment("gold_asia") not in (fam | scalp)


@dataclass(frozen=True)
class _Plan:
    side: int
    entry_ref: float
    stop: float
    target: float
    stop_dist: float
    ttl_until: str = "2026-09-16T12:00:00+00:00"


@dataclass(frozen=True)
class _Tick:
    bid: float
    ask: float


def test_stop_inside_the_spread_is_floored_and_the_geometry_is_kept() -> None:
    # EURGBP: 1.0-pip spread, plan stop 1.8 pips, target 3.6 pips (2:1).
    plan = _Plan(side=-1, entry_ref=0.85651, stop=0.85669, target=0.85615, stop_dist=0.00018)
    tick = _Tick(bid=0.85651, ask=0.85661)
    new, note = gateway.floor_stop_to_spread(plan, tick)
    assert new.stop_dist >= gateway.MIN_STOP_SPREAD_MULT * 0.0001 - 1e-12
    assert abs(new.stop - plan.entry_ref) == pytest.approx(new.stop_dist)
    # Reward-to-risk preserved: target distance scaled by the same factor.
    rr_new = abs(new.target - plan.entry_ref) / new.stop_dist
    rr_old = abs(plan.target - plan.entry_ref) / plan.stop_dist
    assert rr_new == pytest.approx(rr_old)
    assert new.ttl_until == plan.ttl_until
    assert "target scaled" in note


def test_stop_already_outside_the_spread_is_untouched() -> None:
    plan = _Plan(side=1, entry_ref=0.94456, stop=0.94357, target=0.94654, stop_dist=0.00099)
    tick = _Tick(bid=0.94454, ask=0.94456)
    new, note = gateway.floor_stop_to_spread(plan, tick)
    assert new is plan and ">=" in note


def test_unreadable_tick_leaves_the_plan_as_planned() -> None:
    plan = _Plan(side=1, entry_ref=1.0, stop=0.999, target=1.002, stop_dist=0.001)
    new, note = gateway.floor_stop_to_spread(plan, _Tick(bid=0.0, ask=0.0))
    assert new is plan and "left as planned" in note
