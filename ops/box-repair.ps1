<#
.SYNOPSIS
  One command that puts the trading box back into a state where the desk can run.

.DESCRIPTION
  WHY THIS EXISTS. On 2026-09-06 the box was brought back from ten days of silence, and it took
  several hundred manual commands. Not one of the faults was hard; the cost was that NONE OF THEM
  ANNOUNCED ITSELF, and each hid the next:

      the MT5 terminal never started        every research organ then reported its own symptom
      universe.json was empty               the gauntlet refused 15,275 cells as "unknown symbol"
      26 files held merge-conflict markers  families.py could not import, so nothing ran at all
      git had aborted every pull for days   so no fix could reach the machine in the first place

  Each step below checks ONE of those, reports what it found, and refuses to pretend. A step that
  fails prints its cause and the run continues to the remaining independent steps -- but the
  summary at the end names every failure, so a half-repaired box cannot be mistaken for a fixed one.

  WHAT IT WILL NOT DO. It never force-pushes, never resets, never stashes (a stash in a shared
  tree is how work disappears), and never deletes a file it has not first copied to the backup
  directory. Where a decision is genuinely the operator's -- a code conflict, a lost
  parameterisation -- it stops and says so rather than choosing.

.EXAMPLE
  .\ops\box-repair.ps1
  .\ops\box-repair.ps1 -SkipBars              # skip the slow bar download
  .\ops\box-repair.ps1 -WhatIf                # report only, change nothing
  .\ops\box-repair.ps1 -ResolveCode theirs    # take the repository's code for conflicting files
#>
[CmdletBinding()]
param(
    [string]$Root      = "C:\opt\quant",
    [string]$Branch    = "claude/llm-auto-upgrade-verify-gcjac3",
    [string]$Terminal  = "C:\Program Files\Fusion Markets MetaTrader 5\terminal64.exe",
    [string]$BackupDir = "C:\opt\quant-backup",
    [switch]$SkipBars,
    [switch]$WhatIf,
    # EVERY CHART THE BROKER OFFERS, because a cell held for want of a download is not evidence
    # about the cell. H1 is always fetched first and alone so the gauntlet is unblocked within a
    # minute; the rest follow. Narrow this only when time genuinely matters -- the default is the
    # whole set on purpose.
    [string[]]$BarTimeframes = @("H1", "M1", "M5", "M15", "M30", "H4", "D1"),
    # WHICH SIDE OF A CODE CONFLICT WINS -- NAMED BY THE OPERATOR, NEVER GUESSED.
    #
    #   none    (default) refuse, list the files, and leave the merge for a human.
    #   theirs  take the REPOSITORY's version. The box runs code; the repo is where code is
    #           reviewed, so this is the usual intent after a spell of local drift.
    #   ours    keep the BOX's version, for when the box holds a fix the repo has not seen.
    #
    # Neither choice can destroy work: every conflicted file is copied to $BackupDir first, with
    # both sides preserved, and the summary says where. That is what makes an automatic choice
    # defensible here -- the decision is reversible, so it is no longer the one-way door the
    # refusal exists to protect.
    [ValidateSet("none", "ours", "theirs")]
    [string]$ResolveCode = "none"
)

$ErrorActionPreference = "Continue"
$script:Failures = @()
$script:Notes    = @()

function Step   ($n) { Write-Host ""; Write-Host "== $n" -ForegroundColor Cyan }
function Ok     ($m) { Write-Host "   OK    $m" -ForegroundColor Green }
function Warn   ($m) { Write-Host "   WARN  $m" -ForegroundColor Yellow; $script:Notes += $m }
function Fail   ($m) { Write-Host "   FAIL  $m" -ForegroundColor Red;   $script:Failures += $m }
function Info   ($m) { Write-Host "   ...   $m" -ForegroundColor Gray }

if (-not (Test-Path $Root)) { Write-Host "No checkout at $Root" -ForegroundColor Red; exit 2 }
Set-Location $Root

