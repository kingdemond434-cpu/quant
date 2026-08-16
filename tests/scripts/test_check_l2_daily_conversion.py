from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

from scripts.check_l2_daily_conversion import build_report

NOW = datetime(2026, 8, 15, 12, tzinfo=UTC)

def _write(root: Path, rel: str, value: object | None = None) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("heartbeat" if value is None else json.dumps(value), "utf-8")
    os.utime(path, (NOW.timestamp(), NOW.timestamp()))

def _base(root: Path, *, meaningful: bool = True, screen_pct: float = 100.0) -> None:
    for rel in ("data/recorder_heartbeat", "data/recorder_spot_heartbeat",
                "data/recorder_bybit_heartbeat"):
        _write(root, rel)
    _write(root, "data/moat_mine.json", {"cumulative_coverage": {"coverage_pct": 100.0},
        "closure": {"coverage_is_meaningful": meaningful,
                    "disk": {"state": "OK" if meaningful else "PAUSED", "free_bytes": 1}}})
    _write(root, "data/moat_screen.json", {"coverage_pct": screen_pct,
        "cells_covered_pct": screen_pct, "persistent_candidates": [], "survivors": []})
    _write(root, "data/moat_utilisation.json", {"utilisation": {
        "symbols_read_pct": 100.0, "symbol_hours_read_pct": 100.0}, "next_actions": []})

def test_full_measured_chain_can_be_operating(tmp_path: Path) -> None:
    _base(tmp_path)
    report = build_report(tmp_path, now=NOW)
    assert report["status"] == "OPERATING_FULL_CHAIN"
    assert report["redirect_queue"] == []

def test_frozen_tape_invalidates_reported_hundred_percent(tmp_path: Path) -> None:
    _base(tmp_path, meaningful=False)
    report = build_report(tmp_path, now=NOW)
    assert report["status"] == "REDIRECT_REQUIRED"
    assert report["coverage"]["mine_cells_pct"] == 100.0
    assert report["coverage"]["mine_coverage_meaningful"] is False
    assert any(r["stage"] == "RECORD" and "tape growth" in r["action"]
               for r in report["redirect_queue"])

def test_partial_screening_and_candidates_route_testing_and_conversion(tmp_path: Path) -> None:
    _base(tmp_path, screen_pct=63.5)
    p = tmp_path / "data/moat_screen.json"
    screen = json.loads(p.read_text("utf-8"))
    screen["persistent_candidates"] = [{"mechanism": "imbalance"}, {"mechanism": "microprice"}]
    _write(tmp_path, "data/moat_screen.json", screen)
    report = build_report(tmp_path, now=NOW)
    assert {"TEST", "CONVERT"} <= {r["stage"] for r in report["redirect_queue"]}
    assert report["coverage"]["persistent_candidates"] == 2

def test_stale_or_malformed_inputs_are_never_silently_complete(tmp_path: Path) -> None:
    _base(tmp_path)
    stale = tmp_path / "data/recorder_bybit_heartbeat"
    os.utime(stale, (NOW.timestamp() - 601, NOW.timestamp() - 601))
    (tmp_path / "data/moat_screen.json").write_text("not-json", "utf-8")
    report = build_report(tmp_path, now=NOW)
    assert report["status"] == "REDIRECT_REQUIRED"
    assert report["checks"]["recorder_bybit"]["fresh"] is False
    assert report["checks"]["screen"]["fresh_and_valid"] is False
