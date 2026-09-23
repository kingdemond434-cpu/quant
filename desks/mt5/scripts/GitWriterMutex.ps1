# THE ONE LOCK EVERY GIT WRITER ON THIS BOX TAKES -- created so that every writer can actually
# open it, whoever created it first.
#
# MEASURED 2026-09-23, twice, and the second measurement is why this file names a NEW lock.
#
# First: `MT5-AdoptRelease` had been refusing every hour since 2026-09-19 with
#
#   could not OPEN Local\MT5-GitWriter (MethodInvocationException: Exception calling ".ctor" with
#   "2" argument(s): "Access to the path 'Local\MT5-GitWriter' is denied.")
#
# A named mutex created by a process under one principal gets that principal's DEFAULT security
# descriptor, and a later writer under a different principal (a SYSTEM task, an S4U task, an SSH
# session) cannot open it at all. Every adoption declined, nothing shipped reached the box for
# four days, and the gateway ran code from before the live-policy work.
#
# Second: creating the SAME name with a permissive descriptor does not fix it either --
#
#   could not OPEN Local\MT5-GitWriter (create: ... "Access to the path ... is denied" |
#   open(Synchronize, Modify): UnauthorizedAccessException | open(Synchronize): ...)
#
# because the kernel object ALREADY EXISTS with the old descriptor and a live handle keeps it
# alive; a create call on an existing name is an open call, and the DACL on the object decides,
# not the one you pass. The name is unusable until every legacy holder exits, which on a box whose
# git never goes idle is never.
#
# So the lock MOVES: `Global\MT5-GitWriter-v2` (then `Local\MT5-GitWriter-v2` where the Global
# namespace is not available), created with a DACL the whole machine can open. The legacy name is
# still taken BEST EFFORT, so a writer running old code is still coordinated with while it lasts,
# and a legacy name that cannot be opened is a note, never a refusal. It is a synchronisation name
# on one box, not a secret: the only thing another local process can do with it is wait, which is
# exactly what every legitimate writer already does.
#
#   . (Join-Path $PSScriptRoot "GitWriterMutex.ps1")
#   $h = Open-GitWriterMutex
#   if ($null -eq $h.Mutex) { Log ("could not OPEN " + $h.Name + " (" + $h.Why + ")"); exit 6 }

function New-PermissiveMutexSecurity {
    $world = New-Object System.Security.Principal.SecurityIdentifier(
        [System.Security.Principal.WellKnownSidType]::WorldSid, $null)
    $rule = New-Object System.Security.AccessControl.MutexAccessRule(
        $world,
        [System.Security.AccessControl.MutexRights]::FullControl,
        [System.Security.AccessControl.AccessControlType]::Allow)
    $sec = New-Object System.Security.AccessControl.MutexSecurity
    $sec.AddAccessRule($rule)
    return $sec
}

function Open-OneMutex {
    param([string] $Name)
    try {
        $created = $false
        $m = New-Object System.Threading.Mutex($false, $Name, [ref] $created,
                                               (New-PermissiveMutexSecurity))
        return @{ Mutex = $m; Why = ""; Name = $Name; Created = $created }
    } catch {
        $why = "create(" + $Name + "): " + $_.Exception.GetType().Name
    }
    foreach ($rights in @(
        ([System.Security.AccessControl.MutexRights]::Synchronize -bor
         [System.Security.AccessControl.MutexRights]::Modify),
        [System.Security.AccessControl.MutexRights]::Synchronize)) {
        try {
            $m = [System.Threading.Mutex]::OpenExisting($Name, $rights)
            return @{ Mutex = $m; Why = ""; Name = $Name; Created = $false }
        } catch {
            $why = $why + " | open(" + $rights + "): " + $_.Exception.GetType().Name
        }
    }
    return @{ Mutex = $null; Why = $why; Name = $Name; Created = $false }
}

function Open-GitWriterMutex {
    param(
        [string[]] $Names = @("Global\MT5-GitWriter-v2", "Local\MT5-GitWriter-v2"),
        [string] $LegacyName = "Local\MT5-GitWriter",
        [int] $LegacyWaitMs = 30000)

    $why = ""
    foreach ($name in $Names) {
        $h = Open-OneMutex -Name $name
        if ($null -ne $h.Mutex) {
            # BEST EFFORT on the legacy name: a writer still running the old code coordinates on
            # it, and a name we cannot open is a NOTE, never a refusal (that confusion is what
            # wedged this box for four days).
            $legacy = Open-OneMutex -Name $LegacyName
            $h.LegacyMutex = $null
            $h.LegacyWhy = $legacy.Why
            if ($null -ne $legacy.Mutex) {
                try {
                    if ($legacy.Mutex.WaitOne($LegacyWaitMs)) { $h.LegacyMutex = $legacy.Mutex }
                    else { $h.LegacyWhy = "legacy held by another writer; proceeding on $name" }
                } catch [System.Threading.AbandonedMutexException] {
                    $h.LegacyMutex = $legacy.Mutex
                }
            }
            return $h
        }
        $why = $why + " " + $h.Why
    }
    return @{ Mutex = $null; Why = $why.Trim(); Name = ($Names -join ","); Created = $false }
}

function Close-GitWriterMutex {
    param($Handle)
    if ($null -eq $Handle) { return }
    foreach ($key in @("LegacyMutex", "Mutex")) {
        $m = $Handle[$key]
        if ($null -ne $m) {
            try { $m.ReleaseMutex() } catch { }
            try { $m.Dispose() } catch { }
        }
    }
}
