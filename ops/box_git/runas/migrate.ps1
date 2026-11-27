<#
.SYNOPSIS
    BOOT r24 run-as migrator. Pinned copy in C:\ProgramData\QuantBox\guard\runas, task
    QuantGuard-RunAs (SYSTEM) every 5 minutes. Every decision is ops/box_git/runas_plan.py's
    (pinned beside this file); this script only reads tasks and carries the decision out.

    Bounds (Audit 2026-11-27 13:30Z): only the PRINCIPAL of live-tree tasks changes, only TO
    quantrun, after a snapshot of the old principal; after a move only checks run; rollback
    restores the snapshot and nothing else. The portable-terminal move is NOT in r24: if the attach
    probe fails, the state is BLOCKED and nothing moves.
#>
param([switch] $Rollback)
$ErrorActionPreference = 'Stop'
$Self   = $MyInvocation.MyCommand.Path
$Here   = Split-Path -Parent $Self
$Guard  = Split-Path -Parent $Here
$Py     = Get-Content -LiteralPath (Join-Path $Here 'python.txt') -TotalCount 1
$Plan   = Join-Path $Here 'runas_plan.py'
$Probe  = Join-Path $Here 'runas_probe.py'
$State  = Join-Path $Here 'state.json'
$Snap   = Join-Path $Here 'snapshot.json'
$Probes = Join-Path $Here 'probes.json'
$Tasks  = Join-Path $Here 'tasks.json'
$Alarm  = Join-Path $Here 'ALARM.json'
$Log    = Join-Path $Here 'migrate.log'
$Venues = Get-Content -LiteralPath (Join-Path $Here 'venues.json') -Raw | ConvertFrom-Json
$RunUser = 'quantrun'

