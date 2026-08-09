from __future__ import annotations

import pytest

from libs.ops.production_contract import counterfactual_reality_gap


def _rows(offset: float = 0.0) -> list[dict[str, float]]:
    return [{"spread": float(i) + offset, "depth": float(2 * i) + offset} for i in range(1, 21)]


def test_counterfactual_worlds_require_real_calibration() -> None:
    report = counterfactual_reality_gap([], _rows(), features=("spread",))
    assert report["status"] == "UNMEASURED"
    assert report["synthetic_alpha_authority"] is False


def test_counterfactual_world_calibrates_only_for_robustness() -> None:
    report = counterfactual_reality_gap(
        _rows(), _rows(0.01), features=("spread", "depth"), max_preregistered_gap=0.1
    )
    assert report["status"] == "CALIBRATED_FOR_ROBUSTNESS_ONLY"
    assert report["calibrated"] is True
    assert report["correlations"]
    assert report["synthetic_alpha_authority"] is False


def test_material_simulation_reality_gap_is_loud() -> None:
    report = counterfactual_reality_gap(
        _rows(), _rows(100.0), features=("spread",), max_preregistered_gap=0.2
    )
    assert report["status"] == "REALITY_GAP"
    assert report["worst_normalized_gap"] > 1


def test_a_threshold_is_never_inferred_from_the_comparison() -> None:
    report = counterfactual_reality_gap(_rows(), _rows(), features=("spread",))
    assert report["status"] == "CALIBRATION_THRESHOLD_REQUIRED"
    with pytest.raises(ValueError, match="non-negative"):
        counterfactual_reality_gap(
            _rows(), _rows(), features=("spread",), max_preregistered_gap=-0.1
        )


def test_missing_and_constant_features_do_not_create_a_pass() -> None:
    real = [{"x": 1.0, "constant": 1.0} for _ in range(5)]
    synthetic = [{"x": 1.0, "constant": 1.0} for _ in range(5)]
    report = counterfactual_reality_gap(
        real, synthetic, features=("x", "constant", "absent"), max_preregistered_gap=0.1
    )
    assert any(row["status"] == "UNMEASURED" for row in report["features"])
    assert report["status"] == "CALIBRATED_FOR_ROBUSTNESS_ONLY"
