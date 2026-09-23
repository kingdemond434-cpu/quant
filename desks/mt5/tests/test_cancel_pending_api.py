"""Pending-order cancellation must use the documented API and prove the order is gone.

Verified against the live terminal 2026-09-01: `hasattr(mt5, "order_delete")` is False. The
gateway called exactly that and logged "cancelled pending ticket <n>" on the next line, so
unfilled stops stood on a live account while the desk reported them cancelled -- and because
neither the function nor its caller caught the AttributeError, everything after the 20:30
housekeeping block (close_positions, record_trades, reconcile) was skipped too.

gateway.py imports MetaTrader5 and cannot be imported off Windows, so these read its source,
the same adaptation desks/mt5/tests/test_risk_units.py uses.
"""
from __future__ import annotations

import ast
from pathlib import Path

DESK = Path(__file__).resolve().parent.parent
_SRC = (DESK / "mt5desk" / "gateway.py").read_text("utf-8")


def _func_source(name: str) -> str:
    tree = ast.parse(_SRC)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.get_source_segment(_SRC, node) or ""
    raise AssertionError(f"{name}() not found in gateway.py")


def test_the_nonexistent_order_delete_is_never_called() -> None:
    """The CALL must be gone. Prose naming it is fine -- the docstring explains the incident.

    Parsed rather than grepped for exactly that reason: a string search cannot tell an
    explanation from an invocation, and the explanation is worth keeping.
    """
    tree = ast.parse(_SRC)
    calls = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
        and n.func.attr == "order_delete"
    ]
    assert not calls, (
        "mt5.order_delete does not exist in the MetaTrader5 package (verified against the live "
        "terminal: hasattr is False); every call raises AttributeError and leaves the pending "
        "order live while the next line logs it as cancelled")


def test_cancellation_uses_the_documented_removal_action() -> None:
    src = _func_source("cancel_pending")
    assert "TRADE_ACTION_REMOVE" in src, "removal must use order_send + TRADE_ACTION_REMOVE"
    assert "order_send" in src


def test_cancellation_verifies_the_ticket_is_actually_gone() -> None:
    """A retcode is a claim; orders_get is the fact. The venue is the state."""
    src = _func_source("cancel_pending")
    assert "retcode" in src, "the trade-server result must be read, not assumed"
    assert src.count("orders_get") >= 2, (
        "cancel_pending must re-read orders_get AFTER the remove to confirm absence; "
        "one read is only the list of what to cancel")


def test_one_bad_ticket_cannot_abort_the_pass() -> None:
    """The 20:30 block runs before close_positions/record_trades/reconcile in the same pass."""
    src = _func_source("cancel_pending")
    assert "except Exception" in src, (
        "an unhandled failure here skips close_positions, record_trades and reconcile, which "
        "is how last_reconcile stood still from 2026-08-17")
    assert "continue" in src, "a failed ticket must not stop the remaining tickets"
