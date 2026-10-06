from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_terminal_boot_requires_one_process_in_its_interactive_session() -> None:
    source = (ROOT / "ops" / "ensure_terminal.ps1").read_text(encoding="utf-8")
    assert "Get-CimInstance" not in source        # CIM hangs on the trading box
    assert "Get-Process -Name 'terminal64'" in source
    # an unreadable Path (another session) is counted, never dropped into a second launch
    assert "-not $_.Path -or $_.Path -eq $exe" in source
    assert "Where-Object { $_.SessionId -eq $session }" in source
    assert "if ($terminals.Count -gt 1)" in source
    assert "refusing automatic termination of an unverified owner" in source
    assert "Stop-Process" not in source


def test_terminal_boot_never_kills_a_different_broker_terminal() -> None:
    source = (ROOT / "ops" / "ensure_terminal.ps1").read_text(encoding="utf-8")
    assert "Get-Process terminal64 | Stop-Process" not in source
    assert "$_.Path -eq $exe" in source


def test_terminal_boot_never_kills_a_terminal_in_another_session() -> None:
    source = (ROOT / "ops" / "ensure_terminal.ps1").read_text(encoding="utf-8")
    for verb in ("Stop-Process", "taskkill", ".Kill(", "Terminate("):
        assert verb not in source


def test_terminal_probe_interpreter_is_resolved_not_assumed() -> None:
    source = (ROOT / "ops" / "ensure_terminal.ps1").read_text(encoding="utf-8")
    assert "$python = 'C:\\Program Files\\Python314\\python.exe'" not in source
    assert ".venv\\Scripts\\python.exe" in source
    assert "Get-Command python" in source


def test_terminal_boot_refuses_session_zero_and_probes_ipc_without_orders() -> None:
    source = (ROOT / "ops" / "ensure_terminal.ps1").read_text(encoding="utf-8")
    assert "if ($session -eq 0)" in source
    assert "refusing a headless launch" in source
    assert "if ($terminals.Count -gt 0 -and $local.Count -eq 0)" in source
    assert "probe_terminal.py" in source
    assert "$probeCode -ne 0" in source
    assert "allow_send=1" not in source


def test_batch_wrapper_does_not_embed_escaped_powershell_pipelines() -> None:
    source = (ROOT / "ops" / "ensure_terminal.cmd").read_text(encoding="utf-8")
    assert "ensure_terminal.ps1" in source
    assert " -Command " not in source
