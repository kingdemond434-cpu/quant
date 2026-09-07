"""The desk lot floor raises a leg the venue would not let us send, and NEVER lowers a larger one.

The floor is the venue's 0.01. It was briefly 0.02 on the principal's 2026-09-07 instruction and
reverted the same day on the arithmetic -- a lot floor makes a small account run a LARGER
fraction of equity than policy asked for, and doubling it doubled that overshoot on the legs
least able to carry it ("do 0.01 like before then"). These tests outlive the value: every one
reads `dc.min_lot()` rather than a literal, so they assert the PROPERTIES a floor must have at
whatever number it is set to.

The failure they guard against is the easy reading of any such instruction: `lot = <floor>` for
every leg. On the equity where `auto_lot` already returns more, a plain assignment is a SIZE CUT
delivered as a size increase, on the one book that took the account from 500 to 743 -- and
nothing downstream would report it, because the number is exactly what was asked for.
"""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

DESK = pathlib.Path(__file__).resolve().parents[1]
if str(DESK) not in sys.path:
    sys.path.insert(0, str(DESK))

from mt5desk import decision_core as dc  # noqa: E402


def test_a_minimum_lot_is_sent_at_any_capital() -> None:
    """PRINCIPAL 2026-09-07: "base minimum lots r allowed no matter capital".

    The sizer floors rather than refusing, and it does so at every equity down to absurd ones.
    That choice is deliberate and its cost is real: `auto_lot`'s own docstring says a book that
    cannot open a position also cannot compound out of the range where the floor binds. This
    test is what stops a future "refuse below X equity" rule from being added quietly.
    """
    for equity in (10.0, 50.0, 100.0, 300.0, 743.0):
        assert dc.gold_lot(equity) >= dc.min_lot(), f"gold sent nothing at equity {equity}"
        assert dc.promoted_lot(equity, 10, None, "EURUSD", None,
                               risk_frac=0.03) >= dc.min_lot(), (
            f"a promoted sleeve sent nothing at equity {equity}")


def test_the_floor_never_reduces_a_larger_policy_lot() -> None:
    """Wherever policy sizing exceeds the floor, the floor is inert. This is the whole rule."""
    checked_any = False
    for equity in (500.0, 743.0, 2_000.0, 8_000.0, 25_000.0, 100_000.0):
        policy = dc.auto_lot(equity, None, dc.GOLD_SYMBOL)
        floored = dc.gold_lot(equity)
        assert floored >= policy, (
            f"at equity {equity} the floor returned {floored}, BELOW the policy lot {policy} -- "
            f"that is a size cut wearing the principal's instruction")
        if policy > dc.min_lot():
            checked_any = True
            assert floored == pytest.approx(policy), (
                f"at equity {equity} policy sizing asks for {policy}; the floor must be inert "
                f"there, not pin the leg to {dc.min_lot()}")
    assert checked_any, ("no tested equity produced a policy lot above the floor, so the "
                         "no-reduction property was never actually exercised")


def test_the_floor_is_monotone_in_equity_terms() -> None:
    """More equity never buys a smaller gold leg. A floor that inverts the curve is a bug."""
    lots = [dc.gold_lot(e) for e in (100.0, 500.0, 743.0, 2_000.0, 8_000.0, 25_000.0)]
    assert lots == sorted(lots), f"gold lot fell as equity rose: {lots}"


def test_an_override_file_can_raise_the_floor_but_never_lower_it(tmp_path, monkeypatch) -> None:
    """A stale or bad override must not silently halve the principal's instruction."""
    path = tmp_path / "MIN_LOT.json"
    monkeypatch.setattr(dc, "MIN_LOT_FILE", path)

    path.write_text(json.dumps({"lot": 0.05}), "utf-8")
    assert dc.min_lot() == pytest.approx(0.05), "an override above the constant applies"

    path.write_text(json.dumps({"lot": 0.001}), "utf-8")
    assert dc.min_lot() == pytest.approx(dc.MIN_LOT), (
        "an override BELOW the constant must be ignored -- a floor a file can lower is not a floor")

    for junk in ("{", "null", '{"lot": "big"}', '{"lot": -3}', '{"lot": 0}'):
        path.write_text(junk, "utf-8")
        assert dc.min_lot() == pytest.approx(dc.MIN_LOT), (
            f"unusable override {junk!r} must fall back to the constant")

    path.unlink()
    assert dc.min_lot() == pytest.approx(dc.MIN_LOT), "absent override falls back to the constant"


