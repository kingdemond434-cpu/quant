from __future__ import annotations

from datetime import UTC, datetime, timedelta

from libs.data.asymmetry import (
    ASYMMETRY_AXES,
    information_advantage_frontier,
    replication_cost_profile,
    self_footprint_coverage,
)
from libs.research.external_intelligence import cross_universe_fusion, survivor_white_space


def _factors(value: float = 0.8) -> dict[str, float]:
    return {
        "source_breadth": value,
        "historical_depth": value,
        "data_cleaning": value,
        "entity_resolution": value,
        "compute": value,
        "specialist_knowledge": value,
        "latency": value,
        "engineering": value,
        "endogenous_history": value,
        "calibration_history": value,
    }


def test_replication_cost_is_explicit_and_never_imputed() -> None:
    assert replication_cost_profile({})["status"] == "UNMEASURED"
    partial = replication_cost_profile({"engineering": 0.9, "latency": 2.0})
    assert partial["status"] == "PARTIALLY_MEASURED"
    assert partial["replication_difficulty"] == 0.9
    assert "latency" in partial["invalid"]
    complete = replication_cost_profile(_factors())
    assert complete["status"] == "MEASURED"
    assert complete["replication_difficulty"] == 0.8


def test_information_frontier_enforces_legality_decay_and_small_desk_fit() -> None:
    now = datetime(2026, 8, 9, tzinfo=UTC)
    candidates = [
        {"id": "illegal", "lawfully_obtainable": False},
        {"id": "missing", "lawfully_obtainable": True},
        {
            "id": "fusion",
            "lawfully_obtainable": True,
            "economic_usefulness": 0.9,
            "persistence": 0.8,
            "independence": 0.7,
            "actionability": 0.9,
            "replication_factors": _factors(),
            "verified_at": (now - timedelta(days=10)).isoformat(),
            "half_life_days": 10,
            "acquisition_research_cost": 2.0,
            "capacity": 100_000,
            "desk_capital": 5_000,
            "institutional_minimum_capacity": 1_000_000,
            "asymmetry_class": "cross_venue",
            "state_recipe": ["CEX", "DEX"],
        },
    ]
    report = information_advantage_frontier(candidates, as_of=now)
    by_id = {row["id"]: row for row in report["candidates"]}
    assert by_id["illegal"]["status"].startswith("INELIGIBLE")
    assert by_id["missing"]["status"] == "UNMEASURED"
    assert by_id["fusion"]["decay_multiplier"] == 0.5
    assert by_id["fusion"]["small_scale_structural_fit"] is True
    assert "cross_venue" not in report["missing_axes"]
    assert set(ASYMMETRY_AXES) >= {"language", "execution", "capital_size"}


def test_endogenous_footprint_coverage_names_missing_moat_fields() -> None:
    assert self_footprint_coverage([])["status"] == "UNMEASURED"
    records = [
        {"event": "order_submitted", "timestamp": "2026-08-01T00:00:00+00:00"},
        {
            "event": "order_filled",
            "fill_price": 10,
            "slippage": 0.2,
            "timestamp": "2026-08-03T00:00:00+00:00",
        },
        {"decision": "research_decision", "hypothesis": "x"},
    ]
    report = self_footprint_coverage(records)
    assert report["history_days"] == 2
    assert "orders_submitted" in report["covered_fields"]
    assert "queue_estimates" in report["missing_fields"]


def test_cross_universe_fusion_requires_a_real_join_and_legality() -> None:
    values = {
        "expected_information_gain": 1.0,
        "survivor_generation_potential": 0.8,
        "independence": 0.7,
        "capacity": 0.6,
        "persistence": 0.7,
        "asymmetry": 0.9,
        "option_value": 0.5,
    }
    report = cross_universe_fusion(
        [
            {"id": "illegal", "lawfully_obtainable": False, "universes": ["a", "b"]},
            {"id": "one", "lawfully_obtainable": True, "universes": ["a"]},
            {
                "id": "mev-cex",
                "lawfully_obtainable": True,
                "universes": ["MEV", "CEX", "MEV"],
                "hidden_state": "blockspace pressure",
                "hypothesis": "CEX imbalance transports only in cheap blockspace",
                "acquisition_research_cost": 2.0,
                **values,
            },
        ]
    )
    by_id = {row["id"]: row for row in report["candidates"]}
    assert by_id["mev-cex"]["status"] == "TESTABLE_CANDIDATE"
    assert by_id["one"]["status"] == "INVALID_FUSION"
    assert by_id["illegal"]["status"].startswith("INELIGIBLE")
    assert set(report["represented_universes"]) >= {"MEV", "CEX"}


def test_white_space_map_covers_the_full_open_universe() -> None:
    report = survivor_white_space(
        [],
        [
            {
                "asset": "BTC",
                "venue": "DEX",
                "instrument": "option",
                "participant": "liquidator",
                "geography": "global",
                "language": "zh",
                "horizon": "1h",
                "regime": "stress",
                "data_modality": "mempool",
                "mechanism": "forced flow",
                "execution_style": "passive",
                "economic_plausibility": True,
                "independence": 1,
                "crisis_diversification": 1,
                "capacity": 1,
                "persistence": 1,
                "complementarity": 1,
                "cost": 1,
            }
        ],
    )
    assert len(report["dimensions"]) == 11
    assert report["candidate_cells"][0]["status"] == "TARGET_CANDIDATE"
