"""Fixed-fractional sizing is lot = budget / stop. Using the wrong stop is the
whole error, and it is invisible: every number downstream stays self-consistent.

The gateway sized every sleeve from DIST_USD = 19.1 while the caller held the
real bracket on the line above. The live brackets on 2026-08-14 ran from $18.65
to $53.40, so two of four sleeves traded at ~2.5-2.8x their stated budget at
every equity, and the three-leg book believed it was inside a 3.81% cap while
running closer to 8%.
"""

from __future__ import annotations

import ast
import math
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

from mt5desk import decision_core as _dc  # noqa: E402

_SRC = (_DESK / "mt5desk" / "gateway.py").read_text(encoding="utf-8")
_CORE_SRC = (_DESK / "mt5desk" / "decision_core.py").read_text(encoding="utf-8")

#: The armed brackets as the live state file recorded them.
LIVE_STOPS = {"asia": 53.40, "london_am": 27.91, "ny_open": 18.65,
              "afternoon": 48.64}


def _load():
    """The sizing laws, IMPORTED from the decision core (split 2026-09-05) rather than
    AST-extracted out of a gateway that imports MetaTrader5. Same functions, same names; the
    difference is that the coverage report now sees them execute."""
    return dict(vars(_dc))


NS = _load()

#: EUR risked per 1.0 USD/oz per lot of gold, READ FROM THE VENUE rather than from
#: `CONTRACT_OZ * FX_EUR`. Those constants said 92.00; the broker's own tick value says 86.41,
#: so every expectation below that was written against the constant was 6.5% off -- not because
#: the sizing was wrong but because a frozen EUR/USD rate had drifted. See mt5desk.risk_units.
GOLD_PU = NS["_eur_per_price_unit"](NS["GOLD_SYMBOL"])


def _spec(stop, price=4360.0):
    return {"buy_stop": {"price": price, "sl": price - stop, "tp": price + 2 * stop},
            "sell_stop": {"price": price - stop, "sl": price, "tp": price - 3 * stop}}


# ------------------------------------------------------ the stop is readable

def test_the_bracket_reports_its_own_stop():
    assert NS["stop_distance"](_spec(53.40)) == pytest.approx(53.40)


def test_a_spec_with_no_usable_stop_returns_None_rather_than_a_fallback():
    """A caller that cannot see the real stop must decide what to do about it.
    Substituting the house average silently is the defect being fixed."""
    assert NS["stop_distance"]({}) is None
    assert NS["stop_distance"]({"buy_stop": {"price": 4360.0, "sl": 4360.0}}) is None
    assert NS["stop_distance"](None) is None


# --------------------------------------------------- the size tracks the stop

def test_a_wider_stop_buys_a_smaller_lot():
    """THE INVARIANT. lot = budget / stop, so doubling the stop halves the lot."""
    eq = 25_000.0
    narrow = NS["auto_lot"](eq, 19.1)
    wide = NS["auto_lot"](eq, 38.2)
    assert wide < narrow
    assert wide == pytest.approx(narrow / 2, rel=0.06)


def test_every_live_sleeve_lands_within_a_lot_step_of_policy():
    """The property that was false. At EUR 25,000 the grain is fine enough that
    realised q should sit at Q_OPT for every sleeve regardless of its stop.

    THE TOLERANCE IS DERIVED, NOT TYPED. It was `abs=0.0015`, a band that happened to fit
    while gold was priced at the frozen `CONTRACT_OZ * FX_EUR` = 92.00. At the venue's true
    86.41 the asia leg snaps to 1.107% and the hardcoded band failed -- for the LOT GRAIN, not
    for a sizing error. One lot step on a $53.40 stop at EUR 25,000 is 0.185% of equity, so a
    fixed 0.15% band was asserting something finer than the venue can express, and any change
    to gold's tick value would have broken it again. The invariant this test is named for is
    "within one lot step, and never above policy"; that is now what it checks.
    """
    eq = 25_000.0
    for name, stop in LIVE_STOPS.items():
        q = NS["realised_q"](eq, stop)
        step_q = 0.01 * stop * GOLD_PU / eq          # one 0.01-lot grain, as a risk fraction
        assert q <= NS["Q_OPT"] + 1e-12, (
            f"{name} at ${stop} runs {q:.3%} ABOVE policy {NS['Q_OPT']:.3%}")
        assert q > NS["Q_OPT"] - step_q, (
            f"{name} at ${stop} runs {q:.3%}, more than one lot step ({step_q:.3%}) "
            f"below policy {NS['Q_OPT']:.3%}")


def test_the_old_constant_overshot_the_wide_sleeves_by_the_recorded_multiple():
    """Pinning the size of the defect, so a regression is recognisable rather
    than merely failing."""
    eq = 25_000.0
    house = NS["DIST_USD"]
    for name, stop in LIVE_STOPS.items():
        lot_house = NS["auto_lot"](eq, house)          # what it used to do
        realised = lot_house * stop * GOLD_PU / eq
        assert realised == pytest.approx(NS["Q_OPT"] * stop / house, rel=0.05), name
    # asia specifically: 2.8x its budget
    assert LIVE_STOPS["asia"] / house == pytest.approx(2.80, abs=0.02)


