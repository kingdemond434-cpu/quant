from __future__ import annotations

import numpy as np
import pytest

from libs.research.alpha_frontier import (
    alpha_reproduction,
    crowding_hazard,
    edge_npv,
    family_reality_priors,
    mechanism_eligibility,
    mechanism_half_life,
    mechanism_transfer,
    multi_timescale_state,
    null_factory_calibration,
    online_strategy_population,
    practitioner_frontier,
    return_source_decomposition,
    strategy_dna,
    tail_complementarity,
    useful_disagreement,
    validation_evig,
)


def test_alpha_reproduction_and_validation_evig() -> None:
    report = alpha_reproduction(
        [
            {"event": "BORN"},
            {"event": "BORN"},
            {"event": "DECAYED"},
            {"event": "REPLACED", "replacement_days": 3},
        ],
        window_days=10,
    )
    assert report["net_alpha_reproduction"] == 1
    assert report["replacement_ratio"] == 1
    assert report["median_days_to_replace"] == 3
    assert (
        validation_evig(
            probability_changes_decision=0.5, economic_value_if_resolved=10, test_cost=2
        )["run"]
        is True
    )
    assert (
        validation_evig(
            probability_changes_decision=0.1, economic_value_if_resolved=1, test_cost=2
        )["run"]
        is False
    )


def test_transfer_eligibility_and_multiscale_state() -> None:
    ok = mechanism_transfer("queue", "VENUE_SPECIFIC", {"venue": "binance"}, {"venue": ["binance"]})
    assert ok["eligible"] is True
    bad = mechanism_transfer("queue", "VENUE_SPECIFIC", {"venue": "other"}, {"venue": ["binance"]})
    assert bad["eligible"] is False
    with pytest.raises(ValueError):
        mechanism_transfer("x", "EVERYWHERE", {}, {})
    surface = mechanism_eligibility({"on": 0.8, "off": 0.2}, {"carry": {"on": 0.02, "off": -0.01}})
    assert surface["mechanisms"]["carry"]["eligible"] is True
    assert mechanism_eligibility({"on": 0.8}, {})["status"] == "UNMEASURED"
    state = multi_timescale_state(
        structural={"trend": "up"},
        tactical={},
        fast={"vol": "high"},
        microstructure={},
        as_of="now",
    )
    assert state["measured_layers"] == 2


def test_half_life_tail_and_online_population() -> None:
    times = np.arange(10)
    edges = 0.02 * 0.5 ** (times / 4)
    half = mechanism_half_life(edges, times)
    assert half["half_life"] == pytest.approx(4)
    assert mechanism_half_life([1, 2], [1, 2])["status"] == "UNMEASURED"
    rng = np.random.default_rng(3)
    left = rng.normal(0, 1, 100)
    right = -left + rng.normal(0, 0.1, 100)
    tail = tail_complementarity(left, right)
    assert tail["ordinary_correlation"] < -0.9
    assert tail_complementarity([1], [1])["status"] == "UNMEASURED"
    pop = online_strategy_population(
        [
            {"strategy": "a", "edge_mean": 0.03, "edge_uncertainty": 0.01, "decay_hazard": 0.1},
            {"strategy": "b", "edge_mean": -0.01, "edge_uncertainty": 0.0},
        ]
    )
    assert pop["population"][0]["strategy"] == "a"


def test_crowding_null_factory_and_reality_priors() -> None:
    history = [{"public_diffusion": x, "fill_deterioration": x} for x in (0, 0.1, 2)]
    crowd = crowding_hazard(history)
    assert crowd["crowding_decay_hazard"] > 0
    assert crowding_hazard(history[:2])["status"] == "UNMEASURED"
    controls = null_factory_calibration(
        [{"survived": True}] * 20, expected_false_positive_rate=0.01
    )
    assert controls["promotion_blocked"] is True
    assert (
        null_factory_calibration([], expected_false_positive_rate=0.01)["promotion_blocked"] is True
    )
    priors = family_reality_priors(
        [
            {"family": "carry", "upstream": 2, "downstream": 1},
            {"family": "carry", "upstream": 4, "downstream": 1},
        ]
    )
    assert priors["families"]["carry"]["median_retention"] == pytest.approx(0.375)


def test_disagreement_dna_return_decomposition_and_edge_npv() -> None:
    disagreement = useful_disagreement(
        [
            {"case": "1", "verdict": "pass", "unique_valid_finding": True},
            {"case": "1", "verdict": "fail"},
        ]
    )
    assert disagreement["disagreement_rate"] == 1
    dna = strategy_dna(
        [
            {"components": ["momentum"], "oos_elog": -0.1},
            {"components": ["momentum"], "oos_elog": -0.2},
            {"components": ["momentum"], "oos_elog": -0.3},
        ]
    )
    assert dna["genes"]["momentum"]["negative_gene"] is True
    decomp = return_source_decomposition(
        total_return=1.0, beta_return=0.4, carry_return=0.1, leverage_multiplier=3
    )
    assert decomp["components"]["unexplained_alpha_or_luck"] == pytest.approx(0.5)
    npv = edge_npv(
        edge_per_period=0.01,
        capacity=100,
        half_life_periods=10,
        implementation_periods=10,
        operating_cost_per_period=0.01,
    )
    assert npv["edge_retained_at_launch"] == pytest.approx(0.5)
    assert (
        edge_npv(
            edge_per_period=1,
            capacity=-1,
            half_life_periods=1,
            implementation_periods=0,
            operating_cost_per_period=0,
        )["status"]
        == "UNMEASURED"
    )


def test_practitioner_frontier_unifies_three_gpt_missions_without_replacing_kimi() -> None:
    report = practitioner_frontier(
        [
            {
                "mission": "VIDEO_TRANSCRIPT",
                "mechanism": "queue decay",
                "evidence_class": "VERIFIED",
            },
            {
                "mission": "EXTREME_RETURN",
                "mechanism": "carry",
                "evidence_class": "COMPETITION_RECORD",
            },
            {
                "mission": "PUBLIC_STRATEGY",
                "mechanism": "queue decay",
                "evidence_class": "BACKTEST",
            },
        ],
        known_mechanisms=["carry"],
    )
    assert report["new_mechanisms"] == ["queue decay"]
    assert report["mission_counts"]["VIDEO_TRANSCRIPT"] == 1
    assert report["k_miner_replaced"] is False
