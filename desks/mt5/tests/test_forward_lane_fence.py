"""forward_lane_fence: every lane ticking, every certificate in a lane, or red with a repair."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "research"), str(DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import forward_lane_fence as flf  # noqa: E402

NOW = datetime(2026, 10, 13, 17, 0, tzinfo=UTC)


def _iso(hours_ago: float) -> str:
    return (NOW - timedelta(hours=hours_ago)).isoformat()


def _lane(updated_h: float, rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {"updated_at": _iso(updated_h), **rows}


def _clock(tick_h: float, start_d: float = 20.0) -> dict[str, Any]:
    return {"status": "ACTIVE", "last_attempt_at": _iso(tick_h),
            "forward_start": _iso(24 * start_d), "last_entry": _iso(5)}


def test_fresh_lane_is_fresh_and_a_stale_file_is_stale() -> None:
    spec = flf.LANES["qquant"]
    fresh = flf.lane_verdict("qquant", spec, _lane(0.5, {"a": _clock(0.5)}), NOW)
    stale = flf.lane_verdict("qquant", spec, _lane(5.0, {"a": _clock(0.5)}), NOW)
    assert fresh["verdict"] == flf.FRESH and fresh["rows_with_entry_24h"] == 1
    assert stale["verdict"] == flf.STALE


def test_a_fresh_file_with_a_silent_clock_is_stale() -> None:
    got = flf.lane_verdict("main", flf.LANES["main"], _lane(0.1, {"a": _clock(0.1),
                                                                 "b": _clock(9.0)}), NOW)
    assert got["verdict"] == flf.STALE and got["active_silent"] == 1


def test_absent_is_unmeasured_and_retired_is_retired() -> None:
    assert flf.lane_verdict("farm", flf.LANES["farm"], None, NOW)["verdict"] == flf.UNMEASURED
    ret = flf.lane_verdict("external", flf.LANES["external"],
                           {"pipeline_status": "RETIRED_REDUNDANT"}, NOW)
    assert ret["verdict"] == flf.RETIRED


def test_a_certificate_in_no_lane_past_one_cycle_is_red_and_the_farm_covers_it() -> None:
    census = {"certificates": [
        {"key": "A", "enrolled": True},
        {"key": "B", "enrolled": False, "clockless_hours": 30.0},
        {"key": "C", "enrolled": False, "clockless_hours": 0.2}]}
    red = flf.coverage(census, set(), NOW)
    assert red["verdict"] == "RED" and red["in_no_lane_over_one_cycle"] == 1
    green = flf.coverage(census, {"B", "C"}, NOW)
    assert green["verdict"] == "GREEN" and green["in_farm_only"] == 2
    assert green["share_in_a_lane"] == 1.0 and green["share_in_promoting_lane"] == 0.3333


def test_common_clock_counts_clocks_per_horizon() -> None:
    docs = {"main": _lane(0.1, {"a": _clock(0.1, 20), "b": _clock(0.1, 3),
                                "c": {"status": "KILL", "forward_start": _iso(24 * 90)}})}
    got = flf.common_clock(docs, NOW)
    assert got["accruing_clocks"] == 2
    assert got["clocks_with_at_least_days"]["14"] == 1
    assert got["clocks_with_at_least_days"]["30"] == 0


def test_a_stale_lane_is_restarted_and_proved_by_its_stamp(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    shadow = tmp_path / "shadow"
    shadow.mkdir()
    (shadow / "qquant_shadow_state.json").write_text(json.dumps(_lane(9.0, {})))
    monkeypatch.setattr(flf, "SHADOW", shadow)
    monkeypatch.setattr(flf, "_now", lambda: NOW)
    monkeypatch.setattr(flf, "_running", lambda script: False)
    monkeypatch.setattr(flf, "enrolment_census", lambda now: ({"certificates": [
        {"key": "A", "enrolled": True}]}, "test"))
    ran: list[list[str]] = []

    def fake_run(cmd: list[str], **_: Any) -> Any:
        ran.append(cmd)
        (shadow / "qquant_shadow_state.json").write_text(json.dumps(_lane(0.0, {})))

        class P:
            returncode, stdout, stderr = 0, "ok", ""
        return P()

    monkeypatch.setattr(flf.subprocess, "run", fake_run)
    doc = flf.run(out=tmp_path / "out.json")
    assert [Path(c[1]).name for c in ran] == ["qquant_shadow.py"]
    assert doc["repairs"][0]["status"] == "RESTARTED"
    assert doc["stale_lanes"] == [] and doc["verdict"] == "GREEN"


def test_hourly_leg_is_wired() -> None:
    text = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '_costed("forward_lane_fence"' in text
    from libs.research.layers import LEG_LAYER
    assert LEG_LAYER["forward_lane_fence"] == "timing"
