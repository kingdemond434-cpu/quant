<#
.SYNOPSIS
    BOOT r23 + r24, the owner's one install: the guard's folder and the run-as migrator.
    Run once, elevated, from the boot checkout:  powershell -ExecutionPolicy Bypass -File ops\box_git\install_guard.ps1

    zuck 2026-11-27 13:13Z: "An independent, protected automated checker validates it ... You only
    intervene when the system needs to change its fundamental authority or protected safeguards."

    WHAT IT DOES (logged to C:\ProgramData\QuantBox\logs\install_guard_<stamp>.log); it changes no
    trading task, no terminal and nothing in C:\opt\quant except one ACL grant to quantrun:
      1. Refuses unless elevated.
      2. C:\ProgramData\QuantBox\guard (+ verdicts, runas): Administrators and SYSTEM Full,
         quantgate Modify (the loop writes verdicts and the merge ledger), quantci and quantrun
         denied.
      3. Creates `quantrun` (no administrator) with batch logon, Modify on C:\opt\quant, read on
         the python the gateway uses, and WRITE DENIED on guard, trust, tokens, forge, inbox, each
         terminal's install folder and each terminal's data folder.
      4. Copies the migrator (runas_plan.py, runas_probe.py, migrate.ps1) from this checkout into
         guard\runas and records each file's SHA-256 in guard\runas\PINNED.json.
      5. Writes venues.json: each running terminal's exe, its data folder (from origin.txt) and
         the LAST TWO DIGITS of its login (from the window title), nothing more.
      6. Registers QuantGuard-RunAs (SYSTEM, every 5 min) and runs it once. From here the migrator
         probes, waits for the weekend closure, moves, watches and proves on its own.
#>
$ErrorActionPreference = 'Stop'
$src   = Split-Path -Parent $MyInvocation.MyCommand.Path            # ...\ops\box_git
$QB    = 'C:\ProgramData\QuantBox'
$Guard = Join-Path $QB 'guard'
$Runas = Join-Path $Guard 'runas'
$Live  = 'C:\opt\quant'
$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$null  = New-Item -ItemType Directory -Force -Path (Join-Path $QB 'logs')
$log   = Join-Path $QB "logs\install_guard_$stamp.log"
function Say([string] $m) { $l = "{0}  {1}" -f (Get-Date).ToUniversalTime().ToString('HH:mm:ss'), $m; Write-Host $l; Add-Content -LiteralPath $log -Value $l }
function Stop-Here([string] $why) { Say "STOPPED: $why"; exit 1 }

