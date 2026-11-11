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
#
# A PR HEAD, NOT LIVE'S (2026-11-11, Desk health's read sign_train_pr_head_read G1-G10). CI's
# law gate refuses unsigned sealed bytes, so they never reach LIVE and a train that signed only
# LIVE's head never had anything to sign. Each run now asks LIVE's own sign_train.py which PR
# heads LIVE's committed SEAL_CLEARS rows clear (`head` field), takes the oldest one an open PR
# into LIVE still points at, checks it out as a separate DATA worktree, and runs LIVE's train
# with --root on it: no PR file is ever imported, executed or used as a hook (G1, G2). The head
# is read again just before the push and any move aborts the run (G5). The signed commit goes to
# claude/sign-train-<head12>, never to the PR's own branch (G7), and its PR carries the whole
# original diff plus the one train commit (G8). Under the bin stub (sign_train_stub.ps1) this file
# is read fresh from LIVE each run, so a change here needs no re-install.
#
# The desk interpreter is the system Python 3.14 (Desk health BH2: the old virtualenv path never existed
# on this box and the task failed 21 runs in a row). QB-002 is now a static check, no test run.

[CmdletBinding()]
param(
    [string] $Root = "C:\ProgramData\QuantBox",
    [string] $Repo = "kingdemond434-cpu/quant",
    [string] $Live = "claude/llm-auto-upgrade-verify-gcjac3",
    [string] $Gh = "C:\Users\Administrator\tools\gh\bin\gh.exe",
    # the box's system interpreter (BH2); the train is stdlib only and runs isolated (-I)
    [string] $Python = "C:\Program Files\Python314\python.exe"
)
$ErrorActionPreference = 'Stop'
$LogDir = Join-Path $Root "logs"
$Clone = Join-Path $Root "sign-repo"
$PrDir = Join-Path $Root "sign-pr"  # the PR head, checked out as data (a worktree of the clone)
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

