# Dot-sourced by provision_midnight_lane_clone.ps1 (after it seals) and Run-DeskCycle.ps1 (before
# every Codex pass). One definition of "the midnight lane clone is still sealed", so the check that
# runs at 00:xx is the same one that passed at provisioning.
#
# WHY IT EXISTS (auditor HOLD on PR #439). The Codex sandbox may write INSIDE the clone, but must
# never be able to change what an unsandboxed process trusts there: the clone root and .git
# (rename them and plant a fresh .git, or a whole new folder at the path, since C:\opt grants Users
# AD), .git\config and .git\hooks (fsmonitor, hooksPath, filter drivers), and .git\commondir (git
# reads config from the common dir it names). The -RunAs account runs Codex's parent and git there.

$LaneTrustedSids = @('S-1-5-32-544', 'S-1-5-18')   # BUILTIN\Administrators, SYSTEM

function Get-LaneCloneProblems([string] $Clone, [string[]] $TrustedOwners) {
    $problems = @()
    $git = Join-Path $Clone '.git'
    foreach ($p in @($Clone, $git, (Join-Path $git 'config'), (Join-Path $git 'hooks'))) {
        if (-not (Test-Path -LiteralPath $p)) { $problems += "$p missing"; continue }
    }
    if ($problems) { return $problems }
    foreach ($p in @($Clone, $git)) {
        if ((Get-Item -LiteralPath $p -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
            $problems += "$p is a reparse point"
        }
    }
    $owner = (Get-Acl -LiteralPath $Clone).GetOwner([Security.Principal.SecurityIdentifier]).Value
    if ($TrustedOwners -notcontains $owner) { $problems += "$Clone owned by $owner" }
    if (Test-Path -LiteralPath (Join-Path $git 'commondir')) { $problems += "$git\commondir present" }
    # Codex reads project config from its workspace (.codex\config.toml can name commands, e.g. MCP
    # servers, that the UNSANDBOXED parent starts). The repo tracks none, so any is a plant.
    if (Test-Path -LiteralPath (Join-Path $Clone '.codex')) { $problems += "$Clone\.codex present" }

    # Rights that let a principal rename, delete, rewrite or re-permission the object itself.
    $R = [Security.AccessControl.FileSystemRights]
    $bad = $R::WriteData -bor $R::AppendData -bor $R::WriteExtendedAttributes -bor
           $R::WriteAttributes -bor $R::Delete -bor $R::DeleteSubdirectoriesAndFiles -bor
           $R::ChangePermissions -bor $R::TakeOwnership
    # Root and .git: untrusted principals may add entries (git writes index.lock and HEAD there)
    # and hold Modify inherit-only for the children, but never delete, re-permission or re-own
    # the folder itself. config and hooks: untrusted principals may not hold write at all.
    $folderBad = $R::Delete -bor $R::DeleteSubdirectoriesAndFiles -bor $R::ChangePermissions -bor
                 $R::TakeOwnership -bor $R::WriteAttributes -bor $R::WriteExtendedAttributes
    $checks = @(
        @{ Path = $Clone; AllowInheritOnly = $true },
        @{ Path = $git; AllowInheritOnly = $true },
        @{ Path = (Join-Path $git 'config'); AllowInheritOnly = $false },
        @{ Path = (Join-Path $git 'hooks'); AllowInheritOnly = $false }
    )
    foreach ($c in $checks) {
        $acl = Get-Acl -LiteralPath $c.Path
        foreach ($ace in $acl.GetAccessRules($true, $true, [Security.Principal.SecurityIdentifier])) {
            if ($ace.AccessControlType -ne 'Allow') { continue }
            if ($LaneTrustedSids -contains $ace.IdentityReference.Value) { continue }
            $inheritOnly = ($ace.PropagationFlags -band [Security.AccessControl.PropagationFlags]::InheritOnly) -ne 0
            if ($c.AllowInheritOnly -and $inheritOnly) { continue }
            $forbidden = if ($c.AllowInheritOnly) { $folderBad } else { $bad }
            if (($ace.FileSystemRights -band $forbidden) -eq 0) { continue }
            $problems += ("{0}: {1} holds {2}" -f $c.Path, $ace.IdentityReference.Value, $ace.FileSystemRights)
        }
    }
    return $problems
}
