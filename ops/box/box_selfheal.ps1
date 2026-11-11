# THE BOX'S THREE STUCK STEPS, HEALED BY THE SYSTEM ADOPTER (Governance, 2026-11-11).
#
# Dot-sourced by desks\mt5\scripts\Adopt-And-Seal.ps1, which runs as SYSTEM on every adoption.
# Before this file, each of these needed an elevated Administrator window and a person in it.
# zuck (11-11 12:33Z-12:36Z): "I approve it dont require me now", "fix all the jams".
# Each step acts only on its exact stuck shape. It never chooses a value of its own, and a
# failure is logged and never stops the seal.
#
#  1. PIN RELOCATION. zuck wrote the ROOT pin himself on 11-11 to C:\opt\authority\ROOT_PIN.json.
#     Every reader uses C:\opt\audit_registry\ROOT_PIN.json, so his pin was never read. (The wrong
#     path was Governance's unjam line, copied from pin_root.py's own docstring.) This step moves
#     HIS file, byte for byte, to where the readers look. It does so only when ALL of these hold:
#       a. the file's digest equals this adopted tree's root digest (pin_root.py, read only);
#       b. its owner and every principal that may write it are Administrators or SYSTEM, so no
#          session or user could have written it;
#       c. its commit is an ancestor of this tree's HEAD;
#       d. the registry pin is absent or differs from it.
#     It never computes or writes a digest of its own. With no owner file there is nothing to move.
#
#  2. GATE CLONE RESET. The gate clone (C:\ProgramData\QuantBox\gate-repo) holds no state. On the
#     blobless clone, `sparse-checkout set` before the fetch fails with 128 from the second sweep
#     on; #887 is the code fix. While the newest FAILED line in workflow_gate.log is that failure
#     and no checkout has happened since (the clone's index is older), the clone is removed. The
#     next sweep re-clones it, and every merge rule still applies to that sweep.
#
#  3. BIN REFRESH. The gate runs admin-only COPIES in C:\ProgramData\QuantBox\bin, so a merged
#     fix to ops\box\*.ps1 used to wait for a person to re-run install_unattended.ps1. The copies are
#     refreshed from this tree ONLY while its root digest equals the registry pin. workflow_gate.ps1
#     is a ROOT file (enforced_root_files), so a copy can only ever carry code the ROOT path
#     approved. If the pin does not match, nothing is copied.

$QB = Join-Path $env:ProgramData "QuantBox"
$OwnerPin = "C:\opt\authority\ROOT_PIN.json"
$RegistryPin = "C:\opt\audit_registry\ROOT_PIN.json"
$AdminSids = @("S-1-5-32-544", "S-1-5-18")   # BUILTIN\Administrators, NT AUTHORITY\SYSTEM

function Get-TreeRootDigest {
    $out = @(& $py @pyArgs (Join-Path $RepoRoot "ops\release\authority\pin_root.py") 2>$null)
    $d = ("$($out | Select-Object -Last 1)").Trim()
    if ($d -match '^[0-9a-f]{64}$') { return $d }
    return $null
}

function Read-PinDigest([string] $path) {
    if (-not (Test-Path -LiteralPath $path)) { return $null }
    try { return [string](Get-Content -LiteralPath $path -Raw | ConvertFrom-Json).digest } catch { return $null }
}

function Test-AdminOnlyWrite([string] $path) {
    $acl = Get-Acl -LiteralPath $path
    $owner = (New-Object System.Security.Principal.NTAccount($acl.Owner)).Translate(
        [System.Security.Principal.SecurityIdentifier]).Value
    if ($AdminSids -notcontains $owner) { return $false }
    $write = [System.Security.AccessControl.FileSystemRights]"Write, Modify, FullControl, ChangePermissions, TakeOwnership"
    foreach ($a in $acl.Access) {
        if ($a.AccessControlType -ne "Allow") { continue }
        if (([int]$a.FileSystemRights -band [int]$write) -eq 0) { continue }
        $sid = $a.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value
        if ($AdminSids -notcontains $sid) { return $false }
    }
    return $true
}

