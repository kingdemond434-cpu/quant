<#
.SYNOPSIS
    Register the MT5 desk's scheduled work on THIS Windows box, deriving every
    path instead of carrying another machine's.

.DESCRIPTION
    WHY THE EXISTING SCRIPTS COULD NOT BE COPIED ACROSS

    MT5Hourly.cmd and MT5Sync.cmd hardcode `C:\Users\dell\mt5-research` and a
    specific Python 3.12 install path. On any other box every one of those is
    wrong, and the failure is quiet in the worst way: `cd /d` to a missing
    directory does NOT stop a .cmd file, so the loop runs `research\hourly_cycle.py`
    from whatever directory it happened to start in, fails, and keeps looping
    forever at one attempt per hour with nothing reporting it.

    This derives the checkout from its own location and finds the interpreter,
    so there is nothing to edit when the box changes.

    WHY TASK SCHEDULER AND NOT THE .cmd LOOPS

    The old pattern is `:loop / run / timeout 3540 / goto loop` started from the
    Startup folder. It has three holes this closes:

      - Nothing restarts it. If the cmd window is closed, the process is killed,
        or the box reboots without a logon, the loop is simply gone. Task
        Scheduler restarts a failed task and runs AtStartup, not just at logon.
      - `timeout` is not a schedule. A run that takes 20 minutes makes the next
        one 80 minutes late, and the drift accumulates silently.
      - No record. A .cmd loop that has been dead for a week looks identical to
        one that is running and finding nothing to do.

    WHAT IT DOES NOT DO

    It does not start MT5, and it does not arm trading. The gateway task moves
    orders only when the gateway itself decides to; registering a schedule is
    not the same act as arming a book, and this script deliberately cannot do
    the second one.

.PARAMETER DeskRoot
    The desks/mt5 checkout. Defaults to this script's parent, correct by
    construction.

.PARAMETER Python
    Interpreter to run the desk with. Defaults to the repo venv if present,
    then `py -3`. NEVER `python3` -- that name is Linux-only and does not exist
    on Windows, which is the single most common failure when following a
    runbook written on Linux.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\Install-QuantWindows.ps1
#>
[CmdletBinding()]
param(
    [string] $DeskRoot,
    [string] $Python,
    [string] $AurumRoot,
    [switch] $WhatIfOnly
)

$ErrorActionPreference = "Stop"

if ($PSVersionTable.PSVersion.Major -lt 3) {
    Write-Host "FATAL: PowerShell $($PSVersionTable.PSVersion); need 3.0+."
    exit 1
}

# $PSScriptRoot is unreliable inside a param() default on 5.1 -- resolved here.
if (-not $DeskRoot) {
    $d = $PSScriptRoot
    if (-not $d) { $d = Split-Path -Parent $MyInvocation.MyCommand.Path }
    if (-not $d) { throw "cannot locate this script; pass -DeskRoot explicitly" }
    $DeskRoot = Split-Path -Parent $d
}
$DeskRoot = (Resolve-Path $DeskRoot).Path

if (-not (Test-Path (Join-Path $DeskRoot "research\hourly_cycle.py"))) {
    Write-Host "FATAL: no research\hourly_cycle.py under $DeskRoot."
    Write-Host "       That is not the desks/mt5 checkout. Pass -DeskRoot."
    exit 1
}

if (-not $Python) {
    $venv = Join-Path $DeskRoot "..\..\.venv\Scripts\python.exe"
    if (Test-Path $venv) { $Python = (Resolve-Path $venv).Path }
    elseif (Get-Command py -ErrorAction SilentlyContinue) { $Python = "py" }
    elseif (Get-Command python -ErrorAction SilentlyContinue) { $Python = "python" }
    else {
        Write-Host "FATAL: no interpreter. Install Python 3.12+, or create the"
        Write-Host "       repo venv:  py -3 -m venv .venv"
        Write-Host "       NOTE: 'python3' is a Linux name and never exists here."
        exit 1
    }
}
$pyArgs = if ($Python -eq "py") { "-3 " } else { "" }

Write-Host ""
Write-Host ("=" * 74)
Write-Host "QUANT MT5 DESK -- Windows scheduled work"
Write-Host ("=" * 74)
Write-Host "  checkout    $DeskRoot"
Write-Host "  interpreter $Python"

