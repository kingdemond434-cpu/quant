<#
.SYNOPSIS
    Re-seal the release when the running tree is code-clean but unsealed. Seconds, not minutes.

.DESCRIPTION
    WHY THIS EXISTS, AND WHY IT IS NOT PART OF Adopt-And-Seal.ps1.

    The release identity fence refuses NEW risk whenever the running tree carries a code path the
    sealed release never named. That is correct and it is the point. What broke is that NOTHING
    RELIABLY RE-SEALED, so any session that committed code left the gateway "managing open
    positions only" until a human noticed.

    MEASURED 2026-09-15: the fence had been refusing for 103 to 150 HOURS across at least six
    different SHA pairs -- 1,780 refusal lines in one week. Gold logged `bracket NOT placed` and
    none of the 444 forex signals the families produced that week could reach the venue. The desk
    was not broken; it was unsealed, and the organ whose job was to re-seal it never ran.

    WHY THAT ORGAN NEVER RAN, which is the part this script fixes:

      Adopt-And-Seal.ps1 does TWO things -- a heavyweight ADOPTION (fetch, read-tree, merge the
      box's state) and a trivial SEAL (write RELEASE.json, commit it alone). Both sit behind one
      acquisition of `Local\MT5-GitWriter` with a 9 minute timeout. `MT5-ShadowSync` and the
      hourly syncs hold that mutex more or less continuously, so the hourly adopt logged
      "another git writer held Local\MT5-GitWriter for the full 9 min; not adopting under it"
      and exited 6 -- and on the passes where it DID get in, a 20 minute ExecutionTimeLimit
      killed it mid-adoption (result 267014). Either way the seal at the end was never reached.

      The seal did not need any of that. It reads two SHAs, asks `release.accepts`, and on a
      clean tree writes one file and commits one path. It was starved by being bundled with the
      expensive operation it does not depend on.

    SO THIS SCRIPT IS THE CHEAP HALF, ALONE, ON A FAST CLOCK. It takes the same mutex with a
    SHORT timeout, does no fetch, no read-tree and no merge, and exits immediately if it cannot
    get the lock -- because at this cadence the next attempt is minutes away, and a seal that
    waits is a seal competing with the thing it was starved by. Adoption stays where it is.

    IT REFUSES EXACTLY WHERE Adopt-And-Seal REFUSES. `release.seal` will not seal a tree with a
    dirty CODE path, and neither will this: a dirty money path means the running code is not any
    commit, and sealing it would certify a tree nobody can reconstruct. State paths are expected
    to be dirty on a live box and are ignored, which is the same rule `release.accepts` applies.

    NO `git add -A`, NO `git stash`, NO FORCE. It stages exactly one path by name (R0423).

.NOTES
    Registered as MT5-SealIfClean, every 10 minutes. Exit codes:
      0  nothing to do, or sealed successfully
      2  environment problem (no python, no git, cannot read HEAD)
      5  mutex busy -- normal, the next run retries
      7  refused: a CODE path is dirty, so the tree matches no commit
#>
[CmdletBinding()]
param()

$ErrorActionPreference = "Continue"

$desk = Split-Path -Parent $PSScriptRoot
$root = Split-Path -Parent (Split-Path -Parent $desk)
$logFile = Join-Path $desk "logs\seal_if_clean.log"
$release = Join-Path $desk "data\RELEASE.json"

function Log([string] $m) {
    $line = "$((Get-Date).ToUniversalTime().ToString('u')) seal-if-clean: $m"
    Write-Output $line
    try {
        $dir = Split-Path -Parent $logFile
        if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
        Add-Content -Path $logFile -Value $line -Encoding utf8
    } catch { }
}

Set-Location $root

# THE INTERPRETER IS RESOLVED, NEVER ASSUMED. A task pointed at a python that does not exist
# fails instantly with ERROR_FILE_NOT_FOUND, writes no log and leaves no artifact -- which is
# how E8-Executor sat "scheduled" for days having never once executed.
$py = $null
foreach ($cand in @(
    (Join-Path $root ".venv\Scripts\python.exe"),
    "$env:LOCALAPPDATA\Programs\Python\Python314\python.exe"
)) { if (Test-Path $cand) { $py = $cand; break } }
if (-not $py) {
    $c = Get-Command python -ErrorAction SilentlyContinue
    if ($c) { $py = $c.Source }
}
if (-not $py) { Log "no python interpreter found"; exit 2 }

$head = (git rev-parse HEAD 2>$null | Out-String).Trim()
if (-not $head) { Log "cannot read HEAD"; exit 2 }

# ASK THE FENCE ITSELF, rather than re-implementing its rule here. `release.accepts` is the
# exact predicate the gateway applies before it will take NEW risk, so agreeing with it by
# construction is the only way this script cannot drift from the thing it exists to satisfy.
$acc = & $py -c "import sys; from libs.ops import release; ok, why, _ = release.accepts(sys.argv[1], release.load() or {}); print('OK' if ok else 'NO'); print(why)" $head 2>$null
if ($LASTEXITCODE -ne 0) { Log "cannot evaluate release.accepts (exit $LASTEXITCODE)"; exit 2 }
$verdict = ($acc | Select-Object -First 1)
$why = ($acc | Select-Object -Skip 1) -join " "
if ($verdict -eq "OK") { exit 0 }

Log "fence REFUSES: $why"

# A DIRTY CODE PATH IS A REFUSAL, NOT A SEAL. State paths are dirty on a live box by design;
# `libs.ops.release.is_state_path` owns that distinction and is asked rather than guessed.
$dirtyCode = & $py -c @"
import subprocess, sys
from libs.ops import release
out = subprocess.run(['git','status','--porcelain','--untracked-files=no'],
                     capture_output=True, text=True).stdout
bad = []
for ln in out.splitlines():
    p = ln[3:].strip().strip('"')
    if not p:
        continue
    p = p.split(' -> ')[-1]
    if not release.is_state_path(p):
        bad.append(p)
print('\n'.join(bad[:12]))
"@ 2>$null
if ($dirtyCode) {
    Log "REFUSED: code path(s) dirty, tree matches no commit: $($dirtyCode -join ', ')"
    exit 7
}

# SHORT WAIT BY DESIGN. Adopt-And-Seal waits 9 minutes and is starved anyway; at a 10 minute
# cadence the right move when the lock is busy is to leave and come back, not to queue behind
# the writer that starved it.
$mutex = $null
. (Join-Path $PSScriptRoot "GitWriterMutex.ps1")
try { $mutex = (Open-GitWriterMutex).Mutex }
catch { Log "cannot open Local\MT5-GitWriter ($($_.Exception.GetType().Name)); not sealing"; exit 5 }

$got = $false
try { $got = $mutex.WaitOne(20000) }
catch [System.Threading.AbandonedMutexException] { $got = $true }
if (-not $got) { Log "git writer busy; next run retries"; exit 5 }

try {
    $sealed = & $py -c "from libs.ops import release; d=release.seal(by='Seal-IfClean'); print(d.get('code_sha') or d.get('live_sha'))" 2>&1
    if ($LASTEXITCODE -ne 0) { Log "release.seal failed (exit $LASTEXITCODE): $sealed"; exit 3 }

    git add -- "desks/mt5/data/RELEASE.json"
    $env:QUANT_ALLOW_SSH_PY = "1"
    git commit -q -m "Seal release $($head.Substring(0,12)) (Seal-IfClean, unattended)"
    if ($LASTEXITCODE -ne 0) { Log "nothing committed (seal may already match)"; exit 0 }
    Log "SEALED $($head.Substring(0,12)); the gateway may take NEW risk again"
    exit 0
}
finally {
    try { $mutex.ReleaseMutex() } catch { }
    try { $mutex.Dispose() } catch { }
}
