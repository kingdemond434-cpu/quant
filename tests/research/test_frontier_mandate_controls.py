from __future__ import annotations

import pytest

from libs.research.research_control import (
    causal_structure,
    context_packet,
    resolve_instruction_conflict,
    source_information_economics,
)


def test_causal_structure_requires_chain_and_invariance_predictions() -> None:
    nodes = {
        "participant_state": "leveraged long",
        "constraint_incentive": "margin call",
        "behavior": "forced sale",
        "observable_data": "liquidation print",
        "market_impact": "temporary impact",
        "expected_response": "rebound",
        "confounders": ["news shock"],
    }
    report = causal_structure(nodes, [
        {
            "from": "behavior",
            "to": "market_impact",
            "prediction": "impact rises with forced size",
            "environment": "independent venue",
        },
        {
            "from": "market_impact",
            "to": "expected_response",
            "prediction": "rebound weakens when informed flow dominates",
            "environment": "news days",
        },
    ])
    assert report["status"] == "MEASURED"
    assert report["multiple_independent_predictions"] is True
    assert report["diagnostics"]["confounders"] == ["news shock"]


def test_source_value_prices_latency_against_information_half_life() -> None:
    report = source_information_economics([{
        "source": "fast",
        "observation_latency_seconds": 1,
        "publication_latency_seconds": 1,
        "ingestion_latency_seconds": 8,
        "market_reaction_latency_seconds": 20,
        "information_half_life_seconds": 10,
        "historical_reliability": 0.8,
        "uniqueness": 0.5,
        "downstream_survivor_yield": 0.1,
    }])
    row = report["sources"][0]
    assert row["information_retained_at_ingestion"] == pytest.approx(0.5)
    assert row["latency_adjusted_option_value"] == pytest.approx(0.02)


def test_instruction_hierarchy_beats_a_higher_proxy_score() -> None:
    report = resolve_instruction_conflict([
        {"id": "survival", "precedence": 1, "expected_elog_gain": -1, "evidence_quality": 1},
        {"id": "throughput", "precedence": 9, "expected_elog_gain": 100, "evidence_quality": 1},
    ])
    assert report["winning_rule"] == "survival"
    assert report["overridden_rules"] == ["throughput"]


def test_context_packet_keeps_core_and_only_relevant_doctrine() -> None:
    report = context_packet(
        core=["survival", "evidence", "trust boundary"],
        doctrine_modules={"discovery": ["novelty", "dedupe"], "execution": ["paired intent"]},
        domain="discovery",
        dynamic_state={"task": "blind map", "dependencies": []},
    )
    assert report["status"] == "MEASURED"
    assert report["packet"]["core_constitution"] == ["survival", "evidence", "trust boundary"]
    assert report["packet"]["doctrine"] == ["novelty", "dedupe"]
    assert report["omitted_irrelevant_doctrine_items"] == 1