function Say([string] $m) {
    Add-Content -LiteralPath $Log -Value ("{0}  {1}" -f (Get-Date).ToUniversalTime().ToString('s'), $m)
}
function Save($obj, [string] $path) {
    $tmp = "$path.part"
    $obj | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $tmp -Encoding utf8
    Move-Item -LiteralPath $tmp -Destination $path -Force
}
function Raise-Alarm([string] $why) {
    Save @{ at = (Get-Date).ToUniversalTime().ToString('s'); why = $why } $Alarm
    Say "ALARM: $why"
}
function Read-Tasks {
    $rows = foreach ($t in Get-ScheduledTask) {
        $acts = $null
        try {
            $acts = @($t.Actions | ForEach-Object {
                @{ execute = "$($_.Execute)"; arguments = "$($_.Arguments)"; workdir = "$($_.WorkingDirectory)" } })
        } catch { $acts = $null }
        @{ name = $t.TaskName; path = $t.TaskPath; actions = $acts
           principal = @{ user = "$($t.Principal.UserId)"; logon = "$($t.Principal.LogonType)"
                          runlevel = "$($t.Principal.RunLevel)" } }
    }
    Save @($rows) $Tasks
}
function Set-Principal([string] $name, $p) {
    $t = Get-ScheduledTask -TaskName $name
    if ($p.user -match '^(NT AUTHORITY\\)?SYSTEM$') {
        $np = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
    } else {
        $np = New-ScheduledTaskPrincipal -UserId $p.user -LogonType $p.logon -RunLevel $p.runlevel
    }
    Set-ScheduledTask -TaskName $name -TaskPath $t.TaskPath -Principal $np | Out-Null
}
function Restart-Moved([string[]] $names) {
    # One pipe per venue (Audit should-fix 1): every moved task stops, its old principal's python
    # leftovers end, and only then does any start again.
    foreach ($n in $names) { Stop-ScheduledTask -TaskName $n -ErrorAction SilentlyContinue }
    $markers = @()
    foreach ($n in $names) {
        foreach ($a in (Get-ScheduledTask -TaskName $n).Actions) {
            $wd = if ($a.WorkingDirectory) { $a.WorkingDirectory } else { 'C:\opt\quant' }
            foreach ($m in [regex]::Matches("$($a.Arguments)", '[\w:\\/.-]+\.(py|cmd|ps1)')) {
                $markers += if ([IO.Path]::IsPathRooted($m.Value)) { $m.Value } else { Join-Path $wd $m.Value }
            }
        }
    }
    if ($markers.Count) { & $Py -I $Plan kill-old @markers | ForEach-Object { Say "kill-old: $_" } }
    foreach ($n in $names) { Start-ScheduledTask -TaskName $n -ErrorAction SilentlyContinue }
}
function Run-Probe([string] $exe, [string] $expect, [string] $out) {
    # One-shot task as quantrun (S4U, Limited): attach, read the login suffix, shut down.
    $name = 'QuantGuard-RunAsProbe'
    $act = New-ScheduledTaskAction -Execute $Py -Argument "-I `"$Probe`" --exe `"$exe`" --expect $expect --out `"$out`""
    $pr  = New-ScheduledTaskPrincipal -UserId $RunUser -LogonType S4U -RunLevel Limited
    $set = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 3) -MultipleInstances IgnoreNew
    Register-ScheduledTask -TaskName $name -Action $act -Principal $pr -Settings $set -Force | Out-Null
    Remove-Item -LiteralPath $out -ErrorAction SilentlyContinue
    Start-ScheduledTask -TaskName $name
    $deadline = (Get-Date).AddMinutes(4)
    while (-not (Test-Path -LiteralPath $out) -and (Get-Date) -lt $deadline) { Start-Sleep -Seconds 5 }
    Unregister-ScheduledTask -TaskName $name -Confirm:$false -ErrorAction SilentlyContinue
    if (Test-Path -LiteralPath $out) { return (Get-Content -LiteralPath $out -Raw | ConvertFrom-Json) }
    return @{ ok = $false; why = 'probe wrote nothing in 4 min' }
}
function Write-Probes {
    # Each must be DENIED for quantrun (Audit MF-A, Q2). Probed by a one-shot quantrun task.
    $targets = @((Join-Path $Guard ''), 'C:\ProgramData\QuantBox\trust', 'C:\ProgramData\QuantBox\tokens',
                 'C:\ProgramData\QuantBox\forge', 'C:\ProgramData\QuantBox\inbox', 'C:\Windows\System32\Tasks')
    foreach ($v in $Venues) { $targets += $v.install; $targets += $v.data_dirs }
    $list = Join-Path $Here 'write_targets.json'; Save @($targets) $list
    $out = Join-Path $Here 'write_probe.json'
    $name = 'QuantGuard-RunAsWrite'
    $code = "import json,os,sys,uuid;t=json.load(open(sys.argv[1],encoding='utf-8-sig'));r={}`n" +
            "for d in t:`n p=os.path.join(d,'.w'+uuid.uuid4().hex)`n try:`n  open(p,'w').close();os.remove(p);r[d]=False`n except OSError:`n  r[d]=True`n" +
            "json.dump(r,open(sys.argv[2],'w'))"
    $cf = Join-Path $Here 'write_probe.py'; Set-Content -LiteralPath $cf -Value $code -Encoding ascii
    $act = New-ScheduledTaskAction -Execute $Py -Argument "-I `"$cf`" `"$list`" `"$out`""
    $pr  = New-ScheduledTaskPrincipal -UserId $RunUser -LogonType S4U -RunLevel Limited
    Register-ScheduledTask -TaskName $name -Action $act -Principal $pr -Force | Out-Null
    Remove-Item -LiteralPath $out -ErrorAction SilentlyContinue
    Start-ScheduledTask -TaskName $name
    $deadline = (Get-Date).AddMinutes(2)
    while (-not (Test-Path -LiteralPath $out) -and (Get-Date) -lt $deadline) { Start-Sleep -Seconds 3 }
    Unregister-ScheduledTask -TaskName $name -Confirm:$false -ErrorAction SilentlyContinue
    if (Test-Path -LiteralPath $out) { return $out }
    Save @{} $out; return $out   # nothing measured: proof refuses an empty probe set
}
function Terminal-Checks {
    # No EA attached and DLL imports off on every venue's data folder (Audit Q2).
    $r = @{}
    foreach ($v in $Venues) {
        foreach ($d in $v.data_dirs) {
            $ini = Join-Path $d 'config\common.ini'
            $dll = (Test-Path -LiteralPath $ini) -and -not (Select-String -LiteralPath $ini -Pattern '^\s*AllowDllImport\s*=\s*1' -Quiet)
            $r["$d dll_off"] = [bool]$dll
            $ea = @(Get-ChildItem -LiteralPath (Join-Path $d 'MQL5\Profiles\Charts') -Recurse -Filter *.chr -ErrorAction SilentlyContinue |
                    Select-String -Pattern '^\s*<expert>' -List)
            $r["$d no_ea"] = ($ea.Count -eq 0)
        }
    }
    $out = Join-Path $Here 'terminal_checks.json'; Save $r $out; return $out
}

