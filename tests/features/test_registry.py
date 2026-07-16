"""Tests for the feature registry and versioning."""

from __future__ import annotations

import pytest
from tests.features.conftest import causal_feature, make_bars

from libs.features.builtin import register_builtin_features
from libs.features.errors import FeatureError
from libs.features.registry import FeatureRegistry, get_feature, register_feature


def test_register_and_get() -> None:
    reg = FeatureRegistry()
    register_feature(causal_feature(), registry=reg)
    assert "sma_3@v1" in reg
    assert reg.get("sma_3").version == 1


def test_duplicate_version_rejected() -> None:
    reg = FeatureRegistry()
    register_feature(causal_feature(), registry=reg)
    with pytest.raises(FeatureError):
        register_feature(causal_feature(), registry=reg)


def test_versions_and_latest() -> None:
    reg = FeatureRegistry()
    from libs.features.definition import FeatureDefinition

    reg.register(FeatureDefinition("f", 1, lambda df: df["close"], inputs=("close",)))
    reg.register(FeatureDefinition("f", 2, lambda df: df["close"] * 2, inputs=("close",)))
    assert reg.versions("f") == [1, 2]
    assert reg.get("f").version == 2  # latest
    assert reg.get("f", 1).version == 1


def test_get_missing_raises() -> None:
    reg = FeatureRegistry()
    with pytest.raises(FeatureError):
        reg.get("nope")


def test_register_with_validation_accepts_causal() -> None:
    reg = FeatureRegistry()
    register_feature(causal_feature(), registry=reg, bars=make_bars())
    assert "sma_3@v1" in reg


def test_builtins_registered_into_default() -> None:
    reg = FeatureRegistry()
    register_builtin_features(reg)
    assert get_feature("atr_14", registry=reg).inputs == ("high", "low", "close")
    assert len(reg) >= 9
