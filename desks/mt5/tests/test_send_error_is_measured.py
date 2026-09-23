"""`order_send` returning None is not a lost connection, and claiming so cost a real diagnosis.

Measured 2026-09-14 at 12:41:08 exactly, one second, one symbol, two near-identical market orders:

    [xau_m5_anti_breakout_overlap] retcode=None   "the terminal connection is gone."
    [xau_m5_anti_momentum_ny]      retcode=10009  BUY 0.01 XAUUSD @market -- ACCEPTED

The connection was demonstrably alive. Three of that sleeve's orders were dropped today and the
log named a cause nobody had checked, so it read as "promoted but never trades" while the real
reason went unrecorded. MetaTrader5 sets `last_error()` for exactly this: `order_send` returns
None when the request is refused at the API boundary, the same shape as `copy_rates_from_pos`
returning None with `(-2, 'Terminal: Invalid params')`.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

dc = pytest.importorskip("mt5desk.decision_core")


def test_a_captured_error_is_reported_instead_of_a_guess():
    out = dc.diagnose(None, "", (-10021, "No prices"))
    assert "last_error" in out
    assert "No prices" in out
    assert "connection is gone" not in out


def test_an_uncaptured_error_says_UNKNOWN_and_refuses_to_invent_one():
    """Absence is a verdict (L1.28a). It must not resolve to a confident cause."""
    out = dc.diagnose(None, "")
    assert "UNKNOWN" in out
    assert "connection is gone" not in out
    assert "not safe to read this as a dead terminal" in out


def test_an_accepted_retcode_still_reports_nothing():
    assert dc.diagnose(10009, "") == ""


def test_a_known_failure_retcode_is_unchanged():
    out = dc.diagnose(10015, "")
    assert "10015" in out and out != ""
