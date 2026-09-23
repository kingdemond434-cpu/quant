"""A LIVE SLEEVE IS NEVER SKIPPED FOR BEING UNSIZEABLE -- principal's order, 2026-09-12.

    "all sleeves must trade at least 0.01 lots overriding the risk per trade cuz thats broker
    minimum no matter what"

Two paths used to return 0.0 and three gateway sites then logged "allocator gave this sleeve no
heat; skipped":

    decision_core.promoted_lot   when the allocator's fraction for a rostered sleeve was zero
    sizing.risk_lot              when the venue's own minimum risked more than 2x the target

Both now return the venue minimum. These tests pin the order, and they pin the three things that
make it correct rather than merely obedient -- because the failure modes of a naive reading are
worse than the skip it replaces.
"""
from __future__ import annotations

import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import decision_core as core  # noqa: E402
from mt5desk import sizing  # noqa: E402


def test_a_zeroed_sleeve_now_trades_the_venue_minimum() -> None:
    """The order itself: the allocator declining no longer means no trade."""
    lot = core.promoted_lot(607.68, 100, dist_usd=0.005, symbol="EURUSD",
                            risk_frac=0.0, from_book=True)
    assert lot > 0.0, "a rostered sleeve the allocator zeroed must still trade"
    assert lot == core.venue_min_lot("EURUSD")


def test_the_venue_minimum_is_per_symbol_and_not_a_literal() -> None:
    """0.01 IS NOT THE BROKER MINIMUM EVERYWHERE.

    universe.json records share CFDs at volume_min 0.1. An order below a symbol's own minimum is
    not a small trade, it is a REJECTED one -- which would be a worse outcome than the skip this
    order replaces, and it would look like the order working.
    """
    assert core.venue_min_lot("EURUSD") == 0.01
    for share_cfd in ("3M", "ADP"):
        assert core.venue_min_lot(share_cfd) == 0.1, (
            f"{share_cfd} requires 0.1 on this venue; 0.01 would be rejected, not small")


def test_gold_keeps_its_higher_desk_floor_on_the_gold_path() -> None:
    """A DESK policy floor is not a BROKER floor, and they are enforced in different places.

    The principal set gold at 0.02 on 2026-09-07. That is a policy decision and it lives on the
    gold path (`gold_min_lot` / `gold_lot`), which is where it has always been enforced.
    `venue_min_lot` answers the other question -- the smallest ticket the BROKER will accept --
    and for gold that is 0.01. Folding the policy floor into the venue one raised gold's floor
    inside `promoted_lot`, a path that has always floored gold at 0.01, and the stop-aware
    sizing fence caught it immediately.
    """
    assert core.gold_min_lot() == 0.02, "the principal's gold floor stands"
    assert core.venue_min_lot(core.GOLD_SYMBOL) == 0.01, "this is the VENUE's number"
    assert core.gold_lot(607.68, 20.0) >= 0.02, "the gold path enforces the policy floor"


def test_an_unknown_symbol_falls_back_to_the_desk_floor_and_still_trades() -> None:
    """This function exists to make a trade happen; refusing here reinstates the skip."""
    assert core.venue_min_lot("NO_SUCH_SYMBOL_XYZ") == core.min_lot()


def test_risk_lot_no_longer_refuses_when_the_minimum_blows_the_target() -> None:
    """The 2x refusal is what the order replaces. The overshoot is real and is REPORTED."""
    lots = sizing.risk_lot(equity=607.68, sl_dist_price=0.0050, tick_value=1.0,
                           tick_size=0.00001, volume_min=0.1, volume_step=0.1,
                           volume_max=5.0, risk_frac=0.03, live_n=0)
    assert lots == 0.1, "the venue minimum overrides the risk target"


def test_risk_lot_still_refuses_genuinely_unpriceable_inputs() -> None:
    """A non-positive stop or tick value is UNPRICEABLE, not merely small.

    The order removes a RISK refusal. It does not ask the desk to send an order it cannot price,
    and sizing from a degenerate input is how a position gets an arbitrary size rather than a
    large one.
    """
    for bad in ({"sl_dist_price": 0.0}, {"tick_value": 0.0}, {"tick_size": 0.0},
                {"equity": 0.0}, {"volume_min": 0.0}, {"volume_step": 0.0}):
        args = {"equity": 607.68, "sl_dist_price": 0.005, "tick_value": 1.0,
                "tick_size": 0.00001, "volume_min": 0.01, "volume_step": 0.01,
                "volume_max": 5.0, **bad}
        assert sizing.risk_lot(**args) == 0.0, f"{bad} is unpriceable and must not size"


def test_the_venue_maximum_still_caps_the_floor() -> None:
    """A floor above the venue's MAXIMUM is the same rejected order at the other end."""
    lots = sizing.risk_lot(equity=607.68, sl_dist_price=0.0050, tick_value=1.0,
                           tick_size=0.00001, volume_min=0.5, volume_step=0.5,
                           volume_max=0.2, risk_frac=0.03, live_n=0)
    assert lots == 0.2
