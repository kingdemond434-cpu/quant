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


#: Every way PowerShell can end, freeze or orphan a process, case-insensitive: the cmdlet and its
#: aliases, the native tools, the CIM/WMI terminate method and the .NET calls; suspending it, the
#: scheduled tasks that own it, the machine and the session under it; and Invoke-Expression,
#: which can run any of these from a string built at run time where no pin can read it.
_KILL = re.compile(
    r"\b(stop-process|spps|kill|taskkill|tskill|pskill|wmic|suspend-process"
    r"|stop-scheduledtask|disable-scheduledtask|unregister-scheduledtask|stop-service"
    r"|stop-computer|restart-computer|shutdown|logoff|iex|invoke-expression)\b"
    r"|terminate|\.kill\(|closemainwindow")


def _boundary(source: str, i: int) -> bool:
    """PowerShell opens a comment only where a token can start: line start, after whitespace or
    a separator. `a#b` is one bare word, so `Write-Host a#b; kill 1` must still show the kill."""
    return i == 0 or source[i - 1] in " \t\r\n;|&(){}"


def _code(source: str) -> str:
    """The script lower-cased with its comments removed, and ONLY its comments.

    A `#` inside a quoted string is text, not a comment: splitting every line at the first `#`
    let `Write-Host '#'; kill 1` through. This walks the source once, tracking single-quoted
    ('' escapes), double-quoted (backtick escapes) and here-strings (@' '@ / @" "@), and drops
    `# ...` to end of line and `<# ... #>` only outside them. String contents are KEPT, so a
    kill spelled inside a string still reads as one -- the safe side for a no-kill pin.
    """
    out: list[str] = []
    i, n = 0, len(source)
    while i < n:
        c = source[i]
        two = source[i:i + 2]
        if two in ("@'", '@"') and (i == 0 or source[i - 1] in " \t=(\n"):
            close = "\n" + two[1] + "@"
            j = source.find(close, i + 2)
            j = n if j < 0 else j + len(close)
            out.append(source[i:j])
            i = j
        elif c in ("'", '"'):
            j = i + 1
            while j < n:
                if c == '"' and source[j] == "`":
                    j += 2
                    continue
                if source[j] == c:
                    if j + 1 < n and source[j + 1] == c:      # doubled quote is an escape
                        j += 2
                        continue
                    break
                j += 1
            out.append(source[i:j + 1])
            i = j + 1
        elif two == "<#" and _boundary(source, i):
            j = source.find("#>", i + 2)
            i = n if j < 0 else j + 2
        elif c == "#" and _boundary(source, i):
            j = source.find("\n", i)
            i = n if j < 0 else j
        else:
            out.append(c)
            i += 1
    return "".join(out).lower()


def test_terminal_boot_never_kills_a_terminal() -> None:
    source = (ROOT / "ops" / "ensure_terminal.ps1").read_text(encoding="utf-8")
    hits = _KILL.findall(_code(source))
    assert not hits, f"the watchdog can end a process: {hits}"


def test_the_kill_pin_catches_every_spelling() -> None:
    for kill in ("stop-process -Id 1", "Stop-Process -Id 1", "kill 1", "spps 1",
                 "TASKKILL /PID 1", "Invoke-CimMethod -MethodName Terminate",
                 "wmic process where name='terminal64.exe' delete", "$p.Kill()",
                 "Suspend-Process -Id 1", "Stop-ScheduledTask MT5-Gateway",
                 "Disable-ScheduledTask MT5-Gateway", "Stop-Computer -Force",
                 "Restart-Computer", "shutdown /r /t 0", "logoff 2", "pskill 1",
                 "$p.CloseMainWindow()", "iex ('Stop-' + 'Process 1')",
                 "Invoke-Expression $cmd"):
        assert _KILL.findall(_code(kill)), kill
    assert not _KILL.findall(_code("# Stop-Process is never called here\n$x = 1"))
    assert not _KILL.findall(_code("<# block: Stop-Process #>\n$x = 1"))


def test_a_hash_inside_a_string_does_not_hide_the_code_after_it() -> None:
    for src in ("Write-Host '#'; kill 1", 'Write-Host "a#b"; Stop-Process -Id 1',
                "$s = 'it''s #1'; spps 1", 'Write-Host "`"#"; taskkill /PID 1',
                "$h = @'\n# not a comment\n'@\nStop-Process -Id 1",
                "Write-Host a#b; kill 1", "Write-Host a<#b; kill 1 #>"):
        assert _KILL.findall(_code(src)), src
    assert _code("$x = 1 # Stop-Process here is a comment") == "$x = 1 "


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


def test_an_unreadable_terminal_in_our_own_session_blocks_a_launch() -> None:
    source = (ROOT / "ops" / "ensure_terminal.ps1").read_text(encoding="utf-8")
    guard = source.index("$unreadableLocal.Count -gt 0")
    assert guard < source.index("Start-Process -FilePath $exe")
    assert "refusing to launch a second terminal" in source
    # ...but it asks the read-only probe first: an answering terminal is healthy, not refused
    branch = source[guard:source.index("refusing to launch a second terminal")]
    assert "Invoke-ReadOnlyProbe" in branch and "Write-BootHealth" in branch
    assert "exit 0" in branch
