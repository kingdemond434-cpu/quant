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
from types import SimpleNamespace

import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
for p in (str(_DESK), str(_DESK / "research")):
    if p not in sys.path:
        sys.path.insert(0, p)

from mt5desk import decision_core as dc  # noqa: E402
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


# ------------------------------------------------ the family lane's bracket, laid from the entry

def _sig(stop: float, target: float) -> SimpleNamespace:
    return SimpleNamespace(time=None, side=-1, stop=stop, target=target, ttl_bars=3)


def test_family_bracket_within_tolerance_sends_the_certified_levels() -> None:
    # EURGBP short off a close of 0.85585: certified stop 8.4 pips above, target 12.6 below.
    g = _sig(stop=0.85669, target=0.85459)
    entry, stop, target, dist, note, drift, verdict = dc.family_bracket(
        g, -1, bid=0.85590, ask=0.85600, signal_close=0.85585)
    assert entry == 0.85590 and (stop, target) == (0.85669, 0.85459)
    # Adverse for a short: the bid rose 0.5 pip of an 8.4-pip stop.
    assert drift == pytest.approx(0.00005 / 0.00084) and drift < dc.ENTRY_DRIFT_TOL_FRAC
    assert dist == pytest.approx(0.00079) and "levels as certified" in note
    assert verdict == "certified"


def test_family_bracket_past_tolerance_is_re_anchored_with_the_certified_rr() -> None:
    # The measured case: the quote had run 6.6 pips past the close by the time the pass arrived,
    # leaving 1.8 pips to the absolute stop. The distances are the certificate's; the anchor is
    # the fill.
    g = _sig(stop=0.85669, target=0.85459)
    entry, stop, target, dist, note, drift, verdict = dc.family_bracket(
        g, -1, bid=0.85651, ask=0.85661, signal_close=0.85585)
    assert drift == pytest.approx(0.00066 / 0.00084) and drift > dc.ENTRY_DRIFT_TOL_FRAC
    assert dist == pytest.approx(0.00084)
    assert stop == pytest.approx(0.85651 + 0.00084)
    assert target == pytest.approx(0.85651 - 0.00126)
    assert abs(target - entry) / abs(stop - entry) == pytest.approx(1.5)
    assert "re-anchored to the entry" in note and "R:R kept" in note
    assert verdict == "re_anchored"


def test_family_bracket_refuses_a_signal_the_market_has_already_stopped_or_paid() -> None:
    g = _sig(stop=0.85669, target=0.85459)
    # Adverse: the bid has crossed the certified stop since the close -- the replay is stopped.
    *_, note, drift, verdict = dc.family_bracket(g, -1, bid=0.85672, ask=0.85682,
                                                 signal_close=0.85585)
    assert verdict == "stale" and drift > 1.0 and "certified stop" in note
    # Favourable: the bid has reached the certified target -- the replay has taken its profit.
    *_, note, drift, verdict = dc.family_bracket(g, -1, bid=0.85455, ask=0.85465,
                                                 signal_close=0.85585)
    assert verdict == "stale" and drift < 0.0 and "certified target" in note


def test_family_bracket_without_a_signal_close_is_unmeasured_and_verbatim() -> None:
    g = _sig(stop=0.85669, target=0.85459)
    _entry, stop, target, dist, note, drift, verdict = dc.family_bracket(
        g, -1, bid=0.85651, ask=0.85661, signal_close=None)
    assert (stop, target) == (0.85669, 0.85459) and drift is None and verdict == "unmeasured"
    assert dist == pytest.approx(0.00018) and "UNMEASURED" in note
    # A certified stop AT the close is no distance at all.
    flat = _sig(stop=0.85585, target=0.85459)
    *_, dist, note, drift, verdict = dc.family_bracket(flat, -1, bid=0.85651, ask=0.85661,
                                                       signal_close=0.85585)
    assert dist == 0.0 and verdict == "degenerate"


def test_signal_with_levels_copies_a_dataclass_signal_and_a_plain_bag_without_mutation() -> None:
    from mt5desk.engine import Signal
    g = Signal(time=pd.Timestamp("2026-09-16T08:00:00Z"), side=-1, stop=0.85669,
               target=0.85459, ttl_bars=3, tag="discovered:x")
    h = dc.signal_with_levels(g, 0.85735, 0.85525)
    assert (h.stop, h.target, h.ttl_bars, h.tag) == (0.85735, 0.85525, 3, "discovered:x")
    assert (g.stop, g.target) == (0.85669, 0.85459)
    bag = _sig(stop=1.0, target=2.0)
    nb = dc.signal_with_levels(bag, 1.5, 2.5)
    assert (nb.stop, nb.target, nb.ttl_bars) == (1.5, 2.5, 3)
    assert (bag.stop, bag.target) == (1.0, 2.0)


def test_bar_already_traded_reads_only_entry_deals_under_the_sleeves_tag() -> None:
    deals = [SimpleNamespace(entry=1, comment="DWx", ticket=1, time=1_800_000_000),   # an exit
             SimpleNamespace(entry=0, comment="DWother", ticket=2, time=1_800_000_000),
             SimpleNamespace(entry=0, comment="DWx", ticket=3, time=1_800_000_000)]
    assert dc.bar_already_traded(deals[:2], "DWx") is None
    ticket, iso = dc.bar_already_traded(deals, "DWx")
    assert ticket == 3 and iso.startswith("2027-")
    assert dc.bar_already_traded([], "DWx") is None and dc.bar_already_traded(None, "DWx") is None
