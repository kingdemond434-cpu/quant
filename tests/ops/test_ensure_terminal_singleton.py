import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_terminal_boot_requires_one_process_in_its_interactive_session() -> None:
    source = (ROOT / "ops" / "ensure_terminal.ps1").read_text(encoding="utf-8")
    assert "Get-CimInstance" not in source        # CIM hangs on the trading box
    assert "Get-Process -Name 'terminal64'" in source
    # an unreadable Path is another account's terminal: logged by session, never counted
    assert "unreadable-path terminal in session" in source
    assert "Where-Object { $_.Path -eq $exe }" in source


def test_terminal_boot_health_file_is_written_on_a_passed_probe_only() -> None:
    source = (ROOT / "ops" / "ensure_terminal.ps1").read_text(encoding="utf-8")
    assert source.index("terminal_boot_ok.json") > source.index("probe passed")
    contract = (ROOT / "ops" / "organ_contract.py").read_text(encoding="utf-8")
    assert '"MT5-TerminalBoot":   ("desks/mt5/data/terminal_boot_ok.json"' in contract
    assert "Where-Object { $_.SessionId -eq $session }" in source
    assert "if ($terminals.Count -gt 1)" in source
    assert "refusing automatic termination of an unverified owner" in source
    assert "Stop-Process" not in source


def test_terminal_boot_never_kills_a_different_broker_terminal() -> None:
    source = (ROOT / "ops" / "ensure_terminal.ps1").read_text(encoding="utf-8")
    assert "Get-Process terminal64 | Stop-Process" not in source
    assert "$_.Path -eq $exe" in source


#: Every way PowerShell can end a process, case-insensitive: the cmdlet and its aliases, the
#: native tools, the CIM/WMI terminate method and the .NET call.
_KILL = re.compile(r"\b(stop-process|spps|kill|taskkill|tskill|wmic)\b|terminate|\.kill\(")


def _code(source: str) -> str:
    """The script with comments removed (block comments, then line comments), lower-cased."""
    source = re.sub(r"<#.*?#>", "", source, flags=re.S)
    return "\n".join(line.split("#", 1)[0] for line in source.splitlines()).lower()


def test_terminal_boot_never_kills_a_terminal() -> None:
    source = (ROOT / "ops" / "ensure_terminal.ps1").read_text(encoding="utf-8")
    hits = _KILL.findall(_code(source))
    assert not hits, f"the watchdog can end a process: {hits}"


def test_the_kill_pin_catches_every_spelling() -> None:
    for kill in ("stop-process -Id 1", "Stop-Process -Id 1", "kill 1", "spps 1",
                 "TASKKILL /PID 1", "Invoke-CimMethod -MethodName Terminate",
                 "wmic process where name='terminal64.exe' delete", "$p.Kill()"):
        assert _KILL.findall(_code(kill)), kill
    assert not _KILL.findall(_code("# Stop-Process is never called here\n$x = 1"))


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
