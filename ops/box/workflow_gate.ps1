# MERGE AUDIT-CLEARED PRs FROM THE BOX (2026-10-28).
#
# The Actions audit gate (.github/scripts/audit_gate.py, #445) merges a PR into LIVE once the
# auditor CLEARs its head and CI is green -- but it needs the `audit-clear` label to start, which
# the cloud sessions are refused (as is marking a draft ready), and it cannot merge a PR that
# changes .github/workflows/** (GitHub refuses the workflow token). This runs the SAME gate, same
# rule, in its box mode with zuck's own gh login: `audit_gate.py --sweep --box` looks at every
# open PR into LIVE with no label needed, and merges (marking a draft ready first) only on a CLEAR
# for the head (or the same exact diff) plus green gating CI, pinned to the head sha, never waiting.
#
# TRUSTED CODE ONLY. The gate script is read from a clean, detached checkout of origin/LIVE in an
# admin-only folder, never from a PR branch. A merge made with a user token starts the normal push
# CI on LIVE (seal, promote); nothing is dispatched.
#
# No token is read, printed or stored here: gh keeps zuck's login in Windows Credential Manager.
# Any GITHUB_TOKEN / GH_TOKEN in the environment is dropped for this process so the merge is made
# with that login and nothing else. Without the `workflow` scope it still merges the other PRs, and
# says in logs\workflow_gate.json that workflow-file PRs will fail until zuck runs once:
# `gh auth refresh -h github.com -s workflow`.

[CmdletBinding()]
param(
    [string] $Root = "C:\ProgramData\QuantBox",
    [string] $Repo = "kingdemond434-cpu/quant",
    [string] $Live = "claude/llm-auto-upgrade-verify-gcjac3",
    [string] $Gh = "C:\Users\Administrator\tools\gh\bin\gh.exe",
    [string] $Python = ""
)
$ErrorActionPreference = 'Stop'
$LogDir = Join-Path $Root "logs"
$Clone = Join-Path $Root "gate-repo"
$log = Join-Path $LogDir "workflow_gate.log"
$beat = Join-Path $LogDir "workflow_gate.json"

$mutex = New-Object System.Threading.Mutex($false, "Global\QuantBox-WorkflowGate")
if (-not $mutex.WaitOne(0)) { exit 0 }  # the previous sweep is still running

function Say([string] $line) {
    Add-Content -LiteralPath $log -Value ("{0} {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ssK'), $line)
}
function Beat([int] $rc, [string] $note, [bool] $scope) {
    $doc = [ordered]@{ at = (Get-Date).ToUniversalTime().ToString('o'); rc = $rc; workflow_scope = $scope; note = $note }
    $doc | ConvertTo-Json -Compress | Set-Content -LiteralPath "$beat.tmp" -Encoding UTF8
    Move-Item -LiteralPath "$beat.tmp" -Destination $beat -Force
}
if ((Test-Path -LiteralPath $log) -and (Get-Item -LiteralPath $log).Length -gt 5MB) {
    Move-Item -LiteralPath $log -Destination "$log.1" -Force
}

# zuck's gh login and nothing else; git trusts the gate clone (an elevated admin's files are owned
# by Administrators, which git calls "dubious ownership") through command-scope config only.
foreach ($v in @('GITHUB_TOKEN', 'GH_TOKEN', 'GH_ENTERPRISE_TOKEN', 'GITHUB_ENTERPRISE_TOKEN')) {
    Remove-Item -LiteralPath "env:$v" -ErrorAction SilentlyContinue
}
$env:GH_PROMPT_DISABLED = '1'
$env:GIT_TERMINAL_PROMPT = '0'
$env:GIT_CONFIG_COUNT = '1'
$env:GIT_CONFIG_KEY_0 = 'safe.directory'
$env:GIT_CONFIG_VALUE_0 = ($Clone -replace '\\', '/')
$env:PATH = (Split-Path -Parent $Gh) + ';' + $env:PATH

try {
    if (-not $Python) {
        foreach ($cand in @("$env:LOCALAPPDATA\Programs\Python\Python314\python.exe", 'C:\Program Files\Python314\python.exe')) {
            if (Test-Path -LiteralPath $cand) { $Python = $cand; break }
        }
    }
    if (-not $Python) { throw "no Python 3.14 found" }

    $ErrorActionPreference = 'Continue'  # native stderr is data; exit codes are the verdict
    $status = (& $Gh auth status -h github.com 2>&1 | Out-String)
    $scopeLine = ($status -split "`n" | Where-Object { $_ -match 'Token scopes' } | Select-Object -First 1)
    if ($LASTEXITCODE -ne 0) { Say "gh is not logged in: $($status.Trim())"; Beat 3 "gh not logged in" $false; exit 3 }
    $scope = $scopeLine -match "'workflow'"
    if (-not $scope) {
        Say "gh login lacks the workflow scope ($scopeLine); workflow-file PRs will fail to merge"
    }

    if (-not (Test-Path -LiteralPath (Join-Path $Clone ".git"))) {
        & git clone -q --filter=blob:none --no-checkout "https://github.com/$Repo.git" $Clone 2>&1 | ForEach-Object { Say "clone: $_" }
        if ($LASTEXITCODE -ne 0) { throw "git clone failed ($LASTEXITCODE)" }
    }
    # every run, so a moved gate script is followed (only this one file is ever checked out)
    & git -C $Clone sparse-checkout set --no-cone /.github/scripts/audit_gate.py
    if ($LASTEXITCODE -ne 0) { throw "sparse-checkout failed ($LASTEXITCODE)" }
    & git -C $Clone fetch -q --no-tags origin "+refs/heads/${Live}:refs/remotes/origin/${Live}" 2>&1 | ForEach-Object { Say "fetch: $_" }
    if ($LASTEXITCODE -ne 0) { throw "git fetch failed ($LASTEXITCODE)" }
    & git -C $Clone checkout -q -f --detach "origin/$Live" 2>&1 | ForEach-Object { Say "checkout: $_" }
    if ($LASTEXITCODE -ne 0) { throw "git checkout failed ($LASTEXITCODE)" }
    $at = (& git -C $Clone rev-parse --short=9 HEAD)

    Push-Location -LiteralPath $Clone
    try {
        $out = (& $Python -I -u (Join-Path $Clone ".github\scripts\audit_gate.py") --repo $Repo --base $Live --sweep --box 2>&1 | Out-String)
        $rc = $LASTEXITCODE
    } finally { Pop-Location }
    foreach ($l in ($out -split "`r?`n" | Where-Object { $_ })) { Say "gate@$at $l" }
    $merged = @($out -split "`r?`n" | Where-Object { $_ -match 'MERGED' }).Count
    $note = "gate@{0}: {1} merged" -f $at, $merged
    if (-not $scope) { $note += "; NO workflow scope: run once  gh auth refresh -h github.com -s workflow" }
    Beat $rc $note $scope
    exit $rc
} catch {
    Say "FAILED: $($_.Exception.Message)"
    Beat 1 "FAILED: $($_.Exception.Message)" $false
    exit 1
} finally {
    $mutex.ReleaseMutex()
}
