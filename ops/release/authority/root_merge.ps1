# THE OWNER'S EXCEPTIONAL ROOT MERGE, AFTER LEVEL 2 (ops/release/authority/LEVEL2.md).
#
# A ROOT change (the authority itself, the publisher, audit_gate.py, trusted-eval.yml) is never
# approved by the authority, and after Level 2 the LIVE ruleset lets no person bypass it. So the
# owner lands one with this, in an elevated PowerShell on the box:
#     powershell -ExecutionPolicy Bypass -File C:\opt\authority\repo\ops\release\authority\root_merge.ps1 -Pr N
# It signs him in to gh in the browser if he is not (and signs out again at the end), checks the
# PR's exact head against the gate's ROOT bar (genuine green checks + the latest trusted audit
# CLEAR of that head), adds his admin pull_request bypass for that one merge, merges pinned to
# the head, puts the bypass list back (in a finally, read back), and re-pins the root digest.
[CmdletBinding()]
param(
    [Parameter(Mandatory)] [int] $Pr,
    [string] $Owner = "kingdemond434-cpu",
    [string] $Repo = "kingdemond434-cpu/quant",
    [string] $Live = "claude/llm-auto-upgrade-verify-gcjac3",
    [string] $Registry = "C:\opt\audit_registry",
    [string] $AuthHome = "C:\opt\authority"
)
$ErrorActionPreference = 'Stop'
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Open PowerShell with 'Run as administrator' and run this again."
}
$Python = (Get-Content -Raw (Join-Path $AuthHome "config.json") | ConvertFrom-Json).python
$Clone = Join-Path $AuthHome "repo"
$signedIn = $false
$me = (& gh api user --jq .login 2>$null)
if ($LASTEXITCODE -ne 0) { & gh auth login --hostname github.com --web --git-protocol https; $signedIn = $true; $me = (& gh api user --jq .login) }
try {
    if ("$me".Trim() -ne $Owner) { throw "gh is signed in as '$me', not $Owner: a ROOT merge is the owner's own act." }
    & git -c safe.directory=* -C $Clone fetch -q --no-tags origin "+refs/heads/${Live}:refs/remotes/origin/${Live}"
    & git -c safe.directory=* -C $Clone checkout -q -f --detach "origin/$Live"
    $Here = Join-Path $Clone "ops\release\authority"
    & $Python -I (Join-Path $Here "bootstrap_github.py") --repo $Repo root-merge --pr $Pr
    if ($LASTEXITCODE -ne 0) { throw "#$Pr was not merged (see above)." }
    & git -c safe.directory=* -C $Clone fetch -q --no-tags origin "+refs/heads/${Live}:refs/remotes/origin/${Live}"
    & git -c safe.directory=* -C $Clone checkout -q -f --detach "origin/$Live"
    & $Python -I (Join-Path $Here "pin_root.py") --write (Join-Path $Registry "ROOT_PIN.json")
    if ($LASTEXITCODE -ne 0) { throw "merged, but the re-pin failed: the authority stays off until pin_root.py --write succeeds" }
    & icacls (Join-Path $Registry "ROOT_PIN.json") /inheritance:r /grant:r "Administrators:F" "SYSTEM:F" "Users:R" | Out-Null
    Copy-Item -Force (Join-Path $Here "run_authority.ps1") (Join-Path $AuthHome "run_authority.ps1")
    & icacls $Clone /setowner "quant-authority" /T /C /Q | Out-Null
    Write-Host "DONE: #$Pr merged and re-pinned. The authority resumes on its next pass." -ForegroundColor Green
} finally {
    if ($signedIn) { & gh auth logout --hostname github.com 2>$null | Out-Null }
}
