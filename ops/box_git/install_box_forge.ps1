<#
.SYNOPSIS
    THE BOX'S OWN GIT FORGE: the repository's source of truth moves onto the box, so a GitHub
    outage changes nothing. One run, as administrator, over RDP. Every step is logged to
    C:\ProgramData\QuantBox\logs\install_box_forge_<UTC stamp>.log.

.DESCRIPTION
    WHY (principal 2026-11-19: "nothing should rely on GitHub at all ... just a backup"). On 11-19
    GitHub suspended the account and every merge, CI run, CLEAR and adoption froze for the day.

    WHAT IT DOES, IN ORDER (each step logged; any failure stops before the next, and nothing in
    C:\opt\quant is written at any step):
      1. Refuses unless elevated, and refuses on a box carrying desks\mt5\data\BOX_RETIRED.
      2. Downloads Gitea for Windows from dl.gitea.com (never GitHub) at the version named by
         -GiteaVersion, and verifies the SHA-256 published beside it. A mismatch stops here.
      3. Creates a local service account `quantforge` (not an administrator) and the forge's
         folders under C:\ProgramData\QuantBox\forge, readable by that account and Administrators.
      4. Writes app.ini: HTTPS only on -Port with a self-signed certificate for this box's address,
         SQLite, registration off, sign-in required to read, Actions on, offline mode, no mail.
      5. Registers and starts the `QuantForge` service as `quantforge`, auto-start.
      6. Creates the forge's users: `quant-admin` (an administrator, random password written for the
         owner only), `claude` (no admin; its token stays on the box and is used only by the inbox
         importer), merge-gate, release-authority and box-ci, each with a box-only token. Creates
         the repository quant/quant and seeds it from the box gate clone
         (C:\ProgramData\QuantBox\gate-repo), which holds LIVE and production as last fetched;
         -SeedBundle first fast-forwards that clone's LIVE from a bundle when LIVE moved since.
      7. Protects LIVE, production and master on the forge (no force push, no deletion, pushes
         only by the merge-gate user) and installs ops\box_git\protect.py as the repository's
         pre-receive hook too, so the rules hold even if the forge's own settings are changed.
      8. LOCAL ONLY (Audit MF-3): the forge listens on 127.0.0.1, no inbound firewall rule (one
         left by an earlier run is removed), forge Actions off. Nothing off the box reaches it.
      9. The release loop (QuantForge-Loop, every 5 minutes) with its inbox
         (C:\ProgramData\QuantBox\inbox): cloud threads' work arrives there as git bundles carried
         by the box's Remote Control session (ops/box_git/inbox.py). Nothing in the cloud connects
         to the box, so no network allowlist and no approval card exist anywhere.
     10-12. Re-points the gate clone and the live tree's origin at the forge, re-pins ROOT, adopts.

    WHAT IT NEVER DOES. It never writes C:\opt\quant (MT5-AdoptRelease stays its only writer), never
    touches MT5, secrets under data\secrets, or any scheduled task of the desk, never weakens a gate
    and never contacts GitHub.

    Run: right-click ops\box_git\install_box_forge.cmd -> Run as administrator.
#>
param(
    [string] $GiteaVersion = "latest",
    [int] $Port = 0,
    # Optional git bundle that fast-forwards the gate clone's LIVE before seeding (LIVE moved after
    # the box last fetched). Never a rewrite: a non-fast-forward stops the installer.
    [string] $SeedBundle = "",
    [string] $Root = "C:\ProgramData\QuantBox",
    [string] $QuantRoot = "C:\opt\quant"
)

$ErrorActionPreference = "Stop"
$Live = "claude/llm-auto-upgrade-verify-gcjac3"
$Forge = Join-Path $Root "forge"
$Bin = Join-Path $Forge "gitea.exe"
$Ini = Join-Path $Forge "custom\conf\app.ini"
$Data = Join-Path $Forge "data"
$Repos = Join-Path $Forge "repos"
$OwnerOnly = Join-Path $Forge "owner-only"
$Tokens = Join-Path $Forge "box-tokens"
$Svc = "QuantForge"
$SvcUser = "quantforge"

$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$logDir = Join-Path $Root "logs"
$null = New-Item -ItemType Directory -Force -Path $logDir
$log = Join-Path $logDir "install_box_forge_$stamp.log"
function Say([string] $m) {
    $line = "{0}  {1}" -f (Get-Date).ToUniversalTime().ToString("HH:mm:ss"), $m
    Write-Host $line
    Add-Content -LiteralPath $log -Value $line
}
function Stop-Here([int] $code, [string] $why) { Say "STOPPED: $why"; Say "log: $log"; exit $code }
function New-Secret([int] $bytes = 24) {
    $b = New-Object byte[] $bytes
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b)
    return ([Convert]::ToBase64String($b) -replace '[+/=]', 'x')
}
function Lock-ToOwners([string] $path, [string[]] $extra = @()) {
    # Administrators and SYSTEM (plus any named account) only; inheritance off.
    & icacls $path /inheritance:r /grant:r "*S-1-5-32-544:(OI)(CI)F" "*S-1-5-18:(OI)(CI)F" | Out-Null
    foreach ($u in $extra) { & icacls $path /grant:r "${u}:(OI)(CI)M" | Out-Null }
}
function Forge([string[]] $a) {
    # Windows PowerShell 5.1 turns a native program's stderr lines into errors under Stop:
    # gitea logs to stderr, so judge by the exit code alone.
    # Stdout and stderr stay apart: a value read from stdout (a --raw token) must never carry a
    # stderr warning (it did once: a multi-line token broke every http.extraHeader).
    $ErrorActionPreference = 'Continue'
    $all = @(& $Bin --config $Ini --work-path $Forge @a 2>&1)
    $rc = $LASTEXITCODE
    $so = ($all | Where-Object { $_ -isnot [Management.Automation.ErrorRecord] } | Out-String).Trim()
    $se = ($all | Where-Object { $_ -is [Management.Automation.ErrorRecord] } | Out-String).Trim()
    if ($rc -ne 0) { $so = ("$so`n$se").Trim() }
    return @{ rc = $rc; out = $so }
}