def test_the_three_leg_book_was_over_its_own_cap_under_the_old_sizing():
    """The book believed it was inside 3.81% and was not."""
    eq = 25_000.0
    house = NS["DIST_USD"]
    lot = NS["auto_lot"](eq, house)
    legs = ("asia", "london_am", "ny_open")
    heat = sum(lot * LIVE_STOPS[s] * GOLD_PU / eq for s in legs)
    assert heat > 0.0381, f"old sizing produced {heat:.2%}, cap 3.81%"


def test_stop_aware_sizing_brings_the_book_back_inside_the_cap():
    eq = 25_000.0
    legs = ("asia", "london_am", "ny_open")
    heat = sum(NS["realised_q"](eq, LIVE_STOPS[s]) for s in legs)
    assert heat <= 0.0381 + 1e-9, f"stop-aware sizing still at {heat:.2%}"


# --------------------------------------------------------------- the floor

def test_the_venue_floor_still_binds_and_is_reported_honestly():
    """At EUR 300 the 0.01 floor forces a risk far above policy. That must show
    up in realised_q rather than being hidden by the lot being 'valid'."""
    q = NS["realised_q"](300.0, LIVE_STOPS["asia"])
    assert q == pytest.approx(0.01 * 53.40 * GOLD_PU / 300.0,
                              rel=1e-6)
    assert q > 0.15, f"asia at EUR 300 is {q:.2%}, not a policy-compliant number"


def test_the_floor_risk_differs_per_sleeve_at_a_small_account():
    """The reason a single house constant could not describe this account: the
    same 0.01 lot is a different bet in every session."""
    qs = {k: NS["realised_q"](300.0, v) for k, v in LIVE_STOPS.items()}
    assert qs["asia"] > 2.5 * qs["ny_open"]


def test_lots_are_still_floored_never_rounded_up():
    for stop in LIVE_STOPS.values():
        for eq in (300.0, 1_684.0, 8_000.0, 25_000.0):
            lot = NS["auto_lot"](eq, stop)
            assert abs(lot / 0.01 - round(lot / 0.01)) < 1e-9
            raw = NS["Q_OPT"] * eq / (stop * GOLD_PU)
            assert lot <= max(raw, 0.01) + 1e-9


def test_a_missing_distance_falls_back_to_the_house_constant():
    """Backwards compatible for callers that genuinely have no bracket."""
    assert NS["auto_lot"](25_000.0) == NS["auto_lot"](25_000.0, NS["DIST_USD"])
    assert NS["auto_lot"](25_000.0, 0) == NS["auto_lot"](25_000.0, NS["DIST_USD"])


# ------------------------------------------------------------ promoted ramp

def test_the_promoted_ramp_is_stop_aware_too():
    """A promoted sleeve on a wide session runs the same overshoot, and the ramp
    would have made it look deliberate."""
    eq = 25_000.0
    assert NS["promoted_lot"](eq, 500, 53.40) < NS["promoted_lot"](eq, 500, 19.1)


def test_the_promoted_ramp_floors_rather_than_rounds():
    """Rounding up reintroduced the overshoot _lot_steps exists to prevent, on
    exactly the sleeves with the least forward evidence.

    The bound is computed at the promoted path's OWN risk basis -- clamp_risk_frac
    (3% base, sleeve-specific since 2026-08-25), not the gold book's Q_OPT -- because
    promoted_lot passes q_eff = clamp_risk_frac(risk_frac) * ramp into auto_lot. Bounding
    against Q_OPT tested a policy the gateway no longer runs."""
    from mt5desk.sizing import clamp_risk_frac
    for live_n in (0, 100, 500):
        for eq in (1_684.0, 8_000.0, 25_000.0):
            lot = NS["promoted_lot"](eq, live_n, 53.40)
            ramp = 0.25 if live_n < 50 else (0.5 if live_n < 200 else 1.0)
            q_eff = clamp_risk_frac(None) * ramp
            bound = NS["auto_lot"](eq, 53.40, NS["GOLD_SYMBOL"], None, q=q_eff)
            assert lot <= max(bound, 0.01) + 1e-9


# ------------------------------------------------------- the live path is wired

def test_the_gateway_sizes_from_the_spec_and_refuses_when_it_cannot():
    """The fix is only real if the trade loop passes the distance."""
    assert "dist = stop_distance(spec)" in _SRC
    # canon evolved the call to carry the symbol's own risk units (L1.67) and the clamped
    # per-sleeve risk fraction; the property under test -- the REAL distance reaches the
    # sizer, never the house constant -- is unchanged. The delegation now lives in the core.
    assert "auto_lot(equity, dist_usd, symbol, info, q=q_eff)" in _CORE_SRC
    assert "refusing to size from the house average" in _SRC


def test_no_call_site_sizes_from_the_house_constant_by_omission():
    """A bare auto_lot(equity) in the trade loop is the bug returning -- in either file."""
    bad = []
    for src in (_SRC, _CORE_SRC):
        for node in ast.walk(ast.parse(src)):
            if (isinstance(node, ast.Call) and getattr(node.func, "id", "") == "auto_lot"
                    and len(node.args) < 2):
                bad.append(node.lineno)
    assert not bad, f"auto_lot called without a stop distance at line(s) {bad}"
