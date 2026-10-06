"""Execute the shipped PowerShell functions and both real guards in private repositories."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "desks/mt5/scripts/Adopt-Release.ps1"
SHELL = shutil.which("pwsh") or shutil.which("powershell")


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True,
                          capture_output=True, text=True, encoding="utf-8").stdout.strip()


def repository(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.email", "fixture@example.test")
    git(repo, "config", "user.name", "Fixture")
    for name in ["scripts/moneypath_precommit_guard.py", "scripts/check_protected_records.py",
                 "libs/ops/protected_artifacts.py", "libs/ops/__init__.py", "libs/__init__.py"]:
        dest = repo / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, dest)
    (repo / "context").mkdir()
    (repo / "context/decision_journal.jsonl").write_text(
        json.dumps({"id": "D-20261005-001", "title": "Original receipt"}) + "\n")
    (repo / "source.py").write_text("value = 1\n")
    (repo / "empty.txt").write_bytes(b"")
    git(repo, "add", "--", "scripts", "libs", "context", "source.py", "empty.txt")
    git(repo, "commit", "-q", "-m", "Original fixture")
    return repo


def powershell(repo: Path, body: str) -> subprocess.CompletedProcess[str]:
    # Parse without executing the adopter's global scheduler/repository entrypoint.
    prefix = f"""
$ErrorActionPreference = 'Stop'
$RepoRoot = '{repo.as_posix()}'
$tokens = $null; $errors = $null
$sourcePath = '{SCRIPT.as_posix()}'
$ast = [System.Management.Automation.Language.Parser]::ParseFile(
    $sourcePath, [ref]$tokens, [ref]$errors)
if ($errors.Count) {{ throw ($errors | Out-String) }}
$names = @('Invoke-GuardedIndexCommit','Invoke-GitBytes','Get-WorktreeBytes','Write-InPlace')
$ast.FindAll({{ param($node)
    $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
    $names -contains $node.Name
}}, $true) | ForEach-Object {{ Invoke-Expression $_.Extent.Text }}
function Invoke-Git {{
  param([string[]]$GitArgs)
  $out = @(& git -C $RepoRoot @GitArgs)
  if ($LASTEXITCODE -ne 0) {{ throw 'Real Git operation failed' }}
  return ($out -join "`n")
}}
Set-Location $RepoRoot
"""
    assert SHELL
    return subprocess.run([SHELL, "-NoProfile", "-NonInteractive", "-Command", prefix + body],
                          capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=90, env={**os.environ, "PYTHONUTF8": "1"})


@pytest.mark.skipif(SHELL is None, reason="Native PowerShell is unavailable")
def test_real_zero_byte_blob_truncates_in_place(tmp_path: Path) -> None:
    repo = repository(tmp_path)
    head = git(repo, "rev-parse", "HEAD")
    (repo / "empty.txt").write_bytes(b"stale content")
    result = powershell(repo, f"$bytes = Get-WorktreeBytes '{head}' 'empty.txt'; "
                        "if ($null -eq $bytes) { throw 'Empty blob became null' }; "
                        "Write-InPlace (Join-Path $RepoRoot 'empty.txt') $bytes")
    assert result.returncode == 0, result.stdout + result.stderr
    assert (repo / "empty.txt").read_bytes() == b""


@pytest.mark.skipif(SHELL is None, reason="Native PowerShell is unavailable")
def test_native_commit_executes_real_guards_and_advances_exact_tree(tmp_path: Path) -> None:
    repo = repository(tmp_path)
    before = git(repo, "rev-parse", "HEAD")
    (repo / "source.py").write_text("value = 2\n")
    git(repo, "add", "--", "source.py")
    tree = git(repo, "write-tree")
    result = powershell(repo, "Invoke-GuardedIndexCommit -Message 'Verified fixture update'")
    assert result.returncode == 0, result.stdout + result.stderr
    assert git(repo, "rev-parse", "HEAD^{tree}") == tree
    assert git(repo, "rev-parse", "HEAD^") == before
    assert "protected records: OK" in result.stdout


@pytest.mark.skipif(SHELL is None, reason="Native PowerShell is unavailable")
def test_real_guard_refusal_preserves_head_and_journal(tmp_path: Path) -> None:
    repo = repository(tmp_path)
    before = git(repo, "rev-parse", "HEAD")
    (repo / "context/decision_journal.jsonl").write_text(
        json.dumps({"id": "D-20261005-001", "title": "Rewritten receipt"}) + "\n")
    git(repo, "add", "--", "context/decision_journal.jsonl")
    result = powershell(repo, "Invoke-GuardedIndexCommit -Message 'Must refuse'")
    assert result.returncode != 0
    assert "RECORDS_REWRITTEN" in result.stdout + result.stderr
    assert git(repo, "rev-parse", "HEAD") == before
    assert "Original receipt" in git(repo, "show", "HEAD:context/decision_journal.jsonl")
