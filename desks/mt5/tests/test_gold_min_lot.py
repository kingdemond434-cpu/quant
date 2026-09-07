"""The gold book's 0.02 floor raises a small lot and NEVER lowers a larger one.

PRINCIPAL, 2026-09-07: "let them use 0.02 lots each" and, one message later, "dont reduce their
risk or size from before". Those are not two instructions -- the second one says what kind of
number the first one is. A gold leg that fixed-fractional sizing already puts at 0.05 must still
send 0.05; only the legs the venue floor was holding at 0.01 move.

The failure this guards against is the easy reading: `lot = 0.02` for every gold leg. On the
equity where `auto_lot` returns more than that, a plain assignment is a SIZE CUT delivered as a
size increase, on the one book that took the account from 500 to 743 -- and nothing downstream
would report it, because 0.02 is exactly what was asked for.
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


def test_the_floor_raises_the_venue_minimum_leg() -> None:
    """At an equity where policy sizing lands on the 0.01 venue floor, gold sends 0.02."""
    small = 100.0
    assert dc.auto_lot(small, None, dc.GOLD_SYMBOL) == pytest.approx(0.01), (
        "precondition: this equity is meant to be in the range where the venue floor binds")
    assert dc.gold_lot(small) == pytest.approx(0.02)


def test_the_floor_never_reduces_a_larger_policy_lot() -> None:
    """Wherever policy sizing exceeds the floor, the floor is inert. This is the whole rule."""
    checked_any = False
    for equity in (500.0, 743.0, 2_000.0, 8_000.0, 25_000.0, 100_000.0):
        policy = dc.auto_lot(equity, None, dc.GOLD_SYMBOL)
        floored = dc.gold_lot(equity)
        assert floored >= policy, (
            f"at equity {equity} the floor returned {floored}, BELOW the policy lot {policy} -- "
            f"that is a size cut wearing the principal's instruction")
        if policy > 0.02:
            checked_any = True
            assert floored == pytest.approx(policy), (
                f"at equity {equity} policy sizing asks for {policy}; the floor must be inert "
                f"there, not pin the leg to 0.02")
    assert checked_any, ("no tested equity produced a policy lot above the floor, so the "
                         "no-reduction property was never actually exercised")


def test_the_floor_is_monotone_in_equity_terms() -> None:
    """More equity never buys a smaller gold leg. A floor that inverts the curve is a bug."""
    lots = [dc.gold_lot(e) for e in (100.0, 500.0, 743.0, 2_000.0, 8_000.0, 25_000.0)]
    assert lots == sorted(lots), f"gold lot fell as equity rose: {lots}"


def test_an_override_file_can_raise_the_floor_but_never_lower_it(tmp_path, monkeypatch) -> None:
    """A stale or bad override must not silently halve the principal's instruction."""
    path = tmp_path / "GOLD_MIN_LOT.json"
    monkeypatch.setattr(dc, "GOLD_MIN_LOT_FILE", path)

    path.write_text(json.dumps({"lot": 0.05}), "utf-8")
    assert dc.gold_min_lot() == pytest.approx(0.05), "an override above the constant applies"

    path.write_text(json.dumps({"lot": 0.01}), "utf-8")
    assert dc.gold_min_lot() == pytest.approx(0.02), (
        "an override BELOW the constant must be ignored -- a floor a file can lower is not a floor")

    for junk in ("{", "null", '{"lot": "big"}', '{"lot": -3}', '{"lot": 0}'):
        path.write_text(junk, "utf-8")
        assert dc.gold_min_lot() == pytest.approx(0.02), f"unusable override {junk!r} must fall "\
                                                         f"back to the constant"

    path.unlink()
    assert dc.gold_min_lot() == pytest.approx(0.02), "absent override falls back to the constant"


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


def test_nothing_else_on_the_desk_inherits_gold_s_floor() -> None:
    """`auto_lot` sizes every instrument. The gold floor must not have been put inside it.

    Asserted two ways, because either alone is weak. The general sizer's own floor is still the
    0.01 VENUE minimum on an instrument small enough to sit on it -- so nothing was raised to
    0.02 wholesale -- and `auto_lot`'s source does not mention the gold floor at all, which is
    the property that survives a future change of the equity these numbers happen to land on.
    (Other instruments are not expected at 0.01 here: `_eur_per_price_unit` differs per symbol,
    so US500 sizes to 0.07 at this equity for reasons that have nothing to do with gold.)
    """
    assert dc.auto_lot(100.0, None, "EURUSD") == pytest.approx(0.01), (
        "EURUSD no longer sits on the 0.01 venue minimum at tiny equity -- gold's floor has "
        "leaked into the general sizer")
    import inspect
    body = inspect.getsource(dc.auto_lot)
    for token in ("GOLD_MIN_LOT", "gold_min_lot", "gold_lot"):
        assert token not in body, (
            f"auto_lot references {token}: the gold book's floor belongs in gold_lot, not in "
            f"the sizer every instrument on the desk shares")