# ---------------------------------------------------------------- 0. privileges
Step "Privileges"
$elevated = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
            ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if ($elevated) { Ok "elevated" }
else {
    # NOT FATAL, and that is deliberate. Most of this script works unelevated; only taking
    # ownership of a locked file and editing a scheduled task need it. Refusing to run at all
    # would make the common case harder for the sake of the rare one.
    Warn "NOT elevated -- file-ownership and scheduled-task repairs will be skipped. Re-run from an elevated PowerShell if a step reports Access denied."
}

# ---------------------------------------------------------------- 1. MT5 terminal
Step "MT5 terminal"
# FIND THE TERMINAL, DO NOT ASSUME IT. This step used to be gated entirely on `Test-Path
# $Terminal`, so a stale default path FAILED the step and skipped the Python probe -- reporting a
# broken terminal on a box whose bridge was working perfectly. That is the same absence-as-verdict
# this script exists to stamp out, and it cost a round trip on 2026-09-06.
#
# The RUNNING PROCESS is the authority: whatever exe is serving MT5 right now is by definition the
# right one, whatever any constant says. Only if nothing is running do we fall back to searching
# the usual install roots, and only then to the passed-in default.
$running = Get-Process terminal64 -ErrorAction SilentlyContinue
$found = $null
if ($running) {
    $found = ($running | Select-Object -First 1 -ExpandProperty Path -ErrorAction SilentlyContinue)
    if ($found) { Info "terminal already running from $found" }
}
if (-not $found) {
    $candidates = @($Terminal) + @(
        "$env:ProgramFiles\*MetaTrader 5*\terminal64.exe",
        "${env:ProgramFiles(x86)}\*MetaTrader 5*\terminal64.exe",
        "$env:ProgramFiles\*MetaTrader*\terminal64.exe",
        "$env:APPDATA\MetaQuotes\Terminal\*\terminal64.exe"
    )
    foreach ($c in $candidates) {
        $hit = Get-Item -Path $c -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($hit) { $found = $hit.FullName; break }
    }
    if ($found -and $found -ne $Terminal) { Warn "terminal64.exe is at $found, not the default $Terminal -- pass -Terminal to silence this" }
}
if (-not $found) {
    Warn "terminal64.exe not located on disk (searched Program Files and %APPDATA%\MetaQuotes) -- probing the Python bridge anyway, which is the test that actually matters"
} else {
    $Terminal = $found
    if (-not $running -and -not $WhatIf) {
        Info "starting the terminal"
        Start-Process $Terminal | Out-Null
        Start-Sleep -Seconds 20
    }
}
# THE ONLY TEST THAT MEANS ANYTHING is whether the Python bridge can attach, so it runs
# UNCONDITIONALLY now -- a terminal that answers Python is a working terminal whether or not this
# script managed to locate its exe. A running process is also not the same as a reachable one:
# -10003 "Process create failed" comes back when the exe EXISTS but a Session 0 scheduled task
# cannot create a GUI process, and the path in that message sends everyone to check a path that
# was already correct.
$probe = & python -c "import MetaTrader5 as m; print('OK' if m.initialize() else 'ERR '+str(m.last_error()))" 2>&1
if ("$probe" -match "OK") { Ok "terminal reachable from Python" }
else {
    Fail "MT5 will not initialize: $probe"
    Info "If the exe exists this is a SESSION problem, not a path one: terminal64.exe is a GUI process and a scheduled task with LogonType Password/S4U runs in Session 0, where Windows refuses to create one. Fix: schtasks /Change /TN MT5-TerminalBoot /RU Administrator /IT (elevated), or leave the terminal running so initialize() attaches."
}
# Survive reboots without needing the scheduler at all. Needs a real target, so it is skipped
# rather than pointed at a path that was never found.
$lnk = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup\mt5boot.lnk"
if ($found -and -not (Test-Path $lnk) -and -not $WhatIf) {
    try {
        $s = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk)
        $s.TargetPath = $Terminal; $s.Save()
        Ok "Startup shortcut created (terminal now survives reboot)"
    } catch { Warn "could not create Startup shortcut: $($_.Exception.Message)" }
}

