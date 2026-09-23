"""CARRY STATE -- the financing leg, and the wiring that must not be quietly removed.

Every test here fails if a specific piece of the build is reverted. The two unit tests that
matter most are the ones that encode a convention the desk has already got wrong once:
`swap_mode` 1 vs 5 (a DIMENSION, not a factor, on 55% of the universe) and the MT5-to-Python
weekday offset (both are small integers, so a raw hand-off is silent).
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_DESK = _ROOT / "desks" / "mt5"
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

from research import carry_state  # noqa: E402


# ---------------------------------------------------------------------------------------------
# THE ALWAYS-FATAL DEFECT. `swap_table_miner` used `field(default_factory=dict)` while importing
# only `dataclass`, so the module raised NameError at class-body evaluation and had NEVER been
# imported on this box -- not once, not partially. It has zero callers, so no test and no grep
# could see it; only an import can.
# ---------------------------------------------------------------------------------------------
def test_swap_table_miner_is_importable():
    mod = importlib.import_module("side_channels.swap_table_miner")
    assert hasattr(mod, "SwapSnapshot"), "swap_table_miner imported but lost its dataclass"


# ---------------------------------------------------------------------------------------------
# UNITS
# ---------------------------------------------------------------------------------------------
def test_points_mode_converts_through_tick_value():
    """Mode 1: money = swap_points * tick_value. Verified against EURUSD's real terms, whose
    result annualises to the EUR-minus-USD policy differential from an independent direction."""
    terms = {"swap_mode": 1, "tick_value": 0.858657, "tick_size": 0.00001}
    money, why = carry_state.money_per_lot_night(-6.45, terms, None)
    assert money == pytest.approx(-5.538, abs=1e-3)
    assert "POINTS" in why


def test_interest_mode_is_a_percent_and_is_never_read_as_currency():
    """Mode 5 is an ANNUAL PERCENT of notional. Reading it as currency-per-night -- the reading
    `perishability.py` documented until 2026-08-29 -- is a dimension error on 138 symbols."""
    terms = {"swap_mode": 5, "tick_value": 0.008587, "tick_size": 0.01}
    money, why = carry_state.money_per_lot_night(-7.31, terms, price=150.0)
    # pct/100 * price * (tick_value/tick_size) / 360
    assert money == pytest.approx(-7.31 / 100 * 150.0 * (0.008587 / 0.01) / 360.0, rel=1e-9)
    assert "INTEREST_CURRENT" in why
    # and the naive currency reading would be -7.31, three orders of magnitude away
    assert abs(money) < abs(-7.31) / 100


def test_interest_mode_without_a_price_refuses_rather_than_guessing():
    terms = {"swap_mode": 5, "tick_value": 0.008587, "tick_size": 0.01}
    money, why = carry_state.money_per_lot_night(-7.31, terms, price=None)
    assert money is None
    assert "price" in why


def test_unknown_mode_refuses_and_names_the_mode():
    money, why = carry_state.money_per_lot_night(1.0, {"swap_mode": 4, "tick_value": 1.0,
                                                       "tick_size": 0.1}, None)
    assert money is None and "4" in why


def test_missing_mode_is_never_silently_currency():
    money, why = carry_state.money_per_lot_night(1.0, {"tick_value": 1.0}, None)
    assert money is None and "swap_mode" in why


# ---------------------------------------------------------------------------------------------
# THE WEEKDAY OFF-BY-ONE. MT5 is SUNDAY=0..SATURDAY=6; Python's weekday() is MONDAY=0..SUNDAY=6.
# Both are small ints, so a raw hand-off reads Wednesday as Thursday and nothing raises.
# ---------------------------------------------------------------------------------------------
@pytest.mark.parametrize("mt5_day,py_day", [(0, 6), (1, 0), (3, 2), (5, 4), (6, 5)])
def test_triple_weekday_converts_the_mt5_enum(mt5_day, py_day):
    assert carry_state.triple_weekday_for(mt5_day) == py_day


def test_triple_weekday_refuses_an_out_of_enum_value():
    """None disables the weekend rule in `financing.rollover_nights`, which is the right refusal.
    An unrecognised broker value must not silently become Wednesday."""
    assert carry_state.triple_weekday_for(9) is None
    assert carry_state.triple_weekday_for(None) is None


def test_financing_wednesday_default_agrees_with_the_broker_enum():
    from mt5desk import financing
    assert carry_state.triple_weekday_for(3) == financing.TRIPLE_SWAP_WEEKDAY


# ---------------------------------------------------------------------------------------------
# THE COLLAPSED VERDICT. UNMEASURED (no rate) and UNCLASSIFIED (rate known, no spread basis to
# scale it against) are different facts. This module's own first run collapsed them and reported
# USDJPY -- on a LIVE forward clock, rate resolving cleanly -- as UNMEASURED.
# ---------------------------------------------------------------------------------------------
def test_unclassified_is_not_unmeasured():
    assert carry_state.classify(3.843, None)[0] == "UNCLASSIFIED"
    assert carry_state.classify(None, 10.0)[0] == "UNMEASURED"


def test_swap_per_lot_keys_on_the_value_not_the_label():
    """A known rate must be served even when the state label could not be computed."""
    state = {"symbols": {"USDJPY": {"long": {"side": "long", "state": "UNCLASSIFIED",
                                             "swap_money_per_lot_night": 3.843}}}}
    assert carry_state.swap_per_lot(state, "USDJPY", "long") == pytest.approx(-3.843)


def test_swap_per_lot_negates_into_the_cost_convention():
    """The artifact publishes CREDIT-positive (MT5's own sign); `financing.drag_r` wants a
    positive COST. A credit must come back negative, or a paid side is charged as a cost."""
    state = {"symbols": {"X": {"short": {"side": "short", "state": "CARRY-PAID",
                                         "swap_money_per_lot_night": 28.121}}}}
    assert carry_state.swap_per_lot(state, "X", "short") == pytest.approx(-28.121)


def test_swap_per_lot_refuses_an_unmeasured_side():
    state = {"symbols": {"X": {"long": {"side": "long", "state": "UNMEASURED",
                                        "swap_money_per_lot_night": None}}}}
    assert carry_state.swap_per_lot(state, "X", "long") is None
    assert carry_state.swap_per_lot(state, "MISSING", "long") is None


# ---------------------------------------------------------------------------------------------
# THE SOCKET. `financing.assess` was built with `swap_per_lot=None` as the desk's permanent state.
# This is the test that fails if the producer stops feeding it.
# ---------------------------------------------------------------------------------------------
def test_financing_reaches_measured_when_the_rate_is_supplied():
    from mt5desk import financing
    un = financing.assess("s", expectancy_r=0.0957, mean_nights=1.481, stop_value_per_lot=1834.0)
    assert un.state == "UNMEASURED" and un.drag_r is None
    me = financing.assess("s", expectancy_r=0.0957, mean_nights=1.481,
                          stop_value_per_lot=1834.0, swap_per_lot=57.582)
    assert me.state == "MEASURED"
    assert me.drag_r == pytest.approx(1.481 * 57.582 / 1834.0, rel=1e-9)
    assert me.expectancy_after_r < me.expectancy_r


def test_a_paid_side_is_a_credit_not_a_cost():
    from mt5desk import financing
    me = financing.assess("s", expectancy_r=0.0957, mean_nights=1.481,
                          stop_value_per_lot=1834.0, swap_per_lot=-28.121)
    assert me.drag_r < 0 and me.expectancy_after_r > me.expectancy_r


# ---------------------------------------------------------------------------------------------
# THE FENCE. Its whole job is to refuse to say OK about something it did not measure.
# ---------------------------------------------------------------------------------------------
def _fence():
    sys.path.insert(0, str(_ROOT / "scripts"))
    return importlib.import_module("check_carry_state")


def test_fence_passing_set_excludes_every_blind_status():
    f = _fence()
    for blind in ("UNMEASURED", "STALE", "STATE-MISSING", "NO-LIVE-SLEEVES",
                  "CARRY-UNCHARGED", "CARRY-FLIP"):
        assert blind not in f._PASSING, f"{blind} must never exit 0"
    assert "OK" in f._PASSING


def test_fence_reports_no_live_sleeves_rather_than_ok():
    """A verdict over an empty population is vacuous, never a pass (L1.57)."""
    f = _fence()
    out = f.scan({"symbols": {}}, {"sleeves": {}})
    assert out["live_sleeves"] == 0 and out["checked"] == 0


def test_fence_flags_an_uncharged_material_leg():
    f = _fence()
    state = {"symbols": {"XAUUSD": {
        "long": {"side": "long", "swap_money_per_lot_night": -57.582,
                 "carry_ratio_vs_spread": -4.62, "state": "CARRY-ADVERSE", "sign_flipped": False},
        "short": {"side": "short", "swap_money_per_lot_night": 28.121,
                  "carry_ratio_vs_spread": 2.25, "state": "CARRY-PAID", "sign_flipped": False},
        "triple_swap_weekday": 2}}}
    out = f.scan(state, {"sleeves": {"XAUUSD.asia": {"status": "LIVE"}}})
    assert len(out["uncharged"]) == 1
    row = out["uncharged"][0]
    assert row["worst_side"] == "long" and row["charged_by_engine"] == 0.0
    assert row["symbol_source"] == "name-prefix"


def test_fence_judges_the_worst_side_when_direction_is_unrecorded():
    """All 17 live sleeves record `direction: None`. Picking the convenient side would be the
    false-null direction; the fence must judge on the worst and publish both."""
    f = _fence()
    state = {"symbols": {"S": {
        "long": {"side": "long", "swap_money_per_lot_night": -50.0,
                 "carry_ratio_vs_spread": -5.0, "state": "CARRY-ADVERSE", "sign_flipped": False},
        "short": {"side": "short", "swap_money_per_lot_night": 10.0,
                  "carry_ratio_vs_spread": 1.0, "state": "CARRY-PAID", "sign_flipped": False}}}}
    out = f.scan(state, {"sleeves": {"S.x": {"status": "LIVE", "direction": None}}})
    assert out["uncharged"][0]["worst_side"] == "long"
    assert out["uncharged"][0]["best_side"] == "short"


def test_fence_reports_unresolved_rather_than_clean_for_an_unpriced_symbol():
    f = _fence()
    state = {"symbols": {"Z": {"long": {"side": "long", "swap_money_per_lot_night": None,
                                        "unit": "no swap_mode", "state": "UNMEASURED"},
                               "short": {"side": "short", "swap_money_per_lot_night": None,
                                         "unit": "no swap_mode", "state": "UNMEASURED"}}}}
    out = f.scan(state, {"sleeves": {"Z.x": {"status": "LIVE"}}})
    assert out["checked"] == 0 and len(out["unresolved"]) == 1


# ---------------------------------------------------------------------------------------------
# THE SCHEDULE. Built is not a status (III.16): a capability with no scheduled runner is unwired.
# ---------------------------------------------------------------------------------------------
def test_both_organs_are_scheduled_in_the_manifest():
    text = (_ROOT / "ops" / "crontab.manifest").read_text("utf-8")
    assert "desks/mt5/research/carry_state.py" in text, "producer is not scheduled"
    assert "scripts/check_carry_state.py" in text, "fence is not scheduled"


def test_artifact_shape_if_present():
    """If the producer has run here, its artifact must never report a measured side without a
    unit, and must never claim a state for an unpriced side."""
    p = _DESK / "data" / "carry_state.json"
    if not p.exists():
        pytest.skip("carry_state.json not built on this box")
    state = json.loads(p.read_text("utf-8"))
    assert state["n_symbols"] > 0
    for sym in state["symbols"].values():
        for side in ("long", "short"):
            leg = sym[side]
            if leg["swap_money_per_lot_night"] is None:
                assert leg["state"] == "UNMEASURED"
            else:
                assert leg["state"] != "UNMEASURED"
                assert leg["unit"]
