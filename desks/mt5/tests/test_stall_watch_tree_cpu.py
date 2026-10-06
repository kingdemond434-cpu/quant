"""Run the watchdog's CPU collector with a mocked Windows process tree."""
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows PowerShell watchdog')
def test_grandchildren_cycles_and_unmeasured_processes():
    path = Path(__file__).resolve().parents[1] / 'scripts' / 'stall_watch.ps1'
    quoted = str(path).replace("'", "''")
    script = f"$source=Get-Content -LiteralPath '{quoted}' -Raw\n" + r'''
$ast=[System.Management.Automation.Language.Parser]::ParseInput($source,[ref]$null,[ref]$null)
$function=$ast.Find({param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq 'Get-ResearchTreeCpuSeconds'},$true)
if (-not $function) { throw 'CPU collector missing' }
Invoke-Expression $function.Extent.Text
function Get-Process {
  param($Id,$ErrorAction)
  if($Id -eq 99){return $null}
  [pscustomobject]@{TotalProcessorTime=[TimeSpan]::FromSeconds(@{1=1;2=2;3=12;4=40}[[int]$Id])}
}
$tree=@([pscustomobject]@{ProcessId=2;ParentProcessId=1},
        [pscustomobject]@{ProcessId=3;ParentProcessId=2},
        [pscustomobject]@{ProcessId=4;ParentProcessId=999},
        [pscustomobject]@{ProcessId=1;ParentProcessId=3})
if((Get-ResearchTreeCpuSeconds -RootProcessId 1 -Snapshot $tree) -ne 15){throw 'Tree CPU wrong'}
if($null -ne (Get-ResearchTreeCpuSeconds -RootProcessId 99 -Snapshot @())){throw 'Missing process measured'}
'''
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
