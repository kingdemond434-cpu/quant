param([string]$Source,[switch]$ReadRealTasks)
$ErrorActionPreference='Stop'
$tokens=$null; $errors=$null
$ast=[System.Management.Automation.Language.Parser]::ParseFile($Source,[ref]$tokens,[ref]$errors)
if ($errors.Count) { throw $errors[0] }
$definition=$ast.FindAll({param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst]},$true) | Where-Object Name -eq 'Get-RequiredTaskPresence'
if (@($definition).Count -ne 1) { throw 'Expected unique census function' }
. ([scriptblock]::Create($definition.Extent.Text))
$script:seen=@()
$rows=@(Get-RequiredTaskPresence -TaskNames @('MT5-Present','MT5-Missing','MT5-Timeout','MT5-Denied','MT5-Wrong') -Query {
  param($name)
  $script:seen += $name
  switch ($name) {
    'MT5-Present' { [pscustomobject]@{TaskName=$name;TaskPath='\'} }
    'MT5-Missing' { }
    'MT5-Timeout' { throw [System.TimeoutException]::new('synthetic') }
    'MT5-Denied' { throw [System.UnauthorizedAccessException]::new('synthetic') }
    'MT5-Wrong' { [pscustomobject]@{TaskName=$name;TaskPath='\Other\'} }
  }
})
$expected=@('PRESENT','MISSING','UNMEASURED','UNMEASURED','UNMEASURED')
for($i=0;$i -lt $expected.Count;$i++) {
  if($rows[$i].State -ne $expected[$i]) { throw "Bad state for $($rows[$i].TaskName)" }
}
if($script:seen.Count -ne 5) { throw 'Query was repeated or expanded' }
if($rows[2].Reason -ne 'TimeoutException' -or $rows[3].Reason -ne 'UnauthorizedAccessException') { throw 'Failure type lost' }
if((Get-Content $Source -Raw).Contains('$present = (schtasks /Query')) { throw 'Unbounded inventory remains' }
Write-Output '8 census controls passed; no actuator invoked'
if($ReadRealTasks) {
  $clock=[System.Diagnostics.Stopwatch]::StartNew()
  $real=@(Get-RequiredTaskPresence -TaskNames @('MT5-Gauntlet','MT5-Shadow','MT5-Hourly','MT5-DeskState','MT5-MoatRecorder','MT5-MoatSilver','MT5-StallWatch','MT5-Universe','MT5-ShadowSync','MT5-TerminalBoot'))
  [pscustomobject]@{elapsed_s=$clock.Elapsed.TotalSeconds;tasks=$real} | ConvertTo-Json -Depth 4
}
