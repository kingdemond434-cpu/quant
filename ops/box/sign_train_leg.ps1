# THE SIGN TRAIN'S CLOCK (2026-10-29).
#
# scripts/sign_train.py signs a moved sealed file once its CLEAR row is committed in
# desks/mt5/data/SEAL_CLEARS.jsonl (D-20261027-003: the audit signs, not a person), but nothing
# ran it: runtime_state listed it UNMEASURED with no cadence (Desk health 19:30Z). This is that
# clock. Each run takes a clean, detached checkout of origin/LIVE, runs the auditor-clear sign at
# that head, and when it signs, pushes claude/sign-train-<head> and opens its PR into LIVE with
# zuck's gh login, so the PR's CI runs and the gate merges it like any other.
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
function Beat([int] $rc, [string] $note, [int] $held = 0) {
    $fails = 0
    if ($rc -ne 0 -and $rc -ne 4) { $fails = (Prev 'fail_runs') + 1 } elseif ($rc -eq 4) { $fails = Prev 'fail_runs' }
    $doc = [ordered]@{ at = (Get-Date).ToUniversalTime().ToString('o'); rc = $rc; note = $note; fail_runs = $fails; mutex_held_runs = $held }
    $doc | ConvertTo-Json -Compress | Set-Content -LiteralPath "$beat.tmp" -Encoding UTF8
    Move-Item -LiteralPath "$beat.tmp" -Destination $beat -Force
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

    # One sign at a time: an open sign-train PR is waited for, never stacked on. Searched by head,
    # never a bare list (30 PRs by default; #541 audit MF1); a full page is refused, not trusted.
    $open = (& $Gh pr list -R $Repo --base $Live --state open --search "head:claude/sign-train-" --limit 100 --json headRefName --jq '.[].headRefName' 2>&1 | Out-String)
    if ($LASTEXITCODE -ne 0) { throw "gh pr list failed: $($open.Trim())" }
    $listed = @($open -split "`r?`n" | Where-Object { $_ })
    if ($listed.Count -ge 100) { throw "100 or more PRs matched head:claude/sign-train-; the list may be cut" }
    $waiting = @($listed | Where-Object { $_ -like 'claude/sign-train-*' })
    if ($waiting.Count -gt 0) { Say "waiting on $($waiting -join ', ')"; Beat 0 "waiting on $($waiting[0])"; exit 0 }

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
    # A branch the train already pushed for this head (its PR never opened: gh failed after the
    # push) is reused, never re-signed: a second sign makes a new commit the push would refuse
    # forever (#541 audit MF2). It must be the train's own commit, alone on this head.
    $remote = (& git -C $Clone ls-remote origin "refs/heads/$branch" 2>&1 | Out-String).Trim()
    if ($LASTEXITCODE -ne 0) { throw "git ls-remote failed: $remote" }
    if ($remote) {
        & git -C $Clone fetch -q --no-tags origin "+refs/heads/${branch}:refs/remotes/origin/${branch}" 2>&1 | ForEach-Object { Say "fetch: $_" }
        $parent = (& git -C $Clone rev-parse "origin/$branch~1").Trim()
        $subject = (& git -C $Clone log -1 --format=%s "origin/$branch").Trim()
        if ($parent -ne $head -or -not $subject.StartsWith("Sign train at $($head.Substring(0, 12))")) {
            throw "$branch exists but is not the train's own commit on $short; not touched"
        }
        $out = "reused the pushed $branch ($subject)"
        Say "train@$short $out"
    } else {
        Push-Location -LiteralPath $Clone
        try {
            $lines = New-Object System.Collections.Generic.List[string]
            & $Python -u "scripts\sign_train.py" --target $head --push 2>&1 | ForEach-Object {
                $l = "$_"
                if ($l) { Say "train@$short $l"; $lines.Add($l) }
            }
            $rc = $LASTEXITCODE
            $out = $lines -join "`n"
        } finally { Pop-Location }
        if ($rc -ne 0) { Beat $rc "train@$short rc=$rc"; exit $rc }
        # Signed or not is read from git, not from the train's wording (#541 audit S3): a sign is
        # exactly one new commit whose parent is the target.
        $now = (& git -C $Clone rev-parse HEAD).Trim()
        if ($now -eq $head) { Beat 0 "train@${short}: nothing to sign"; exit 0 }
        if ((& git -C $Clone rev-parse "HEAD~1").Trim() -ne $head) { throw "HEAD $now does not sit on the target $short" }
    }

    $body = "The sign train signed at $head from the CLEAR rows committed in desks/mt5/data/SEAL_CLEARS.jsonl (D-20261027-003).`n`n``````n$out`n``````n`nOpened by ops/box/sign_train_leg.ps1."
    $pr = (& $Gh pr create -R $Repo --base $Live --head $branch --title "Sign train at $($head.Substring(0, 12))" --body $body 2>&1 | Out-String)
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
