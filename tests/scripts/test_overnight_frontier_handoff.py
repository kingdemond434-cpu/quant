from __future__ import annotations

import json
from pathlib import Path

import scripts.overnight_frontier_handoff as handoff


def _configure(tmp_path: Path, monkeypatch) -> Path:
    data = tmp_path / "data"
    data.mkdir()
    contract = tmp_path / "docs" / "research" / "OVERNIGHT_FRONTIER_CONTRACT.json"
    contract.parent.mkdir(parents=True)
    contract.write_text(json.dumps({
        "required_artifacts": ["data/full_sweep.json", "data/max_push_queue.json"]
    }), "utf-8")
    monkeypatch.setattr(handoff, "ROOT", tmp_path)
    monkeypatch.setattr(handoff, "CONTRACT", contract)
    monkeypatch.setattr(handoff, "BASELINE", data / "overnight_frontier_baseline.json")
    monkeypatch.setattr(handoff, "OUT", data / "overnight_frontier_handoff.json")
    monkeypatch.setattr(handoff, "HISTORY", data / "overnight_frontier_history.jsonl")
    return data


def test_absent_conversion_evidence_is_unmeasured_not_zero(tmp_path: Path, monkeypatch) -> None:
    _configure(tmp_path, monkeypatch)
    metrics = handoff.conversion_metrics()
    assert all(row["status"] == "UNMEASURED" for row in metrics.values())
    assert all(row["value"] is None for row in metrics.values())


def test_finalize_emits_deltas_scorecard_harvest_and_generic_gaps(
    tmp_path: Path, monkeypatch
) -> None:
    data = _configure(tmp_path, monkeypatch)
    handoff.snapshot()
    baseline = json.loads(handoff.BASELINE.read_text("utf-8"))
    baseline["started_epoch"] = 0
    handoff.BASELINE.write_text(json.dumps(baseline), "utf-8")
    (data / "full_sweep.json").write_text(json.dumps({
        "counts": {
            "declared": 10, "measurable": 8, "FORMULA": 2,
            "INDEPENDENT_MECHANISM": 1, "PORTFOLIO_CONTRIBUTING": 1,
        },
        "killed_cells": [{}, {}, {}],
    }), "utf-8")
    (data / "research_review.json").write_text(
        json.dumps({"near_survivor_bank": {"count": 2}}), "utf-8"
    )
    (data / "max_push_queue.json").write_text(
        json.dumps({"queue": [{"aspect": "x", "score": 1.0}]}), "utf-8"
    )
    (data / "completion_program.json").write_text(json.dumps({
        "validation": {"power": {"status": "MEASURED"}},
        "production": {
            "deterministic_hot_path": {"status": "MEASURED"},
            "decision_ledger": {"status": "MEASURED"},
            "preflight": {"status": "ELIGIBLE"},
            "venue_capability": {"status": "ELIGIBLE"},
        },
    }), "utf-8")
    (data / "research_alpha_optimizer.json").write_text(json.dumps({
        "search_strategy_evolution": {
            "coverage": {"ratio": 0.5},
            "concentration": {"exploration_starvation": False},
            "serendipity_channel": {"status": "ACTIVE", "domain": "ecology"},
            "mutations_and_combinations": [], "retirement_candidates": [],
        }
    }), "utf-8")
    intelligence = data / "intelligence"
    intelligence.mkdir()
    (intelligence / "daily_alpha_frontier.json").write_text(json.dumps({
        "practitioner_frontier": {"new_mechanisms": ["m"]},
        "high_priority_residuals": [],
    }), "utf-8")
    report = handoff.finalize(pipeline_rc=0, sweep_rc=0, cycle_rc=0)
    assert report["conversion_metrics"]["hypotheses"]["value"] == 10
    assert report["conversion_metrics"]["independent_survivors"]["value"] == 1
    assert report["deltas"]["hypotheses"]["delta"] is None
    assert report["harvest"]["new_mechanisms"] == ["m"]
    assert report["maturity_scorecard"]["search_method_diversity"]["status"] == "HEALTHY"
    assert handoff.OUT.exists()
    assert (data / "published_gaps" / "overnight_frontier.json").exists()


def test_snapshot_is_machine_readable_and_preserves_git_state(tmp_path: Path, monkeypatch) -> None:
    _configure(tmp_path, monkeypatch)
    report = handoff.snapshot()
    saved = json.loads(handoff.BASELINE.read_text("utf-8"))
    assert saved["run_id"] == report["run_id"]
    assert "dirty_paths" in saved["git"]