# ---------------------------------------------------------------- 2. conflict markers
Step "Merge-conflict markers in tracked files"
$marked = Get-ChildItem -Recurse -Include *.py,*.json,*.yaml,*.yml -ErrorAction SilentlyContinue |
          Select-String -Pattern '^<<<<<<< |^>>>>>>> ' -List -ErrorAction SilentlyContinue |
          Select-Object -ExpandProperty Path
if (-not $marked) { Ok "none" }
elseif ($WhatIf) { Warn "$($marked.Count) file(s) carry conflict markers (WhatIf: not repaired)" }
else {
    Info "$($marked.Count) file(s) carry markers -- restoring each from the remote"
    git fetch origin $Branch 2>&1 | Out-Null
    New-Item -ItemType Directory -Force $BackupDir | Out-Null
    foreach ($p in $marked) {
        $rel = ((Resolve-Path -Relative $p) -replace '^\.\\','') -replace '\\','/'
        # BACKED UP BEFORE OVERWRITING, always. A corrupted file may still hold the only copy of
        # something local, and "it had conflict markers" is not a reason to destroy it unseen.
        Copy-Item $p (Join-Path $BackupDir (Split-Path $rel -Leaf)) -Force -ErrorAction SilentlyContinue
        git checkout FETCH_HEAD -- $rel 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) { Ok "restored $rel" }
        else { Fail "NOT IN REMOTE: $rel -- resolve by hand (backup in $BackupDir)" }
    }
}

# ---------------------------------------------------------------- 3. git, unstuck
Step "Git"
git config core.editor true 2>&1 | Out-Null      # never open an editor; a blocked merge is worse
git config pull.rebase false 2>&1 | Out-Null     # merge, so the box's own commits are preserved

if (Test-Path ".git/MERGE_HEAD") {
    if ($WhatIf) { Warn "an unfinished merge is in progress (WhatIf: not concluded)" }
    else {
        $unmerged = git diff --name-only --diff-filter=U
        if ($unmerged) {
            # CODE CONFLICTS ARE THE OPERATOR'S CALL. Auto-resolving a gateway or a gauntlet would
            # silently choose which version trades money. Data files are different: the box
            # authors them, so its own copy is the right one.
            $code = $unmerged | Where-Object { $_ -match '\.(py|ps1|yaml|yml)$' }
            $data = $unmerged | Where-Object { $_ -notmatch '\.(py|ps1|yaml|yml)$' }
            foreach ($f in $data) { git checkout --ours -- $f 2>&1 | Out-Null; git add -- $f 2>&1 | Out-Null }
            if ($data) { Ok "$($data.Count) data conflict(s) resolved in the box's favour (it authors them)" }
            if ($code) {
                if ($ResolveCode -eq "none") {
                    Fail "$($code.Count) CODE file(s) conflict and will not be auto-resolved: $($code -join ', ')"
                    Info "Re-run with -ResolveCode theirs (take the repo's) or -ResolveCode ours (keep the box's)"
                    Info "Either way both sides are backed up first. Or resolve by hand: git add <file>; git commit --no-edit"
                }
                else {
                    # BACK BOTH SIDES UP BEFORE CHOOSING. The conflicted working file still holds
                    # the merge markers, so it carries BOTH versions in one artifact -- copying it
                    # verbatim preserves everything either side had, and it is a plain file the
                    # operator can read without knowing git.
                    $stamp  = Get-Date -Format "yyyyMMdd-HHmmss"
                    $vault  = Join-Path $BackupDir "merge-$stamp"
                    foreach ($f in $code) {
                        $dest = Join-Path $vault $f
                        New-Item -ItemType Directory -Force -Path (Split-Path $dest) 2>&1 | Out-Null
                        Copy-Item -LiteralPath $f -Destination $dest -Force -ErrorAction SilentlyContinue
                    }
                    $side = if ($ResolveCode -eq "theirs") { "--theirs" } else { "--ours" }
                    foreach ($f in $code) {
                        git checkout $side -- $f 2>&1 | Out-Null
                        git add -- $f 2>&1 | Out-Null
                    }
                    $whose = if ($ResolveCode -eq "theirs") { "the repository's" } else { "the box's" }
                    Ok "$($code.Count) code conflict(s) resolved to $whose version"
                    Warn "code conflicts were resolved to $whose version -- BOTH sides are in $vault; check it before deleting: $($code -join ', ')"
                }
            }
        }
        if (-not (git diff --name-only --diff-filter=U)) {
            git commit --no-edit 2>&1 | Out-Null
            Ok "merge concluded"
        }
        else {
            # A MERGE LEFT IN PROGRESS STOPS THE BOX FROM REPORTING AT ALL. Every later git call
            # dies on `fatal: Exiting because of an unresolved conflict`, so the runtime state is
            # never committed and never pushed -- which is exactly how the dashboard came to read
            # "box SILENT for 260.8h" while the desk itself was running fine and recording ticks
            # every hour. The publication path must not be hostage to an unfinished merge.
            #
            # Aborting DECIDES NOTHING: it restores the pre-merge tree, so the box keeps running
            # precisely the code it was already running and the merge is still there to be done
            # deliberately later. Declining a merge and resolving one are different acts.
            Warn "merge could not be concluded -- aborting it so the box can still publish its state"
            git merge --abort 2>&1 | Out-Null
            if (Test-Path ".git/MERGE_HEAD") { Fail "git merge --abort did not clear the merge -- run: git status" }
            else { Ok "merge declined and the tree restored; redo it when the code conflict is settled" }
        }
    }
}

