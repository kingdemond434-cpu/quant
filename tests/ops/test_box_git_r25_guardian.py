"""Boot r25b: the box guardian, phase 1 (read-only status). These tests pin its powers, as Audit
asked on 2026-11-27 21:27Z: it writes exactly one file (guard_status.log, through Write-Status),
and it never changes an ACL, a task, the trust set, the guard's interpreter, any approval or
verdict, or anything under the live tree."""
from __future__ import annotations

import fnmatch
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GUARDIAN = ROOT / "ops" / "box_git" / "box_guardian.ps1"
RAW = GUARDIAN.read_bytes()
TEXT = RAW.decode("ascii")


def _body_without_comments() -> str:
    s = re.sub(r"<#.*?#>", "", TEXT, flags=re.S)
    return "\n".join(line.split("#", 1)[0] if not line.lstrip().startswith("#") else ""
                     for line in s.splitlines())


def _write_status_span(code: str, fn: str = "Write-Status") -> tuple[int, int]:
    start = code.index(f"function {fn}")
    depth, i = 0, code.index("{", start)
    for j in range(i, len(code)):
        if code[j] == "{":
            depth += 1
        elif code[j] == "}":
            depth -= 1
            if depth == 0:
                return start, j
    raise AssertionError("Write-Status has no closing brace")


def test_ascii_crlf_for_windows_powershell() -> None:
    assert RAW.isascii()
    assert b"\r\n" in RAW and b"\n" not in RAW.replace(b"\r\n", b"")


def test_trust_set_lists_the_guardian() -> None:
    t = json.loads((ROOT / "ops" / "box_git" / "TRUST_SET.json").read_text(encoding="utf-8"))
    rel = "ops/box_git/box_guardian.ps1"
    assert any(fnmatch.fnmatch(rel, g) for g in t["files"])
    assert any(fnmatch.fnmatch("ops/box_git/guardian/x.ps1", g) for g in t["files"])


BARRED = [
    r"\bSet-Content\b", r"\bAdd-Content\b", r"\bOut-File\b", r"\bNew-Item\b",
    r"\bRemove-Item\b(?!\s+Env:)",
    r"\bMove-Item\b", r"\bCopy-Item\b", r"\bRename-Item\b", r"\bicacls\b", r"\bSet-Acl\b",
    r"\bSet-ScheduledTask\b", r"\bRegister-ScheduledTask\b", r"\bUnregister-ScheduledTask\b",
    r"\bStart-ScheduledTask\b", r"\bStop-ScheduledTask\b", r"\bDisable-ScheduledTask\b",
    r"\bEnable-ScheduledTask\b", r"\bschtasks\b", r"\bStart-Process\b", r"\bStop-Process\b",
    r"\bInvoke-Expression\b", r"\biex\b", r"\bgit\b", r"\btakeown\b", r"\bRestart-Service\b",
    r"\bStop-Service\b", r"\bSet-ItemProperty\b", r"\bNew-ItemProperty\b", r"\bExpand-Archive\b",
    r"WriteAllText", r"WriteAllBytes", r"WriteAllLines", r"AppendAllText", r"\[IO\.File\]::Create",
    r"\[IO\.File\]::(Move|Copy|Delete|Replace)", r"\bSetAccessControl\b",
    r"(?<![0-9])>(?!&)",  # a redirection to a file (2>&1 is a stream merge; -gt is spelled out)
]


#: each allowed primitive, and the one function it may appear in
ALLOWED_IN = {
    r"WriteAllText": "Write-Status", r"AppendAllText": "Write-Status",
    r"\[IO\.File\]::Create": "New-AdminFile",
    r"\bStart-ScheduledTask\b": "Start-Declared",
    r"\bgit\b": "Get-BootFile",
}


def _strip_fns(code: str, names: list[str]) -> str:
    for n in names:
        a, b = _write_status_span(code, n)
        code = code[:a] + code[b + 1:]
    return code


def test_no_write_outside_write_status() -> None:
    code = _body_without_comments()
    outside = _strip_fns(code, ["Write-Status", "New-AdminFile", "Start-Declared", "Get-BootFile"])
    for pat in BARRED:
        # quoted strings are log text or paths, not commands; stream merges are not redirects
        strip = r"'[^']*'|\"[^\"]*\"|2>\$null|2>&1"
        lines = [re.sub(strip, "", ln) for ln in outside.splitlines()]
        hits = [ln for ln in lines if re.search(pat, ln)]
        assert not hits, f"{pat} outside its one allowed function: {hits}"
    # and each allowed primitive appears only in its own function
    for pat, fn in ALLOWED_IN.items():
        others = _strip_fns(code, [fn])
        lines = [re.sub(r"'[^']*'|\"[^\"]*\"", "", ln) for ln in others.splitlines()]
        assert not [ln for ln in lines if re.search(pat, ln)], f"{pat} outside {fn}"


