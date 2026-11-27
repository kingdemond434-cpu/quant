"""MONEYPATH_CRASH: a failing or stale money-path organ is named with its root cause.

Principal 2026-11-24 18:14Z, after the allocator crashed 440 times (11-21..11-24) with nothing
saying so, the gateway reading froze on 10-30 under the Fusion deadman, and the daily research
chain stamped each day and then ran 1 of 39 steps.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK / "research"), str(_DESK), str(_DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import desk_self_heal as heal  # noqa: E402
import run_desk_self_heal as rheal  # noqa: E402

NOW = datetime(2026, 11, 24, 18, 0, tzinfo=UTC)


def _w(root: Path, rel: str, doc, age_h: float | None = None) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(doc if isinstance(doc, str) else json.dumps(doc), "utf-8")
    if age_h is not None:
        t = NOW.timestamp() - age_h * 3600
        os.utime(p, (t, t))
    return p


def test_a_failed_allocator_pass_is_named_with_its_exception(tmp_path: Path) -> None:
    _w(tmp_path, "desks/mt5/reports/pf_allocation.json",
       {"generated_utc": (NOW - timedelta(days=3)).isoformat()})
    _w(tmp_path, "desks/mt5/reports/ALLOCATOR_STANDDOWN.json",
       {"status": "STOOD_DOWN", "reason": "FAILED", "at": "2026-11-24T17:49:15Z",
        "why": "AttributeError: 'str' object has no attribute 'get'"})
    f = heal.check_allocator_crash(tmp_path, NOW)
    assert not f.ok and not f.fixable
    assert "MONEYPATH_CRASH" in f.detail and "'str' object has no attribute 'get'" in f.detail
    assert "72.0h" in f.detail


def test_a_fresh_book_with_no_failure_is_healthy(tmp_path: Path) -> None:
    _w(tmp_path, "desks/mt5/reports/pf_allocation.json",
       {"generated_utc": (NOW - timedelta(minutes=40)).isoformat()})
    _w(tmp_path, "desks/mt5/reports/ALLOCATOR_STANDDOWN.json", {"status": "CLEARED"})
    assert heal.check_allocator_crash(tmp_path, NOW).ok


def test_a_frozen_gateway_reading_is_named(tmp_path: Path) -> None:
    _w(tmp_path, "desks/mt5/data/gateway_state.json",
       {"equity": 266.01, "last_reconcile": "2026-10-30T19:50:13Z"}, age_h=25 * 24)
    f = heal.check_gateway_publication(tmp_path, NOW)
    assert not f.ok and "frozen number" in f.detail and "266.01" in f.detail
    _w(tmp_path, "desks/mt5/data/gateway_state.json", {"equity": 1.0}, age_h=0.2)
    assert heal.check_gateway_publication(tmp_path, NOW).ok


STEPS = heal._step_names()


def _chain(tmp_path: Path, steps: dict, *, stamp_quiet_h: float | None = None,
           owner_quiet_h: float | None = None) -> None:
    """The box's real shapes: the stamp, and the lock's owner sidecar whose `last_progress` is
    a bare iso string (research/daily_cycle.py ChainLock._write_owner)."""
    doc: dict = {"last_run": NOW.date().isoformat(), "steps": steps}
    if stamp_quiet_h is not None:
        doc["last_progress"] = {"at": (NOW - timedelta(hours=stamp_quiet_h)).isoformat(),
                                "pid": 1}
    _w(tmp_path, "desks/mt5/data/daily_cycle_state.json", doc)
    if owner_quiet_h is not None:
        _w(tmp_path, "desks/mt5/data/.job_locks/daily_cycle.owner.json",
           {"pid": 1, "create_time": 1.0, "at": (NOW - timedelta(hours=9)).isoformat(),
            "last_progress": (NOW - timedelta(hours=owner_quiet_h)).isoformat(
                timespec="seconds")})


def test_the_step_list_is_imported_from_daily_cycle() -> None:
    assert len(STEPS) > 10 and STEPS[0] == "weekly_hunt_refresh"


def test_a_chain_that_stamps_the_day_then_stops_is_named(tmp_path: Path) -> None:
    _chain(tmp_path, {STEPS[0]: {"ok": False, "error": "AttributeError: gone"},
                      STEPS[1]: {"ok": True}}, stamp_quiet_h=5, owner_quiet_h=5)
    f = heal.check_daily_chain(tmp_path, NOW)
    assert not f.ok and f"2 of {len(STEPS)}" in f.detail and STEPS[2] in f.detail
    assert f"{STEPS[0]}: AttributeError: gone" in f.detail and "quiet 5.0h" in f.detail


def test_a_healthy_mid_run_chain_reads_ok_from_the_owner_sidecar(tmp_path: Path) -> None:
    """Audit HOLD: the stamp's progress is old (no step finished for hours, one long step) but
    the sidecar heartbeat is fresh -- a healthy chain at 18:00 UTC must not page."""
    _chain(tmp_path, {STEPS[0]: {"ok": True}}, stamp_quiet_h=6, owner_quiet_h=0.5)
    f = heal.check_daily_chain(tmp_path, NOW)
    assert f.ok, f.detail


def test_a_sidecar_only_box_still_measures_progress(tmp_path: Path) -> None:
    _chain(tmp_path, {STEPS[0]: {"ok": True}}, owner_quiet_h=0.2)
    assert heal.check_daily_chain(tmp_path, NOW).ok
    _chain(tmp_path, {STEPS[0]: {"ok": True}}, owner_quiet_h=4)
    f = heal.check_daily_chain(tmp_path, NOW)
    assert not f.ok and "quiet 4.0h" in f.detail


def test_no_progress_anywhere_is_unmeasured_and_stalled(tmp_path: Path) -> None:
    _chain(tmp_path, {STEPS[0]: {"ok": True}})
    f = heal.check_daily_chain(tmp_path, NOW)
    assert not f.ok and "UNMEASURED" in f.detail


def test_a_paused_gateway_is_not_a_crash(tmp_path: Path) -> None:
    """Principal 18:02Z: Fusion at 0 is a correct halt -- no alert spam while equity is 0."""
    _w(tmp_path, "desks/mt5/data/gateway_state.json", {"equity": 266.01}, age_h=25 * 24)
    _w(tmp_path, "desks/mt5/data/GATEWAY_PAUSED", "deadman")
    f = heal.check_gateway_publication(tmp_path, NOW)
    assert f.ok and "paused by the Fusion deadman" in f.detail


def test_a_standing_fault_pages_once_then_again_after_a_day(tmp_path: Path) -> None:
    _w(tmp_path, "desks/mt5/data/gateway_state.json", {"equity": 0}, age_h=48)

    def run(at: datetime) -> dict:
        return rheal.run(root=tmp_path, apply=True, out=tmp_path / "out.json",
                         ledger_path=tmp_path / "l.json", run_task=lambda _t: True, now=at,
                         task_running=lambda _t: False, end_task=lambda _t: True)

    t0 = datetime.now(UTC)
    assert "moneypath gateway" in run(t0)["moneypath_paged"]
    assert "moneypath gateway" not in run(t0 + timedelta(minutes=15))["moneypath_paged"]
    assert "moneypath gateway" in run(t0 + timedelta(hours=25))["moneypath_paged"]
    ev = (tmp_path / "desks/mt5/data/events.jsonl").read_text("utf-8").splitlines()
    gw = [r for r in map(json.loads, ev) if r.get("organ") == "moneypath gateway"]
    assert len(gw) == 2


def test_an_applied_pass_writes_one_event_per_moneypath_alert(tmp_path: Path) -> None:
    _w(tmp_path, "desks/mt5/data/gateway_state.json", {"equity": 0}, age_h=48)
    out = tmp_path / "out.json"
    doc = rheal.run(root=tmp_path, apply=True, out=out, ledger_path=tmp_path / "l.json",
                    run_task=lambda _t: True, now=datetime.now(UTC),
                    task_running=lambda _t: False, end_task=lambda _t: True)
    organs = [a["organ"] for a in doc["moneypath_alerts"]]
    assert "moneypath gateway" in organs
    ev = (tmp_path / "desks/mt5/data/events.jsonl").read_text("utf-8").splitlines()
    rows = [json.loads(x) for x in ev]
    assert any(r["kind"] == "PLUMBING_DEFECT" and r["defect"] == "MONEYPATH_CRASH"
               and r["organ"] == "moneypath gateway" for r in rows)
