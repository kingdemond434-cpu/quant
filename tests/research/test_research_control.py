from __future__ import annotations

import pytest

from libs.research.research_control import (
    actor_graph,
    compile_public_strategy,
    completion_supervisor,
    concurrency_economics,
    creator_change_intelligence,
    dependency_aware_evidence,
    distill_doctrine,
    distill_workflow,
    ephemeral_specialist,
    frontier_health,
    lawful_disclosure_record,
    missed_opportunity_tests,
    model_router,
    open_world_coverage,
    operator_surface,
    prequential_score,
    research_dag_schedule,
)


def test_disclosure_provenance_measures_latency_and_rejects_time_travel() -> None:
    row = lawful_disclosure_record(
        source="exchange-notice",
        published_at="2026-01-01T00:00:00Z",
        first_seen_at="2026-01-01T00:01:00Z",
        parsed_at="2026-01-01T00:01:10Z",
        content_hash="abc",
        claim="margin changes",
    )
    assert row["source_latency_seconds"] == 60
    assert row["parse_latency_seconds"] == 10
    with pytest.raises(ValueError):
        lawful_disclosure_record(
            source="x",
            published_at="2026-01-02T00:00:00Z",
            first_seen_at="2026-01-01T00:00:00Z",
            parsed_at="2026-01-03T00:00:00Z",
            content_hash="x",
            claim="x",
        )


def test_actor_identity_and_dependent_evidence_stay_honest() -> None:
    graph = actor_graph(
        [
            {"actor": "desk-a", "identity_confidence": 0.9, "action": "deposit", "asset": "BTC"},
            {"actor": "maybe-a", "identity_confidence": 0.3, "action": "sell", "asset": "BTC"},
        ]
    )
    assert graph["unknown_count"] == 1
    fused = dependency_aware_evidence([1.0, 1.0], [[1.0, 0.99], [0.99, 1.0]])
    assert fused["effective_evidence"] == pytest.approx(1.005025, rel=1e-5)
    assert fused["fused_value"] == pytest.approx(1.0)
    assert dependency_aware_evidence([], [])["status"] == "UNMEASURED"


def test_creator_changes_and_semantic_lattice() -> None:
    report = creator_change_intelligence(
        [
            {"creator": "a", "as_of": "1", "claim": "long", "source": "s1"},
            {"creator": "a", "as_of": "2", "claim": "flat", "source": "s2"},
        ]
    )
    assert report["change_count"] == 1
    compiled = compile_public_strategy(
        {
            "signal": "funding",
            "universe": "perps",
            "entry": "rich",
            "exit": "normal",
            "horizons": ["1h", "1d"],
            "thresholds": [1, 2],
        }
    )
    assert compiled["effective_trials"] == 8
    assert compile_public_strategy({"signal": "x"})["status"] == "REFUSED"


def test_dag_concurrency_and_model_routing_measure_useful_output() -> None:
    dag = research_dag_schedule(
        [
            {"id": "ingest", "expected_elog_gain": 1, "cost": 2},
            {"id": "test", "depends_on": ["ingest"], "expected_elog_gain": 10, "cost": 1},
        ]
    )
    assert dag["next"] == "ingest"
    econ = concurrency_economics(
        [
            {"workers": 1, "useful_outputs": 2, "hours": 1, "cost": 1},
            {"workers": 3, "useful_outputs": 3, "hours": 1, "cost": 6},
        ],
        work_waiting=5,
        available_slots=4,
    )
    assert econ["target_workers"] == 1
    assert econ["idle_defect"] is True
    route = model_router(
        [
            {"task_class": "audit", "model": "a", "downstream_value": 2, "cost": 1},
            {"task_class": "audit", "model": "b", "downstream_value": 1, "cost": 2},
        ],
        "audit",
    )
    assert route["selected"] == "a"
    assert model_router([], "audit")["selected"] is None


