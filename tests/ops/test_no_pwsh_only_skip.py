"""Prevention for Audit 2026-11-25 (train 1b condition e): three PowerShell tests skipped on the
box because they gated on pwsh 7 alone, while every box script runs under Windows PowerShell 5.1.
A skip on the box is not a test. Any test that needs PowerShell must fall back to powershell.exe,
and must prefer it over pwsh, or a later pwsh install would move the tests to a shell the box's
scripts never run under."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_DIRS = ("tests", "desks/mt5/tests", "desks/mt5/research/tests")
_PWSH_ONLY_SKIP = re.compile(r"skipif\([^)]*which\(\s*[\"']pwsh[\"']\s*\)(?![^)]*powershell)")
_PWSH_LITERAL_ARGV = re.compile(r"\[\s*[\"']pwsh[\"']\s*,")
_PWSH_FIRST = re.compile(
    r"which\(\s*[\"']pwsh[\"']\s*\)\s*or\s*(?:shutil\.)?which\(\s*[\"']powershell"
)
_RULES = (_PWSH_ONLY_SKIP, _PWSH_LITERAL_ARGV, _PWSH_FIRST)


def _offenders(text: str) -> list[str]:
    return [m.group(0) for rx in _RULES for m in rx.finditer(text)]


def test_the_scan_catches_the_class_and_spares_the_fallback() -> None:
    assert _offenders('@pytest.mark.skipif(not shutil.which("pwsh"), reason="x")')
    assert _offenders('subprocess.run(["pwsh", "-NoProfile"])')
    assert _offenders('PS = shutil.which("pwsh") or shutil.which("powershell")')
    assert not _offenders('PS = shutil.which("powershell") or shutil.which("pwsh")')
    assert not _offenders("@pytest.mark.skipif(PS is None, reason='x')")
    assert not _offenders("subprocess.run([PS, '-NoProfile'])")


def test_no_test_gates_on_pwsh_alone() -> None:
    me = Path(__file__).resolve()
    bad = [
        f"{p.relative_to(ROOT).as_posix()}: {hit}"
        for d in _DIRS
        if (ROOT / d).is_dir()
        for p in sorted((ROOT / d).rglob("test_*.py"))
        if p.resolve() != me
        for hit in _offenders(p.read_text(encoding="utf-8", errors="ignore"))
    ]
    why = "pwsh-only or pwsh-first PowerShell gate (prefer powershell.exe):\n"
    assert not bad, why + "\n".join(bad)
