$ErrorActionPreference = "SilentlyContinue"
"== GAUNTLET LAST RESULT =="
Get-ScheduledTaskInfo -TaskName MT5-Gauntlet | ForEach-Object { "last={0} result={1} next={2}" -f $_.LastRunTime, $_.LastTaskResult, $_.NextRunTime }
"== GAUNT LOG TAIL =="
$gl = Get-ChildItem "C:\opt\quant\desks\mt5\logs" -Filter "*gaunt*" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 3
foreach ($f in $gl) { "--- $($f.Name) ($($f.LastWriteTime)) ---"; Get-Content $f.FullName -Tail 6 }
"== UNIVERSAL SURVIVORS (the certifying authority file) =="
$u = "C:\opt\quant\desks\mt5\reports\UNIVERSAL_SURVIVORS.json"
if (Test-Path $u) { $f = Get-Item $u; "written {0}, {1:N0} bytes" -f $f.LastWriteTime, $f.Length } else { "MISSING" }