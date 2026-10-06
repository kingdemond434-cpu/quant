# GitBoxEnv.ps1 -- the git environment an UNATTENDED box writer needs, set once per process.
#
# MEASURED 2026-10-06 (read-only census on vmi3571445, 15:43Z). No box-authored state had reached
# origin since 2026-09-24, and sync_shadow_to_git.log named three separate causes in one day:
#
#   1. OWNERSHIP. C:\opt\quant is owned by BUILTIN\Administrators while the task runs as
#      VMI3571445\Administrator, so every plain git call refuses with "detected dubious ownership".
#      From 14:05 every slot ended "git add failed rc=128". The installer's SYSTEM safe.directory
#      line (install_adopt_release_task.ps1) only lands when that installer is re-run.
#   2. NO NON-INTERACTIVE CREDENTIAL. At 13:36 the push failed three times with "Cannot prompt
#      because user interactivity has been disabled" / "unable to get password": a scheduled task
#      has no one to answer the credential manager, so it waited on a prompt that cannot appear.
#   3. A CRASHING COMMIT. At 13:54 `git commit` died with rc=-1073741819 (0xC0000005, access
#      violation) -- handled by the caller's retry, not here.
#
# WHAT THIS DOES, AND ONLY THIS. It puts git config into the PROCESS environment
# (GIT_CONFIG_COUNT / GIT_CONFIG_KEY_n / GIT_CONFIG_VALUE_n), which git reads as COMMAND-scope
# configuration -- a protected scope, so `safe.directory` is honoured there -- and which every
# child git inherits, hooks included. Nothing is written to any config file, and nothing outlives
# the process.
#
#   * safe.directory = this repository, exactly (never "*").
#   * Prompts off: GIT_TERMINAL_PROMPT=0 and GCM_INTERACTIVE=never, so a missing credential FAILS
#     at once and is named, instead of hanging a task slot on a dialog nobody can see.
#   * GITHUB_TOKEN, when the machine has one (`setx /M GITHUB_TOKEN ...`, the principal's step),
#     becomes an Authorization header scoped to https://github.com/. The token is never logged,
#     never echoed, never put on a command line and never written to disk by this file.
#
# No token is not an error here: a box with a working credential-manager entry for a service
# account still pushes. The caller learns the outcome from the push itself (Test-GitAuthFailure)
# and reports BLOCKED_AUTH, a named state, rather than a bare rc=1.

function Add-GitConfigEnv {
    param([string]$Key, [string]$Value)
    $n = 0
    if ($env:GIT_CONFIG_COUNT) { [void][int]::TryParse($env:GIT_CONFIG_COUNT, [ref]$n) }
    Set-Item -Path ("Env:GIT_CONFIG_KEY_{0}" -f $n) -Value $Key
    Set-Item -Path ("Env:GIT_CONFIG_VALUE_{0}" -f $n) -Value $Value
    $env:GIT_CONFIG_COUNT = "{0}" -f ($n + 1)
}

function Get-BoxGitHubToken {
    # Process first (a hand run that set it), then Machine (`setx /M`, what the task sees), then
    # User. Returns the value only to the caller; never prints it.
    foreach ($scope in @("Process", "Machine", "User")) {
        $t = [Environment]::GetEnvironmentVariable("GITHUB_TOKEN", $scope)
        if ($t -and $t.Trim()) { return $t.Trim() }
    }
    return $null
}

function Initialize-BoxGitEnv {
    param([string]$RepoRoot)
    $env:GIT_TERMINAL_PROMPT = "0"
    $env:GCM_INTERACTIVE = "never"
    $safe = ($RepoRoot -replace '\\', '/').TrimEnd('/')
    Add-GitConfigEnv -Key "safe.directory" -Value $safe
    $token = Get-BoxGitHubToken
    if ($token) {
        $basic = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("x-access-token:$token"))
        Add-GitConfigEnv -Key "http.https://github.com/.extraheader" -Value "AUTHORIZATION: basic $basic"
        return [pscustomobject]@{ SafeDirectory = $safe; Auth = "GITHUB_TOKEN" }
    }
    return [pscustomobject]@{ SafeDirectory = $safe; Auth = "CREDENTIAL_MANAGER_ONLY" }
}

# The lines git and Git Credential Manager print when a push needed a credential it could not get.
$script:GitAuthFailurePatterns = @(
    "Cannot prompt because user interactivity has been disabled",
    "unable to get password",
    "could not read Username",
    "could not read Password",
    "terminal prompts disabled",
    "Authentication failed",
    "Invalid username or (password|token)",
    "Permission to \S+ denied",
    "returned error: 40[13]"
)

function Test-GitAuthFailure {
    param([string[]]$Lines)
    foreach ($l in @($Lines)) {
        foreach ($p in $script:GitAuthFailurePatterns) {
            if ("$l" -match $p) { return $true }
        }
    }
    return $false
}
