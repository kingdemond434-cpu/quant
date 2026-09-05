"""An unfilled bracket must not outlive the session whose range formed it.

CANCEL_HOUR cancels every sleeve's bracket at one clock time (20:30 UTC), so a `gold_asia`
bracket placed at its 07:00 signal hour rested for 13.5 hours. A breakout filling at 19:00 on a
range measured before 07:00 is not the strategy that was validated -- it is a different trade
wearing that sleeve's name and charged to its risk budget.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

from mt5desk import decision_core as _dc  # noqa: E402

_SRC = (_DESK / "mt5desk" / "gateway.py").read_text(encoding="utf-8")
_TREE = ast.parse(_SRC)
#: The session constants and `bracket_deadline` live in the decision core since the 2026-09-05
#: split; the sweep and the broker-expiry request stay in the gateway, which talks to the venue.
_CORE_TREE = ast.parse((_DESK / "mt5desk" / "decision_core.py").read_text(encoding="utf-8"))


def _fn(name: str) -> ast.FunctionDef:
    for node in _TREE.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} is not defined in gateway.py")


def _const(name: str) -> float:
    for node in _CORE_TREE.body:
        if isinstance(node, ast.Assign) and any(
                getattr(t, "id", "") == name for t in node.targets):
            return float(ast.literal_eval(node.value))
    raise AssertionError(f"{name} is not defined in decision_core.py")


def test_the_ttl_is_shorter_than_the_end_of_day_backstop() -> None:
    """If the TTL were the longer of the two it would never bind and CANCEL_HOUR would still be
    the real limit -- the defect this fixes."""
    assert _const("BRACKET_TTL_HOURS") < _const("CANCEL_HOUR")


def test_the_ttl_cannot_span_two_sessions() -> None:
    """The armed windows signal at 07:00, 13:00 and 17:00 UTC -- six hours apart at the widest.
    A bracket that outlives its own session is trading a regime nobody validated it in."""
    assert _const("BRACKET_TTL_HOURS") <= 6.0


def _deadline_fn():
    """`bracket_deadline` and the windows it derives from, imported from the decision core."""
    return {"bracket_deadline": _dc.bracket_deadline, "GOLD_WINDOWS": _dc.GOLD_WINDOWS,
            "CLOSE_HOUR": _dc.CLOSE_HOUR, "BRACKET_TTL_HOURS": _dc.BRACKET_TTL_HOURS}


def test_each_session_s_bracket_dies_when_that_session_does() -> None:
    """"asian for asian, london for london, ny for ny" -- the principal, 2026-09-02.

    A bracket belongs to the session whose range formed it, so the next window opening is what
    ends it, and the last of the day ends at the force-close. A flat TTL cannot express that:
    six hours is right for asia alone and would run london_am four hours into the afternoon.
    """
    from datetime import UTC, datetime  # noqa: PLC0415

    ns = _deadline_fn()
    bd, windows, close = ns["bracket_deadline"], ns["GOLD_WINDOWS"], float(ns["CLOSE_HOUR"])
    sig = {w[0]: float(w[1]) for w in windows}
    now = datetime.now(tz=UTC)
    here = now.hour + now.minute / 60.0
    ceiling = _const("BRACKET_TTL_HOURS")
    for name, hour in sig.items():
        later = [h for h in sig.values() if h > hour]
        want = min(later) if later else close
        got = bd(f"gold_{name}")
        assert got > now, f"gold_{name}: deadline is in the past"
        if want > here:
            # The session's end is still ahead today: the deadline IS that hour, exactly.
            assert got.hour + got.minute / 60.0 == want, (
                f"gold_{name} must expire at {want}, got {got:%H:%M}")
        else:
            # Its end has already passed (a late or replayed pass). The deadline must roll
            # forward without ever exceeding the ceiling -- asserted at any hour of the day, so
            # this test does not quietly pass by being run in the morning.
            ahead = (got - now).total_seconds() / 3600.0
            assert 0 < ahead <= ceiling + 0.01, (
                f"gold_{name} rolled to {got:%H:%M} ({ahead:.1f}h), past the {ceiling}h ceiling")


def test_an_unknown_window_is_bounded_by_the_ceiling_not_unbounded() -> None:
    """A promoted family sleeve whose window the desk does not recognise still gets a limit."""
    from datetime import UTC, datetime  # noqa: PLC0415

    ns = _deadline_fn()
    got = ns["bracket_deadline"]("promoted_something_new")
    hours = (got - datetime.now(tz=UTC)).total_seconds() / 3600.0
    assert 0 < hours <= _const("BRACKET_TTL_HOURS") + 0.01


def test_the_sweep_uses_the_same_session_rule_as_the_broker_expiry() -> None:
    """Two rules would disagree: a flat sweep cutoff would keep an afternoon bracket alive past
    the force-close the broker expiry had already set it to die at."""
    src = ast.get_source_segment(_SRC, _fn("expire_stale_brackets")) or ""
    assert "bracket_deadline" in src


def test_expiry_is_requested_from_the_broker() -> None:
    """Broker-side expiry survives this process dying; a gateway-side sweep alone does not, and
    an OOM kill would leave a stale bracket resting with nothing managing it."""
    src = ast.get_source_segment(_SRC, _fn("_expiry_request")) or ""
    assert "ORDER_TIME_SPECIFIED" in src
    assert "expiration" in src
    assert "SYMBOL_EXPIRATION_SPECIFIED" in src, (
        "the symbol must be asked whether it accepts a timed order; sending one blindly to a "
        "symbol that refuses them rejects the whole bracket")
    assert "ORDER_TIME_GTC" in src, "there must be a fallback when timed orders are refused"


def test_the_sweep_only_touches_this_desk_s_orders() -> None:
    src = ast.get_source_segment(_SRC, _fn("expire_stale_brackets")) or ""
    assert "magic" in src and "MAGIC" in src, (
        "a sweep that is not keyed on MAGIC can cancel another system's orders")


def test_the_sweep_verifies_the_cancel_instead_of_trusting_the_retcode() -> None:
    """A retcode says the request was accepted, never that the order is gone -- the same lesson
    cancel_pending already learned."""
    src = ast.get_source_segment(_SRC, _fn("expire_stale_brackets")) or ""
    assert "orders_get" in src and "SURVIVED" in src


def test_the_sweep_runs_every_pass_not_only_at_cancel_hour() -> None:
    """Gating it behind CANCEL_HOUR would reproduce the original defect exactly."""
    body = ast.get_source_segment(_SRC, _fn("main")) or _SRC
    idx_sweep = body.index("expire_stale_brackets(st)")
    idx_gate = body.index("if hour >= CANCEL_HOUR")
    assert idx_sweep < idx_gate, "the TTL sweep must not sit inside the end-of-day branch"