# Logs must exist before a task writes to them; a task that fails on a missing
# directory reports "last result 0x1" and nothing about the reason.
$logDir = Join-Path $DeskRoot "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

#: REPETITION DURATION IS 10 YEARS, NOT [TimeSpan]::MaxValue. MaxValue
#: serialises to the ISO-8601 duration P99999999DT23H59M59S, which the Task
#: Scheduler service rejects outright:
#:
#:   Register-ScheduledTask : The task XML contains a value which is
#:   incorrectly formatted or out of range. (8,42):Duration:P99999999DT23H59M59S
#:
#: It fails at REGISTRATION, so the task simply does not exist afterwards --
#: and a script that reports the other tasks fine leaves an operator believing
#: the schedule is installed. 3650 days is indefinite for any practical purpose
#: and serialises to a duration the service accepts.
#:
#: name -> (script, schedule-builder, description)
#: The gateway runs EVERY MINUTE and holds its own file lock, so overlapping
#: passes cannot double-bracket. The hourly cycle self-guards on a UTC date
#: stamp, so running it hourly gives exactly one daily-cycle run per day and
#: catches up whenever the box is awake instead of missing a fixed minute.
$tasks = @(
    @{ Name = "MT5-Gateway"
       Script = "research\run_gateway_loop.py"
       Trigger = { New-ScheduledTaskTrigger -Once -At (Get-Date).Date `
                     -RepetitionInterval (New-TimeSpan -Minutes 1) `
                     -RepetitionDuration (New-TimeSpan -Days 3650) }
       Desc = "One gateway pass per minute; file-locked against overlap." },
    @{ Name = "MT5-Hourly"
       Script = "research\hourly_cycle.py"
       Trigger = { New-ScheduledTaskTrigger -Once -At (Get-Date).Date `
                     -RepetitionInterval (New-TimeSpan -Hours 1) `
                     -RepetitionDuration (New-TimeSpan -Days 3650) }
       Desc = "Health, mining, and the daily chain: shadow -> promoter -> markout -> export." },
    @{ Name = "MT5-Shadow"
       Script = "research\shadow_cycle.py"
       Trigger = { New-ScheduledTaskTrigger -Once -At (Get-Date).Date `
                     -RepetitionInterval (New-TimeSpan -Minutes 15) `
                     -RepetitionDuration (New-TimeSpan -Days 3650) }
       Desc = "Refresh broker bars and replay every configured zero-capital sleeve every 15m." }
)