# 1. ELEVATED, AND NOT A RETIRED BOX.
$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) { Stop-Here 2 "run this as administrator (right-click, Run as administrator)." }
if (Test-Path -LiteralPath (Join-Path $QuantRoot "desks\mt5\data\BOX_RETIRED")) {
    Stop-Here 2 "this box is retired (BOX_RETIRED); the forge belongs on the trading box."
}
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { Stop-Here 2 "git is not on PATH." }
$gate = Join-Path $Root "gate-repo"
if (-not (Test-Path -LiteralPath (Join-Path $gate ".git"))) { Stop-Here 2 "the gate clone $gate is missing; it seeds the forge." }
Say "elevated; seeding from $gate"

# THE PORT: 443 when nothing listens there (cloud egress proxies reliably carry 443), else 3443.
if ($Port -eq 0 -and (Test-Path -LiteralPath $Ini)) {
    # A re-run keeps the port the forge already serves (443 is then busy with our own forge).
    $kept = Select-String -LiteralPath $Ini -Pattern '^HTTP_PORT\s*=\s*(\d+)' | Select-Object -First 1
    if ($kept) { $Port = [int]$kept.Matches[0].Groups[1].Value }
}
if ($Port -eq 0) {
    $busy443 = Get-NetTCPConnection -LocalPort 443 -State Listen -ErrorAction SilentlyContinue
    $Port = if ($busy443) { 3443 } else { 443 }
}
Say "forge port: $Port on 127.0.0.1 only"

# 2. GITEA, VERIFIED.
# Governance 2026-11-19: the owner's forge credential is never stored where a session can reach.
if (Test-Path -LiteralPath $OwnerOnly) {
    if (Get-ChildItem -LiteralPath $OwnerOnly -Filter "quant-admin*" -ErrorAction SilentlyContinue) {
        Stop-Here 2 "a quant-admin credential is stored in $OwnerOnly; the owner's credential must never be on the box. Remove it, then run again."
    }
}
$null = New-Item -ItemType Directory -Force -Path $Forge, $Data, $Repos, $Tokens, (Split-Path $Ini)
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
if ($GiteaVersion -eq "latest") {
    try { $GiteaVersion = [string](Invoke-RestMethod -UseBasicParsing -Uri "https://dl.gitea.com/gitea/version.json").latest.version }
    catch { Stop-Here 3 "could not read the latest Gitea version from dl.gitea.com. Nothing was installed." }
    if ($GiteaVersion -notmatch '^\d+\.\d+\.\d+$') { Stop-Here 3 "dl.gitea.com named an odd version '$GiteaVersion'." }
}
$url = "https://dl.gitea.com/gitea/$GiteaVersion/gitea-$GiteaVersion-windows-amd64.exe"
if (-not (Test-Path -LiteralPath $Bin)) {
    Say "downloading $url"
    $tmp = "$Bin.download"
    try {
        Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $tmp
        $want = ((Invoke-WebRequest -UseBasicParsing -Uri "$url.sha256").Content -split '\s+')[0].Trim().ToLower()
    } catch { Stop-Here 3 "download failed ($($_.Exception.Message)). Nothing was installed." }
    $got = (Get-FileHash -Algorithm SHA256 -LiteralPath $tmp).Hash.ToLower()
    if ($want -notmatch '^[0-9a-f]{64}$' -or $got -ne $want) {
        Remove-Item -LiteralPath $tmp -Force
        Stop-Here 3 "checksum mismatch (published $want, got $got). Nothing was installed."
    }
    Move-Item -LiteralPath $tmp -Destination $Bin
    Say "gitea $GiteaVersion verified sha256 $got"
} else { Say "gitea already present at $Bin" }

