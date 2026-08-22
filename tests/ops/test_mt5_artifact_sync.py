from __future__ import annotations

from pathlib import Path

SYNC = Path("desks/mt5/scripts/sync_to_vps.ps1")
INSTALLER = Path("desks/mt5/scripts/Install-QuantWindows.ps1")


def test_full_artifact_sync_is_relocatable_and_carries_cost_evidence() -> None:
    source = SYNC.read_text("utf-8")
    assert '$base = Split-Path -Parent $PSScriptRoot' in source
    assert "C:\\Users\\dell\\mt5-research" not in source.split("$base =", 1)[1]
    for required in (
        '"universe"',
        '"order_intents.jsonl"',
        '"live_ledger.jsonl"',
        '"daily_cycle_state.json"',
        "$srcReports",
    ):
        assert required in source
    assert "git add $addPaths" not in source
    assert "tar -xzf '$remote'" in source


def test_full_artifact_sync_is_an_hourly_crash_recovering_task() -> None:
    source = INSTALLER.read_text("utf-8")
    assert 'TaskName "MT5-ArtifactSync"' in source
    assert "sync_to_vps.ps1" in source
    assert "New-TimeSpan -Hours 1" in source
    assert "StartWhenAvailable" in source
    assert "MultipleInstances IgnoreNew" in source
