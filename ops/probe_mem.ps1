$ErrorActionPreference = "SilentlyContinue"
"== MEMORY OVERVIEW =="
$os = Get-CimInstance Win32_OperatingSystem
"Total: {0:N1} GB   Free: {1:N1} GB" -f ($os.TotalVisibleMemorySize/1MB), ($os.FreePhysicalMemory/1MB)
"== TOP PROCESSES BY WORKING SET =="
Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 15 | ForEach-Object { "{0,-24} {1,8:N0} MB  PID {2}" -f $_.ProcessName, ($_.WorkingSet64/1MB), $_.Id }
"== PYTHON PROCESSES WITH COMMAND LINES =="
Get-CimInstance Win32_Process -Filter "Name='python.exe' or Name='python3.exe' or Name='py.exe'" | ForEach-Object { "PID {0} cmdline: {1}" -f $_.ProcessId, $_.CommandLine }