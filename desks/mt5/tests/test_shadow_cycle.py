from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESK / "research"))

import shadow_cycle  # noqa: E402


def test_cycle_counts_only_certified_shadow_books_before_promoter(
    tmp_path: Path, monkeypatch,
) -> None:
    import promoter
    import qquant_shadow
    import scalp_shadow
    import shadow_forward

    calls: list[str] = []
    monkeypatch.setattr(shadow_forward, "main", lambda: calls.append("legacy"))
    monkeypatch.setattr(scalp_shadow, "main", lambda: calls.append("scalp"))
    monkeypatch.setattr(qquant_shadow, "main", lambda: calls.append("qquant"))
    monkeypatch.setattr(promoter, "main", lambda: calls.append("promoter"))
    monkeypatch.setattr(shadow_cycle, "_refresh_scalp_bars", lambda: calls.append("refresh"))
    reports = tmp_path / "reports" / "shadow"
    reports.mkdir(parents=True)
    (reports / "shadow_state.json").write_text(json.dumps({
        "configured_sleeves": 1, "gate_blocked_sleeves": 36,
        "XAUUSD.asia": {"n": 0, "gate_admission": "ORIGINAL_UNIVERSAL_10_PASS"},
    }))
    (reports / "scalp_shadow_state.json").write_text(
        json.dumps({"configured_sleeves": 1, "gate_blocked_sleeves": 4,
                    "sleeves": {"scalp": {"n": 0}}}))
    (reports / "qquant_shadow_state.json").write_text(json.dumps({
        "certified_qquant_sleeves": 1,
        "qquant.pass": {"n": 0, "status": "NO_DATA"},
    }))
    monkeypatch.setattr(shadow_cycle, "BASE", tmp_path)
    monkeypatch.setattr(shadow_cycle, "OUT", reports / "health.json")
    health, rc = shadow_cycle.run()
    assert calls == ["refresh", "legacy", "scalp", "qquant", "promoter"]
    assert rc == 2 and health["configured_sleeves"] == 3
    assert health["status"] == "EVIDENCE_BLOCKED"
    assert health["represented_sleeves"] == 3
    assert health["certified_sleeves_total"] == 3
    assert health["retired_shadow_sleeves"] == 0
    assert health["quarantined_uncertified_candidates"] == 40


def test_terminal_shadow_verdict_is_retained_but_not_active(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import promoter
    import qquant_shadow
    import scalp_shadow
    import shadow_forward

    for module in (shadow_forward, scalp_shadow, qquant_shadow, promoter):
        monkeypatch.setattr(module, "main", lambda: None)
    monkeypatch.setattr(shadow_cycle, "_refresh_scalp_bars", lambda: None)
    reports = tmp_path / "reports" / "shadow"
    reports.mkdir(parents=True)
    (reports / "shadow_state.json").write_text(json.dumps({"configured_sleeves": 0}))
    (reports / "scalp_shadow_state.json").write_text(json.dumps({
        "configured_sleeves": 0, "sleeves": {},
    }))
    (reports / "qquant_shadow_state.json").write_text(json.dumps({
        "certified_qquant_sleeves": 1,
        "qquant.retired": {"n": 50, "status": "RETIRED_GATE_FAIL"},
    }))
    monkeypatch.setattr(shadow_cycle, "BASE", tmp_path)
    monkeypatch.setattr(shadow_cycle, "OUT", reports / "health.json")
    health, rc = shadow_cycle.run()
    assert rc == 0 and health["status"] == "OPERATING"
    assert health["configured_sleeves"] == 0
    assert health["certified_sleeves_total"] == 1
    assert health["retired_shadow_sleeves"] == 1


def test_missing_sleeve_fails_loud(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import promoter
    import qquant_shadow
    import scalp_shadow
    import shadow_forward

    monkeypatch.setattr(shadow_forward, "main", lambda: None)
    monkeypatch.setattr(scalp_shadow, "main", lambda: None)
    monkeypatch.setattr(qquant_shadow, "main", lambda: None)
    monkeypatch.setattr(promoter, "main", lambda: None)
    monkeypatch.setattr(shadow_cycle, "_refresh_scalp_bars", lambda: None)
    reports = tmp_path / "reports" / "shadow"
    reports.mkdir(parents=True)
    (reports / "shadow_state.json").write_text(json.dumps({"configured_sleeves": 1}))
    (reports / "scalp_shadow_state.json").write_text(json.dumps({
        "configured_sleeves": 0, "sleeves": {},
    }))
    (reports / "qquant_shadow_state.json").write_text(json.dumps({
        "certified_qquant_sleeves": 0,
    }))
    monkeypatch.setattr(shadow_cycle, "BASE", tmp_path)
    monkeypatch.setattr(shadow_cycle, "OUT", tmp_path / "health.json")
    health, rc = shadow_cycle.run()
    assert rc == 1 and health["missing_sleeves"] == ["1 certified sleeve(s)"]


def test_nonzero_step_result_fails_loud(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import promoter
    import qquant_shadow
    import scalp_shadow
    import shadow_forward

    monkeypatch.setattr(shadow_forward, "main", lambda: None)
    monkeypatch.setattr(scalp_shadow, "main", lambda: None)
    monkeypatch.setattr(qquant_shadow, "main", lambda: 1)
    monkeypatch.setattr(promoter, "main", lambda: None)
    monkeypatch.setattr(shadow_cycle, "_refresh_scalp_bars", lambda: None)
    reports = tmp_path / "reports" / "shadow"
    reports.mkdir(parents=True)
    (reports / "shadow_state.json").write_text(json.dumps({"configured_sleeves": 0}))
    (reports / "scalp_shadow_state.json").write_text(json.dumps({
        "configured_sleeves": 0, "sleeves": {},
    }))
    (reports / "qquant_shadow_state.json").write_text(json.dumps({
        "certified_qquant_sleeves": 0,
    }))
    monkeypatch.setattr(shadow_cycle, "BASE", tmp_path)
    monkeypatch.setattr(shadow_cycle, "OUT", tmp_path / "health.json")

    health, rc = shadow_cycle.run()

    assert rc == 1
    assert health["errors"]["qquant_shadow"] == "RuntimeError: returned non-zero status 1"
