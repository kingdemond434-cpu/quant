# REGISTER Quant-BoxSelfHeal -- THE CLOSED SELF-HEAL TABLE, EVERY FIVE MINUTES, AS SYSTEM (2026-10-29).
#
# THE PASTE IT RETIRES. zuck had to open an admin PowerShell and, by hand: stop a wedged
# merge_hypotheses that held data\.job_locks\merge_hypotheses.json, stop a pf_allocator heavy pass
# that held the allocator lock past its budget, stop the gate's gh "pulls" child and python,
# `schtasks /end` a hung MT5-IndependenceIntake, `schtasks /end` + `/run` a Quant-WorkflowGate that
# had been dead since a crash, and add the gate repo to git's safe.directory. ops\box_self_heal.py
# is the SYSTEM-only lines of that paste (end the hung task, end a wedged gate tree, restart a dead
# gate) as a fixed, reviewed rule table with the evidence each one needs before it fires (past
# budget AND dead owner or no CPU progress across two passes); this registers its clock. The two
# job-lock lines are job_lock's own wedged-owner stop (#526, scripts/check_job_locks.py), not this.
#
# WHY SYSTEM. The gate and the tasks it clears run elevated or as SYSTEM. The bridge and every
# cloud session are non-elevated, and a non-elevated process can neither stop an elevated one nor
# `schtasks /End` a SYSTEM task -- which is the only reason the paste needed zuck at all. A
# watchdog that ran with less would log "access denied" every five minutes and clear nothing.
#
# THE ONE-TIME MACHINE CONFIG. The paste's `git config --global --add safe.directory` line is
# written here instead, ONCE, to the SYSTEM git config (not --global: SYSTEM's HOME is
# systemprofile, so a --global entry written from an admin shell lands in the wrong file -- the
# install_adopt_release_task.ps1 lesson). workflow_gate.ps1 also passes it at command scope, so
# this is belt and braces for any other git call into the gate clone. Idempotent.
#
# IDEMPOTENT. With -IfMissing it does nothing when the task already exists (the form
# Adopt-And-Seal.ps1's ensure-task list calls). Without it, it replaces the registration with
# exactly this one.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File desks\mt5\scripts\install_box_self_heal_task.ps1
#   powershell -NoProfile -ExecutionPolicy Bypass -File desks\mt5\scripts\install_box_self_heal_task.ps1 -IfMissing
param([switch]$IfMissing)

$ErrorActionPreference = 'Stop'

$TaskName = 'Quant-BoxSelfHeal'
$DeskRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$RepoRoot = (Resolve-Path (Join-Path $DeskRoot '..\..')).Path
$Script   = Join-Path $RepoRoot 'ops\box_self_heal.py'
if (-not (Test-Path $Script)) { throw "box_self_heal.py missing at $Script" }

# THE SYSTEM TASK RUNS AN ADMIN-ONLY COPY, NEVER THE REPO TREE (audit HOLD of 7a01c1b09). The repo
# is writable by the non-elevated bridge and every cloud session; a SYSTEM task that executed a
# file from it would run whatever was last written there with SYSTEM's rights. So this file and
# the only two helpers it loads are copied into C:\ProgramData\QuantBox\bin, under
# install_unattended.ps1's audited ACL (owned by Administrators/SYSTEM, no junction anywhere, no
# ACE that grants anyone else more than read), and the task runs THAT copy. The installed copy
# loads its helpers from beside itself only; the repo is just its working directory (where it
# writes its report, ledger and state). Re-run this installer to deploy a new version.
$Root   = 'C:\ProgramData\QuantBox'
$BinDir = Join-Path $Root 'bin'
$Copies = @(
    @((Join-Path $RepoRoot 'ops\box_self_heal.py'),        'box_self_heal.py'),
    @((Join-Path $RepoRoot 'ops\process_health.py'),       'process_health.py'),
    @((Join-Path $RepoRoot 'libs\ops\alert_channels.py'),  'alert_channels.py')
)
$Installed = Join-Path $BinDir 'box_self_heal.py'

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) { throw "run this elevated: registering a SYSTEM task needs an administrator" }