$me = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
if (-not $me.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { Stop-Here 'run this elevated (Run as administrator)' }

# 1-2. the guard's folder
$null = New-Item -ItemType Directory -Force -Path $Guard, (Join-Path $Guard 'verdicts'), $Runas
& icacls $Guard /inheritance:r /grant:r "*S-1-5-32-544:(OI)(CI)F" "*S-1-5-18:(OI)(CI)F" "quantgate:(OI)(CI)M" | Out-Null
& icacls $Runas /inheritance:r /grant:r "*S-1-5-32-544:(OI)(CI)F" "*S-1-5-18:(OI)(CI)F" "quantgate:(OI)(CI)RX" | Out-Null
& icacls $Guard /deny "quantci:(OI)(CI)F" | Out-Null
Say "guard folder ready: $Guard (Admins/SYSTEM full, quantgate modify, quantci denied)"

# 3. quantrun
$RunUser = 'quantrun'
if (-not (Get-LocalUser -Name $RunUser -ErrorAction SilentlyContinue)) {
    $b = New-Object byte[] 24; [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b)
    $pw = ConvertTo-SecureString ([Convert]::ToBase64String($b)) -AsPlainText -Force
    New-LocalUser -Name $RunUser -Password $pw -PasswordNeverExpires -UserMayNotChangePassword `
        -Description 'Quant box trading code (no admin)' | Out-Null
    $pw = $null
    Say "created $RunUser (no administrator; S4U tasks need no stored password)"
}
$sid = (New-Object Security.Principal.NTAccount $RunUser).Translate([Security.Principal.SecurityIdentifier]).Value
$inf = Join-Path $env:TEMP 'qr_rights.inf'; $db = Join-Path $env:TEMP 'qr_rights.sdb'
& secedit /export /cfg $inf /areas USER_RIGHTS | Out-Null
$rights = Get-Content -LiteralPath $inf
if (-not ($rights -match "SeBatchLogonRight.*\*$sid")) {
    $rights = $rights -replace '^(SeBatchLogonRight\s*=\s*.*)$', "`$1,*$sid"
    if (-not ($rights -match '^SeBatchLogonRight')) { $rights += "SeBatchLogonRight = *$sid" }
    Set-Content -LiteralPath $inf -Value $rights
    & secedit /configure /db $db /cfg $inf /areas USER_RIGHTS | Out-Null
}
Remove-Item -LiteralPath $inf, $db -Force -ErrorAction SilentlyContinue

# the python the gateway runs (from its own task), which quantrun must be able to read
$gw = Get-ScheduledTask -TaskName 'MT5-Gateway' -ErrorAction SilentlyContinue
$py = $null
if ($gw) {
    $blob = ($gw.Actions | ForEach-Object { "$($_.Execute) $($_.Arguments)" }) -join ' '
    $m = [regex]::Match($blob, '[A-Za-z]:\\[^"&>|]*?python\.exe')
    if ($m.Success) { $py = $m.Value }
    elseif ($blob -match '(Python3\d+\\python\.exe)') {
        $cand = @("C:\$($Matches[1])", "C:\Program Files\$($Matches[1])", "$env:LOCALAPPDATA\Programs\Python\$($Matches[1])")
        $py = $cand | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    }
}
if (-not $py) { Stop-Here 'could not find the python MT5-Gateway runs' }
Set-Content -LiteralPath (Join-Path $Runas 'python.txt') -Value $py -Encoding ascii
& icacls (Split-Path -Parent $py) /grant "${RunUser}:(OI)(CI)RX" | Out-Null
Set-Content -LiteralPath (Join-Path $Runas 'live_tree.txt') -Value $Live -Encoding ascii
& icacls $Live /grant "${RunUser}:(OI)(CI)M" | Out-Null
Say "python: $py (quantrun may read it); quantrun may modify $Live"

# 5. venues: running terminals, their data folders, login suffixes
$venues = @()
$dataRoot = 'C:\Users\Administrator\AppData\Roaming\MetaQuotes\Terminal'
foreach ($p in Get-Process -Name terminal64 -ErrorAction SilentlyContinue | Where-Object { $_.SessionId -ne 0 -and $_.Path }) {
    $dirs = @(Get-ChildItem -LiteralPath $dataRoot -Directory -ErrorAction SilentlyContinue | Where-Object {
        $o = Join-Path $_.FullName 'origin.txt'
        (Test-Path -LiteralPath $o) -and ((Get-Content -LiteralPath $o -Raw -Encoding Unicode).Trim() -eq (Split-Path -Parent $p.Path))
    } | ForEach-Object { $_.FullName })
    $digits = [regex]::Match("$($p.MainWindowTitle)", '\d{4,}').Value
    if (-not $digits) { Stop-Here "terminal $($p.Path): no login in its window title; cannot set the probe's expectation" }
    $name = if ($p.Path -match 'FTMO') { 'ftmo' } elseif ($p.Path -match 'Fusion') { 'fusion' } else { "t$($p.Id)" }
    $venues += @{ name = $name; exe = $p.Path; install = (Split-Path -Parent $p.Path); data_dirs = $dirs
                  expect = $digits.Substring($digits.Length - 2) }
    Say "venue $name : $($p.Path), $($dirs.Count) data folder(s), login ending $($digits.Substring($digits.Length - 2))"
}
if ($venues.Count -eq 0) { Stop-Here 'no interactive terminal running; start them first' }
$venues | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $Runas 'venues.json') -Encoding utf8

# write denied for quantrun (Audit MF-A, Q2)
$deny = @($Guard, (Join-Path $QB 'trust'), (Join-Path $QB 'tokens'), (Join-Path $QB 'forge'), (Join-Path $QB 'inbox'), 'C:\opt\bridge')
foreach ($v in $venues) { $deny += $v.install; $deny += $v.data_dirs }
foreach ($d in $deny) { if (Test-Path -LiteralPath $d) { & icacls $d /deny "${RunUser}:(OI)(CI)(W,D,DC,WDAC,WO)" | Out-Null; Say "write denied to quantrun: $d" } }

# (Audit MF1 (b)) quantci, which runs PR code, may not read the terminals or the MT5 package
$mt5pkg = Join-Path (Split-Path -Parent $py) 'Lib\site-packages\MetaTrader5'
foreach ($d in @($venues | ForEach-Object { $_.install }) + @($mt5pkg)) {
    if (Test-Path -LiteralPath $d) { & icacls $d /deny "quantci:(OI)(CI)(RX)" | Out-Null; Say "quantci denied: $d" }
}

