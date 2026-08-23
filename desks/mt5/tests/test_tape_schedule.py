from __future__ import annotations

from pathlib import Path

INSTALLER = Path(__file__).parents[1] / "scripts" / "Install-QuantWindows.ps1"


def test_fusion_tick_tape_is_a_persistent_nonoverlapping_task() -> None:
    source = INSTALLER.read_text("utf-8")
    assert 'Name = "MT5-Tape"' in source
    assert 'Script = "mt5desk\\tape.py"' in source
    tape_block = source[source.index('Name = "MT5-Tape"') :]
    assert "New-TimeSpan -Minutes 15" in tape_block
    assert "MultipleInstances IgnoreNew" in source
