# POST-REBOOT VERIFICATION. Run after the desk box restarts; prints one PASS/FAIL block.
# Everything here is READ-ONLY except re-enabling a task Windows left Disabled.
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
