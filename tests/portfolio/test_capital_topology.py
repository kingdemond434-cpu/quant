from __future__ import annotations

import math

from libs.portfolio.decision_intelligence import capital_topology


def test_capital_topology_prices_location_risk_and_efficiency() -> None:
    report = capital_topology(
        [
            {
                "venue": "a",
                "collateral": "USDT",
                "chain": "eth",
                "bridge": "none",
                "equity": 80,
                "failure_probability": 0.01,
                "recovery_fraction": 0.5,
                "margin_efficiency": 1.5,
            },
            {
                "venue": "b",
                "collateral": "USDC",
                "chain": "eth",
                "bridge": "none",
                "equity": 20,
                "failure_probability": 0.005,
                "recovery_fraction": 0.8,
                "margin_efficiency": 1.0,
            },
        ],
        max_venue_fraction=0.75,
    )
    assert report["venue"]["largest"] == 0.8
    assert report["capital_efficiency"] == 1.4
    assert report["expected_log_drag"] < 0
    assert report["breaches"] == ["VENUE_CONCENTRATION"]
    assert report["eligible"] is False


def test_missing_counterparty_risk_is_partial_not_zero() -> None:
    report = capital_topology([{"venue": "a", "equity": 10}])
    assert report["status"] == "PARTIALLY_MEASURED"
    assert report["expected_log_drag"] is None
    assert report["eligible"] is False


def test_total_loss_has_negative_infinite_log_wealth() -> None:
    report = capital_topology([
        {
            "venue": "only",
            "equity": 10,
            "failure_probability": 0.1,
            "recovery_fraction": 0.0,
        }
    ])
    assert math.isinf(report["stress"][0]["expected_log_drag"])
    assert report["expected_log_drag"] == -math.inf
