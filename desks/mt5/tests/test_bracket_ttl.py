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

_SRC = (_DESK / "mt5desk" / "gateway.py").read_text(encoding="utf-8")
_TREE = ast.parse(_SRC)


def _fn(name: str) -> ast.FunctionDef:
    for node in _TREE.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} is not defined in gateway.py")


def _const(name: str) -> float:
    for node in _TREE.body:
        if isinstance(node, ast.Assign) and any(
                getattr(t, "id", "") == name for t in node.targets):
            return float(ast.literal_eval(node.value))
    raise AssertionError(f"{name} is not defined in gateway.py")


def test_the_ttl_is_shorter_than_the_end_of_day_backstop() -> None:
    """If the TTL were the longer of the two it would never bind and CANCEL_HOUR would still be
    the real limit -- the defect this fixes."""
    assert _const("BRACKET_TTL_HOURS") < _const("CANCEL_HOUR")


def test_the_ttl_cannot_span_two_sessions() -> None:
    """The armed windows signal at 07:00, 13:00 and 17:00 UTC -- six hours apart at the widest.
    A bracket that outlives its own session is trading a regime nobody validated it in."""
    assert _const("BRACKET_TTL_HOURS") <= 6.0


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
