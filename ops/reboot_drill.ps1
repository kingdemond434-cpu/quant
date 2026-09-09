# POST-REBOOT VERIFICATION. Run after the desk box restarts; prints one PASS/FAIL block.
# Everything here is READ-ONLY except re-enabling a task Windows left Disabled.
#
# ON A CLOCK SINCE 2026-09-08 (Install-QuantWindows.ps1: MT5-RebootDrill, daily). Until then this
# ran only when a person remembered to, so a box that lost a task on reboot stayed that way until
# the next time somebody looked. Every run now leaves two records the issue board reads:
#   desks\mt5\reports\REBOOT_DRILL.json  -- the latest verdict (missing or stale = the drill has
#                                           stopped running, which the board grades STALLED)
#   data\REBOOT_DRILL_ALARM.txt          -- present only after a FAIL, first line the reason;
#                                           removed by the next PASS (the board's alarm contract)
$root = Split-Path -Parent $PSScriptRoot
$fail = @()
$term = Get-Process terminal64 -ErrorAction SilentlyContinue
if ($term) { "TERMINAL: running (pid " + $term.Id + ", up " + [math]::Round(((Get-Date) - $term.StartTime).TotalMinutes) + "m)" }
else { $fail += "terminal64 NOT running"; "TERMINAL: NOT RUNNING" }

$required = @('MT5-TerminalBoot','MT5-Gateway','MT5-Gauntlet','MT5-Shadow','MT5-Hourly',
              'MT5-DeskState','MT5-MoatRecorder','MT5-MoatSilver','MT5-StallWatch',
              'MT5-Universe','MT5-ShadowSync')
$present = (schtasks /Query /FO CSV | ConvertFrom-Csv | ForEach-Object { $_.TaskName -replace '^\\','' })
foreach ($r in $required) {
  if ($present -notcontains $r) { $fail += "task MISSING: $r"; "TASK $r : MISSING" }
  else {
    $st = (schtasks /Query /TN $r /FO CSV | ConvertFrom-Csv).Status
    if ($st -eq 'Disabled') { Enable-ScheduledTask -TaskName $r | Out-Null; "TASK $r : was Disabled -> re-enabled" }
    else { "TASK $r : $st" }
  }
}

# The live account read is published INSIDE desk_state.json by the 5-minute state builder
# (account_state.json was an older path that no longer exists) -- source_age_seconds is the
# terminal's own freshness, which is what a reboot must restore.
try {
  $d = Get-Content C:\opt\quant\web\desk_state.json -Raw | ConvertFrom-Json
  $age = [double]$d.account.source_age_seconds
  if ($age -gt 900) { $fail += "account source $([math]::Round($age))s stale -- terminal is up but not feeding" }
  "ACCOUNT SOURCE: $([math]::Round($age))s old (venue " + $d.account.venue + ", equity " + $d.account.equity + ")"
} catch { $fail += "desk_state account unreadable"; "ACCOUNT SOURCE: unreadable" }

if ($fail.Count -eq 0) { "`nREBOOT DRILL: PASS -- terminal, tasks and account read all recovered" }
else { "`nREBOOT DRILL: FAIL"; $fail | ForEach-Object { "  - $_" } }

# THE RECORD, so the verdict reaches the issue board rather than a console nobody reads.
$stamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
$verdict = if ($fail.Count -eq 0) { "PASS" } else { "FAIL" }
$drillJson = Join-Path $root "desks\mt5\reports\REBOOT_DRILL.json"
$alarm = Join-Path $root "data\REBOOT_DRILL_ALARM.txt"
try {
  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $drillJson) | Out-Null
  @{ checked_at = $stamp; verdict = $verdict; failures = @($fail); required = @($required)
     terminal_running = [bool]$term } | ConvertTo-Json -Depth 4 | Set-Content -Path $drillJson -Encoding UTF8
  if ($fail.Count -eq 0) {
    Remove-Item -Path $alarm -ErrorAction SilentlyContinue
  } else {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $alarm) | Out-Null
    $body = @("REBOOT DRILL FAIL $stamp -- " + ($fail -join "; ")) + ($fail | ForEach-Object { "  - $_" })
    Set-Content -Path $alarm -Value $body -Encoding UTF8
  }
} catch { "RECORD: could not write the drill record ($($_.Exception.Message))" }
