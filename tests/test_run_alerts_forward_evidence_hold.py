"""The pager names every promotion candidate the forward-evidence hold kept over 24h."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import run_alerts


def _doc(path: Path, last_age_h: float) -> Path:
    now = datetime.now(UTC)
    path.write_text(json.dumps({"alarm_after_h": 24, "alarm": ["EURZAR.carry"], "held": {
        "EURZAR.carry": {"first_held_at": (now - timedelta(hours=30)).isoformat(),
                         "last_held_at": (now - timedelta(hours=last_age_h)).isoformat(),
                         "why": "forward evidence UNMEASURED: no bars"}}}), "utf-8")
    return path


def test_a_current_long_hold_pages(tmp_path: Path) -> None:
    out = run_alerts._forward_evidence_hold_alarms(_doc(tmp_path / "a.json", 0.25))
    assert [k for k, _ in out] == ["forward_evidence_hold_EURZAR.carry"]
    assert "UNMEASURED" in out[0][1]


def test_a_released_hold_does_not_page(tmp_path: Path) -> None:
    assert run_alerts._forward_evidence_hold_alarms(_doc(tmp_path / "a.json", 3.0)) == []


def test_an_absent_file_pages_nothing(tmp_path: Path) -> None:
    assert run_alerts._forward_evidence_hold_alarms(tmp_path / "missing.json") == []
