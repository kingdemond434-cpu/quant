# Test-GitAclSealed (boot r24 r6, Audit MF1 on r5). quantrun has Modify on C:\opt\quant, and SYSTEM
# git reads that tree's .git: if quantrun could rename .git, rewrite .git\config, re-ACL either, or
# plant .git\commondir / config.worktree, a filter, sshCommand, credential helper or include in
# that config would run inside SYSTEM git. This answers, from the ACLs alone, whether it can:
#   - .git and .git\config are owned by Administrators or SYSTEM;
#   - quantrun (directly or via Users/Everyone/Authenticated Users/INTERACTIVE/BATCH/SERVICE) has
#     no Delete, ChangePermissions or TakeOwnership on .git, no write/append/Delete/re-ACL on
#     .git\config, and no DeleteSubdirectoriesAndFiles on the tree root, after quantrun's own
#     explicit deny ACEs;
#   - neither .git\commondir nor .git\config.worktree exists.
# Returns the list of reasons it is NOT sealed (empty = sealed). Dot-sourced by the pinned
# Adopt-And-Seal (from the guard checkout) and by the pinned migrator (guard\runas copy).
function Test-GitAclSealed {
    param([Parameter(Mandatory)] [string] $RepoRoot, [string] $RunUser = 'quantrun')
    $okOwner = '^(BUILTIN\\Administrators|NT AUTHORITY\\SYSTEM)$'
    $who = "(?i)(\\$RunUser$|^Everyone$|\\Users$|\\Authenticated Users$|\\INTERACTIVE$|\\BATCH$|\\SERVICE$)"
    $F = [Security.AccessControl.FileSystemRights]
    $gitDir = Join-Path $RepoRoot '.git'
    $checks = @(
        @{ Path = $gitDir; Owner = $true
           Risky = [int]($F::Delete -bor $F::ChangePermissions -bor $F::TakeOwnership) },
        @{ Path = (Join-Path $gitDir 'config'); Owner = $true
           Risky = [int]($F::WriteData -bor $F::AppendData -bor $F::Delete -bor $F::ChangePermissions -bor $F::TakeOwnership) },
        @{ Path = $RepoRoot; Owner = $false; Risky = [int]$F::DeleteSubdirectoriesAndFiles }
    )
    $why = @()
    foreach ($c in $checks) {
        $acl = $null
        try { $acl = Get-Acl -LiteralPath $c.Path -ErrorAction Stop } catch { $why += "$($c.Path): ACL unreadable"; continue }
        if ($c.Owner -and "$($acl.Owner)" -notmatch $okOwner) { $why += "$($c.Path): owner is $($acl.Owner)" }
        $allow = 0; $deny = 0
        foreach ($r in $acl.Access) {
            $id = "$($r.IdentityReference)"
            if ($id -notmatch $who) { continue }
            if ($r.PropagationFlags -band [Security.AccessControl.PropagationFlags]::InheritOnly) { continue }
            $bits = [int]$r.FileSystemRights
            if ($bits -band 0x50000000) { $bits = $bits -bor $c.Risky }   # GENERIC_ALL / GENERIC_WRITE
            if ("$($r.AccessControlType)" -eq 'Deny') {
                # only quantrun's own explicit denies are counted: explicit deny outranks any allow
                if ($id -match "(?i)\\$RunUser$" -and -not $r.IsInherited) { $deny = $deny -bor $bits }
            } else { $allow = $allow -bor $bits }
        }
        $left = $allow -band $c.Risky -band (-bnot $deny)
        if ($left) { $why += ("{0}: {1} may {2}" -f $c.Path, $RunUser, [Security.AccessControl.FileSystemRights]$left) }
    }
    foreach ($n in @('commondir', 'config.worktree')) {
        if (Test-Path -LiteralPath (Join-Path $gitDir $n)) { $why += "$gitDir\$n exists" }
    }
    return ,$why
}
