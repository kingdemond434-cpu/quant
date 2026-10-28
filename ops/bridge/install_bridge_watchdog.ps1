# REGISTER THE BOX BRIDGE'S WATCHDOG, AND START IT NOW (2026-10-28).
#
# The bridge (`claude remote-control` in C:\opt\bridge\quant) was started by hand in the RDP
# session and died minutes later; nothing brought it back but zuck. This registers ONE task,
# Claude-Bridge-Watchdog, that runs ops\bridge\bridge_watchdog.ps1 at this user's logon and
# re-arms it every five minutes (the watchdog's own mutex makes a re-arm a no-op while it lives).
# The watchdog keeps the server running and restarts it whenever it exits.
#
# WHY A COPY OUTSIDE THE CHECKOUT. Sessions on the bridge check out branches in C:\opt\bridge\quant.
# The task runs C:\opt\bridge\bin\bridge_watchdog.ps1, copied here, so a branch switch in the
# checkout never changes or removes the script that keeps the bridge alive. Re-run this installer to
# update it.
#
# WHY INTERACTIVE, AND WHAT A REBOOT STILL NEEDS. The server uses this user's Claude sign-in and the
# FTMO terminal already needs this user's desktop session, so the task runs as this user,
# interactive, at the run level the bridge runs at today (elevated Administrator). After a reboot
# the bridge comes back at the first logon of this user (one RDP connect + Disconnect, which the
# FTMO terminal needs anyway). Coming back with nobody logged on would need Windows auto-logon,
# which stores this account's password on the box; that is not done here.
#
# Idempotent; touches no other task. Read the result with ops\bridge\bridge_status.ps1.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File ops\bridge\install_bridge_watchdog.ps1

[CmdletBinding()]
param(
    [string] $Checkout = "C:\opt\bridge\quant",
    [string] $BinDir = "C:\opt\bridge\bin"
)
# Highest, not a choice: the bin folder below is Administrators + SYSTEM only, so a limited token
# could not even read the script it runs.
$RunLevel = "Highest"
$ErrorActionPreference = 'Stop'

$TaskName = 'Claude-Bridge-Watchdog'
$src = Join-Path $PSScriptRoot 'bridge_watchdog.ps1'
if (-not (Test-Path $src)) { throw "bridge_watchdog.ps1 missing at $src" }
# THE FOLDER THE ELEVATED TASK RUNS FROM IS ADMIN-ONLY. A new folder under C:\ inherits a DACL that
# normally lets Authenticated Users modify it, which would make this a writable script run
# elevated. Inheritance is cut and only Administrators and SYSTEM keep any right; the watchdog
# also refuses to run when its own sha256 differs from the pin written next to it here.
New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
& icacls.exe $BinDir /inheritance:r /grant:r "*S-1-5-32-544:(OI)(CI)F" "*S-1-5-18:(OI)(CI)F" | Out-Null
if ($LASTEXITCODE -ne 0) { throw "icacls could not restrict $BinDir (exit $LASTEXITCODE)" }
& icacls.exe $BinDir /setowner "*S-1-5-32-544" /T | Out-Null
$acl = (Get-Acl $BinDir).Access | Where-Object { $_.AccessControlType -eq 'Allow' } |
    ForEach-Object { $_.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value }
$extra = @($acl | Where-Object { $_ -notin @('S-1-5-32-544', 'S-1-5-18') })
if ($extra.Count -gt 0) { throw "$BinDir still grants $($extra -join ', '); not installing" }
$dst = Join-Path $BinDir 'bridge_watchdog.ps1'
Copy-Item -Path $src -Destination $dst -Force
$sha = (Get-FileHash $dst -Algorithm SHA256).Hash.ToLower()
Set-Content -Path (Join-Path $BinDir 'watchdog.sha256') -Value $sha -Encoding ascii
"copied {0} -> {1} (sha256 {2}); {3} is Administrators + SYSTEM only" -f $src, $dst, $sha.Substring(0, 12), $BinDir

$user = "{0}\{1}" -f $env:USERDOMAIN, $env:USERNAME
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument `
    ('-NoProfile -NonInteractive -WindowStyle Minimized -ExecutionPolicy Bypass -File "{0}" -Checkout "{1}"' -f $dst, $Checkout)

# AT LOGON, AND A DAILY TRIGGER REPEATING EVERY FIVE MINUTES FOR ONE DAY -- never a -Once trigger with
# a long duration: the desk measured one fold into P9D and expire (install_adopt_release_task.ps1).
$atLogon = New-ScheduledTaskTrigger -AtLogOn -User $user
$rearm = New-ScheduledTaskTrigger -Daily -At ((Get-Date).Date)
$rearm.Repetition = (New-ScheduledTaskTrigger -Once -At ((Get-Date).Date) `
    -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration (New-TimeSpan -Days 1)).Repetition

# No time limit: the watchdog is meant to run for as long as the session lives. IgnoreNew so a
# re-arm never stacks a second copy; the mutex inside is the second lock.
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Seconds 0) -MultipleInstances IgnoreNew `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)

$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel $RunLevel

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger @($atLogon, $rearm) `
    -Principal $principal -Settings $settings `
    -Description "Keep the box bridge (claude remote-control in $Checkout) running; restart it when it exits." | Out-Null

Start-ScheduledTask -TaskName $TaskName
Start-Sleep -Seconds 8
$i = Get-ScheduledTaskInfo -TaskName $TaskName
"installed {0}: state={1} last_run={2} last_result={3}" -f $TaskName, (Get-ScheduledTask -TaskName $TaskName).State, $i.LastRunTime, $i.LastTaskResult
$beat = 'C:\opt\bridge\logs\bridge_watchdog.json'
if (Test-Path $beat) { "heartbeat: " + ((Get-Content $beat -Raw | ConvertFrom-Json) | ConvertTo-Json -Compress) }