function Invoke-PinRelocation([string] $treeDigest) {
    $owner = Read-PinDigest $OwnerPin
    if (-not $owner) { return "pin: no owner pin at $OwnerPin; nothing to move" }
    if ($owner -eq (Read-PinDigest $RegistryPin)) { return "pin: registry pin already equals the owner pin" }
    if ($owner -ne $treeDigest) { return "pin: owner pin $($owner.Substring(0,12)) is not this tree's root $treeDigest; NOT moved" }
    if (-not (Test-AdminOnlyWrite $OwnerPin)) { return "pin: $OwnerPin is writable by a non-admin principal; NOT moved" }
    $commit = ""
    try { $commit = [string](Get-Content -LiteralPath $OwnerPin -Raw | ConvertFrom-Json).commit } catch { }
    if ($commit -notmatch '^[0-9a-f]{40}$') { return "pin: owner pin names no commit; NOT moved" }
    & git -C $RepoRoot merge-base --is-ancestor $commit HEAD 2>$null
    if ($LASTEXITCODE -ne 0) { return "pin: owner pin commit $($commit.Substring(0,12)) is not an ancestor of HEAD; NOT moved" }
    Copy-Item -LiteralPath $OwnerPin -Destination $RegistryPin -Force
    & icacls $RegistryPin /inheritance:r /grant:r "*S-1-5-32-544:F" "*S-1-5-18:F" "*S-1-5-32-545:R" | Out-Null
    return "pin: MOVED the owner pin $($owner.Substring(0,12)) to $RegistryPin (byte copy)"
}

function Invoke-GateCloneReset {
    $clone = Join-Path $QB "gate-repo"
    $log = Join-Path $QB "logs\workflow_gate.log"
    $index = Join-Path $clone ".git\index"
    if (-not (Test-Path -LiteralPath $log) -or -not (Test-Path -LiteralPath $index)) { return "gate: nothing to reset" }
    $last = Get-Content -LiteralPath $log -Tail 400 | Where-Object { $_ -match 'FAILED: ' } | Select-Object -Last 1
    if (-not $last -or $last -notmatch 'sparse-checkout failed') { return "gate: no sparse-checkout jam" }
    $at = [datetime]::MinValue
    if (-not [datetime]::TryParse(($last -split ' ')[0..1] -join ' ', [ref]$at)) { return "gate: unreadable failure time; not reset" }
    if ((Get-Item -LiteralPath $index).LastWriteTimeUtc -ge $at.ToUniversalTime()) { return "gate: a checkout ran after the failure" }
    Remove-Item -LiteralPath $clone -Recurse -Force -ErrorAction SilentlyContinue
    if (Test-Path -LiteralPath $clone) { return "gate: jammed clone could NOT be removed" }
    return "gate: removed the jammed clone (failure at $($at.ToString('u'))); the next sweep re-clones"
}

function Invoke-BinRefresh([string] $treeDigest) {
    $bin = Join-Path $QB "bin"
    if (-not (Test-Path -LiteralPath $bin)) { return "bin: no bin dir; install_unattended has not run" }
    $pin = Read-PinDigest $RegistryPin
    if ($pin -ne $treeDigest) { return "bin: this tree's root is not the registry pin; nothing copied" }
    $done = @()
    foreach ($name in @('unattended_boot.ps1', 'workflow_gate.ps1', 'sign_train_leg.ps1')) {
        $src = Join-Path $RepoRoot ("ops\box\" + $name)
        $dst = Join-Path $bin $name
        if (-not (Test-Path -LiteralPath $src)) { continue }
        if ((Test-Path -LiteralPath $dst) -and
            (Get-FileHash $src -Algorithm SHA256).Hash -eq (Get-FileHash $dst -Algorithm SHA256).Hash) { continue }
        Copy-Item -LiteralPath $src -Destination $dst -Force
        $done += $name
    }
    if ($done) { return "bin: refreshed $($done -join ', ') from the pinned tree" }
    return "bin: copies already match the pinned tree"
}

function Invoke-BoxSelfHeal {
    try {
        $tree = Get-TreeRootDigest
        if (-not $tree) { Log "selfheal: this tree's root digest is unreadable; nothing done"; return }
        foreach ($step in @(
                { Invoke-PinRelocation $tree },
                { Invoke-GateCloneReset },
                { Invoke-BinRefresh $tree })) {
            try { Log ("selfheal: " + (& $step)) | Out-Host } catch { Log "selfheal: step failed: $($_.Exception.Message)" | Out-Host }
        }
    } catch {
        Log "selfheal: failed: $($_.Exception.Message)" | Out-Host
    }
}
