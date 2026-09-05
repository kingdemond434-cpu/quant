# Give every RESEARCH scheduled task a live log.
#
# WHY. Python block-buffers stdout when it is redirected to a file, so a task that runs for an
# hour writes nothing until it exits -- and nothing at all if it is killed. Measured 2026-08-28:
# MT5-Gauntlet's log had no line for the entire duration of a running sweep, so the only
# available progress signal for a job in flight was its cache writes. That is the blind spot
# that made an 87-minute thrashing sweep indistinguishable from a healthy one, and it is the
# same defect the hourly controller had on the research box.
#
# A log that only appears on success cannot report a failure in progress. -u costs nothing here:
# these are IO-light jobs whose output is a few hundred lines an hour.
#
# THE MONEY PATH IS NOT TOUCHED. Gateway, deadman and the terminal boot task are excluded by
# name -- not because -u would harm them, but because nothing on the order path gets modified
# by an automated sweep over "every task matching a pattern". That rule has no exceptions worth
# the risk of discovering one.

$excluded = @('MT5-Gateway', 'MT5-FusionDeadman', 'MT5-TerminalBoot')
$changed = @()

foreach ($task in (Get-ScheduledTask | Where-Object { $_.TaskName -like 'MT5-*' })) {
  if ($excluded -contains $task.TaskName) { continue }
  $acts = @($task.Actions)
  if ($acts.Count -ne 1) { continue }
  $a = $acts[0]
  if (-not $a.Arguments) { continue }
  # Only python invocations, and only ones not already unbuffered.
  if ($a.Arguments -notmatch 'python\.exe"?\s') { continue }
  if ($a.Arguments -match 'python\.exe"?\s+(-\w+\s+)*-u\b') { continue }

  $new = $a.Arguments -replace '(python\.exe"?)(\s+)', '$1 -u$2'
  if ($new -eq $a.Arguments) { continue }

  $act = New-ScheduledTaskAction -Execute $a.Execute -Argument $new
  try {
    Set-ScheduledTask -TaskName $task.TaskName -Action $act -ErrorAction Stop | Out-Null
    $changed += $task.TaskName
  } catch {
    Write-Output ("FAILED " + $task.TaskName + ": " + $_.Exception.Message)
  }
}

if ($changed.Count -gt 0) {
  Write-Output ("unbuffered: " + ($changed -join ', '))
} else {
  Write-Output "no task needed changing (all research tasks already unbuffered)"
}
