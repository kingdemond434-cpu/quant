# REGISTER THE BOX'S PULL, AND RUN IT NOW (2026-09-08).
#
# THE GAP. Install-QuantWindows.ps1 registers MT5-AdoptRelease among ~twenty other tasks, and
# re-running the whole installer on a box whose tasks are live re-registers every one of them
# -- which on this box has already failed with "Access is denied" against the S4U principals.
# The adoption itself is one task and it is the ONLY thing standing between a day of fixes on
# origin and the gateway that runs them, so it gets the same single-task installer the moat
# miner and the contract terms got: idempotent, one file, no other task touched.
#
# WHAT IT DOES. Registers MT5-AdoptRelease -- hourly at :20, after the :05 ShadowSync slot has
# committed the box's state and before the research legs at the top of the next hour read code
# -- pointing at Adopt-And-Seal.ps1, which lands the branch's tree in place (the box's own
# state kept), re-seals when HEAD is not the sealed code, commits RELEASE.json alone, and
# restarts MT5-Gateway on the new seal. Then STARTS it, so the first adoption happens now
# rather than at the next :20, and prints the task's state and last result so the run can be
# read from the same window that launched it.
#
# Mirrors the installer's block exactly (test_the_standalone_installer_agrees_with_the_full_one
# pins the two to each other): same name, same script, same cadence, same limits, same
# principal shape.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File desks\mt5\scripts\install_adopt_release_task.ps1

$ErrorActionPreference = 'Stop'

$TaskName = 'MT5-AdoptRelease'
$DeskRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Script   = Join-Path $DeskRoot 'scripts\Adopt-And-Seal.ps1'
if (-not (Test-Path $Script)) { throw "Adopt-And-Seal.ps1 missing at $Script" }

$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument `
    ("-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"{0}`"" -f $Script)

$trigger = New-ScheduledTaskTrigger -Once -At ((Get-Date).Date.AddMinutes(20)) `
    -RepetitionInterval (New-TimeSpan -Hours 1) `
    -RepetitionDuration (New-TimeSpan -Days 3650)

# StartWhenAvailable so an hour missed to a reboot is caught up rather than silently skipped;
# IgnoreNew so a slow adoption is never stacked on itself; twenty minutes because an adoption
# that takes longer is a box that needs the log read, not a second adoption.
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 2) `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 20) -MultipleInstances IgnoreNew

# The same principal shape as MT5-ShadowSync, the task whose commits this one follows: the
# logged-on user, interactive, limited. Adoption writes files and runs git; it needs nothing
# more, and a task that asks for more than it needs is the one that fails to register.
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings `
    -Description "Adopt the branch's code in place, re-seal the release, restart the gateway on the new seal." | Out-Null

$t = Get-ScheduledTask -TaskName $TaskName
"installed {0}: state={1} interval={2}" -f $t.TaskName, $t.State, $t.Triggers[0].Repetition.Interval

# THE FIRST ADOPTION IS NOW. Waiting for :20 is another hour of the gateway on the old tree.
Start-ScheduledTask -TaskName $TaskName
Start-Sleep -Seconds 5
$i = Get-ScheduledTaskInfo -TaskName $TaskName
"started {0}: state={1} last_run={2} last_result={3}" -f $TaskName, (Get-ScheduledTask -TaskName $TaskName).State, $i.LastRunTime, $i.LastTaskResult
"log: desks\mt5\logs\MT5-AdoptRelease.log is not written by the task itself; read the task history, or run Adopt-And-Seal.ps1 by hand to watch it."
