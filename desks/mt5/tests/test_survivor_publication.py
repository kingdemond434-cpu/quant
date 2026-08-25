from __future__ import annotations

import json
import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
for path in (DESK, DESK / "research", DESK.parent.parent):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from gate_policy import ATTESTATION, GATES  # noqa: E402
from survivor_publication import publish_qquant_survivors  # noqa: E402
from universal_gate import retained_exact_survivors  # noqa: E402


def _stages(passed: bool = True) -> dict:
    return {name: {"passed": passed} for name in GATES}


def test_qquant_pass_is_atomically_merged_with_shadow_identity(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "UNIVERSAL_SURVIVORS.json").write_text(json.dumps({
        "survivors": {"other.hunt": {"cell": "kept"}},
        "gate_policy": ATTESTATION,
    }), encoding="utf-8")
    report = {
        "gate_policy": ATTESTATION,
        "swept_at": "2026-08-23T13:51:10+00:00",
        "verdicts": [{
            "id": "AUDNZD dav_range_filter_adx SHORT afternoon NORMAL_DAY",
            "hunt": "hunt16.json",
            "days": 179,
            "passed": True,
            "stages": _stages(),
        }],
    }
    result = publish_qquant_survivors(report, reports)
    assert result["survivor_count"] == 2
    payload = json.loads((reports / "UNIVERSAL_SURVIVORS.json").read_text("utf-8"))
    row = payload["survivors"][result["published"][0]]
    assert row["shadow_spec"] == {
        "symbol": "AUDNZD", "family": "dav_range_filter_adx", "side": "SHORT",
        "selector": "afternoon", "condition": "NORMAL_DAY", "is_universe": True,
        "hunt": "hunt16.json",
    }
    ledger = json.loads((reports / "SURVIVORS_LEDGER.json").read_text("utf-8"))
    assert ledger["n"] == 1


def test_failed_or_partial_rows_never_publish(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    report = {
        "gate_policy": ATTESTATION,
        "verdicts": [
            {"id": "A f LONG w s", "hunt": "h", "passed": False, "stages": _stages()},
            {"id": "B f LONG w s", "hunt": "h", "passed": True,
             "stages": {k: v for k, v in _stages().items() if k != "pbo"}},
        ],
    }
    assert publish_qquant_survivors(report, reports)["survivor_count"] == 0


def test_incremental_universal_sweep_retains_only_exact_prior_passes(tmp_path: Path) -> None:
    path = tmp_path / "UNIVERSAL_SURVIVORS.json"
    path.write_text(json.dumps({
        "gate_policy": ATTESTATION,
        "survivors": {
            "qquant.kept": {"gates": _stages(), "shadow_spec": {"symbol": "AUDNZD"}},
            "partial.rejected": {"gates": {"economic_prior": {"passed": True}}},
        },
    }), encoding="utf-8")
    assert retained_exact_survivors(path) == {
        "qquant.kept": {"gates": _stages(), "shadow_spec": {"symbol": "AUDNZD"}},
    }