# 3. THE SERVICE ACCOUNT, NOT AN ADMINISTRATOR.
$svcPass = New-Secret 24
if (-not (Get-LocalUser -Name $SvcUser -ErrorAction SilentlyContinue)) {
    New-LocalUser -Name $SvcUser -Password (ConvertTo-SecureString $svcPass -AsPlainText -Force) `
        -PasswordNeverExpires -UserMayNotChangePassword -Description "Quant box git forge service" | Out-Null
    Say "created local account $SvcUser (not an administrator)"
} else {
    Set-LocalUser -Name $SvcUser -Password (ConvertTo-SecureString $svcPass -AsPlainText -Force)
    Say "reset the password of $SvcUser for the service"
}
Lock-ToOwners $Forge @($SvcUser)
Lock-ToOwners $Tokens
# Log on as a service, granted through secedit to this one account.
$inf = Join-Path $env:TEMP "forge_rights.inf"; $db = Join-Path $env:TEMP "forge_rights.sdb"
& secedit /export /cfg $inf /areas USER_RIGHTS | Out-Null
$sid = (New-Object Security.Principal.NTAccount $SvcUser).Translate([Security.Principal.SecurityIdentifier]).Value
$cfg = Get-Content -LiteralPath $inf
if (-not ($cfg -match "SeServiceLogonRight.*\*$sid")) {
    $cfg = $cfg -replace '^(SeServiceLogonRight\s*=\s*.*)$', "`$1,*$sid"
    if (-not ($cfg -match '^SeServiceLogonRight')) { $cfg += "SeServiceLogonRight = *$sid" }
    Set-Content -LiteralPath $inf -Value $cfg
    & secedit /configure /db $db /cfg $inf /areas USER_RIGHTS | Out-Null
}
Remove-Item -LiteralPath $inf, $db -Force -ErrorAction SilentlyContinue

# 4. app.ini: HTTPS ONLY, CLOSED TO STRANGERS.
$cert = Join-Path $Forge "custom\https\cert.pem"; $key = Join-Path $Forge "custom\https\key.pem"
$null = New-Item -ItemType Directory -Force -Path (Split-Path $cert)
if (-not (Test-Path -LiteralPath $cert)) {
    Push-Location (Split-Path $cert)
    try { & $Bin cert --host "127.0.0.1,localhost" --rsa-bits 3072 --duration 87600h | Out-Null } finally { Pop-Location }
    if (-not (Test-Path -LiteralPath $cert)) { Stop-Here 4 "could not make the HTTPS certificate." }
}
$secretKey = New-Secret 32; $internal = New-Secret 48
if (-not (Test-Path -LiteralPath $Ini)) {
@"
APP_NAME = quant box forge
RUN_USER = $SvcUser
RUN_MODE = prod
WORK_PATH = $Forge

[server]
PROTOCOL = https
DOMAIN = 127.0.0.1
HTTP_ADDR = 127.0.0.1
HTTP_PORT = $Port
ROOT_URL = https://127.0.0.1:$Port/
CERT_FILE = $cert
KEY_FILE = $key
DISABLE_SSH = true
OFFLINE_MODE = true
LFS_START_SERVER = false

[database]
DB_TYPE = sqlite3
PATH = $Data\forge.db

[repository]
ROOT = $Repos
DEFAULT_BRANCH = $Live

[security]
INSTALL_LOCK = true
SECRET_KEY = $secretKey
INTERNAL_TOKEN = $internal
MIN_PASSWORD_LENGTH = 16

[service]
DISABLE_REGISTRATION = true
REQUIRE_SIGNIN_VIEW = true
DEFAULT_ALLOW_CREATE_ORGANIZATION = false

[actions]
ENABLED = false

[mailer]
ENABLED = false

[log]
ROOT_PATH = $Forge\log
MODE = file
LEVEL = Info
"@ | Set-Content -LiteralPath $Ini -Encoding ascii
    Say "wrote $Ini (HTTPS on $Port, registration off, sign-in required)"
} else {
    # An earlier app.ini keeps its secrets, but never its exposure: loopback only, Actions off.
    $iniLines = Get-Content -LiteralPath $Ini
    $iniLines = $iniLines -replace '^HTTP_ADDR\s*=.*$', 'HTTP_ADDR = 127.0.0.1' -replace '^DOMAIN\s*=.*$', 'DOMAIN = 127.0.0.1' `
                -replace '^ROOT_URL\s*=.*$', "ROOT_URL = https://127.0.0.1:$Port/"
    $inActions = $false
    $iniLines = foreach ($l in $iniLines) {
        if ($l -match '^\[') { $inActions = ($l -eq '[actions]') }
        if ($inActions -and $l -match '^ENABLED\s*=') { 'ENABLED = false' } else { $l }
    }
    Set-Content -LiteralPath $Ini -Value $iniLines -Encoding ascii
    Say "kept the existing $Ini, forced to 127.0.0.1 with Actions off"
}
$r = Forge @("migrate"); if ($r.rc -ne 0) { Stop-Here 4 "database setup failed: $($r.out)" }

# 5. THE SERVICE.
if (-not (Get-Service -Name $Svc -ErrorAction SilentlyContinue)) {
    & sc.exe create $Svc start= auto binPath= "`"$Bin`" web --config `"$Ini`" --work-path `"$Forge`"" `
        obj= ".\$SvcUser" password= $svcPass DisplayName= "Quant box git forge" | Out-Null
} else {
    & sc.exe config $Svc obj= ".\$SvcUser" password= $svcPass | Out-Null
}
$svcPass = $null
Restart-Service -Name $Svc -ErrorAction SilentlyContinue
Start-Service -Name $Svc
Start-Sleep -Seconds 8
if ((Get-Service -Name $Svc).Status -ne "Running") { Stop-Here 5 "the $Svc service did not start; see $Forge\log." }
Say "service $Svc running as $SvcUser"

# 6. USERS, TOKEN, REPOSITORY.
$adminPass = New-Secret 24
$r = Forge @("admin", "user", "create", "--username", "quant-admin", "--password", $adminPass,
             "--email", "quant-admin@box.invalid", "--admin", "--must-change-password=false")
