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
    r"\bStart-ScheduledTask\b": "Restart-Declared", r"\bStop-ScheduledTask\b": "Restart-Declared",
    r"\bgit\b": "Get-Declarations",
}


def _strip_fns(code: str, names: list[str]) -> str:
    for n in names:
        a, b = _write_status_span(code, n)
        code = code[:a] + code[b + 1:]
    return code


def test_no_write_outside_write_status() -> None:
    code = _body_without_comments()
    outside = _strip_fns(code, ["Write-Status", "New-AdminFile", "Restart-Declared", "Get-Declarations"])
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
    a, b = _write_status_span(code, "Restart-Declared")
    body = code[a:b]
    assert "Start-ScheduledTask -TaskName $name" in body
    assert "Stop-ScheduledTask -TaskName $name" in body
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
    a, b = _write_status_span(code, "Restart-Declared")
    assert "throw" in code[a:b]


def test_defers_to_the_runas_migrator_and_rate_limits() -> None:
    assert "@('WAIT_WINDOW', 'MOVED', 'WATCH') -contains" in TEXT
    assert "elseif ($busy) { $why = 'run-as migrator busy' }" in TEXT
    assert "elseif ($restartedThisPass) { $why = 'one restart per pass' }" in TEXT
    assert "[int]$row.fails -ge 2) { $row.verdict = 'ALARM' }" in TEXT
    assert "-not $row.last_restart" in TEXT          # one restart per max-age window


def test_gateway_is_start_only_when_dead_and_outside_rollover() -> None:
    assert "auto_dead_only' -and $running) { $why = 'alive but stale" in TEXT
    assert "(Get-BrokerHour) -eq 0) { $why = 'broker rollover hour' }" in TEXT
    assert "Restart-Declared $name $running ($mode -eq 'auto_dead_only')" in TEXT
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
    assert "show \"${boot}:ops/box_git/guardian/task_outputs.json\"" in TEXT
    t = json.loads((ROOT / "ops" / "box_git" / "TRUST_SET.json").read_text(encoding="utf-8"))
    assert any(fnmatch.fnmatch("ops/box_git/guardian/task_outputs.json", g) for g in t["files"])