if (-not $WhatIf) {
    # The box's runtime state is committed BEFORE pulling so a pull can never be blocked by it,
    # and so nothing the box produced is lost to a checkout.
    git add -A -- desks/mt5/data desks/mt5/reports 2>&1 | Out-Null
    git diff --cached --quiet
    if ($LASTEXITCODE -ne 0) { git commit -m "box runtime state before sync" 2>&1 | Out-Null; Ok "local state committed" }

    $pull = git pull origin $Branch 2>&1
    if ($LASTEXITCODE -eq 0) { Ok "pulled $Branch" }
    else {
        Fail "pull failed"
        ($pull | Select-Object -Last 12) | ForEach-Object { Info $_ }
    }
}

# ------------------------------------------- 3c. THE PUBLISHER THAT FEEDS THE PUBLIC DASHBOARD
Step "Shadow sync to git (this is what feeds the dashboard)"
# NOTHING ELSE PUBLISHES THIS BOX'S STATE. `sync_shadow_to_git.ps1` commits the allowlisted state
# summaries -- account_state, the three shadow lane states, sleeves, shadow_health -- to the
# shared branch every 15 minutes as scheduled task MT5-ShadowSync. It REPLACED the old scp path
# when Hetzner was decommissioned on 2026-08-23; the VPS's `pull_desk_state.sh` still scp's from
# an ssh alias named for a machine that no longer exists, and has failed every two minutes since.
#
# So this task is the whole delivery chain, and when it stops the dashboard starves in a way that
# looks like a research failure rather than a delivery one. MEASURED 2026-09-06: shadow_health.json
# last written 2026-08-26 14:45, gateway_state.json 08-17, regime_state.json 08-20, and the page
# read "box has not reported for 266.4h" while the desk itself was running fine, recording ticks
# every hour and completing its daily cycle. Eleven days of green research, invisible.
$sync = Join-Path $Root "desks\mt5\scripts\sync_shadow_to_git.ps1"
if (-not (Test-Path $sync)) {
    Fail "sync_shadow_to_git.ps1 is absent -- nothing publishes this box's state, so the dashboard can only ever read SILENT"
} else {
    $task = Get-ScheduledTask -TaskName "MT5-ShadowSync" -ErrorAction SilentlyContinue
    if (-not $task) {
        Fail "scheduled task MT5-ShadowSync does not exist -- this box has no 15-minute publisher"
        Info "register it (elevated): powershell -ExecutionPolicy Bypass -File desks\mt5\scripts\Install-QuantWindows.ps1"
    }
    else {
        $ti = Get-ScheduledTaskInfo -TaskName "MT5-ShadowSync" -ErrorAction SilentlyContinue
        Info ("MT5-ShadowSync state={0} lastRun={1} lastResult={2}" -f $task.State, $ti.LastRunTime, $ti.LastTaskResult)
        if ($task.State -eq "Disabled") {
            if ($WhatIf) { Warn "MT5-ShadowSync is DISABLED (WhatIf: not enabled)" }
            else {
                Enable-ScheduledTask -TaskName "MT5-ShadowSync" -ErrorAction SilentlyContinue | Out-Null
                if ((Get-ScheduledTask -TaskName "MT5-ShadowSync").State -eq "Disabled") { Fail "MT5-ShadowSync is disabled and could not be enabled -- needs an elevated run" }
                else { Ok "MT5-ShadowSync re-enabled" }
            }
        }
        # A TASK THAT EXISTS AND IS ENABLED CAN STILL HAVE STOPPED. It repeats every 15 minutes,
        # so a last run older than an hour is a dead publisher wearing a healthy task's clothes --
        # exactly the shape that hid this for eleven days.
        if ($ti -and $ti.LastRunTime -and $ti.LastRunTime -lt (Get-Date).AddHours(-1)) {
            $stale = [int]((Get-Date) - $ti.LastRunTime).TotalHours
            Fail "MT5-ShadowSync last ran ${stale}h ago on a 15-MINUTE schedule -- the publisher is dead, which is why the dashboard reads SILENT"
        }
        if ($ti -and $ti.LastTaskResult -ne 0 -and $null -ne $ti.LastTaskResult) {
            Warn "MT5-ShadowSync last exit code was $($ti.LastTaskResult) -- see desks\mt5\logs\sync_shadow_to_git.log"
        }
    }
    # RUN IT ONCE NOW, whatever the scheduler says. The point of this script is that the dashboard
    # is current when it finishes, not fifteen minutes later -- and a manual run is also the
    # fastest way to see the real error if the scheduled one has been failing silently.
    if (-not $WhatIf) {
        Info "publishing state now"
        $out = & powershell -NoProfile -ExecutionPolicy Bypass -File $sync 2>&1
        if ($LASTEXITCODE -eq 0) { Ok "state published to git -- the dashboard picks it up on the VPS's next pull" }
        else {
            Fail "sync_shadow_to_git.ps1 exited $LASTEXITCODE -- the box's state did NOT reach the dashboard"
            ($out | Select-Object -Last 10) | ForEach-Object { Info $_ }
        }
    }
}

