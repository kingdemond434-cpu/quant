<#
.SYNOPSIS
    Adopt the miner discovery corpus from the VPS transport branch intel-ship/send onto this
    box, without touching code, without sealing, without restarting the gateway.

.DESCRIPTION
    WHY THIS EXISTS. The hel8 miner swarm produces candidates into data/intelligence/ and
    desks/mt5/data/intelligence/ and ships them hourly on the dedicated data-only branch
    intel-ship/send (ops/ship_intel.sh on the VPS; rooted on this box's OWN origin base
    93da41e5a so the trees carry no code). This box's gauntlet consumes candidates through
    local_converter.py, whose SOURCES are exactly those two trees. This task lands only those
    paths into the working tree and index -- never a branch switch, never a code change.

    WHY NOT Adopt-And-Seal. That organ lands a WHOLE branch tree and then seals + restarts the
    gateway. The intel-ship branch is data-only by construction, but adopting it wholesale
    would also rewrite every other path to its base tree, reverting this box's 7 local commits
    (cb60d19c7). The tow path lists are the whole point.

    GIT-WRITER GUARD (2026-09-08 discipline). sync_shadow_to_git.ps1 holds Local\MT5-GitWriter
    for its whole pass; adopt-and-seal waits on it too. This script takes the same mutex so it
    never stages into an index a sync is mid-rewrite, and it waits for MT5-ShadowSync the way
    Adopt-And-Seal does. A commit is never made here -- only a path checkout, so the risk is an
    index-lock collision, and the mutex is what prevents that.
#>
param(
    [string] $RepoRoot
)
$ErrorActionPreference = "Continue"
if (-not $RepoRoot) { $RepoRoot = "C:\opt\quant" }
Set-Location $RepoRoot
$log = "C:\opt\quant\desks\mt5\logs\intel_ship_adopt.log"
function Log([string] $m) {
    $line = "{0} intel-ship-adopt: {1}" -f (Get-Date).ToUniversalTime().ToString('o'), $m
    New-Item -ItemType Directory -Force -Path (Split-Path $log) | Out-Null
    Add-Content -Path $log -Value $line -Encoding utf8
    Write-Output $line
}

if (-not (Test-Path (Join-Path $RepoRoot ".git"))) { Log "no .git under $RepoRoot"; exit 2 }

# 1. wait for MT5-ShadowSync the way Adopt-And-Seal does (sync limit is 10 min; give it 9)
$waited = 0
while ((Get-ScheduledTask -TaskName "MT5-ShadowSync" -ErrorAction SilentlyContinue).State -eq "Running") {
    if ($waited -ge 540) { Log "MT5-ShadowSync still running after 9 min; not adopting under it"; exit 6 }
    if ($waited -eq 0) { Log "MT5-ShadowSync is running; waiting for it before adopting" }
    Start-Sleep -Seconds 5
    $waited += 5
}

# 2. the mutex every git writer on this box takes
$script:GitWriterMutex = New-Object System.Threading.Mutex($false, "Local\MT5-GitWriter")
$gotLock = $false
try { $gotLock = $script:GitWriterMutex.WaitOne(540000) }
catch [System.Threading.AbandonedMutexException] { $gotLock = $true }
if (-not $gotLock) { Log "another git writer holds Local\MT5-GitWriter after 9 min; not adopting under it"; exit 6 }

try {
    # 3. fetch the transport branch into FETCH_HEAD, then land ONLY the two discovery trees
    & git fetch origin intel-ship/send 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { Log "git fetch failed (rc=$LASTEXITCODE)"; exit 3 }
    & git checkout FETCH_HEAD -- data/intelligence desks/mt5/data/intelligence 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { Log "git checkout failed (rc=$LASTEXITCODE)"; exit 4 }

    # 4. verify a marker from the ship is actually on disk (the ship always carries the
    #    discovery per-miner corpus; count what came down)
    $n = (Get-ChildItem -Recurse -File "C:\opt\quant\data\intelligence","C:\opt\quant\desks\mt5\data\intelligence" -ErrorAction SilentlyContinue | Measure-Object).Count
    $head = (& git rev-parse --short FETCH_HEAD | Out-String).Trim()
    Log "adopted $head onto disk ($n intelligence files); leaving conversion to the box's own pipeline"
    exit 0
}
finally {
    $script:GitWriterMutex.ReleaseMutex()
}