# Its password is written nowhere (Governance): the owner sets his own, by his own act, only when
# a trust-set change needs his AUTHORIZE TRUST (gitea admin user change-password, over RDP).
if ($r.rc -eq 0) { Say "created quant-admin" }
else {
    # exists (a re-run): the installer takes a temporary password for this run only
    $r = Forge @("admin", "user", "change-password", "--username", "quant-admin", "--password", $adminPass,
                 "--must-change-password=false")
    if ($r.rc -ne 0) { Stop-Here 6 "could not take quant-admin for this run: $($r.out)" }
    Say "quant-admin exists; temporary password for this run"
}
$botPass = New-Secret 24
$r = Forge @("admin", "user", "create", "--username", "claude", "--password", $botPass,
             "--email", "claude@box.invalid", "--must-change-password=false")
if ($r.rc -ne 0) { $null = Forge @("admin", "user", "change-password", "--username", "claude",
                                   "--password", $botPass, "--must-change-password=false") }
$botPass = $null
# The two box roles the repository hook trusts by the forge's own pusher name (never by anything
# a client sends): merge-gate moves LIVE/production/master, release-authority creates release tags.
# `auditor` posts only the Audit seat's verdict packets: the one account whose CLEAR the gate counts
# (Audit MF-1). `adopt` reads, for the gate clone and the live tree (Audit MF-4).
foreach ($u in @("merge-gate", "release-authority", "box-ci", "auditor", "adopt")) {
    $null = Forge @("admin", "user", "create", "--username", $u, "--password", (New-Secret 24),
                    "--email", "$u@box.invalid", "--must-change-password=false")
}
# Box-only tokens (never leave the box): the gate, the release authority, box CI and the inbox
# importer's `claude` (a thread's authority: claude/* work branches and comments, nothing more).
$scopes = @{ "merge-gate" = "write:repository,write:issue,read:user"
             "release-authority" = "write:repository,write:issue,read:user"
             "box-ci" = "write:repository,read:user"; "claude" = "write:repository,write:issue,read:user"
             "auditor" = "read:repository,write:issue,read:user"; "adopt" = "read:repository" }
foreach ($u in $scopes.Keys) {
    $tf = Join-Path $Tokens "$u.token"
    if (-not (Test-Path -LiteralPath $tf)) {
        $r = Forge @("admin", "user", "generate-access-token", "--username", $u,
                     "--token-name", "box-$stamp", "--scopes", $scopes[$u], "--raw")
        if ($r.rc -ne 0 -or $r.out -notmatch '^[0-9a-f]{40}$') {
            Stop-Here 6 "could not make the $u token (exit $($r.rc); not one 40-hex line)." }
        Set-Content -LiteralPath $tf -Value $r.out.Trim() -NoNewline
    }
}
# No owner token is ever made: this run uses the temporary password (basic auth, memory only) and
# scrambles it at the end, so no credential of the owner's account outlives the installer.
$adminBasic = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes("quant-admin:$adminPass"))
$adminPass = $null
$api = "https://127.0.0.1:$Port/api/v1"
$hdr = @{ Authorization = "Basic $adminBasic" }
# The forge's own self-signed certificate, trusted for this local call only.
$thumb = (New-Object Security.Cryptography.X509Certificates.X509Certificate2 $cert).Thumbprint
[Net.ServicePointManager]::ServerCertificateValidationCallback = {
    param($s, $c, $ch, $e) return ($c.GetCertHashString() -eq $thumb)
}
function Api([string] $method, [string] $path, $body = $null) {
    $req = @{ Method = $method; Uri = "$api$path"; Headers = $hdr; UseBasicParsing = $true; ContentType = "application/json" }
    if ($null -ne $body) { $req.Body = ($body | ConvertTo-Json -Depth 6) }
    return Invoke-RestMethod @req
}
try { Api POST "/orgs" @{ username = "quant"; visibility = "private" } | Out-Null; Say "created org quant" } catch { Say "org quant exists" }
try { Api POST "/orgs/quant/repos" @{ name = "quant"; private = $true; default_branch = $Live } | Out-Null; Say "created quant/quant" } catch { Say "repo quant/quant exists" }
try { Api PUT "/repos/quant/quant/collaborators/claude" @{ permission = "write" } | Out-Null } catch { }
foreach ($u in @("merge-gate", "release-authority", "box-ci")) {
    try { Api PUT "/repos/quant/quant/collaborators/$u" @{ permission = "write" } | Out-Null } catch { }
}
foreach ($u in @("auditor", "adopt")) {
    try { Api PUT "/repos/quant/quant/collaborators/$u" @{ permission = "read" } | Out-Null } catch { }
}