def test_the_heat_ledger_bills_the_floored_lot_not_the_policy_lot() -> None:
    """The cap must reserve budget for the size actually sent.

    Source-level, because the branch lives in `gateway.main`'s pre-cap loop and standing that
    whole function up needs a terminal. What is asserted is the property that matters: the gold
    branch prices `gold_lot`, so the ledger and the order path call the same sizer. Without it
    the cap falls through to `cap_by_heat`'s own `realised_q(equity, None, XAUUSD)` -- the POLICY
    lot -- and a floored book runs at up to twice the risk the budget reserved for it.
    """
    src = (DESK / "mt5desk" / "gateway.py").read_text("utf-8")
    assert 'elif _s.get("lot") == "auto":' in src, (
        "the pre-cap loop has no branch for the gold book's lot mode")
    head = src.split('elif _s.get("lot") == "auto":', 1)[1][:1200]
    assert "gold_lot(equity)" in head, (
        "the gold heat charge must be priced from gold_lot -- the lot that will be sent")
    assert 'lot = gold_lot(equity, dist, sym) if s["lot"] == "auto"' in src, (
        "the placement path must size the gold book through gold_lot, or the ledger and the "
        "order disagree about the same leg")


def test_promoted_sleeves_get_the_floor_too() -> None:
    """Principal 2026-09-07: "each trade". The floor is desk-wide, not gold alone."""
    small = 100.0
    lot = dc.promoted_lot(small, 10, None, "EURUSD", None, risk_frac=0.03)
    assert lot >= dc.min_lot(), f"a promoted sleeve sized to {lot}, below the desk floor"


def test_a_leg_the_allocator_zeroed_is_still_zero() -> None:
    """THE ONE EXCEPTION, and it is not negotiable.

    `book_zeroed` puts a sleeve the solve gave NO heat into the book at exactly 0.0 so it places
    nothing while keeping any bracket it still has open. A floor applied after that would put
    capital on the single sleeve the optimiser explicitly refused -- the worst leg in the book,
    chosen by a rounding rule.
    """
    assert dc.promoted_lot(5_000.0, 300, 20.0, "EURUSD", None,
                           risk_frac=0.0, from_book=True) == 0.0


def test_the_floor_is_a_lot_floor_and_not_a_risk_base() -> None:
    """Principal 2026-09-07: "its base floor minimum of minimum but not risk floor base".

    The RISK base is `clamp_risk_frac`'s 3%, earned up through `authority_ramp`. This test fails
    if the lot floor was ever implemented by touching that ladder -- which would make every
    promoted sleeve START at a risk fraction rather than merely never send a tiny position.
    """
    assert dc.clamp_risk_frac(None) == pytest.approx(0.03), "the 3% risk base moved"
    assert dc.MIN_LOT != dc.clamp_risk_frac(None), "the lot floor and the risk base are not the "\
                                                   "same kind of number and must not be equal"
    # The ladder still scales risk: a sleeve with no forward evidence is sized BELOW one with
    # 300 live trades wherever policy sizing is what decides (i.e. above the floor).
    # Equity and stop chosen so BOTH sit well above the floor: the point is that the ramp still
    # decides the size there, which is only observable where the floor is not what decided it.
    young = dc.promoted_lot(1_000_000.0, 1, 0.05, "EURUSD", None, risk_frac=0.03)
    proven = dc.promoted_lot(1_000_000.0, 300, 0.05, "EURUSD", None, risk_frac=0.03)
    assert young > dc.min_lot() and proven > dc.min_lot(), (
        f"precondition: both legs must be above the floor ({young}, {proven})")
    assert young < proven, (
        f"authority ramp no longer separates a new sleeve ({young}) from a proven one "
        f"({proven}) -- the floor has been applied to the risk fraction, not the lot")
    import inspect
    for fn in (dc.ramped_fraction, dc.clamp_risk_frac, dc.authority_ramp):
        body = inspect.getsource(fn)
        assert "min_lot" not in body and "MIN_LOT" not in body, (
            f"{fn.__name__} references the lot floor: risk fractions and lot sizes are different "
            f"quantities and the floor belongs only to the second")


def test_nothing_else_on_the_desk_inherits_gold_s_floor() -> None:
    """`auto_lot` sizes every instrument. The gold floor must not have been put inside it.

    Asserted two ways, because either alone is weak. The general sizer's own floor is still the
    VENUE minimum on an instrument small enough to sit on it -- so nothing was raised to
    the floor wholesale -- and `auto_lot`'s source does not mention the floor at all, which is
    the property that survives a future change of the equity these numbers happen to land on.
    (Other instruments are not expected at 0.01 here: `_eur_per_price_unit` differs per symbol,
    so US500 sizes to 0.07 at this equity for reasons that have nothing to do with gold.)
    """
    assert dc.auto_lot(100.0, None, "EURUSD") == pytest.approx(0.01), (
        "EURUSD no longer sits on the 0.01 venue minimum at tiny equity -- gold's floor has "
        "leaked into the general sizer")
    import inspect
    body = inspect.getsource(dc.auto_lot)
    for token in ("MIN_LOT", "min_lot", "gold_lot"):
        assert token not in body, (
            f"auto_lot references {token}: the gold book's floor belongs in gold_lot, not in "
            f"the sizer every instrument on the desk shares")


