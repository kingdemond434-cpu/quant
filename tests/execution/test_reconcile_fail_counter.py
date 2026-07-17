"""Tests for the reconciler's consecutive-failure counter (2026-07-17 gap-register #16 fix).

Before this fix, a rejected re-hedge order from ``_mkt_or_limit`` returned ``''`` and NOTHING was
logged -- the exact silent-failure class that let COOKIEUSDT's broken pair sit unhedged for 75
minutes on 2026-07-16 (the reconciler retried every cycle and failed every cycle, invisibly).
These tests pin the fixed semantics: failures accumulate per symbol across cycles, and only the
3rd consecutive failure surfaces a RECONCILE-FAIL action line + a visible error-log write. A
lone or intermittent failure (transient venue hiccup) must NOT alarm-fatigue the journal.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

_PATH = Path(__file__).resolve().parents[2] / "scripts" / "run_cashcarry_executor.py"
_SPEC = importlib.util.spec_from_file_location("run_cashcarry_executor_rc", _PATH)
assert _SPEC is not None and _SPEC.loader is not None
_MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MOD)


class _FakeFut:
    """Minimal futures-connector stand-in: reports one under-hedged tracked position."""

    def has_keys(self) -> bool:
        return True

    def positions(self) -> dict[str, float]:
        return {}                                    # no futures leg exists -> fully missing

    def force_orders(self, _hours: float) -> dict[str, int]:
        return {}                                    # not ADL -> takes the normal re-hedge path

    def set_leverage(self, _sym: str, _lev: int) -> None:
        pass


class _FakeSpot:
    """Spot leg already fully hedged -- keeps the test isolated to the futures re-hedge path."""

    def balances(self) -> dict[str, float]:
        return {"ABC": 100.0}

    def exchange_filters(self) -> dict[str, dict]:
        return {}


def _pos() -> dict[str, dict]:
    return {"ABCUSDT": {"perp_qty": -100.0, "spot_qty": 100.0}}


class _FakeErrLog:
    def __init__(self) -> None:
        self.writes: list[str] = []

    def write_text(self, s: str) -> None:
        self.writes.append(s)


def test_reconcile_fail_counter_silent_until_third_strike(monkeypatch: Any) -> None:
    monkeypatch.setattr(_MOD, "fut", _FakeFut())
    monkeypatch.setattr(_MOD, "spot", _FakeSpot())
    monkeypatch.setattr(_MOD, "_mkt_or_limit", lambda *a, **k: "")   # every attempt rejected
    fake_err = _FakeErrLog()
    monkeypatch.setattr(_MOD, "_ERR", fake_err)
    writes = fake_err.writes

    fails: dict[str, int] = {}
    for _ in range(2):
        acts = _MOD._reconcile(_pos(), dry=False, fail_counts=fails)
        assert not any("RECONCILE-FAIL" in a for a in acts)   # 1st and 2nd failure stay quiet
    assert writes == []
    assert fails["ABCUSDT"] == 2

    acts = _MOD._reconcile(_pos(), dry=False, fail_counts=fails)
    assert any("RECONCILE-FAIL" in a and "ABCUSDT" in a for a in acts)   # 3rd strike surfaces
    assert len(writes) == 1
    assert "ABCUSDT" in writes[0]
    assert fails["ABCUSDT"] == 3


def test_reconcile_fail_counter_resets_on_success(monkeypatch: Any) -> None:
    monkeypatch.setattr(_MOD, "fut", _FakeFut())
    monkeypatch.setattr(_MOD, "spot", _FakeSpot())
    calls = {"n": 0}

    def _flaky(*_a: Any, **_k: Any) -> str:
        calls["n"] += 1
        return "" if calls["n"] < 3 else "mkt"        # fails twice, then succeeds

    monkeypatch.setattr(_MOD, "_mkt_or_limit", _flaky)
    monkeypatch.setattr(_MOD, "_ERR", _FakeErrLog())

    fails: dict[str, int] = {}
    _MOD._reconcile(_pos(), dry=False, fail_counts=fails)
    _MOD._reconcile(_pos(), dry=False, fail_counts=fails)
    assert fails["ABCUSDT"] == 2
    _MOD._reconcile(_pos(), dry=False, fail_counts=fails)   # this one succeeds
    assert "ABCUSDT" not in fails                            # success clears the streak