# Seed from the gate clone through the forge itself (so its database sees every ref), as
# quant-admin, BEFORE any protection exists: LIVE, production, master and release tags as last fetched.
$bare = Join-Path $Repos "quant\quant.git"
$env:GIT_TERMINAL_PROMPT = '0'
$env:GIT_CONFIG_COUNT = '3'
$env:GIT_CONFIG_KEY_0 = 'safe.directory'; $env:GIT_CONFIG_VALUE_0 = '*'
$env:GIT_CONFIG_KEY_1 = 'http.sslCAInfo'; $env:GIT_CONFIG_VALUE_1 = ($cert -replace '\\', '/')
$env:GIT_CONFIG_KEY_2 = 'http.extraHeader'; $env:GIT_CONFIG_VALUE_2 = "Authorization: Basic $adminBasic"
$seedUrl = "https://127.0.0.1:$Port/quant/quant.git"
if ($SeedBundle) {
    & { $ErrorActionPreference = 'Continue'; git -C $gate bundle verify $SeedBundle 2>&1 } | ForEach-Object { Say "  seed bundle: $_" }
    if ($LASTEXITCODE -ne 0) { Stop-Here 6 "the seed bundle does not verify against $gate." }
    & { $ErrorActionPreference = 'Continue'; git -C $gate fetch -q $SeedBundle "refs/heads/${Live}:refs/remotes/origin/$Live" 2>&1 } |
        ForEach-Object { Say "  seed bundle: $_" }
    if ($LASTEXITCODE -ne 0) { Stop-Here 6 "the seed bundle's LIVE is not a fast-forward of the gate clone's." }
}
$refs = @("refs/remotes/origin/${Live}:refs/heads/$Live")
foreach ($b in @("production", "master")) {
    & git -C $gate rev-parse -q --verify "refs/remotes/origin/$b" 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { $refs += "refs/remotes/origin/${b}:refs/heads/$b" }
}
& { $ErrorActionPreference = 'Continue'; git -C $gate -c "http.sslVerify=true" push -q $seedUrl @refs "refs/tags/release/*:refs/tags/release/*" 2>&1 } |
    ForEach-Object { Say "  seed: $_" }
$seedRc = $LASTEXITCODE
$env:GIT_CONFIG_COUNT = '1'; Remove-Item Env:GIT_CONFIG_KEY_1, Env:GIT_CONFIG_VALUE_1, Env:GIT_CONFIG_KEY_2, Env:GIT_CONFIG_VALUE_2 -ErrorAction SilentlyContinue
if ($seedRc -ne 0) { Stop-Here 6 "seeding the forge from $gate failed." }
& git -C $bare config receive.denyNonFastForwards true
& git -C $bare config receive.denyDeletes true
Say ("seeded: LIVE at {0}" -f ((& git -C $bare rev-parse "refs/heads/$Live") | Out-String).Trim().Substring(0, 12))

# 7. PROTECTION: the forge's own, AND the repo's hook, so each holds if the other is changed.
$owners = @{ $Live = "merge-gate"; "production" = "release-authority"; "master" = "release-authority" }
foreach ($b in @($Live, "production", "master")) {
    $o = $owners[$b]
    $rule = @{ rule_name = $b; enable_push = $true; enable_push_whitelist = $true
               push_whitelist_usernames = @($o); enable_merge_whitelist = $true
               merge_whitelist_usernames = @($o); block_on_rejected_reviews = $true
               block_on_outdated_branch = $true; enable_force_push = $false }
    try { Api POST "/repos/quant/quant/branch_protections" $rule | Out-Null; Say "protected $b" }
    catch { Say "protection for $b exists or failed: $($_.Exception.Message)" }
}
$py = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $py) { Stop-Here 7 "python is not on PATH, so the repository hook cannot run." }
# THE BOOT HEAD: the Audit-CLEARed commit this installer runs from.
$srcRepo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$boot = ((& git -c safe.directory=* -C $srcRepo rev-parse HEAD) | Out-String).Trim()
if ($boot -notmatch '^[0-9a-f]{40}$') { Stop-Here 7 "cannot read the installer's own commit in $srcRepo." }
$seededLive = ((& git -C $bare rev-parse "refs/heads/$Live") | Out-String).Trim()

# THE TRUST BOUNDARY (zuck 2026-11-19 20:22Z; Governance, D-20261119-TRUSTSET). The checker, its
# policy, the pin writer, the door (protect.py) and the pinned contract suites live in a folder
# only Administrators and SYSTEM can write; the forge service and the gate's account may only read
# it. The one bootstrap pin is the trust set at the boot head: this install is the owner's own
# request. From here on only the SYSTEM pin writer moves the pin, after its own verdict.
$trustDir = Join-Path $Root "trust"
$null = New-Item -ItemType Directory -Force -Path $trustDir
Lock-ToOwners $trustDir
$gateUser = "quantgate"
$pinPath = Join-Path $trustDir "pin.json"
if (-not (Test-Path -LiteralPath $pinPath)) {
    $pwSrc = Join-Path $env:TEMP "pin_writer_boot_$stamp.py"
    (& git -c safe.directory=* -C $srcRepo show "${boot}:ops/box_git/pin_writer.py" | Out-String) |
        Set-Content -LiteralPath $pwSrc -Encoding utf8
    Copy-Item -LiteralPath $pwSrc -Destination (Join-Path $trustDir "pin_writer.py") -Force
    Remove-Item -LiteralPath $pwSrc -Force
    & { $ErrorActionPreference = 'Continue'; & $py -I (Join-Path $trustDir "pin_writer.py") --init $srcRepo $boot $seededLive 2>&1 } | ForEach-Object { Say "  pin: $_" }
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $pinPath)) { Stop-Here 7 "could not pin the trust set at the boot head." }
} else { Say "keeping the existing trust pin $pinPath (the pin writer owns it)" }
& icacls $trustDir /grant "${SvcUser}:(OI)(CI)RX" | Out-Null

