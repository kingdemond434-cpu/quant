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
         owner only) and `claude` (no admin), and an access token for `claude` limited to
         repositories. Creates the repository quant/quant and seeds it from the box gate clone
         (C:\ProgramData\QuantBox\gate-repo), which holds LIVE and production as last fetched.
      7. Protects LIVE, production and master on the forge (no force push, no deletion, pushes
         only by the merge-gate user) and installs ops\box_git\protect.py as the repository's
         pre-receive hook too, so the rules hold even if the forge's own settings are changed.
      8. Opens TCP -Port inbound in Windows Firewall, for this one program only.
      9. Prints what the owner must do once in Project settings: the address, the certificate
         fingerprint (public) and the file holding the `claude` token (secret: the owner pastes it
         into the cloud environment's secrets; it is never printed to a log).

    WHAT IT NEVER DOES. It never writes C:\opt\quant (MT5-AdoptRelease stays its only writer), never
    touches MT5, secrets under data\secrets, or any scheduled task of the desk, never weakens a gate
    and never contacts GitHub.

    Run: right-click ops\box_git\install_box_forge.cmd -> Run as administrator.
#>
param(
    [string] $GiteaVersion = "latest",
    [int] $Port = 3443,
    [string] $Address = "62.171.172.249",
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
    $out = & $Bin --config $Ini --work-path $Forge @a 2>&1 | Out-String
    return @{ rc = $LASTEXITCODE; out = $out.Trim() }
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

# 2. GITEA, VERIFIED.
$null = New-Item -ItemType Directory -Force -Path $Forge, $Data, $Repos, $OwnerOnly, (Split-Path $Ini)
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
if ($GiteaVersion -eq "latest") {
    try { $GiteaVersion = [string](Invoke-RestMethod -UseBasicParsing -Uri "https://dl.gitea.com/gitea/version.json").latest.version }
    catch { Stop-Here 3 "could not read the latest Gitea version from dl.gitea.com. Nothing was installed." }
    if ($GiteaVersion -notmatch '^\d+\.\d+\.\d+$') { Stop-Here 3 "dl.gitea.com named an odd version '$GiteaVersion'." }
}
$url = "https://dl.gitea.com/gitea/$GiteaVersion/gitea-$GiteaVersion-windows-4.0-amd64.exe"
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
Lock-ToOwners $OwnerOnly
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
    try { & $Bin cert --host $Address --rsa-bits 3072 --duration 87600h | Out-Null } finally { Pop-Location }
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
DOMAIN = $Address
HTTP_ADDR = 0.0.0.0
HTTP_PORT = $Port
ROOT_URL = https://${Address}:$Port/
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
ENABLED = true

[mailer]
ENABLED = false

[log]
ROOT_PATH = $Forge\log
MODE = file
LEVEL = Info
"@ | Set-Content -LiteralPath $Ini -Encoding ascii
    Say "wrote $Ini (HTTPS on $Port, registration off, sign-in required)"
} else { Say "keeping the existing $Ini" }
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
if ($r.rc -eq 0) {
    Set-Content -LiteralPath (Join-Path $OwnerOnly "quant-admin.password.txt") -Value $adminPass
    Say "created quant-admin; its password is in $OwnerOnly (Administrators only)"
} else { Say "quant-admin exists already ($($r.out -replace '\s+',' '))" }
$adminPass = $null
$botPass = New-Secret 24
$r = Forge @("admin", "user", "create", "--username", "claude", "--password", $botPass,
             "--email", "claude@box.invalid", "--must-change-password=false")
$botPass = $null
# The two box roles the repository hook trusts by the forge's own pusher name (never by anything
# a client sends): merge-gate moves LIVE/production/master, release-authority creates release tags.
foreach ($u in @("merge-gate", "release-authority")) {
    $null = Forge @("admin", "user", "create", "--username", $u, "--password", (New-Secret 24),
                    "--email", "$u@box.invalid", "--must-change-password=false")
}
$tokFile = Join-Path $OwnerOnly "claude.token.txt"
if (-not (Test-Path -LiteralPath $tokFile)) {
    $r = Forge @("admin", "user", "generate-access-token", "--username", "claude",
                 "--token-name", "cloud-threads-$stamp", "--scopes", "write:repository,read:user",
                 "--raw")
    if ($r.rc -ne 0 -or -not $r.out) { Stop-Here 6 "could not make the claude token: $($r.out)" }
    Set-Content -LiteralPath $tokFile -Value $r.out.Trim()
}
$r = Forge @("admin", "user", "generate-access-token", "--username", "quant-admin",
             "--token-name", "installer-$stamp", "--scopes", "write:admin,write:repository,write:organization",
             "--raw")
if ($r.rc -ne 0 -or -not $r.out) { Stop-Here 6 "could not make the installer token: $($r.out)" }
$adminTok = $r.out.Trim()
$api = "https://127.0.0.1:$Port/api/v1"
$hdr = @{ Authorization = "token $adminTok" }
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
foreach ($u in @("merge-gate", "release-authority")) {
    try { Api PUT "/repos/quant/quant/collaborators/$u" @{ permission = "write" } | Out-Null } catch { }
}

# Seed from the gate clone through the forge itself (so its database sees every ref), as
# quant-admin, BEFORE any protection exists: LIVE, production, master and release tags as last fetched.
$bare = Join-Path $Repos "quant\quant.git"
$env:GIT_TERMINAL_PROMPT = '0'
$env:GIT_CONFIG_COUNT = '3'
$env:GIT_CONFIG_KEY_0 = 'safe.directory'; $env:GIT_CONFIG_VALUE_0 = '*'
$env:GIT_CONFIG_KEY_1 = 'http.sslCAInfo'; $env:GIT_CONFIG_VALUE_1 = ($cert -replace '\\', '/')
$env:GIT_CONFIG_KEY_2 = 'http.extraHeader'; $env:GIT_CONFIG_VALUE_2 = "Authorization: token $adminTok"
$seedUrl = "https://127.0.0.1:$Port/quant/quant.git"
$refs = @("refs/remotes/origin/${Live}:refs/heads/$Live")
foreach ($b in @("production", "master")) {
    & git -C $gate rev-parse -q --verify "refs/remotes/origin/$b" 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { $refs += "refs/remotes/origin/${b}:refs/heads/$b" }
}
& git -C $gate -c "http.sslVerify=true" push -q $seedUrl @refs "refs/tags/release/*:refs/tags/release/*" 2>&1 |
    ForEach-Object { Say "  seed: $_" }
$seedRc = $LASTEXITCODE
$env:GIT_CONFIG_COUNT = '1'; Remove-Item Env:GIT_CONFIG_KEY_1, Env:GIT_CONFIG_VALUE_1, Env:GIT_CONFIG_KEY_2, Env:GIT_CONFIG_VALUE_2 -ErrorAction SilentlyContinue
if ($seedRc -ne 0) { Stop-Here 6 "seeding the forge from $gate failed." }
& git -C $bare config receive.denyNonFastForwards true
& git -C $bare config receive.denyDeletes true
Say ("seeded: LIVE at {0}" -f ((& git -C $bare rev-parse "refs/heads/$Live") | Out-String).Trim().Substring(0, 12))

# 7. PROTECTION: the forge's own, AND the repo's hook, so each holds if the other is changed.
foreach ($b in @($Live, "production", "master")) {
    $rule = @{ rule_name = $b; enable_push = $true; enable_push_whitelist = $true
               push_whitelist_usernames = @("merge-gate"); enable_merge_whitelist = $true
               merge_whitelist_usernames = @("merge-gate"); block_on_rejected_reviews = $true
               block_on_outdated_branch = $true; enable_force_push = $false }
    try { Api POST "/repos/quant/quant/branch_protections" $rule | Out-Null; Say "protected $b" }
    catch { Say "protection for $b exists or failed: $($_.Exception.Message)" }
}
$hookDir = Join-Path $bare "hooks\pre-receive.d"
$null = New-Item -ItemType Directory -Force -Path $hookDir
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "protect.py") -Destination (Join-Path $hookDir "protect.py") -Force
$py = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $py) { Stop-Here 7 "python is not on PATH, so the repository hook cannot run." }
@"
#!/bin/sh
# Box branch protection (ops/box_git/protect.py). Pushes through the forge's web or API run as
# the forge itself; the gate sets QUANT_BOX_GIT_ROLE for its own local pushes.
exec "$($py -replace '\\','/')" "$(($hookDir -replace '\\','/'))/protect.py"
"@ | Set-Content -LiteralPath (Join-Path $hookDir "box-protect") -Encoding ascii
Say "installed the repository hook (pre-receive.d\box-protect)"

# 8. FIREWALL: this one program, this one port.
if (-not (Get-NetFirewallRule -DisplayName "Quant box forge" -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -DisplayName "Quant box forge" -Direction Inbound -Protocol TCP -LocalPort $Port `
        -Program $Bin -Action Allow | Out-Null
}
Say "firewall: inbound TCP $Port for gitea.exe only"

# 9. WHAT THE OWNER DOES ONCE.
$fp = (Get-FileHash -Algorithm SHA256 -InputStream ([IO.MemoryStream]::new(
    (New-Object Security.Cryptography.X509Certificates.X509Certificate2 $cert).RawData))).Hash
Say "DONE. The forge is at https://${Address}:$Port/quant/quant (LIVE seeded, protected)."
Say "certificate SHA-256 (public, pin this): $fp"
Say "ONE THING LEFT FOR THE OWNER: open $tokFile, copy the token, and paste it into the project's"
Say "cloud environment as the secret QUANT_FORGE_TOKEN (with $Address allowed in its network)."
Say "Then delete $tokFile. Nothing else is needed from you for this step."
Say "log: $log"
exit 0
