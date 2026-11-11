# GATE CLONE WATCHDOG -- THE MERGE GATE'S CLONE IS REBUILT WITHOUT A PERSON (2026-11-11).
#
# THE JAM. Quant-WorkflowGate keeps a stateless clone of LIVE in C:\ProgramData\QuantBox\gate-repo.
# A stale .git\objects\maintenance.lock (left 11-05 by an elevated run) made every sweep from
# 23:40Z 11-10 die with "sparse-checkout failed (128)" before any merge. About 40 CLEARed PRs froze
# for ~10 h and zuck had to paste an administrator block to delete the folder by hand.
#
# WHY A TASK OF ITS OWN. #901 does the same heal inside Adopt-And-Seal (SYSTEM), but adoption can
# itself be blocked (ReleaseAuthority rc 2 on a stale ROOT_PIN blocked it the same night), and then
# the heal never runs. This task runs as SYSTEM every 15 minutes whatever adoption is doing.
#
# WHAT IT DOES, AND ONLY UNDER ALL OF THESE (the #901 conditions, unchanged):
#   - the gate's heartbeat (logs\workflow_gate.json) is rc 1 with a clone-refresh failure note,
#   - the last three FAILED lines of logs\workflow_gate.log are all that class,
#   - no reparse point (junction/symlink) at or anywhere under gate-repo,
#   - the gate's own mutex (Global\QuantBox-WorkflowGate) is free -- no sweep is running.
# Then it removes gate-repo (the clone holds no state: the next sweep clones LIVE from origin) and
# starts Quant-WorkflowGate so the train moves on this pass, not in ten minutes. It removes nothing
# else, never touches bin\ or logs\, never touches C:\opt\authority, the pin, the key or a ledger.
# It also ends a HUNG MergeDocket run (section 1). Every pass writes logs\gate_clone_watchdog.json (verdict, reason, what it did) for the pagers.
#
# NOT A BYPASS. The folder is the gate's own cache, rebuilt bit-for-bit from origin; no gate, check,
# CLEAR or veto window changes. The SYSTEM account already owns this heal under #901.
param([switch]$DryRun)

$ErrorActionPreference = 'Stop'
$qb = Join-Path $env:ProgramData 'QuantBox'
$gateRepo = Join-Path $qb 'gate-repo'
$beatPath = Join-Path $qb 'logs\workflow_gate.json'
$gateLog = Join-Path $qb 'logs\workflow_gate.log'
$outPath = Join-Path $qb 'logs\gate_clone_watchdog.json'
$cloneFail = 'FAILED: (git clone|sparse-checkout|sparse config|git fetch|git checkout) failed'

function Write-Beat([string]$verdict, [string]$why, [string]$did) {
    $doc = [ordered]@{
        at = (Get-Date).ToUniversalTime().ToString('o'); verdict = $verdict; why = $why; did = $did
        merge_docket = $script:ReapNote
        dry_run = [bool]$DryRun
    }
    try {
        $tmp = "$outPath.tmp"
        ($doc | ConvertTo-Json -Compress) | Set-Content -LiteralPath $tmp -Encoding UTF8
        Move-Item -LiteralPath $tmp -Destination $outPath -Force
    } catch { }
    "gate_clone_watchdog: $verdict -- $why$(if ($did) { " ($did)" })"
}