def test_write_status_refuses_any_other_path_and_targets_the_log() -> None:
    code = _body_without_comments()
    a, b = _write_status_span(code)
    body = code[a:b]
    assert "if (@($Status, $Health) -notcontains $path) { throw" in body
    assert "$Status = Join-Path $LogDir 'guard_status.log'" in TEXT
    assert "$Health = Join-Path $LogDir 'task_health.json'" in TEXT
    assert "$LogDir = Join-Path $Q 'logs'" in TEXT
    assert "$Q      = 'C:\\ProgramData\\QuantBox'" in TEXT
    # every Write-Status call passes $Status, and only Say calls it
    calls = re.findall(r"Write-Status\s+(\S+)", code)
    assert calls and all(c in ("$Status", "$Health") for c in calls if c != "([string]")


def test_no_link_writes_as_system() -> None:
    assert "ReparsePoint" in TEXT and "hardlink list" in TEXT
    assert "if (-not (Test-PlainFile $path)) { return }" in TEXT
    # a log a non-admin pre-created or can write is neither appended to nor trusted for the
    # hourly throttle (Audit 21:40Z)
    assert "return (Test-AdminFile $p)" in TEXT
    assert "(Test-Path -LiteralPath $Status) -and (Test-AdminFile $Status)" in TEXT


def test_never_logs_an_environment_value() -> None:
    for ln in TEXT.splitlines():
        if re.search(r"\bSay\b", ln):
            assert "$env:" not in ln, ln
            assert "GetEnvironmentVariable" not in ln, ln


def test_runs_only_the_pinned_python_probe() -> None:
    code = _body_without_comments()
    invokes = re.findall(r"&\s+(\S+)", code)
    # & $py -c $code (the probe) and & fsutil (hardlink list); dot-source of the guard's git_acl
    assert set(invokes) <= {"$py", '"$env:SystemRoot\\System32\\fsutil.exe"', "git"}, invokes
    gits = re.findall(r"&\s+git\b[^\n]*", code)
    assert len(gits) == 1 and " show " in gits[0] and "core.hooksPath=NUL" in gits[0], gits
    assert "& $py -c $code" in code
    assert ". (Join-Path $tree 'ops\\box_git\\runas\\git_acl.ps1')" in code


def test_status_hourly_health_every_pass_and_always_exits_zero() -> None:
    assert "TotalMinutes -lt 55) { $doStatus = $false }" in TEXT
    assert "if ($doStatus) { Invoke-Status }" in TEXT
    assert "try { Invoke-Health } catch" in TEXT
    assert TEXT.rstrip().endswith("exit 0")
    assert TEXT.count("exit 0") == 1


# ---- phase 3 bounds (Audit 21:52Z) --------------------------------------------------------

DECL = json.loads((ROOT / "ops" / "box_git" / "guardian" / "task_outputs.json").read_text("utf-8"))


def test_task_control_is_start_stop_only_by_exact_name() -> None:
    code = _body_without_comments()
    a, b = _write_status_span(code, "Start-Declared")
    body = code[a:b]
    assert "Start-ScheduledTask -TaskName $name" in body
    for bad in ("Enable-ScheduledTask", "Set-ScheduledTask", "Register-ScheduledTask",
                "New-ScheduledTaskPrincipal", "-Principal", "-Action", "-Trigger", "-Settings"):
        assert bad not in body, bad
    # the task name passed to the cmdlets is never a glob
    assert not re.search(r"ScheduledTask\s+-TaskName\s+['\"][^'\"]*[*?]", body)
    assert "$byName[$name]" in code   # rows are found by exact name, never by pattern


def test_guard_tasks_and_movers_are_alarm_only_in_code() -> None:
    m = re.search(r"\$NeverRestart = @\(([^)]*)\)", TEXT)
    assert m
    names = set(re.findall(r"'([^']+)'", m.group(1)))
    assert {"QuantGuard-RunAs", "QuantForge-BootMove", "QuantForge-Pin", "MT5-AdoptRelease"} <= names
    assert TEXT.count("$name -like 'QuantGuard-*'") == 2
    code = _body_without_comments()
    a, b = _write_status_span(code, "Start-Declared")
    assert "throw" in code[a:b]