# (Audit C3) the door: protect.py rule 7, every LIVE move needs a guard verdict or is a seal.
# The pinned copy in trust\ is replaced from this checkout and the hook gains --guard-dir.
$trust = Join-Path $QB 'trust'
Copy-Item -LiteralPath (Join-Path $src 'protect.py') -Destination (Join-Path $trust 'protect.py') -Force
$hook = Get-ChildItem -Path (Join-Path $QB 'forge') -Recurse -Filter 'box-protect' -ErrorAction SilentlyContinue |
    Where-Object { $_.DirectoryName -like '*pre-receive.d' } | Select-Object -First 1
if (-not $hook) { Stop-Here 'could not find the forge pre-receive hook box-protect' }
$text = Get-Content -LiteralPath $hook.FullName -Raw
if ($text -notmatch '--guard-dir') {
    $gFwd = ($Guard -replace '\\','/')
    $text = $text -replace '(--trust-dir "[^"]+")', "`$1 --guard-dir `"$gFwd`""
    Set-Content -LiteralPath $hook.FullName -Value $text -Encoding ascii
}
& icacls (Join-Path $Guard 'verdicts') /grant "quantforge:(OI)(CI)RX" | Out-Null
& icacls $Guard /grant "quantforge:(RX)" | Out-Null
Say "door: protect.py pinned in trust\, hook reads guard\verdicts ($($hook.FullName))"

# 4. the pinned migrator
$pinned = @{}
foreach ($f in @('runas_plan.py', 'runas_probe.py', 'runas\migrate.ps1', 'runas\git_acl.ps1')) {
    $from = Join-Path $src $f
    if (-not (Test-Path -LiteralPath $from)) { Stop-Here "missing $from" }
    $to = Join-Path $Runas (Split-Path -Leaf $f)
    Copy-Item -LiteralPath $from -Destination $to -Force
    $pinned[(Split-Path -Leaf $f)] = (Get-FileHash -LiteralPath $to -Algorithm SHA256).Hash.ToLower()
}
$pinned | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $Runas 'PINNED.json') -Encoding utf8
Say ("pinned: " + (($pinned.GetEnumerator() | ForEach-Object { "$($_.Key) $($_.Value.Substring(0,12))" }) -join ', '))

# (Audit C4) THE PINNED ADOPTER: a clean checkout of THIS boot commit in guard\adopt\tree, run by
# MT5-AdoptRelease with -Pinned. Only its action changes; its principal stays SYSTEM. The tree's
# .git config, hooks and info are denied to quantrun so no adopted code can plant a git hook.
$adopt = Join-Path $Guard 'adopt'; $tree = Join-Path $adopt 'tree'
$repo = Split-Path -Parent (Split-Path -Parent $src)
$bootSha = ((& git -C $repo rev-parse HEAD) | Out-String).Trim()
if ($bootSha -notmatch '^[0-9a-f]{40}$') { Stop-Here "cannot read this checkout's HEAD" }
$null = New-Item -ItemType Directory -Force -Path $adopt
if (Test-Path -LiteralPath $tree) { Remove-Item -LiteralPath $tree -Recurse -Force }
& git -c core.hooksPath=NUL clone -q --no-checkout $repo $tree
& git -c core.hooksPath=NUL -C $tree checkout -q $bootSha
if ($LASTEXITCODE -ne 0) { Stop-Here "could not check out $bootSha into $tree" }
# THE PINNED PYTHON IS THE GUARD'S OWN (Audit C4, r24.2). The gateway's interpreter may be the
# tree's .venv, or a base install quantrun or Users can write, so the adopter runs neither: the
# BASE install is copied into guard\adopt\base (Admins and SYSTEM only), a fresh venv is built from
# that copy in guard\adopt\venv, the gateway's packages are copied in (minus any .pth or editable
# hook pointing into C:\opt), and the runtime fence becomes its sitecustomize. The install stops
# if python is older than 3.11 (no PYTHONSAFEPATH) or any sys.path entry still points into C:\opt.
& icacls $adopt /inheritance:r /grant:r "*S-1-5-32-544:(OI)(CI)F" "*S-1-5-18:(OI)(CI)F" | Out-Null
$pyInfo = (& $py -I -c "import sys, json, sysconfig; print(json.dumps({'base': sys.base_prefix, 'ver': list(sys.version_info[:2]), 'site': sysconfig.get_paths()['purelib']}))" | Out-String).Trim() | ConvertFrom-Json
if (-not $pyInfo) { Stop-Here "could not interrogate $py" }
if ($pyInfo.ver[0] -lt 3 -or ($pyInfo.ver[0] -eq 3 -and $pyInfo.ver[1] -lt 11)) { Stop-Here "python $($pyInfo.ver -join '.') has no PYTHONSAFEPATH; the pinned adopter needs 3.11+" }
$baseCopy = Join-Path $adopt 'base'; $venv = Join-Path $adopt 'venv'
foreach ($d in @($baseCopy, $venv)) { if (Test-Path -LiteralPath $d) { Remove-Item -LiteralPath $d -Recurse -Force } }
& robocopy "$($pyInfo.base)".TrimEnd('\') $baseCopy /E /XD site-packages __pycache__ /NFL /NDL /NJH /NJS /NP | Out-Null
if (-not (Test-Path -LiteralPath (Join-Path $baseCopy 'python.exe'))) { Stop-Here "could not copy the base interpreter $($pyInfo.base)" }
& (Join-Path $baseCopy 'python.exe') -I -m venv --without-pip $venv
$pinnedPy = Join-Path $venv 'Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pinnedPy)) { Stop-Here "could not build the guard venv at $venv" }
$vsite = Join-Path $venv 'Lib\site-packages'
if (Test-Path -LiteralPath $pyInfo.site) { & robocopy $pyInfo.site $vsite /E /XD __pycache__ /NFL /NDL /NJH /NJS /NP | Out-Null }
Get-ChildItem -LiteralPath $vsite -Filter '*.pth' -ErrorAction SilentlyContinue | Where-Object {
    (Get-Content -LiteralPath $_.FullName -Raw) -match '(?i)c:[\\/]+opt|__editable__' } | ForEach-Object {
    Remove-Item -LiteralPath $_.FullName -Force; Say "guard venv: dropped $($_.Name) (it pointed into C:\opt)" }
Get-ChildItem -LiteralPath $vsite -Filter '__editable__*' -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
$sc = Join-Path $vsite 'sitecustomize.py'
if (Test-Path -LiteralPath $sc) { Move-Item -LiteralPath $sc -Destination (Join-Path $vsite 'sitecustomize_orig.py') -Force }
Copy-Item -LiteralPath (Join-Path $tree 'ops\box_git\pinned_sitecustomize.py') -Destination $sc -Force
$env:QUANT_ADOPT_PINNED = '1'; $env:QUANT_LEDGER_ROOT = $Live; $env:PYTHONSAFEPATH = '1'; $env:PYTHONPATH = $tree
$sp = (& $pinnedPy -c "import sys, json; print(json.dumps([bool(getattr(sys, '_quant_pinned_fence', False))] + sys.path))" | Out-String).Trim() | ConvertFrom-Json
Remove-Item Env:QUANT_ADOPT_PINNED, Env:QUANT_LEDGER_ROOT, Env:PYTHONSAFEPATH, Env:PYTHONPATH -ErrorAction SilentlyContinue
if (-not $sp -or $sp[0] -ne $true) { Stop-Here "the pinned fence did not arm in $pinnedPy" }
$leak = @($sp | Select-Object -Skip 1 | Where-Object { "$_".ToLower().StartsWith('c:\opt\') -or "$_" -eq '' })
if ($leak.Count -gt 0) { Stop-Here ("the guard venv still reaches into C:\opt: " + ($leak -join ', ')) }
Set-Content -LiteralPath (Join-Path $adopt 'python.txt') -Value $pinnedPy -Encoding ascii
Say "pinned python: $pinnedPy (base copied from $($pyInfo.base), fence armed, nothing on sys.path under C:\opt)"
& icacls $adopt /inheritance:r /grant:r "*S-1-5-32-544:(OI)(CI)F" "*S-1-5-18:(OI)(CI)F" | Out-Null
# (Audit MF1 on r5) THE LIVE TREE'S .git IS SEALED AGAINST quantrun. Its Modify on C:\opt\quant
# would otherwise let it rename .git (DELETE inherits onto the folder) and drop in one with its own
# config, whose filters, sshCommand, helpers or includes then run inside SYSTEM git. So: .git and
# .git\config are owned by Administrators; quantrun is denied D/WDAC/WO on .git itself (this folder
# only), W/D/WDAC/WO on .git\config, everything but read on hooks and info, and DC on the tree
# root. Test-GitAclSealed (the same check the pinned adopter and the RUN_AS proof run) must pass.
$gitDir = Join-Path $Live '.git'
& icacls $gitDir /setowner '*S-1-5-32-544' | Out-Null
& icacls (Join-Path $gitDir 'config') /setowner '*S-1-5-32-544' | Out-Null
& icacls $gitDir /deny "${RunUser}:(D,WDAC,WO)" | Out-Null
& icacls (Join-Path $gitDir 'config') /deny "${RunUser}:(W,D,WDAC,WO)" | Out-Null
foreach ($g in @('hooks', 'info')) {
    $gp = Join-Path $gitDir $g
    if (-not (Test-Path -LiteralPath $gp)) { $null = New-Item -ItemType Directory -Force -Path $gp }
    & icacls $gp /setowner '*S-1-5-32-544' | Out-Null
    & icacls $gp /deny "${RunUser}:(OI)(CI)(W,D,DC,WDAC,WO)" | Out-Null
}
# the root itself: owned by Administrators, never renamed, deleted or re-ACLed by quantrun (this
# folder only), and its parent takes no new folder or file from quantrun -- so no swapped tree
# with its own .git can appear at the same path after the check passes (Audit, r6 hold).
& icacls $Live /setowner '*S-1-5-32-544' | Out-Null
& icacls $Live /deny "${RunUser}:(D,DC,WDAC,WO)" | Out-Null
& icacls (Split-Path -Parent $Live) /deny "${RunUser}:(WD,AD,DC,WDAC,WO)" | Out-Null
. (Join-Path $tree 'ops\box_git\runas\git_acl.ps1')
$unsealed = Test-GitAclSealed -RepoRoot $Live -RunUser $RunUser
if ($unsealed.Count -gt 0) { Stop-Here ("the live .git is not sealed against ${RunUser}: " + ($unsealed -join '; ')) }
Say "live .git sealed against ${RunUser} (owner Administrators; no rename, re-ACL or config write)"
$ar = Get-ScheduledTask -TaskName 'MT5-AdoptRelease' -ErrorAction SilentlyContinue
if (-not $ar) { Stop-Here 'MT5-AdoptRelease not found' }
$pinScript = Join-Path $tree 'desks\mt5\scripts\Adopt-And-Seal.ps1'
$newAct = New-ScheduledTaskAction -Execute 'powershell.exe' -WorkingDirectory $Live `
    -Argument "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$pinScript`" -RepoRoot `"$Live`" -GuardRoot `"$tree`" -Pinned"
Set-ScheduledTask -TaskName 'MT5-AdoptRelease' -TaskPath $ar.TaskPath -Action $newAct | Out-Null
@{ boot = $bootSha; old_actions = @($ar.Actions | ForEach-Object { @{ execute = "$($_.Execute)"; arguments = "$($_.Arguments)"; workdir = "$($_.WorkingDirectory)" } }) } |
    ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $adopt 'old_action.json') -Encoding utf8
Say "pinned adopter: $tree at $($bootSha.Substring(0,12)); MT5-AdoptRelease now runs it with -Pinned (old action kept in old_action.json)"

# r22's packets inbox (BRIEF2 step 2, measured absent 14:00Z): author packets only; the loop's
# drop stage refuses any verdict or seat line in it (drop_pull.stage_packets).
$pk = 'C:\opt\bridge\quant\packets_inbox'
$null = New-Item -ItemType Directory -Force -Path $pk
& icacls $pk /inheritance:r /grant:r "*S-1-5-32-544:(OI)(CI)F" "*S-1-5-18:(OI)(CI)F" "Administrator:(OI)(CI)M" | Out-Null
Say "packets inbox ready: $pk"

# 6. the migrator's task
$act = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$Runas\migrate.ps1`""
$trg = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 5)
$set = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 20) -StartWhenAvailable
$pr  = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
Register-ScheduledTask -TaskName 'QuantGuard-RunAs' -Action $act -Trigger $trg -Settings $set -Principal $pr -Force | Out-Null
Start-ScheduledTask -TaskName 'QuantGuard-RunAs'
Say 'QuantGuard-RunAs registered (SYSTEM, every 5 min) and started: it probes now, moves only in the weekend closure'
Say "log: $log"
