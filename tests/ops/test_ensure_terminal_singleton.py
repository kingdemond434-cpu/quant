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


def test_terminal_boot_ends_only_a_session_zero_or_a_hung_fusion_terminal() -> None:
    """TWO kill sites, both narrow (2026-11-17). A headless Session 0 Fusion terminal started by a
    bare initialize() after a reboot is closed, and the desk's own terminal is restarted only after
    it stops answering under the conditions pinned below; nothing else may end."""
    source = (ROOT / "ops" / "ensure_terminal.ps1").read_text(encoding="utf-8")
    hits = _KILL.findall(_code(source))
    names = [h if isinstance(h, str) else next(x for x in h if x) for h in hits]
    assert names == ["stop-process", "stop-process"], hits
    kill = source.index("Stop-Process -Id $h.Id")
    # only from an interactive session: the Session 0 exit comes first
    assert source.index("if ($session -eq 0)") < kill
    # only Fusion terminals (exact executable path), and only those in Session 0
    assert "$headless = @($terminals | Where-Object { $_.SessionId -eq 0 })" in source
    assert source.index("$headless = @($terminals") < kill
    assert "foreach ($h in $headless)" in source[:kill]
    # journalled to the log and the event log, then the census is re-read before any refusal
    branch = source[kill:source.index("if ($terminals.Count -gt 0 -and $local.Count -eq 0)")]
    assert "JOURNAL headless Session 0 Fusion terminal" in branch
    assert "TERMINAL_SESSION0_CLOSED" in branch and "events.jsonl" in source
    assert "$terminals = Get-FusionTerminals" in branch
    # a terminal in another interactive session is still refused, never ended
    assert "controlled recovery required" in source
    assert "Get-Process terminal64 | Stop-Process" not in source


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
    assert "$probeCode -ne 0" in source and "$probeCode -eq $HangCode" in source
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


def test_a_hung_terminal_is_restarted_only_under_its_conditions() -> None:
    source = (ROOT / "ops" / "ensure_terminal.ps1").read_text(encoding="utf-8")
    kill = source.index("Stop-Process -Id $old")
    gate = source.rindex("if ($count -ge $HungProbes", 0, kill)
    cond = source[gate:source.index("{", gate)]
    for term in ("$count -ge $HungProbes", "$hungMin -ge $HungMinutes", "$safe", "$cooled",
                 "$underCap", "$local.Count -eq 1"):
        assert term in cond, term
    # safe = flat book, paused gateway, or a hang long enough that nothing is being managed
    assert ("$safe = ($positions -eq 0) -or $paused -or ($hungMin -ge $HungUnmanagedMinutes)"
            in source)
    # an unreadable or missing position count is never read as flat
    assert "if ($null -ne $acct.open_positions)" in source
    assert "$HungProbes = 3" in source and "$HungMinutes = 15" in source
    assert "$RestartCooldownMinutes = 60" in source and "$MaxRestartsPerDay = 3" in source
    # only the one interactive terminal the census already holds, after the Session 0 exit
    assert source.index("if ($session -eq 0)") < kill
    assert "$old = $local[0].Id" in source[gate:kill]
    # journalled both ways, and health is written only on a passing re-probe
    after = source[kill:]
    assert "JOURNAL hung Fusion terminal" in after and "TERMINAL_HUNG_RESTARTED" in after
    assert after.index("if ($after -eq 0)") < after.index("Write-BootHealth")


def test_a_passing_probe_keeps_the_restart_cooldown() -> None:
    """Auditor MF1 (2026-11-17): the cooldown lives in the probe-failure file, so the file is
    never deleted; a pass -- after a restart or on its own -- resets the count and KEEPS
    last_restart_at, or a terminal that answers once and hangs again restarts every 3 probes."""
    source = (ROOT / "ops" / "ensure_terminal.ps1").read_text(encoding="utf-8")
    assert "Remove-Item -LiteralPath $hungPath" not in source
    assert "first_fail_at = $null; count = 0;" in source
    cleared = source[source.index("function Write-HungCleared"):]
    cleared = cleared[:cleared.index("\n}\n")]
    assert "$kept.last_restart_at" in cleared and "$kept.restarts_on_day" in cleared
    restart_pass = source[source.index("if ($after -eq 0)"):]
    assert restart_pass.index("Write-HungCleared ([pscustomobject]$state)") < restart_pass.index(
        "Write-BootHealth")
    # the restart stamps last_restart_at and the day's count before that write
    write = source.index("Write-HungCleared ([pscustomobject]$state)")
    assert source.index("$state.last_restart_at = $now.ToString('o')") < write
    assert source.index("$state.restarts_on_day = $restartsToday + 1") < write
    tail = source[source.rindex("Write-HungCleared (Read-Hung)"):]
    assert "Write-BootHealth" in tail


def test_only_the_hang_code_counts_toward_a_restart() -> None:
    """Auditor MF2 (2026-11-17): rc 99 (no python / no probe) and rc 1 (import error,
    traceback, account_info None) mean the PROBE is broken; they exit before the failure count
    is read or written, so they can never reach Stop-Process."""
    source = (ROOT / "ops" / "ensure_terminal.ps1").read_text(encoding="utf-8")
    assert "$HangCode = 2" in source
    probe = (ROOT / "desks" / "mt5" / "research" / "probe_terminal.py").read_text(encoding="utf-8")
    assert "if not ok:\n    sys.exit(2)" in probe
    broken = source.index("if ($probeCode -ne 0 -and $probeCode -ne $HangCode) {")
    hang = source.index("if ($probeCode -eq $HangCode) {")
    assert broken < hang < source.index("Stop-Process -Id $old")
    branch = source[broken:hang]
    assert "exit 2" in branch
    for forbidden in ("Read-Hung", "Set-Content", "$hungPath", "Stop-Process", "$count"):
        assert forbidden not in branch, forbidden


def test_restarts_are_capped_per_day_and_the_cap_is_journalled() -> None:
    source = (ROOT / "ops" / "ensure_terminal.ps1").read_text(encoding="utf-8")
    assert "$underCap = $restartsToday -lt $MaxRestartsPerDay" in source
    assert "$today = $now.ToString('yyyyMMdd')" in source
    assert "JOURNAL RESTART_CAP" in source and "'RESTART_CAP held'" in source
