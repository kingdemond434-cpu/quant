from __future__ import annotations

import pytest

from libs.validation.research_diagnostics import semantic_label_integrity


def test_semantic_truth_requires_an_authoritative_source() -> None:
    report = semantic_label_integrity(
        [], inferred_field="side", authoritative_field="truth", authoritative_source=""
    )
    assert report["status"] == "GROUND_TRUTH_SOURCE_REQUIRED"
    assert report["confidence_multiplier"] is None


def test_absent_and_underpowered_truth_remain_unvalidated() -> None:
    empty = semantic_label_integrity(
        [{}], inferred_field="side", authoritative_field="truth", authoritative_source="chain"
    )
    assert empty["status"] == "UNMEASURED"
    thin = semantic_label_integrity(
        [{"side": "BUY", "truth": "BUY"}],
        inferred_field="side",
        authoritative_field="truth",
        authoritative_source="native receipt",
        min_ground_truth=2,
    )
    assert thin["status"] == "UNDERPOWERED"
    assert thin["confidence_multiplier"] is None


def test_label_errors_reduce_confidence_and_expose_alpha_sign_flip() -> None:
    rows = []
    for index in range(40):
        inferred = "BUY" if index < 30 else "SELL"
        truth = "BUY" if index % 2 == 0 else "SELL"
        rows.append(
            {
                "inferred": inferred,
                "truth": truth,
                "future_return": 1.0 if inferred == "BUY" else -1.0,
            }
        )
    report = semantic_label_integrity(
        rows,
        inferred_field="inferred",
        authoritative_field="truth",
        authoritative_source="on-chain transaction truth",
        outcome_field="future_return",
        min_ground_truth=30,
        min_preregistered_kappa=0.8,
    )
    assert report["status"] == "SEMANTICS_FAILED"
    assert report["cohen_kappa"] < 0.8
    assert report["confidence_multiplier"] < 0.8
    assert report["outcome_effects"]


def test_validated_semantics_are_still_diagnostic_only() -> None:
    rows = [
        {"feed": "BUY" if i % 2 else "SELL", "truth": "BUY" if i % 2 else "SELL"} for i in range(40)
    ]
    report = semantic_label_integrity(
        rows,
        inferred_field="feed",
        authoritative_field="truth",
        authoritative_source="venue-native",
        min_preregistered_kappa=0.9,
    )
    assert report["status"] == "SEMANTICS_VALIDATED"
    assert report["confidence_multiplier"] == 1.0
    measured = semantic_label_integrity(
        rows,
        inferred_field="feed",
        authoritative_field="truth",
        authoritative_source="venue-native",
    )
    assert measured["status"] == "MEASURED_NOT_VALIDATED"


def test_semantic_audit_validates_its_design_inputs() -> None:
    with pytest.raises(ValueError, match="at least 2"):
        semantic_label_integrity(
            [],
            inferred_field="a",
            authoritative_field="b",
            authoritative_source="native",
            min_ground_truth=1,
        )
    with pytest.raises(ValueError, match=r"\[-1, 1\]"):
        semantic_label_integrity(
            [],
            inferred_field="a",
            authoritative_field="b",
            authoritative_source="native",
            min_preregistered_kappa=2,
        )
