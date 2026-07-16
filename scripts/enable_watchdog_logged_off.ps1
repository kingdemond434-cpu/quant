# Enable QuantWatchdog to run whether logged on or not (+ at startup). Must run elevated.
# Launch via:  Start-Process powershell -Verb RunAs -ArgumentList '-ExecutionPolicy','Bypass','-File','C:\Users\dell\quant-platform\scripts\enable_watchdog_logged_off.ps1'
$ErrorActionPreference = "Stop"
$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) {
    Write-Host "NOT ELEVATED. Close this and relaunch via the Start-Process ... -Verb RunAs command." -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit 1
}
try {
    $exe = "C:\Users\dell\quant-platform\.venv\Scripts\pythonw.exe"
    $arg = "C:\Users\dell\quant-platform\scripts\watchdog.py"
    $action    = New-ScheduledTaskAction -Execute $exe -Argument $arg -WorkingDirectory "C:\Users\dell\quant-platform"
    $t1 = New-ScheduledTaskTrigger -AtStartup
    $t2 = New-ScheduledTaskTrigger -Once -At (Get-Date)
    $t2.Repetition = (New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 3)).Repetition
    $principal = New-ScheduledTaskPrincipal -UserId "dell" -LogonType S4U -RunLevel Limited
    $settings  = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -MultipleInstances IgnoreNew
    Register-ScheduledTask -TaskName QuantWatchdog -Action $action -Trigger $t1,$t2 -Principal $principal -Settings $settings -Force | Out-Null
    New-Item -ItemType File -Path "C:\Users\dell\quant-platform\data\.watchdog_logged_off" -Force | Out-Null
    Start-ScheduledTask -TaskName QuantWatchdog
    $lt = (Get-ScheduledTask -TaskName QuantWatchdog).Principal.LogonType
    Write-Host ("DONE - LogonType is now " + $lt + " (runs whether logged on + at startup).") -ForegroundColor Green
} catch {
    Write-Host ("FAILED: " + $_.Exception.Message) -ForegroundColor Red
}
Read-Host "Press Enter to close"
