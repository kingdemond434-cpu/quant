# THE CORE PASS HAS NEVER ONCE REACHED ITS OWN EPILOGUE (measured 2026-09-24).
#
# `desks\mt5\logs\MT5-HourlyCore.log` carries 16 pass STARTS -- each prints
# `leg rotation plan=core roster=113/330 admitted=NN deferred=NN budget=1920s planned=1920s` --
# and ZERO pass completions: not one `leg rotation recorded:` line exists in the whole file.
# Every pass is killed where it stands at ExecutionTimeLimit=PT40M, which is exactly the shape
# that lost the judge 65 fully-passed cells: work computed, killed before it writes.
#
# THE ARITHMETIC, AND WHY IT COULD NOT WORK. `leg_rotation.budget_for("core")` plans into
# 2400 s x BUDGET_FILL(0.80) = 1920 s, and the logs show it filling that budget exactly, every
# pass. That leaves 480 s -- eight minutes -- of slack for EVERYTHING the plan does not price:
# interpreter start on a 4,800-line module, the desk-memory injection, and above all the fact
# that a leg's ledger median was measured on a box whose processor is 92-99% saturated, so legs
# systematically cost MORE than the median they are admitted on. Eight minutes of slack against
# ~30 admitted legs is about sixteen seconds of overrun each.
#
# WHICH DIRECTION TO FIX IT IN. Lowering BUDGET_FILL would make each pass fit by admitting fewer
# legs -- that is buying completion with research, and the standing order is that the desk never
# reduces its aggressiveness. So the WINDOW moves, not the work:
#
#   ExecutionTimeLimit PT40M -> PT55M   the pass gets 15 more minutes
#   HOURLY_BUDGET_S=2640                the rotation plans into 3300 x 0.80 instead of 2400 x 0.80
#
# `budget_for` already reads HOURLY_BUDGET_S from the environment ahead of its own constant, so
# this needs no code change and `libs/ops/leg_rotation.py` is not touched. The trigger stays
# hourly at :36 and MultipleInstancesPolicy stays IgnoreNew, so a pass that still overruns is
# refused rather than stacked -- 55 minutes ends at :31, five minutes clear of the next trigger.
#
# MORE LEGS PER PASS, NOT FEWER: 2,640 s of admitted work against 1,920 s is a 37% larger
# admitted set every hour, and the deferred legs still lead the next pass exactly as before.

param([switch]$DryRun)

$ErrorActionPreference = 'Stop'

$t = Get-ScheduledTask -TaskName 'MT5-HourlyCore'
$beforeLimit = $t.Settings.ExecutionTimeLimit
$beforeArgs = $t.Actions[0].Arguments
Write-Output ("before: limit=" + $beforeLimit)
Write-Output ("before: args=" + $beforeArgs)

if ($beforeArgs -match 'HOURLY_BUDGET_S') {
  $newArgs = $beforeArgs
  Write-Output 'args already carry HOURLY_BUDGET_S; leaving them'
} else {
  $newArgs = $beforeArgs -replace 'set HOURLY_PLAN=core&&', 'set HOURLY_PLAN=core&& set HOURLY_BUDGET_S=2640&&'
}

if ($DryRun) {
  Write-Output ("DRYRUN would set limit PT55M and args=" + $newArgs)
} else {
  $t.Settings.ExecutionTimeLimit = 'PT55M'
  $t.Actions[0].Arguments = $newArgs
  Set-ScheduledTask -InputObject $t | Out-Null
  $a = Get-ScheduledTask -TaskName 'MT5-HourlyCore'
  Write-Output ("after:  limit=" + $a.Settings.ExecutionTimeLimit)
  Write-Output ("after:  args=" + $a.Actions[0].Arguments)
}
