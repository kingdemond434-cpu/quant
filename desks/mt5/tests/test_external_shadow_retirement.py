from __future__ import annotations

import json
import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESK / "research"))

import external_shadow  # noqa: E402


def test_old_external_clock_is_retired_without_deleting_evidence(
    tmp_path: Path, monkeypatch,
) -> None:
    state_path = tmp_path / "external_shadow_state.json"
    state_path.write_text(json.dumps({
        "external.XAUUSD.session_range_breakout": {
            "status": "ACTIVE", "n": 3, "cum_r": 1.25,
            "forward_start": "2026-08-25T00:00:00+00:00",
        },
    }), "utf-8")
    monkeypatch.setattr(external_shadow, "STATE", state_path)

    assert external_shadow.main() == 0
    got = json.loads(state_path.read_text("utf-8"))
    row = got["external.XAUUSD.session_range_breakout"]
    assert row["status"] == "RETIRED_DUPLICATE_CLOCK"
    assert row["n"] == 3 and row["cum_r"] == 1.25
    assert row["promotion_authority"] is False
    assert got["pipeline_status"] == "RETIRED_REDUNDANT"


def test_retirement_is_idempotent(tmp_path: Path, monkeypatch) -> None:
    state_path = tmp_path / "external_shadow_state.json"
    state_path.write_text(json.dumps({
        "external.X": {"status": "RETIRED_DUPLICATE_CLOCK", "n": 7},
    }), "utf-8")
    monkeypatch.setattr(external_shadow, "STATE", state_path)
    assert external_shadow.main() == 0
    assert external_shadow.main() == 0
    got = json.loads(state_path.read_text("utf-8"))
    assert got["external.X"]["n"] == 7
    assert got["retired_duplicate_sleeves"] == 1
