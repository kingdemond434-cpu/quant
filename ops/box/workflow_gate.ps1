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

function Say([string] $line) {
    Add-Content -LiteralPath $log -Value ("{0} {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ssK'), $line)
}
function Beat([int] $rc, [string] $note, [bool] $scope, [int] $held = 0) {
    $doc = [ordered]@{ at = (Get-Date).ToUniversalTime().ToString('o'); rc = $rc; workflow_scope = $scope; note = $note; mutex_held_runs = $held }
    $doc | ConvertTo-Json -Compress | Set-Content -LiteralPath "$beat.tmp" -Encoding UTF8
    Move-Item -LiteralPath "$beat.tmp" -Destination $beat -Force
}

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
        $wout = (& $py -I -u $script --repo $Repo --base $Live --out $report --heartbeat $beat 2>&1 | Out-String)
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
    if (-not $Python) {
        foreach ($cand in @("$env:LOCALAPPDATA\Programs\Python\Python314\python.exe", 'C:\Program Files\Python314\python.exe')) {
            if (Test-Path -LiteralPath $cand) { $Python = $cand; break }
        }
    }
    if (-not $Python) { throw "no Python 3.14 found" }

    $ErrorActionPreference = 'Continue'  # native stderr is data; exit codes are the verdict
    $status = (& $Gh auth status -h github.com 2>&1 | Out-String)
    $scopeLine = ($status -split "`n" | Where-Object { $_ -match 'Token scopes' } | Select-Object -First 1)
    if ($LASTEXITCODE -ne 0) { Say "gh is not logged in: $($status.Trim())"; Beat 3 "gh not logged in" $false; Watch; exit 3 }
    $scope = $scopeLine -match "'workflow'"
    if (-not $scope) {
        Say "gh login lacks the workflow scope ($scopeLine); workflow-file PRs will fail to merge"
    }

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

    # LIVE first (zuck 2026-10-29 19:50Z "yes"): PR runs queued ahead of a waiting LIVE push run
    # are cancelled and re-run behind it, and runs on moved heads are cancelled. A failure here is
    # logged and never stops the sweep.
    try {
        $env:GH_BIN = $Gh
        & $Python -I -u (Join-Path $Clone "scripts\live_first_ci.py") --repo $Repo --base $Live --state (Join-Path $QuantRoot "desks\mt5\reports\LIVE_FIRST_CI.json") 2>&1 | ForEach-Object { Say "live-first $_" }
    } catch {
        Say "live-first failed: $($_.Exception.Message)"
    }

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
    $merged = @($out -split "`r?`n" | Where-Object { $_ -match 'MERGED' }).Count
    $note = "gate@{0}: {1} merged" -f $at, $merged
    if (-not $scope) { $note += "; NO workflow scope: run once  gh auth refresh -h github.com -s workflow" }
    Beat $rc $note $scope
    Watch
    exit $rc
} catch {
    Say "FAILED: $($_.Exception.Message)"
    Beat 1 "FAILED: $($_.Exception.Message)" $false
    Watch  # a sweep that fails every run still writes its RED (#521 audit MF-A)
    exit 1
} finally {
    $mutex.ReleaseMutex()
}
