<#
.SYNOPSIS
    Give the Codex sandbox the two write grants the MIDNIGHT CRO lane needs, and nothing more,
    after the live-desk ACL lock has removed inherited BUILTIN\Users write from C:\opt\quant.

.DESCRIPTION
    WHY THIS EXISTS (2026-10-28). The midnight lane runs `codex exec --full-auto` (Run-DeskCycle.ps1),
    and Codex's Windows sandbox executes as restricted accounts in the local group
    CodexSandboxUsers. Those accounts used to write through the inherited BUILTIN\Users grant on
    C:\opt\quant. The ACL lock (RDP sitting step 6: /inheritance:d, Users reduced to RX) removes
    that path on purpose, so non-admin accounts cannot add files to the live desk. Without an
    explicit grant the lane would start, fail every write, and look like a lane that found nothing.

    THE GRANT IS SCOPED, NOT A RE-OPENING OF THE LOCK. Codex never needs to write the live working
    tree: the lane brief makes every change in a worktree (`git worktree add ..\quant-cro-<lane>`)
    and pushes from there. So exactly two paths get Modify:
      1. C:\opt\quant\.git          -- fetch, worktree bookkeeping, objects and refs for its commits
      2. C:\opt\quant-cro-midnight  -- the lane's own worktree (created here if absent)
    The live tree itself keeps the lock: CodexSandboxUsers stays at whatever the lock left (RX).

    FAILS LOUDLY. If the group does not exist (Codex never initialised its sandbox on this box),
    the script exits 2 and grants nothing; a guessed principal would print "No mapping between
    account names and security IDs" after a success line (docs/BOX_PERMISSIONS.md).

    REVERSIBLE. The ACLs of both paths are saved first; -Undo restores them.

.PARAMETER RepoRoot
    The live desk checkout. Default C:\opt\quant.

.PARAMETER Group
    The Codex sandbox group. Default CodexSandboxUsers.

.PARAMETER Undo
    Restore the ACLs saved by the last grant and exit.
#>
[CmdletBinding()]
param(
    [string] $RepoRoot = 'C:\opt\quant',
    [string] $Group = 'CodexSandboxUsers',
    [switch] $Undo
)
$ErrorActionPreference = 'Stop'

$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
         ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) { Write-Host 'FATAL: run in an elevated PowerShell'; exit 1 }

$GitDir   = Join-Path $RepoRoot '.git'
$Worktree = Join-Path (Split-Path $RepoRoot -Parent) 'quant-cro-midnight'
$Backup   = Join-Path $env:ProgramData 'quant-acl-backup'
New-Item -ItemType Directory -Force -Path $Backup | Out-Null

if ($Undo) {
    foreach ($p in @($GitDir, $Worktree)) {
        $bak = Join-Path $Backup ((Split-Path $p -Leaf) + '.acl')
        if (Test-Path $bak) {
            icacls (Split-Path $p -Parent) /restore $bak /C /Q
            "restored $p"
        } else { "no saved ACL for $p" }
    }
    exit 0
}

$g = Get-LocalGroup -Name $Group -ErrorAction SilentlyContinue
if (-not $g) {
    Write-Host "FATAL: local group '$Group' does not exist; Codex has not initialised its sandbox here. Nothing granted."
    exit 2
}
$sid = $g.SID.Value

if (-not (Test-Path $GitDir)) { Write-Host "FATAL: $GitDir missing"; exit 2 }
New-Item -ItemType Directory -Force -Path $Worktree | Out-Null

foreach ($p in @($GitDir, $Worktree)) {
    $bak = Join-Path $Backup ((Split-Path $p -Leaf) + '.acl')
    icacls $p /save $bak /T /C /Q | Out-Null
    icacls $p /grant "*${sid}:(OI)(CI)M" /T /C /Q
    if ($LASTEXITCODE -ne 0) { Write-Host "FATAL: grant on $p failed ($LASTEXITCODE)"; exit 3 }
}

"--- result ---"
icacls $GitDir
icacls $Worktree
"live tree (must NOT list $Group with M or F):"
icacls $RepoRoot | Select-String -SimpleMatch $Group
