from __future__ import annotations

import pytest

from libs.validation.research_diagnostics import (
    ConditionalClaim,
    ablate_gates,
    cluster_failures,
    conditional_validation,
    threshold_sensitivity,
)


def test_threshold_sensitivity_exposes_knife_edges_without_selecting_a_bar() -> None:
    report = threshold_sensitivity([0.89, 0.95, 1.0, 1.04, 1.2], 1.0)
    assert report["status"] == "MEASURED"
    assert report["baseline_passed"] == 3
    assert report["max_flip_share"] > 0
    assert "never selects" in report["authority"]
    assert threshold_sensitivity([], 1.0)["status"] == "UNMEASURED"


def test_gate_ablation_attributes_unique_and_overlapping_kills() -> None:
    report = ablate_gates(
        {"cost": [True, False, False, True], "span": [True, True, False, False]},
        planted_positive=[True, True, False, False],
    )
    assert report["survivors"] == 1
    assert report["gates"]["cost"]["unique_kills"] == 1
    assert report["gates"]["span"]["unique_kills"] == 1
    assert report["kill_overlap"]["cost|span"] == 1
    with pytest.raises(ValueError):
        ablate_gates({"a": [True], "b": [True, False]})


def test_failure_clustering_counts_mechanisms_not_parameter_variants() -> None:
    report = cluster_failures(
        [
            {"key": "a", "family": "carry", "kill": "cost", "regime": "risk-off", "horizon": "1h"},
            {"key": "b", "family": "carry", "kill": "cost", "regime": "risk-off", "horizon": "1h"},
            {"key": "c", "family": "flow", "kill": "span", "regime": "all", "horizon": "1d"},
        ]
    )
    assert report["nominal"] == 3
    assert report["independent_archetypes"] == 2
    assert report["clusters"][0]["members"] == ["a", "b"]


def test_conditional_branch_requires_ex_ante_causal_untouched_state() -> None:
    base = {
        "claim_id": "liq-rebound-v1",
        "state_name": "liquidation",
        "state_declared_before_results": True,
        "state_observable_at_decision": True,
        "untouched_oos": True,
        "ancestry_trials": 100,
        "returns": tuple([0.02] * 40 + [-0.01] * 40),
        "state_mask": tuple([True] * 40 + [False] * 40),
    }
    measured = conditional_validation(ConditionalClaim(**base), min_state_n=30)
    assert measured["status"] == "MEASURED"
    assert measured["inherited_trials"] == 100
    assert measured["authority"].startswith("SCREEN_ONLY")

    refused = conditional_validation(
        ConditionalClaim(**(base | {"state_declared_before_results": False})), min_state_n=30
    )
    assert refused["status"] == "REFUSED"

    underpowered = conditional_validation(
        ConditionalClaim(**(base | {"state_mask": tuple([True] * 79 + [False])})), min_state_n=30
    )
    assert underpowered["status"] == "UNMEASURED"
