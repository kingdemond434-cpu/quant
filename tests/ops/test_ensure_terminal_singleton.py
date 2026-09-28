from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_terminal_boot_repairs_duplicate_fusion_processes() -> None:
    source = (ROOT / "ops" / "ensure_terminal.cmd").read_text(encoding="utf-8")
    assert "Get-CimInstance Win32_Process" in source
    assert "Where-Object { $_.ExecutablePath -eq $env:EXE }" in source
    assert "Sort-Object CreationDate" in source
    assert "Select-Object -Skip 1" in source
    assert "Stop-Process -Id $_.ProcessId -Force" in source


def test_terminal_boot_never_kills_a_different_broker_terminal() -> None:
    source = (ROOT / "ops" / "ensure_terminal.cmd").read_text(encoding="utf-8")
    assert "Get-Process terminal64 | Stop-Process" not in source
    assert "$_.ExecutablePath -eq $env:EXE" in source
