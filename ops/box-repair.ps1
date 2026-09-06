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
  .\ops\box-repair.ps1 -SkipBars      # skip the slow bar download
  .\ops\box-repair.ps1 -WhatIf        # report only, change nothing
#>
[CmdletBinding()]
param(
    [string]$Root      = "C:\opt\quant",
    [string]$Branch    = "claude/llm-auto-upgrade-verify-gcjac3",
    [string]$Terminal  = "C:\Program Files\Fusion Markets MetaTrader 5\terminal64.exe",
    [string]$BackupDir = "C:\opt\quant-backup",
    [switch]$SkipBars,
    [switch]$WhatIf
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
if (-not (Test-Path $Terminal)) {
    Fail "terminal64.exe not found at $Terminal -- set -Terminal to its real path"
} else {
    $running = Get-Process terminal64 -ErrorAction SilentlyContinue
    if (-not $running -and -not $WhatIf) {
        Info "starting the terminal"
        Start-Process $Terminal | Out-Null
        Start-Sleep -Seconds 20
    }
    # THE ONLY TEST THAT MEANS ANYTHING is whether the Python bridge can attach. A running
    # process is not the same as a reachable terminal: -10003 "Process create failed" is returned
    # when the exe EXISTS but a Session 0 scheduled task cannot create a GUI process, and the
    # path in that message sends everyone to check a path that is already correct.
    $probe = & python -c "import MetaTrader5 as m; print('OK' if m.initialize() else 'ERR '+str(m.last_error()))" 2>&1
    if ("$probe" -match "OK") { Ok "terminal reachable from Python" }
    else {
        Fail "MT5 will not initialize: $probe"
        Info "If the exe exists this is a SESSION problem, not a path one: terminal64.exe is a GUI process and a scheduled task with LogonType Password/S4U runs in Session 0, where Windows refuses to create one. Fix: schtasks /Change /TN MT5-TerminalBoot /RU Administrator /IT (elevated), or leave the terminal running so initialize() attaches."
    }
    # Survive reboots without needing the scheduler at all.
    $lnk = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup\mt5boot.lnk"
    if (-not (Test-Path $lnk) -and -not $WhatIf) {
        try {
            $s = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk)
            $s.TargetPath = $Terminal; $s.Save()
            Ok "Startup shortcut created (terminal now survives reboot)"
        } catch { Warn "could not create Startup shortcut: $($_.Exception.Message)" }
    }
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
                Fail "$($code.Count) CODE file(s) conflict and will not be auto-resolved: $($code -join ', ')"
                Info "Choose deliberately, then: git add <file>; git commit --no-edit"
            }
        }
        if (-not (git diff --name-only --diff-filter=U)) {
            git commit --no-edit 2>&1 | Out-Null
            Ok "merge concluded"
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

# ---------------------------------------------------------------- 4. bars + cost model
Step "Bars and universe registry"
if ($SkipBars) { Info "skipped (-SkipBars)" }
elseif ($WhatIf) { Info "would run download_remaining.py --timeframes H1" }
else {
    $dl = Join-Path $Root "desks\mt5\scripts\download_remaining.py"
    if (-not (Test-Path $dl)) { Fail "download_remaining.py absent -- the pull did not land" }
    else {
        # H1 FIRST AND ALONE BY DEFAULT. Every docket row is H1-undeclared, so H1 is what unblocks
        # the gauntlet; the other six charts are worth having and are not worth blocking on.
        & python $dl --timeframes H1
        if ($LASTEXITCODE -eq 0) { Ok "H1 bars and universe.json refreshed" }
        else { Fail "bar download exited $LASTEXITCODE" }
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
        else { Fail "push failed"; ($push | Select-Object -Last 8) | ForEach-Object { Info $_ } }
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
