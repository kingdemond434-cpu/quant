<#
.SYNOPSIS
    Move MT5-MoatRecorder and MT5-MoatRecorder-Watchdog into the interactive logon session.
    Idempotent; touches only these two tasks' principal.

.DESCRIPTION
    Both run desks\moat\moat_recorder.py, which reads the Fusion terminal. As SYSTEM they ran in
    Session 0, and after the 2026-11-12 reboot their bare mt5.initialize() launched the Fusion
    terminal headless there with no login, darkening Fusion and fencing E8 (PR #1089). The recorder
    now attaches through research.mt5_session, which never launches from Session 0 -- so as SYSTEM
    it would only exit. MetaTrader5 attaches to a running terminal from the desktop session of the
    user who runs it, so the tasks run as that user, interactive, at the run level they had.

    Actions and triggers are kept as registered; only the principal changes.

        powershell -NoProfile -ExecutionPolicy Bypass -File desks\mt5\scripts\install_moat_recorder_interactive.ps1
#>
[CmdletBinding()]
param(
    [string] $InteractiveUser = "Administrator",
    [switch] $DryRun
)
$ErrorActionPreference = "Stop"

$principal = New-ScheduledTaskPrincipal -UserId $InteractiveUser -LogonType Interactive -RunLevel Highest
foreach ($name in @("MT5-MoatRecorder", "MT5-MoatRecorder-Watchdog")) {
    $t = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
    if (-not $t) { Write-Host "  [SKIP] $name is not registered"; continue }
    if ($t.Principal.UserId -eq $InteractiveUser -and $t.Principal.LogonType -eq "Interactive") {
        Write-Host "  [OK  ] $name already runs as $InteractiveUser (interactive)"
        continue
    }
    if ($DryRun) { Write-Host "  [DRY ] $name would move from $($t.Principal.UserId) to $InteractiveUser (interactive)"; continue }
    Set-ScheduledTask -TaskName $name -Principal $principal | Out-Null
    Write-Host "  [OK  ] $name moved from $($t.Principal.UserId) to $InteractiveUser (interactive)"
}
