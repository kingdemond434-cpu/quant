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


def _chain(tmp_path: Path, steps: dict, quiet_h: float) -> None:
    _w(tmp_path, "desks/mt5/research/daily_cycle.py",
       'STEPS = (("weekly_hunt_refresh", _w),\n         ("research_gap_map", _r),\n'
       '         ("refresh_bars", _b))\n\nX = 1\n')
    _w(tmp_path, "desks/mt5/data/daily_cycle_state.json",
       {"last_run": NOW.date().isoformat(), "steps": steps,
        "last_progress": {"at": (NOW - timedelta(hours=quiet_h)).isoformat()}})


def test_a_chain_that_stamps_the_day_then_stops_is_named(tmp_path: Path) -> None:
    _chain(tmp_path, {"weekly_hunt_refresh": {"ok": False, "error": "AttributeError: gone"},
                      "research_gap_map": {"ok": True}}, quiet_h=5)
    f = heal.check_daily_chain(tmp_path, NOW)
    assert not f.ok and "2 of 3" in f.detail and "refresh_bars" in f.detail
    assert "weekly_hunt_refresh: AttributeError: gone" in f.detail


def test_a_chain_still_progressing_is_not_stalled(tmp_path: Path) -> None:
    _chain(tmp_path, {"weekly_hunt_refresh": {"ok": True}}, quiet_h=0.5)
    assert heal.check_daily_chain(tmp_path, NOW).ok


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
