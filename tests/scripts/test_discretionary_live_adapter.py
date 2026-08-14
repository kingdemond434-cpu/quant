"""ICTSetup -> RuleSignal: the field mapping that was the only missing link.

WHAT WAS ALREADY THERE. The playbook is pre-registered as H1-H11
(docs/research/DISCRETIONARY_PLAYBOOK_PREREGISTRATION.md) and H3 is fully implemented in
libs/ict/strategy: `setups()` returns direction, entry_price, stop and target -- a complete trade
story. `discretionary_sleeve.RuleSignal` requires exactly those fields. The distance between a
detected setup and a placeable intent was a field mapping nobody had written.

WHY THE TEST IS ABOUT CARRYING NUMBERS THROUGH UNCHANGED. The pre-registration survives only while
this adapter TRANSLATES and never DECIDES. Rounding a stop, clamping a target or 'improving' an
entry here would move the playbook's terms after the data arrived -- which is precisely what
pre-registration exists to prevent, and it would happen silently.
"""

from __future__ import annotations

from dataclasses import dataclass

from scripts.run_discretionary_live import _FORCED, _to_signal

from libs.execution.discretionary_sleeve import SleeveState, size_and_check


@dataclass
class _Setup:
    """Mirrors libs.ict.strategy.ICTSetup's public shape."""

    direction: int
    sweep_i: int
    shift_i: int
    entry_i: int
    entry_price: float
    stop: float
    target: float


def _long() -> _Setup:
    return _Setup(1, 10, 12, 14, 100.0, 98.0, 106.0)


def _short() -> _Setup:
    return _Setup(-1, 10, 12, 14, 100.0, 102.0, 94.0)


def test_DIRECTION_MAPS_TO_SIDE_IN_BOTH_DIRECTIONS() -> None:
    assert _to_signal(_long(), "BTCUSDT", "H3").side == "BUY"
    assert _to_signal(_short(), "BTCUSDT", "H3").side == "SELL"


def test_EVERY_PRICE_IS_CARRIED_THROUGH_UNCHANGED() -> None:
    """No rounding, no clamping, no 'improvement'. A stop nudged here is a pre-registered term
    edited after the data arrived."""
    s = _short()
    sig = _to_signal(s, "ETHUSDT", "H3")
    assert sig.entry_price == s.entry_price
    assert sig.stop_price == s.stop
    assert sig.target_price == s.target
    assert sig.symbol == "ETHUSDT"


def test_THE_FORCED_PARTICIPANT_IS_NAMED() -> None:
    """The hunt's own admission criterion. A liquidity sweep IS the forced participant: stops
    beyond a swing must fill when touched and cannot wait."""
    sig = _to_signal(_long(), "BTCUSDT", "H3")
    assert sig.forced_participant == _FORCED
    assert "cannot wait" in sig.forced_participant


def test_A_SHORT_SETUP_SIZES_OFF_ITS_STOP_ABOVE_ENTRY() -> None:
    """The risk distance is an absolute value, so a stop ABOVE entry sizes identically to one the
    same distance below. Getting this wrong would size shorts wrongly and only shorts."""
    st = SleeveState(equity_usd=10_000.0)
    long_d = size_and_check(_to_signal(_long(), "BTCUSDT", "H3"), st)
    short_d = size_and_check(_to_signal(_short(), "BTCUSDT", "H3"), st)
    assert long_d.take and short_d.take
    assert abs(long_d.qty - short_d.qty) < 1e-9


def test_THE_WHOLE_CHAIN_PRODUCES_A_PLACEABLE_INTENT_AT_200() -> None:
    """The live question, answered concretely: a 2% stop on a $200 book is a $100 notional, which
    clears a $10 venue minimum. Discretionary is placeable at this size -- WITH A TIGHT STOP."""
    d = size_and_check(_to_signal(_long(), "BTCUSDT", "H3"),
                       SleeveState(equity_usd=200.0), min_notional_usd=10.0)
    assert d.take
    assert d.risk_usd == 2.0
    assert d.qty * 100.0 >= 10.0
