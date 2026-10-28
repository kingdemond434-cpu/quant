"""The box bridge's watchdog (ops/bridge/): source-level pins for the properties that keep the
bridge alive without zuck and keep it from doing anything the hand-started bridge did not."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "ops" / "bridge"
WATCHDOG = (BRIDGE / "bridge_watchdog.ps1").read_text(encoding="utf-8")
INSTALL = (BRIDGE / "install_bridge_watchdog.ps1").read_text(encoding="utf-8")
STATUS = (BRIDGE / "bridge_status.ps1").read_text(encoding="utf-8")


def _code(src: str) -> str:
    """The script without its comments and help block: what it DOES, not what it says."""
    src = re.sub(r"<#.*?#>", "", src, flags=re.S)
    return "\n".join(line for line in src.splitlines() if not line.lstrip().startswith("#"))


SCRIPTS = {"watchdog": _code(WATCHDOG), "installer": _code(INSTALL), "status": _code(STATUS)}
#: The bytes as shipped, comments and here-strings included: a banned call hidden between a
#: here-string holding "<#" and one holding "#>" is stripped by `_code` but not from these.
RAW = {"watchdog": WATCHDOG, "installer": INSTALL, "status": STATUS}

#: What none of the three may do. Each pattern is a way to widen the sessions' permissions, store
#: or set a secret, change machine state outside the bridge's own folders, or kill a process.
BANNED = {
    "permission flag": (
        r"--permission-mode|--allowedTools|--allowed-tools|--dangerously|bypassPermissions"
    ),
    "settings override": r"--settings|settings\.json|managed-settings",
    "environment write": r"\$env:\w+\s*=|SetEnvironmentVariable|Set-Item\s+-Path\s+env:|setx",
    "registry write": r"Set-ItemProperty|New-ItemProperty|reg(\.exe)?\s+add|HKLM:|HKCU:",
    "auto-logon": r"Winlogon|AutoAdminLogon|Autologon|DefaultPassword",
    "stored password": r"-Password\b|ConvertTo-SecureString|-LogonType\s+(Password|S4U)",
    "process kill": r"Stop-Process|taskkill|\.Kill\(",
    "sign-in": r"auth\s+login|setup-token|ANTHROPIC_API_KEY|credentials",
    "live tree": r"C:\\opt\\quant(?!\w)",
    # including a command name built at run time: the call operator on an expression, & ("i"+"ex")
    "dynamic code": (
        r"Invoke-Expression|\biex\b|\[scriptblock\]::Create|\.AddScript\(|-EncodedCommand|&\s*\("
    ),
    # a name hidden from every pattern above: a backtick inside a word (Ki`ll), or a member named
    # by a string or a variable (."Kill"(), .$m())
    "obfuscation": r"`[^nrt\r\n\s]|\.\s*[\"'][\w`]+[\"']\s*\(|\.\s*\$\w+\s*\(",
}


@pytest.mark.parametrize("script", sorted(SCRIPTS))
@pytest.mark.parametrize("what", sorted(BANNED))
def test_no_script_does_what_the_bridge_must_not(script: str, what: str) -> None:
    # comments may quote code in backticks, so obfuscation is judged on the code alone
    for text in (SCRIPTS[script], RAW[script]) if what != "obfuscation" else (SCRIPTS[script],):
        m = re.search(BANNED[what], text, flags=re.I)
        assert m is None, f"{script}: {what}: {m.group(0) if m else ''}"


def test_the_banned_patterns_catch_what_they_name() -> None:
    probes = {
        "permission flag": '"--permission-mode", "acceptEdits"',
        "settings override": "Set-Content $HOME\\.claude\\settings.json",
        "environment write": "$env:CLAUDE_X = 1",
        "registry write": "Set-ItemProperty -Path HKLM:\\SOFTWARE\\X",
        "auto-logon": "Winlogon",
        "stored password": "New-ScheduledTaskPrincipal -LogonType Password",
        "process kill": "Stop-Process -Id 1",
        "sign-in": "claude auth login",
        "live tree": "cd C:\\opt\\quant",
        "dynamic code": "& ('i' + 'ex') $x",
        "obfuscation": '$p."Ki`ll"()',
    }
    for what, probe in probes.items():
        assert re.search(BANNED[what], probe, flags=re.I), what


def test_one_watchdog_per_user() -> None:
    assert 'Mutex($false, "Local\\Claude-Bridge-Watchdog")' in WATCHDOG
    assert "WaitOne(0)" in WATCHDOG and "if (-not $owned) { exit 0 }" in WATCHDOG


def test_it_refuses_bytes_the_installer_did_not_pin() -> None:
    code = SCRIPTS["watchdog"]
    assert code.index("watchdog.sha256") < code.index("Start-Process -FilePath $claude")
    assert 'state = "TAMPERED"' in code


def test_adoption_is_narrow_and_cannot_hang_the_bridge() -> None:
    code = SCRIPTS["watchdog"]
    assert "Start-Job" in code and "Wait-Job -Job $job -Timeout 20" in code
    cim = code[code.index("function Find-NamedServer") : code.index("function Wait-Server")]
    assert "--name" in cim and "GetOwner" in cim
    assert code.count("Get-CimInstance") == 1  # only inside the timed job


def test_it_restarts_on_exit_with_backoff_and_a_live_heartbeat() -> None:
    code = SCRIPTS["watchdog"]
    assert "while ($true)" in code and "WaitForExit(60000)" in code
    assert "$null = $p.Handle" in code and "$null = $proc.Handle" in code
    assert "[Math]::Min(" in code and "900" in code
    assert "Wait-Beating 1800" in code  # sign-in failures back off, never spin


def test_every_wait_keeps_the_heartbeat_fresh() -> None:
    code = SCRIPTS["watchdog"]
    # the only sleep is Wait-Beating's, at most 60 s, with a beat before each chunk
    assert re.findall(r"Start-Sleep[^\n]*", code) == [
        "Start-Sleep -Seconds ([Math]::Min(60, $left))"
    ]
    wb = code[code.index("function Wait-Beating") : code.index("function Get-OwnDebug")]
    assert wb.index("Beat $f") < wb.index("Start-Sleep")
    assert '"next_at"' in wb and '"next_in_s"' in wb


def test_the_backoff_has_a_floor_and_a_ceiling() -> None:
    code = SCRIPTS["watchdog"]
    assert "$backoff = 30\n" in code
    waits = re.findall(r"Wait-Beating (\S+)", code)
    assert waits and all(w in ("$backoff", "10", "1800") for w in waits), waits
    assert code.count("[Math]::Max($backoff, 30) * 2, 900)") == 2
    assert "$backoff = 10" in code  # only after a run of 5 min or more
    assert "[Math]::Max($seconds, 1)" in code


def test_the_watchdog_refuses_unsafe_folders_before_it_writes() -> None:
    code = SCRIPTS["watchdog"]
    first_write = min(code.index("function Log"), code.index("function Beat"))
    assert code.index("Assert-SafeFolders\n") < first_write
    assert "New-Item" not in code  # it never creates the folders the installer locks
    unsafe = code[
        code.index("function Get-UnsafeReason") : code.index("function Assert-SafeFolders")
    ]
    assert "ReparsePoint" in unsafe and ".Parent" in unsafe and "Get-ChildItem" in unsafe
    assert "S-1-5-32-544" in code and "S-1-5-18" in code and "0x50000000" in code
    loop = code[code.index("while ($true) {\n    Assert-SafeFolders") :]
    assert loop  # re-checked every pass
    assert "Assert-SafeFolders" in code[code.index("function Wait-Server") :]


def test_a_server_found_again_is_still_measured() -> None:
    code = SCRIPTS["watchdog"]
    assert "debug = $debug }" in code  # the pid file carries the debug path
    assert "--debug-file" in code[code.index("function Find-NamedServer") :]
    assert "ToUniversalTime().Ticks" in code  # start time compared under 5.1 and 7 alike
    own = code[code.index("function Get-OwnDebug") : code.index("function Get-TrackedServer")]
    assert "rc_debug_" in own and "GetFullPath($LogDir)" in own


def test_sign_in_is_decided_by_logged_in_not_by_an_exit_code() -> None:
    code = SCRIPTS["watchdog"]
    si = code[code.index("function Test-SignedIn") : code.index("function Remove-OldDebugFiles")]
    assert "$j.loggedIn" in si and '$rc.Trim() -ne "0"' not in si


def test_the_reader_trusts_nothing_the_heartbeat_says_about_itself() -> None:
    code = SCRIPTS["status"]
    assert "Get-FileHash -LiteralPath $copy" in code
    assert code.index('"UNSAFE:') < code.index('"TAMPERED:') < code.index('"STALE:')
    assert "3 * $every" in code and "beat_every_s" in code
    assert code.index('"STALE:') < code.index('"$($b.state):')
    assert '"UNMEASURED:' in code and '"DEGRADED:' in code


def test_the_installer_locks_both_folders_and_writes_fresh_files() -> None:
    code = SCRIPTS["installer"]
    assert "Lock-Folder $BinDir\n" in code and "Lock-Folder $LogDir -UsersRead" in code
    lock = code[code.index("function Lock-Folder") : code.index("Lock-Folder $BinDir\n")]
    assert "/reset /T /C" in lock and "ReparsePoint" in lock and "-Recurse" in lock
    assert code.index("Remove-Item -LiteralPath $dst, $pinFile") < code.index(
        "Copy-Item -Path $src"
    )
    assert '-LogDir "{2}"' in code


def test_sign_in_is_judged_from_this_run_only() -> None:
    code = SCRIPTS["watchdog"]
    assert 'rc_debug_{0}.log" -f (Get-Date).ToUniversalTime().ToString("yyyyMMdd_HHmmss")' in code
    assert "auth status" in code


def test_rc_args_are_the_bridge_and_nothing_more() -> None:
    m = re.search(r"\$rcArgs = @\((.*?)\)", WATCHDOG, re.S)
    assert m is not None
    args = re.findall(r'"([^"]+)"|\$(\w+)', m.group(1))
    flat = [a or f"${b}" for a, b in args]
    assert flat == [
        "remote-control",
        "--spawn",
        "$SpawnMode",
        "--no-create-session-in-dir",
        "--name",
        "$Name",
        "--debug-file",
        "$debug",
    ]
    same_dir = WATCHDOG[m.end() : m.end() + 200]
    assert 'if ($SpawnMode -eq "same-dir") { $rcArgs += @("--capacity", "1") }' in same_dir


def test_installer_locks_the_folder_it_runs_from_and_pins_the_copy() -> None:
    code = SCRIPTS["installer"]
    assert "/inheritance:r" in code and "S-1-5-32-544" in code and "S-1-5-18" in code
    assert code.index("icacls") < code.index("Copy-Item -Path $src -Destination $dst")
    assert "watchdog.sha256" in code
    assert '$RunLevel = "Highest"' in code


def test_installer_rearms_and_registers_one_interactive_task() -> None:
    code = SCRIPTS["installer"]
    assert "-AtLogOn" in code and "-RepetitionInterval (New-TimeSpan -Minutes 5)" in code
    assert "-MultipleInstances IgnoreNew" in code
    assert "-ExecutionTimeLimit (New-TimeSpan -Seconds 0)" in code
    assert code.count("Register-ScheduledTask ") == 1
    assert "-LogonType Interactive" in code


def test_the_heartbeat_has_a_reader_and_the_task_is_in_the_manifest() -> None:
    assert "bridge_watchdog.json" in STATUS and "exit 0" in STATUS
    for verdict in (
        "LIVE",
        "STALE",
        "TAMPERED",
        "ABSENT",
        "QUIET",
        "DEAD_SERVER",
        "UNSAFE",
        "UNMEASURED",
        "DEGRADED",
    ):
        assert f'"{verdict}:' in STATUS, verdict
    manifest = (ROOT / "desks/mt5/ops/box_tasks.manifest").read_text(encoding="utf-8")
    assert 'name="Claude-Bridge-Watchdog"' in manifest
    assert 'installer="ops/bridge/install_bridge_watchdog.ps1"' in manifest


# ------------------------------------------------------------------------------- v1.3 (audit v1.2)
def test_the_call_operator_only_runs_what_it_names() -> None:
    """A command name held in a variable is any command: only these targets may follow `&`."""
    allowed = {"watchdog": {"$c", "$g"}, "installer": {"icacls.exe"}, "status": set()}
    # and a variable target runs only inside its own job, on what the job was handed (audit v1.5)
    code = SCRIPTS["watchdog"]
    assert sorted(m.group(0) for m in re.finditer(r"&\s*\$[cg]\b[^\n]*", code)) == [
        '& $c auth status 2>&1 | Out-String; "$LASTEXITCODE|$o" }',
        "& $g -C $d rev-parse --git-dir 2>&1 | Out-String }",
    ]
    assert not re.search(r"\$[cg]\s*=(?!=)", code)
    for script, code in SCRIPTS.items():
        targets = set(re.findall(r"(?<![\w&>-])&\s*(\S+)", code))
        assert targets <= allowed[script], (script, targets - allowed[script])


def test_the_installer_grants_only_admins_system_and_users_read() -> None:
    code = SCRIPTS["installer"]
    # OWNER RIGHTS (S-1-3-4) only ever read-only, and only on the checkout and its .git
    assert set(re.findall(r"\*(S-1-[\d-]+):", code)) <= {
        "S-1-5-32-544",
        "S-1-5-18",
        "S-1-5-32-545",
        "S-1-3-4",
    }
    assert re.findall(r"\*S-1-3-4:\(([^)]*)\)", code) == ["RX"]
    assert "*S-1-5-32-545:(OI)(CI)RX" in code
    for bad in ("Everyone", "Authenticated Users", "S-1-1-0", "S-1-5-11", "/grant ", "(M)", ":M"):
        assert bad not in code, bad
    assert code.count("& icacls.exe $dir /inheritance:r /grant:r @grants") == 1


def test_every_wait_rechecks_the_folders() -> None:
    code = SCRIPTS["watchdog"]
    for fn, nxt in (
        ("function Wait-Server", "$Refused = "),
        ("function Wait-Beating", "function Get-OwnDebug"),
    ):
        body = code[code.index(fn) : code.index(nxt)]
        assert "Assert-SafeFolders" in body, fn


def test_only_a_state_written_before_exit_promises_the_re_arm_interval() -> None:
    code = SCRIPTS["watchdog"]
    hits = [m.start() for m in re.finditer(r"beat_every_s = 300", code)]
    assert len(hits) == 3
    for at in hits:
        assert re.search(r"\bexit [23]\b", code[at : at + 40]), code[at - 80 : at + 40]
    assert '$script:State["beat_every_s"] = 60' in code


def test_bin_and_logs_live_under_an_admin_only_root_and_every_parent_is_checked() -> None:
    code, inst = SCRIPTS["watchdog"], SCRIPTS["installer"]
    assert '$LogDir = "C:\\ProgramData\\ClaudeBridge\\logs"' in code
    assert '$Root = "C:\\ProgramData\\ClaudeBridge"' in inst
    assert inst.index("Lock-Folder $Root -UsersRead") < inst.index("Lock-Folder $BinDir\n")
    walk = code[code.index("function Get-UnsafeReason") : code.index("function Assert-SafeFolders")]
    assert "Get-AclProblem $walk.FullName $ParentMask" in walk
    acl = code[code.index("function Get-AclProblem") : code.index("function Get-UnsafeReason")]
    assert "InheritOnly" in acl and "$owners" in acl
    assert "TakeOwnership" in code[code.index("$ParentMask") :]
    assert "C:\\opt\\bridge\\bin" not in code + inst + SCRIPTS["status"]


def test_the_checkout_is_locked_and_its_risk_reported_never_fatal() -> None:
    code, inst, status = SCRIPTS["watchdog"], SCRIPTS["installer"], SCRIPTS["status"]
    risk = code[code.index("function Get-CheckoutRisk") : code.index("function Wait-Beating")]
    assert ".git\\hooks" in risk and ".claude" in risk and "exit" not in risk
    assert "checkout_risk = (Get-CheckoutRisk)" in code
    assert '"LIVE_CHECKOUT_AT_RISK: $($b.checkout_risk); $detail"; exit 2' in status
    assert "Lock-Folder (Split-Path -Parent $Checkout) -UsersRead -KeepOwner" in inst


def test_degraded_is_a_count_over_ten_minutes_of_new_lines() -> None:
    code, status = SCRIPTS["watchdog"], SCRIPTS["status"]
    up = code[code.index("function Update-SessionErrors") : code.index("function Wait-Server")]
    assert "$fs.Seek($pos" in up and "AddMinutes(-10)" in up
    assert "$script:DebugPos[$debug] = $len" in up  # history in a new file is not counted
    assert "$SessionNoise" in up and "updateSessionTitle" in code
    assert "[int]$b.session_errors_10m -ge 3" in status


def test_the_reader_names_the_tasks_last_result() -> None:
    assert "Get-ScheduledTaskInfo -TaskName $TaskName" in SCRIPTS["status"]


# ------------------------------------------------------------------------------- v1.4 (audit v1.3)
def test_owners_and_generic_all_are_checked_on_every_folder() -> None:
    for script in ("watchdog", "status"):
        code = SCRIPTS[script]
        acl = code[code.index("function Get-AclProblem") : code.index("function Get-UnsafeReason")]
        assert 'if ($owner -notin $owners) { return "$path is owned by' in acl, script
        parent = code[code.index("$ParentMask = ") :].splitlines()[0]
        assert parent.endswith("-bor 0x10000000"), script  # GENERIC_ALL
        assert "TakeOwnership" in parent and "ChangePermissions" in parent and "Delete" in parent
        write = code[code.index("$WriteMask = ") :].splitlines()[0]
        assert write.endswith("-bor 0x50000000"), script  # GENERIC_WRITE | GENERIC_ALL


def test_a_root_someone_else_created_is_refused() -> None:
    inst = SCRIPTS["installer"]
    at = inst.index("foreach ($d in @($Root, $BinDir, $LogDir))")
    assert at < inst.index("Lock-Folder $Root -UsersRead")
    assert "throw" in inst[at : inst.index("Lock-Folder $Root -UsersRead")]


def test_a_new_debug_file_is_read_from_its_first_byte() -> None:
    code = SCRIPTS["watchdog"]
    assert 'Update-SessionErrors $debug ($by -eq "watchdog")' in code
    assert "$(if ($ours) { 0 } else { $len })" in code


# --------------------------------------------------------------- v1.5 (git refused the checkout)
def test_spawn_mode_defaults_to_same_dir_and_is_a_closed_set() -> None:
    for script in ("watchdog", "installer"):
        assert (
            '[ValidateSet("same-dir", "worktree")] [string] $SpawnMode = "same-dir"'
            in SCRIPTS[script]
        )
    assert "-SpawnMode {3}' -f $dst, $Checkout, $LogDir, $SpawnMode" in SCRIPTS["installer"]


def test_git_refusing_the_checkout_is_measured_and_reported() -> None:
    code, status, inst = SCRIPTS["watchdog"], SCRIPTS["status"], SCRIPTS["installer"]
    fn = code[code.index("function Get-GitRefusal") : code.index("function Wait-Beating")]
    assert "rev-parse --git-dir" in fn and "Wait-Job -Job $job -Timeout 60" in fn
    assert "dubious ownership" in fn and "-lt 300" in fn and "exit" not in fn
    assert "git_refusal = (Get-GitRefusal)" in code
    assert '"GIT_REFUSED: $($b.git_refusal); $detail"; exit 1' in status
    assert status.index("GIT_REFUSED:") < status.index("DEGRADED:")
    # the installer fixes it by ownership, never by git config
    assert '/setowner "*$me"' in inst and "safe.directory" not in inst and "git config" not in inst


def test_the_worktree_park_counts_toward_degraded() -> None:
    m = re.search(r"\$SessionError = '([^']+)'", WATCHDOG)
    assert m is not None
    pat = m.group(1)
    for line in (
        "Failed to create worktree for session abc: the protected checkout C:\\opt\\bridge\\quant "
        "has git metadata that could not be resolved",
        "fatal: detected dubious ownership in repository at 'C:/opt/bridge/quant'",
        "[child] session 12 exited with code 1",
    ):
        assert re.search(pat, line), line
    assert not re.search(pat, "updateSessionTitle ok") or "updateSessionTitle" in WATCHDOG


# ------------------------------------------------------------------- v1.6 (audit v1.4 + v1.5 HOLD)
def test_the_installer_refuses_a_checkout_beside_the_live_desk() -> None:
    inst = SCRIPTS["installer"]
    guard = inst.index("(Get-Item -LiteralPath $Checkout -Force -ErrorAction Stop).FullName")
    assert guard < inst.index("Lock-Folder $Root") and guard < inst.index("/setowner")
    assert "GetFullPath($Checkout)" not in inst  # text, not the file system, decided before
    for needle in (
        '$bridgeDir = Join-Path $env:SystemDrive "opt\\bridge"',
        "if ($parent -ine $bridgeDir) { throw",
        'if (-not (Test-Path -LiteralPath (Join-Path $Checkout ".git"))) { throw',
        '(Test-Path -LiteralPath (Join-Path $sib.FullName ".git"))',
    ):
        assert needle in inst, needle


def test_a_hand_started_uncapped_server_is_reported() -> None:
    code, status = SCRIPTS["watchdog"], SCRIPTS["status"]
    assert '--capacity\\s+"?1"?(\\s|$)' in code and 'Uncapped = ($open -eq "True")' in code
    assert "server_risk = $script:ServerRisk" in code
    assert '"LIVE_SERVER_AT_RISK: $($b.server_risk); $detail"; exit 2' in status


def test_a_root_or_folder_someone_else_owns_is_refused_exactly() -> None:
    inst = SCRIPTS["installer"]
    loop = inst[inst.index("foreach ($d in @($Root, $BinDir, $LogDir))") :]
    loop = loop[: loop.index("Lock-Folder $Root")]
    assert "if ($dOwner -notin @('S-1-5-32-544', 'S-1-5-18')) {" in loop and "throw" in loop
    # created with its ACL in one call, never created open and locked after
    create = inst[inst.index("if (-not (Test-Path -LiteralPath $Root))") : inst.index(loop[:20])]
    assert "SetAccessRuleProtection($true, $false)" in create
    assert "[System.IO.Directory]::CreateDirectory($Root, $sec)" in create
    assert "New-Item" not in create


def test_the_owner_change_is_not_recursive_and_owner_rights_are_read_only() -> None:
    inst = SCRIPTS["installer"]
    line = next(x for x in inst.splitlines() if '/setowner "*$me"' in x)
    assert "/T" not in line
    assert '& icacls.exe $d /grant:r "*S-1-3-4:(RX)" /C' in inst


def test_binaries_come_from_known_paths_first_and_their_folders_are_measured() -> None:
    code, status = SCRIPTS["watchdog"], SCRIPTS["status"]
    assert code.index("$env:ProgramFiles\\Git\\cmd\\git.exe") < code.index("Get-Command git")
    lookup = code[code.index("$script:Git = $null") : code.index("function Get-BinaryRisk")]
    assert lookup.index("foreach ($cand in") < lookup.index("if (-not $script:Git)")
    assert code.index(".local\\bin\\claude.exe") < code.index("Get-Command claude")
    assert "binary_risk = (Get-BinaryRisk)" in code
    assert '"LIVE_BINARY_AT_RISK: $($b.binary_risk); $detail"; exit 2' in status


def test_benign_failures_do_not_count_toward_degraded() -> None:
    m = re.search(r"\$SessionError = '([^']+)'", WATCHDOG)
    assert m is not None
    for line in (
        "MCP server github failed to start: spawn ENOENT",
        "Failed to start file watcher",
        "getaddrinfo: host api.example could not be resolved",
    ):
        assert not re.search(m.group(1), line), line


def _block(src: str, first: str, lines: int) -> list[str]:
    rows = src.splitlines()
    i = next(n for n, x in enumerate(rows) if x.strip() == first)
    return [x.strip() for x in rows[i : i + lines]]


def test_a_junction_anywhere_on_the_checkout_path_refuses_the_install() -> None:
    """Audit v1.7/v1.8 (K2, K4): the parent is reset recursively, so a junction must never be
    followed. The refusals are pinned whole, and ahead of every ACL, owner or reset call."""
    inst = SCRIPTS["installer"]
    assert _block(
        inst, "foreach ($p in @((Split-Path -Parent $bridgeDir), $bridgeDir, $Checkout)) {", 5
    ) == [
        "foreach ($p in @((Split-Path -Parent $bridgeDir), $bridgeDir, $Checkout)) {",
        "if ((Get-Item -LiteralPath $p -Force).Attributes -band "
        "[IO.FileAttributes]::ReparsePoint) {",
        'throw "$p is a junction or symlink; not installing"',
        "}",
        "}",
    ]
    assert inst.index("$Checkout)) {") < inst.index("function Lock-Folder")
    body = inst.split("function Lock-Folder", 1)[1].split("\n}\n", 1)[0]
    assert _block(body, "if (Test-Path -LiteralPath $dir) {", 6) == [
        "if (Test-Path -LiteralPath $dir) {",
        "foreach ($c in @(Get-ChildItem -LiteralPath $dir -Force -Recurse)) {",
        "if (-not ($c.Attributes -band [IO.FileAttributes]::ReparsePoint)) { continue }",
        'throw "$($c.FullName) is a junction or symlink; not installing"',
        "}",
        "}",
    ]
    scan = body.index("if (Test-Path -LiteralPath $dir) {")
    assert scan < min(body.index(k) for k in ("New-Item", "icacls.exe", "/setowner", "/reset"))
    # audit v1.9: a second, identical scan after the lock and right before the recursive reset
    loop = "foreach ($c in @(Get-ChildItem -LiteralPath $dir -Force -Recurse)) {"
    rows = [x.strip() for x in body.splitlines()]
    at = [n for n, x in enumerate(rows) if x == loop]
    assert len(at) == 2
    assert rows[at[1] : at[1] + 4] == [
        loop,
        "if (-not ($c.Attributes -band [IO.FileAttributes]::ReparsePoint)) { continue }",
        'throw "$($c.FullName) is a junction or symlink; not installing"',
        "}",
    ]
    lock = next(n for n, x in enumerate(rows) if "/inheritance:r" in x)
    reset = next(n for n, x in enumerate(rows) if "/reset" in x)
    assert lock < at[1] < reset
    assert (
        "Write-Warning" not in body and body.count("$KeepOwner") == 2
    )  # its declaration and /setowner


def test_an_uncapped_adopted_server_sets_the_risk() -> None:
    """Mutation J1: the flag must be acted on, by the loop that adopts a hand-started server."""
    assert _block(SCRIPTS["watchdog"], "$existing = Find-NamedServer", 3) == [
        "$existing = Find-NamedServer",
        "if ($existing -and $existing.Uncapped) {",
        '$script:ServerRisk = "adopted server pid $($existing.Proc.Id) shares its checkout '
        'without --capacity 1 (R0423); stop it once and this watchdog starts a capped one"',
    ]
    loop = SCRIPTS["watchdog"].split("while ($true) {", 1)[1]
    assert loop.index("$script:ServerRisk = $null") < loop.index("$existing.Uncapped")


@pytest.mark.parametrize(
    ("cmd", "uncapped"),
    [
        ("claude remote-control --spawn same-dir --capacity 1", False),
        ('claude remote-control --spawn same-dir --capacity "1"', False),
        ("claude remote-control --spawn worktree", False),
        ("claude remote-control --spawn same-dir", True),
        ("claude remote-control --spawn same-dir --capacity 12", True),
        ("claude remote-control", True),
    ],
)
def test_the_uncapped_flag_means_what_it_says(cmd: str, uncapped: bool) -> None:
    """Mutation J1: the flag the risk verdict reads is pinned by behaviour, not by spelling."""
    line = next(x for x in SCRIPTS["watchdog"].splitlines() if "$open = (" in x)
    pats = re.findall(r"-notmatch '([^']+)'", line)
    assert len(pats) == 2 and line.count("-notmatch") == 2 and " -and " in line
    assert (not any(re.search(p, cmd) for p in pats)) is uncapped
