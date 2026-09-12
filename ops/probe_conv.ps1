$ErrorActionPreference = "SilentlyContinue"
"== TASKS =="
Get-ScheduledTask -TaskName MT5-LocalConvert,MT5-ConvertSwarm,MT5-Gauntlet,MT5-Hourly,MT5-IntelShip | ForEach-Object { "{0,-16} {1}" -f $_.TaskName, $_.State }
"== RUN INFO =="
Get-ScheduledTaskInfo -TaskName MT5-LocalConvert,MT5-ConvertSwarm,MT5-Gauntlet,MT5-Hourly | ForEach-Object { "{0,-16} last={1} next={2}" -f $_.TaskName, $_.LastRunTime, $_.NextRunTime }
"== LOCAL_CANDIDATES =="
$lc = "C:\opt\quant\desks\mt5\data\hypotheses\local_candidates.json"
if (Test-Path $lc) {
  $f = Get-Item $lc
  "local_candidates.json {0:N0} bytes, written {1}" -f $f.Length, $f.LastWriteTime
  try {
    $d = Get-Content $lc -Raw | ConvertFrom-Json
    "candidates in file: {0}" -f $d.candidates.Count
  } catch { "parse failed: $($_.Exception.Message)" }
} else { "local_candidates.json MISSING" }
"== SURVIVORS DOCKET =="
$sv = "C:\opt\quant\desks\mt5\data\hypotheses\external_survivors.json"
if (Test-Path $sv) { $f = Get-Item $sv; "external_survivors.json {0:N0} bytes, written {1}" -f $f.Length, $f.LastWriteTime }
else { "external_survivors.json MISSING" }