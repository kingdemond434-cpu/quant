"""A broker reporting stops_level 0 must still have its entry side checked.

MEASURED 2026-09-14 on the live intent ledger: every 10015 rejection this desk has taken was a
buy_stop placed BELOW the ask.

    buy_stop 4407.85 vs ask 4408.13   (0.28 below)
    buy_stop 4407.85 vs ask 4408.09   (0.24 below)
    buy_stop 4357.47 vs ask 4371.25  (13.78 below)

`entry_is_legal` exists precisely to stop that and its docstring says so. It was guarded by
`_lvl > 0`, and Fusion reports trade_stops_level 0 on every symbol, so it was never called on the
only venue the desk trades.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "desks" / "mt5"))

from mt5desk.decision_core import entry_is_legal  # noqa: E402


def _legal(**kw):
    return entry_is_legal(**kw)


def test_a_buy_stop_below_the_ask_is_illegal_even_with_no_distance_band() -> None:
    """The side requirement is unconditional; the band only sets a MINIMUM distance."""
    legal, why = _legal(price=4357.47, side="buy_stop", bid=4371.20, ask=4371.25,
                        point=0.01, stops_level=0)
    assert legal is False, "a buy_stop below the ask is not a stop order at all"
    assert why, "a refusal must say why -- a bare False is not a diagnosis"


def test_the_near_miss_that_actually_happened_is_caught() -> None:
    """0.28 below the ask: the ordinary case, where price drifts past the range as it completes."""
    legal, _ = _legal(price=4407.85, side="buy_stop", bid=4408.08, ask=4408.13,
                      point=0.01, stops_level=0)
    assert legal is False


def test_a_legal_buy_stop_above_the_ask_still_passes() -> None:
    """The fix must not refuse the orders the strategy exists to place."""
    legal, _ = _legal(price=4410.00, side="buy_stop", bid=4408.08, ask=4408.13,
                      point=0.01, stops_level=0)
    assert legal is True


def test_a_sell_stop_above_the_bid_is_illegal() -> None:
    """The mirror case. Not yet observed live, which is why it is worth pinning."""
    legal, _ = _legal(price=4420.00, side="sell_stop", bid=4408.08, ask=4408.13,
                      point=0.01, stops_level=0)
    assert legal is False


def test_the_gateway_does_not_gate_the_check_on_a_nonzero_stops_level() -> None:
    """The guard itself, read from source: `_lvl > 0` is what switched this off on Fusion."""
    src = (ROOT / "desks" / "mt5" / "mt5desk" / "gateway.py").read_text("utf-8")
    assert "if _t is not None and _lvl > 0:" not in src, (
        "entry legality must be checked whenever a tick exists -- a broker that reports "
        "stops_level 0 is saying it has no minimum DISTANCE, not that any price is legal")