def test_defers_to_the_runas_migrator_and_rate_limits() -> None:
    assert "@('WAIT_WINDOW', 'MOVED', 'WATCH') -contains" in TEXT
    assert "elseif ($busy) { $why = 'run-as migrator busy' }" in TEXT
    assert "elseif ($restartedThisPass) { $why = 'one restart per pass' }" in TEXT
    assert "[int]$row.fails -ge 2) { $row.verdict = 'ALARM' }" in TEXT
    assert "-not $row.last_restart" in TEXT          # one restart per max-age window


def test_gateway_is_start_only_when_dead_and_outside_rollover() -> None:
    assert "(Get-BrokerHour) -eq 0) { $why = 'broker rollover hour' }" in TEXT
    assert "Start-Declared $name" in TEXT
    gw = [r for r in DECL["tasks"] if r["task"] == "MT5-GatewayResident"][0]
    assert gw["restart"] == "auto_dead_only"


def test_declarations_cover_the_census_and_money_defaults_to_alarm() -> None:
    rows = DECL["tasks"]
    assert len(rows) == len({r["task"] for r in rows}) == 134
    for r in rows:
        assert r["restart"] in ("auto", "alarm", "auto_dead_only")
        assert not any(ch in r["task"] for ch in "*?[")
        if r["money_path"] and r["task"] != "MT5-GatewayResident":
            assert r["restart"] == "alarm", r["task"]
        if r["max_age_min"] and r["interval_min"]:
            assert r["max_age_min"] >= max(3 * r["interval_min"], r["interval_min"] + 30) or \
                r["task"] == "QuantForge-Loop"
    for n in ("E8-Executor", "MT5-FTMO-Executor", "MT5-ShadowSync", "MT5-LawGate", "MT5-CycleNoon",
              "MT5-AllocatorFast", "MT5-FTMO-Allocator"):
        assert [r for r in rows if r["task"] == n][0]["restart"] == "alarm", n


def test_declarations_are_read_from_the_boot_never_a_writable_file() -> None:
    assert "show \"${boot}:$rel\"" in TEXT
    assert "if (@('ops/box_git/guardian/task_outputs.json', 'ops/money_closure.txt') -notcontains $rel) { throw" in TEXT
    t = json.loads((ROOT / "ops" / "box_git" / "TRUST_SET.json").read_text(encoding="utf-8"))
    assert any(fnmatch.fnmatch("ops/box_git/guardian/task_outputs.json", g) for g in t["files"])


# ---- r25c.1: Audit HOLD 22:01Z (MF1..MF4) --------------------------------------------------