$Python = 'C:\Program Files\Python314\python.exe'
if (-not (Test-Path $Python)) {
    $Python = (Get-Command python.exe -ErrorAction Stop).Source
}
& $Python -c "import psutil" 2>$null
if ($LASTEXITCODE -ne 0) {
    "WARNING: psutil is not importable by $Python; the watchdog will report UNMEASURED (RED) and stop nothing until it is"
}
$adm = 'S-1-5-32-544'; $sys = 'S-1-5-18'; $usr = 'S-1-5-32-545'
# THE ROOT IS ADMIN-ONLY FROM ITS FIRST BYTE (install_unattended.ps1's pattern, verbatim in effect):
# a new root is created with its locked ACL in one call; an existing one that Administrators/SYSTEM
# do not own is refused, never taken over; no junction is followed anywhere under it.
if (-not (Test-Path -LiteralPath $Root)) {
    $sec = New-Object System.Security.AccessControl.DirectorySecurity
    $sec.SetAccessRuleProtection($true, $false)
    $sec.SetOwner((New-Object System.Security.Principal.SecurityIdentifier $adm))
    foreach ($ace in @(@($adm, 'FullControl'), @($sys, 'FullControl'), @($usr, 'ReadAndExecute'))) {
        $sec.AddAccessRule((New-Object System.Security.AccessControl.FileSystemAccessRule(
            (New-Object System.Security.Principal.SecurityIdentifier $ace[0]), $ace[1], 'ContainerInherit, ObjectInherit', 'None', 'Allow')))
    }
    $null = [System.IO.Directory]::CreateDirectory($Root, $sec)
}
$owner = (New-Object System.Security.Principal.NTAccount((Get-Acl -LiteralPath $Root).Owner)).Translate([System.Security.Principal.SecurityIdentifier]).Value
if ($owner -notin @($adm, $sys)) { throw "$Root is owned by $owner, not Administrators/SYSTEM; delete it as an administrator and re-run" }
foreach ($c in @(Get-Item -LiteralPath $Root -Force) + @(Get-ChildItem -LiteralPath $Root -Force -Recurse)) {
    if ($c.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "$($c.FullName) is a junction or symlink; not installing" }
}
New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
function Assert-AdminOnly {
    foreach ($path in @($Root) + @(Get-ChildItem -LiteralPath $Root -Force -Recurse | ForEach-Object { $_.FullName })) {
        foreach ($a in (Get-Acl -LiteralPath $path).Access | Where-Object { $_.AccessControlType -eq 'Allow' }) {
            $sid = $a.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value
            $write = [int64]$a.FileSystemRights -band ([int64][System.Security.AccessControl.FileSystemRights]"Write, Delete, ChangePermissions, TakeOwnership" -bor 0x50000000)
            if ($sid -notin @($adm, $sys, $usr) -or ($sid -eq $usr -and $write -ne 0)) {
                throw "$path grants $($a.IdentityReference) more than read; not installing"
            }
        }
    }
}
Assert-AdminOnly
foreach ($pair in $Copies) {
    $src = $pair[0]; $dst = Join-Path $BinDir $pair[1]
    if (-not (Test-Path -LiteralPath $src)) { throw "$($pair[1]) missing at $src" }
    Remove-Item -LiteralPath $dst -Force -ErrorAction SilentlyContinue
    Copy-Item -LiteralPath $src -Destination $dst
    if ((Get-FileHash $dst -Algorithm SHA256).Hash -ne (Get-FileHash $src -Algorithm SHA256).Hash) {
        throw "copy of $($pair[1]) does not match its source; not installing"
    }
    "copied {0} (sha256 {1})" -f $dst, (Get-FileHash $dst -Algorithm SHA256).Hash.ToLower().Substring(0, 12)
}
Assert-AdminOnly     # the copies inherit the root's ACL; proved, not assumed

$LogDir = Join-Path $DeskRoot 'logs'
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }
$Log = Join-Path $LogDir 'Quant-BoxSelfHeal.log'

# No arguments: the rule table is in the code, and the only flag it has is --dry-run. The
# INSTALLED copy, isolated (-I: no PYTHONPATH, no user site, no script-dir imports); the repo is
# only the working directory, which is where the installed copy writes its report and state.
$action = New-ScheduledTaskAction -Execute 'cmd.exe' -WorkingDirectory $RepoRoot -Argument `
    ('/d /s /c ""{0}" -I -W ignore "{1}" >> "{2}" 2>&1"' -f $Python, $Installed, $Log)

# A DAILY trigger repeating every five minutes for one day, never a long -Once (one expired on
# this box 2026-09-21 with Next Run Time N/A). Offset to :03 so it misses the :05/:12/:20 writers.
$at = (Get-Date).Date.AddMinutes(3)
$trigger = New-ScheduledTaskTrigger -Daily -At $at
$trigger.Repetition = (New-ScheduledTaskTrigger -Once -At $at `
    -RepetitionInterval (New-TimeSpan -Minutes 5) `
    -RepetitionDuration (New-TimeSpan -Days 1)).Repetition

# FIFTEEN MINUTES, NOT FOUR (audit HOLD of 7a01c1b09). The scheduler kills a task at its limit
# with no chance to run a `finally`, so a limit that can land inside a freeze leaves a tree
# SUSPENDED -- a wedge this watchdog made. The worst pass is five 60 s schtasks calls (query,
# end, end, end, run; schtasks has been measured hanging past two minutes on this box under
# load), two 10 s kill waits and a 12 s-per-channel page: about 6.5 min. Fifteen is over twice
# that, and still under the report's 20 min staleness, so a hung pass still reads RED.
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 15) -MultipleInstances IgnoreNew

$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

$gateRepo = 'C:/ProgramData/QuantBox/gate-repo'
$already = @(git config --system --get-all safe.directory 2>$null)
if ($already -notcontains $gateRepo) {
    git config --system --add safe.directory $gateRepo 2>&1 | Out-Null
    "safe.directory: added {0} to the SYSTEM git config" -f $gateRepo
}

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings `
    -Description "Closed self-heal table (C:\ProgramData\QuantBox\bin\box_self_heal.py, copied from ops\box_self_heal.py): a hung MT5-IndependenceIntake, a wedged or dead Quant-WorkflowGate only; never the terminal, the money path, the bridge or the miners. Every act and refusal is RED in reports\BOX_SELF_HEAL.json." | Out-Null

$t = Get-ScheduledTask -TaskName $TaskName
"installed {0}: state={1} user={2} interval={3}" -f $t.TaskName, $t.State, $t.Principal.UserId, $t.Triggers[0].Repetition.Interval

Start-ScheduledTask -TaskName $TaskName
Start-Sleep -Seconds 20
$i = Get-ScheduledTaskInfo -TaskName $TaskName
"started {0}: state={1} last_run={2} last_result={3}" -f $TaskName, (Get-ScheduledTask -TaskName $TaskName).State, $i.LastRunTime, $i.LastTaskResult
"report: desks\mt5\reports\BOX_SELF_HEAL.json; ledger: desks\mt5\logs\box_self_heal.jsonl; log: {0}" -f $Log
