# THE SIGN TRAIN'S CLOCK (2026-10-29).
#
# scripts/sign_train.py signs a moved sealed file once its CLEAR row is committed in
# desks/mt5/data/SEAL_CLEARS.jsonl (D-20261027-003: the audit signs, not a person), but nothing
# ran it: runtime_state listed it UNMEASURED with no cadence (Desk health 19:30Z). This is that
# clock. Each run takes a clean, detached checkout of origin/LIVE, runs the auditor-clear sign at
# that head, and when it signs, pushes claude/sign-train-<head> and opens its PR into LIVE with
# zuck's gh login, so the PR's CI runs and the gate merges it like any other.
#
# THE BOX VOUCHES ONLY FOR BYTES IT SIGNED (#541 audit v2 MF1). Every run signs locally and
# force-pushes its own commit to claude/sign-train-<head>: whatever was on that branch before
# (a half-finished run, or anything planted there) is replaced, never reused. No text from git
# or the train reaches gh's arguments: the PR body goes through --body-file (v2 MF2).
#
# It never signs on its own say: no CLEAR row, no sign, and every refusal of sign_train.py stands
# (1aa4b33f is never signed, QB-002 must be green after). It never takes --principal or --expect.
# A run while a sign-train PR is still open does nothing, so one sign waits for the last.
#
# TRUSTED CODE ONLY, as in workflow_gate.ps1: the train is read from origin/LIVE, never a PR. No
# token is read, printed or stored here; gh keeps zuck's login in Windows Credential Manager. No
# elevation is needed. Heartbeat: logs\sign_train.json (rc, note, at).

[CmdletBinding()]
param(
    [string] $Root = "C:\ProgramData\QuantBox",
    [string] $Repo = "kingdemond434-cpu/quant",
    [string] $Live = "claude/llm-auto-upgrade-verify-gcjac3",
    [string] $Gh = "C:\Users\Administrator\tools\gh\bin\gh.exe",
    # the desk's own interpreter: QB-002 runs under pytest
    [string] $Python = "C:\opt\quant\.venv\Scripts\python.exe"
)
$ErrorActionPreference = 'Stop'
$LogDir = Join-Path $Root "logs"
$Clone = Join-Path $Root "sign-repo"
$log = Join-Path $LogDir "sign_train.log"
$beat = Join-Path $LogDir "sign_train.json"