foreach ($t in $tasks) {
    $script = Join-Path $DeskRoot $t.Script
    if (-not (Test-Path $script)) {
        Write-Host ("  [SKIP] {0,-14} {1} not found" -f $t.Name, $t.Script)
        continue
    }
    $log = Join-Path $logDir ("{0}.log" -f $t.Name)
    # cmd /c wraps the redirect: Task Scheduler has no shell, so `>>` in the
    # arguments field is passed to python as a literal argument otherwise.
    # cmd.exe needs an OUTER quote pair when the executable itself is quoted. Without it,
    # Task Scheduler returns 1 before Python starts and no log is created.
    $cmd = "/d /s /c `"`"$Python`" $pyArgs`"$script`" >> `"$log`" 2>&1`""

    if ($WhatIfOnly) {
        Write-Host ("  [DRY ] {0,-14} cmd {1}" -f $t.Name, $cmd)
        continue
    }

    $action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument $cmd `
                                      -WorkingDirectory $DeskRoot
    # RestartCount/RestartInterval are what replace systemd's Restart=always.
    # StartWhenAvailable catches up a run missed while the box was off, which is
    # the whole point on a machine that is not guaranteed up.
    $settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -StartWhenAvailable -RestartCount 3 `
        -RestartInterval (New-TimeSpan -Minutes 1) `
        -ExecutionTimeLimit (New-TimeSpan -Hours 4)

    try {
        Unregister-ScheduledTask -TaskName $t.Name -Confirm:$false -ErrorAction SilentlyContinue
        $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME `
            -LogonType Interactive -RunLevel Limited
        Register-ScheduledTask -TaskName $t.Name -Action $action `
            -Trigger (& $t.Trigger) -Settings $settings `
            -Description $t.Desc -Principal $principal | Out-Null
        Write-Host ("  [OK  ] {0,-14} registered -> {1}" -f $t.Name, $log)
    } catch {
        Write-Host ("  [FAIL] {0,-14} {1}" -f $t.Name, $_.Exception.Message)
    }
}

# The research supervisor is a persistent queue/experiment worker, not a one-shot task. A short
# recurring trigger supplies crash recovery; IgnoreNew keeps exactly one live owner.
$supervisor = Join-Path $DeskRoot "research\research_supervisor.py"
if (Test-Path $supervisor) {
    if ($WhatIfOnly) {
        Write-Host "  [DRY ] MT5-ResearchSupervisor persistent canonical worker"
    } else {
        try {
            # Use base pythonw directly: no console and no short-lived venv launcher parent for
            # Task Scheduler to mistake for the persistent worker.
            $basePython = (& $Python -c "import sys; print(sys._base_executable)").Trim()
            $supervisorPython = Join-Path (Split-Path $basePython) "pythonw.exe"
            if (-not (Test-Path $supervisorPython)) { $supervisorPython = $basePython }
            $supAction = New-ScheduledTaskAction -Execute $supervisorPython `
                -Argument ("`"{0}`"" -f $supervisor) -WorkingDirectory $DeskRoot
            $supTrigger = New-ScheduledTaskTrigger -Once -At (Get-Date).Date `
                -RepetitionInterval (New-TimeSpan -Minutes 5) `
                -RepetitionDuration (New-TimeSpan -Days 3650)
            $supSettings = New-ScheduledTaskSettingsSet `
                -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
                -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) `
                -ExecutionTimeLimit (New-TimeSpan -Hours 72) -MultipleInstances IgnoreNew
            $supPrincipal = New-ScheduledTaskPrincipal -UserId $env:USERNAME `
                -LogonType Interactive -RunLevel Limited
            Unregister-ScheduledTask -TaskName "MT5-ResearchSupervisor" `
                -Confirm:$false -ErrorAction SilentlyContinue
            Register-ScheduledTask -TaskName "MT5-ResearchSupervisor" -Action $supAction `
                -Trigger $supTrigger -Settings $supSettings -Principal $supPrincipal `
                -Description "Persistent canonical MT5 hypothesis/research worker." | Out-Null
            Write-Host "  [OK  ] MT5-ResearchSupervisor registered"
        } catch {
            Write-Host ("  [FAIL] MT5-ResearchSupervisor {0}" -f $_.Exception.Message)
        }
    }
}

$shadowSync = Join-Path $DeskRoot "scripts\sync_shadow_to_vps.ps1"
if ((Test-Path $shadowSync) -and -not $WhatIfOnly) {
    try {
        $syncAction = New-ScheduledTaskAction -Execute "powershell.exe" -Argument `
            ("-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"{0}`"" -f $shadowSync)
        # Five minutes after the 00/15/30/45 replay slots: never race a ledger write.
        $syncTrigger = New-ScheduledTaskTrigger -Once -At ((Get-Date).Date.AddMinutes(5)) `
            -RepetitionInterval (New-TimeSpan -Minutes 15) `
            -RepetitionDuration (New-TimeSpan -Days 3650)
        $syncSettings = New-ScheduledTaskSettingsSet `
            -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
            -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) `
            -ExecutionTimeLimit (New-TimeSpan -Minutes 10) -MultipleInstances IgnoreNew
        $syncPrincipal = New-ScheduledTaskPrincipal -UserId $env:USERNAME `
            -LogonType Interactive -RunLevel Limited
        Unregister-ScheduledTask -TaskName "MT5-ShadowSync" `
            -Confirm:$false -ErrorAction SilentlyContinue
        Register-ScheduledTask -TaskName "MT5-ShadowSync" -Action $syncAction `
            -Trigger $syncTrigger -Settings $syncSettings -Principal $syncPrincipal `
            -Description "Publish complete MT5 shadow evidence to the shared VPS." | Out-Null
        Write-Host "  [OK  ] MT5-ShadowSync registered"
    } catch {
        Write-Host ("  [FAIL] MT5-ShadowSync {0}" -f $_.Exception.Message)
    }
} elseif ($WhatIfOnly) {
    Write-Host "  [DRY ] MT5-ShadowSync 15-minute artifact publisher"
}

# ---- THE LINK THAT WAS NOT AUTOMATIC ---------------------------------------
# quant EXPORTS findings daily (daily_cycle step 4) and Aurum READS them daily
# (aurum_cycle step_absorb). Both ends ran on a schedule; NOTHING CARRIED THE
# FILE BETWEEN THEM. A pipe whose middle section is a human remembering to run a
# script is a pipe that stops the first busy week, and it stops SILENTLY --
# Aurum keeps reporting "0 new findings", which reads exactly like the quant
# desk having learned nothing.
#
# Runs at 22:15 UTC, after the 21:45 daily cycle has written the export. The
# script is idempotent on (statement, measured_on), so an early or repeated run
# appends nothing rather than duplicating.
if ($AurumRoot) {
    $syncScript = Join-Path $AurumRoot "deploy\windows\Sync-QuantFindings.ps1"
    if (-not (Test-Path $syncScript)) {
        Write-Host ("  [SKIP] {0,-14} not found at {1}" -f "Aurum-Sync", $syncScript)
    } elseif ($WhatIfOnly) {
        Write-Host ("  [DRY ] {0,-14} {1}" -f "Aurum-Sync", $syncScript)
    } else {
        $quantRoot = Split-Path -Parent (Split-Path -Parent $DeskRoot)
        $sa = New-ScheduledTaskAction -Execute "powershell.exe" `
            -Argument ("-NoProfile -ExecutionPolicy Bypass -File `"$syncScript`" " +
                       "-QuantRoot `"$quantRoot`" -AurumRoot `"$AurumRoot`"") `
            -WorkingDirectory $AurumRoot
        $stg = New-ScheduledTaskSettingsSet -StartWhenAvailable -RestartCount 3 `
            -RestartInterval (New-TimeSpan -Minutes 5) `
            -ExecutionTimeLimit (New-TimeSpan -Minutes 10)
        try {
            Unregister-ScheduledTask -TaskName "Aurum-Sync" -Confirm:$false -ErrorAction SilentlyContinue
            Register-ScheduledTask -TaskName "Aurum-Sync" -Action $sa `
                -Trigger (New-ScheduledTaskTrigger -Daily -At "22:15") -Settings $stg `
                -Description "Carry quant's exported findings into Aurum's absorption inbox." `
                -User "SYSTEM" -RunLevel Highest | Out-Null
            Write-Host ("  [OK  ] {0,-14} daily 22:15 -> {1}" -f "Aurum-Sync", $AurumRoot)
        } catch {
            Write-Host ("  [FAIL] {0,-14} {1}" -f "Aurum-Sync", $_.Exception.Message)
        }
    }
} else {
    Write-Host ""
    Write-Host "  NOTE: -AurumRoot not given, so the findings transport is NOT scheduled."
    Write-Host "        quant will export daily and Aurum will read daily, but nothing"
    Write-Host "        moves the file between them. Re-run with -AurumRoot C:\Aurum."
}

Write-Host ""
Write-Host "VERIFY -- these are the only checks that mean anything:"
Write-Host "  Get-ScheduledTask MT5-Gateway,MT5-Hourly | Select TaskName,State"
Write-Host "  Start-ScheduledTask -TaskName MT5-Hourly     # force one run now"
Write-Host "  Get-Content logs\MT5-Hourly.log -Tail 40"
Write-Host "  Get-Content reports\shadow\shadow_state.json | Select-Object -First 30"
Write-Host ""
Write-Host "SHADOW IS THE THING TO WATCH. Every sleeve sits at n=0 until bars"
Write-Host "reach it. If they stay at 0 after a run, logs\shadow.log names the"
Write-Host "reason per symbol -- it is a data question, never a silent one."
Write-Host ""
Write-Host "All recurring tasks use the interpreter and checkout printed above;"
Write-Host "no research target carries a second machine-specific Python path."
