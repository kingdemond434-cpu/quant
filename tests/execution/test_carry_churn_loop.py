"""Regression tests for the 2026-07-28 carry churn-loop incident.

Every futures hedge had been force-closed out from under the book while ``CASHCARRY_KILL`` was
latched. That produced a loop with no exit:

  1. ``_reconcile`` saw each tracked carry's futures leg missing and RE-SHORTED it, then saw the
     spot leg missing (the previous tick's close had sold it) and RE-BOUGHT it -- rebuilding the
     exact position the kill order was tearing down, with market orders, every tick.
  2. The close then fired a ``reduceOnly`` cover against an already-flat futures position. The
     venue rejects that, ``_filled`` returns False, so ``fut_ok=False``.
  3. ``if not (spot_ok and fut_ok): continue`` kept the pair tracked for a retry -- forever.

Measured cost before the fix: 11,136 venue commission events against 251 logged round-trips,
$1,456 of fees in 48h against $113 of LIFETIME funding harvest, still burning ~$2.40 every 600s
tick at diagnosis time. Two independent defects, so two independent fixes -- either alone leaves
a live loop, so both are pinned here.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest

_PATH = Path(__file__).resolve().parents[2] / "scripts" / "run_cashcarry_executor.py"
_SPEC = importlib.util.spec_from_file_location("run_cashcarry_executor_churn", _PATH)
assert _SPEC is not None and _SPEC.loader is not None
_MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MOD)


def _rejected() -> dict:
    """What the venue returns for a reduceOnly cover against an already-flat position."""
    return {"status": "REJECTED", "executedQty": "0.0"}


class _FlatFut:
    """Futures venue holding nothing -- every hedge already force-closed."""

    def __init__(self) -> None:
        self.orders: list[tuple] = []

    def positions(self) -> dict[str, float]:
        return {}

    def place_market(self, sym: str, side: str, qty: float, reduce_only: bool = False) -> dict:
        self.orders.append((sym, side, qty))
        return _rejected()

    def mark_prices(self) -> dict[str, float]:
        return {}

    def book_ticker(self) -> dict[str, tuple[float, float]]:
        return {}

    def has_keys(self) -> bool:
        return True

    def set_leverage(self, sym: str, lev: int) -> None:
        return None

    def cancel_all(self, sym: str) -> None:
        return None

    def force_orders(self, hours: float) -> dict:
        return {}


class _EmptySpot:
    """Spot wallet already emptied by the close that did fill."""

    def __init__(self) -> None:
        self.orders: list[tuple] = []

    def balances(self) -> dict[str, float]:
        return {}

    def exchange_filters(self) -> dict[str, dict]:
        return {}

    def place_market(self, sym: str, side: str, qty: float) -> dict:
        self.orders.append((sym, side, qty))
        return {"status": "FILLED", "executedQty": str(qty)}

    def book_ticker(self) -> dict[str, tuple[float, float]]:
        return {}

    def cancel_all(self, sym: str) -> None:
        return None

    def has_keys(self) -> bool:
        return True


def _pos() -> dict[str, dict[str, Any]]:
    return {"MOVEUSDT": {"spot_qty": 47306.0, "spot_cost": 0.0097,
                         "perp_qty": -47306.0, "perp_entry": 0.00965,
                         "funding": 0.000207, "opened": "2026-07-27T07:21:14+00:00"}}


# ---- Fix 1: the reconciler must not rebuild a book that is being flattened ----------------

def test_reconcile_rebuilds_both_legs_when_not_flattening(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Normal operation is unchanged -- drift still heals. This is the control."""
    f, s = _FlatFut(), _EmptySpot()
    monkeypatch.setattr(_MOD, "fut", f)
    monkeypatch.setattr(_MOD, "spot", s)
    acts = _MOD._reconcile(_pos(), dry=False, flatten_only=False)
    assert any("re-hedge" in a for a in acts), acts
    assert any(o[1] == "SELL" for o in f.orders), "missing futures leg must be re-shorted"


def test_reconcile_adds_no_exposure_while_book_is_ordered_flat(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """THE FIX: under kill/risk-flatten, neither leg is rebuilt -- no orders, no fees."""
    f, s = _FlatFut(), _EmptySpot()
    monkeypatch.setattr(_MOD, "fut", f)
    monkeypatch.setattr(_MOD, "spot", s)
    acts = _MOD._reconcile(_pos(), dry=False, flatten_only=True)
    assert f.orders == [], f"re-shorted a book ordered flat: {f.orders}"
    assert s.orders == [], f"re-bought spot on a book ordered flat: {s.orders}"
    assert any("flatten-mode" in a for a in acts), acts


# ---- Fix 2: a close is done when the leg is FLAT, not when an order fills -----------------

def test_close_against_already_flat_futures_leg_counts_as_done(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """THE FIX: nothing left to cover IS the goal state, so the pair can finally retire."""
    monkeypatch.setattr(_MOD, "_MAKER", False)
    monkeypatch.setattr(_MOD, "fut", _FlatFut())
    monkeypatch.setattr(_MOD, "spot", _EmptySpot())
    res = _MOD._execute_pair("MOVEUSDT", 47306.0, "SELL", "BUY")
    assert res["fut_ok"] is True, "flat futures leg must not block the close forever"
    assert res["fut"] == "already-flat"


def test_close_still_fails_when_spot_inventory_remains(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """The 2026-07-19 stranded-inventory guard is preserved: real holdings still fail closed."""
    class _HeldSpot(_EmptySpot):
        def balances(self) -> dict[str, float]:
            return {"MOVE": 47306.0}                       # the sell did NOT go through

        def place_market(self, sym: str, side: str, qty: float) -> dict:
            self.orders.append((sym, side, qty))
            return _rejected()

    monkeypatch.setattr(_MOD, "_MAKER", False)
    monkeypatch.setattr(_MOD, "fut", _FlatFut())
    monkeypatch.setattr(_MOD, "spot", _HeldSpot())
    res = _MOD._execute_pair("MOVEUSDT", 47306.0, "SELL", "BUY")
    assert res["spot_ok"] is False, "unsold spot must stay tracked, never silently retired"


def test_open_path_is_untouched_by_the_goal_state_check(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Goal-state logic applies to CLOSES only; a failed OPEN must never read as success."""
    monkeypatch.setattr(_MOD, "_MAKER", False)
    monkeypatch.setattr(_MOD, "fut", _FlatFut())
    monkeypatch.setattr(_MOD, "spot", _EmptySpot())
    res = _MOD._execute_pair("MOVEUSDT", 47306.0, "BUY", "SELL")   # BUY spot = an open
    assert res["fut_ok"] is False, "a rejected open must stay a failure"