function Say([string] $line) {
    Add-Content -LiteralPath $log -Value ("{0} {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ssK'), $line)
}
# The beat counts runs in a row that failed (fail_runs) or found the mutex held
# (mutex_held_runs): scripts/merge_pipeline_watch.py reads it and goes RED past two of either,
# or when it is over 30 min old (#541 audit MF3, S1).
function Prev([string] $key) {
    try { return [int]((Get-Content -LiteralPath $beat -Raw | ConvertFrom-Json).$key) } catch { return 0 }
}
function Beat([int] $rc, [string] $note, [int] $held = 0, [string] $waitingOn = '', [string] $waitingSince = '') {
    $fails = 0
    if ($rc -ne 0 -and $rc -ne 4) { $fails = (Prev 'fail_runs') + 1 } elseif ($rc -eq 4) { $fails = Prev 'fail_runs' }
    $doc = [ordered]@{ at = (Get-Date).ToUniversalTime().ToString('o'); rc = $rc; note = $note; fail_runs = $fails; mutex_held_runs = $held }
    if ($waitingOn) { $doc.waiting_on = $waitingOn; $doc.waiting_since = $waitingSince }
    [System.IO.File]::WriteAllText("$beat.tmp", ($doc | ConvertTo-Json -Compress), (New-Object System.Text.UTF8Encoding($false)))
    Move-Item -LiteralPath "$beat.tmp" -Destination $beat -Force
}
# A wait keeps the first time it was seen, so a wait that never ends goes RED (v2 SF, v3 MF1).
function Wait([string] $on, [string] $note) {
    $since = (Get-Date).ToUniversalTime().ToString('o')
    try { $prev = Get-Content -LiteralPath $beat -Raw | ConvertFrom-Json; if ($prev.waiting_on -eq $on -and $prev.waiting_since) { $since = $prev.waiting_since } } catch { }
    Say $note; Beat 0 $note 0 $on $since
}
# gh's answer to a count query is its stdout alone, and it must be a number (v3 MF1): stderr
# text such as an update notice can never read as "not zero".
function GhCount([string[]] $ghArgs) {
    $err = Join-Path $LogDir "sign_train_gh.err"
    $out = (& $Gh @ghArgs 2>$err | Out-String).Trim()
    if ($LASTEXITCODE -ne 0) { throw "gh $($ghArgs[0..1] -join ' ') failed ($LASTEXITCODE): $((Get-Content -LiteralPath $err -Raw -ErrorAction SilentlyContinue))" }
    if ($out -notmatch '^\d+$') { throw "gh $($ghArgs[0..1] -join ' ') answered '$out', not a count" }
    return [int]$out
}

# A run the task's time limit killed leaves the mutex abandoned: the next run owns it (#541 S2).
$mutex = New-Object System.Threading.Mutex($false, "Global\QuantBox-SignTrain")
try { $got = $mutex.WaitOne(0) } catch [System.Threading.AbandonedMutexException] { $got = $true; Say "the last run was killed holding the mutex; taken over" }
if (-not $got) {
    $held = (Prev 'mutex_held_runs') + 1
    Say "the previous run still holds the mutex (run $held in a row)"
    Beat 4 "mutex held by the previous run ($held runs in a row)" $held
    exit 4
}
if ((Test-Path -LiteralPath $log) -and (Get-Item -LiteralPath $log).Length -gt 5MB) {
    Move-Item -LiteralPath $log -Destination "$log.1" -Force
}

foreach ($v in @('GITHUB_TOKEN', 'GH_TOKEN', 'GH_ENTERPRISE_TOKEN', 'GITHUB_ENTERPRISE_TOKEN')) {
    Remove-Item -LiteralPath "env:$v" -ErrorAction SilentlyContinue
}
$env:GH_PROMPT_DISABLED = '1'
$env:GIT_TERMINAL_PROMPT = '0'
# Command-scope config only. autocrlf off: the manifest pins the committed bytes, and a CRLF
# checkout would read every sealed file as moved.
$env:GIT_CONFIG_COUNT = '2'
$env:GIT_CONFIG_KEY_0 = 'safe.directory'
$env:GIT_CONFIG_VALUE_0 = ($Clone -replace '\\', '/')
$env:GIT_CONFIG_KEY_1 = 'core.autocrlf'
$env:GIT_CONFIG_VALUE_1 = 'false'
$env:GIT_AUTHOR_NAME = 'sign-train'
$env:GIT_AUTHOR_EMAIL = 'sign-train@quantbox.invalid'
$env:GIT_COMMITTER_NAME = $env:GIT_AUTHOR_NAME
$env:GIT_COMMITTER_EMAIL = $env:GIT_AUTHOR_EMAIL
$env:PATH = (Split-Path -Parent $Gh) + ';' + $env:PATH

try {
    if (-not (Test-Path -LiteralPath $Python)) { throw "no desk Python at $Python" }
    $ErrorActionPreference = 'Continue'  # native stderr is data; exit codes are the verdict

    # One sign at a time: an open sign-train PR is waited for, never stacked on. Every
    # claude/sign-train-* branch is listed from git and each is asked for an open PR by its exact
    # head (#541 audit MF1, v2 SF): no search prefix is trusted.
    $refs = (& git ls-remote "https://github.com/$Repo.git" 'refs/heads/claude/sign-train-*' 2>$null)
    if ($LASTEXITCODE -ne 0) { throw "git ls-remote failed ($LASTEXITCODE)" }
    $remoteSha = @{}
    foreach ($r in $refs) {
        if ("$r" -match '^([0-9a-f]{40})\s+refs/heads/(claude/sign-train-[0-9a-f]+)$') { $remoteSha[$Matches[2]] = $Matches[1] }
    }
    foreach ($b in $remoteSha.Keys) {
        if ((GhCount @('pr', 'list', '-R', $Repo, '--head', $b, '--state', 'open', '--json', 'number', '--jq', 'length')) -ne 0) {
            Wait $b "waiting on $b"; exit 0
        }
    }

    # Full history (the CLEAR record must be proven append-only), blobs fetched as needed.
    if (-not (Test-Path -LiteralPath (Join-Path $Clone ".git"))) {
        & git clone -q --filter=blob:none --no-checkout "https://github.com/$Repo.git" $Clone 2>&1 | ForEach-Object { Say "clone: $_" }
        if ($LASTEXITCODE -ne 0) { throw "git clone failed ($LASTEXITCODE)" }
    }
    & git -C $Clone fetch -q --no-tags origin "+refs/heads/${Live}:refs/remotes/origin/${Live}" 2>&1 | ForEach-Object { Say "fetch: $_" }
    if ($LASTEXITCODE -ne 0) { throw "git fetch failed ($LASTEXITCODE)" }
    & git -C $Clone checkout -q -f --detach "origin/$Live" 2>&1 | ForEach-Object { Say "checkout: $_" }
    if ($LASTEXITCODE -ne 0) { throw "git checkout failed ($LASTEXITCODE)" }
    & git -C $Clone clean -q -fdx 2>&1 | ForEach-Object { Say "clean: $_" }
    $head = (& git -C $Clone rev-parse HEAD).Trim()
    $branch = "claude/sign-train-$($head.Substring(0, 12))"

    $short = $head.Substring(0, 9)
    # A sign PR a person closed unmerged is not opened again for the same head (v2 SF): the
    # train waits for LIVE to move.
    if ((GhCount @('pr', 'list', '-R', $Repo, '--head', $branch, '--state', 'closed', '--json', 'mergedAt', '--jq', '[.[] | select(.mergedAt == null)] | length')) -ne 0) {
        Wait $branch "a sign PR for $short was closed unmerged; waiting for LIVE to move"; exit 0
    }

    Push-Location -LiteralPath $Clone
    try {
        & $Python -u "scripts\sign_train.py" --target $head 2>&1 | ForEach-Object {
            $l = "$_"
            if ($l) { Say "train@$short $l" }
        }
        $rc = $LASTEXITCODE
    } finally { Pop-Location }
    if ($rc -ne 0) { Beat $rc "train@$short rc=$rc"; exit $rc }
    # Signed or not is read from git, not from the train's wording (#541 audit S3): a sign is
    # exactly one new commit whose parent is the target.
    $now = (& git -C $Clone rev-parse HEAD).Trim()
    if ($now -eq $head) { Beat 0 "train@${short}: nothing to sign"; exit 0 }
    # Exactly one single-parent commit on the target, touching exactly the two sealed-state files
    # (v3 SF): anything else the train left is never pushed.
    $parents = @((& git -C $Clone rev-list --parents -n 1 HEAD).Trim() -split '\s+')
    if ($parents.Count -ne 2 -or $parents[1] -ne $head) { throw "HEAD $now is not one single-parent commit on $short" }
    if ((& git -C $Clone rev-list --count "$head..HEAD").Trim() -ne '1') { throw "more than one commit over $short" }
    $touched = @(& git -C $Clone diff --name-only $head HEAD | Sort-Object)
    if (($touched -join ',') -ne 'desks/mt5/data/IMMUTABLE_MANIFEST.json,desks/mt5/research/quantbench.py') { throw "the sign touched $($touched -join ', ')" }
    # The lease is the branch as git listed it at the start, or absent (v3 SF): a branch that
    # moved since is never overwritten.
    $lease = "refs/heads/${branch}:$($remoteSha[$branch])"
    & git -C $Clone push -q "--force-with-lease=$lease" origin "HEAD:refs/heads/$branch" 2>&1 | ForEach-Object { Say "push: $_" }
    if ($LASTEXITCODE -ne 0) { throw "git push of $branch failed ($LASTEXITCODE)" }

    # Fixed text only, through a file: nothing from git or the train reaches gh's argv (v2 MF2).
    $bodyFile = Join-Path $LogDir "sign_train_body.md"
    [System.IO.File]::WriteAllText($bodyFile, ("The sign train signed LIVE at $head from the CLEAR rows committed in desks/mt5/data/SEAL_CLEARS.jsonl (D-20261027-003).`n`nOpened by ops/box/sign_train_leg.ps1; its log is logs\sign_train.log on the box."), (New-Object System.Text.UTF8Encoding($false)))
    $pr = (& $Gh pr create -R $Repo --base $Live --head $branch --title "Sign train at $($head.Substring(0, 12))" --body-file $bodyFile 2>&1 | Out-String)
    if ($LASTEXITCODE -ne 0) { throw "gh pr create failed: $($pr.Trim())" }
    Say "opened $($pr.Trim())"
    Beat 0 "signed at $($head.Substring(0, 9)): $($pr.Trim())"
    exit 0
} catch {
    Say "FAILED: $($_.Exception.Message)"
    Beat 1 "FAILED: $($_.Exception.Message)"
    exit 1
} finally {
    $mutex.ReleaseMutex()
}
