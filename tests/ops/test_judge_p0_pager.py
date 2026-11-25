"""Judge P0 (2026-11-25): E10 pages -- 6 h without a verdict row, or a sweep heartbeat 1 h stale.

The 11-24/25 judge published nothing for ~33 h; the sweep heartbeat stopped at 12:56:39Z and
nothing paged, because no_verdict waited 36 h and nothing read the sweep's own heartbeat.
"""
from __future__ import annotations

import json
from datetime import timedelta

from tests.ops.test_judge_stall_pager import NOW, Channel, _iso, _step, _world, jsp  # noqa: F401


def _hb(tmp, age_h: float, status: str = "RUNNING") -> None:
    (tmp / "GAUNTLET_HEARTBEAT.json").write_text(json.dumps(
        {"pid": 18528, "status": status, "phase": "prewarm",
         "beat_utc": _iso(NOW - timedelta(hours=age_h))}), "utf-8")


def test_six_hours_without_a_verdict_row_pages(jsp, tmp_path):  # noqa: F811
    assert jsp.NO_VERDICT_H == 6.0
    ch = Channel()
    d = _step(jsp, tmp_path, NOW, ch, verdict_h=6.5)
    assert "no_verdict" in d["page"]["opened"] and ch.sent


def test_a_stale_running_sweep_heartbeat_pages_and_a_fresh_or_ended_one_does_not(
        jsp, tmp_path):  # noqa: F811
    ch = Channel()
    _hb(tmp_path, 0.2)
    d = _step(jsp, tmp_path, NOW, ch)
    assert d["incidents"]["sweep_heartbeat_stale"]["open"] is False and ch.sent == []
    _hb(tmp_path, 6.4)
    d = _step(jsp, tmp_path, NOW + timedelta(minutes=5), ch)
    assert d["incidents"]["sweep_heartbeat_stale"]["open"] is True
    assert d["page"]["opened"] == ["sweep_heartbeat_stale"]
    assert ch.sent[-1][0] == "JUDGE STALLED: sweep_heartbeat_stale"
    _hb(tmp_path, 6.4, status="DONE")
    d = _step(jsp, tmp_path, NOW + timedelta(minutes=10), ch)
    assert d["incidents"]["sweep_heartbeat_stale"]["open"] is False


def test_a_torn_sweep_heartbeat_is_unmeasured_never_clear(jsp, tmp_path):  # noqa: F811
    (tmp_path / "GAUNTLET_HEARTBEAT.json").write_text("{torn", "utf-8")
    d = jsp.measure(NOW, pid_alive=lambda *a: True, **_world(tmp_path, NOW))
    assert d["incidents"]["sweep_heartbeat_stale"]["open"] is None
