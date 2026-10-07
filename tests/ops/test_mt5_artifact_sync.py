from __future__ import annotations

from pathlib import Path

SYNC = Path("desks/mt5/scripts/sync_to_vps.ps1")
INSTALLER = Path("desks/mt5/scripts/Install-QuantWindows.ps1")


def test_full_artifact_sync_is_relocatable_and_carries_cost_evidence() -> None:
    source = SYNC.read_text("utf-8")
    assert '$base = Split-Path -Parent $PSScriptRoot' in source
    assert "C:\\Users\\dell\\mt5-research" not in source.split("$base =", 1)[1]
    for required in (
        # each entry names its data\ directory (2026-10-06): a bare state-file name read as the
        # stale desk-root copy, so the scanner in test_no_reader_of_the_stale_desk_root_state
        # refuses it
        '"data\\universe"',
        '"data\\order_intents.jsonl"',
        '"data\\live_ledger.jsonl"',
        '"data\\daily_cycle_state.json"',
        '"data\\gateway_state.json"',
        '"data\\sync_marker.json"',
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
