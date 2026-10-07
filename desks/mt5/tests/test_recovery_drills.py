"""The recovery-drill scorecard grades the desk's own drill artifacts: absent or stale is
UNMEASURED (never PASS), a gateway breach is FAIL naming the fix, CI-only is said so, and every
failure mode the principal named has a row."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for p in (str(_DESK), str(_DESK.parent.parent)):
    if p not in sys.path:
        sys.path.insert(0, p)

from research import recovery_drills as rd  # noqa: E402

NOW = datetime(2026, 10, 6, 12, tzinfo=UTC)


def _put(p: Path, doc: dict, at: datetime = NOW) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"generated_utc": at.isoformat(), **doc}))
    return p


def _fault(name: str, breaches: list[str] | None = None) -> dict:
    return {"fault": name, "status": "MEASURED", "breaches": breaches or []}


@pytest.fixture
def chaos(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    p = tmp_path / "CHAOS.json"
    monkeypatch.setattr(rd, "CHAOS", p)
    return p


def test_absent_and_stale_are_unmeasured_never_pass(chaos: Path) -> None:
    assert rd._gateway(("healthy",), NOW)["verdict"] == rd.UNMEASURED
    _put(chaos, {"gateway_drill": {"faults": [_fault("healthy")]}}, NOW - timedelta(hours=5))
    row = rd._gateway(("healthy",), NOW)
    assert row["verdict"] == rd.UNMEASURED and "older" in row["why"]


def test_gateway_breach_fails_and_names_the_desktop_fix(chaos: Path) -> None:
    _put(chaos, {"gateway_drill": {"faults": [
        _fault("orders_get_raises"),
        _fault("reconcile_unreadable", ["RECONCILE_BEFORE_EXPOSURE: no gate"])]}})
    row = rd._gateway(("orders_get_raises", "reconcile_unreadable"), NOW)
    assert row["verdict"] == rd.FAIL and row["fix"] == rd.GATEWAY_SPEC
    # a fault the run did not measure (an old box tree) is not silently a pass
    assert rd._gateway(("terminal_down", "terminal_disconnected"), NOW)["verdict"] == \
        rd.UNMEASURED


def test_clean_gateway_faults_pass(chaos: Path) -> None:
    _put(chaos, {"gateway_drill": {"faults": [_fault("reject_10015"),
                                              _fault("requote_10004")]}})
    assert rd._gateway(("reject_10015", "requote_10004"), NOW)["verdict"] == rd.PASS


def test_the_real_drill_campaign_grades_through_the_scorecard(chaos: Path) -> None:
    from libs.tiers import gateway_drill as gd
    camp = gd.campaign(("healthy", "reconcile_unreadable"))
    if camp["status"] != "MEASURED":
        pytest.skip(f"gateway does not import here: {camp}")
    _put(chaos, {"gateway_drill": camp})
    row = rd._gateway(("reconcile_unreadable",), NOW)
    assert row["verdict"] in (rd.PASS, rd.FAIL)        # measured either way, never UNMEASURED
    assert (row["verdict"] == rd.FAIL) == bool(camp["breaches"])


def test_backup_needs_a_restore_drill(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = tmp_path / "OFFSITE_BACKUP.json"
    monkeypatch.setattr(rd, "OFFSITE", p)
    base = {"at": NOW.isoformat(), "status": "OK", "last_success_at": NOW.isoformat(),
            "last_check_at": NOW.isoformat(), "last_check_ok": True,
            "key_escrowed_off_box": True}
    _put(p, base)
    assert rd._backup(NOW)["verdict"] == rd.FAIL
    _put(p, {**base, "restore_drill": {"at": NOW.isoformat(), "verdict": "PASS", "why": "3/3"}})
    assert rd._backup(NOW)["verdict"] == rd.PASS
    _put(p, {"at": NOW.isoformat(), "status": "NOT_ARMED", "why": "no config"})
    row = rd._backup(NOW)
    assert row["verdict"] == rd.UNMEASURED and row["needs_principal"]


def test_every_named_failure_mode_has_a_row_and_build_is_total() -> None:
    named = {"stale_data", "revision_leakage", "malformed_forecast", "no_quote", "worker_crash",
             "queue_overload", "disk_pressure", "network_loss", "broker_rejection",
             "missing_ack", "partial_fill", "duplicate_delivery", "out_of_order",
             "failed_deployment", "backup_restore", "restore_reconcile", "account_ledger",
             "clock_sync", "secrets", "reproducibility"}
    ids = {d[0] for d in rd.DRILLS}
    assert named <= ids
    doc = rd.build(NOW)
    assert doc["n"] == len(rd.DRILLS) and sum(doc["counts"].values()) == doc["n"]
    assert all(r["verdict"] in (rd.PASS, rd.FAIL, rd.UNMEASURED, rd.CI_ONLY)
               for r in doc["drills"])
    assert doc["verdict"] != rd.PASS or doc["counts"][rd.PASS] == doc["n"]


def test_every_fix_pointer_names_a_file_in_this_tree() -> None:
    root = Path(__file__).resolve().parents[3]
    for spec in (rd.GATEWAY_SPEC, rd.FILL_ORDER_SPEC):
        assert (root / spec).is_file(), spec
    gaps = [r for r in rd.build(NOW)["drills"] if r.get("evidence") == "code"]
    assert gaps and all(r["fix"] == rd.FILL_ORDER_SPEC for r in gaps)
