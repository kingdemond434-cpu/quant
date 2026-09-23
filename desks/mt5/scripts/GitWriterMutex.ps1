# THE ONE LOCK EVERY GIT WRITER ON THIS BOX TAKES -- created so that every writer can actually
# open it, whoever created it first.
#
# MEASURED 2026-09-23. `MT5-AdoptRelease` had been refusing every hour since 2026-09-19 with
#
#   could not OPEN Local\MT5-GitWriter (MethodInvocationException: Exception calling ".ctor" with
#   "2" argument(s): "Access to the path 'Local\MT5-GitWriter' is denied.")
#
# The refusal was correct and the desk was still stuck: a named mutex created by a process running
# under one principal gets the creator's DEFAULT security descriptor, and a later writer under a
# different principal (SYSTEM task vs S4U task vs an SSH session) cannot open it at all. Every
# adoption then declined, nothing shipped reached the box for four days, and the gateway ran code
# from before the live-policy work.
#
# The fix is not a second lock and not a weaker check: it is to CREATE the mutex with a security
# descriptor that grants the whole machine full control, so the name means "a git writer is
# working" to every principal instead of "the creator's principal is working". Dot-source this
# file and call Open-GitWriterMutex; it returns the mutex (or $null with a REASON that is measured,
# never invented).
#
#   . (Join-Path $PSScriptRoot "GitWriterMutex.ps1")
#   $h = Open-GitWriterMutex
#   if ($null -eq $h.Mutex) { Log ("could not OPEN " + $h.Name + " (" + $h.Why + ")"); exit 6 }

function Open-GitWriterMutex {
    param([string] $Name = "Local\MT5-GitWriter")

    $why = ""
    # 1. CREATE (or open) with an explicit DACL granting Everyone full control over the mutex.
    #    This is a synchronisation name on one box, not a secret: the only thing a hostile local
    #    process could do with it is wait, which is what every legitimate writer already does.
    try {
        $world = New-Object System.Security.Principal.SecurityIdentifier(
            [System.Security.Principal.WellKnownSidType]::WorldSid, $null)
        $rule = New-Object System.Security.AccessControl.MutexAccessRule(
            $world,
            [System.Security.AccessControl.MutexRights]::FullControl,
            [System.Security.AccessControl.AccessControlType]::Allow)
        $sec = New-Object System.Security.AccessControl.MutexSecurity
        $sec.AddAccessRule($rule)
        $created = $false
        $m = New-Object System.Threading.Mutex($false, $Name, [ref] $created, $sec)
        return @{ Mutex = $m; Why = ""; Name = $Name; Created = $created }
    } catch {
        $why = "create: " + $_.Exception.GetType().Name + ": " + $_.Exception.Message
    }

    # 2. The name already exists under an old restrictive descriptor (a writer that started before
    #    this file landed). SYNCHRONIZE alone is often grantable where MODIFY is not, and
    #    SYNCHRONIZE is all WaitOne needs.
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
