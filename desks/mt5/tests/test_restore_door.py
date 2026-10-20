"""A restore is a promotion: reconcile_capital asks the promotion doors before STANDBY -> LIVE.

The Judge (2026-10-20) found `reconcile_capital` lifting a STANDBY row to LIVE on an admitting
allocator reading alone, so a row the cost re-grade, the blind reviewer, the Tier S door or a
principal stop would refuse at promotion came back through the side door -- the failure class of
the 2026-10-13 gap-decay re-promotion. `restore_door_refusal` asks the same predicates.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

import promoter  # noqa: E402

_CERT = "external.EURZAR.overnight_gap_decay.p=ab12"


@pytest.fixture()
def doors_open(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every door passes; each test closes the one it is about."""
    monkeypatch.setattr(promoter, "capital_verdict", lambda *a, **k: {
        "status": "LIVE", "risk_frac": 0.03, "streak": 2, "why": "funded at 5.50% heat"})
    monkeypatch.setattr(promoter, "note_door", lambda *a, **k: None)
    monkeypatch.setattr(promoter, "plog", lambda *a, **k: None)
    monkeypatch.setattr(promoter, "replication_check", lambda: (lambda _row: ""))
    monkeypatch.setattr(promoter, "regrade_failures", lambda *a, **k: {})
    monkeypatch.setattr(promoter, "blind_review_veto", lambda *a, **k: None)
    monkeypatch.setattr(promoter, "tier_s_block", lambda *a, **k: None)
    monkeypatch.setattr(promoter, "live_certificate", lambda row: str(row.get("certificate") or ""))
    _stops(monkeypatch, [])


def _stops(monkeypatch: pytest.MonkeyPatch, stops: list[dict], *, raises: bool = False) -> None:
    mod = types.ModuleType("mt5desk.principal_stops")

    def load(_path: Path) -> tuple[list[dict], str | None]:
        if raises:
            raise OSError("disk gone")
        return stops, None

    def match(row: dict, active: list[dict]) -> dict | None:
        return next((e for e in active if e.get("name") == row.get("name")), None)

    mod.load = load  # type: ignore[attr-defined]
    mod.match = match  # type: ignore[attr-defined]
    mod.why = lambda e: f"principal stop on {e.get('name')}"  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "mt5desk.principal_stops", mod)


def _restore(row: dict) -> dict:
    sleeves = [dict(row)]
    promoter.reconcile_capital(sleeves, {"fresh": True, "at": "2026-10-20T00:00:00+00:00",
                                         "admission_at": "2026-10-20T01:00:00+00:00"})
    return sleeves[0]


_ROW = {"name": "eurzar_gap", "status": "STANDBY", "risk_frac": 0.0, "certificate": _CERT,
        "demote_reason": "the optimiser gives it 0.0000% heat"}


@pytest.mark.usefixtures("doors_open")
def test_every_door_open_restores_and_clears_an_old_refusal() -> None:
    row = _restore({**_ROW, "restore_refusal": "BLOCKED_TIER_S: stale"})
    assert (row["status"], row["risk_frac"]) == ("LIVE", 0.03)
    assert "restore_refusal" not in row


@pytest.mark.usefixtures("doors_open")
def test_a_cost_regrade_failure_on_the_certificate_holds_the_row(monkeypatch) -> None:
    monkeypatch.setattr(promoter, "regrade_failures", lambda *a, **k: {
        _CERT: {"gates_failing_now": ["G3_net_sharpe"]}})
    row = _restore(_ROW)
    assert (row["status"], row["risk_frac"]) == ("STANDBY", 0.0)
    assert row["restore_refusal"].startswith("BLOCKED_COST_REGRADE")
    assert "G3_net_sharpe" in row["restore_refusal"]
    assert row["admission"]["status"] == "LIVE"          # the reading is still recorded


@pytest.mark.usefixtures("doors_open")
def test_a_blind_review_veto_holds_the_row(monkeypatch) -> None:
    monkeypatch.setattr(promoter, "blind_review_veto",
                        lambda name, *a, **k: name if name == _CERT else None)
    row = _restore(_ROW)
    assert row["status"] == "STANDBY" and row["restore_refusal"].startswith("BLOCKED_BLIND_REVIEW")


@pytest.mark.usefixtures("doors_open")
def test_a_tier_s_refusal_holds_the_row_under_its_canon_name(monkeypatch) -> None:
    monkeypatch.setattr(promoter, "live_certificate", lambda row: "canon:EURZAR#1")
    monkeypatch.setattr(promoter, "tier_s_block",
                        lambda name: "MISMATCH" if name == "canon:EURZAR#1" else None)
    row = _restore(_ROW)
    assert row["status"] == "STANDBY" and row["restore_refusal"] == "BLOCKED_TIER_S: MISMATCH"


@pytest.mark.usefixtures("doors_open")
def test_a_principal_stop_holds_the_row(monkeypatch) -> None:
    _stops(monkeypatch, [{"name": "eurzar_gap"}])
    row = _restore(_ROW)
    assert row["status"] == "STANDBY"
    assert row["restore_refusal"] == "PRINCIPAL_STOP: principal stop on eurzar_gap"


@pytest.mark.usefixtures("doors_open")
def test_an_unreadable_stop_record_refuses(monkeypatch) -> None:
    _stops(monkeypatch, [], raises=True)
    row = _restore(_ROW)
    assert row["status"] == "STANDBY"
    assert row["restore_refusal"].startswith("PRINCIPAL_STOP_UNMEASURED")


@pytest.mark.usefixtures("doors_open")
def test_the_refusal_lifts_the_pass_the_door_opens(monkeypatch) -> None:
    monkeypatch.setattr(promoter, "tier_s_block", lambda name: "OVER_BUDGET")
    held = _restore(_ROW)
    assert held["status"] == "STANDBY"
    monkeypatch.setattr(promoter, "tier_s_block", lambda name: None)
    row = _restore({**held, "admit_scan": "older"})
    assert row["status"] == "LIVE" and "restore_refusal" not in row


@pytest.mark.usefixtures("doors_open")
def test_demotion_never_asks_the_door(monkeypatch) -> None:
    monkeypatch.setattr(promoter, "capital_verdict", lambda *a, **k: {
        "status": "STANDBY", "risk_frac": 0.0, "streak": 0, "why": "no heat"})
    monkeypatch.setattr(promoter, "tier_s_block",
                        lambda name: (_ for _ in ()).throw(AssertionError("asked")))
    row = _restore({**_ROW, "status": "LIVE", "risk_frac": 0.03})
    assert (row["status"], row["risk_frac"]) == ("STANDBY", 0.0)
