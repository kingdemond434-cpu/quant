# THE BOX'S THREE STUCK STEPS, HEALED BY THE SYSTEM ADOPTER (Governance, 2026-11-11).
#
# Dot-sourced by desks\mt5\scripts\Adopt-And-Seal.ps1 on every adoption. Before this file, each step
# needed an elevated Administrator window and a person in it. zuck (11-11 12:33Z-12:36Z): "I approve
# it dont require me now", "fix all the jams". Conditions are the Auditor's ROOT ruling of 11-11
# 12:38Z, lettered as in that ruling. Each step acts only on its exact stuck shape, never chooses a
# value of its own, writes one line to an append-only ledger, and never stops the seal.
#
#  1. PIN RELOCATION. zuck wrote the ROOT pin himself on 11-11 to C:\opt\authority\ROOT_PIN.json.
#     Every reader uses C:\opt\audit_registry\ROOT_PIN.json, so his pin was never read. (The wrong
#     path was Governance's unjam line, copied from pin_root.py's own docstring.) HIS file is copied
#     byte for byte to where the readers look, only when ALL of these hold:
#       a. its digest equals LIVE's root digest, read from LIVE at run time (d), never remembered;
#       b. its owner and every principal that may write it are Administrators or SYSTEM;
#       c. its commit is an ancestor of LIVE;
#       i. this runner is SYSTEM or an Administrators member;
#       j. no guard read UNMEASURED.
#     An existing destination holding LIVE's digest, or the same bytes, means nothing is done (h).
#     A stale destination (another digest) is RENAMED to .superseded-<UTC>, never deleted (f). The
#     copy must hash equal to the source (e), and the source stays where it is as evidence (g).
#
#  2. GATE CLONE RESET. The gate clone (C:\ProgramData\QuantBox\gate-repo) holds no state. On the
#     blobless clone `sparse-checkout set` before the fetch fails with 128 from the second sweep on;
#     #887 is the code fix. The clone is RENAMED to gate-repo.failed-<UTC> only when:
#       - the newest FAILED line in workflow_gate.log is that failure;
#       - no checkout has run since (the clone's index is older);
#       - the log lives outside the clone;
#       - no reset happened in the last 24 h.
#     If the clone jams again inside the 24 h, the step says so once (PAGE) and does not loop.
#     Renamed clones older than 7 days are pruned only after a good checkout has run since them.
#
#  3. BIN REFRESH. The gate runs admin-only COPIES in C:\ProgramData\QuantBox\bin, so a merged
#     fix to ops\box\*.ps1 used to wait for a person to re-run install_unattended.ps1. The copies are
#     refreshed from this tree ONLY while its root digest equals the registry pin. workflow_gate.ps1
#     is a ROOT file (enforced_root_files), so a copy only ever carries code the ROOT path approved.

$QB = Join-Path $env:ProgramData "QuantBox"
$OwnerPin = "C:\opt\authority\ROOT_PIN.json"
$RegistryPin = "C:\opt\audit_registry\ROOT_PIN.json"
$HealLedger = Join-Path $QB "logs\selfheal_ledger.jsonl"
$LiveRef = "claude/llm-auto-upgrade-verify-gcjac3"
$AdminSids = @("S-1-5-32-544", "S-1-5-18")   # BUILTIN\Administrators, NT AUTHORITY\SYSTEM

function Write-HealLedger([hashtable] $row) {
    $row["at"] = (Get-Date).ToUniversalTime().ToString("o")
    $row["runner"] = [Security.Principal.WindowsIdentity]::GetCurrent().Name
    try {
        $null = New-Item -ItemType Directory -Force -Path (Split-Path $HealLedger)
        Add-Content -LiteralPath $HealLedger -Value ($row | ConvertTo-Json -Compress -Depth 4) -Encoding utf8
    } catch { }
}

function Get-RevRootDigest([string] $rev) {
    $out = @(& $py @pyArgs (Join-Path $RepoRoot "ops\box\live_root_digest.py") $rev 2>$null)
    if ($LASTEXITCODE -ne 0) { return $null }
    $d = ("$($out | Select-Object -Last 1)").Trim()
    if ($d -match '^[0-9a-f]{64}$') { return $d }
    return $null
}

function Get-LiveRootDigest {
    & git -C $RepoRoot fetch -q --no-tags origin "+refs/heads/${LiveRef}:refs/remotes/origin/${LiveRef}" 2>$null
    if ($LASTEXITCODE -ne 0) { return $null }
    return Get-RevRootDigest "origin/$LiveRef"
}

function Read-PinDigest([string] $path) {
    if (-not (Test-Path -LiteralPath $path)) { return $null }
    try { return [string](Get-Content -LiteralPath $path -Raw | ConvertFrom-Json).digest } catch { return $null }
}

