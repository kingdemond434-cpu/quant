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


# --- R0289: the mutation covers EVERY perturbable column, not just OHLC ------------------


def test_non_ohlc_future_leak_rejected() -> None:
    """funding.shift(-1) passed unconditionally before R0289 -- the guard's blind axis was
    the desk's only repeat-survivor family."""
    bars = make_bars()
    for col in ("funding", "volume", "taker_buy_frac", "basis"):
        leaky = FeatureDefinition(
            f"peek_{col}", 1, lambda df, c=col: df[c].shift(-1), inputs=(col,), min_periods=1
        )
        leakage = run_leakage_test(leaky, bars)
        assert not leakage.ok, f"future leak via {col!r} not caught"
        assert leakage.n_leaked > 0


def test_non_ohlc_full_sample_normalization_rejected() -> None:
    bars = make_bars()
    leaky = FeatureDefinition(
        "funding_full_z", 1,
        lambda df: (df["funding"] - df["funding"].mean()) / df["funding"].std(),
        inputs=("funding",), min_periods=5,
    )
    assert not run_leakage_test(leaky, bars).ok


def test_final_bar_broadcast_rejected() -> None:
    """A funding[-1] broadcast reads the FINAL bar of the series -- demonstrated live as a
    pass before R0289."""
    import pandas as pd

    bars = make_bars()
    leaky = FeatureDefinition(
        "funding_last", 1,
        lambda df: pd.Series(df["funding"].iloc[-1], index=df.index),
        inputs=("funding",), min_periods=1,
    )
    assert not run_leakage_test(leaky, bars).ok


def test_ratio_leak_invariant_under_pure_scaling_is_caught() -> None:
    """(high/low).shift(-1) is INVARIANT under uniform scaling -- only the additive shift in
    the perturbation exposes it."""
    bars = make_bars()
    leaky = FeatureDefinition(
        "range_peek", 1, lambda df: (df["high"] / df["low"]).shift(-1),
        inputs=("high", "low"), min_periods=1,
    )
    leakage = run_leakage_test(leaky, bars)
    assert not leakage.ok
    assert leakage.n_leaked > 0


def test_causal_non_price_feature_passes() -> None:
    """No false positive on the axis the fix opened up."""
    bars = make_bars()
    causal = FeatureDefinition(
        "funding_ma3", 1, lambda df: df["funding"].rolling(3, min_periods=1).mean(),
        inputs=("funding",), min_periods=3,
    )
    report = validate_feature(causal, bars)
    assert report.ok, report.reasons


def test_causal_timestamp_feature_passes_and_timestamp_leak_is_caught() -> None:
    """Datetimes are perturbable (displaced), so session features stay validatable and a
    future-timestamp read is caught rather than silently passed."""
    bars = make_bars()
    causal = FeatureDefinition(
        "hour", 1, lambda df: df["timestamp"].dt.hour.astype("float64"),
        inputs=("timestamp",), min_periods=1,
    )
    assert run_leakage_test(causal, bars).ok
    leaky = FeatureDefinition(
        "hour_peek", 1, lambda df: df["timestamp"].dt.hour.astype("float64").shift(-1),
        inputs=("timestamp",), min_periods=1,
    )
    assert not run_leakage_test(leaky, bars).ok


def test_unperturbable_consumed_column_refuses_loudly() -> None:
    """A definition consuming a column the mutation cannot cover gets UNTESTABLE (ok=False),
    never a silent pass -- the UNMEASURED-REPORTED-AS-OK class (L1.40)."""
    bars = make_bars()
    bars["venue"] = "binance"
    consuming = FeatureDefinition(
        "venue_code", 1,
        lambda df: (df["venue"] == "binance").astype("float64"),
        inputs=("venue",), min_periods=1,
    )
    leakage = run_leakage_test(consuming, bars)
    assert not leakage.ok
    assert "UNTESTABLE" in leakage.message
    assert "venue" in leakage.untested_columns
    # ...but a bystander unperturbable column that no definition consumes must not fail
    # otherwise-causal features; it is reported, not fatal.
    report = run_leakage_test(causal_feature(), bars)
    assert report.ok
    assert "venue" in report.untested_columns