# ---------------------------------------------------------------- 4. bars + cost model
Step "Bars and universe registry"
if ($SkipBars) { Info "skipped (-SkipBars)" }
elseif ($WhatIf) { Info "would run download_remaining.py --timeframes H1" }
else {
    $dl = Join-Path $Root "desks\mt5\scripts\download_remaining.py"
    if (-not (Test-Path $dl)) { Fail "download_remaining.py absent -- the pull did not land" }
    else {
        # H1 FIRST, THEN EVERY OTHER CHART. H1 is what unblocks the gauntlet's undeclared cells,
        # so it runs alone first and the registry is usable within a minute even if the rest is
        # interrupted. But H1 ALONE was leaving the docket half-idle: measured 2026-09-06, 10,961
        # of 23,627 cells were held as "no bars" purely because their timeframe had never been
        # downloaded -- cells with a real hypothesis and a tradable symbol, unable to be judged
        # because nobody had fetched an M15 chart. A cell held for want of a download is not
        # evidence about the cell.
        & python $dl --timeframes H1
        if ($LASTEXITCODE -eq 0) { Ok "H1 bars and universe.json refreshed" }
        else { Fail "bar download exited $LASTEXITCODE" }

        $rest = @($BarTimeframes | Where-Object { $_ -ne "H1" })
        if ($rest.Count -gt 0) {
            # ONE COMMA-JOINED VALUE: `--timeframes` is a single string that the downloader splits
            # itself (its default is ",".join(TIMEFRAMES)). Passing the charts as separate words
            # would hand argparse one timeframe and six stray positionals.
            $spec = $rest -join ","
            Info "fetching the remaining charts: $spec -- this is the slow leg"
            & python $dl --timeframes $spec
            if ($LASTEXITCODE -eq 0) { Ok "$($rest.Count) further timeframe(s) refreshed -- no cell is now held for want of a chart this broker offers" }
            else { Fail "secondary bar download exited $LASTEXITCODE -- H1 landed, the other charts did not" }
        }
    }
}

