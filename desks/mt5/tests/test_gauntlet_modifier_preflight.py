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


def test_loky_reuses_the_gauntlets_measured_worker_ceiling() -> None:
    assert int(gauntlet.os.environ["LOKY_MAX_CPU_COUNT"]) >= 1
    assert int(gauntlet.os.environ["LOKY_MAX_CPU_COUNT"]) <= gauntlet.WORKERS
