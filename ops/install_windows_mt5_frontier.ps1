param(
    [string]$Script = "C:\Users\dell\quant-conversion-fix\ops\run_windows_mt5_frontier.ps1",
    [string]$TaskName = "QuantMT5Frontier",
    [string]$At = "01:15"
)

$ErrorActionPreference = "Stop"
if (!(Test-Path $Script)) { throw "MT5 frontier script missing: $Script" }
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument (
    "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$Script`""
)
$trigger = New-ScheduledTaskTrigger -Daily -At $At
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 10) -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 10)
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal -Description `
    "Daily read-only MT5 universe ingest, discovery, VPS shadow publication; no execution authority" -Force | Out-Null
$task = Get-ScheduledTask -TaskName $TaskName
if ($task.State -eq "Disabled") { Enable-ScheduledTask -TaskName $TaskName | Out-Null }
Write-Output "INSTALLED $TaskName daily $At; state=$((Get-ScheduledTask -TaskName $TaskName).State)"