function Test-RunnerIsAdmin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    if ($id.User.Value -eq "S-1-5-18") { return $true }
    return ([Security.Principal.WindowsPrincipal]$id).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
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

function Get-Sha([string] $path) { (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLower() }

function Invoke-PinRelocation([string] $live) {
    $g = [ordered]@{}
    $row = @{ step = "pin"; guards = $g }
    try {
        $g.runner_admin = Test-RunnerIsAdmin                                       # (i)
        if (-not $g.runner_admin) { return "pin: runner is not SYSTEM/Administrators; nothing done" }
        if (-not (Test-Path -LiteralPath $OwnerPin)) { return "pin: no owner pin at $OwnerPin; nothing to move" }
        $src = Get-Sha $OwnerPin; $row.source_sha256 = $src
        if ((Test-Path -LiteralPath $RegistryPin) -and (Get-Sha $RegistryPin) -eq $src) {
            return "pin: registry pin already has the owner pin's bytes; nothing done"            # (h)
        }
        if (-not $live) { $g.live_digest = "UNMEASURED"; Write-HealLedger $row; return "pin: LIVE's root digest UNMEASURED; NOT moved" }   # (d)(j)
        if ((Read-PinDigest $RegistryPin) -eq $live) { return "pin: registry pin already holds LIVE's root; nothing done" }   # (h)
        $owner = Read-PinDigest $OwnerPin
        $g.digest_is_live = ($owner -eq $live)                                      # (a)
        $g.admin_only_write = Test-AdminOnlyWrite $OwnerPin                         # (b)
        $commit = ""
        try { $commit = [string](Get-Content -LiteralPath $OwnerPin -Raw | ConvertFrom-Json).commit } catch { }
        $g.commit_in_live = $false
        if ($commit -match '^[0-9a-f]{40}$') {
            & git -C $RepoRoot merge-base --is-ancestor $commit "origin/$LiveRef" 2>$null
            $g.commit_in_live = ($LASTEXITCODE -eq 0)                               # (c)
        }
        if (-not ($g.digest_is_live -and $g.admin_only_write -and $g.commit_in_live)) {
            Write-HealLedger $row
            return "pin: a guard failed ($(($g.GetEnumerator() | ForEach-Object { "$($_.Key)=$($_.Value)" }) -join ', ')); NOT moved"
        }
        $kept = $null
        if (Test-Path -LiteralPath $RegistryPin) {                                  # (f): stale, kept
            $stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
            $kept = "$RegistryPin.superseded-$stamp"
            $row.superseded = $kept
            $row.superseded_sha256 = Get-Sha $RegistryPin
            $row.superseded_digest = Read-PinDigest $RegistryPin
            Rename-Item -LiteralPath $RegistryPin -NewName ("ROOT_PIN.json.superseded-" + $stamp)
        }
        Copy-Item -LiteralPath $OwnerPin -Destination $RegistryPin                  # (g): source stays
        & icacls $RegistryPin /inheritance:r /grant:r "*S-1-5-32-544:F" "*S-1-5-18:F" "*S-1-5-32-545:R" | Out-Null
        $row.destination_sha256 = Get-Sha $RegistryPin
        $row.equal = ($row.destination_sha256 -eq $src)                             # (e)
        if (-not $row.equal) {                                                      # put the old pin back
            Remove-Item -LiteralPath $RegistryPin -Force -ErrorAction SilentlyContinue
            if ($kept) { Rename-Item -LiteralPath $kept -NewName "ROOT_PIN.json"; $row.restored = $kept }
            Write-HealLedger $row
            return "pin: COPY MISMATCH ($src vs $($row.destination_sha256)); the superseded pin was restored"
        }
        Write-HealLedger $row
        return "pin: MOVED the owner pin $($owner.Substring(0,12)) to $RegistryPin (byte copy, sha256 equal)"
    } catch {
        $row.error = $_.Exception.Message; Write-HealLedger $row
        return "pin: UNMEASURED ($($_.Exception.Message)); NOT moved"               # (j)
    }
}

function Invoke-GateCloneReset {
    $clone = Join-Path $QB "gate-repo"
    $log = Join-Path $QB "logs\workflow_gate.log"
    $index = Join-Path $clone ".git\index"
    if (-not (Test-Path -LiteralPath $log)) { return "gate: no gate log" }
    $full = (Resolve-Path -LiteralPath $log).Path
    if ($full.StartsWith($clone + "\", [StringComparison]::OrdinalIgnoreCase)) { return "gate: the log lives inside the clone; not reset" }
    # prune old renamed clones, only once a good checkout has run after them
    if (Test-Path -LiteralPath $index) {
        $good = (Get-Item -LiteralPath $index).LastWriteTimeUtc
        Get-ChildItem -LiteralPath $QB -Directory -Filter "gate-repo.failed-*" -ErrorAction SilentlyContinue |
            Where-Object { $_.CreationTimeUtc -lt (Get-Date).ToUniversalTime().AddDays(-7) -and $_.CreationTimeUtc -lt $good } |
            ForEach-Object { Remove-Item -LiteralPath $_.FullName -Recurse -Force -ErrorAction SilentlyContinue }
    }
    if (-not (Test-Path -LiteralPath $index)) { return "gate: no clone to reset" }
    $last = Get-Content -LiteralPath $log -Tail 400 | Where-Object { $_ -match 'FAILED: ' } | Select-Object -Last 1
    if (-not $last -or $last -notmatch 'sparse-checkout failed') { return "gate: no sparse-checkout jam" }
    $at = [datetime]::MinValue
    if (-not [datetime]::TryParse((($last -split ' ')[0..1] -join ' '), [ref]$at)) { return "gate: unreadable failure time; not reset" }
    if ((Get-Item -LiteralPath $index).LastWriteTimeUtc -ge $at.ToUniversalTime()) { return "gate: a checkout ran after the failure" }
    $recent = $null
    if (Test-Path -LiteralPath $HealLedger) {
        $recent = Get-Content -LiteralPath $HealLedger -Tail 200 | ForEach-Object { try { $_ | ConvertFrom-Json } catch { } } |
            Where-Object { $_.step -eq "gate" -and $_.action -eq "renamed" -and
                           ([datetime]$_.at).ToUniversalTime() -gt (Get-Date).ToUniversalTime().AddHours(-24) } |
            Select-Object -Last 1
    }
    if ($recent) {
        $paged = Get-Content -LiteralPath $HealLedger -Tail 200 | ForEach-Object { try { $_ | ConvertFrom-Json } catch { } } |
            Where-Object { $_.step -eq "gate" -and $_.action -eq "page" -and [datetime]$_.at -gt [datetime]$recent.at }
        if (-not $paged) { Write-HealLedger @{ step = "gate"; action = "page"; failure_at = $at.ToString("o") } }
        return "gate: PAGE: the clone jammed again within 24 h of the reset at $($recent.at); not resetting again"
    }
    $stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
    Rename-Item -LiteralPath $clone -NewName ("gate-repo.failed-" + $stamp)
    if (Test-Path -LiteralPath $clone) { return "gate: jammed clone could NOT be renamed" }
    Write-HealLedger @{ step = "gate"; action = "renamed"; to = "gate-repo.failed-$stamp"; failure_at = $at.ToString("o") }
    return "gate: renamed the jammed clone to gate-repo.failed-$stamp; the next sweep re-clones"
}

function Invoke-BinRefresh([string] $treeDigest) {
    $bin = Join-Path $QB "bin"
    if (-not (Test-Path -LiteralPath $bin)) { return "bin: no bin dir; install_unattended has not run" }
    if (-not $treeDigest) { return "bin: this tree's root digest UNMEASURED; nothing copied" }
    $pin = Read-PinDigest $RegistryPin
    if ($pin -ne $treeDigest) { return "bin: this tree's root is not the registry pin; nothing copied" }
    $done = @()
    foreach ($name in @('unattended_boot.ps1', 'workflow_gate.ps1', 'sign_train_leg.ps1')) {
        $src = Join-Path $RepoRoot ("ops\box\" + $name)
        $dst = Join-Path $bin $name
        if (-not (Test-Path -LiteralPath $src)) { continue }
        $before = if (Test-Path -LiteralPath $dst) { Get-Sha $dst } else { $null }
        if ($before -eq (Get-Sha $src)) { continue }
        Copy-Item -LiteralPath $src -Destination $dst -Force
        $done += [ordered]@{ name = $name; before_sha256 = $before; after_sha256 = (Get-Sha $dst) }
    }
    if ($done) {
        Write-HealLedger @{ step = "bin"; action = "refreshed"; files = $done; root = $treeDigest }
        return "bin: refreshed $(($done | ForEach-Object { $_.name }) -join ', ') from the pinned tree"
    }
    return "bin: copies already match the pinned tree"
}

function Invoke-BoxSelfHeal {
    try {
        $live = Get-LiveRootDigest
        $tree = Get-RevRootDigest "HEAD"
        foreach ($step in @(
                { Invoke-PinRelocation $live },
                { Invoke-GateCloneReset },
                { Invoke-BinRefresh $tree })) {
            try { Log ("selfheal: " + (& $step)) | Out-Host } catch { Log "selfheal: step failed: $($_.Exception.Message)" | Out-Host }
        }
    } catch {
        Log "selfheal: failed: $($_.Exception.Message)" | Out-Host
    }
}
