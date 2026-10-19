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
Add-Content -Path $Log -Value "=== deepseek cycle $stamp ==="

& py -3 scripts\run_deepseek_cycle.py --state NORMAL --json *>> $Log
$rc = $LASTEXITCODE

Add-Content -Path $Log -Value ("=== exit {0} at {1} ===" -f $rc, (Get-Date).ToUniversalTime().ToString('s') + 'Z')
Get-Content $Log -Tail 6
exit $rc
