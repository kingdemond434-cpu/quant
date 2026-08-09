from __future__ import annotations

from libs.validation.research_diagnostics import sequential_experiment_design


def test_underpowered_null_is_absence_of_evidence() -> None:
    report = sequential_experiment_design(
        minimum_effect=0.1,
        noise_sd=1.0,
        available_n=10,
        planned_looks=4,
        observed_effect=0.0,
        standard_error=0.3,
    )
    assert report["powered"] is False
    assert report["evidence_class"] == "ABSENCE_OF_EVIDENCE"
    assert report["decision"] == "CONTINUE"
    assert report["per_look_alpha"] == 0.0125


def test_powered_interval_below_economic_effect_stops_for_futility() -> None:
    report = sequential_experiment_design(
        minimum_effect=0.2,
        noise_sd=0.2,
        available_n=500,
        observed_effect=0.01,
        standard_error=0.02,
    )
    assert report["powered"] is True
    assert report["decision"] == "STOP_FUTILITY"
    assert report["evidence_class"] == "EVIDENCE_OF_ECONOMIC_ABSENCE"


def test_positive_lower_bound_is_only_a_success_screen() -> None:
    report = sequential_experiment_design(
        minimum_effect=0.05,
        noise_sd=0.1,
        available_n=100,
        observed_effect=0.08,
        standard_error=0.01,
    )
    assert report["decision"] == "STOP_SUCCESS_SCREEN"
    assert str(report["authority"]).startswith("DIAGNOSTIC_ONLY")
