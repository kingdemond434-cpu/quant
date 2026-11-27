# ONE-TIME INSTALL r12: deliveries never need an admin window or a login again (zuck 2026-11-27 00:40Z:
# "fix this permanently ... always go through route that needs neither which delivers same thing").
# Run ONCE from an elevated PowerShell, as zuck's own act. It does exactly three things:
#  1. Grants the interactive owner account (the user SID of whoever runs this, i.e. VMI3571445\Administrator)
#     Modify on C:\opt\bridge\quant\drop_local only, so the owner's ordinary (non-elevated, logged-in) Claude desktop
#     session can stage packets there exactly as the elevated session used to. No other account is added: quantgate,
#     quantci (PR code), Users and Everyone keep read-only or nothing. Every consumer check is unchanged: drop_pull's
#     names/size caps, inbox.py's bundle verify + exact head + auditor-only verdict seat, the mover's sha256 + AUDIT
#     CLEAR + single refs/heads head + fast-forward + D0/D1 (owner approvals stay admin-only in ProgramData).
#  2. Keeps drop_local\owner_seed admin-only (it feeds installers, which run as admin).
#  3. Copies the packets staged by the Autonomy seat in $Stage (if present) into drop_local through temp names,
#     bundles first and verdicts last, after checking each bundle's sha256 against $Want. Nothing else is touched.
# It changes no task, no mover, no trust folder, no secret. Reversal: icacls drop_local /remove:g <sid>.
$ErrorActionPreference = 'Stop'
$Local = 'C:\opt\bridge\quant\drop_local'
$Stage = 'C:\Users\Administrator\quant_install\stage'
$Want = @{
    'ceilings-ftmo-gold-e8-probe-7c3fbc4a20.bundle' = 'E2DC0DFD1B9CFB5131DB59A8C4A5ED37D2F04CCB74BC1D8AB23BB59655FA2A78'
    'gold-session-probe-forge-a52e840922.bundle'    = 'E181C99F854E07CBE3AA6FF90CE0B937EC29655A5CDB6D4705269585720FB172'
    'ftmo-gold-decouple-forge-cc85654d0e.bundle'    = '2944A8E4ED8D5430DD53DC5C9F0B1EB5656FA990476467DA94EE43001AF5F6E3'
    'ftmo-gold-sleeves-forge-09f8cba568.bundle'     = 'B5D0A729148667954850AF14183B6908A2513E4A19642C1DB32A4E10C07BF48D'
    'release-train-4-gates-r6-d9d4e3f697.bundle'    = '48AFF72D3B95F70A72ED0CD79CF89DABE9E51B8882EAA0514EB2160B7F013A77'
}
$id = [Security.Principal.WindowsIdentity]::GetCurrent()
if (-not ([Security.Principal.WindowsPrincipal]::new($id)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'not elevated: right-click PowerShell, Run as administrator'
}
$sid = $id.User.Value
if ($sid -eq 'S-1-5-18') { throw 'run as the owner account, not SYSTEM' }
if (-not (Test-Path -LiteralPath $Local -PathType Container)) { throw "$Local is missing" }
if ((Get-Item -LiteralPath $Local).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "$Local is a reparse point" }
$icacls = "$env:SystemRoot\System32\icacls.exe"
# 1. owner account: Modify on drop_local (inherits to new files and folders)
& $icacls $Local /grant "*${sid}:(OI)(CI)M" | Out-Null
if ($LASTEXITCODE -ne 0) { throw "icacls grant exited $LASTEXITCODE" }
# 2. owner_seed stays Admins/SYSTEM only
$Seed = Join-Path $Local 'owner_seed'
if (Test-Path -LiteralPath $Seed) {
    & $icacls $Seed /inheritance:r /grant:r '*S-1-5-32-544:(OI)(CI)F' '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-545:(OI)(CI)RX' | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "icacls owner_seed exited $LASTEXITCODE" }
}
Write-Host "GRANTED: $sid Modify on $Local (owner_seed admin-only)"
# 3. deliver tonight's staged packets (same checks the consumers apply afterwards)
if (Test-Path -LiteralPath $Stage) {
    $vdir = Join-Path $Local 'verdicts'
    if (-not (Test-Path -LiteralPath $vdir)) { New-Item -ItemType Directory -Path $vdir | Out-Null }
    foreach ($b in $Want.Keys) {
        $src = Join-Path $Stage $b
        if (-not (Test-Path -LiteralPath $src)) { Write-Host "SKIP $b (not staged)"; continue }
        $h = (Get-FileHash -Algorithm SHA256 -LiteralPath $src).Hash
        if ($h -ne $Want[$b]) { Write-Host "REFUSED $b sha256 $h"; continue }
        $stem = $b.Substring(0, $b.Length - '.bundle'.Length)
        $pairs = @(@($b, $Local), @("$stem.json", $Local), @("verdicts\$stem.json", $vdir))
        foreach ($p in $pairs) {
            $s = Join-Path $Stage $p[0]
            if (-not (Test-Path -LiteralPath $s)) { throw "$s missing for $b" }
        }
        foreach ($p in $pairs) {
            $leaf = Split-Path -Leaf $p[0]
            $tmp = Join-Path $p[1] ".$leaf.part"
            Copy-Item -LiteralPath (Join-Path $Stage $p[0]) -Destination $tmp -Force
            Move-Item -LiteralPath $tmp -Destination (Join-Path $p[1] $leaf) -Force
        }
        Write-Host "DELIVERED $stem"
    }
}
Write-Host 'r12 DONE'
