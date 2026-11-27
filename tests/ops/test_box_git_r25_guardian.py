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


def _write_status_span(code: str) -> tuple[int, int]:
    start = code.index("function Write-Status")
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


def test_no_write_outside_write_status() -> None:
    code = _body_without_comments()
    a, b = _write_status_span(code)
    outside = code[:a] + code[b + 1:]
    for pat in BARRED:
        # quoted strings are log text or paths, not commands; stream merges are not redirects
        strip = r"'[^']*'|\"[^\"]*\"|2>\$null|2>&1"
        lines = [re.sub(strip, "", ln) for ln in outside.splitlines()]
        hits = [ln for ln in lines if re.search(pat, ln)]
        assert not hits, f"{pat} outside Write-Status: {hits}"


def test_write_status_refuses_any_other_path_and_targets_the_log() -> None:
    code = _body_without_comments()
    a, b = _write_status_span(code)
    body = code[a:b]
    assert 'if ($path -ne $Status) { throw' in body
    assert "$Status = Join-Path $LogDir 'guard_status.log'" in TEXT
    assert "$LogDir = Join-Path $Q 'logs'" in TEXT
    assert "$Q      = 'C:\\ProgramData\\QuantBox'" in TEXT
    # every Write-Status call passes $Status, and only Say calls it
    calls = re.findall(r"Write-Status\s+(\S+)", code)
    assert calls and all(c == "$Status" for c in calls if c != "([string]")


def test_no_link_writes_as_system() -> None:
    assert "ReparsePoint" in TEXT and "hardlink list" in TEXT
    assert "if (-not (Test-PlainFile $Status)) { return }" in TEXT
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
    assert set(invokes) <= {"$py", '"$env:SystemRoot\\System32\\fsutil.exe"'}, invokes
    assert "& $py -c $code" in code
    assert ". (Join-Path $tree 'ops\\box_git\\runas\\git_acl.ps1')" in code


def test_throttled_to_hourly_and_always_exits_zero() -> None:
    assert "TotalMinutes -lt 55) { exit 0 }" in TEXT
    assert TEXT.rstrip().endswith("exit 0")
