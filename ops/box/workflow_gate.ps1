# MERGE AUDIT-CLEARED PRs FROM THE BOX (2026-10-28).
#
# The Actions audit gate (.github/scripts/audit_gate.py, #445) merges a PR into LIVE once the
# auditor CLEARs its head and CI is green -- but it needs the `audit-clear` label to start, which
# the cloud sessions are refused (as is marking a draft ready), and it cannot merge a PR that
# changes .github/workflows/** (GitHub refuses the workflow token). This runs the SAME gate, same
# rule, in its box mode with zuck's own gh login: `audit_gate.py --sweep --box` looks at every
# open PR into LIVE with no label needed, and merges (marking a draft ready first) only on a CLEAR
# for the head (or the same exact diff) plus green gating CI, pinned to the head sha, never waiting.
#
# TRUSTED CODE ONLY. The gate script is read from a clean, detached checkout of origin/LIVE in an
# admin-only folder, never from a PR branch. A merge made with a user token starts the normal push
# CI on LIVE (seal, promote); nothing is dispatched.
#
# No token is read, printed or stored here: gh keeps zuck's login in Windows Credential Manager.
# Any GITHUB_TOKEN / GH_TOKEN in the environment is dropped for this process so the merge is made
# with that login and nothing else. Without the `workflow` scope it still merges the other PRs, and
# says in logs\workflow_gate.json that workflow-file PRs will fail until zuck runs once:
# `gh auth refresh -h github.com -s workflow`.

[CmdletBinding()]
param(
    [string] $Root = "C:\ProgramData\QuantBox",
    [string] $Repo = "kingdemond434-cpu/quant",
    [string] $Live = "claude/llm-auto-upgrade-verify-gcjac3",
    [string] $Gh = "C:\Users\Administrator\tools\gh\bin\gh.exe",
    [string] $Python = "",
    # where the merge-pipeline report is written: the desk's reports, published with box state
    [string] $QuantRoot = "C:\opt\quant"
)
$ErrorActionPreference = 'Stop'
$LogDir = Join-Path $Root "logs"
$Clone = Join-Path $Root "gate-repo"
$log = Join-Path $LogDir "workflow_gate.log"
$beat = Join-Path $LogDir "workflow_gate.json"
# THE PUBLIC COPY (2026-11-17, Desk health + the Auditor's no-free-text rule): published with box
# state, so it carries numbers, booleans, a phase name and at most an exception TYPE, never a
# message. `phase` is stamped as each phase STARTS, so a run the scheduler kills at its 30-min
# limit (267014, every run on 11-17) still says where it died; MERGE_PIPELINE.json froze at the
# last run that finished and nothing off the box could tell how far a killed run got.
$public = Join-Path $QuantRoot "desks\mt5\reports\WORKFLOW_GATE.json"
$script:Phase = "start"
$script:Merged = 0
# THE RUN'S OWN CLOCK: the task is killed at 30 min. The sweep runs FIRST (its own 15-min budget);
# every other phase runs only when what is left (less the watcher's reserve) covers it.
$script:Deadline = (Get-Date).AddMinutes(27)
$WatchReserveS = 180

