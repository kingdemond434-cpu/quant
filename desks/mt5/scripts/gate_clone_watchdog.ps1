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
# It also ends a HUNG MergeDocket run (section 2, AFTER the heal, its CIM query bounded). Every pass writes logs\gate_clone_watchdog.json (verdict, reason, what it did) for the pagers.
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
$reapState = Join-Path $qb 'logs\gate_clone_watchdog_reap.json'
$cloneFail = 'FAILED: (git clone|sparse-checkout|sparse config|git fetch|git checkout) failed'

function Write-Atomic([string]$path, [string]$text) {
    $tmp = "$path.tmp"
    [System.IO.File]::WriteAllText($tmp, $text, (New-Object System.Text.UTF8Encoding($false)))
    Move-Item -LiteralPath $tmp -Destination $path -Force
}

# ------------------------------------------------------------- 1. THE GATE'S JAMMED CLONE (FIRST)
# FIRST, AND WITH NO EARLY EXIT (#984 audit M1): nothing that can hang runs before it.
$verdict = 'OK'; $why = ''; $did = ''; $rc = 0
try {
    if (-not (Test-Path -LiteralPath $gateRepo)) {
        $why = 'no gate-repo yet; the next sweep clones it'
    } elseif (-not ((Test-Path -LiteralPath $beatPath) -and (Test-Path -LiteralPath $gateLog))) {
        $verdict = 'UNMEASURED'; $why = 'the gate has no heartbeat or log yet'
    } else {
        $beat = Get-Content -Raw -LiteralPath $beatPath | ConvertFrom-Json
        $fails = @(Get-Content -LiteralPath $gateLog -Tail 400 | Where-Object { $_ -match ' FAILED: ' } | Select-Object -Last 3)
        $jammed = ([int]$beat.rc -eq 1) -and ("$($beat.note)" -match $cloneFail) -and $fails.Count -eq 3 -and
                  (@($fails | Where-Object { $_ -match $cloneFail }).Count -eq 3)
        if (-not $jammed) {
            $why = "gate not jammed (rc $($beat.rc))"
        } else {
            $why = "$($beat.note)"
            $item = Get-Item -LiteralPath $gateRepo -Force
            # PowerShell 5.1's Remove-Item -Recurse can follow a junction INSIDE the folder (#901 audit SF1).
            $links = @(Get-ChildItem -LiteralPath $gateRepo -Force -Recurse -ErrorAction SilentlyContinue |
                       Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint } | Select-Object -First 1)
            if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -or $links.Count -gt 0) {
                $verdict = 'REFUSED'; $why = 'gate-repo is or holds a junction or symlink; not removing'; $rc = 3
            } elseif ($DryRun) {
                $verdict = 'JAMMED'; $did = 'dry run: would remove gate-repo and start Quant-WorkflowGate'
            } else {
                $gm = New-Object System.Threading.Mutex($false, 'Global\QuantBox-WorkflowGate')
                try {
                    if (-not $gm.WaitOne(0)) {
                        $verdict = 'JAMMED'; $did = 'a sweep holds the gate mutex; next pass'
                    } else {
                        try { Remove-Item -LiteralPath $gateRepo -Recurse -Force -ErrorAction Stop }
                        finally { $gm.ReleaseMutex() }
                        & schtasks.exe /Run /TN 'Quant-WorkflowGate' | Out-Null
                        $verdict = 'HEALED'; $did = "removed gate-repo; started Quant-WorkflowGate (rc $LASTEXITCODE)"
                    }
                } finally { $gm.Dispose() }
            }
        }
    }
} catch {
    $verdict = 'FAILED'; $why = $_.Exception.Message; $rc = 1
}

# ------------------------------------------------------------- 2. A HUNG MERGE DOCKET IS ENDED
# 2026-11-11: MT5-MergeDocket's python (pid 36280) had hung since 11-09 and survived
# Stop-ScheduledTask; the Judge's intake stalled behind it. #882 gives merge_hypotheses a 12 h wall
# for runs that start on its code; a run that predates it, or hangs where the wall cannot fire, is
# ended here -- but ONLY when it is BOTH older than the wall plus an hour AND has used no CPU
# across two passes (30 min). A process making no CPU progress is not mid-write, so the append-only
# preregistrations.jsonl is never torn by this (#882 waits up to 30 min for its own writes).
# THE PROCESS QUERY IS BOUNDED (#984 audit M1): CIM has hung on this box, so it runs in a job with
# a 60 s timeout, and a timeout is recorded UNMEASURED instead of holding the task.
$reapAgeH = 13
$reaped = @()
try {
    $prev = @{}
    if (Test-Path -LiteralPath $reapState) {
        (Get-Content -Raw -LiteralPath $reapState | ConvertFrom-Json).PSObject.Properties | ForEach-Object { $prev[$_.Name] = $_.Value }
    }
    $job = Start-Job -ScriptBlock {
        Get-CimInstance Win32_Process -Filter "Name like 'python%'" |
            Where-Object { "$($_.CommandLine)" -match 'merge_hypotheses\.py' } |
            ForEach-Object { [pscustomobject]@{ Id = $_.ProcessId; Created = $_.CreationDate; Cpu = [double]($_.KernelModeTime + $_.UserModeTime) } }
    }
    if (-not (Wait-Job -Job $job -Timeout 60)) {
        Stop-Job -Job $job; Remove-Job -Job $job -Force
        $reaped += 'merge-docket check UNMEASURED: CIM timed out'
    } else {
        $procs = @(Receive-Job -Job $job); Remove-Job -Job $job -Force
        $seen = [ordered]@{}
        foreach ($p in $procs) {
            $ageH = ((Get-Date) - $p.Created).TotalHours
            $cpu = [double]$p.Cpu
            $key = "$($p.Id)@$($p.Created.ToUniversalTime().ToString('o'))"
            $was = $prev[$key]
            $still = if ($was -and [double]$was.cpu -eq $cpu) { [int]$was.flat + 1 } else { 0 }
            $seen[$key] = [ordered]@{ cpu = $cpu; flat = $still; age_h = [math]::Round($ageH, 1) }
            if ($ageH -gt $reapAgeH -and $still -ge 2 -and -not $DryRun) {
                & taskkill.exe /PID $p.Id /T /F | Out-Null
                $reaped += "pid $($p.Id) ($([math]::Round($ageH, 1)) h old, no CPU for $still passes; taskkill rc $LASTEXITCODE)"
            }
        }
        Write-Atomic $reapState ($seen | ConvertTo-Json -Compress)
    }
} catch {
    $reaped += "merge-docket check skipped: $($_.Exception.Message)"
}

# ------------------------------------------------------------- the beat, once, for the pagers
$doc = [ordered]@{
    at = (Get-Date).ToUniversalTime().ToString('o'); verdict = $verdict; why = $why; did = $did
    merge_docket = ($reaped -join '; '); dry_run = [bool]$DryRun
}
try { Write-Atomic $outPath ($doc | ConvertTo-Json -Compress) } catch { }
"gate_clone_watchdog: $verdict -- $why$(if ($did) { " ($did)" })$(if ($reaped) { " | " + ($reaped -join '; ') })"
exit $rc