# ------------------------------------------------------------------ one cycle
Read-Tasks
if ($Rollback) {
    $snap = Get-Content -LiteralPath $Snap -Raw | ConvertFrom-Json
    $names = @($snap.PSObject.Properties.Name)
    foreach ($n in $names) { Set-Principal $n $snap.$n; Say "rollback: $n -> $($snap.$n.user)" }
    Restart-Moved $names
    Save @{ state = 'ROLLED_BACK'; at = (Get-Date).ToUniversalTime().ToString('s') } $State
    Raise-Alarm 'rolled back to the snapshot; the seat CLEAR is required again'
    Read-Tasks
}
$st = if (Test-Path -LiteralPath $State) { Get-Content -LiteralPath $State -Raw | ConvertFrom-Json } else { @{ state = 'PROBE' } }
$d = (& $Py -I $Plan plan $Tasks $State $Probes) | ConvertFrom-Json
switch -Regex ($d.action) {
    '^probe$' {
        # every venue must attach: the move takes the FTMO lanes too
        $rows = @(); $all = $true
        foreach ($v in $Venues) {
            $r = Run-Probe $v.exe $v.expect (Join-Path $Here "probe_attach_$($v.name).json")
            $rows += @{ venue = $v.name; ok = [bool]$r.ok; why = "$($r.why)" }
            if (-not $r.ok) { $all = $false }
            Say "probe attach $($v.name): ok=$($r.ok) $($r.why)"
        }
        Save @{ attach = @{ ok = $all; venues = $rows } } $Probes
        Save @{ state = 'PROBE' } $State
    }
    '^wait:(\w+)$' { Save @{ state = 'WAIT_WINDOW'; mode = $Matches[1] } $State; Say "probe passed ($($Matches[1])); waiting for the weekend window" }
    '^wait$' { }
    '^alarm$' { Save @{ state = 'BLOCKED' } $State; Raise-Alarm 'attach probe failed; nothing moves (portable is not in r24)' }
    '^move:attach$' {
        $names = @($d.move)
        Save $d.snapshot $Snap                       # bound 2: snapshot before any change
        foreach ($n in $names) {
            Set-Principal $n @{ user = $RunUser; logon = 'S4U'; runlevel = 'Limited' }
            Say "moved: $n -> $RunUser"
        }
        Restart-Moved $names
        Save @{ state = 'MOVED'; mode = 'attach'; moved_at = (Get-Date).ToUniversalTime().ToString('s'); moved = $names } $State
    }
    '^move:' { Save @{ state = 'BLOCKED' } $State; Raise-Alarm "mode $($d.action) is not in r24" }
    '^check$' {
        if ($st.state -in @('MOVED', 'WATCH')) {
            $hb = Join-Path (Get-Content -LiteralPath (Join-Path $Here 'live_tree.txt') -TotalCount 1) 'desks\mt5\data\gateway_state.json'
            $wv = (& $Py -I $Plan watch $st.moved_at $hb) | Select-Object -Last 1
            if ($wv -eq 'rollback') {
                Say 'Monday watch: gateway heartbeat stale after the move; rolling back'
                & powershell -NoProfile -ExecutionPolicy Bypass -File $Self -Rollback
                exit 0
            } elseif ($wv -eq 'done') { $st.state = 'DONE'; Save $st $State; Say 'watch passed: DONE' }
            elseif ($st.state -eq 'MOVED') { $st.state = 'WATCH'; Save $st $State }
        }
    }
}
# proof, every cycle (Audit MF-A/MF-B): guard\runas\RUN_AS.json (quantgate may only read it)
$w = Write-Probes; $t = Terminal-Checks
& $Py -I $Plan proof $Tasks $w $t (Join-Path $Here 'RUN_AS.json') | Out-Null
