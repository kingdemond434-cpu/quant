# Give this box the virtual memory its own workload actually commits.
#
# WHY. Measured 2026-08-28: C:\pagefile.sys was 12,756MB with PeakUsage EQUAL to its allocated
# size -- it had been completely exhausted. Total virtual memory was 20,943MB (8,186 physical +
# 12,756 page) against a workload that commits around 15GB when the searcher, the sweep and the
# terminal overlap. When that ceiling is hit, allocations fail and processes die mid-work with no
# traceback: a profiling run could not even import scipy, failing on
# "DLL load failed while importing _flapack: The paging file is too small for this operation to
# complete." That is the same death the 6.6-hour sweep died -- it vanished with its entire
# buffered log lost, which is why nothing explained it.
#
# Automatic management was ON and still capped at 12,756MB, so leaving it automatic is not a fix.
# C: has 38.4GB free, and a page file is the cheapest possible resource here: disk this box is
# not otherwise using, in exchange for processes that stop dying.
#
# THIS IS NOT A LICENCE TO OVERSUBSCRIBE. Paging is slower than RAM and the memory admission and
# RAM-floor guards stay exactly as they are; their job is to keep the working set in RAM. This
# only ensures that when the box is briefly over its physical memory it SLOWS DOWN instead of
# killing the work -- degradation instead of loss.

$initialMB = 16384
$maxMB = 32768

$free = [math]::Round((Get-PSDrive C).Free / 1GB, 1)
if ($free -lt ($maxMB / 1024) + 5) {
  Write-Output "REFUSING: only ${free}GB free on C:, need $([math]::Round($maxMB/1024)+5)GB headroom for a ${maxMB}MB page file"
  exit 1
}

$cs = Get-CimInstance Win32_ComputerSystem
if ($cs.AutomaticManagedPagefile) {
  Set-CimInstance -InputObject $cs -Property @{ AutomaticManagedPagefile = $false } | Out-Null
  Write-Output "automatic page file management: disabled (it had capped at 12,756MB)"
}

$setting = Get-CimInstance -ClassName Win32_PageFileSetting -Filter "SettingID='pagefile.sys @ C:'" -ErrorAction SilentlyContinue
if ($setting) {
  Set-CimInstance -InputObject $setting -Property @{ InitialSize = $initialMB; MaximumSize = $maxMB } | Out-Null
  Write-Output "page file updated: initial=${initialMB}MB max=${maxMB}MB"
} else {
  New-CimInstance -ClassName Win32_PageFileSetting -Property @{
    Name = 'C:\pagefile.sys'; InitialSize = $initialMB; MaximumSize = $maxMB } | Out-Null
  Write-Output "page file created: initial=${initialMB}MB max=${maxMB}MB"
}

Get-CimInstance Win32_PageFileSetting | ForEach-Object {
  Write-Output ("configured now: " + $_.Name + " initial=" + $_.InitialSize + "MB max=" + $_.MaximumSize + "MB")
}
$os = Get-CimInstance Win32_OperatingSystem
Write-Output ("live totalVirtualMB=" + [math]::Round($os.TotalVirtualMemorySize/1KB) +
              " (a raised MAXIMUM applies as the file grows on demand; the raised INITIAL size " +
              "is only fully in place after the next reboot)")