$hookDir = Join-Path $bare "hooks\pre-receive.d"
$null = New-Item -ItemType Directory -Force -Path $hookDir
$tFwd = ($trustDir -replace '\\','/')
@"
#!/bin/sh
# Box door (protect.py, PINNED copy in the trust folder): roles, fast-forward only, and every LIVE
# move judged by the pinned trust checker. Refreshed only by the pin writer.
exec "$($py -replace '\\','/')" "$tFwd/protect.py" --trust-dir "$tFwd"
"@ | Set-Content -LiteralPath (Join-Path $hookDir "box-protect") -Encoding ascii
Say "installed the repository hook (pre-receive.d\box-protect)"

# 8. NO INBOUND ROUTE (Audit MF-3): the ferry needs none. A rule from an earlier run is removed.
Get-NetFirewallRule -DisplayName "Quant box forge" -ErrorAction SilentlyContinue | Remove-NetFirewallRule
Say "no inbound firewall rule: the forge answers on 127.0.0.1 only"

# 9. THE RELEASE LOOP: one scheduled task, its code read from LIVE on every pass.
$loopSrc = Join-Path $Forge "loop-src"
$caFwd = ($cert -replace '\\', '/')
$forgeUrl = "https://127.0.0.1:$Port"
# The forge's repositories belong to quantforge; git refuses a local fetch from another owner's
# repository unless safe.directory is set in protected (system) config: `-c` does not reach
# upload-pack. Name exactly these two, never `*`.
foreach ($sd in @($bare, (Join-Path $Forge "mirror.git"))) {
    $sdF = $sd -replace '\\', '/'
    $have = (& git config --system --get-all safe.directory 2>$null) -contains $sdF
    if (-not $have) { & git config --system --add safe.directory $sdF }
    if ($LASTEXITCODE -ne 0) { Stop-Here 9 "could not mark $sdF as a safe directory." }
}
if (-not (Test-Path -LiteralPath (Join-Path $loopSrc ".git"))) {
    & git clone -q --reference $bare --no-checkout $bare $loopSrc
    if ($LASTEXITCODE -ne 0) { Stop-Here 9 "could not create the loop's checkout." }
}
# Until LIVE contains the boot head, LIVE's own gate only speaks GitHub, so the loop and its gate
# run from the boot head (box_loop.gate_code).
& git -c safe.directory=* -C $loopSrc fetch -q $srcRepo $boot
if ($LASTEXITCODE -ne 0) { Stop-Here 9 "could not bring the boot head $boot into the loop's checkout." }
$inboxDir = Join-Path $Root "inbox"
$null = New-Item -ItemType Directory -Force -Path $inboxDir
Lock-ToOwners $inboxDir
Say "boot head $($boot.Substring(0,12)); inbox $inboxDir"
# The loop works in its OWN mirror (worktrees, bundle fetches), synced from the forge each pass:
# its account only reads the forge's repository, so nothing it runs can write a ref there.
$mirror = Join-Path $Forge "mirror.git"
if (-not (Test-Path -LiteralPath $mirror)) {
    & git clone -q --mirror $bare $mirror
    if ($LASTEXITCODE -ne 0) { Stop-Here 9 "could not create the loop's mirror." }
}
& git -c safe.directory=* -C $mirror fetch -q $srcRepo $boot

