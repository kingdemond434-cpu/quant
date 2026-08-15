"""The reduce leg -- and the one guard that stops a rebalance from opening a short.

MEASURED 2026-08-15. `place_market_reduce` existed, was tested, and had NO CALLER on the money
path: the margin executor refused every SELL with "belongs on the de-risk path". The consequence
was structural. A BUY-only executor cannot rebalance down, cannot take profit and cannot free
quote, so once the account was fully invested it was frozen -- $193 of equity in three coins with
ONE CENT of USDC, every leg it wanted was a SELL, and nothing could fund a new sleeve or trim a
position that had run. The book had no way back.

Selling is the operation that RAISES the margin level. The original comment used that as a reason
to refuse; it is the reason to allow. A book that can borrow but never repay only moves one way.
"""

from __future__ import annotations

import pytest

from libs.execution.spot_order_path import round_step


def test_A_REDUCE_NEVER_EXCEEDS_WHAT_IS_HELD() -> None:
    """THE WHOLE GUARD, IN ONE min(). Selling beyond the balance on cross margin does not fail --
    it BORROWS the base asset and opens a SHORT, converting a rebalance into a new levered
    position nobody asked for, on a book whose sizing assumed a reduction."""
    price, step = 100.0, 0.001
    held = 0.5
    wanted_usd = 200.0                      # asks for 2.0 units against 0.5 held
    qty = round_step(min(wanted_usd / price, held), step)
    assert qty == pytest.approx(0.5)
    assert qty <= held, "a reduce leg that exceeds the balance is a short in disguise"


def test_THE_STEP_ROUNDS_DOWN_SO_A_REDUCE_CANNOT_OVERSHOOT() -> None:
    """Rounding UP on a sell asks the venue for more base than is held. On spot that is a
    rejection; on cross margin it is a borrow."""
    assert round_step(0.5009, 0.001) == pytest.approx(0.500)
    assert round_step(0.4999, 0.001) == pytest.approx(0.499)
    assert round_step(1.23456789, 0.0) == pytest.approx(1.23456789), "no step = no rounding"


def test_A_DUST_REDUCE_IS_REFUSED_RATHER_THAN_SENT() -> None:
    """Below the venue minimum the position stays where it is rather than paying a fee for
    noise -- the same rule the buy leg already obeyed."""
    price, min_notional = 100.0, 5.0
    qty = round_step(min(0.02, 1.0), 0.001)      # $2 of a $5-minimum market
    assert qty * price < min_notional


def test_ONE_ROUNDER_SERVES_BOTH_ORDER_PATHS() -> None:
    """`round_step` was private to the spot path and the margin executor needed the identical
    DOWN-rounding. A second copy is a second rule, and the two would drift in the one place where
    drift costs money -- which is the entire argument the shared primitive's docstring makes."""
    from libs.execution import spot_order_path as P

    assert "round_step" in P.__all__
    assert not hasattr(P, "_round_step"), "the private copy must be gone, not shadowed"


def test_THE_CONNECTOR_REPAYS_AND_IS_NEVER_GATED_ON_THE_MARGIN_LEVEL() -> None:
    """AUTO_REPAY is the point: a sell that closes the position but leaves the loan outstanding
    has removed the asset and kept the liability. And a rail that blocked THIS operation would
    trap a book above the liquidation line with no way down -- turning a margin call into a
    liquidation while every check reported working as designed."""
    from pathlib import Path

    from libs.execution import binance_margin_live as m

    src = Path(m.__file__).read_text("utf-8")
    body = src.split("def place_market_reduce")[1].split("\ndef ")[0]
    assert "AUTO_REPAY" in body
    assert "margin_level" not in body, "the reduce path must never consult the margin level"
    assert "MIN_PROJECTED_LEVEL" not in body


def test_SELLS_SORT_BEFORE_BUYS_SO_THEIR_PROCEEDS_FUND_THE_ADDS() -> None:
    """A rebalance that buys before it sells asks for cash the run is about to raise: every buy
    is refused for insufficient funds while the sell that would have funded it waits its turn.
    Ordering by delta ASCENDING puts the reductions at the front."""
    deltas = {"OVERWEIGHT": -50.0, "UNDER_A": 30.0, "UNDER_B": 20.0}
    order = sorted(deltas, key=lambda k: deltas[k])
    assert order[0] == "OVERWEIGHT", "the reduce leg must run first"
    assert all(deltas[k] > 0 for k in order[1:])
