# Registers the 24/7 YouTube channel miner as a per-user scheduled task (no admin needed).
# Runs every 30 minutes forever and survives reboots (task re-fires at logon + on schedule).
# Each run: discover new channels, backfill every channel's history, pick up new uploads.
# Polite: one request at a time, 6-9 s apart; first 429 / bot wall stops the run and later runs
# stay idle for 90 minutes (backoff), then resume. No cookies, proxies or logins.
#
# Usage (from the folder holding mine_channel_transcripts.py and the channels config):
#   powershell -ExecutionPolicy Bypass -File install_video_miner_task.ps1 [-Config channels.json]
param(
  [string]$Dir = $PSScriptRoot,
  [string]$Config = "channels.json",
  [int]$EveryMinutes = 30,
  [int]$LimitPerRun = 150
)
$ErrorActionPreference = "Stop"
$py = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $py) { $py = (Get-Command py -ErrorAction Stop).Source }
$script = Join-Path $Dir "mine_channel_transcripts.py"
if (-not (Test-Path $script)) { throw "missing $script" }
$log = Join-Path $Dir "run.log"
$cmd = "/c cd /d `"$Dir`" && `"$py`" `"$script`" --config `"$Config`" --discover --sleep 6 --limit $LimitPerRun >> `"$log`" 2>&1"

$action  = New-ScheduledTaskAction -Execute "cmd.exe" -Argument $cmd -WorkingDirectory $Dir
$t1 = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
        -RepetitionInterval (New-TimeSpan -Minutes $EveryMinutes)
$t2 = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable `
        -ExecutionTimeLimit (New-TimeSpan -Hours 6) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName "Quant-VideoMiner" -Action $action -Trigger @($t1, $t2) `
        -Settings $settings -Description "24/7 YouTube channel transcript miner (public captions only)" -Force | Out-Null
Write-Host "Registered Quant-VideoMiner: every $EveryMinutes min + at logon. Log: $log"
