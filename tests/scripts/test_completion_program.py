from __future__ import annotations

import json
from pathlib import Path

import scripts.run_completion_program as program


def test_completion_program_is_fail_loud_on_missing_inputs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(program, "ROOT", tmp_path)
    monkeypatch.setattr(program, "OUT", tmp_path / "data" / "completion_program.json")
    report = program.build()
    assert report["authority"].startswith("MEASUREMENT_ONLY")
    assert report["validation"]["threshold_sensitivity"]["status"] == "UNMEASURED"
    assert report["portfolio"]["portfolio_monte_carlo"]["status"] == "UNMEASURED"
    assert report["research"]["frontier_health"]["frontier"]["escalate_measurement_set"] is True
    assert report["production"]["preflight"]["status"] == "INELIGIBLE"


def test_main_writes_one_consumable_artifact(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(program, "ROOT", tmp_path)
    out = tmp_path / "data" / "completion_program.json"
    monkeypatch.setattr(program, "OUT", out)
    assert program.main() == 0
    saved = json.loads(out.read_text("utf-8"))
    assert set(saved) >= {"validation", "portfolio", "research", "production"}


def test_program_consumes_conditional_disclosure_specialist_and_replay(
    tmp_path: Path, monkeypatch
) -> None:
    data = tmp_path / "data"
    data.mkdir()
    (data / "conditional_claims.json").write_text(
        json.dumps(
            {
                "claims": [
                    {
                        "claim_id": "c",
                        "state_name": "s",
                        "state_declared_before_results": True,
                        "state_observable_at_decision": True,
                        "untouched_oos": True,
                        "ancestry_trials": 10,
                        "returns": [0.02] * 40 + [-0.01] * 40,
                        "state_mask": [True] * 40 + [False] * 40,
                    }
                ]
            }
        ),
        "utf-8",
    )
    (data / "disclosure_events.json").write_text(
        json.dumps(
            {
                "events": [
                    {
                        "source": "exchange",
                        "published_at": "2026-01-01T00:00:00Z",
                        "first_seen_at": "2026-01-01T00:01:00Z",
                        "parsed_at": "2026-01-01T00:01:10Z",
                        "content_hash": "abc",
                        "claim": "margin change",
                    }
                ]
            }
        ),
        "utf-8",
    )
    (data / "specialist_history.json").write_text(
        json.dumps(
            {
                "events": [
                    {
                        "specialist_id": "s",
                        "task_id": "t",
                        "artifact": "a.json",
                        "useful_value": 2,
                        "cost": 1,
                        "completed": True,
                    }
                ]
            }
        ),
        "utf-8",
    )
    (data / "hot_path_replay.json").write_text(
        json.dumps(
            {
                "manifest": {"immutable": True, "manifest_hash": "h"},
                "observation": {"x": 1},
                "signal": {"s": 1},
                "desired_order": {"q": 1},
                "risk_output": {"q": 0.5},
                "adapter_order": {"q": 0.5},
            }
        ),
        "utf-8",
    )
    monkeypatch.setattr(program, "ROOT", tmp_path)
    report = program.build()
    assert report["validation"]["conditional_validation"][0]["status"] == "MEASURED"
    assert report["research"]["disclosure_intelligence"][0]["source_latency_seconds"] == 60
    assert report["research"]["ephemeral_specialists"][0]["persistent_worker_created"] is False
    assert report["production"]["deterministic_hot_path"]["status"] == "MEASURED"
