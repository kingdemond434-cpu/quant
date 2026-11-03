"""Large reporting reads must never consume the converter's entire closure budget."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "research"))
import conversion_maximiser as cm


def test_streaming_census_matches_population_across_chunk_boundary(tmp_path, monkeypatch):
    rows = [{"family": "carry", "payload": "x" * ((1 << 20) + 11)},
            {"family": "carry"}, {"family": "pca_residual"}, {"other": 1}, 7]
    p = tmp_path / "docket.json"
    p.write_text(json.dumps(rows), encoding="utf-8")

    def no_whole_read(*args, **kwargs):
        raise AssertionError("the large docket must never be read whole")

    monkeypatch.setattr(Path, "read_text", no_whole_read)
    counts, total = cm._docket_family_counts(p)
    assert counts == {"carry": 2, "pca_residual": 1, "unknown": 1}
    assert total == len(rows)


@pytest.mark.parametrize("payload", ['[{"family":"carry"}', '[{},]', '[{} {}]', '[]extra', '{}'])
def test_partial_or_invalid_population_is_never_measured(tmp_path, payload):
    p = tmp_path / "docket.json"
    p.write_text(payload, encoding="utf-8")
    with pytest.raises(ValueError):
        cm._docket_family_counts(p)


def test_expired_reporting_budget_returns_no_population(tmp_path, monkeypatch):
    p = tmp_path / "docket.json"
    p.write_text('[{"family":"carry"}]', encoding="utf-8")
    monkeypatch.setattr(cm.time, "monotonic", lambda: 10.0)
    with pytest.raises(TimeoutError):
        cm._docket_family_counts(p, deadline=9.0)


def test_incomplete_census_is_explicit_and_never_reports_partial_ratios(tmp_path, monkeypatch):
    from research import merge_hypotheses as mh

    p = tmp_path / "docket.json"
    p.write_text('[{"family":"carry"}', encoding="utf-8")
    monkeypatch.setattr(mh, "TARGET", p)
    monkeypatch.setattr(mh, "judged_by_family", lambda: {"carry": 2})
    out = cm.judged_vs_docket()
    assert out["status"] == cm.UNMEASURED
    assert out["partial_population_published"] is False
    assert "least_judged_first" not in out
