# ONE-TIME INSTALL of the dashboard push (Cloudflare Pages + Workers KV), r2 (dash_push r2). Run ONCE in an admin PowerShell on the box.
# Installs C:\ProgramData\QuantBox\dash\dash_push.py (admin/SYSTEM-only) from the local drop, only if its sha256 is the
# Audit-CLEAR one, and registers QuantForge-DashPush (SYSTEM, every 1 min, one instance at a time, 5 min limit).
# The task reads CLOUDFLARE_API_TOKEN / CLOUDFLARE_ACCOUNT_ID from machine env, never prints them, and keeps the slug
# and the permanent URL only in C:\ProgramData\QuantBox\dash (admin/SYSTEM-only). Public report: desks\mt5\reports\DASHBOARD_PUSH.json.
# Off switch: Disable-ScheduledTask QuantForge-DashPush (the site keeps serving the last feed; nothing else depends on it).
# Idempotent: re-running with the same file re-asserts the ACL and the task; the slug (permanent link) is never re-minted.
param([Parameter(Mandatory = $true)][string] $ExpectSha256)
$ErrorActionPreference = 'Stop'
$Src = 'C:\opt\bridge\quant\drop_local\dashboard\dash_push.py'
$Dir = 'C:\ProgramData\QuantBox\dash'
$Dst = "$Dir\dash_push.py"
$Py = 'C:\Program Files\Python314\python.exe'
$Task = 'QuantForge-DashPush'
if (-not (Test-Path -LiteralPath $Src)) { throw "$Src is missing; nothing installed" }
if (-not (Test-Path -LiteralPath $Py)) { throw "$Py is missing; nothing installed" }
if (-not (Test-Path -LiteralPath $Dir)) { New-Item -ItemType Directory -Path $Dir | Out-Null }
& "$env:SystemRoot\System32\icacls.exe" $Dir /setowner '*S-1-5-32-544' | Out-Null
if ($LASTEXITCODE -ne 0) { throw "icacls setowner $Dir exited $LASTEXITCODE" }
& "$env:SystemRoot\System32\icacls.exe" $Dir /inheritance:r /grant:r '*S-1-5-32-544:(OI)(CI)F' '*S-1-5-18:(OI)(CI)F' | Out-Null
if ($LASTEXITCODE -ne 0) { throw "icacls $Dir exited $LASTEXITCODE" }
$tmp = "$Dst.new"
Copy-Item -LiteralPath $Src -Destination $tmp -Force
$got = (Get-FileHash -Algorithm SHA256 -LiteralPath $tmp).Hash
if ($got -ne $ExpectSha256.ToUpper()) { Remove-Item -LiteralPath $tmp -Force; throw "sha256 $got is not the Audit-CLEAR $ExpectSha256; nothing installed" }
& $Py -I -c "import ast,sys; ast.parse(open(sys.argv[1],encoding='utf-8').read())" $tmp
if ($LASTEXITCODE -ne 0) { Remove-Item -LiteralPath $tmp -Force; throw 'candidate does not parse; nothing installed' }
Move-Item -LiteralPath $tmp -Destination $Dst -Force
Write-Host "INSTALLED $Dst sha256 $got"
$act = New-ScheduledTaskAction -Execute $Py -Argument "-I `"$Dst`"" -WorkingDirectory $Dir
$trg = New-ScheduledTaskTrigger -Once -At ((Get-Date).AddMinutes(1)) -RepetitionInterval (New-TimeSpan -Minutes 1)
$set = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 5) -StartWhenAvailable
$pri = New-ScheduledTaskPrincipal -UserId 'S-1-5-18' -LogonType ServiceAccount -RunLevel Highest
Register-ScheduledTask -TaskName $Task -Action $act -Trigger $trg -Settings $set -Principal $pri -Force | Out-Null
Write-Host "TASK $Task registered (SYSTEM, every 1 min). First tick in about a minute; report: C:\opt\quant\desks\mt5\reports\DASHBOARD_PUSH.json"
