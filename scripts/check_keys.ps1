<#
.SYNOPSIS
  Which API keys this Windows host can see. Prints presence and length, NEVER a value.

.DESCRIPTION
  Reads the key list from libs\ops\env_keys_catalog.json (the same list scripts\check_keys.py
  and libs\ops\env_keys.read_key use) and, for each name, checks the Machine scope (setx /M),
  the User scope (setx) and this process. Read-only: it sets nothing and restarts nothing.

  powershell -ExecutionPolicy Bypass -File C:\opt\quant\scripts\check_keys.ps1
#>
[CmdletBinding()]
param([string]$Catalog = (Join-Path $PSScriptRoot '..\libs\ops\env_keys_catalog.json'))

$ErrorActionPreference = 'Stop'
$cat = Get-Content -Raw -Encoding UTF8 $Catalog | ConvertFrom-Json

function Measure-Key([string]$name) {
    $m = [Environment]::GetEnvironmentVariable($name, 'Machine')
    $u = [Environment]::GetEnvironmentVariable($name, 'User')
    $p = [Environment]::GetEnvironmentVariable($name, 'Process')
    $where = @()
    if ($m) { $where += 'machine' }
    if ($u) { $where += 'user' }
    if ($p) { $where += 'process' }
    $len = 0
    foreach ($v in @($m, $u, $p)) { if ($v) { $len = $v.Trim().Length; break } }
    [pscustomobject]@{
        Key     = $name
        Status  = $(if ($where.Count) { 'present' } else { 'MISSING' })
        Length  = $len
        Where   = $(if ($where.Count) { $where -join ',' } else { '-' })
        Group   = ''
        Machine = ''
    }
}

$rows = foreach ($k in $cat.keys) {
    $r = Measure-Key $k.name
    if ($r.Status -eq 'MISSING' -and $k.aliases) {
        foreach ($al in $k.aliases) {
            $a2 = Measure-Key $al
            if ($a2.Status -eq 'present') { $r = $a2; $r.Key = "$($k.name) (as $al)"; break }
        }
    }
    $r.Group = $k.group
    $r.Machine = $k.machine
    $r
}
$rows | Format-Table -AutoSize Key, Status, Length, Where, Group, Machine

$cfg = foreach ($c in $cat.config) { Measure-Key $c.name }
Write-Host 'Config ids (not secrets) some keyed sources also need:'
$cfg | Format-Table -AutoSize Key, Status, Where

$free = @('free_data', 'free_llm', 'free_infra')
$missing = $rows | Where-Object { $_.Status -eq 'MISSING' -and $free -contains $_.Group }
$present = ($rows | Where-Object { $_.Status -eq 'present' }).Count
Write-Host ("{0}/{1} present. Free keys still missing: {2}" -f $present, $rows.Count,
    $(if ($missing) { ($missing.Key -join ', ') } else { 'none' }))
$stale = $rows | Where-Object { $_.Where -match 'machine|user' -and $_.Where -notmatch 'process' }
if ($stale) {
    Write-Host ("Set in the registry but not in this window: {0}. That is normal right after setx;" -f ($stale.Key -join ', '))
    Write-Host 'open a new PowerShell to see them here. The desk reads the registry directly (read_key).'
}