# ------------------------------------------------------------- 1. A HUNG MERGE DOCKET IS ENDED
# 2026-11-11: MT5-MergeDocket's python (pid 36280) had hung since 11-09 and survived
# Stop-ScheduledTask; the Judge's intake stalled behind it. #882 gives merge_hypotheses a 12 h wall
# for runs that start on its code; a run that predates it, or hangs where the wall cannot fire, is
# ended here -- but ONLY when it is BOTH older than the wall plus an hour AND has used no CPU
# across two passes (30 min). A process making no CPU progress is not mid-write, so the append-only
# preregistrations.jsonl is never torn by this (#882 waits up to 30 min for its own writes).
$reapState = Join-Path $qb 'logs\gate_clone_watchdog_reap.json'
$reapAgeH = 13
$reaped = @()
try {
    $prev = @{}
    if (Test-Path -LiteralPath $reapState) {
        (Get-Content -Raw -LiteralPath $reapState | ConvertFrom-Json).PSObject.Properties | ForEach-Object { $prev[$_.Name] = $_.Value }
    }
    $seen = [ordered]@{}
    $procs = @(Get-CimInstance Win32_Process -Filter "Name like 'python%'" |
               Where-Object { "$($_.CommandLine)" -match 'merge_hypotheses\.py' })
    foreach ($p in $procs) {
        $ageH = ((Get-Date) - $p.CreationDate).TotalHours
        $cpu = [double]($p.KernelModeTime + $p.UserModeTime)
        $key = "$($p.ProcessId)@$($p.CreationDate.ToUniversalTime().ToString('o'))"
        $was = $prev[$key]
        $still = if ($was -and [double]$was.cpu -eq $cpu) { [int]$was.flat + 1 } else { 0 }
        $seen[$key] = [ordered]@{ cpu = $cpu; flat = $still; age_h = [math]::Round($ageH, 1) }
        if ($ageH -gt $reapAgeH -and $still -ge 2 -and -not $DryRun) {
            & taskkill.exe /PID $p.ProcessId /T /F | Out-Null
            $reaped += "pid $($p.ProcessId) ($([math]::Round($ageH, 1)) h old, no CPU for $still passes; taskkill rc $LASTEXITCODE)"
        }
    }
    ($seen | ConvertTo-Json -Compress) | Set-Content -LiteralPath $reapState -Encoding UTF8
} catch {
    $reaped += "merge-docket check skipped: $($_.Exception.Message)"
}
$script:ReapNote = ($reaped -join '; ')

# ------------------------------------------------------------- 2. THE GATE'S JAMMED CLONE
try {
    if (-not (Test-Path -LiteralPath $gateRepo)) { Write-Beat 'OK' 'no gate-repo yet; the next sweep clones it' ''; exit 0 }
    if (-not ((Test-Path -LiteralPath $beatPath) -and (Test-Path -LiteralPath $gateLog))) {
        Write-Beat 'UNMEASURED' 'the gate has no heartbeat or log yet' ''; exit 0
    }
    $beat = Get-Content -Raw -LiteralPath $beatPath | ConvertFrom-Json
    $fails = @(Get-Content -LiteralPath $gateLog -Tail 400 | Where-Object { $_ -match ' FAILED: ' } | Select-Object -Last 3)
    $jammed = ([int]$beat.rc -eq 1) -and ("$($beat.note)" -match $cloneFail) -and $fails.Count -eq 3 -and
              (@($fails | Where-Object { $_ -match $cloneFail }).Count -eq 3)
    if (-not $jammed) { Write-Beat 'OK' "gate not jammed (rc $($beat.rc))" ''; exit 0 }

    $item = Get-Item -LiteralPath $gateRepo -Force
    # PowerShell 5.1's Remove-Item -Recurse can follow a junction INSIDE the folder (#901 audit SF1).
    $links = @(Get-ChildItem -LiteralPath $gateRepo -Force -Recurse -ErrorAction SilentlyContinue |
               Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint } | Select-Object -First 1)
    if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -or $links.Count -gt 0) {
        Write-Beat 'REFUSED' 'gate-repo is or holds a junction or symlink; not removing' ''; exit 3
    }
    if ($DryRun) { Write-Beat 'JAMMED' "$($beat.note)" 'dry run: would remove gate-repo and start Quant-WorkflowGate'; exit 0 }

    $gm = New-Object System.Threading.Mutex($false, 'Global\QuantBox-WorkflowGate')
    $removed = $false
    try {
        if (-not $gm.WaitOne(0)) { Write-Beat 'JAMMED' "$($beat.note)" 'a sweep holds the gate mutex; next pass'; exit 0 }
        try {
            Remove-Item -LiteralPath $gateRepo -Recurse -Force -ErrorAction Stop
            $removed = $true
        } finally { $gm.ReleaseMutex() }
    } finally { $gm.Dispose() }
    if ($removed) {
        & schtasks.exe /Run /TN 'Quant-WorkflowGate' | Out-Null
        Write-Beat 'HEALED' "$($beat.note)" "removed gate-repo; started Quant-WorkflowGate (rc $LASTEXITCODE)"
    }
    exit 0
} catch {
    Write-Beat 'FAILED' $_.Exception.Message ''
    exit 1
}
