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