function Say([string] $line) {
    Add-Content -LiteralPath $log -Value ("{0} {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ssK'), $line)
}
function Publish([object] $rc, [object] $scope, [int] $held, [string] $errType, [bool] $finished) {
    try {
        $doc = [ordered]@{ at = (Get-Date).ToUniversalTime().ToString('o'); phase = $script:Phase
                           finished = $finished; rc = $rc; merged = $script:Merged
                           workflow_scope = $scope; mutex_held_runs = $held; error_type = $errType }
        $null = New-Item -ItemType Directory -Force -Path (Split-Path $public) -ErrorAction Stop
        $doc | ConvertTo-Json -Compress | Set-Content -LiteralPath "$public.tmp" -Encoding UTF8
        Move-Item -LiteralPath "$public.tmp" -Destination $public -Force
    } catch { Say "public heartbeat unwritable: $($_.Exception.GetType().Name)" }
}
function Beat([int] $rc, [string] $note, [bool] $scope, [int] $held = 0, [string] $errType = "") {
    $doc = [ordered]@{ at = (Get-Date).ToUniversalTime().ToString('o'); rc = $rc; workflow_scope = $scope; note = $note; mutex_held_runs = $held; phase = $script:Phase }
    $doc | ConvertTo-Json -Compress | Set-Content -LiteralPath "$beat.tmp" -Encoding UTF8
    Move-Item -LiteralPath "$beat.tmp" -Destination $beat -Force
    Publish $rc $scope $held $errType $true
}
# A PHASE STARTS: logged and stamped on the public copy only. The private heartbeat's `at` stays
# the last FINISHED run, so SWEEP_STALE still fires when no run finishes.
function Mark([string] $phase) {
    $script:Phase = $phase
    Say "phase $phase"
    Publish $null $null 0 "" $false
}
# THE TIME A PHASE STILL HAS: seconds to the run's deadline less the watcher's reserve. A phase
# that needs more than is left is skipped and says so (the next run, 10 min on, does it); nothing
# is killed (no process kill in this script, test_box_unattended), so a phase is never cut mid-push.
function Left { return [int](($script:Deadline - (Get-Date)).TotalSeconds) - $WatchReserveS }

# The merge pipeline's clock (#521 audit MF2): queued-check ages, CLEARed or green work waiting,
# LIVE's last code, the reviewer's false-positive rate and this sweep's own heartbeat. It runs on
# every run, the refused ones too, so a wedged sweep still writes a RED report. Read-only on
# GitHub; a failure here is logged and never changes the sweep's exit code.
function Watch {
    try {
        $env:GH_BIN = $Gh
        $py = $Python
        if (-not $py) {
            foreach ($cand in @("$env:LOCALAPPDATA\Programs\Python\Python314\python.exe", 'C:\Program Files\Python314\python.exe')) {
                if (Test-Path -LiteralPath $cand) { $py = $cand; break }
            }
        }
        $script = Join-Path $Clone "scripts\merge_pipeline_watch.py"
        if (-not $py -or -not (Test-Path -LiteralPath $script)) { Say "watch: no Python or no watcher in the clone"; return }
        $report = Join-Path $QuantRoot "desks\mt5\reports\MERGE_PIPELINE.json"
        $sign = Join-Path $LogDir "sign_train.json"  # Quant-SignTrain's heartbeat (#541 audit MF3)
        $wout = (& $py -I -u $script --repo $Repo --base $Live --out $report --heartbeat $beat --sign-heartbeat $sign 2>&1 | Out-String)
        Say "watch rc=$LASTEXITCODE $($wout.Trim())"
    } catch {
        Say "watch failed: $($_.Exception.Message)"
    }
}

# A HELD MUTEX IS NEVER SILENT (2026-10-29). A gh call hung from 13:53Z held this mutex and every
# later run exited 0 here without a line, so the only merger of AUTO PRs was dead for hours and
# the heartbeat simply stopped. Each refused run now logs, counts and stamps the heartbeat; the
# merge-pipeline watcher reads it (rc 4, mutex_held_runs) and goes RED past two runs. The gate's
# own gh calls now time out, so a hold cannot last past one sweep.
$mutex = New-Object System.Threading.Mutex($false, "Global\QuantBox-WorkflowGate")
if (-not $mutex.WaitOne(0)) {
    $held = 1
    try { $held = [int]((Get-Content -LiteralPath $beat -Raw | ConvertFrom-Json).mutex_held_runs) + 1 } catch { }
    Say "the previous sweep still holds the mutex (run $held in a row)"
    $script:Phase = "mutex-held"
    Beat 4 "mutex held by the previous sweep ($held runs in a row)" $true $held
    Watch
    exit 4
}
if ((Test-Path -LiteralPath $log) -and (Get-Item -LiteralPath $log).Length -gt 5MB) {
    Move-Item -LiteralPath $log -Destination "$log.1" -Force
}

# zuck's gh login and nothing else; git trusts the gate clone (an elevated admin's files are owned
# by Administrators, which git calls "dubious ownership") through command-scope config only.
foreach ($v in @('GITHUB_TOKEN', 'GH_TOKEN', 'GH_ENTERPRISE_TOKEN', 'GITHUB_ENTERPRISE_TOKEN')) {
    Remove-Item -LiteralPath "env:$v" -ErrorAction SilentlyContinue
}
$env:GH_PROMPT_DISABLED = '1'
$env:GIT_TERMINAL_PROMPT = '0'
$env:GIT_CONFIG_COUNT = '1'
$env:GIT_CONFIG_KEY_0 = 'safe.directory'
$env:GIT_CONFIG_VALUE_0 = ($Clone -replace '\\', '/')
$env:PATH = (Split-Path -Parent $Gh) + ';' + $env:PATH

try {
    Mark "clone"
    if (-not $Python) {
        foreach ($cand in @("$env:LOCALAPPDATA\Programs\Python\Python314\python.exe", 'C:\Program Files\Python314\python.exe')) {
            if (Test-Path -LiteralPath $cand) { $Python = $cand; break }
        }
    }
    if (-not $Python) { throw "no Python 3.14 found" }

    $ErrorActionPreference = 'Continue'  # native stderr is data; exit codes are the verdict
    if (-not (Test-Path -LiteralPath (Join-Path $Clone ".git"))) {
        & git clone -q --filter=blob:none --no-checkout "https://github.com/$Repo.git" $Clone 2>&1 | ForEach-Object { Say "clone: $_" }
        if ($LASTEXITCODE -ne 0) { throw "git clone failed ($LASTEXITCODE)" }
    }
    # every run, so a moved gate script is followed. The code files come too: the LOW-tier check
    # greps LIVE's code for any program that reads a document, and a checkout fetches their
    # blobs in one batch (a grep over a blobless tree would fetch them one by one).
    & git -C $Clone sparse-checkout set --no-cone /.github/scripts/audit_gate.py '*.py' '*.ps1' '*.sh' '*.cmd' '*.txt' '*.yml' '*.yaml' '*.toml' '*.manifest' '*.service' /ops/githooks/
    if ($LASTEXITCODE -ne 0) { throw "sparse-checkout failed ($LASTEXITCODE)" }
    & git -C $Clone fetch -q --no-tags origin "+refs/heads/${Live}:refs/remotes/origin/${Live}" 2>&1 | ForEach-Object { Say "fetch: $_" }
    if ($LASTEXITCODE -ne 0) { throw "git fetch failed ($LASTEXITCODE)" }
    & git -C $Clone checkout -q -f --detach "origin/$Live" 2>&1 | ForEach-Object { Say "checkout: $_" }
    if ($LASTEXITCODE -ne 0) { throw "git checkout failed ($LASTEXITCODE)" }
    $at = (& git -C $Clone rev-parse --short=9 HEAD)

    # LEVEL 2 (ops/release/authority/LEVEL2.md step 3): the quant-merger App when it is installed.
    # Loaded only AFTER the clone is on LIVE's tip (2026-11-13): it used to run first, from the
    # clone's OLD copy, so a broken merger_env.ps1 failed every git call before the fetch that
    # would have brought its fix -- a loop no merge could break. The repo is public, so the
    # sparse-checkout, fetch and checkout above need no identity.
    Mark "identity"
    $asApp = $false
    $mergerEnv = Join-Path $Clone "ops\release\merger\merger_env.ps1"
    if (Test-Path -LiteralPath $mergerEnv) {
        . $mergerEnv
        try { $asApp = Use-MergerIdentity $Clone } catch { Say "$($_.Exception.Message)"; Beat 3 "merger App token failed" $false; Watch; exit 3 }
    }
    $status = (& $Gh auth status -h github.com 2>&1 | Out-String)
    $scopeLine = ($status -split "`n" | Where-Object { $_ -match 'Token scopes' } | Select-Object -First 1)
    if ($LASTEXITCODE -ne 0) { Say "gh is not logged in: $($status.Trim())"; Beat 3 "gh not logged in" $false; Watch; exit 3 }
    $scope = $asApp -or ($scopeLine -match "'workflow'")  # an App's Workflows permission is not a scope
    if (-not $scope) {
        Say "gh login lacks the workflow scope ($scopeLine); workflow-file PRs will fail to merge"
    }

    # THE SWEEP FIRST (2026-11-17): it is what merges, and every run was killed at the task's
    # 30-min limit before reaching a merge while live-first, adopt-rows and memecoin ran ahead of or
    # around it with no clock of their own. #1244 sat green and unmerged.
    Mark "sweep"
    Push-Location -LiteralPath $Clone
    try {
        # Streamed, one log line per gate line as it comes (2026-10-29: a sweep killed by the
        # task's time limit had buffered everything and left no line at all).
        $lines = New-Object System.Collections.Generic.List[string]
        & $Python -I -u (Join-Path $Clone ".github\scripts\audit_gate.py") --repo $Repo --base $Live --sweep --box 2>&1 | ForEach-Object {
            $l = "$_"
            if ($l) { Say "gate@$at $l"; $lines.Add($l) }
        }
        $rc = $LASTEXITCODE
        $out = $lines -join "`n"
    } finally { Pop-Location }
    # case-sensitive, the gate's own word: -match counted every "merged" in any line (20:20Z: 5)
    $merged = @($out -split "`r?`n" | Where-Object { $_ -cmatch ': MERGED \(' }).Count
    $script:Merged = $merged

    # LIVE first (zuck 2026-10-29 19:50Z "yes"): PR runs queued ahead of a waiting LIVE push run
    # are cancelled and re-run behind it, and runs on moved heads are cancelled. Capped; a failure
    # here is logged and never stops the run.
    Mark "live-first"
    try {
        $env:GH_BIN = $Gh
        $budget = [Math]::Min(240, (Left) - 60)  # live_first stops itself at --budget-s
        if ($budget -lt 60) { Say "live-first skipped: $(Left)s left" } else {
            & $Python -I -u (Join-Path $Clone "scripts\live_first_ci.py") --repo $Repo --base $Live --state (Join-Path $QuantRoot "desks\mt5\reports\LIVE_FIRST_CI.json") --budget-s $budget 2>&1 | ForEach-Object { Say "live-first $_" }
            Say "live-first rc=$LASTEXITCODE"
        }  # 2: a re-run was given up on; 1: it stopped on an API error
    } catch {
        Say "live-first failed: $($_.Exception.Message)"
    }
    # MERGE-TIME ADOPT_CLEARS ROWS (R2f): a recent LIVE merge whose exact head carries a verified
    # authority attestation or Auditor registry CLEAR gets its adoption row, pushed fast-forward as
    # a data-only commit; the adopt guard re-verifies each one. A failure here is logged and never
    # stops the sweep's heartbeat; no row means the guard stays closed, as before.
    Mark "adopt-rows"
    try {
        if ((Left) -lt 180) { Say "adopt-rows skipped: $(Left)s left" } else {
            & $Python -I -u (Join-Path $Clone "ops\release\adopt_rows.py") --root $Clone --apply --report (Join-Path $QuantRoot "desks\mt5\reports\ADOPT_ROWS.json") 2>&1 | ForEach-Object { Say "adopt-rows@$at $_" }
            Say "adopt-rows rc=$LASTEXITCODE"
        }
    } catch {
        Say "adopt-rows failed: $($_.Exception.Message)"
    }
    # THE MEMECOIN REPO (zuck 2026-11-03, "zero taps everywhere"): the same box, login and veto
    # window merge a CLEARed, green memecoin PR that does not touch its live switch
    # (.github/scripts/memecoin_gate.py). It runs only when MEMECOIN_AUDIT_REGISTRY is set on the
    # box, and a failure here is logged and never stops the quant sweep's heartbeat.
    if ($env:MEMECOIN_AUDIT_REGISTRY) {
        Mark "memecoin"
        try {
            $mClone = Join-Path (Split-Path -Parent $Clone) "memecoin-gate"
            # APPENDED, never index 1: merger_env.ps1 may already hold entries 1 and 2 (the App's
            # extraheader and the credential.helper reset), and overwriting 1 dropped the token.
            $k = [int]$env:GIT_CONFIG_COUNT
            Set-Item -LiteralPath "env:GIT_CONFIG_KEY_$k" -Value 'safe.directory'
            Set-Item -LiteralPath "env:GIT_CONFIG_VALUE_$k" -Value ($mClone -replace '\\', '/')
            $env:GIT_CONFIG_COUNT = "$($k + 1)"
            if (-not (Test-Path -LiteralPath (Join-Path $mClone ".git"))) {
                & git clone -q "https://github.com/kingdemond434-cpu/memecoin.git" $mClone 2>&1 | ForEach-Object { Say "memecoin clone: $_" }
            }
            if ((Left) -lt 180) { Say "memecoin skipped: $(Left)s left" } else {
                & $Python -I -u (Join-Path $Clone ".github\scripts\memecoin_gate.py") --box --clone $mClone 2>&1 | ForEach-Object { Say "memecoin@$at $_" }
                Say "memecoin rc=$LASTEXITCODE"
            }
        } catch {
            Say "memecoin sweep failed: $($_.Exception.Message)"
        }
    }
    $note = "gate@{0}: {1} merged" -f $at, $merged
    if (-not $scope) { $note += "; NO workflow scope: run once  gh auth refresh -h github.com -s workflow" }
    Mark "watch"
    Beat $rc $note $scope
    Watch
    exit $rc
} catch {
    Say "FAILED: $($_.Exception.Message)"
    Beat 1 "FAILED: $($_.Exception.Message)" $false 0 $_.Exception.GetType().Name
    Watch  # a sweep that fails every run still writes its RED (#521 audit MF-A)
    exit 1
} finally {
    $mutex.ReleaseMutex()
}
