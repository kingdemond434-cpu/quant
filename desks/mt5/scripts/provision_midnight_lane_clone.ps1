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

    WHAT THE SANDBOX GROUP GETS. Modify on the clone, except its .git\config and .git\hooks, which
    stay read-only to it: Codex itself (the unsandboxed parent, running as the -RunAs account) reads
    git metadata in its workspace, so a sandbox-written config there would execute as that account.
    BUILTIN\Users get nothing on the clone (C:\opt hands them AD by inheritance; it is cut).

    PRE-EXISTING FOLDERS ARE NOT TRUSTED. C:\opt grants Users AD, so anyone could have pre-created
    the clone folder and own it. An existing clone folder whose owner is not Administrators, SYSTEM
    or the elevated caller is refused (exit 5) and nothing is touched.

    DUBIOUS OWNERSHIP. The clone is owned by an administrator, and git run as a sandbox account
    refuses such a repository. Exactly this one path is added to the SYSTEM gitconfig's
    safe.directory list (never `*`).

    FAILS LOUDLY. No group (Codex never initialised its sandbox here): exit 2, nothing done. A failed
    clone or grant: exit 3. The live tree listing the group afterwards: exit 6.

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
} else {
    $origin = (& git -C $RepoRoot remote get-url origin | Out-String).Trim()
    $branch = (& git -C $RepoRoot rev-parse --abbrev-ref HEAD | Out-String).Trim()
    if (-not $origin -or -not $branch) { Write-Host 'FATAL: cannot read origin/branch from the live repo'; exit 3 }
    & git clone --reference (Join-Path $RepoRoot '.git') --branch $branch $origin $Clone
    if ($LASTEXITCODE -ne 0) { Write-Host "FATAL: clone failed ($LASTEXITCODE)"; exit 3 }
}

# The clone's ACL, set whole: admins and SYSTEM full, the sandbox group Modify, nobody else.
icacls $Clone /inheritance:r /grant:r '*S-1-5-32-544:(OI)(CI)F' '*S-1-5-18:(OI)(CI)F' "*${sid}:(OI)(CI)M" /C /Q
if ($LASTEXITCODE -ne 0) { Write-Host "FATAL: grant on $Clone failed ($LASTEXITCODE)"; exit 3 }
# Children take the new inherited ACL. Never /reset the root itself: that would re-inherit C:\opt.
Get-ChildItem -LiteralPath $Clone -Force | ForEach-Object { icacls $_.FullName /reset /T /C /Q | Out-Null }
foreach ($ro in @('.git\config', '.git\hooks')) {
    $p = Join-Path $Clone $ro
    if (Test-Path -LiteralPath $p) {
        icacls $p /inheritance:r /grant:r '*S-1-5-32-544:(OI)(CI)F' '*S-1-5-18:(OI)(CI)F' "*${sid}:(OI)(CI)RX" /T /C /Q
        if ($LASTEXITCODE -ne 0) { Write-Host "FATAL: read-only on $p failed ($LASTEXITCODE)"; exit 3 }
    }
}

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
