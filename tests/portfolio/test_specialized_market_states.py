from __future__ import annotations

import numpy as np
import pytest

from libs.portfolio.decision_intelligence import (
    venue_stress_state,
    volatility_manifold_state,
)


def test_volatility_manifold_uses_a_fixed_calibration_split() -> None:
    rng = np.random.default_rng(9)
    factor = rng.normal(size=(50, 1))
    loadings = np.array([[1.0, 0.5, -0.2, 0.8]])
    surfaces = factor @ loadings + rng.normal(0, 0.01, size=(50, 4))
    surfaces[-1] += np.array([6.0, -6.0, 6.0, -6.0])
    labels = ["BTC"] * 25 + ["ETH"] * 25
    report = volatility_manifold_state(
        surfaces, train_rows=35, rank=1, anomaly_quantile=0.95, asset_labels=labels
    )
    assert report["status"] == "MEASURED"
    assert report["latest_state"] == "ABNORMAL"
    assert report["held_out_rows"] == 15
    assert "ETH" in report["by_asset"]
    assert "CANDIDATE STATE ONLY" in report["authority"]


def test_volatility_manifold_refuses_bad_or_leaky_designs() -> None:
    with pytest.raises(ValueError, match="anomaly_quantile"):
        volatility_manifold_state([[1.0], [2.0]], train_rows=1, rank=1, anomaly_quantile=0.2)
    assert volatility_manifold_state([1.0, 2.0], train_rows=1, rank=1)["status"] == "UNMEASURED"
    x = np.arange(30.0).reshape(10, 3)
    assert volatility_manifold_state(x, train_rows=4, rank=1)["status"] == "UNMEASURED"
    assert volatility_manifold_state(x, train_rows=7, rank=3)["status"] == "UNMEASURED"


def _venue_history() -> list[dict[str, float | str]]:
    return [
        {
            "venue": "X",
            "as_of": f"2026-08-0{i + 1}",
            "liquidations": float(i),
            "insurance_fund_drawdown": float(i) / 10,
        }
        for i in range(5)
    ]


def test_venue_solvency_state_combines_dynamic_backstop_inputs() -> None:
    history = _venue_history()
    history[-1]["liquidations"] = 20.0
    history[-1]["insurance_fund_drawdown"] = 3.0
    report = venue_stress_state(
        history,
        components=("liquidations", "insurance_fund_drawdown"),
        alert_z=2.0,
    )
    assert report["status"] == "MEASURED"
    assert report["stress_alert"] is True
    assert report["venue"] == "X"
    assert set(report["uses"]) == {"alpha_research", "risk_protection", "venue_economics"}


def test_venue_state_preserves_missingness_and_predeclared_alerts() -> None:
    with pytest.raises(ValueError, match="positive"):
        venue_stress_state(_venue_history(), alert_z=0)
    assert venue_stress_state([])["status"] == "UNMEASURED"
    blank = [{"venue": "X"}] * 4
    assert venue_stress_state(blank, components=("adl_level",))["status"] == "UNMEASURED"
    partial = venue_stress_state(_venue_history(), components=("liquidations", "adl_level"))
    assert partial["status"] == "PARTIALLY_MEASURED"
    assert partial["stress_alert"] is None
    assert "adl_level" in partial["missing_components"]
