$ErrorActionPreference = "SilentlyContinue"
"== HOURLY + CONVERT SWARM STATUS =="
Get-ScheduledTaskInfo -TaskName MT5-Hourly,MT5-ConvertSwarm,MT5-LocalConvert | ForEach-Object { "{0,-16} last={1} result={2} next={3}" -f $_.TaskName, $_.LastRunTime, $_.LastTaskResult, $_.NextRunTime }
"== BROKEN POOL CRASH FREQUENCY (today) =="
$gl = "C:\opt\quant\desks\mt5\logs\MT5-Gauntlet.log"
if (Test-Path $gl) {
  $hits = Select-String -Path $gl -Pattern "BrokenProcessPool" 
  "BrokenProcessPool occurrences: {0}" -f $hits.Count
  $hits | Select-Object -Last 3 | ForEach-Object { "  {0}: line {1}" -f $_.Filename, $_.LineNumber }
  "--- tail of gauntlet log ---"
  Get-Content $gl -Tail 4
} else { "MT5-Gauntlet.log missing" }
"== GAUNTLET SCRIPT VERSION/ENERGY TRACES =="
$tail = Get-Content "C:\opt\quant\desks\mt5\logs\MT5-Gauntlet.log" -Tail 40
$tail -match "Traceback|Error|SURVIV|certified|survivor" | ForEach-Object { $_ }