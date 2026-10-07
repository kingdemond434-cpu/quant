"""The box publisher must survive the three failures measured on the box on 2026-10-06.

Read-only census of vmi3571445 at 15:43Z: no box-authored state had reached origin since
2026-09-24. sync_shadow_to_git.log named
  * "Cannot prompt because user interactivity has been disabled / unable to get password" (13:36,
    a scheduled task with no non-interactive git credential),
  * `git commit` rc=-1073741819, an access violation (13:54),
  * "git add failed rc=128" on every slot from 14:05 -- git's "dubious ownership" refusal, the
    repository being owned by BUILTIN\\Administrators and the task running as Administrator.

There is no pwsh on the research host, so this pins the script's structure and proves on real git
that the configuration mechanism it relies on (GIT_CONFIG_COUNT, command scope) does what the
script assumes.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "desks" / "mt5" / "scripts"
SYNC = SCRIPTS / "sync_shadow_to_git.ps1"
ENV = SCRIPTS / "GitBoxEnv.ps1"


def _src(p: Path) -> str:
    return p.read_text("utf-8", errors="ignore")


def _code(p: Path) -> str:
    """The script with comment lines removed, so a rule cannot be met by a comment."""
    return "\n".join(ln for ln in _src(p).splitlines() if not ln.lstrip().startswith("#"))


def test_the_git_env_is_set_before_the_first_git_call() -> None:
    code = _code(SYNC)
    init = code.index("Initialize-BoxGitEnv -RepoRoot $RepoRoot")
    assert '. (Join-Path $PSScriptRoot "GitBoxEnv.ps1")' in code
    # Only Git-In-Repo is DEFINED above it; every top-level git call (the branch read, the pull,
    # the add) runs after it.
    assert init < code.index("function Invoke-GitWriteRetry")
    for call in ("$branch = (& git -C $RepoRoot rev-parse", "Sync-Pull -RepoRoot $RepoRoot",
                 "Open-GitWriterMutex"):
        assert init < code.index(call), f"{call!r} runs before safe.directory is set"


def test_safe_directory_is_this_repo_never_a_wildcard() -> None:
    code = _code(ENV)
    assert 'Add-GitConfigEnv -Key "safe.directory" -Value $safe' in code
    assert '"*"' not in code, "safe.directory must name this repository, never trust every path"


def test_prompts_are_off_so_a_missing_credential_fails_and_is_named() -> None:
    code = _code(ENV)
    assert '$env:GIT_TERMINAL_PROMPT = "0"' in code
    assert '$env:GCM_INTERACTIVE = "never"' in code


def test_the_token_comes_from_the_machine_and_is_never_logged() -> None:
    env, sync = _code(ENV), _code(SYNC)
    assert '"GITHUB_TOKEN", $scope' in env and '"Machine"' in env
    assert "http.https://github.com/.extraheader" in env
    for src in (env, sync):
        for line in src.splitlines():
            if re.search(r"Write-(SyncLog|Host|Output)|Add-Content|Set-Content|Out-File", line):
                assert "$token" not in line and "$basic" not in line, line


@pytest.mark.parametrize("line", [
    "fatal: Cannot prompt because user interactivity has been disabled.",
    "error: unable to get password from user",
    "fatal: could not read Username for 'https://github.com': terminal prompts disabled",
    "remote: Invalid username or token. Password authentication is not supported",
    "fatal: Authentication failed for 'https://github.com/x/y.git/'",
    "remote: Permission to x/y.git denied to someone.",
    "fatal: unable to access 'https://github.com/x/y.git/': The requested URL returned error: 403",
])
def test_the_measured_auth_failures_are_recognised(line: str) -> None:
    pats = re.findall(r'^\s*"(.+)",?$', _src(ENV).split("$script:GitAuthFailurePatterns = @(")[1]
                      .split("\n)")[0], re.M)
    assert pats, "no auth-failure patterns found"
    assert any(re.search(p, line) for p in pats), line


def test_a_non_auth_push_failure_is_not_called_blocked_auth() -> None:
    pats = re.findall(r'^\s*"(.+)",?$', _src(ENV).split("$script:GitAuthFailurePatterns = @(")[1]
                      .split("\n)")[0], re.M)
    for line in ("error: RPC failed; HTTP 408 curl 22", "! [rejected] (non-fast-forward)",
                 "PUSH REFUSED: a constitutional law fence is failing (L1.37)."):
        assert not any(re.search(p, line) for p in pats), line


def test_blocked_auth_is_a_named_exit_and_stops_the_futile_retries() -> None:
    code = _code(SYNC)
    assert "if (Test-GitAuthFailure -Lines $out) { $script:BlockedAuth = $true }" in code
    pub = code[code.index("function Publish-StateOnto"):]
    pub = pub[:pub.index("\n}\n")]
    assert pub.index("if ($script:BlockedAuth)") < pub.index("re-fetching and re-basing")
    assert "exit 3" in code and "ABORT: BLOCKED_AUTH" in code


def test_a_crashing_add_or_commit_is_retried_and_never_aborts_delivery() -> None:
    code = _code(SYNC)
    assert 'Invoke-GitWriteRetry -GitArgs (@("add", "--") + $existing) -What "git add"' in code
    assert '-What "git commit"' in code
    assert 'ABORT: git commit failed' not in code and 'ABORT: git add failed' not in code
    assert "-FromDisk:$script:PublishFromDisk" in code
    fn = code[code.index("function Invoke-GitWriteRetry"):]
    fn = fn[:fn.index("\n}\n")]
    assert "index.lock" in fn and "TotalMinutes -ge 5" in fn, "stale lock must be aged, not blind"


def test_from_disk_publishing_never_touches_head_or_the_real_index() -> None:
    code = _code(SYNC)
    pub = code[code.index("function Publish-StateOnto"):]
    pub = pub[:pub.index("\n}\n")]
    assert '"hash-object", "-w", "--", $rel' in pub
    for forbidden in ('"add"', '"commit",', '"checkout"', '"reset"', '"stash"'):
        assert forbidden not in pub, forbidden


def test_scripts_stay_ascii_for_windows_powershell_5() -> None:
    for p in (ENV, SYNC):
        bad = [i for i, ch in enumerate(_src(p)) if ord(ch) > 127]
        assert not bad, f"{p.name} has non-ASCII at {bad[:3]}"


@pytest.mark.skipif(shutil.which("git") is None, reason="git required")
def test_git_reads_safe_directory_and_the_header_from_the_process_env(tmp_path: Path) -> None:
    """The mechanism the script relies on: GIT_CONFIG_COUNT entries are COMMAND scope, which is a
    protected scope (safe.directory is honoured there), and no config file is written."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    env = {**os.environ, "GIT_CONFIG_COUNT": "2",
           "GIT_CONFIG_KEY_0": "safe.directory", "GIT_CONFIG_VALUE_0": str(tmp_path),
           "GIT_CONFIG_KEY_1": "http.https://github.com/.extraheader",
           "GIT_CONFIG_VALUE_1": "AUTHORIZATION: basic eA=="}
    out = subprocess.run(["git", "-C", str(tmp_path), "config", "--show-scope", "--get-all",
                          "safe.directory"], capture_output=True, text=True, env=env, check=True)
    # A host may carry its own system/global entries (CI's checkout adds one); ours must be among
    # them, and in the COMMAND scope.
    scoped = [ln.split("\t", 1) for ln in out.stdout.splitlines() if "\t" in ln]
    assert ["command", str(tmp_path)] in [[s, v] for s, v in scoped], out.stdout
    hdr = subprocess.run(["git", "-C", str(tmp_path), "config", "--get",
                          "http.https://github.com/.extraheader"],
                         capture_output=True, text=True, env=env, check=True)
    assert hdr.stdout.strip() == "AUTHORIZATION: basic eA=="
    assert "extraheader" not in (tmp_path / ".git" / "config").read_text("utf-8")