# ------------------------------------------------- the GOLD-ONLY exception (principal 2026-09-07)
def test_gold_has_its_own_higher_floor_and_nothing_else_does() -> None:
    """Principal: "make gold 0.02 lots instead of 0.01 as exception per trade these live sleeves
    only". The word that carries the risk is EXCEPTION -- it must not leak to the other lanes.

    The same instruction was applied desk-wide earlier the same day and reverted within hours,
    because a floor on every promoted sleeve doubles the overshoot on the whole book rather than
    on the one part of it with forward evidence. This test is what keeps the second attempt
    scoped where the first one was not.
    """
    assert dc.gold_min_lot() > dc.min_lot(), "the gold exception is not above the desk floor"
    assert dc.gold_min_lot() == pytest.approx(0.02)
    assert dc.min_lot() == pytest.approx(0.01), "the DESK floor moved; only gold was to change"

    small = 300.0
    assert dc.gold_lot(small) == pytest.approx(dc.gold_min_lot())
    # Only meaningful where a FLOOR is what decides the lot. US500 sizes to 0.13 at this equity
    # from policy alone (`_eur_per_price_unit` differs per instrument), and asserting that is
    # below gold's floor tests the instrument's tick value, not the scoping.
    checked = False
    for symbol in ("EURUSD", "CADJPY", "US500"):
        policy = dc.auto_lot(small, None, symbol, None,
                             q=dc.ramped_fraction(0.03, 10, None))
        lot = dc.promoted_lot(small, 10, None, symbol, None, risk_frac=0.03)
        if policy <= dc.min_lot():
            checked = True
            assert lot == pytest.approx(dc.min_lot()), (
                f"{symbol} sits on a floor and got {lot}, not the desk floor {dc.min_lot()} -- "
                f"gold's exception has leaked into the promoted lanes")
    assert checked, "no tested symbol was floored, so the scoping was never exercised"


def test_the_gold_floor_still_never_cuts_a_larger_policy_lot() -> None:
    """A plain `lot = 0.02` would be a size CUT wherever policy already asks for more."""
    checked = False
    for equity in (8_000.0, 25_000.0, 100_000.0):
        policy = dc.auto_lot(equity, None, dc.GOLD_SYMBOL)
        if policy > dc.gold_min_lot():
            checked = True
            assert dc.gold_lot(equity) == pytest.approx(policy), (
                f"at equity {equity} policy asks {policy}; the floor must be inert there")
    assert checked, "no tested equity exercised the no-cut property"


def test_the_gold_override_file_can_only_raise(tmp_path, monkeypatch) -> None:
    path = tmp_path / "GOLD_MIN_LOT.json"
    monkeypatch.setattr(dc, "GOLD_MIN_LOT_FILE", path)
    path.write_text(json.dumps({"lot": 0.05}), "utf-8")
    assert dc.gold_min_lot() == pytest.approx(0.05)
    path.write_text(json.dumps({"lot": 0.01}), "utf-8")
    assert dc.gold_min_lot() == pytest.approx(dc.GOLD_MIN_LOT), (
        "a file below the constant must be ignored -- a floor a file can lower is not a floor")


def test_the_heat_ledger_bills_gold_at_its_own_floor() -> None:
    """The cap must reserve what the gold lane will actually send, not the desk floor.

    Source-level: the branch lives in `gateway.main`'s pre-cap loop. Without it the cap prices
    the POLICY lot, and the gold exception is exactly the case where the lot sent is larger --
    so the book would run at up to twice the risk the budget reserved for it.
    """
    src = (DESK / "mt5desk" / "gateway.py").read_text("utf-8")
    head = src.split('elif _s.get("lot") == "auto":', 1)[1][:1200]
    assert "gold_lot(equity)" in head, "the gold heat charge is not priced from gold_lot"
    assert 'lot = gold_lot(equity, dist, sym) if s["lot"] == "auto"' in src
    assert '_floor = gold_min_lot() if s.get("lot") == "auto" else min_lot()' in src, (
        "the floor-binding log line reports the wrong floor for the gold lane")
