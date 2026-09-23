# INVENTORY THE CONTABO BOX BEFORE ANY CONSOLIDATION IS PLANNED. Changes nothing.
#
# WHY THIS EXISTS RATHER THAN A QUESTIONNAIRE. The plan for folding the research VPS onto this
# machine depends on numbers nobody should be asked to recite from memory: how much RAM is
# actually free under a live gateway, how big the tick tape really is, whether WSL2 is present,
# what is scheduled here today, and -- the one that decides the whole shape -- how much of this
# box's state is NOT in git and would be lost by a naive move.
#
# Every failure this desk hit on 2026-09-10 came from the two-machine split: adoption that could
# not seal, a sync marker written by one host and read by another, ~960 silent merge aborts
# between two branches, a universe.json that would have zeroed twelve majors, and a code file
# that differed only by line endings between a Linux checkout and a Windows one. One machine with
# one clone removes that class rather than patching it. But it is a LIVE TRADING BOX, so the plan
# gets written against measurements, not assumptions.
#
#   powershell -ExecutionPolicy Bypass -File desks\mt5\scripts\consolidation_inventory.ps1
#
# Writes desks/mt5/reports/CONSOLIDATION_INVENTORY.json and prints a summary. READ ONLY: it
# starts nothing, stops nothing, installs nothing and deletes nothing.

$ErrorActionPreference = "Continue"
$Root = "C:\opt\quant"
$out = [ordered]@{ at = (Get-Date).ToUniversalTime().ToString("o"); root = $Root }

function Section($n) { Write-Host ""; Write-Host "== $n" }
function Line($k, $v) { Write-Host ("   {0,-34} {1}" -f $k, $v) }

# ---------------------------------------------------------------- the machine
Section "Host"
$cs  = Get-CimInstance Win32_ComputerSystem -EA SilentlyContinue
$os  = Get-CimInstance Win32_OperatingSystem -EA SilentlyContinue
$cpu = Get-CimInstance Win32_Processor -EA SilentlyContinue | Select-Object -First 1
$ramMB   = [int]($cs.TotalPhysicalMemory / 1MB)
$freeMB  = [int]($os.FreePhysicalMemory / 1KB)
$out.host = [ordered]@{
    name = $env:COMPUTERNAME
    os = $os.Caption
    build = $os.BuildNumber
    cores_physical = $cs.NumberOfProcessors
    cores_logical = $cs.NumberOfLogicalProcessors
    cpu = $cpu.Name
    ram_total_mb = $ramMB
    ram_free_mb = $freeMB
}
Line "host" $env:COMPUTERNAME
Line "os" ("{0} (build {1})" -f $os.Caption, $os.BuildNumber)
Line "cpu" ("{0} x {1} logical" -f $cpu.Name, $cs.NumberOfLogicalProcessors)
Line "RAM" ("{0} MB total, {1} MB free right now" -f $ramMB, $freeMB)
# THE RESEARCH SIDE IS WHAT NEEDS THE MEMORY. The old 4GB host OOM-killed its own cron daemon
# (3.1GB peak) and the global killer then took the dashboard rather than the organ that overran.
if ($ramMB -lt 16000) {
    Line "VERDICT" "under 16GB -- the research pipeline and a live gateway will contend; say so in the plan"
} else {
    Line "VERDICT" "enough headroom to host the research pipeline beside the gateway"
}

