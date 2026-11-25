"""gold_oco: a lane resting both sides (a bracket, no position) does not block the same bracket
on another lane in "oco" mode before the day's first fill (zuck 2026-11-20: same orders)."""
from __future__ import annotations

from mt5desk import gold_oco as oco


def test_is_bracket() -> None:
    assert oco.is_bracket({"positions": [], "orders": [{"side": "buy"}, {"side": "sell"}]})
    assert not oco.is_bracket({"positions": [], "orders": [{"side": "buy"}]})
    assert not oco.is_bracket({"positions": [{"side": "long"}],
                               "orders": [{"side": "buy"}, {"side": "sell"}]})
