"""The allocator sizes the gold book, and it can only ever raise the lot.

Tier-1 P1, closed 2026-09-09. `roster` already stamped the optimiser's h_i and billed heat at it
on every gold row the certified book contained, and the placement site tested `lot == "auto"`
first -- so gold fell through to the policy lot and the fraction that maximised E[log W] jointly
with every other sleeve was computed, charged, and thrown away at the venue.

The half of the fix that matters most is the direction. Routing gold at h_i ALONE would be a size
CUT at today's equity, on the only book with forward evidence behind it, delivered as better
sizing. `max(h_i lot, gold_lot)` closes the break upward only.
"""
from __future__ import annotations

import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import decision_core as dc  # noqa: E402

EQUITY = 20_000.0
DIST = 5.0


class _Info:
    """The venue fields `auto_lot` prices risk from. Gold on a five-digit CFD feed."""

    trade_tick_value = 1.0
    trade_tick_size = 0.01
    volume_min = 0.01
    volume_step = 0.01
    volume_max = 100.0
    digits = 2


INFO = _Info()


def _policy() -> float:
    return dc.gold_lot(EQUITY, DIST, INFO)


def test_the_allocator_never_makes_the_gold_book_smaller() -> None:
    """THE STANDING ORDER IN ARITHMETIC. Sweep the fraction from far below the policy lot to far
    above it: the sent lot is never below what the desk sends today, at any fraction."""
    policy = _policy()
    for h_i in (1e-9, 0.0001, 0.001, 0.005, 0.01, 0.02, 0.05, 0.10, 0.30, 1.0):
        lot, basis = dc.gold_book_lot(EQUITY, DIST, INFO, h_i)
        assert lot >= policy - 1e-12, f"h_i={h_i} sized {lot} below today's {policy}: {basis}"


def test_a_fraction_the_optimiser_wants_larger_actually_raises_the_lot() -> None:
    """The growth case, and the whole reason h_i exists: when the optimiser wants MORE gold than
    fixed-fractional sizing asks for, gold gets more."""
    policy = _policy()
    big, basis = dc.gold_book_lot(EQUITY, DIST, INFO, 0.50)
    assert big > policy, f"a 50% fraction must outsize the policy lot {policy}"
    assert "allocator_book" in basis and "above the gold policy lot" in basis


def test_no_fraction_and_a_zeroed_window_both_fall_back_to_the_policy_lot() -> None:
    """A zeroed sleeve is a skip everywhere else. For gold that skip would be a size cut to
    nothing on the book the principal's order protects, so it falls back and SAYS so."""
    policy = _policy()
    for h_i, expect in ((None, "not a number"), ("", "not a number"), (0.0, "no heat"),
                        (-1.0, "no heat")):
        lot, basis = dc.gold_book_lot(EQUITY, DIST, INFO, h_i)
        assert lot == policy and expect in basis, (h_i, lot, basis)


def test_the_fade_flag_still_applies_and_is_reduce_only() -> None:
    """A faded window's allocator lot is smaller -- but the floor still catches it, so the fade
    can lower the ALLOCATOR term without ever lowering the sent lot below today's."""
    policy = _policy()
    healthy, _ = dc.gold_book_lot(EQUITY, DIST, INFO, 0.50, None)
    faded, _ = dc.gold_book_lot(EQUITY, DIST, INFO, 0.50, True)
    assert faded <= healthy, "the fade may only reduce the allocator's term"
    assert faded >= policy, "and it may never take the book below its policy lot"


def test_the_outer_per_trade_envelope_still_caps_the_fraction() -> None:
    """MAX_RISK_FRAC is the outer per-trade envelope and raising it is a principal act. A
    fraction above it must size as if it were at it."""
    at_cap, _ = dc.gold_book_lot(EQUITY, DIST, INFO, dc.MAX_RISK_FRAC)
    over_cap, _ = dc.gold_book_lot(EQUITY, DIST, INFO, dc.MAX_RISK_FRAC * 10.0)
    assert over_cap == at_cap


def test_the_basis_always_names_which_term_set_the_size() -> None:
    for h_i in (None, 0.0, 0.001, 0.50):
        _, basis = dc.gold_book_lot(EQUITY, DIST, INFO, h_i)
        assert basis and ("gold_lot" in basis or "allocator_book" in basis)


def test_the_gateway_routes_the_gold_branch_through_it() -> None:
    """The wiring, pinned in source: gateway.py cannot import MetaTrader5 here, so the placement
    site is read rather than run. If this branch is ever reverted to the bare policy lot, the
    semantic break returns silently and this test is what catches it."""
    src = (_DESK / "mt5desk" / "gateway.py").read_text("utf-8")
    assert "gold_book_lot as gold_book_lot" in src, "the gateway must import it"
    assert "lot, _lot_basis = gold_book_lot(" in src
    assert 'lot = gold_lot(equity, dist, sym) if s["lot"] == "auto"' not in src, \
        "the old auto branch is back and the allocator no longer sizes gold"
    assert 's.get("sized_by") == "allocator_book"' in src
    assert "gold sizing basis" in src, "the log must say which term set the size"


def test_the_floor_and_the_envelope_constants_are_untouched() -> None:
    src = (_DESK / "mt5desk" / "decision_core.py").read_text("utf-8")
    assert "max(auto_lot(equity, dist_usd, GOLD_SYMBOL, info), gold_min_lot())" in src, \
        "gold_lot must still floor at the principal's minimum"
    assert dc.gold_min_lot() >= 0.02 - 1e-12
