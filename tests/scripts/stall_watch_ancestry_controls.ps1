param([string]$Source)
$ErrorActionPreference = 'Stop'
$tokens=$null; $errors=$null
$ast=[System.Management.Automation.Language.Parser]::ParseFile($Source,[ref]$tokens,[ref]$errors)
if ($errors.Count) { throw $errors[0] }
foreach ($name in @('Get-GauntletLauncherAncestor','Get-ResearchStackedDisposition')) {
  $definition=$ast.FindAll({param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst]},$true) | Where-Object Name -eq $name
  if (@($definition).Count -ne 1) { throw "Missing unique function $name" }
  . ([scriptblock]::Create($definition.Extent.Text))
}
function Proc($id,$parent,$command,$time=1) {
  [pscustomobject]@{ProcessId=$id;ParentProcessId=$parent;CommandLine=$command;CreationDate=$time}
}
$root=Proc 100 1 'python C:\opt\quant\desks\mt5\scripts\run_sharded_gauntlet.py'
$a=Proc 200 100 'python external_gauntlet shard_worker('
$aa=Proc 201 200 'python external_gauntlet shard_worker('
$b=Proc 300 100 'python external_gauntlet shard_worker('
$bb=Proc 301 300 'python external_gauntlet shard_worker('
$deep=Proc 302 301 'python external_gauntlet shard_worker('
$other=Proc 400 1 'python C:/opt/quant/desks/mt5/scripts/run_sharded_gauntlet.py'
$c=Proc 500 400 'python external_gauntlet shard_worker('
$cc=Proc 501 500 'python external_gauntlet shard_worker('
$snapshot=@($root,$a,$aa,$b,$bb,$deep,$other,$c,$cc)
$checks=0
function Check($candidate,$expected,$pattern='external_gauntlet',$items=$snapshot) {
  $actual=Get-ResearchStackedDisposition $pattern $a $candidate $items
  if ($actual -ne $expected) { throw "PID $($candidate.ProcessId): $actual != $expected" }
  $script:checks++
}
Check $aa KEEP_RELATED
Check $b KEEP_RELATED
Check $bb KEEP_SHARD_TREE
Check $deep KEEP_SHARD_TREE
Check $cc KILL_DUPLICATE
Check $bb KILL_DUPLICATE edge_search
Check (Proc 600 999 'python external_gauntlet shard_worker(') UNMEASURED_ANCESTRY
Check (Proc 601 602 'python external_gauntlet shard_worker(') UNMEASURED_ANCESTRY external_gauntlet @($root,$a,(Proc 601 602 'x'),(Proc 602 601 'x'))
Check (Proc 603 300 'python external_gauntlet shard_worker(' 0.5) UNMEASURED_ANCESTRY
Check (Proc 604 999 'python external_gauntlet.py') KILL_DUPLICATE
if (-not ($bb.ParentProcessId -ne $a.ProcessId -and $bb.ParentProcessId -ne $a.ParentProcessId)) { throw 'Regression fixture did not reproduce old kill' }
Write-Output "$checks pure classification controls passed; no process operations executed"

