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
        "missing_sleeves": [],
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
        "missing_sleeves": [],
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


def _health(**over) -> dict:
    base = {
        "updated_at": datetime.now(UTC).isoformat(),
        "certified_sleeves_total": 22, "represented_sleeves": 21,
        "evidence_blocked_sleeves": 0, "missing_sleeves": [], "status": "OPERATING",
    }
    base.update(over)
    return base


def _wire(tmp_path, monkeypatch, health: dict) -> None:
    shadow = tmp_path / "shadow"
    shadow.mkdir()
    (shadow / "shadow_health.json").write_text(json.dumps(health))
    (shadow / "shadow_state.json").write_text(json.dumps({
        "A": {"status": "ACTIVE", "n": 3, "bar_source_stale": False},
        "B": {"status": "KILL", "n": 51},
    }))
    monkeypatch.setattr(monitor, "SHADOW", shadow)
    monkeypatch.setattr(monitor, "OUT", tmp_path / "monitor.json")


def test_a_killed_certificate_is_not_a_missing_sleeve(tmp_path, monkeypatch) -> None:
    """MEASURED 2026-08-27: 22 certificates enrolled, 21 rows still active, one KILL verdict --
    and the watchdog reported `shadow missing 1 certified sleeve(s)` against a book whose own
    producer said OPERATING with `missing_sleeves: []`.

    `represented_sleeves` counts ACTIVE rows and `certified_sleeves_total` counts every
    certificate ENROLLED, so the two diverge permanently the first time the pipeline kills
    anything -- and kills accumulate. An always-red detector buries the real one (L1.37).
    """
    _wire(tmp_path, monkeypatch, _health())
    assert monitor.main() == 0, "a killed certificate was reported as a missing one"
    report = json.loads(monitor.OUT.read_text())
    assert report["defects"] == []
    # The counters are still REPORTED -- they are worth reading, they are just not a defect test.
    assert report["certified"] == 22 and report["represented"] == 21


def test_a_genuinely_missing_sleeve_still_fails(tmp_path, monkeypatch) -> None:
    """The producer owns the key sets; when IT says a certificate is absent, this must fail."""
    _wire(tmp_path, monkeypatch, _health(missing_sleeves=["XAUUSD.asia"]))
    assert monitor.main() == 1
    report = json.loads(monitor.OUT.read_text())
    assert any("XAUUSD.asia" in d for d in report["defects"])


def test_a_health_file_with_no_missing_verdict_is_unmeasured_not_clean(
    tmp_path, monkeypatch,
) -> None:
    """Absence of the verdict is not the verdict `[]` (WS-005)."""
    health = _health()
    health.pop("missing_sleeves")
    _wire(tmp_path, monkeypatch, health)
    assert monitor.main() == 1
    report = json.loads(monitor.OUT.read_text())
    assert any("UNMEASURED" in d for d in report["defects"])