# gh's list of 40-hex lines (stdout only), for comparing in PowerShell: Windows PowerShell drops
# the quotes a jq string literal would need in a native argument.
function GhLines([string[]] $ghArgs) {
    $err = Join-Path $LogDir "sign_train_gh.err"
    $out = (& $Gh @ghArgs 2>$err | Out-String)
    if ($LASTEXITCODE -ne 0) { throw "gh $($ghArgs[0..1] -join ' ') failed ($LASTEXITCODE): $((Get-Content -LiteralPath $err -Raw -ErrorAction SilentlyContinue))" }
    $lines = @($out -split "`r?`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ })
    foreach ($l in $lines) { if ($l -notmatch '^[0-9a-f]{40}$') { throw "gh $($ghArgs[0..1] -join ' ') answered '$l', not a commit" } }
    return $lines
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
$env:GIT_CONFIG_COUNT = '4'  # safe.directory x2, autocrlf, hooksPath; merger_env appends after these
$env:GIT_CONFIG_KEY_0 = 'safe.directory'
$env:GIT_CONFIG_VALUE_0 = ($Clone -replace '\\', '/')
$env:GIT_CONFIG_KEY_1 = 'core.autocrlf'
$env:GIT_CONFIG_VALUE_1 = 'false'
$env:GIT_CONFIG_KEY_2 = 'safe.directory'
$env:GIT_CONFIG_VALUE_2 = ($PrDir -replace '\\', '/')
# G1 (Auditor, 2026-11-11): NO git operation in this leg ever runs a hook, so none can take a
# hooksPath from the PR tree: every git call here (worktree add, commit, push) reads this empty,
# admin-only folder as its hooks directory.
$NoHooks = Join-Path $Root "nohooks"
$env:GIT_CONFIG_KEY_3 = 'core.hooksPath'
$env:GIT_CONFIG_VALUE_3 = ($NoHooks -replace '\\', '/')
$ownConfig = '4'  # the train's child runs with these entries only: no App header (G2)
$env:GIT_AUTHOR_NAME = 'sign-train'
$env:GIT_AUTHOR_EMAIL = 'sign-train@quantbox.invalid'
$env:GIT_COMMITTER_NAME = $env:GIT_AUTHOR_NAME
$env:GIT_COMMITTER_EMAIL = $env:GIT_AUTHOR_EMAIL
$env:PATH = (Split-Path -Parent $Gh) + ';' + $env:PATH
# LEVEL 2 step 3: the quant-merger App when installed (ops/release/merger/merger_env.ps1, read
# from the train's own clean clone of LIVE); otherwise zuck's gh login as before.
$mergerEnv = Join-Path $Clone "ops\release\merger\merger_env.ps1"
if (Test-Path -LiteralPath $mergerEnv) { . $mergerEnv; $null = Use-MergerIdentity $Clone }

try {
    if (-not (Test-Path -LiteralPath $Python)) { throw "no desk Python at $Python" }
    New-Item -ItemType Directory -Force -Path $NoHooks | Out-Null
    if (@(Get-ChildItem -LiteralPath $NoHooks -Force).Count -ne 0) { throw "$NoHooks is not empty; no git call runs while it holds anything" }
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
    $live = (& git -C $Clone rev-parse HEAD).Trim()
    $liveShort = $live.Substring(0, 9)

    # G3: the heads LIVE's own record clears, read by LIVE's own train (append-only proven).
    $heads = New-Object System.Collections.Generic.List[string]
    Push-Location -LiteralPath $Clone
    try {
        & $Python -I -B -u "scripts\sign_train.py" --list-heads 2>&1 | ForEach-Object {
            $l = "$_".Trim()
            if ($l -match '^[0-9a-f]{40}$') { $heads.Add($l) } elseif ($l) { Say "list@$liveShort $l" }
        }
        $rc = $LASTEXITCODE
    } finally { Pop-Location }
    if ($rc -ne 0) { Beat $rc "list@$liveShort rc=$rc"; exit $rc }
    if ($heads.Count -eq 0) { Beat 0 "live@${liveShort}: no cleared PR head to sign"; exit 0 }

    # Every branch tip, once: a head is signed only while a branch still points at it.
    $tips = (& git ls-remote "https://github.com/$Repo.git" 'refs/heads/*' 2>$null)
    if ($LASTEXITCODE -ne 0) { throw "git ls-remote failed ($LASTEXITCODE)" }
    $pick = $null; $prBranch = $null; $carrierTip = $null
    foreach ($h in $heads) {
        $branch = "claude/sign-train-$($h.Substring(0, 12))"
        if ((GhCount @('pr', 'list', '-R', $Repo, '--head', $branch, '--state', 'closed', '--json', 'mergedAt', '--jq', '[.[] | select(.mergedAt == null)] | length')) -ne 0) {
            Say "a sign PR for $($h.Substring(0, 9)) was closed unmerged; not signed again"; continue
        }
        foreach ($t in $tips) {
            if ("$t" -notmatch '^([0-9a-f]{40})\s+refs/heads/([A-Za-z0-9._/-]+)$') { continue }
            if ($Matches[1] -ne $h -or $Matches[2] -like 'claude/sign-train-*' -or $Matches[2] -eq $Live) { continue }
            $b = $Matches[2]
            # an open PR into LIVE whose head is exactly this commit (h is 40-hex, checked above)
            if ((GhLines @('pr', 'list', '-R', $Repo, '--head', $b, '--base', $Live, '--state', 'open', '--json', 'headRefOid', '--jq', '.[].headRefOid')) -contains $h) { $pick = $h; $prBranch = $b; break }
        }
        if ($pick) { break }
        # SEAL CARRIER (Auditor ruling 13:12Z): the pre-push gate keeps unsigned sealed bytes off
        # every branch, so a cleared head may ride claude/seal-carrier-<h12> as a bundle + patch.
        # Its open PR into LIVE must point at the carrier's exact tip; it never merges.
        $cb = "claude/seal-carrier-$($h.Substring(0, 12))"
        foreach ($t in $tips) {
            if ("$t" -notmatch '^([0-9a-f]{40})\s+refs/heads/([A-Za-z0-9._/-]+)$' -or $Matches[2] -ne $cb) { continue }
            $ct = $Matches[1]
            if ((GhLines @('pr', 'list', '-R', $Repo, '--head', $cb, '--base', $Live, '--state', 'open', '--json', 'headRefOid', '--jq', '.[].headRefOid')) -contains $ct) { $pick = $h; $prBranch = $cb; $carrierTip = $ct }
            break
        }
        if ($pick) { break }
        Say "no open PR into LIVE points at $($h.Substring(0, 9)) or carries it any more; skipped"
    }
    if (-not $pick) { Beat 0 "live@${liveShort}: $($heads.Count) cleared head(s), none still a PR head"; exit 0 }
    $head = $pick
    $short = $head.Substring(0, 9)
    $branch = "claude/sign-train-$($head.Substring(0, 12))"

    # G10: the PR head (or its carrier) by its branch ref, never refs/pull/*/merge.
    $watch = $head; if ($carrierTip) { $watch = $carrierTip }
    & git -C $Clone fetch -q --no-tags origin "+refs/heads/${prBranch}:refs/remotes/pr/${prBranch}" 2>&1 | ForEach-Object { Say "fetch pr: $_" }
    if ($LASTEXITCODE -ne 0) { throw "git fetch of the PR branch failed ($LASTEXITCODE)" }
    if ((& git -C $Clone rev-parse "refs/remotes/pr/$prBranch").Trim() -ne $watch) { Wait $branch "the PR branch moved off $($watch.Substring(0, 9)) while fetched; next run"; exit 0 }

    # G2 for every child: no App token and no App header; only LIVE's code runs.
    $savedTok = $env:GH_TOKEN; $savedCount = $env:GIT_CONFIG_COUNT
    if ($carrierTip) {
        # The carrier is re-judged by LIVE's train with LIVE's proven record, the same checks
        # as the push fence, and only then is its head fetched (refs/carriers/<head>).
        Remove-Item -LiteralPath env:GH_TOKEN -ErrorAction SilentlyContinue
        $env:GIT_CONFIG_COUNT = $ownConfig
        $carried = $null
        Push-Location -LiteralPath $Clone
        try {
            & $Python -I -B -u "scripts\sign_train.py" --carrier $carrierTip 2>&1 | ForEach-Object {
                $l = "$_".Trim()
                if ($l -match '^[0-9a-f]{40}$') { $carried = $l } elseif ($l) { Say "carrier@$short $l" }
            }
            $rc = $LASTEXITCODE
        } finally {
            Pop-Location
            if ($savedTok) { $env:GH_TOKEN = $savedTok }
            $env:GIT_CONFIG_COUNT = $savedCount
        }
        if ($rc -ne 0 -or $carried -ne $head) { Beat 2 "carrier@$short refused (rc=$rc)"; exit 2 }
    }

    # The PR head as DATA: a fresh detached worktree, replaced every run.
    if (Test-Path -LiteralPath $PrDir) {
        & git -C $Clone worktree remove --force $PrDir 2>&1 | ForEach-Object { Say "worktree: $_" }
        if (Test-Path -LiteralPath $PrDir) { Remove-Item -LiteralPath $PrDir -Recurse -Force }
    }
    & git -C $Clone worktree prune 2>&1 | ForEach-Object { Say "worktree: $_" }
    & git -C $Clone worktree add -q -f --detach $PrDir $head 2>&1 | ForEach-Object { Say "worktree: $_" }
    if ($LASTEXITCODE -ne 0) { throw "git worktree add failed ($LASTEXITCODE)" }

    # G2: the train's child holds no App token and no App header; it runs only LIVE's code.
    Remove-Item -LiteralPath env:GH_TOKEN -ErrorAction SilentlyContinue
    $env:GIT_CONFIG_COUNT = $ownConfig
    Push-Location -LiteralPath $Clone
    try {
        & $Python -I -B -u "scripts\sign_train.py" --root $PrDir --target $head 2>&1 | ForEach-Object {
            $l = "$_"
            if ($l) { Say "train@$short $l" }
        }
        $rc = $LASTEXITCODE
    } finally {
        Pop-Location
        if ($savedTok) { $env:GH_TOKEN = $savedTok }
        $env:GIT_CONFIG_COUNT = $savedCount
    }
    if ($rc -ne 0) { Beat $rc "train@$short rc=$rc"; exit $rc }
    # Signed or not is read from git, not from the train's wording (#541 audit S3): a sign is
    # exactly one new commit whose parent is the target.
    $now = (& git -C $PrDir rev-parse HEAD).Trim()
    if ($now -eq $head) { Beat 0 "train@${short}: nothing to sign"; exit 0 }
    # Exactly one single-parent commit on the target, touching exactly the two sealed-state files
    # (v3 SF, G7): anything else the train left is never pushed.
    $parents = @((& git -C $PrDir rev-list --parents -n 1 HEAD).Trim() -split '\s+')
    if ($parents.Count -ne 2 -or $parents[1] -ne $head) { throw "HEAD $now is not one single-parent commit on $short" }
    if ((& git -C $PrDir rev-list --count "$head..HEAD").Trim() -ne '1') { throw "more than one commit over $short" }
    $touched = @(& git -C $PrDir diff --name-only $head HEAD | Sort-Object)
    if (($touched -join ',') -ne 'desks/mt5/data/IMMUTABLE_MANIFEST.json,desks/mt5/research/quantbench.py') { throw "the sign touched $($touched -join ', ')" }

    # G5: the PR branch still points at the signed head, and LIVE has not moved.
    $again = (& git ls-remote "https://github.com/$Repo.git" "refs/heads/$prBranch" "refs/heads/$Live" 2>$null)
    if ($LASTEXITCODE -ne 0) { throw "git ls-remote failed ($LASTEXITCODE)" }
    $nowPr = $null; $nowLive = $null
    foreach ($r in $again) {
        if ("$r" -match '^([0-9a-f]{40})\s+refs/heads/(.+)$') {
            if ($Matches[2] -eq $prBranch) { $nowPr = $Matches[1] } elseif ($Matches[2] -eq $Live) { $nowLive = $Matches[1] }
        }
    }
    if ($nowPr -ne $watch) { Wait $branch "the PR branch moved off $short before the push; nothing pushed"; exit 0 }
    if ($nowLive -ne $live) { Wait $branch "LIVE moved off $liveShort before the push; nothing pushed, next run"; exit 0 }

    # The lease is the branch as git listed it at the start, or absent (v3 SF): a branch that
    # moved since is never overwritten.
    $lease = "refs/heads/${branch}:$($remoteSha[$branch])"
    & git -C $PrDir push -q "--force-with-lease=$lease" origin "HEAD:refs/heads/$branch" 2>&1 | ForEach-Object { Say "push: $_" }
    if ($LASTEXITCODE -ne 0) { throw "git push of $branch failed ($LASTEXITCODE)" }

    # Fixed text only, through a file: nothing from git or the train reaches gh's argv (v2 MF2).
    $bodyFile = Join-Path $LogDir "sign_train_body.md"
    [System.IO.File]::WriteAllText($bodyFile, ("The sign train signed the PR head $head (branch $prBranch) from the CLEAR rows for that exact head committed on LIVE in desks/mt5/data/SEAL_CLEARS.jsonl (D-20261027-003). This PR carries that PR's whole diff plus one train commit touching only IMMUTABLE_MANIFEST.json and quantbench.py; it supersedes that PR, which GitHub closes as merged when this one lands.`n`nOpened by ops/box/sign_train_leg.ps1 with LIVE's sign_train.py at $live; its log is logs\sign_train.log on the box."), (New-Object System.Text.UTF8Encoding($false)))
    $pr = (& $Gh pr create -R $Repo --base $Live --head $branch --title "Sign train at $($head.Substring(0, 12))" --body-file $bodyFile 2>&1 | Out-String)
    if ($LASTEXITCODE -ne 0) { throw "gh pr create failed: $($pr.Trim())" }
    Say "opened $($pr.Trim())"
    if ($carrierTip) {
        # The carrier's job is done: H+1 is signed and has its own PR. Close the carrier (it
        # never merges) and write the ledger row. Numbers only reach gh's argv.
        $err = Join-Path $LogDir "sign_train_gh.err"
        $nums = @((& $Gh pr list -R $Repo --head $prBranch --base $Live --state open --json number --jq '.[].number' 2>$err | Out-String) -split "`r?`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ -match '^\d+$' })
        foreach ($n in $nums) {
            & $Gh pr close $n -R $Repo 2>&1 | ForEach-Object { Say "close carrier #${n}: $_" }
            if ($LASTEXITCODE -ne 0) { Say "carrier #$n not closed ($LASTEXITCODE); the CI fence still refuses its merge" }
        }
        $row = [ordered]@{ at = (Get-Date).ToUniversalTime().ToString('o'); head = $head; carrier_branch = $prBranch; carrier_tip = $carrierTip; carrier_prs = @($nums); sign_branch = $branch; live = $live }
        [System.IO.File]::AppendAllText((Join-Path $LogDir "seal_carriers.jsonl"), (($row | ConvertTo-Json -Compress) + "`n"), (New-Object System.Text.UTF8Encoding($false)))
    }
    Beat 0 "signed PR head $short ($prBranch): $($pr.Trim())"
    exit 0
} catch {
    Say "FAILED: $($_.Exception.Message)"
    Beat 1 "FAILED: $($_.Exception.Message)"
    exit 1
} finally {
    $mutex.ReleaseMutex()
}