# ---------------------------------------------------------------- 5. the desk's own cycle
Step "Hourly cycle"
if ($WhatIf) { Info "would run research/hourly_cycle.py" }
else {
    $hc = Join-Path $Root "desks\mt5\research\hourly_cycle.py"
    if (-not (Test-Path $hc)) { Fail "hourly_cycle.py absent" }
    else {
        Push-Location (Join-Path $Root "desks\mt5")
        & python "research\hourly_cycle.py"
        if ($LASTEXITCODE -eq 0) { Ok "cycle completed" } else { Warn "cycle exited $LASTEXITCODE (some legs may have failed; see its own log)" }
        Pop-Location
    }
}

# ---------------------------------------------------------------- 6. publish state
Step "Push state to the VPS"
if ($WhatIf) { Info "would commit and push desks/mt5/{data,reports}" }
else {
    git add -A -- desks/mt5/data desks/mt5/reports 2>&1 | Out-Null
    git diff --cached --quiet
    if ($LASTEXITCODE -eq 0) { Warn "nothing new to publish -- the cycle wrote no state, so the dashboard will stay SILENT" }
    else {
        git commit -m "box state sync" 2>&1 | Out-Null
        $push = git push origin $Branch 2>&1
        if ($LASTEXITCODE -eq 0) { Ok "state pushed to $Branch" }
        else {
            Fail "push failed"
            ($push | Select-Object -Last 8) | ForEach-Object { Info $_ }
            # NAME THE ONE CAUSE THE OPERATOR CANNOT SEE FROM THE ERROR. A declined merge leaves
            # the box BEHIND origin, and git then refuses the push as non-fast-forward -- which
            # reads like a broken remote rather than the consequence of the step above. Say how
            # far behind, because "behind by 14" and "behind by 0" are different problems.
            git fetch origin $Branch 2>&1 | Out-Null
            $behind = (git rev-list --count "HEAD..FETCH_HEAD" 2>$null)
            if ($behind -and [int]$behind -gt 0) {
                Info "this branch is $behind commit(s) behind origin, so the push cannot fast-forward"
                Info "that is the declined merge above: re-run with -ResolveCode theirs (or ours) to conclude it, then the push succeeds"
            }
        }
    }
}

# ---------------------------------------------------------------- 7. verdict
Step "Summary"
$gates = Join-Path $Root "desks\mt5\reports\universal_gates_external.json"
if (Test-Path $gates) {
    $g = Get-Content $gates -Raw | ConvertFrom-Json
    Info ("gauntlet: judged {0}, unmeasured {1}, passed all ten {2}" -f $g.n_judged, $g.n_unmeasured, $g.survivors_passing_all)
}
if ($script:Failures.Count -eq 0) {
    Write-Host ""
    Write-Host "BOX REPAIRED -- no step failed." -ForegroundColor Green
    if ($script:Notes) { $script:Notes | ForEach-Object { Write-Host "  note: $_" -ForegroundColor Yellow } }
    exit 0
}
Write-Host ""
Write-Host "BOX NOT FULLY REPAIRED -- $($script:Failures.Count) step(s) failed:" -ForegroundColor Red
$script:Failures | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
Write-Host "Nothing above this line should be read as working." -ForegroundColor Red
exit 1