def test_ephemeral_workers_and_distillation_do_not_create_daemons() -> None:
    worker = ephemeral_specialist(
        specialist_id="s1", task_id="t1", artifact="a.json", useful_value=2, cost=1, completed=True
    )
    assert worker["lifecycle"][-1] == "TERMINATED"
    assert worker["persistent_worker_created"] is False
    workflows = distill_workflow([["read", "test"], ["read", "test"], ["read", "test"]])
    assert workflows["distillable"] == 1
    doctrine = distill_doctrine(
        [
            {"mechanism": "stale-input", "automatable": True},
            {"mechanism": "stale-input", "automatable": True},
        ]
    )
    assert doctrine["proposals"][0]["strongest_justified_form"] == "test"


def test_missed_opportunities_prequential_and_operator_surface() -> None:
    missed = missed_opportunity_tests(
        [
            {
                "id": "d1",
                "decision": "COST_REJECTED",
                "reason": "cost",
                "counterfactual_return": 0.02,
            },
            {"id": "d2", "decision": "EXECUTED", "counterfactual_return": 0.01},
        ]
    )
    assert missed["missed"] == 1
    assert missed["tests"][0]["promotion_authority"] is False
    score = prequential_score(
        [
            {"probability": 0.8, "outcome": 1},
            {"probability": 0.2, "outcome": 0},
            {"probability": 0.5, "outcome": None},
        ]
    )
    assert score["brier"] == pytest.approx(0.04)
    assert score["unresolved"] == 1
    assert prequential_score([{"probability": 0.5}])["status"] == "UNMEASURED"
    with pytest.raises(ValueError):
        prequential_score([{"probability": 1.2, "outcome": 1}])
    surface = operator_surface(
        live=[{"realised_pnl": 1}],
        blocked=[{"id": "b"}],
        queue=[{"id": "low", "score": 1}, {"id": "high", "score": 2}],
    )
    assert surface["making_money_count"] == 1
    assert surface["highest_value_next"]["id"] == "high"


def test_supervisor_and_frontier_keep_the_measurement_set_open() -> None:
    supervisor = completion_supervisor(
        [
            {"capability_id": "a", "status": "MISSING", "expected_elog_gain": 1, "cost": 1},
            {"capability_id": "b", "status": "MISSING", "expected_elog_gain": 4, "cost": 2},
            {"capability_id": "c", "status": "VERIFIED_COMPLETE", "expected_elog_gain": 9},
        ]
    )
    assert supervisor["next"]["capability_id"] == "b"
    frontier = frontier_health(
        discovered=100,
        distinct_mechanisms=20,
        tested=18,
        dispositioned=15,
        survivors=2,
        portfolio_tested=1,
        deployed=1,
        queue_waiting=9,
        eligible_capacity_idle=2,
        blind_spots_open=3,
        blind_spots_new=1,
    )
    assert frontier["breadth"]["independence_ratio"] == 0.2
    assert frontier["utilisation"]["idle_defect"] is True
    assert frontier["frontier"]["renewing"] is True


def test_open_world_coverage_ranks_white_space_and_never_claims_completion() -> None:
    report = open_world_coverage(
        [
            {
                "id": "covered",
                "source": "exchange",
                "language": "en",
                "asset": "BTC",
                "status": "COVERED",
            },
            {
                "id": "high-value-gap",
                "source": "regional-forum",
                "language": "vi",
                "asset": "small-cap",
                "venue": "regional",
                "research_method": "participant-first",
                "status": "UNTESTED",
                "expected_elog_gain": 4,
                "expected_information_gain": 2,
                "unknown_unknown_option_value": 2,
                "cost": 2,
                "lawfully_obtainable": True,
            },
            {
                "id": "illegal",
                "source": "private-chat",
                "status": "UNKNOWN",
                "expected_elog_gain": 100,
                "expected_information_gain": 100,
                "unknown_unknown_option_value": 100,
                "cost": 1,
                "lawfully_obtainable": False,
            },
        ],
        [
            {"dimension": "settlement_topology", "search_method": "ontology-adversarial"},
            {"dimension": "language", "search_method": "coverage-residual"},
        ],
    )
    assert report["daily_priority"][0]["cell_id"] == "high-value-gap"
    assert report["white_spaces"][-1]["cell_id"] == "illegal"
    assert report["novel_dimensions_discovered"] == ["settlement_topology"]
    assert report["taxonomy_renewing"] is True
    assert report["frontier_complete"] is False
    assert open_world_coverage([])["status"] == "UNMEASURED"
