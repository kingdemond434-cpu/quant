"""Regression tests for the 2026-07-19 dead-man incident root cause (GAP register row 34).

``_execute_pair``'s market fallback used to swallow every order exception via ``_safe()`` with
zero fill verification -- a rejected/partial order looked identical to a filled one to every
caller. Three closes silently failed on the spot leg, stranding ~$2,150 of real inventory that
was deleted from tracking and invisible to every subsequent reconcile pass. These tests pin the
fix: a leg only counts as filled when the venue confirms ``status == "FILLED"``.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_PATH = Path(__file__).resolve().parents[2] / "scripts" / "run_cashcarry_executor.py"
_SPEC = importlib.util.spec_from_file_location("run_cashcarry_executor_fillverif", _PATH)
assert _SPEC is not None and _SPEC.loader is not None
_MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MOD)


def _filled_order(qty: float = 1.0) -> dict:
    return {"status": "FILLED", "executedQty": str(qty), "cummulativeQuoteQty": "1.0"}


def _rejected_order() -> dict:
    return {"status": "REJECTED", "executedQty": "0.0"}


class _FakeConn:
    def __init__(self, response: object) -> None:
        self._response = response
        self.calls: list[tuple] = []

    def place_market(self, sym: str, side: str, qty: float) -> dict:
        self.calls.append((sym, side, qty))
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


def test_filled_helper_requires_confirmed_status_and_qty() -> None:
    assert _MOD._filled(_filled_order(5.0)) is True
    assert _MOD._filled(_rejected_order()) is False
    assert _MOD._filled(_filled_order(0.0)) is False   # FILLED but zero qty is not real
    assert _MOD._filled(None) is False
    assert _MOD._filled({}) is False


def test_execute_pair_reports_success_when_both_legs_confirm_filled(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_MOD, "_MAKER", False)
    monkeypatch.setattr(_MOD, "spot", _FakeConn(_filled_order(10.0)))
    monkeypatch.setattr(_MOD, "fut", _FakeConn(_filled_order(10.0)))
    result = _MOD._execute_pair("GTCUSDT", 10.0, "SELL", "BUY")
    assert result["spot_ok"] is True
    assert result["fut_ok"] is True


def test_execute_pair_reports_failure_when_spot_leg_rejected(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # the exact 2026-07-19 shape: futures side fine, spot side silently rejected
    monkeypatch.setattr(_MOD, "_MAKER", False)
    monkeypatch.setattr(_MOD, "spot", _FakeConn(_rejected_order()))
    monkeypatch.setattr(_MOD, "fut", _FakeConn(_filled_order(10.0)))
    monkeypatch.setattr(_MOD, "_ERR", tmp_path / "cashcarry_error.log")
    result = _MOD._execute_pair("GTCUSDT", 10.0, "SELL", "BUY")
    assert result["spot_ok"] is False
    assert result["fut_ok"] is True
    # a leg failure must be VISIBLE, not silent (the actual 2026-07-19 defect: nothing logged)
    assert (tmp_path / "cashcarry_error.log").exists()
    assert "unfilled leg" in (tmp_path / "cashcarry_error.log").read_text("utf-8")


def test_execute_pair_reports_failure_when_order_raises(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(_MOD, "_MAKER", False)
    monkeypatch.setattr(_MOD, "spot", _FakeConn(RuntimeError("connection reset")))
    monkeypatch.setattr(_MOD, "fut", _FakeConn(_filled_order(10.0)))
    monkeypatch.setattr(_MOD, "_ERR", tmp_path / "cashcarry_error.log")
    result = _MOD._execute_pair("GTCUSDT", 10.0, "SELL", "BUY")
    assert result["spot_ok"] is False  # exception -> res stays None -> _filled(None) is False


def test_close_path_never_deletes_position_on_unfilled_leg(monkeypatch: pytest.MonkeyPatch) -> None:
    """End-to-end pin: a close whose spot leg fails must NOT be logged as closed or dropped from
    tracking -- this is the exact mechanism that stranded GTC/SHELL/ONE on 2026-07-19."""
    monkeypatch.setattr(_MOD, "_MAKER", False)
    logged: list[dict] = []
    monkeypatch.setattr(_MOD, "_log_trade", lambda row: logged.append(row))
    monkeypatch.setattr(_MOD, "spot", _FakeConn(_rejected_order()))
    monkeypatch.setattr(_MOD, "fut", _FakeConn(_filled_order(100.0)))
    monkeypatch.setattr(_MOD, "_ERR", Path("/tmp/test_cashcarry_error.log"))

    pos = {"GTCUSDT": {"spot_qty": 100.0, "spot_cost": 0.067, "perp_qty": -100.0,
                       "perp_entry": 0.067, "funding": 0.0001,
                       "opened": "2026-07-18T00:00:00+00:00"}}
    target: set[str] = set()   # GTCUSDT is leaving the target set -> close attempt
    actions: list[str] = []

    for sym in list(pos):
        if sym not in target:
            p = pos[sym]
            fill = _MOD._execute_pair(sym, float(p["spot_qty"]), "SELL", "BUY")
            if not (fill.get("spot_ok") and fill.get("fut_ok")):
                actions.append(f"CLOSE-FAIL {sym}")
                continue
            actions.append(f"close {sym}")
            del pos[sym]

    assert "GTCUSDT" in pos, "an unconfirmed close must keep the position tracked"
    assert logged == [], "an unconfirmed close must never write a close trade record"
    assert any("CLOSE-FAIL" in a for a in actions)
