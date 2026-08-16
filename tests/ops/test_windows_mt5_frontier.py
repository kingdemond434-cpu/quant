from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_mt5_frontier_is_research_only_and_publishes_to_shadow() -> None:
    script = (ROOT / "ops" / "run_windows_mt5_frontier.ps1").read_text("utf-8")
    assert "--allow-readonly-live" in script
    assert "execution_authority = $false" in script
    assert "survival_gates_bypassed = $false" in script
    assert "run_crossasset_shadow.py" in script
    assert "order_send" not in script
    assert "--place" not in script


def test_mt5_frontier_covers_cross_asset_intraday_and_daily_frames() -> None:
    script = (ROOT / "ops" / "run_windows_mt5_frontier.ps1").read_text("utf-8")
    assert '--timeframes "D1,H4,H1,M15"' in script
    for asset_class in ("fx", "metal", "energy", "index"):
        assert f"data/lake/bronze/{asset_class}" in script


def test_mt5_frontier_installer_is_daily_and_catch_up_enabled() -> None:
    installer = (ROOT / "ops" / "install_windows_mt5_frontier.ps1").read_text("utf-8")
    assert "New-ScheduledTaskTrigger -Daily" in installer
    assert "-StartWhenAvailable" in installer
    assert "-AllowStartIfOnBatteries" in installer
    assert "QuantMT5Frontier" in installer
