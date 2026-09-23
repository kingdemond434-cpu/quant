$ErrorActionPreference = "SilentlyContinue"
"== GAUNTLET TRIGGERS =="
Get-ScheduledTask -TaskName MT5-Gauntlet | ForEach-Object { $_.Triggers | ForEach-Object { "repeat={0} once={1}" -f $_.Repetition.Interval, $_.StartBoundary } }
"== INTEL INTAKE SIZE =="
$n = (Get-ChildItem -Recurse -File "C:\opt\quant\data\intelligence","C:\opt\quant\desks\mt5\data\intelligence" -ErrorAction SilentlyContinue | Measure-Object).Count
"intelligence files: $n"
"== RECENT INTAKE COPIES (VPS-shipped fingerprint) =="
Get-ChildItem -Recurse -File "C:\opt\quant\desks\mt5\data\intelligence" -ErrorAction SilentlyContinue | Where-Object { $_.LastWriteTime -gt (Get-Date).AddHours(-2) } | Measure-Object | ForEach-Object { "boxes touched in last 2h: $($_.Count)" }
"== GAUNT CURSOR/VERDICTS =="
$gc = "C:\opt\quant\desks\mt5\data\hypotheses\gauntlet_build_cursor.json"
if (Test-Path $gc) { $f = Get-Item $gc; "gauntlet cursor written {0}" -f $f.LastWriteTime }
$sv = Get-Content "C:\opt\quant\desks\mt5\data\hypotheses\external_survivors.json" -Raw | ConvertFrom-Json
"external_survivors entries: $($sv.Count)"