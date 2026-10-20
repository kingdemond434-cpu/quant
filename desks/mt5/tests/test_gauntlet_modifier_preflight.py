"""Deterministic non-executable variants must not consume gauntlet build workers."""

import copy

import pandas as pd
import pytest
from desks.mt5.scripts import external_gauntlet as gauntlet


def test_modifier_preflight_matches_build_refusal_without_bars() -> None:
    refused = gauntlet.modifier_preflight({
        "family": "overnight_drift",
        "params": {"anchor_hour": 8, "conditioner": "macro", "timeframe": "M5"},
    })
    assert refused is not None
    assert "conditioner='macro'" in refused


def test_modifier_preflight_keeps_executable_variant() -> None:
    assert gauntlet.modifier_preflight({
        "family": "overnight_drift",
        "params": {"anchor_hour": 8, "regime": "high_vol", "timeframe": "M5"},
    }) is None


def test_modifier_preflight_refuses_plain_unsupported_family_parameter() -> None:
    refused = gauntlet.modifier_preflight({
        "family": "failed_breakout",
        "params": {"max_hold": 9, "stop_atr": 1.0, "target_atr": 1.5,
                   "timeframe": "M15", "session": "asia"},
    })
    assert refused is not None
    assert "max_hold" in refused
    assert "stop_atr" in refused
    assert "target_atr" in refused


def test_modifier_preflight_does_not_pass_chart_labels_to_family() -> None:
    refused = gauntlet.modifier_preflight({
        "family": "multi_speed_trend",
        "params": {"chart": "M5", "parent_chart": "H1", "timeframe": "M15",
                   "speeds": [10, 21, 63], "hold_days": 5, "min_agreement": 0.6},
    })
    assert refused is not None
    assert "chart" in refused and "parent_chart" in refused


def test_loky_reuses_the_gauntlets_measured_worker_ceiling() -> None:
    assert int(gauntlet.os.environ["LOKY_MAX_CPU_COUNT"]) >= 1
    assert int(gauntlet.os.environ["LOKY_MAX_CPU_COUNT"]) <= gauntlet.WORKERS


@pytest.mark.parametrize("family,params,reason", [
    ("relative_value", {}, "no peer_symbol"),
    ("correlation_regime", {"timeframe": "M5"}, "no peer_symbol"),
    ("pca_residual", {}, "no complete named factor basket"),
    ("cross_asset_residual", {"factor_symbols": []}, "no complete named factor basket"),
    ("clock_transition", {"stamp_hour": 24}, "integer stamp_hour"),
    ("usd_session_shock", {}, "named FX driver"),
])
def test_required_input_preflight_matches_builder_and_preserves_spec(
        monkeypatch, family, params, reason):
    def no_bars(*args, **kwargs):
        raise AssertionError("deterministic incomplete inputs must never load bars")

    monkeypatch.setattr(gauntlet, "_frame_for", no_bars)
    spec = {"sym": "AUDCAD", "family": family, "params": params}
    before = copy.deepcopy(spec)
    why = gauntlet.modifier_preflight(spec)
    assert why is not None and reason in why
    assert gauntlet.build_cell("AUDCAD", family, params, {}) is None
    assert why == gauntlet.LAST_BUILD_FAILURE
    assert spec == before


def test_absent_executor_is_named_without_loading_bars():
    why = gauntlet.modifier_preflight({"family": "no_such_family", "params": {}})
    assert why is not None and "BLOCKED_EXECUTOR" in why


def test_warmer_keeps_builder_failure_reason(monkeypatch):
    frame = pd.DataFrame({"close": [1.0]}, index=pd.date_range("2026-01-01", periods=1, tz="UTC"))
    monkeypatch.setattr(gauntlet, "_bars_for", lambda *args: frame)
    monkeypatch.setattr(gauntlet, "cache_load", lambda *args: None)
    result = gauntlet._warm_one({"sym": "AUDCAD", "family": "relative_value", "params": {}}, {})
    assert result["status"] == "NOT_RUN_BUILD_FAILED"
    assert result["why"] == "BLOCKED_RULES: no peer_symbol on the candidate"
