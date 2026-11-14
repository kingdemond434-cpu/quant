<#
.SYNOPSIS
    Give the MIDNIGHT CRO lane (Codex) its OWN clone at C:\opt\quant-cro-midnight and the one write
    grant it needs there, so the live desk C:\opt\quant and its .git stay locked.

.DESCRIPTION
    WHY A CLONE, NOT A WORKTREE (auditor HOLD on PR #439, 2026-10-28). The lane runs
    `codex exec --full-auto`, and Codex's Windows sandbox executes as accounts in the local group
    CodexSandboxUsers. A git worktree always writes the MAIN .git (worktrees/, refs, objects,
    index), and write on C:\opt\quant\.git is code execution as SYSTEM: .git/config carries
    core.fsmonitor, core.hooksPath, filter drivers and aliases, and the 107 MT5-*/E8-* tasks and the
    adopter run git there as SYSTEM or Administrator. So the live .git gets NO grant, ever. The lane
    gets a separate clone that fetches from and pushes to origin directly and borrows objects
    read-only from the live repository through alternates (`--reference`).

    WHAT THE SANDBOX GROUP GETS. Modify on everything INSIDE the clone, inherit-only, and RX on the
    clone root and on .git themselves, so neither can be renamed away and replaced. .git\config and
    .git\hooks stay read-only to it: Codex itself (the unsandboxed parent, running as the -RunAs
    account) reads git metadata in its workspace, so a sandbox-written config there would execute
    as that account. BUILTIN\Users get nothing (C:\opt hands them AD by inheritance; it is cut).
    lane_clone_guard.ps1 checks all of this here and again before every Codex pass. The origin URL
    is stripped of any credentials, because the group can read the clone's config.

    PRE-EXISTING FOLDERS ARE NOT TRUSTED. C:\opt grants Users AD, so anyone could have pre-created
    the clone folder and own it. An existing clone folder whose owner is not Administrators, SYSTEM
    or the elevated caller is refused (exit 5) and nothing is touched.

    DUBIOUS OWNERSHIP. The clone is owned by an administrator, and git run as a sandbox account
    refuses such a repository. Exactly this one path is added to the SYSTEM gitconfig's
    safe.directory list (never `*`).

    FAILS LOUDLY. No group (Codex never initialised its sandbox here): exit 2, nothing done. A failed
    clone or grant: exit 3. The live tree listing the group afterwards: exit 6. The clone failing
    the seal check: exit 7.

    -Undo removes the group's grant from the clone and the safe.directory entry; it never touches
    C:\opt\quant. Delete the clone by hand if the lane is retired.

.PARAMETER RepoRoot
    The live desk checkout, used read-only (origin URL, branch and alternates). Default C:\opt\quant.

.PARAMETER Group
    The Codex sandbox group. Default CodexSandboxUsers.

.PARAMETER Undo
    Remove the grant and the safe.directory entry, then exit.
#>
[CmdletBinding()]
param(
    [string] $RepoRoot = 'C:\opt\quant',
    [string] $Group = 'CodexSandboxUsers',
    [switch] $Undo
)
$ErrorActionPreference = 'Stop'

$me = [Security.Principal.WindowsIdentity]::GetCurrent()
if (-not ([Security.Principal.WindowsPrincipal]$me).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host 'FATAL: run in an elevated PowerShell'; exit 1
}

$Clone   = Join-Path (Split-Path $RepoRoot -Parent) 'quant-cro-midnight'
$SafeDir = $Clone -replace '\\', '/'
$TrustedOwners = @('S-1-5-32-544', 'S-1-5-18', $me.User.Value)

function Get-OwnerSid([string] $Path) {
    (Get-Acl -LiteralPath $Path).GetOwner([Security.Principal.SecurityIdentifier]).Value
}

$g = Get-LocalGroup -Name $Group -ErrorAction SilentlyContinue
# Native git/icacls write progress to stderr, which Windows PowerShell turns into terminating
# errors under Stop; every native call below is judged by its exit code instead.
$ErrorActionPreference = 'Continue'

if ($Undo) {
    if ($g -and (Test-Path -LiteralPath $Clone)) {
        icacls $Clone /remove:g "*$($g.SID.Value)" /T /C /Q | Out-Null
        "removed $Group from $Clone"
    }
    & git config --system --unset-all safe.directory ("^" + [regex]::Escape($SafeDir) + "$") 2>$null
    "removed safe.directory $SafeDir"
    exit 0
}

if (-not $g) {
    Write-Host "FATAL: local group '$Group' does not exist; Codex has not initialised its sandbox here. Nothing done."
    exit 2
}
$sid = $g.SID.Value

if (Test-Path -LiteralPath $Clone) {
    $owner = Get-OwnerSid $Clone
    if ($TrustedOwners -notcontains $owner) {
        Write-Host "FATAL: $Clone already exists and is owned by $owner, not an administrator. Refusing to trust it; inspect and remove it by hand."
        exit 5
    }
    if (-not (Test-Path -LiteralPath (Join-Path $Clone '.git\config'))) {
        Write-Host "FATAL: $Clone exists but is not a clone. Remove it by hand and re-run."
        exit 5
    }
    "reusing $Clone (owner $owner)"
    $cur = (& git -C $Clone remote get-url origin | Out-String).Trim()
    $stripped = $cur -replace '^([A-Za-z][A-Za-z0-9+.-]*://)[^/@]*@', '$1'
    if ($stripped -ne $cur) { & git -C $Clone remote set-url origin $stripped; 'stripped credentials from the clone origin URL' }
} else {
    $origin = (& git -C $RepoRoot remote get-url origin | Out-String).Trim()
    $branch = (& git -C $RepoRoot rev-parse --abbrev-ref HEAD | Out-String).Trim()
    if (-not $origin -or -not $branch) { Write-Host 'FATAL: cannot read origin/branch from the live repo'; exit 3 }
    # The clone's .git\config is readable by the sandbox, so a token in the origin URL would reach
    # it. Userinfo is stripped, and the URL is never printed.
    $origin = $origin -replace '^([A-Za-z][A-Za-z0-9+.-]*://)[^/@]*@', '$1'
    # --dissociate: borrow the live objects for speed, then copy them, so a gc in the live repo
    # can never drop an object the clone depends on.
    & git clone --reference (Join-Path $RepoRoot '.git') --dissociate --branch $branch $origin $Clone
    if ($LASTEXITCODE -ne 0) { Write-Host "FATAL: clone failed ($LASTEXITCODE)"; exit 3 }
}

# The clone's ACL, set whole. On the root and on .git the group holds read, add-file and
# add-folder on the folder itself (git needs index.lock, HEAD, FETCH_HEAD there) and Modify
# INHERIT-ONLY, so everything inside is writable, but neither folder carries DELETE or
# delete-child, so neither can be renamed away and replaced by a planted one. Users: none.
$Admins = '*S-1-5-32-544'; $System = '*S-1-5-18'
icacls $Clone /inheritance:r /grant:r "${Admins}:(OI)(CI)F" "${System}:(OI)(CI)F" "*${sid}:(RX,WD,AD)" /C /Q
if ($LASTEXITCODE -eq 0) { icacls $Clone /grant "*${sid}:(OI)(CI)(IO)M" /C /Q }   # a second ACE, not a replacement
if ($LASTEXITCODE -ne 0) { Write-Host "FATAL: grant on $Clone failed ($LASTEXITCODE)"; exit 3 }
# Children take the new inherited ACL. Never /reset the root itself: that would re-inherit C:\opt.
Get-ChildItem -LiteralPath $Clone -Force | ForEach-Object { icacls $_.FullName /reset /T /C /Q | Out-Null }
$GitDir = Join-Path $Clone '.git'
icacls $GitDir /inheritance:r /grant:r "${Admins}:(OI)(CI)F" "${System}:(OI)(CI)F" "*${sid}:(RX,WD,AD)" /C /Q
if ($LASTEXITCODE -eq 0) { icacls $GitDir /grant "*${sid}:(OI)(CI)(IO)M" /C /Q }   # a second ACE, not a replacement
if ($LASTEXITCODE -ne 0) { Write-Host "FATAL: grant on $GitDir failed ($LASTEXITCODE)"; exit 3 }
Get-ChildItem -LiteralPath $GitDir -Force | ForEach-Object { icacls $_.FullName /reset /T /C /Q | Out-Null }
# config (a file) and hooks (a folder) are read-only to the group: what git executes lives there.
icacls (Join-Path $GitDir 'config') /inheritance:r /grant:r "${Admins}:F" "${System}:F" "*${sid}:RX" /C /Q
if ($LASTEXITCODE -ne 0) { Write-Host "FATAL: read-only on .git\config failed ($LASTEXITCODE)"; exit 3 }
$Hooks = Join-Path $GitDir 'hooks'
New-Item -ItemType Directory -Force -Path $Hooks | Out-Null
icacls $Hooks /inheritance:r /grant:r "${Admins}:(OI)(CI)F" "${System}:(OI)(CI)F" "*${sid}:(OI)(CI)RX" /C /Q
if ($LASTEXITCODE -ne 0) { Write-Host "FATAL: read-only on .git\hooks failed ($LASTEXITCODE)"; exit 3 }
Get-ChildItem -LiteralPath $Hooks -Force | ForEach-Object { icacls $_.FullName /reset /T /C /Q | Out-Null }

# Owned by the Administrators group, not whichever admin ran this, so the launcher's owner check
# holds whatever -RunAs account the task uses.
icacls $Clone /setowner '*S-1-5-32-544' /C /Q | Out-Null

$have = @(& git config --system --get-all safe.directory 2>$null)
if ($have -notcontains $SafeDir) { & git config --system --add safe.directory $SafeDir }

"--- result ---"
icacls $Clone
icacls (Join-Path $Clone '.git\config')
# icacls prints resolved names (HOST\CodexSandboxUsers), or the bare SID when it cannot resolve.
$pattern = [regex]::Escape($sid) + '|' + [regex]::Escape($Group)
$leak = icacls $RepoRoot | Select-String -Pattern $pattern
$leak2 = icacls (Join-Path $RepoRoot '.git') | Select-String -Pattern $pattern
if ($leak -or $leak2) {
    Write-Host "FATAL: the live tree or its .git lists $Group ($sid); the lock is open. Remove that grant."
    exit 6
}
"live tree and live .git: no $Group grant (OK)"

. (Join-Path $PSScriptRoot 'lane_clone_guard.ps1')
$sealed = @(Get-LaneCloneProblems $Clone $TrustedOwners)
if ($sealed.Count) {
    Write-Host "FATAL: the clone is not sealed:"; $sealed | ForEach-Object { Write-Host "  $_" }
    exit 7
}
"lane clone sealed (OK)"
