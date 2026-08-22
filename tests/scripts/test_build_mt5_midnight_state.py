from __future__ import annotations

import json
from pathlib import Path

from scripts.build_mt5_midnight_state import build


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), "utf-8")


def test_build_reports_mt5_conversion_state_without_execution_authority(tmp_path: Path) -> None:
    desk = tmp_path / "desks" / "mt5"
    _write(desk / "data" / "universe" / "universe.json", {"XAUUSD": {}, "EURUSD": {}})
    (desk / "data" / "universe" / "XAUUSD_H1.parquet").write_bytes(b"bars")
    _write(
        desk / "data" / "research_queue.json",
        [{"id": "a", "status": "QUEUED"}, {"id": "b", "status": "TESTED"}],
    )
    _write(desk / "reports" / "UNIVERSAL_SURVIVORS.json", {"survivors": {"s1": {}}})
    _write(
        desk / "reports" / "shadow" / "shadow_state.json",
        {"last_run": "2026-08-22", "s1": {"n": 7}, "s2": {"n": 3}},
    )

    result = build(tmp_path)

    assert result["scope"] == "MT5_FUSION_ONLY"
    assert result["execution_authority"] is False
    assert result["universe"]["metadata_entities"] == 2
    assert result["universe"]["h1_bar_files"] == 1
    assert result["conversion"] == {
        "research_queue": {"QUEUED": 1, "TESTED": 1},
        "universal_survivors": 1,
        "shadow_sleeves": 2,
        "shadow_observations": 10,
        "shadow_last_run": "2026-08-22",
    }
    assert result["defects"] == []


def test_build_fails_visible_when_mt5_inputs_are_absent(tmp_path: Path) -> None:
    result = build(tmp_path)
    assert result["defects"]
    assert result["conversion"]["universal_survivors"] == 0