# ---------------------------------------------------------------- disk
Section "Disk"
$out.disks = @()
foreach ($d in (Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3" -EA SilentlyContinue)) {
    $row = [ordered]@{ drive = $d.DeviceID
                       size_gb = [math]::Round($d.Size / 1GB, 1)
                       free_gb = [math]::Round($d.FreeSpace / 1GB, 1) }
    $out.disks += $row
    Line $d.DeviceID ("{0} GB free of {1} GB" -f $row.free_gb, $row.size_gb)
}

# ---------------------------------------------------------------- WSL2
Section "WSL2"
# THE ONE THING THAT DECIDES THE SHAPE. The research side runs 160 committed systemd USER timers.
# Windows has no systemd, so either WSL2 hosts them unchanged or all 160 are hand-ported to Task
# Scheduler -- weeks of regression risk on a desk that already cannot complete a cycle.
$wsl = $null
try { $wsl = (& wsl.exe --status) 2>&1 | Out-String } catch { $wsl = "" }
$wslList = ""
try { $wslList = (& wsl.exe -l -v) 2>&1 | Out-String } catch { $wslList = "" }
$hasWsl = ($LASTEXITCODE -eq 0) -or ($wsl -and $wsl.Trim().Length -gt 0)
$out.wsl = [ordered]@{ present = [bool]$hasWsl; status = "$wsl".Trim(); distros = "$wslList".Trim() }
if ($hasWsl) { Line "wsl" "PRESENT"; "$wslList".Trim() -split "`n" | ForEach-Object { Line "  " $_.Trim() } }
else { Line "wsl" "ABSENT -- installable with: wsl --install -d Ubuntu (needs a reboot)" }
$hyperv = (Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Windows-Subsystem-Linux -EA SilentlyContinue)
if ($hyperv) { Line "WSL feature" $hyperv.State }

# ---------------------------------------------------------------- what is scheduled here now
Section "Scheduled tasks (MT5-*)"
$tasks = Get-ScheduledTask -EA SilentlyContinue | Where-Object { $_.TaskName -like "MT5-*" -or $_.TaskName -like "*mt5*" -or $_.TaskName -like "*quant*" -or $_.TaskName -like "*Codex*" }
$out.tasks = @()
foreach ($t in $tasks) {
    $i = Get-ScheduledTaskInfo -TaskName $t.TaskName -EA SilentlyContinue
    $row = [ordered]@{ name = $t.TaskName; state = "$($t.State)"
                       last_run = "$($i.LastRunTime)"; last_result = $i.LastTaskResult
                       next_run = "$($i.NextRunTime)" }
    $out.tasks += $row
    Line $t.TaskName ("{0}  last={1} rc={2}" -f $t.State, $i.LastRunTime, $i.LastTaskResult)
}
Line "count" $out.tasks.Count
# A DISABLED TASK IS THE STALENESS. MT5-AdoptRelease was disabled by hand during the 2026-09-10
# lock fight and must go back on; it is what keeps this box current.
$disabled = @($out.tasks | Where-Object { $_.state -eq "Disabled" })
if ($disabled.Count) { Line "DISABLED" (($disabled | ForEach-Object { $_.name }) -join ", ") }

# ---------------------------------------------------------------- MT5 terminal
Section "MetaTrader"
$mt5 = Get-Process terminal64, terminal -EA SilentlyContinue | Select-Object -First 1
$out.mt5 = [ordered]@{ running = [bool]$mt5; path = if ($mt5) { $mt5.Path } else { "" } }
Line "terminal" (if ($mt5) { "RUNNING  $($mt5.Path)" } else { "not running" })
try {
    $py = (& python -c "import MetaTrader5,sys;print(MetaTrader5.__version__)") 2>&1 | Out-String
    $out.mt5.python_package = "$py".Trim()
    Line "MetaTrader5 python pkg" "$py".Trim()
} catch { Line "MetaTrader5 python pkg" "NOT IMPORTABLE -- the gateway cannot reach the terminal" }

# ---------------------------------------------------------------- the repo
Section "Repo"
Push-Location $Root -EA SilentlyContinue
$out.repo = [ordered]@{}
$out.repo.head      = (& git log --oneline -1) 2>&1 | Out-String
$out.repo.branch    = ((& git rev-parse --abbrev-ref HEAD) 2>&1 | Out-String).Trim()
$out.repo.unpushed  = ((& git rev-list --count "@{u}..HEAD") 2>&1 | Out-String).Trim()
$out.repo.dirty     = @((& git status --porcelain) 2>&1 | Where-Object { $_ -and $_ -notmatch '^\?\?' }).Count
$out.repo.untracked = @((& git status --porcelain) 2>&1 | Where-Object { $_ -match '^\?\?' }).Count
$out.repo.locks     = @(Get-ChildItem "$Root\.git" -Filter "*.lock" -EA SilentlyContinue | ForEach-Object { $_.Name })
Line "branch" $out.repo.branch
Line "head" $out.repo.head.Trim()
Line "unpushed commits" $out.repo.unpushed
Line "tracked dirty / untracked" ("{0} / {1}" -f $out.repo.dirty, $out.repo.untracked)
if ($out.repo.locks.Count) { Line "STALE GIT LOCKS" ($out.repo.locks -join ", ") }

# ---------------------------------------------------------------- state that git does NOT carry
Section "State outside git (this is what a naive move loses)"
# repo-root data/* is gitignored with a short allowlist, and desks/mt5/reports/* entirely. Those
# paths exist ONLY here. Sizing them is the difference between a copy that takes minutes and one
# that takes a day.
$out.unversioned = @()
foreach ($rel in @("data", "desks\mt5\data\tape", "desks\mt5\reports", "desks\mt5\logs",
                   "data\secrets", "desks\mt5\data\universe")) {
    $p = Join-Path $Root $rel
    if (-not (Test-Path $p)) { Line $rel "absent"; continue }
    $items = Get-ChildItem $p -Recurse -File -EA SilentlyContinue
    $mb = [math]::Round((($items | Measure-Object Length -Sum).Sum) / 1MB, 1)
    $row = [ordered]@{ path = $rel; files = $items.Count; mb = $mb }
    $out.unversioned += $row
    Line $rel ("{0} files, {1} MB" -f $items.Count, $mb)
}

# ---------------------------------------------------------------- verdict
Section "Summary"
$outFile = Join-Path $Root "desks\mt5\reports\CONSOLIDATION_INVENTORY.json"
New-Item -ItemType Directory -Force -Path (Split-Path $outFile) -EA SilentlyContinue | Out-Null
$out | ConvertTo-Json -Depth 6 | Set-Content -Path $outFile -Encoding utf8
Write-Host "   written: $outFile"
Write-Host ""
Write-Host "   NOTHING WAS CHANGED. Paste the summary above (or the JSON) back to the cloud"
Write-Host "   session and the consolidation plan gets written against these numbers."
Pop-Location -EA SilentlyContinue
