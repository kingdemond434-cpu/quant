from __future__ import annotations

import pytest

from libs.research.external_intelligence import (
    mev_cex_fusion,
    portable_microstructure_representation,
)


def test_mev_cex_fusion_keeps_thin_cells_underpowered_and_counts_trials() -> None:
    events = [
        {
            "cex_state": "stressed",
            "blockspace_state": "congested",
            "liquidation_state": "high",
            "future_return": 0.01,
            "future_volatility": 0.02,
            "execution_cost_bps": 5,
        }
        for _ in range(5)
    ]
    report = mev_cex_fusion(events, min_cell_n=10)
    assert report["cells"][0]["status"] == "UNDERPOWERED"
    assert report["effective_trials"] == 1
    assert str(report["authority"]).startswith("SCREEN_ONLY")


def test_portability_is_measured_without_posthoc_threshold() -> None:
    events = []
    for asset in ("BTC", "ETH"):
        events.extend([
            {"asset": asset, "representation": "liquid", "future_state": "liquid"},
            {"asset": asset, "representation": "liquid", "future_state": "stressed"},
        ])
    report = portable_microstructure_representation(events)
    pair = report["pairwise_transport"][0]
    assert pair["mean_js_divergence"] == pytest.approx(0.0)
    assert pair["transfer_candidate"] is False
    assert report["preregistered_js_threshold"] is None


def test_preregistered_portability_threshold_can_nominate_only_a_screen() -> None:
    events = [
        {"asset": "BTC", "representation": "thin", "future_state": "stressed"},
        {"asset": "ETH", "representation": "thin", "future_state": "stressed"},
    ]
    report = portable_microstructure_representation(events, max_preregistered_js=0.05)
    assert report["pairwise_transport"][0]["transfer_candidate"] is True
    assert "leave-one-asset" in report["authority"]
