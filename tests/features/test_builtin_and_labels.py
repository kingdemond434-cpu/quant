"""Tests that built-in features are causal, and that labels cannot be used as features."""

from __future__ import annotations

import numpy as np
import pytest
from tests.features.conftest import make_bars

from libs.features.builtin import BUILTIN_FEATURES
from libs.features.definition import FeatureDefinition
from libs.features.errors import FeatureError
from libs.features.labels import LABEL_PREFIX, forward_direction, forward_log_return
from libs.features.registry import FeatureRegistry, register_feature
from libs.features.validation import validate_feature


@pytest.mark.parametrize("definition", BUILTIN_FEATURES, ids=lambda d: d.key)
def test_builtin_features_are_causal_and_parity_clean(definition: FeatureDefinition) -> None:
    report = validate_feature(definition, make_bars(60))
    assert report.ok, report.reasons


def test_forward_log_return_is_forward_looking() -> None:
    bars = make_bars(20)
    label = forward_log_return(bars, horizon=1)
    expected = np.log(bars["close"].shift(-1) / bars["close"])
    assert label.name.startswith(LABEL_PREFIX)
    assert np.allclose(label.to_numpy()[:-1], expected.to_numpy()[:-1], equal_nan=True)
    assert np.isnan(label.iloc[-1])  # last has no future


def test_forward_direction_label() -> None:
    label = forward_direction(make_bars(20), horizon=1)
    assert set(np.unique(label.dropna())) <= {-1.0, 0.0, 1.0}


def test_label_used_as_feature_is_hindsight_leakage() -> None:
    bars = make_bars(40)
    hindsight = FeatureDefinition(
        "hindsight", 1, lambda df: forward_log_return(df, horizon=1), inputs=("close",)
    )
    report = validate_feature(hindsight, bars)
    assert not report.ok
    assert not report.leakage.ok
    reg = FeatureRegistry()
    with pytest.raises(FeatureError):
        register_feature(hindsight, registry=reg, bars=bars)
