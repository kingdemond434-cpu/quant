"""No PowerShell script in the repo can die on a `$name:` inside a double-quoted string.

THE DEFECT THIS PINS (#479 re-audit MF2, 2026-10-29). `"using the per-user python $py: ..."`
parses `$py:` as a drive-qualified variable reference, a PARSE error, so the whole installer
failed before registering anything. A test that only reads the source for task names cannot see
that. This scans every .ps1 for the class, and when pwsh is installed also runs PowerShell's own
parser on each one.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
#: `$env:X`, `$script:x` and the like are real scopes/drives; `${py}:` and `` `$py: `` are fine.
_DRIVE_VAR = re.compile(
    r'"[^"\n]*(?<![`{])\$(?!(?:env|script|global|local|using|private|variable|function|alias)'
    r"\b)[A-Za-z_]\w*:(?!:)[^\"\n]*\"", re.IGNORECASE)


def _scripts() -> list[Path]:
    return sorted(p for p in REPO.rglob("*.ps1")
                  if not ({".git", "node_modules", ".venv"} & set(p.parts)))


def test_no_drive_qualified_variable_inside_a_double_quoted_string() -> None:
    bad = [f"{p.relative_to(REPO)}:{i}: {line.strip()[:100]}"
           for p in _scripts()
           for i, line in enumerate(p.read_text("utf-8", errors="replace").splitlines(), 1)
           if not line.lstrip().startswith("#") and _DRIVE_VAR.search(line)]
    assert not bad, "use ${name}: or $($name): --\n" + "\n".join(bad)


def test_the_pattern_catches_the_bug_and_spares_real_drives() -> None:
    assert _DRIVE_VAR.search('Write-Warning "using $py: x"')
    assert not _DRIVE_VAR.search('Write-Warning "using ${py}: x"')
    assert not _DRIVE_VAR.search('"$env:TEMP\\x"')
    assert not _DRIVE_VAR.search('"[$t] ok"')


@pytest.mark.skipif(not shutil.which("pwsh"), reason="pwsh not installed")
def test_every_script_parses_in_powershell() -> None:
    files = [str(p) for p in _scripts()]
    cmd = ("$bad=@(); foreach($f in (ConvertFrom-Json $env:PS_FILES)){$e=$null;"
           "[void][System.Management.Automation.Language.Parser]::ParseFile($f,[ref]$null,[ref]$e);"
           "if($e){$bad+=\"${f}: $($e[0].Message)\"}}; $bad -join \"`n\"")
    r = subprocess.run(["pwsh", "-NoProfile", "-Command", cmd], capture_output=True, text=True,
                       env={**os.environ, "PS_FILES": json.dumps(files)},
                       timeout=300)
    assert r.returncode == 0 and not r.stdout.strip(), r.stdout + r.stderr
