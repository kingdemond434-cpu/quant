# RUN THE DEEPSEEK CYCLE ON THE WINDOWS BOX, HEADLESS (2026-10-20).
#
# The cycle was written for a Linux systemd unit (`ops/quant-deepseek.timer`) and its model ids
# live in a bash file (`ops/free_tier.env`). On this box there is no systemd, no bash and no
# logged-in session at 03:00, so the organ ran only while somebody else's Linux box was up.
# This runner is the Windows half: it reads the same env file, runs the same cycle, appends the
# same log, and exits with the cycle's own code. A DARK seat is exit 0 by design; a policy
# failure is exit 2 and is meant to show as a failed task.
$ErrorActionPreference = 'Stop'

$Root = 'C:\opt\quant'
$Log = Join-Path $Root 'desks\mt5\logs\MT5-DeepSeek.log'
New-Item -ItemType Directory -Force -Path (Split-Path $Log) | Out-Null

$envFile = Join-Path $Root 'ops\free_tier.env'
if (Test-Path $envFile) {
    foreach ($line in Get-Content $envFile) {
        if ($line -match '^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)$') {
            $name = $Matches[1]
            $value = $Matches[2].Trim()
            if ($value.Length -ge 2 -and
                (($value[0] -eq '"' -and $value[-1] -eq '"') -or
                 ($value[0] -eq "'" -and $value[-1] -eq "'"))) {
                $value = $value.Substring(1, $value.Length - 2)
            }
            Set-Item -Path ("Env:" + $name) -Value $value
        }
    }
}

Set-Location $Root
$stamp = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
$utf8 = [System.Text.Encoding]::UTF8
[System.IO.File]::AppendAllText($Log, "=== deepseek cycle $stamp ===`r`n", $utf8)

# CAPTURE, THEN APPEND AS UTF-8. `Add-Content` and `>>` disagree about encoding on PowerShell 5.1
# (MEASURED 2026-10-20: the first live run wrote UTF-16, so the log read as NUL-spaced text).
$out = & py -3 scripts\run_deepseek_cycle.py --state NORMAL --json 2>&1 | Out-String
$rc = $LASTEXITCODE
[System.IO.File]::AppendAllText($Log, $out, $utf8)
[System.IO.File]::AppendAllText($Log, ("=== exit {0} at {1}Z ===`r`n" -f $rc, (Get-Date).ToUniversalTime().ToString('s')), $utf8)

$out -split "`r?`n" | Where-Object { $_ } | Select-Object -Last 4
exit $rc
