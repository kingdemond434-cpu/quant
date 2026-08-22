from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESK / "research"))

import shadow_cycle  # noqa: E402


def test_cycle_runs_both_shadow_books_before_promoter(tmp_path: Path, monkeypatch) -> None:
    import promoter
    import scalp_shadow
    import shadow_forward

    calls: list[str] = []
    monkeypatch.setattr(shadow_forward, "SLEEVES", [("XAUUSD", "asia", None)])
    monkeypatch.setattr(shadow_forward, "UNIVERSE_SLEEVES", [])
    monkeypatch.setattr(scalp_shadow, "CANDIDATES", {"scalp": object()})
    monkeypatch.setattr(shadow_forward, "main", lambda: calls.append("legacy"))
    monkeypatch.setattr(scalp_shadow, "main", lambda: calls.append("scalp"))
    monkeypatch.setattr(promoter, "main", lambda: calls.append("promoter"))
    monkeypatch.setattr(shadow_cycle, "_refresh_scalp_bars", lambda: calls.append("refresh"))
    reports = tmp_path / "reports" / "shadow"
    reports.mkdir(parents=True)
    (reports / "shadow_state.json").write_text(json.dumps({"XAUUSD.asia": {"n": 0}}))
    (reports / "scalp_shadow_state.json").write_text(
        json.dumps({"sleeves": {"scalp": {"n": 0}}}))
    monkeypatch.setattr(shadow_cycle, "BASE", tmp_path)
    monkeypatch.setattr(shadow_cycle, "OUT", reports / "health.json")
    health, rc = shadow_cycle.run()
    assert calls == ["refresh", "legacy", "scalp", "promoter"]
    assert rc == 0 and health["configured_sleeves"] == 2
    # No gateway_state.json / sleeves.json on this box yet -- absence must read as
    # unarmed and no live sleeves, never crash and never default to the opposite.
    assert health["gateway_armed"] is False
    assert health["promoted_live_sleeves"] == []


def test_the_health_report_surfaces_live_arm_state_for_every_other_brain(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """gateway_state.json's `armed` flag is box-local and gitignored -- nothing outside
    this exact machine can see it any other way. This file is the one artifact
    MT5-ShadowSync already pushes to Hetzner every 15 minutes, so surfacing `armed`
    and the promoted-live-sleeve list here is what makes a fact that used to exist
    in exactly one place visible to every brain that reads the synced health report."""
    import promoter
    import scalp_shadow
    import shadow_forward

    monkeypatch.setattr(shadow_forward, "SLEEVES", [])
    monkeypatch.setattr(shadow_forward, "UNIVERSE_SLEEVES", [])
    monkeypatch.setattr(scalp_shadow, "CANDIDATES", {})
    monkeypatch.setattr(shadow_forward, "main", lambda: None)
    monkeypatch.setattr(scalp_shadow, "main", lambda: None)
    monkeypatch.setattr(promoter, "main", lambda: None)
    monkeypatch.setattr(shadow_cycle, "_refresh_scalp_bars", lambda: None)
    reports = tmp_path / "reports" / "shadow"
    reports.mkdir(parents=True)
    data = tmp_path / "data"
    data.mkdir(parents=True)
    (data / "gateway_state.json").write_text(json.dumps({"armed": True}))
    (data / "sleeves.json").write_text(json.dumps({"sleeves": [
        {"name": "GBPJPY.fair_value_gap", "status": "LIVE"},
        {"name": "CADJPY.asia", "status": "RETIRED"},
    ]}))
    monkeypatch.setattr(shadow_cycle, "BASE", tmp_path)
    monkeypatch.setattr(shadow_cycle, "OUT", reports / "health.json")
    health, _ = shadow_cycle.run()
    assert health["gateway_armed"] is True
    assert health["promoted_live_sleeves"] == ["GBPJPY.fair_value_gap"]


def test_missing_sleeve_fails_loud(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import promoter
    import scalp_shadow
    import shadow_forward

    monkeypatch.setattr(shadow_forward, "SLEEVES", [("XAUUSD", "asia", None)])
    monkeypatch.setattr(shadow_forward, "UNIVERSE_SLEEVES", [])
    monkeypatch.setattr(scalp_shadow, "CANDIDATES", {})
    monkeypatch.setattr(shadow_forward, "main", lambda: None)
    monkeypatch.setattr(scalp_shadow, "main", lambda: None)
    monkeypatch.setattr(promoter, "main", lambda: None)
    monkeypatch.setattr(shadow_cycle, "_refresh_scalp_bars", lambda: None)
    monkeypatch.setattr(shadow_cycle, "BASE", tmp_path)
    monkeypatch.setattr(shadow_cycle, "OUT", tmp_path / "health.json")
    health, rc = shadow_cycle.run()
    assert rc == 1 and health["missing_sleeves"] == ["XAUUSD.asia"]
