from __future__ import annotations

import json
from pathlib import Path

import scripts.run_completion_program as program


def _write(data: Path, name: str, doc: object) -> None:
    (data / name).write_text(json.dumps(doc), "utf-8")


def test_completion_program_consumes_new_mandate_controls(
    tmp_path: Path, monkeypatch
) -> None:
    data = tmp_path / "data"
    data.mkdir()
    _write(data, "experiment_designs.json", {"experiments": [{
        "minimum_effect": 0.1, "noise_sd": 0.2, "available_n": 200,
        "planned_looks": 2, "observed_effect": 0.01, "standard_error": 0.02,
    }]})
    _write(data, "capital_topology.json", {
        "accounts": [{
            "venue": "v", "collateral": "USDT", "equity": 10,
            "failure_probability": 0.01, "recovery_fraction": 0.5,
        }],
        "limits": {"max_venue_fraction": 1.0, "max_collateral_fraction": 1.0},
    })
    _write(data, "research_alpha_optimizer.json", {
        "search_strategy_evolution": {"status": "MEASURED", "coverage": {"ratio": 0.5}}
    })
    _write(data, "causal_mechanisms.json", {"mechanisms": [{
        "nodes": {
            "participant_state": "x", "constraint_incentive": "y", "behavior": "z",
            "observable_data": "o", "market_impact": "i", "expected_response": "r",
        },
        "links": [],
    }]})
    _write(data, "source_economics.json", {"sources": [{
        "source": "s", "observation_latency_seconds": 1,
        "publication_latency_seconds": 2, "ingestion_latency_seconds": 3,
        "market_reaction_latency_seconds": 9, "information_half_life_seconds": 12,
        "historical_reliability": 0.8, "uniqueness": 0.5,
        "downstream_survivor_yield": 0.1,
    }]})
    _write(data, "instruction_conflicts.json", {"conflicts": [{"rules": [
        {"id": "risk", "precedence": 1}, {"id": "proxy", "precedence": 9},
    ]}]})
    _write(data, "context_tasks.json", {
        "core": ["survival"], "doctrine_modules": {"discovery": ["novelty"]},
        "tasks": [{"domain": "discovery", "dynamic_state": {"task": "blind map"}}],
    })
    monkeypatch.setattr(program, "ROOT", tmp_path)
    report = program.build()
    assert report["validation"]["sequential_experiment_design"][0]["status"] == "MEASURED"
    assert report["portfolio"]["capital_topology"]["status"] == "MEASURED"
    research = report["research"]
    assert research["search_strategy_evolution"]["coverage"]["ratio"] == 0.5
    assert research["causal_structures"][0]["status"] == "MEASURED"
    assert research["source_information_economics"]["sources"][0]["status"] == "MEASURED"
    assert research["instruction_conflicts"][0]["winning_rule"] == "risk"
    assert research["context_packets"][0]["status"] == "MEASURED"
