from __future__ import annotations

import json
from datetime import UTC, datetime

from scripts import monitor_mt5_shadow_sync as monitor


def test_monitor_accepts_fresh_complete_authoritative_state(tmp_path, monkeypatch) -> None:
    shadow = tmp_path / "shadow"
    shadow.mkdir()
    (shadow / "shadow_health.json").write_text(json.dumps({
        "updated_at": datetime.now(UTC).isoformat(),
        "certified_sleeves_total": 2,
        "represented_sleeves": 2,
        "evidence_blocked_sleeves": 0,
        "status": "OPERATING",
    }))
    (shadow / "shadow_state.json").write_text(json.dumps({
        "A": {"status": "ACTIVE", "n": 1, "bar_source_stale": False},
        "B": {"status": "ACTIVE", "n": 0, "bar_source_stale": False},
    }))
    monkeypatch.setattr(monitor, "SHADOW", shadow)
    monkeypatch.setattr(monitor, "OUT", tmp_path / "monitor.json")

    assert monitor.main() == 0
    report = json.loads(monitor.OUT.read_text())
    assert report["status"] == "OPERATING"
    assert report["rows_with_forward_trades"] == 1


def test_monitor_fails_on_identity_or_staleness(tmp_path, monkeypatch) -> None:
    shadow = tmp_path / "shadow"
    shadow.mkdir()
    (shadow / "shadow_health.json").write_text(json.dumps({
        "updated_at": "2020-01-01T00:00:00+00:00",
        "certified_sleeves_total": 1,
        "represented_sleeves": 1,
        "evidence_blocked_sleeves": 1,
        "status": "EVIDENCE_BLOCKED",
    }))
    (shadow / "shadow_state.json").write_text(json.dumps({
        "A": {"status": "IDENTITY_BROKEN", "n": 0, "identity_drift": ["data_venue"]},
    }))
    monkeypatch.setattr(monitor, "SHADOW", shadow)
    monkeypatch.setattr(monitor, "OUT", tmp_path / "monitor.json")

    assert monitor.main() == 1
    report = json.loads(monitor.OUT.read_text())
    assert report["defects"]
    assert report["evidence_blocked_sleeves"] == 1


def test_desk_pull_includes_every_shadow_health_input() -> None:
    root = monitor.ROOT
    script = (root / "ops" / "pull_desk_state.sh").read_text("utf-8")

    assert "external_shadow_state.json" in script
    assert "shadow_health.json" in script
