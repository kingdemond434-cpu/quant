from __future__ import annotations

import json
import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESK / "research"))

import forward_reconcile  # noqa: E402


def test_qquant_certificate_identity_is_not_parsed_as_symbol_selector(
    tmp_path: Path, monkeypatch,
) -> None:
    reports = tmp_path / "reports"
    shadow = reports / "shadow"
    shadow.mkdir(parents=True)
    key = "qquant.hunt16.json.AUDNZD dav_range_filter_adx SHORT afternoon NORMAL_DAY"
    state_path = shadow / "qquant_shadow_state.json"
    state_path.write_text(json.dumps({
        key: {"certificate": key, "status": "ACTIVE", "n": 0},
    }), encoding="utf-8")

    monkeypatch.setattr(forward_reconcile, "BASE", tmp_path)
    monkeypatch.setattr(forward_reconcile, "SHADOW", shadow)
    monkeypatch.setattr(forward_reconcile, "OUT", tmp_path / "forward_reconcile.json")
    monkeypatch.setattr(forward_reconcile, "enrolled_keys", lambda: {key})
    monkeypatch.setattr(forward_reconcile, "certified_pairs", lambda: {("AUDNZD", "afternoon")})
    monkeypatch.setattr(forward_reconcile, "certified_ids", lambda: {key})

    assert forward_reconcile.main() == 0
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state[key]["status"] == "ACTIVE"
    assert "retired_at" not in state[key]


def test_frequent_shadow_owner_does_not_freeze_after_first_daily_run() -> None:
    source = (DESK / "research" / "shadow_forward.py").read_text(encoding="utf-8")
    assert "shadow already ran today; skip" not in source
    assert 'state["configured_sleeves"] = len(enrolled)' in source
