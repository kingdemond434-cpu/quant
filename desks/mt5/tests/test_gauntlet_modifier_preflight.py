"""Deterministic non-executable variants must not consume gauntlet build workers."""

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