def _rs():
    import importlib.util
    spec = importlib.util.spec_from_file_location("replay_shadow", ROOT / "ops/release/replay_shadow.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


#: a script that can reach anything at run time: static imports prove nothing about it
DISPATCH = re.compile(r"\bsubprocess\b|\bPopen\b|os\.system|\brunpy\b|\bimportlib\b|__import__|\bexec\(")
#: acting on the box itself: reboot, kill, re-register, clock, ACL, git ref, signing (MF2)
DANGER = re.compile(
    r"shutdown|Restart-Computer|os\.kill|\.kill\(|\.terminate\(|taskkill|schtasks|ScheduledTask"
    r"|w32tm|Set-Date|SetSystemTime|icacls|Set-Acl|SetAccessControl|takeown|signtool"
    r"|AuthenticodeSignature|update-ref|\bgit\b[^\n]{0,40}\b(push|reset|commit|checkout|branch|tag)\b"
    r"|[\"'](push|reset|commit|checkout|update-ref)[\"']",
    re.IGNORECASE)


def money_and_why(row: dict, rs=None, files: set[str] | None = None) -> tuple[bool, str]:
    """MF3, mechanical: rebuild a row's money_path from the scripts its live action runs. Fail
    closed: anything this cannot follow is money."""
    rs = rs or _rs()
    files = files if files is not None else rs.tree_files(ROOT)
    closure = {x.strip().lower() for x in (ROOT / "ops/money_closure.txt").read_text("utf-8").splitlines()
               if x.strip() and not x.startswith("#")}
    if not row.get("action_sha256"):
        return True, "action unread"
    scripts = row.get("action_scripts") or []
    if not scripts:
        return True, "no script named"
    for s in scripts:
        if not s.endswith(".py") or s not in files:
            return True, f"{s}: not a repository .py file"
        if s.startswith(rs.MONEY_PATH) or s in rs.ENTRY_POINTS or s.lower() in closure:
            return True, f"{s}: on the money path"
        if rs.MONEY_WORDS.search(s):
            return True, f"{s}: venue word"
        if DISPATCH.search(rs.read(ROOT, s) or ""):
            return True, f"{s}: dispatches at run time"
        reach = rs.import_closure(ROOT, (s,)) & set(rs.ENTRY_POINTS)
        if reach:
            return True, f"{s}: imports {sorted(reach)[0]}"
    return False, "off the money path"


def acts_on_box(row: dict, rs=None) -> str:
    rs = rs or _rs()
    for s in row.get("action_scripts") or []:
        for f in sorted(rs.import_closure(ROOT, (s,)) | {s}):
            m = DANGER.search(rs.read(ROOT, f) or "")
            if m:
                return f"{f}: {m.group(0)}"
    return ""


def test_never_stops_a_task_and_starts_only_a_ready_one() -> None:
    code = _body_without_comments()
    assert "Stop-ScheduledTask" not in code
    a, b = _write_status_span(code, "Start-Declared")
    body = code[a:b]
    assert "-ne 'Ready') { throw" in body
    assert "if ($row.verdict -eq 'STALE' -and \"$($t.State)\" -eq 'Running') { $row.verdict = 'HUNG' }" in TEXT
    assert "elseif (\"$($t.State)\" -ne 'Ready') { $why = \"task is $($t.State)\" }" in TEXT


def test_alarm_is_the_code_default() -> None:
    assert "if (@('auto', 'auto_dead_only') -notcontains $mode) { $mode = 'alarm' }" in TEXT
    assert "elseif ($d.money_path -and $name -ne 'MT5-GatewayResident') { $mode = 'alarm' }" in TEXT
    assert "elseif (\"$($d.action_sha256)\" -ne $row.action_sha256) { $mode = 'alarm'" in TEXT
    assert "elseif ($mode -eq 'auto' -and (Test-MoneyAction $live @($d.action_scripts) $closure)) { $mode = 'alarm' }" in TEXT
    assert "elseif ($mode -eq 'auto_dead_only' -and $name -ne 'MT5-GatewayResident') { $mode = 'alarm' }" in TEXT
    # a row with no outputs is never restarted
    assert "if (-not $d -or -not @($d.outputs | Where-Object { $_ }).Count) {" in TEXT


AUDIT_BOX_ACTING = {"MT5-RebootDrill", "MT5-ReapGitWriters", "MT5-ClockFixer", "MT5-ProcessHealth",
                    "MT5-Healers", "MT5-IdentityHealer", "MT5-PlumbingWatchdog",
                    "MT5-MoatRecorder-Watchdog", "MT5-FetchUniverse-Repair", "MT5-SshGuard",
                    "Quant-CpuShaper", "Claude-Bridge-Watchdog", "Quant-SignTrain"}


def test_box_acting_tasks_are_alarm_in_code_and_in_the_declarations() -> None:
    m = re.search(r"\$NeverRestart = @\(([^)]*)\)", TEXT)
    assert m
    assert AUDIT_BOX_ACTING <= set(re.findall(r"'([^']+)'", m.group(1)))
    rows = {r["task"]: r for r in DECL["tasks"]}
    for n in AUDIT_BOX_ACTING:
        assert rows[n]["restart"] == "alarm", n


def test_money_path_is_rebuilt_from_the_actions_and_no_auto_row_acts_on_the_box() -> None:
    rs = _rs()
    files = rs.tree_files(ROOT)
    for r in DECL["tasks"]:
        money, why = money_and_why(r, rs, files)
        assert r["money_path"] == money, (r["task"], why)
        if r["restart"] == "auto":
            assert not money, (r["task"], why)
            assert not acts_on_box(r, rs), (r["task"], acts_on_box(r, rs))
            assert r["outputs"], r["task"]


def test_guardian_money_lists_match_replay_shadow() -> None:
    rs = _rs()
    def arr(name: str) -> tuple[str, ...]:
        m = re.search(r"\$" + name + r" = @\(([^)]*)\)", TEXT)
        assert m, name
        return tuple(re.findall(r"'([^']+)'", m.group(1)))
    assert arr("MoneyPrefixes") == rs.MONEY_PATH
    assert arr("MoneyEntries") == rs.ENTRY_POINTS
    m = re.search(r"\$MoneyWords = '([^']+)'", TEXT)
    assert m and m.group(1) == rs.MONEY_WORDS.pattern


def test_gateway_start_needs_no_live_gateway_process() -> None:
    code = _body_without_comments()
    a, b = _write_status_span(code, "Test-GatewayAlive")
    body = code[a:b]
    assert "Win32_Process" in body and "-OperationTimeoutSec 20" in body
    assert "gateway_resident|run_gateway_loop" in body
    assert "if ($null -eq $p.CommandLine) { return $true }" in body
    assert "} catch { return $true }" in body
    assert "elseif ($mode -eq 'auto_dead_only' -and (Test-GatewayAlive)) { $why =" in TEXT