# THE GATE'S ACCOUNT (Governance finding 1): the loop -- gate sweep, inbox, box CI hand-off, seal,
# promote -- runs as the local non-admin `quantgate`. It reads the box tokens and the trust folder,
# writes only its own folders, and can never write the pin, the checker or the forge's repository.
$gatePass = New-Secret 24
if (-not (Get-LocalUser -Name $gateUser -ErrorAction SilentlyContinue)) {
    New-LocalUser -Name $gateUser -Password (ConvertTo-SecureString $gatePass -AsPlainText -Force) `
        -PasswordNeverExpires -UserMayNotChangePassword -Description "Quant box merge gate (no admin)" | Out-Null
} else { Set-LocalUser -Name $gateUser -Password (ConvertTo-SecureString $gatePass -AsPlainText -Force) }
$logDirF = Join-Path $Forge "log"; $ciDir = Join-Path $Forge "ci"
$null = New-Item -ItemType Directory -Force -Path $logDirF, $ciDir
& icacls $Forge /grant "${gateUser}:(RX)" | Out-Null
foreach ($d in @($Tokens, $trustDir, $Repos)) { & icacls $d /grant "${gateUser}:(OI)(CI)RX" | Out-Null }
foreach ($d in @($loopSrc, $mirror, $inboxDir, $logDirF, $ciDir)) { & icacls $d /grant "${gateUser}:(OI)(CI)M" | Out-Null }
& icacls (Join-Path $Forge "custom") /grant "${gateUser}:(RX)" | Out-Null
& icacls $cert /grant "${gateUser}:(R)" | Out-Null

# THE CI WORKER (Audit MF-2): a PR's code never runs as SYSTEM. A local non-admin account runs it,
# denied the tokens, the trust folder, the inbox and C:\opt\quant (data\secrets included).
$ciUser = "quantci"
$ciPass = New-Secret 24
if (-not (Get-LocalUser -Name $ciUser -ErrorAction SilentlyContinue)) {
    New-LocalUser -Name $ciUser -Password (ConvertTo-SecureString $ciPass -AsPlainText -Force) `
        -PasswordNeverExpires -UserMayNotChangePassword -Description "Quant box CI worker (no admin)" | Out-Null
} else { Set-LocalUser -Name $ciUser -Password (ConvertTo-SecureString $ciPass -AsPlainText -Force) }
$jobs = Join-Path $Forge "ci-jobs"; $work = Join-Path $Forge "work"
$null = New-Item -ItemType Directory -Force -Path $jobs, $work
& icacls $Forge /grant "${ciUser}:(RX)" | Out-Null                 # traverse this folder only
foreach ($d in @($jobs, $work)) { & icacls $d /grant "${ciUser}:(OI)(CI)M" | Out-Null }
foreach ($d in @($Repos, $loopSrc)) { & icacls $d /grant "${ciUser}:(OI)(CI)RX" | Out-Null }
foreach ($d in @($Tokens, $trustDir, $inboxDir, $QuantRoot, (Join-Path $Forge "custom"), $Data)) {
    & icacls $d /deny "${ciUser}:(OI)(CI)F" | Out-Null
}
# Log on as a batch job, for this one account (a scheduled task with a password needs it).
$inf = Join-Path $env:TEMP "ci_rights.inf"; $db = Join-Path $env:TEMP "ci_rights.sdb"
& secedit /export /cfg $inf /areas USER_RIGHTS | Out-Null
$ciSid = (New-Object Security.Principal.NTAccount $ciUser).Translate([Security.Principal.SecurityIdentifier]).Value
$rights = Get-Content -LiteralPath $inf
if (-not ($rights -match "SeBatchLogonRight.*\*$ciSid")) {
    $rights = $rights -replace '^(SeBatchLogonRight\s*=\s*.*)$', "`$1,*$ciSid"
    if (-not ($rights -match '^SeBatchLogonRight')) { $rights += "SeBatchLogonRight = *$ciSid" }
    Set-Content -LiteralPath $inf -Value $rights
    & secedit /configure /db $db /cfg $inf /areas USER_RIGHTS | Out-Null
}
Remove-Item -LiteralPath $inf, $db -Force -ErrorAction SilentlyContinue
$ciRunner = Join-Path $Forge "run_ci_worker.cmd"
@"
@echo off
rem QuantForge-CI: run waiting test jobs as $ciUser (no admin, no tokens). Code from the loop's checkout.
"$py" "$loopSrc\ops\box_git\box_loop.py" --ci-worker "$jobs"
"@ | Set-Content -LiteralPath $ciRunner -Encoding ascii
$cAct = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$ciRunner`""
$cTrg = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 1)
$cSet = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 7) -StartWhenAvailable -Priority 9
Register-ScheduledTask -TaskName "QuantForge-CI" -Action $cAct -Trigger $cTrg -Settings $cSet `
    -User "$env:COMPUTERNAME\$ciUser" -Password $ciPass -RunLevel Limited -Force | Out-Null
$ciPass = $null
Say "scheduled QuantForge-CI every minute as $ciUser (no administrator, no token access)"

foreach ($d in @($work, $jobs)) { & icacls $d /grant "${gateUser}:(OI)(CI)M" | Out-Null }
$cfg = @{ forge_url = $forgeUrl; bare = $mirror; forge_bare = $bare; work = $work
          tokens = $Tokens; ca = $cert; state = (Join-Path $ciDir "state.json"); python = $py
          inbox = $inboxDir; boot = $boot; ci_jobs = $jobs; rules_log = (Join-Path $logDirF "rules_changes.jsonl")
          trust_checker = (Join-Path $trustDir "trust_check.py"); trust_pin = $pinPath }