def test_a_stale_lock_is_removed_only_when_no_git_process_is_alive() -> None:
    """Audit R1 (2026-10-06): age alone is not debris. An orphan `git merge` that outlived a killed
    task holds index.lock without the mutex; deleting it under that git corrupts the index."""
    code = _code(SYNC)
    fn = code[code.index("function Invoke-GitWriteRetry"):]
    fn = fn[:fn.index("\n}\n")]
    assert "Get-Process -Name git" in fn
    remove = fn.index("Remove-Item -LiteralPath $lock")
    cond = fn.rfind("if (", 0, remove)
    guard = fn[cond:remove]
    assert "TotalMinutes -ge 5" in guard and "$alive.Count -eq 0" in guard, guard
    assert "KEEPING .git\\index.lock" in fn, "a kept lock must be logged with the live pids"


def test_the_from_disk_fallback_names_every_file_it_drops() -> None:
    code = _code(SYNC)
    pub = code[code.index("function Publish-StateOnto"):]
    pub = pub[:pub.index("\n}\n")]
    disk = pub[pub.index("if ($FromDisk)"):pub.index("} else {")]
    assert "could not hash" in disk and "it is NOT in this publish" in disk
    assert "listed path(s) hashed" in disk
    assert "EVERY state file failed to hash" in disk, "all-failed needs its own message"


def test_an_old_git_is_warned_at_startup() -> None:
    env, sync = _code(ENV), _code(SYNC)
    assert '[version]"2.38"' in env and "Get-BoxGitVersion" in env
    assert "GitTooOldForEnvSafeDirectory" in sync and "WARN:" in sync


def test_a_crash_writes_a_diagnosis_that_travels() -> None:
    code = _code(SYNC)
    fn = code[code.index("function Write-GitCrashDiag"):]
    fn = fn[:fn.index("\n}\n")]
    for key in ("rc_hex", "git_version", "index_bytes", "count-objects", "Get-WinEvent",
                "git_processes_alive", "command"):
        assert key in fn, key
    assert "<{0} path(s)>" in fn, "paths are counted, never listed"
    assert "Windows Error Reporting" in fn and "git\\.exe" in fn, "events must name git.exe"
    assert "-match 'git'" not in fn
    retry = code[code.index("function Invoke-GitWriteRetry"):]
    assert "if ($rc -lt 0 -or $rc -gt 255) { Write-GitCrashDiag" in retry
    assert "-Extra @($script:CrashDiagRel, $script:BacklogRel)" in code


def test_the_backlog_drain_is_daily_and_never_blocks_the_publish() -> None:
    code = _code(SYNC)
    tail = code[code.index("shadow state synced to origin"):]
    assert "libs.ops.box_backlog" in tail
    # Audit HOLD (2026-10-06): the public repository gets nothing pushed until the audit clears
    # the drain, so the box runs it classify-only.
    assert "--push" not in tail, "the box drain must stay classify-only until the audit clears it"
    assert "TotalHours -ge 24" in tail
    assert tail.rstrip().endswith("exit 0"), "a failed drain must not fail the state publish"


def test_the_python_reader_carries_safe_directory_too() -> None:
    from libs.ops import state_publication as sp
    src = Path(sp.__file__).read_text("utf-8")
    assert "env=git_env(root)" in src
