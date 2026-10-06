"""THE GLOBAL COVERAGE TENSOR FENCE, VALIDATED -- it passes this tree, and fails each lie it names.

Nothing here reads or writes the live reports: every artifact is built in `tmp_path`.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import check_global_coverage_tensor as F  # noqa: E402

NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)


@pytest.fixture
def arts(tmp_path, monkeypatch):
    paths = {"REPORT": tmp_path / "G.json", "ROI": tmp_path / "R.json",
             "BACKPRESSURE": tmp_path / "B.json"}
    for k, p in paths.items():
        monkeypatch.setattr(F, k, p)
    return paths


def _good(at: datetime = NOW) -> dict:
    return {"at": at.isoformat(), "nominal": 10**15, "distinct": 10**5,
            "effective_independent": 12.0, "proven_path_covered_share": 0.0001,
            "top_missions": [{"cell": "c"}], "missions": {"n_moves": 5}}


def test_the_portable_half_passes_this_tree_without_artifacts(arts):
    assert F.portable() == []


def test_a_missing_cro_key_fails(arts):
    doc = _good()
    del doc["proven_path_covered_share"]
    arts["REPORT"].write_text(json.dumps(doc), "utf-8")
    arts["ROI"].write_text(json.dumps({"funnel": {}, "incremental_keff": {}}), "utf-8")
    bad = " ".join(F.portable())
    assert "proven_path_covered_share" in bad and "info_gain_per_compute_hour" in bad


def test_holes_with_zero_missions_fails(arts):
    arts["REPORT"].write_text(json.dumps({**_good(), "top_missions": []}), "utf-8")
    assert any("ZERO missions" in b for b in F.portable())


def test_the_box_half_needs_all_three_artifacts_fresh(arts):
    assert len(F.state(NOW)) == 3, "absent is a failure on the box, never a clean pass"
    for k in ("REPORT", "ROI"):
        arts[k].write_text(json.dumps(_good()), "utf-8")
    arts["BACKPRESSURE"].write_text(json.dumps({"at": (NOW - timedelta(hours=5)).isoformat()}),
                                    "utf-8")
    bad = F.state(NOW)
    assert len(bad) == 1 and "B.json" in bad[0] and "stopped" in bad[0]
