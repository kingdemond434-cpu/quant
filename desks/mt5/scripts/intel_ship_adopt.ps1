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

    A FROZEN SHIP IS NEVER RE-ADOPTED (2026-11-03). hel8 shipped last at 2026-11-03T02:50Z and the
    box now writes the feed itself (the `intel_feed` leg of MT5-Dept-Intel, writing straight into
    desks/mt5/data/intelligence). Checking out the frozen ref every hour would revert those
    box-written files to their stale 02:50Z copies -- and refresh their mtimes, so the staleness
    contracts would read the reverted feed as fresh. So the checkout is SKIPPED, and the log says
    why, when the ref's commit is older than -MaxShipAgeHours (6 h), or when the ref has not moved
    since the last adoption (its sha is kept in desks/mt5/data/intel_ship_adopt_state.json). A
    skip exits 0: it is the organ working, not failing.
#>
param(
    [string] $RepoRoot,
    [double] $MaxShipAgeHours = 6
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

# 1. FETCH WITHOUT HOLDING THE INDEX-WRITER MUTEX.  The transport branch can contain tens of
# thousands of objects; measured 2026-09-30, index-pack ran for more than nine minutes while this
# task held the global writer mutex, causing every release adoption to time out. Fetching objects
# and updating this task's DEDICATED remote ref does not touch the worktree or index. Crucially,
# --no-write-fetch-head prevents this fetch from overwriting FETCH_HEAD while Adopt-Release uses
# it as its immutable target.
$shipRef = "refs/remotes/intel-ship/send"
# Do not let transport spawn detached maintenance after this pre-lock phase.  Such a child no
# longer participates in the named writer mutex and can collide with either this checkout or the
# canonical adopter's later commit.
& git -c maintenance.auto=false -c gc.auto=0 fetch --no-write-fetch-head origin "+refs/heads/intel-ship/send:$shipRef" 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) { Log "git fetch failed (rc=$LASTEXITCODE)"; exit 3 }

# 1b. SKIP A FROZEN OR UNCHANGED SHIP (2026-11-03) -- before any wait or lock, so a skip costs
# nothing. The last adopted sha is this task's own state; an unreadable state file is "never
# adopted", which only ever lets an adoption through, never invents a skip.
$adoptState = Join-Path $RepoRoot "desks\mt5\data\intel_ship_adopt_state.json"
$shipSha = (& git rev-parse $shipRef 2>$null | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or -not $shipSha) { Log "could not resolve $shipRef after the fetch"; exit 3 }
$shipCtText = (& git log -1 --format=%ct $shipRef 2>$null | Out-String).Trim()
[int64] $shipCt = 0
if (-not [int64]::TryParse($shipCtText, [ref] $shipCt) -or $shipCt -le 0) {
    Log "could not read the commit time of $shipRef ($shipSha); not adopting what cannot be dated"
    exit 3
}
$nowEpoch = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
$shipAgeH = ($nowEpoch - $shipCt) / 3600.0
$shipAt = [DateTimeOffset]::FromUnixTimeSeconds($shipCt).UtcDateTime.ToString('o')
if ($shipAgeH -gt $MaxShipAgeHours) {
    $why = ("SKIP: {0} was committed {1}, {2:N1} h ago (over {3} h): the VPS has stopped " +
            "shipping, and checking it out would revert the box-written feed in " +
            "desks/mt5/data/intelligence to stale copies") -f $shipSha.Substring(0, 12), $shipAt,
           $shipAgeH, $MaxShipAgeHours
    Log $why
    exit 0
}
$lastSha = ""
if (Test-Path $adoptState) {
    try { $lastSha = [string]((Get-Content -Raw -Path $adoptState | ConvertFrom-Json).last_adopted_sha) }
    catch { $lastSha = "" }
}
if ($lastSha -and $lastSha -eq $shipSha) {
    $why = ("SKIP: {0} is unchanged since the last adoption: nothing new shipped, and " +
            "re-checking it out would only overwrite what the box wrote since") -f $shipSha.Substring(0, 12)
    Log $why
    exit 0
}

# 2. wait for MT5-ShadowSync the way Adopt-And-Seal does (sync limit is 10 min; give it 9)
$waited = 0
while ((Get-ScheduledTask -TaskName "MT5-ShadowSync" -ErrorAction SilentlyContinue).State -eq "Running") {
    if ($waited -ge 540) { Log "MT5-ShadowSync still running after 9 min; not adopting under it"; exit 6 }
    if ($waited -eq 0) { Log "MT5-ShadowSync is running; waiting for it before adopting" }
    Start-Sleep -Seconds 5
    $waited += 5
}

# 3. the mutex every WORKTREE/INDEX writer on this box takes
. (Join-Path $PSScriptRoot "GitWriterMutex.ps1")
# THE WHOLE HANDLE (2026-09-23): `.Mutex` alone drops the legacy name the helper also takes, and
# a $null from a name that could not be OPENED then failed non-terminating and was reported as
# another writer holding it -- a refusal with an invented reason, which is the shape of the
# four-day adoption outage.
$script:GitWriterHandle = Open-GitWriterMutex
$script:GitWriterMutex = $script:GitWriterHandle.Mutex
if ($null -eq $script:GitWriterMutex) {
    Log ("could not OPEN the git-writer lock (" + $script:GitWriterHandle.Why + ") -- this is " +
         "not evidence that another writer holds it; the lock could not be examined at all")
    exit 6
}
$gotLock = $false
try { $gotLock = $script:GitWriterMutex.WaitOne(540000) }
catch [System.Threading.AbandonedMutexException] { $gotLock = $true }
if (-not $gotLock) { Log ("another git writer held " + $script:GitWriterHandle.Name + " for the full 9 min; not adopting under it"); exit 6 }

try {
    # 4. land ONLY the two discovery trees from the dedicated ref. The expensive transfer above
    # happened before this lock window; only the bounded index/worktree write is serialized.
    & git checkout $shipRef -- data/intelligence desks/mt5/data/intelligence 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { Log "git checkout failed (rc=$LASTEXITCODE)"; exit 4 }

    # 5. verify a marker from the ship is actually on disk (the ship always carries the
    #    discovery per-miner corpus; count what came down)
    $n = (Get-ChildItem -Recurse -File "C:\opt\quant\data\intelligence","C:\opt\quant\desks\mt5\data\intelligence" -ErrorAction SilentlyContinue | Measure-Object).Count
    $head = (& git rev-parse --short $shipRef | Out-String).Trim()
    # Record what was adopted, so an unchanged ref is skipped next hour (step 1b).
    $stateDoc = [ordered]@{ last_adopted_sha = $shipSha; ship_committed_at = $shipAt;
                            adopted_at = (Get-Date).ToUniversalTime().ToString('o') }
    try {
        New-Item -ItemType Directory -Force -Path (Split-Path $adoptState) | Out-Null
        [System.IO.File]::WriteAllText($adoptState, ($stateDoc | ConvertTo-Json -Compress))
    } catch { Log ("adopted, but the state file could not be written: " + $_.Exception.Message) }
    Log "adopted $head onto disk ($n intelligence files); leaving conversion to the box's own pipeline"
    exit 0
}
finally {
    Close-GitWriterMutex $script:GitWriterHandle
}
