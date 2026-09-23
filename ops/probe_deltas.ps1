$ErrorActionPreference = "SilentlyContinue"
"== LAST 20 CERTIFICATION DELTAS =="
$gl = "C:\opt\quant\desks\mt5\logs\MT5-Gauntlet.log"
Select-String -Path $gl -Pattern "Updated UNIVERSAL_SURVIVORS" | Select-Object -Last 12 | ForEach-Object { $_.Line }
"== INPUT-FAIL COUNTS LAST RUN =="
$tail = Get-Content $gl -Tail 500
"INPUT-FAIL lines in last 500: {0}" -f ($tail | Where-Object { $_ -match "INPUT-FAIL" } | Measure-Object).Count
"== GAUNTLET EXIT LINES =="
$tail | Where-Object { $_ -match "update-done|RUN-DONE|completed|fell through|union" } | Select-Object -Last 6