"""Tests for leakage detection and parity validation."""

from __future__ import annotations

import pytest
from tests.features.conftest import (
    causal_feature,
    full_sample_zscore_feature,
    future_return_feature,
    make_bars,
)

from libs.features.definition import FeatureDefinition
from libs.features.errors import FeatureError
from libs.features.registry import FeatureRegistry, register_feature
from libs.features.validation import run_leakage_test, run_parity_test, validate_feature


def test_causal_feature_passes() -> None:
    bars = make_bars()
    report = validate_feature(causal_feature(), bars)
    assert report.ok
    assert report.leakage.ok
    assert report.parity.ok


def test_future_leakage_rejected() -> None:
    bars = make_bars()
    leakage = run_leakage_test(future_return_feature(), bars)
    assert not leakage.ok
    assert leakage.n_leaked > 0
    report = validate_feature(future_return_feature(), bars)
    assert not report.ok


def test_full_sample_normalization_rejected() -> None:
    bars = make_bars()
    leakage = run_leakage_test(full_sample_zscore_feature(), bars)
    assert not leakage.ok


def test_target_leakage_rejected_structurally() -> None:
    bars = make_bars()
    bars["label_fwd"] = bars["close"].shift(-1)
    feature = FeatureDefinition("uses_label", 1, lambda df: df["label_fwd"], inputs=("label_fwd",))
    report = validate_feature(feature, bars, label_columns=["label_fwd"])
    assert not report.ok
    assert not report.structural_ok
    assert any("target leakage" in r for r in report.reasons)


def test_strict_validation_raises() -> None:
    with pytest.raises(FeatureError):
        validate_feature(future_return_feature(), make_bars(), strict=True)


def test_register_auto_rejects_leaky_feature() -> None:
    reg = FeatureRegistry()
    with pytest.raises(FeatureError):
        register_feature(future_return_feature(), registry=reg, bars=make_bars())
    assert "future_ret@v1" not in reg


def test_parity_holds_for_causal_feature() -> None:
    parity = run_parity_test(causal_feature(), make_bars())
    assert parity.ok
    assert parity.n_mismatch == 0