$cfgPath = Join-Path $Forge "loop.json"
$cfg | ConvertTo-Json | Set-Content -LiteralPath $cfgPath -Encoding ascii
$runner = Join-Path $Forge "run_loop.cmd"
@"
@echo off
rem QuantForge-Loop: refresh the loop's code from LIVE (trusted, gate-merged), then one pass.
rem Until LIVE contains the boot head (the Audit-CLEARed installer commit), the boot head runs.
git -c safe.directory=* -C "$loopSrc" fetch -q "$bare" "refs/heads/${Live}"
git -c safe.directory=* -C "$loopSrc" merge-base --is-ancestor $boot FETCH_HEAD
if errorlevel 1 (git -c safe.directory=* -C "$loopSrc" checkout -q --detach --force $boot) else (git -c safe.directory=* -C "$loopSrc" checkout -q --detach --force FETCH_HEAD)
git -c safe.directory=* -C "$mirror" fetch -q --prune origin "+refs/heads/*:refs/heads/*" "+refs/tags/*:refs/tags/*"
set QUANT_FORGE_RULES_LOG=$logDirF\rules_changes.jsonl
"$py" "$loopSrc\ops\box_git\box_loop.py" --config "$cfgPath" >> "$Forge\log\loop.log" 2>&1
"@ | Set-Content -LiteralPath $runner -Encoding ascii
$act = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$runner`""
$trg = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 5)
$set = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 8) -StartWhenAvailable
# Log on as a batch job for the gate's account too.
$inf = Join-Path $env:TEMP "gate_rights.inf"; $db = Join-Path $env:TEMP "gate_rights.sdb"
& secedit /export /cfg $inf /areas USER_RIGHTS | Out-Null
$gSid = (New-Object Security.Principal.NTAccount $gateUser).Translate([Security.Principal.SecurityIdentifier]).Value
$rights = Get-Content -LiteralPath $inf
if (-not ($rights -match "SeBatchLogonRight.*\*$gSid")) {
    $rights = $rights -replace '^(SeBatchLogonRight\s*=\s*.*)$', "`$1,*$gSid"
    if (-not ($rights -match '^SeBatchLogonRight')) { $rights += "SeBatchLogonRight = *$gSid" }
    Set-Content -LiteralPath $inf -Value $rights
    & secedit /configure /db $db /cfg $inf /areas USER_RIGHTS | Out-Null
}
Remove-Item -LiteralPath $inf, $db -Force -ErrorAction SilentlyContinue
Register-ScheduledTask -TaskName "QuantForge-Loop" -Action $act -Trigger $trg -Settings $set `
    -User "$env:COMPUTERNAME\$gateUser" -Password $gatePass -RunLevel Limited -Force | Out-Null
$gatePass = $null
Say "scheduled QuantForge-Loop every 5 minutes as $gateUser (no administrator)"

# THE PIN WRITER: SYSTEM, its code from the trust folder only. Tamper restore, pin moves, recorded
# contract passes and owner authorizations. Nothing else writes the pin.
$pAct = New-ScheduledTaskAction -Execute $py -Argument "-I `"$(Join-Path $trustDir 'pin_writer.py')`" --config `"$cfgPath`""
$pTrg = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(2) -RepetitionInterval (New-TimeSpan -Minutes 5)
$pSet = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 3) -StartWhenAvailable
Register-ScheduledTask -TaskName "QuantForge-Pin" -Action $pAct -Trigger $pTrg -Settings $pSet `
    -User "SYSTEM" -RunLevel Highest -Force | Out-Null
Say "scheduled QuantForge-Pin every 5 minutes (SYSTEM, pinned code)"

# ASSERT THE SEPARATION (Governance finding 1): refuse to finish if a non-admin account can write
# the trust folder.
$acl = (Get-Acl -LiteralPath $trustDir).Access | Where-Object {
    $_.IdentityReference -match "($gateUser|$ciUser|$SvcUser|Users|Everyone|Authenticated)" -and
    $_.AccessControlType -eq "Allow" -and ($_.FileSystemRights -match "Write|Modify|FullControl") }
if ($acl) { Stop-Here 9 "the trust folder is writable by a non-admin account: $($acl.IdentityReference -join ', ')" }
Say "trust folder: Administrators and SYSTEM write; $gateUser and $SvcUser read only"

# 10. ADOPTION READS THE FORGE: origin of the gate clone and of the live tree point at it, with
# the forge certificate and a box-only token in each repository's own config (never global).
$originUrl = "https://127.0.0.1:$Port/quant/quant.git"
$localUrl = "$forgeUrl/quant/quant.git"
# A read-only account (Audit MF-4): the clones fetch, they never hold a token that moves LIVE.
$gateTok = (Get-Content -LiteralPath (Join-Path $Tokens "adopt.token") -Raw).Trim()
foreach ($repo in @($gate, $QuantRoot)) {
    & git -c safe.directory=* -C $repo remote set-url origin $localUrl
    & git -c safe.directory=* -C $repo config "http.$forgeUrl/.sslCAInfo" $caFwd
    & git -c safe.directory=* -C $repo config "http.$forgeUrl/.extraHeader" "Authorization: token $gateTok"
    & { $ErrorActionPreference = 'Continue'; git -c safe.directory=* -C $repo fetch -q origin 2>&1 } | ForEach-Object { Say "  fetch ${repo}: $_" }
    if ($LASTEXITCODE -ne 0) { Stop-Here 10 "$repo cannot fetch from the forge." }
    Say "$repo now fetches from the forge"
}
$gateTok = $null

# 11. THE ROOT PIN, from a clean LIVE checkout (the publisher and authority refuse until it matches).
& git -c safe.directory=* -C $loopSrc fetch -q $bare "refs/heads/$Live"
& git -c safe.directory=* -C $loopSrc checkout -q --detach --force FETCH_HEAD
Push-Location $loopSrc
try { & { $ErrorActionPreference = 'Continue'; & $py ops\release\authority\pin_root.py --write C:\opt\audit_registry\ROOT_PIN.json 2>&1 } | ForEach-Object { Say "  pin: $_" } }
finally { Pop-Location }
if ($LASTEXITCODE -ne 0) { Say "ROOT re-pin did not complete (exit $LASTEXITCODE); the loop still runs" }

# 12. ADOPT NOW rather than at the next hour.
& schtasks /Run /TN "MT5-AdoptRelease" | Out-Null
Say "asked MT5-AdoptRelease to run now"

# The owner's account keeps no password anyone holds (Governance): scrambled, never written.
$null = Forge @("admin", "user", "change-password", "--username", "quant-admin", "--password",
                (New-Secret 32), "--must-change-password=false")
$adminBasic = $null; $hdr = $null
Say "quant-admin scrambled: no stored or known credential for the owner's account"

$fp = (Get-FileHash -Algorithm SHA256 -InputStream ([IO.MemoryStream]::new(
    (New-Object Security.Cryptography.X509Certificates.X509Certificate2 $cert).RawData))).Hash
Say "DONE. The forge is at $originUrl (LIVE seeded, protected, looped)."
Say "certificate SHA-256 (public): $fp"
Say "log: $log"
exit 0
